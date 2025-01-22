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

import hashlib
import logging
import os
import pathlib
import sys
import time
import warnings
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

if sys.version_info >= (3, 11):
    import tomllib
else:
    import wheel_stub._vendor.tomli as tomllib

from wheel_stub._vendor.packaging.tags import (
    interpreter_name,
    interpreter_version,
    platform_tags,
)
from wheel_stub._vendor.packaging.utils import canonicalize_name, parse_wheel_filename
from wheel_stub.common import parse_metadata
from wheel_stub.error import report_install_failure

logging.basicConfig()
logger = logging.getLogger("wheel-stub")
log_level = os.getenv("WHEEL_STUB_LOGLEVEL", "INFO").upper()
try:
    logger.setLevel(log_level)
except ValueError:
    warnings.warn(f"Bad user supplied log level: {log_level}; falling back to INFO")
    log_level = "INFO"
    logger.setLevel(log_level)

WHEEL_STUB_PIP_INDEX_URL = os.environ.get("WHEEL_STUB_PIP_INDEX_URL", None)
WHEEL_STUB_NO_PIP = os.environ.get("WHEEL_STUB_NO_PIP", False)


class WheelFilter(HTMLParser):
    """Parse PEP 503 project index page to get the list of wheels and their hash."""

    def __init__(
        self, *, convert_charrefs: bool = True, project_url: str = None
    ) -> None:
        super().__init__(convert_charrefs=convert_charrefs)
        self.wheel_files = []
        self.project_url = project_url

    def handle_starttag(self, tag, attrs) -> None:
        if tag == "a":
            for name, value in attrs:
                if name == "href" and value is not None:
                    parsed = urlparse(value)
                    if not parsed.path.endswith(".whl"):
                        continue
                    # TODO: is there a better heurisitc for this?
                    if parsed.fragment[:3] in ("md5", "sha"):
                        scheme, hash = parsed.fragment.split("=")
                    else:
                        scheme, hash = None, None
                    wheel_filename = os.path.basename(parsed.path)
                    # Empty netloc means relative URL
                    if not parsed.netloc:
                        wheel_url = urljoin(self.project_url, parsed.path)
                    else:
                        wheel_url = value
                    logger.debug("Found wheel: %s", wheel_filename)
                    self.wheel_files.append((wheel_url, wheel_filename, (scheme, hash)))


def urlopen_with_retry(url, num_retries=4, **kwargs):
    """Retry HTTP call with backoff"""
    for i in range(1, num_retries + 1):
        try:
            return urlopen(url, **kwargs)
        except URLError:
            if i == num_retries:
                raise
        time.sleep(1.2**i)


def is_compatible_tag(tag, this_interp_tag, system_tags):
    if tag.abi == "none":
        if tag.interpreter in ["py3", this_interp_tag]:
            logger.debug("Wheel is ABI generic.")
            if tag.platform in system_tags:
                return True
            logger.debug("Skipping tag because the platform tag is incompatible.")
            return False
        else:
            logger.debug(
                "Skipping tag because of incompatible interpreter tag for ABI generic wheel."
            )
            return False
    elif tag.abi == this_interp_tag:
        # If the ABI is for this interpreter, the interpreter tag must be this interpreters
        if tag.interpreter != this_interp_tag:
            logger.debug(
                "Skipping tag because of incompatible interpreter tag for Python ABI."
            )
            return False
    elif tag.abi == "abi3":
        # Any interpreter abi less than ours is acceptable for the stable ABI
        wheel_interp = tag.interpreter
        if wheel_interp.startswith("cp3"):
            interp_minor_version = wheel_interp[3:]
            if int(interp_minor_version) > sys.version_info.minor:
                logger.debug("Skipping tag because abi3 interpreter tag is too new.")
                return False
        else:
            logger.debug("Skipping tag because abi3 interpreter tag is incorrect.")
            return False
    elif tag.abi != this_interp_tag:
        logger.debug("Skipping tag because ABI tag does not match the interpreter tag.")
        return False
    if tag.platform in system_tags:
        return True
    logger.debug("Skipping tag because the platform tag is incompatible.")
    return False


