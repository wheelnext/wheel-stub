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

import sys

if sys.version_info[:3] < (3, 8, 0):  # noqa: UP036
    raise RuntimeError("NVIDIA Software requires Python 3.8+")

import pathlib

from wheel_stub.sdist import SDistBuilder
from wheel_stub.wheel import download_wheel


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    """PEP 517 entrypoint to 'build' a wheel, which we actually just download from pypi.nvidia.com."""
    return download_wheel(pathlib.Path(wheel_directory), config_settings)


def build_sdist(sdist_directory, config_settings=None):
    """PEP 517 entrypoint to build a source distribution from a wheel path.

    We really only care about the wheel's METADATA file to turn into a PKG-INFO file for the
    sdist and get the information needed for downloading the wheel from the NVIDIA Python Package Index.
    """
    return SDistBuilder(pathlib.Path(sdist_directory), config_settings).build().name
