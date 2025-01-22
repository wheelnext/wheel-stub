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

import pathlib
import re
import shutil
import subprocess
import sys

import py.path
import pytest
from packaging.utils import parse_wheel_filename
from test_util import BASE_DIR, sample_wheels_and_sdists


def run_build(wheel, tmpdir, **kwargs):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--sdist",
            f"--config-setting=source_wheel={wheel.name}",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=tmpdir,
        **kwargs,
    )


@pytest.mark.skipif(
    sys.version_info < (3, 9), reason="Tar creation changed in Python 3.9."
)
@pytest.mark.parametrize("wheel,expected_sdist", sample_wheels_and_sdists())
def test_sdist_from_wheel(
    wheel, expected_sdist, pyproject_toml_temp_dir, build_backend_wheel
):
    shutil.copy(BASE_DIR / wheel, pyproject_toml_temp_dir)
    # PIP_NO_INDEX makes sure we pull the wheel-stub wheel from the local path via PIP_FIND_LINKS
    proc = run_build(
        wheel,
        tmpdir=pyproject_toml_temp_dir,
        env={"PIP_FIND_LINKS": build_backend_wheel.parent, "PIP_NO_INDEX": "1"},
    )
    distribution, version, *_ = parse_wheel_filename(pathlib.Path(wheel).name)
    artifact = f"{distribution.replace('-', '_')}-{version}.tar.gz"
    assert re.search(
        rf"Successfully built {artifact}",
        proc.stdout,
    ), "Did not build the sdist!"
    built_sha = (
        pyproject_toml_temp_dir.join("dist")
        .join(artifact)
        .computehash(hashtype="sha256")
    )
    pypi_sha = py.path.local(expected_sdist).computehash(hashtype="sha256")
    assert built_sha == pypi_sha, "File hashes did not match!"


@pytest.mark.parametrize(
    "wheel",
    [
        "invalid_files/this-wheel-invalid.whl",
        "invalid_files/nvidia_cuda_runtime_cu12-12.1.105-py3-none-manylinux1_x86_64.whl",
    ],
)
def test_sdist_fails_invalid_wheel(wheel, pyproject_toml_temp_dir, build_backend_wheel):
    shutil.copy(BASE_DIR / wheel, pyproject_toml_temp_dir)
    with pytest.raises(subprocess.CalledProcessError):
        run_build(
            BASE_DIR / wheel,
            tmpdir=pyproject_toml_temp_dir,
            env={"PIP_FIND_LINKS": build_backend_wheel.parent, "PIP_NO_INDEX": "1"},
        )
