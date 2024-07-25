# Vendored packages for wheel-stub

Rules for vendored code:
Ideally, vendored code should be completely unmodified. It should only be modified if that is needed to vendor the code.

The only vendored projects at the moment are:
- packaging: https://github.com/pypa/packaging
- tomli: https://github.com/hukkin/tomli

`packaging` is licensed under either the BSD 2-clause license or the Apache-2 license. Both are available under `_vendor/packaging-24.1.dist-info/`

`tomli` is licensed under the MIT license, available under `_vendor/tomli-2.0.1.dist-info/LICENSE`
