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

import os
import platform
import re
import subprocess
import traceback

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ERROR_TEMPLATE = os.path.join(BASE_DIR, "ERROR.txt")


def cuda_version_info():
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if result.returncode != 0:
            return f"Error in running nvidia-smi: {result.stderr}"
        output = result.stdout
        driver_version = re.search(r"Driver Version: (\d+\.\d+)", output)
        cuda_info = ""
        if driver_version:
            cuda_info += f"Driver Version: {driver_version.group(1)}\n"
        else:
            cuda_info += "Driver version not found in nvidia-smi output.\n"
        runtime_version = re.search(r"CUDA Version: (\d+\.\d+)", output)
        if runtime_version:
            cuda_info += f"CUDA Version: {runtime_version.group(1)}\n"
        else:
            cuda_info += "CUDA version not found in nvidia-smi output.\n"
        return cuda_info
    except FileNotFoundError:
        return "nvidia-smi command not found. Ensure NVIDIA drivers are installed.\n"


class InstallFailedError(RuntimeError):
    pass


def report_install_failure(distribution, version, config, exception_context):
    """Report installation failure and debugging information with steps to fix the failure."""
    # We want to give context of why we are failing install
    if exception_context is not None:
        traceback.print_tb(exception_context.__traceback__)
    python_info = f"{platform.python_implementation()} {platform.python_version()}"
    os_info = f"{platform.system()} {platform.release()}"
    cpu_arch = platform.machine()
    if config.get("include_cuda_debuginfo"):
        nvidia_smi_info = cuda_version_info()
    else:
        nvidia_smi_info = ""
    pypi_index = config["index_url"]
    with open(ERROR_TEMPLATE) as template:
        template_text = template.read()
    raise InstallFailedError(
        template_text.format(
            distribution=distribution,
            version=version,
            pypi_index=pypi_index,
            python_info=python_info,
            os_info=os_info,
            cpu_arch=cpu_arch,
            nvidia_smi_info=nvidia_smi_info,
        )
    )
