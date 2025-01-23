# wheel-stub

This is a PEP 517 build backend to act as a "soft link" between a package released on a 3rd party package index and pypi.org. This allows users to keep the simple UX of `pip install foo` while hosting the actual wheel files on a non-PyPi index.

## Demo usage

1. Install hatch: https://hatch.pypa.io/latest/install/
2. Run `hatch shell`
3. Run `hatch build -t wheel`
4. `cd demo`
5. Grab your favorite wheel file on https://pypi.nvidia.com, e.g.
   ```
   wget https://pypi.nvidia.com/nvidia-cuda-runtime-cu12/nvidia_cuda_runtime_cu12-12.4.99-py3-none-manylinux2014_x86_64.whl
   ```
6. Build the sdist:
   ```
   PIP_FIND_LINKS=`pwd`/../dist PIP_NO_INDEX=1 python -m build --sdist --config-setting source_wheel=nvidia_cuda_runtime_cu12-12.4.99-py3-none-manylinux2014_x86_64.whl
   ```
   There should now be a new `dist/` folder with e.g. `nvidia_cuda_runtime_cu12-12.4.99.tar.gz`
8. Install the sdist:
   ```
   pip install --no-cache ./dist/<my_sdist>.tar.gz
   ```
   Feel free to test with `--extra-index-url https://pypi.nvidia.com` as well.
9. Done! You should see everything install correctly

## Configuration

There are a few configuration options available for `wheel_stub`. These can be set in your `pyproject.toml` file:

- `index_url`: The url to the 3rd party index to install wheels from. This is the only required configuration setting.

- `stub_only`: Do not install the wheel from the 3rd party package repository, instead erroring with instructions of how to use the repository directly. This can be used in cases such as a project which depends on non-PyPi dependencies, which would get rejected from pypi.org. Set automatically based on project dependencies. `true` or `false` (default `false`)

- `include_cuda_debuginfo`: Whether to query information about the available CUDA runtime when reporting an error. `true` or `false` (default `false`)

## License

This project is released under the Apache-2 license. It vendors the `packaging` project, which is BSD 2-clause and Apache 2 dual licensed. It also vendors `tomli`, which is MIT licensed. For more details see the [LICENSE](/LICENSE) file.
