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

import glob
import os
import pathlib
import shutil
import subprocess
import sys
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
from test_util import BASE_DIR

os.environ["WHEEL_STUB_LOGLEVEL"] = "DEBUG"

PYPROJECT_TOML_TEMPLATE = """
[build-system]
requires = ["wheel-stub"]
build-backend = "wheel_stub.buildapi"

[tool.wheel_stub]
index_url = "http://127.0.0.1:7001/"
include_cuda_debuginfo = true
"""

INDEX = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <title>Package Index</title>
  </head>
  <body>
    <a href="/wheel-stub/{0}">{0}</a><br>
  </body>
</html>
"""


@pytest.fixture(scope="session")
def docker_compose_command() -> str:
    return "docker-compose"


@pytest.fixture(scope="session")
def build_backend_wheel():
    root_dir = BASE_DIR.parent
    dist_dir = root_dir / "dist"
    subprocess.run(["hatch", "build", "-t", "wheel"], check=True, cwd=root_dir)
    wheels = list(glob.glob(f"{dist_dir}/wheel_stub-*.whl"))
    return pathlib.Path(wheels[0])


@pytest.fixture(scope="session")
def install_in_pypi(build_backend_wheel):
    """Install the build backend wheel in our pypi server"""
    pypi_simple = BASE_DIR / "pypi_simple" / "root"
    pkg_dir = pypi_simple / "wheel-stub"
    pkg_dir.mkdir(exist_ok=True)
    shutil.copy(build_backend_wheel, pkg_dir)
    with open(pkg_dir / "index.html", "w") as f:
        f.write(INDEX.format(build_backend_wheel.name))
    yield True
    shutil.rmtree(pkg_dir, ignore_errors=True)


@pytest.fixture(scope="function")
def pyproject_toml_temp_dir(tmpdir):
    """Fixture to set up a pyproject.toml file with path to the build backend templated in, in a tmpdir"""
    pyproject_toml = tmpdir.join("pyproject.toml")
    pyproject_toml.write(PYPROJECT_TOML_TEMPLATE)
    yield tmpdir


@pytest.fixture(scope="function")
def venv_python(tmpdir):
    # make a venv in the temp directory
    venv_path = tmpdir.join("venv")
    subprocess.run([sys.executable, "-m", "virtualenv", venv_path], check=True)
    # give path to Python executable for venv
    if sys.platform == "win32":
        bin_dir = "Scripts"
        python_name = "python.exe"
    else:
        bin_dir = "bin"
        python_name = "python"
    yield venv_path.join(bin_dir).join(python_name)
    shutil.rmtree(venv_path)


def is_responsive(url):
    index = url + "/"
    print(index)
    try:
        res = urlopen(index)
        if res.status == 200:
            return True
        else:
            return False
    except HTTPError:
        return False


@pytest.fixture(scope="session")
def pypi_server(docker_ip, docker_services):
    pypi_port = docker_services.port_for("pypi", 80)
    pypi_url = f"http://{docker_ip}:{pypi_port}"
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.1, check=lambda: is_responsive(pypi_url)
    )
    return pypi_url


@pytest.fixture(scope="session")
def stub_pypi_server(docker_ip, docker_services):
    stub_pypi_port = docker_services.port_for("stub_pypi", 80)
    stub_pypi_url = f"http://{docker_ip}:{stub_pypi_port}"
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.1, check=lambda: is_responsive(stub_pypi_url)
    )
    return stub_pypi_url