def get_compatible_wheel(wheel_files, version):
    system_tags = list(platform_tags()) + ["any"]
    interp_name = interpreter_name()
    interp_version = interpreter_version()
    this_interp_tag = f"{interp_name}{interp_version}"
    for wheel_url, wheel_filename, hash in wheel_files:
        _name, ver, _build_num, tags = parse_wheel_filename(wheel_filename)
        if str(ver) != version:
            continue
        # tags is a frozenset since there *can* be compressed tags,
        # e.g. manylinux2014_x86_64.manylinux_2_28_x86_64

        for tag in tags:
            logger.info("Testing wheel %s against tag %s", wheel_filename, tag)
            if is_compatible_tag(tag, this_interp_tag, system_tags):
                return wheel_url, wheel_filename, hash
    return None, None, (None, None)


def get_base_domain(config):
    """Get base domain for remote index based on environment variables and config"""
    index_url = config.get("index_url", None)
    if WHEEL_STUB_PIP_INDEX_URL:
        index_url = WHEEL_STUB_PIP_INDEX_URL
    if index_url and not index_url.endswith("/"):
        index_url += "/"
    return index_url


def download_manual(wheel_directory, distribution, version, config):
    base_domain = get_base_domain(config)
    logger.debug(f"Calculated base domain: {base_domain}")
    project_url = f"{urljoin(base_domain, distribution)}/"
    logger.debug(f"Querying project url: {project_url}")
    try:
        index_response = urlopen_with_retry(project_url)
    except HTTPError as e:
        raise RuntimeError(f"Failed to open project URL {project_url}") from e
    html = index_response.read().decode("utf-8")
    parser = WheelFilter(project_url=project_url)
    parser.feed(html)
    # TODO: should we support multiple compatible wheels?
    wheel_url, wheel_filename, (scheme, hash) = get_compatible_wheel(
        parser.wheel_files, version
    )
    if wheel_url is None:
        raise RuntimeError(f"Didn't find wheel for {distribution} {version}")
    logger.info(f"Downloading wheel {wheel_filename}")
    try:
        wheel_response = urlopen_with_retry(wheel_url)
    except HTTPError as e:
        raise RuntimeError(f"Failed to open wheel URL {wheel_url}") from e

    # Only check the hash if we have one and know the scheme
    if scheme is not None and hash is not None:
        try:
            file_hash = getattr(hashlib, scheme.lower())()
        except AttributeError:
            raise RuntimeError(
                f"Hash algorithm {scheme} is unsupported on this Python."
            ) from None
    else:
        file_hash = None
    with open(wheel_directory / wheel_filename, "wb") as f:
        CHUNK = 16 * 1024
        while True:
            data = wheel_response.read(CHUNK)
            if not data:
                break
            if file_hash is not None:
                file_hash.update(data)
            f.write(data)
    if file_hash is not None:
        assert (
            file_hash.hexdigest() == hash
        ), f"Downloaded wheel and {scheme} don't match! {file_hash.hexdigest()}, {hash}"
    return wheel_filename


def get_metadata_from_pkg_info(src_dir):
    with open(src_dir / "PKG-INFO") as f:
        pkg_info = f.read()
    return parse_metadata(pkg_info)


def get_config_from_pyprojecttoml(src_dir):
    with open(src_dir / "pyproject.toml", "rb") as f:
        toml_dict = tomllib.load(f)
    try:
        tool_dict = toml_dict["tool"]
        wheel_stub_dict = tool_dict["wheel_stub"]
    except KeyError:
        raise RuntimeError(
            "Missing [tool.wheel_stub] section in pyproject.toml"
        ) from None
    return wheel_stub_dict


def download_wheel(wheel_directory, config_settings):
    src_dir = pathlib.Path(os.getcwd())
    metadata = get_metadata_from_pkg_info(src_dir)
    config = get_config_from_pyprojecttoml(src_dir)
    distribution = canonicalize_name(metadata["Name"])
    version = metadata["Version"]
    if config.get("stub_only", None):
        report_install_failure(distribution, version, config, None)
    try:
        return download_manual(wheel_directory, distribution, version, config)
    except Exception as exception_context:
        report_install_failure(distribution, version, config, exception_context)
