import os
import re
import subprocess

import pytest


@pytest.mark.parametrize(
    "requirement",
    [
        "nx-cugraph-cu11",
        "nvidia-cuda-runtime-cu12==12.4.99",
    ],
)
def test_wheel_install(
    requirement,
    install_in_pypi,
    venv_python,
    pypi_server,
    stub_pypi_server,
    build_backend_wheel,
):
    assert install_in_pypi, "wheel-stub wheel addition failed"
    env = os.environ.copy()
    env["NVIDIA_PIP_INDEX_URL"] = stub_pypi_server
    proc = subprocess.run(
        [
            venv_python,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-cache-dir",
            requirement,
            f"--index-url={pypi_server}",
            "-vv",
        ],
        env=env,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout + proc.stderr)
    assert re.search(
        rf"Successfully installed {requirement.replace('==', '-')}", proc.stdout
    )
