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

import functools
import glob
import pathlib

from packaging.utils import parse_wheel_filename

BASE_DIR = pathlib.Path(__file__).parent


@functools.lru_cache
def sample_wheels_and_sdists():
    """Return a list of pairs of input wheels and their expected output sdist files."""
    pypi_simple = BASE_DIR / "pypi_simple" / "root"
    stub_pypi_simple = BASE_DIR / "stub_pypi_simple" / "root"
    result = []
    for file in glob.glob(f"{stub_pypi_simple}/**/*.whl"):
        distribution, version, *_ = parse_wheel_filename(pathlib.Path(file).name)
        sdist = (
            pypi_simple
            / distribution
            / f"{distribution.replace('-', '_')}-{version}.tar.gz"
        )
        if sdist.exists():
            result.append((pathlib.Path(file), sdist))
        else:
            raise RuntimeError(f"No sdist found at {sdist}")
    assert len(result) > 0, pypi_simple
    return result
