# Python native modules for WASIX

## Python Index

You can use this index for WASIX easily by providing this index to `pip` or `uv`:
https://pythonindex.wasix.org/

### Using the index in your projects

The actual **Simple API** endpoint that pip/uv expect lives under the `simple/` path, so the full base URL is:

```
https://pythonindex.wasix.org/simple
```

Below are a few common ways to point your tooling at it.

#### pip (one-off)

Install a package **only** from the WASIX index (no PyPI fallback):

```bash
pip install --index-url https://wasix-org.github.io/build-scripts/simple <package-name>
```

Keep the default PyPI index but let pip also search the WASIX index:

```bash
pip install --extra-index-url https://wasix-org.github.io/build-scripts/simple <package-name>
```

You can also set an environment variable once per shell:

```bash
export PIP_INDEX_URL=https://wasix-org.github.io/build-scripts/simple
pip install <package-name>
```

#### uv (one-off)

`uv` accepts the same flags as pip, so you can run e.g.:

```bash
# Only use the WASIX index
uv pip install --index-url https://wasix-org.github.io/build-scripts/simple <package-name>

# Or combine with PyPI
uv pip install --extra-index-url https://wasix-org.github.io/build-scripts/simple <package-name>
```

#### uv (project configuration)

For a permanent, checked-in configuration add a custom index section to your `pyproject.toml`:

```toml
[[tool.uv.index]]
# A human-friendly name you pick
name = "wasix"
# The Simple index URL
url = "https://wasix-org.github.io/build-scripts/simple"
# Optional – make this the primary index
default = true
```

After that, every `uv sync` / `uv pip install` inside the project will automatically resolve packages against the WASIX index.

---


### Rebuilding the index

All the supported native modules are already compiled in the [`artifacts/`](./artifacts) folder.
For each commit that changes the modules, we generate a new index using `dumb-pypi` that is statically stored in the provided URL index.

If you want to regenerate the index manually, you just need to do:

```bash
./generate-index.sh
```

## Building modules from source

Buildscripts to build numpy and other wheels for wasix. For convenience, this package already includes prebuilt versions of all the wheels and libraries.

### Usage

The build script is controlled by the following environment variables:

* `CC`, `CXX`, `AR`, `LD`, `RANLIB`, etc... : The cross-compiler tools. These should all be normal clang tools, but target wasm32-wasix by default and use the wasix sysroot.
* `WASIX_SYSROOT`: The path to the wasix sysroot that is used by the toolchain. Libraries will get installed here when you run `make install` or when they are required to build a package.
* `INSTALL_DIR`: The path to the python library path. Wheels will get installed here when you run `make install`.
* `WASMER`: The path to the wasmer binary. You must have it registered to handle wasm files as binfmt_misc. You can do this with `sudo $WASMER binfmt reregister`.

The easiest way to setup all the environment variables is to activate the wasix-clang environment using `source wasix-clang/activate`.

Then you can run `make all` to build all wheels and libraries.

### Versions

Here is a list of the versions of the wheels and libraries that are included in this package:

#### Wheels

* numpy: numpy/numpy main
* markupsafe: 3.0.2
* pandas: 2.2.3
* pytz: 2025.2
* dateutil: 2.9.0
* tzdata: 2025.2
* six: 1.17.0
* msgpack: 1.1.0
* pycryptodome: 3.23.0
* pycryptodomex: 3.23.0
* pyzbar: 0.1.9
* cpython: 3.1.2
* pypandoc: 1.15
* pypandoc_binary: 1.15
* psycopg: 3.2.9
* psycopg-binary: 3.2.9
* psycopg-pool: pool-3.2.6
* brotlicffi: 1.1.0.0
* cffi: 1.17.1
* pillow: 11.3.0
* matplotlib: 3.10.3
* uvloop: 0.21.0
* mysqlclient: 2.2.7
* python-qrcode: 8.2
* pycparser: 2.22
* pydantic: 2.11.7
* typing_extensions: 4.14.1
* typing-inspection: 0.4.1
* annotated-types: 0.7.0
* shapely: 2.1.1
* mrab-regex: 2025.7.31
* lxml: 6.0.0
* protobuf: 31.1
* grpc: 1.74.1
* numpy: 1.26.5
* python-crc32c: 1.7.1

psycopg3-c is just the sdist of psycopg3-binary

#### Libraries

* libzbar: 0.23.93
* libffi: wasix-org/libffi main
* pandoc: haskell-wasm/pandoc wasm
* postgresql: 17.5
* brotli: 1.1.0
* zlib: develop
  * 1.3.1 does not have proper cmake support, so we are using develop for now
* libjpeg-turbo: 3.1.1
* xz: 5.8.1
* libtiff: 4.7.0
* libwebp: 1.5.0
* giflib: 5.2.2
* libpng: 1.6.50
* SDL: 3.2.16
  * SDL has all subsystems disabled
* openjpeg: 2.5.3
* libuv: 1.51.0
* mariadb-connector-c: 3.4.6
* openssl: 3.5.1
* bzip2: 1.0.8
* util-linux: 2.41.1
  * We only build libuuid from util-linux
* openssh: 10.0p2
* dropbear: 2025.88
* tinyxml2: 11.0.0
* geos: 3.13.1
* libxslt: 1.1.43
* libxml2: 2.14.5
* google-crc32c: 1.1.2

### Notes

All built library packages should include a pkg-config file for each library.

#### [Variables in pkg-config files](https://www.gnu.org/prep/standards/html_node/Directory-Variables.html)

When building libs, we should make shour they include pkg-config files. The pkg config files should have their prefix set to `/usr/local`, exec_prefix set to `${prefix}`, libdir set to `${exec_prefix}/lib/wasm32-wasi`, and includedir set to `${prefix}/include`. In some cases it might be acceptable to have exec_prefix hardcoded to the same value as prefix. In that case libdir should start with `${prefix}` instead of `${exec_prefix}`.

### Analyzing the output

#### Check whether python libaries require shared libs

You can run somethign like

```bash
for f in $(find "$INSTALL_DIR" -name '*.so') ; do echo $f ; wasm-tools print $f | head -n10 | grep '(needed' -C10 ; done
```

to check which python libraries depend on shared libs. We try to keep that to a minimum, so wheels contain everything that is required to use a package.
