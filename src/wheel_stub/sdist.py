# SPDX-FileCopyrightText: Copyright (c) 2024 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import gzip
import io
import os
import pathlib
import sys
import tarfile
import zipfile
from io import BytesIO

if sys.version_info >= (3, 11):
    import tomllib
else:
    import wheel_stub._vendor.tomli as tomllib

from wheel_stub._vendor.packaging.utils import (
    parse_sdist_filename,
    parse_wheel_filename,
)
from wheel_stub.common import parse_metadata


def replace_underscore(name):
    return name.replace("-", "_")


def normalize_tarinfo(tarinfo, mtime):
    tarinfo.uid = 0
    tarinfo.gid = 0
    tarinfo.uname = ""
    tarinfo.gname = ""
    tarinfo.mtime = mtime
    if tarinfo.type == tarfile.DIRTYPE:
        tarinfo.mode = 0o775
    elif tarinfo.mode & 0o100:
        tarinfo.mode = 0o755
    else:
        tarinfo.mode = 0o644
    return tarinfo


class SDistBuilder:
    def __init__(self, target_directory, config_settings) -> None:
        if "source_wheel" not in config_settings:
            raise RuntimeError(
                "Must pass --config-setting source_wheel=./path/to/wheel_file.whl when building an sdist"
            )
        self.target_directory = pathlib.Path(target_directory)
        os.makedirs(self.target_directory, exist_ok=True)
        self.source_wheel = config_settings["source_wheel"]
        if not os.path.exists(self.source_wheel):
            raise FileNotFoundError(f"Could not find {self.source_wheel}")

        if self.source_wheel.endswith(".whl"):
            self.distribution, self.version, _build_tag, _tags = parse_wheel_filename(
                os.path.basename(self.source_wheel)
            )
        elif self.source_wheel.endswith(".tar.gz"):
            self.distribution, self.version = parse_sdist_filename(
                os.path.basename(self.source_wheel)
            )
        else:
            raise RuntimeError(f"Unknown package type {self.source_wheel}")

    def build(self):
        base_dir = pathlib.Path(os.getcwd())
        sdist = (
            self.target_directory
            / f"{replace_underscore(self.distribution)}-{self.version}.tar.gz"
        )
        pyproject_toml_path = base_dir / "pyproject.toml"
        # Make sdist generation reproducible, setting the dates to SOURCE_DATE_EPOCH or April 5, 1993
        source_date = os.getenv("SOURCE_DATE_EPOCH")
        if source_date is not None:
            mtime = int(source_date)
        else:
            mtime = 733993200

        gz = gzip.GzipFile(sdist, mode="wb", mtime=mtime)
        tar = tarfile.TarFile(sdist, fileobj=gz, mode="w", format=tarfile.PAX_FORMAT)

        # There are two files we include in an sdist: the pyproject.toml, and PKG-INFO, which holds the metadata
        try:
            stub_only = False
            if self.source_wheel.endswith(".whl"):
                with zipfile.ZipFile(self.source_wheel, mode="r") as z:
                    with z.open(
                        f"{replace_underscore(self.distribution)}-{self.version}.dist-info/METADATA"
                    ) as metadata_file:
                        metadata_bytes = metadata_file.read()
            else:
                raise RuntimeError(
                    f"Unsupported package format for file {self.source_wheel}"
                )

            # Verify METADATA is valid
            parsed_metadata = parse_metadata(metadata_bytes.decode("utf-8"))
            try:
                self.assert_valid_metadata(parsed_metadata)
            except AssertionError as e:
                print(metadata_bytes.decode("utf-8"), file=sys.stderr)
                raise e
            requires_dists = parsed_metadata.get_all("Requires-Dist")
            if requires_dists is not None:
                for requires_dist in requires_dists:
                    # If the wheel has direct dependencies, the sdist can
                    # only act as a stub, the user should point pip etc. to pypi.nvidia.com
                    if "@" in requires_dist:
                        # We must delete the dependencies so the stub can be uploaded to PyPi
                        del parsed_metadata["Requires-Dist"]
                        stub_only = True
            # Make the sdist cross-platform
            del parsed_metadata["Platform"]
            del parsed_metadata["Supported-Platform"]
            pkg_info_bytes = str(parsed_metadata).encode("utf-8")

            sdist_dir = f"{replace_underscore(self.distribution)}-{self.version}"
            sdist_dir_tarinfo = tarfile.TarInfo(sdist_dir)
            sdist_dir_tarinfo.type = tarfile.DIRTYPE
            normalize_tarinfo(sdist_dir_tarinfo, mtime)
            tar.addfile(sdist_dir_tarinfo)

            pkg_info_tarinfo = tarfile.TarInfo(os.path.join(sdist_dir, "PKG-INFO"))
            pkg_info_tarinfo.size = len(pkg_info_bytes)
            pkg_info_tarinfo = normalize_tarinfo(pkg_info_tarinfo, mtime)
            pkg_info_fp = BytesIO(pkg_info_bytes)
            try:
                tar.addfile(pkg_info_tarinfo, fileobj=pkg_info_fp)
            finally:
                pkg_info_fp.close()

            # now that we know if the package is stub only, we can copy in the pyproject.toml file
            pyproj_tarinfo = tar.gettarinfo(
                name=pyproject_toml_path, arcname="pyproject.toml"
            )
            # Do not do a deep copy otherwise the file pointer will raise an error
            pyproj_tarinfo = pyproj_tarinfo.replace(
                name=os.path.join(sdist_dir, "pyproject.toml"), deep=False
            )
            pyproj_tarinfo = normalize_tarinfo(pyproj_tarinfo, mtime)
            with open(pyproject_toml_path, "rb") as f:
                toml_dict = tomllib.load(f)
                try:
                    tool_dict = toml_dict["tool"]
                    wheel_stub_dict = tool_dict["wheel_stub"]
                except KeyError:
                    raise RuntimeError(
                        "Missing [tool.wheel_stub] section in pyproject.toml"
                    ) from None
            if stub_only:
                if hasattr(wheel_stub_dict, "stub_only"):
                    if wheel_stub_dict["stub_only"]:
                        # already configured stub-only, we can just write the contents
                        with open(pyproject_toml_path, "rb") as f:
                            tar.addfile(pyproj_tarinfo, fileobj=f)
                    else:
                        raise RuntimeError(
                            "Cannot set [tool.wheel_stub].stub_only to false. Package depends on non-PyPi dependency."
                        )
                else:
                    with open(pyproject_toml_path, "rb") as f:
                        content = f.read()
                        # toml settings can exist in their own table
                        content += b"\n[tool.wheel_stub]\nstub_only = true\n"
                        pyproj_tarinfo = tarfile.TarInfo(
                            os.path.join(sdist_dir, "pyproject.toml")
                        )
                        pyproj_tarinfo.size = len(content)
                        pyproj_tarinfo = normalize_tarinfo(pyproj_tarinfo, mtime)
                        output = io.BytesIO(content)
                        try:
                            tar.addfile(pyproj_tarinfo, fileobj=output)
                        finally:
                            output.close()
            else:
                with open(pyproject_toml_path, "rb") as f:
                    tar.addfile(pyproj_tarinfo, fileobj=f)

        finally:
            tar.close()
            gz.close()
        return sdist

    def assert_valid_metadata(self, parsed):
        # Theser are required by the spec
        assert "Name" in parsed, "Must have a distribution name"
        assert "Version" in parsed, "Must have a version"
        # This is very important for releasing software on pypi.org
        assert "License" in parsed, "Software should have a license"
