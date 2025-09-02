ifndef WASIX_SYSROOT
$(error You need to define WASIX_SYSROOT)
endif
ifeq ("$(wildcard $(WASIX_SYSROOT)/include)","")
$(error Your WASIX_SYSROOT at $(WASIX_SYSROOT) does not contain an include directory)
endif

SHELL:=/usr/bin/bash

PWD:=$(shell pwd)
PYTHON_WASIX_BINARIES:=${PWD}/python-wasix-binaries
MESON_CROSSFILE=${PWD}/resources/wasi.meson.cross
BAZEL_TOOLCHAIN=${PWD}/resources/bazel-toolchain
PATCH_DIR=${PWD}/patches
GIT:=git -c 'user.name=build-scripts' -c 'user.email=wasix@wasmer.io'

# Wheels build a .whl file
WHEELS=
WHEELS+=numpy
WHEELS+=pytz
WHEELS+=markupsafe
# Not a native package at all
WHEELS+=dateutil
# Technically not a native package, but it uses a native build process to prepare some files.
WHEELS+=tzdata
WHEELS+=pandas
WHEELS+=six
WHEELS+=msgpack-python
WHEELS+=pycryptodome
WHEELS+=pycryptodomex
WHEELS+=pyzbar
WHEELS+=cython
WHEELS+=pypandoc
WHEELS+=pypandoc_binary
WHEELS+=psycopg
WHEELS+=psycopg-pool
WHEELS+=psycopg-binary
WHEELS+=brotlicffi
WHEELS+=cffi
WHEELS+=pillow
WHEELS+=uvloop
WHEELS+=mysqlclient
WHEELS+=python-qrcode
WHEELS+=pycparser
WHEELS+=pydantic
WHEELS+=typing_extensions
WHEELS+=typing-inspection
WHEELS+=annotated-types
WHEELS+=shapely
WHEELS+=regex
WHEELS+=lxml
WHEELS+=protobuf
WHEELS+=grpc
WHEELS+=numpy1
WHEELS+=numpy2-0-2
WHEELS+=numpy2-3-2
WHEELS+=python-crc32c
WHEELS+=requests
WHEELS+=urllib3
WHEELS+=idna
WHEELS+=certifi
WHEELS+=charset_normalizer
WHEELS+=pypng
WHEELS+=pyarrow
WHEELS+=pyarrow19-0-1
WHEELS+=matplotlib
WHEELS+=packaging

#####     List of all wheel in python-wasix-binaries with reasons for inclusion in here     #####
#
# Use the following command to list all new wheels in the python-wasix-binaries repository:
#
# diff <(git ls-tree 531b962aae070e058138c17614f8cbe3e2607d72:wheels | grep -Po '[^\t ]*.whl') <(git ls-tree HEAD:wheels | grep -Po '[^\t ]*.whl') | grep '^>' | cut -d' ' -f2 | sort
#
# Don't forget to update the commit hash above afterwards!

PYTHON_WASIX_BINARIES_WHEELS=

# Included: Not moved to build-scripts yet
# TODO: Move to build-scripts
PYTHON_WASIX_BINARIES_WHEELS+=aiohttp-3.12.4-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=cffi-1.17.1-cp313-cp313-wasix_wasm32
# Included: Rust
PYTHON_WASIX_BINARIES_WHEELS+=cryptography-45.0.4-cp313-abi3-wasix_wasm32
# Included: Rust
PYTHON_WASIX_BINARIES_WHEELS+=cryptography-43.0.3-cp313-abi3-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=dateutil-cp313-cp313-wasix_wasm32
# Included: Not moved to build-scripts yet
# TODO: Move to build-scripts
PYTHON_WASIX_BINARIES_WHEELS+=ddtrace-3.10.2-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
# PYTHON_WASIX_BINARIES_WHEELS+=google_crc32c-1.7.1-py3-none-any
# Included: Not moved to build-scripts yet
# TODO: Move to build-scripts
PYTHON_WASIX_BINARIES_WHEELS+=httptools-0.6.4-cp313-cp313-wasix_wasm32
# Included: Rust
PYTHON_WASIX_BINARIES_WHEELS+=jiter-0.10.0-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=lxml-6.0.0-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=markupsafe-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=msgpack-1.1.0-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=mysqlclient-2.2.7-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=numpy-wasix-cp313-cp313-wasix_wasm32
# Included: Rust
PYTHON_WASIX_BINARIES_WHEELS+=orjson-3.11.0-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=pandas-cp313-cp313-wasix_wasm32
# Included: Not moved to build-scripts yet
# TODO: Move to build-scripts
PYTHON_WASIX_BINARIES_WHEELS+=peewee-3.18.2-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=psycopg-3.2.9-py3-none-any
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=psycopg_c-3.2.9-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=psycopg_pool-3.3.0.dev1-py3-none-any
# Not included: Source build in build-scripts
# PYTHON_WASIX_BINARIES_WHEELS+=pyarrow-19.0.1-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=pycryptodome-3.23.0-cp37-abi3-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=pycryptodomex-3.23.0-cp37-abi3-wasix_wasm32
# Included: Rust
PYTHON_WASIX_BINARIES_WHEELS+=pydantic_core-2.33.2-cp313-cp313-wasix_wasm32
# Included: Not moved to build-scripts yet
# TODO: Move to build-scripts
PYTHON_WASIX_BINARIES_WHEELS+=pynacl-1.5.0-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=pytz-cp313-cp313-wasix_wasm32
# Included: Not moved to build-scripts yet
# TODO: Move to build-scripts
PYTHON_WASIX_BINARIES_WHEELS+=pyyaml-6.0.2-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=regex-2025.5.18-cp313-cp313-wasix_wasm32
# Included: Rust
PYTHON_WASIX_BINARIES_WHEELS+=rpds_py-0.26.0-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=shapely-2.1.1-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=six-cp313-cp313-wasix_wasm32
# Included: Rust
PYTHON_WASIX_BINARIES_WHEELS+=tiktoken-0.9.0-cp313-cp313-wasix_wasm32
# Included: Rust
PYTHON_WASIX_BINARIES_WHEELS+=tokenizers-0.21.3-cp313-cp313-wasix_wasm32
# Included: Not moved to build-scripts yet. Does not seem native.
# TODO: Move to build-scripts
PYTHON_WASIX_BINARIES_WHEELS+=tornado-6.5.2-cp39-abi3-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=tzdata-cp313-cp313-wasix_wasm32
# Not included: Source build in build-scripts
#PYTHON_WASIX_BINARIES_WHEELS+=uvloop-0.21.0-cp313-cp313-wasix_wasm32
# Included: Not moved to build-scripts yet. Does not seem native.
# TODO: Move to build-scripts
PYTHON_WASIX_BINARIES_WHEELS+=watchdog-6.0.0-py3-none-any

# Libs build a .tar.xz file with a sysroot
LIBS=
LIBS+=zbar
LIBS+=libffi
LIBS+=pandoc
LIBS+=postgresql
LIBS+=brotli
LIBS+=zlib
LIBS+=libjpeg-turbo
LIBS+=xz
LIBS+=libtiff
LIBS+=libwebp
LIBS+=giflib
LIBS+=libpng
LIBS+=SDL3
LIBS+=openjpeg
LIBS+=libuv
LIBS+=mariadb-connector-c
LIBS+=openssl
LIBS+=util-linux
LIBS+=dropbear
LIBS+=tinyxml2
LIBS+=geos
LIBS+=libxslt
LIBS+=libxml2
LIBS+=google-crc32c
LIBS+=arrow19-0-1
LIBS+=arrow
LIBS+=rapidjson
LIBS+=icu
LIBS+=ncurses

# Packages that are broken can be marked as DONT_BUILD
# Packages that work but should not be included in the default install can be marked as DONT_INSTALL

DONT_BUILD=
# Dont build psycopg-binary, because it does not work
DONT_BUILD+=psycopg-binary
# Build is currently broken and I don't know why. It worked before. Continue here if you need 2.0.2
DONT_BUILD+=numpy2-0-2

DONT_INSTALL=$(DONT_BUILD)
# Dont install pypandoc because it uses the same name as pypandoc_binary
DONT_INSTALL+=pypandoc
# Dont install numpy1, because we already have numpy 2
DONT_INSTALL+=numpy1
DONT_INSTALL+=numpy2-0-2
DONT_INSTALL+=numpy2-3-2
# Dont install cryptography 43, because we already have 45
DONT_INSTALL+=cryptography-43.0.3-cp313-abi3-wasix_wasm32
# Dont install old pyarrow, because we already have the new one
DONT_INSTALL+=pyarrow19-0-1

# Helper function to get the project name from a path
project_name = $(basename $(basename $(notdir $(1))))
patches_for = $(shell find ${PATCH_DIR} -name '$(call project_name,$(1))-00*.patch' | sort)

# Helper functions to generate the paths to targets
# Targets should only ever be addressed by these functions
in_pkgs_with_suffix = $(addprefix pkgs/,$(addsuffix $(1),$(call project_name,$(2))))
source = $(call in_pkgs_with_suffix,.source,$(1))
prepared = $(call in_pkgs_with_suffix,.prepared,$(1))
build = $(call in_pkgs_with_suffix,.build,$(1))
targz = $(call in_pkgs_with_suffix,.tar.gz,$(1))
tarxz = $(call in_pkgs_with_suffix,.tar.xz,$(1))
sdist = $(call in_pkgs_with_suffix,.sdist,$(1))
whl = $(call in_pkgs_with_suffix,.whl,$(1))
wheel = $(call in_pkgs_with_suffix,.wheel,$(1))
lib = $(call in_pkgs_with_suffix,.lib,$(1))

WHEEL_SUBMODULES=$(call source,$(WHEELS))
LIB_SUBMODULES=$(call source,$(LIBS))
SUBMODULES=$(WHEEL_SUBMODULES) $(LIB_SUBMODULES)
PREPARED_SUBMODULES=$(call prepared,$(SUBMODULES))

BUILT_WHEELS=$(call whl,$(filter-out $(DONT_BUILD),$(WHEELS)))
UNPACKED_WHEELS=$(call wheel,$(WHEELS))
BUILT_SDISTS=$(call targz,$(WHEELS))
UNPACKED_SDISTS=$(call sdist,$(WHEELS))
UNPACKED_LIBS=$(call lib,$(LIBS))
BUILT_LIBS=$(call tarxz,$(filter-out $(DONT_BUILD),$(LIBS)))

# Names of the wheels and libs that we want to install
BUILT_WHEELS_TO_INSTALL_NAMES=$(filter-out $(DONT_INSTALL),$(WHEELS))
PWB_WHEELS_TO_INSTALL_NAMES=$(filter-out $(DONT_INSTALL),$(PYTHON_WASIX_BINARIES_WHEELS))
BUILT_LIBS_TO_INSTALL_NAMES=$(filter-out $(DONT_INSTALL),$(LIBS))
# Paths to the .whl and .tar.xz files that we want to install
BUILT_WHEELS_TO_INSTALL=$(call whl,$(BUILT_WHEELS_TO_INSTALL_NAMES))
PWB_WHEELS_TO_INSTALL=$(addprefix ${PYTHON_WASIX_BINARIES}/wheels/,$(addsuffix .whl,$(PWB_WHEELS_TO_INSTALL_NAMES)))
BUILT_LIBS_TO_INSTALL=$(call tarxz,$(BUILT_LIBS_TO_INSTALL_NAMES))
# Marker files to indicate that the wheels and libs have been installed
ALL_INSTALLED_WHEELS=$(addprefix ${INSTALL_DIR}/.,$(addsuffix .installed,$(BUILT_WHEELS_TO_INSTALL_NAMES)))
ALL_INSTALLED_WHEELS+=$(addprefix ${INSTALL_DIR}/.pwb-,$(addsuffix .installed,$(PWB_WHEELS_TO_INSTALL_NAMES)))
ALL_INSTALLED_LIBS=$(addprefix ${WASIX_SYSROOT}/.,$(addsuffix .installed,$(BUILT_LIBS_TO_INSTALL_NAMES)))

# mkdir but resets the timestamp if it didnt exist before
define reset_install_dir
bash -c 'rm -rf $$1 ; mkdir $$1 && touch -t 201001010001.00 $$1 || true' .
endef

define reset_submodule =
rm -rf $(realpath $(dir $@))
$(GIT) restore $(realpath $(dir $@))
$(GIT) submodule update --init --recursive $(realpath $(dir $@))
cd $(realpath $(dir $@)) && $(GIT) clean -dxf >/dev/null 2>&1 || true
cd $(realpath $(dir $@)) && make clean >/dev/null 2>&1 || true
cd $(realpath $(dir $@)) && $(GIT) am --abort >/dev/null 2>&1 || true
endef

define prepare_submodule =
test -n "$@" 
cd $@ && $(GIT) worktree remove . >/dev/null 2>&1 || true
rm -rf ${PWD}/$@
cd $(call source,$@) && $(GIT) worktree prune >/dev/null 2>&1 || true
cd $(call source,$@) && $(GIT) worktree add --checkout --detach ${PWD}/$@
# Quite a long command to clone submodules from the source directory instead of the remote
cd $@ && $(GIT) -c protocol.file.allow=always $$(cd ${PWD}/$(call source,$@) && $(GIT) submodule foreach --recursive bash -c 'echo -c url.file://$$(pwd).insteadOf=$$($(GIT) remote get-url origin)' | grep -v Entering | xargs echo) submodule update --init --recursive --progress
cd $@ && $(GIT) am --abort >/dev/null 2>&1 || true
cd $@ && echo | $(GIT) am $(call patches_for,$(call project_name,$@))
endef

# Customizable build script
# PYPROJECT_PATH is the path to the pyproject.toml relative to the submodule. Defaults to the submodule which is usually correct
# BUILD_ENV_VARS is a space separated list of environment variables to pass to the build script. Defaults to empty
# BUILD_EXTRA_FLAGS is a space separated list of extra flags to pass to the build script. Defaults to empty
# PREPARE is a command to run before building the wheel. Defaults to empty. Runs inside the submodule directory
define build_wheel =
mkdir -p pkgs
if test -n "${PREPARE}" ; then source ./cross-venv/bin/activate && cd $(call sdist,$@) && _= ${PREPARE} ; fi
source ./cross-venv/bin/activate && cd $(call sdist,$@) && ${BUILD_ENV_VARS} python3 -m build --wheel ${BUILD_EXTRA_FLAGS}
mkdir -p artifacts
cp $(call sdist,$@)/dist/*[2y].whl artifacts
# [2y] is a hack to match anything ending in wasm32 or any
ln -sf ../artifacts/$$(basename $(call sdist,$@)/dist/*[2y].whl) $@
endef

define build_sdist =
mkdir -p pkgs
if test -n "${PREPARE}" ; then source ./cross-venv/bin/activate && cd $(call build,$@) && _= ${PREPARE} ; fi
source ./cross-venv/bin/activate && cd $(call build,$@)/${PYPROJECT_PATH} && ${BUILD_ENV_VARS} python3 -m build --sdist ${BUILD_EXTRA_FLAGS}
mkdir -p artifacts
cp $(call build,$@)/${PYPROJECT_PATH}/dist/*[0-9].tar.gz artifacts
ln -sf ../artifacts/$$(basename $(call build,$@)/${PYPROJECT_PATH}/dist/*[0-9].tar.gz) $@
endef

# Bundle the first dependency to a tar.xz file in artifacts and link it to the target
define package_lib =
mkdir -p artifacts
cd $< && tar cfJ ${PWD}/artifacts/$(notdir $@) *
ln -sf $(shell realpath -s --relative-to="${PWD}/$(dir $@)" "${PWD}/artifacts/$(notdir $@)") $@
endef

# Command to run something in an environment with a haskell compiler targeting wasi
# Uses an older hash, because the latest version requires tail call support
RUN_WITH_HASKELL=nix shell 'gitlab:haskell-wasm/ghc-wasm-meta/6a8b8457df83025bed2a8759f5502725a827104b?host=gitlab.haskell.org' --command

all: $(BUILT_LIBS) $(BUILT_WHEELS) $(PWB_WHEELS_TO_INSTALL)
wheels: $(BUILT_WHEELS)
external-wheels: $(PWB_WHEELS_TO_INSTALL)
libs: $(BUILT_LIBS)

install: install-wheels install-libs
install-wheels: $(ALL_INSTALLED_WHEELS)
install-libs: $(ALL_INSTALLED_LIBS)

test: python-with-packages
	test -n "$$(command -v docker)" || (echo "You must have docker installed to run the tests" && exit 1)
	docker kill wasix-tests-mysql || true
	docker kill wasix-tests-postgres || true
	docker run --rm -it -d --name wasix-tests-mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=password  mysql:latest
	docker run --rm -it -d --name wasix-tests-postgres -p 5432:5432 -e POSTGRES_USER=myuser -e POSTGRES_PASSWORD=mypassword -e POSTGRES_DB=mydatabase postgres
	bash run-tests.sh
	docker kill wasix-tests-mysql || true
	docker kill wasix-tests-postgres || true

#####     Downloading and uploading the python webc     #####

PYTHON_WEBC=zebreus/python
PYTHON_WITH_PACKAGES_WEBC=zebreus/python-with-packages
PYTHON_WITH_LIBS_WEBC=zebreus/python-with-libs

python.webc python.version:
	wasmer package download $(PYTHON_WEBC) -o python.webc --registry wasmer.io
	touch python.webc
python: python.webc
	wasmer package unpack python.webc --out-dir python
	cp python/modules/python python/artifacts/wasix-install/cpython/bin/python3.wasm
	touch python
python-with-libs: python | $(call lib,postgresql) $(call lib,zbar) $(call lib,libjpeg-turbo) $(call lib,geos)
	### Prepare a python release with all the deps
	# Copy the base python package
	rm -rf python-with-libs
	cp -r python python-with-libs

	# Install the libs
	mkdir -p python-with-libs/artifacts/wasix-install/lib
	cp -L $(PWD)/$(call lib,postgresql)/usr/local/lib/wasm32-wasi/*.so* python-with-libs/artifacts/wasix-install/lib
	cp -L $(PWD)/$(call lib,zbar)/usr/local/lib/wasm32-wasi/libzbar.so* python-with-libs/artifacts/wasix-install/lib
	cp -L $(PWD)/$(call lib,libjpeg-turbo)/usr/local/lib/wasm32-wasi/libjpeg.so* python-with-libs/artifacts/wasix-install/lib
	# TODO: Build shapely without a shared geos dep
	cp -L $(PWD)/$(call lib,geos)/usr/local/lib/wasm32-wasi/libgeos*.so* python-with-libs/artifacts/wasix-install/lib

	# Copy the python-wasix-binaries wheels (tomlq is provided in the yq package (but only in the python implementation))
	tomlq -i '.package.name = "$(PYTHON_WITH_LIBS_WEBC)"' python-with-libs/wasmer.toml --output-format toml
	tomlq -i '.fs."/lib" = "./artifacts/wasix-install/lib"' python-with-libs/wasmer.toml --output-format toml
	tomlq -i '.module[0]."source" = "./artifacts/wasix-install/cpython/bin/python3.wasm"' python-with-libs/wasmer.toml --output-format toml

	echo 'Build python-with-libs'
	echo 'To test it run: `bash run-tests.sh`'
	echo 'To publish it run: `wasmer package publish --registry wasmer.io python-with-libs`' 
python-with-packages: python | $(call lib,postgresql) $(call lib,zbar) $(call lib,libjpeg-turbo) $(call lib,geos) $(BUILT_WHEELS_TO_INSTALL) $(PWB_WHEELS_TO_INSTALL)
	### Prepare a python release with all the deps
	# Copy the base python package
	rm -rf python-with-packages
	cp -r python python-with-packages

	# Install the wheels
	INSTALL_DIR=$(PWD)/python-with-packages/artifacts/wasix-install/cpython/lib/python3.13 make install-wheels

	# Install the libs
	mkdir -p python-with-packages/artifacts/wasix-install/lib
	cp -L $(PWD)/$(call lib,postgresql)/usr/local/lib/wasm32-wasi/*.so* python-with-packages/artifacts/wasix-install/lib
	cp -L $(PWD)/$(call lib,zbar)/usr/local/lib/wasm32-wasi/libzbar.so* python-with-packages/artifacts/wasix-install/lib
	cp -L $(PWD)/$(call lib,libjpeg-turbo)/usr/local/lib/wasm32-wasi/libjpeg.so* python-with-packages/artifacts/wasix-install/lib
	# TODO: Build shapely without a shared geos dep
	cp -L $(PWD)/$(call lib,geos)/usr/local/lib/wasm32-wasi/libgeos*.so* python-with-packages/artifacts/wasix-install/lib

	# Copy the python-wasix-binaries wheels (tomlq is provided in the yq package (but only in the python implementation))
	tomlq -i '.package.name = "$(PYTHON_WITH_PACKAGES_WEBC)"' python-with-packages/wasmer.toml --output-format toml
	tomlq -i '.fs."/lib" = "./artifacts/wasix-install/lib"' python-with-packages/wasmer.toml --output-format toml
	tomlq -i '.module[0]."source" = "./artifacts/wasix-install/cpython/bin/python3.wasm"' python-with-packages/wasmer.toml --output-format toml

	echo 'Build python-with-packages'
	echo 'To test it run: `bash run-tests.sh`'
	echo 'To publish it run: `wasmer package publish --registry wasmer.io python-with-packages`' 

#####     Preparing a wasm crossenv     #####

native-venv:
	python3 -m venv ./native-venv
	source ./native-venv/bin/activate && pip install crossenv
cross-venv: native-venv python
	rm -rf ./cross-venv
	source ./native-venv/bin/activate && python3 -m crossenv python/artifacts/wasix-install/cpython/bin/python3.wasm ./cross-venv --cc wasix-clang --cxx wasix-clang++
	source ./cross-venv/bin/activate && PIP_EXTRA_INDEX_URL=https://pythonindex.wasix.org/simple build-pip install cffi
	source ./cross-venv/bin/activate && PIP_EXTRA_INDEX_URL=https://pythonindex.wasix.org/simple pip install build six

#####     Preparing submodules     #####

# A target for making sure a submodule is clean
# To override the reset behaviour, add a target for your submodule
$(PREPARED_SUBMODULES): %:
$(foreach name,$(LIBS) $(WHEELS),$(eval pkgs/$(name).prepared: $(call patches_for,$(name))))
$(PREPARED_SUBMODULES): $(call prepared,%): $(call source,%)
$(call prepared,%):
	$(prepare_submodule)
$(call source,%): $(call source,%)/.git
	touch $@
$(call source,%)/.git:
	$(reset_submodule)
$(call build,%): $(call prepared,%)
	mkdir -p pkgs
	rm -rf $@
	cp -rf $< $@

$(call prepared,pycryptodomex):
	$(prepare_submodule)
	# If that file exists, pycryptodome will be built with a separate namespace
	touch $@/.separate_namespace

$(call prepared,pypandoc_binary):
	$(prepare_submodule)
	# pyproject.toml only works for the non-binary wheel, because they are still moving to pyproject.toml
	mv $@/setup_binary.py $@/setup.py
	rm $@/pyproject.toml
	# The pandoc binary also needs to be copied, but we do that in the build step

$(call prepared,protobuf):
	$(prepare_submodule)
	# The bazel toolchain files need to be in the repository
	cp -r $(BAZEL_TOOLCHAIN) $@/wasix-toolchain

$(call prepared,grpc):
	$(prepare_submodule)
	cd $@/third_party/abseil-cpp && $(GIT) am $(call patches_for,abseil-cpp)

$(call prepared,rapidjson):
	$(prepare_submodule)
	cd $@ && $(GIT) cherry-pick c6a6c7be4d927b57ca4c40cbcfadaf6dfc5212cb
	cd $@ && $(GIT) cherry-pick 20de638fece2706eff6e372a6bcacd322a423240

$(call prepared,pyarrow):
	$(prepare_submodule)
	# Tag so we get a clean name after applying the patch
	cd $@ && $(GIT) tag -fam "" apache-arrow-21.0.0

$(call prepared,pyarrow19-0-1):
	$(prepare_submodule)
	# Tag so we get a clean name after applying the patch
	cd $@ && $(GIT) tag -fam "" apache-arrow-19.0.1

$(call prepared,matplotlib):
	$(prepare_submodule)
	# Tag so we get a clean name after applying the patches
	cd $@ && $(GIT) tag -fam "" v3.10.6
#####     Building wheels     #####

# A target to build a wheel from a python submodule
# To override the build behaviour, add a target for your submodule
$(BUILT_WHEELS): $(call whl,%): $(call sdist,%) | cross-venv
$(call whl,%): $(call sdist,%)
	$(build_wheel)
$(BUILT_SDISTS): $(call targz,%): $(call build,%) | cross-venv
$(call targz,%): $(call build,%)
	$(build_sdist)
$(UNPACKED_SDISTS): $(call sdist,%): $(call targz,%) | cross-venv
$(call sdist,%): $(call targz,%)
	rm -rf $@
	mkdir -p $@
	tar -xzf $^ -C $@ --strip-components=1
$(UNPACKED_WHEELS): $(call wheel,%): | cross-venv
$(call wheel,%): $(call whl,%)
	rm -rf $@
	mkdir -p $@
	unzip -oq $< -d $@ 

# Depends on zbar headers being installed
# setup.py is not in the root directory
$(call targz,pytz): PYPROJECT_PATH = build/dist
# Build the tzdb locally
$(call targz,pytz): PREPARE = CCC_OVERRIDE_OPTIONS='^--target=x86_64-unknown-linux' CC=clang CXX=clang++ make build

$(call targz,psycopg): PYPROJECT_PATH = psycopg
$(call targz,psycopg-pool): PYPROJECT_PATH = psycopg_pool

$(call targz,psycopg-binary): PYPROJECT_PATH = psycopg_binary
$(call targz,psycopg-binary): PREPARE = rm -rf psycopg_binary && python3 tools/build/copy_to_binary.py
# Inject a mock pg_config to the PATH, so the build process can find it
$(call whl,psycopg-binary): BUILD_ENV_VARS = PATH="${PWD}/resources:$$PATH" WASIX_FORCE_STATIC_DEPENDENCIES=true
# Pretend we are a normal posix-like target, so we automatically include <endian.h>
$(call whl,psycopg-binary): export CCC_OVERRIDE_OPTIONS = ^-D__linux__=1

$(call whl,pillow): BUILD_ENV_VARS = PKG_CONFIG_SYSROOT_DIR=${WASIX_SYSROOT} PKG_CONFIG_PATH=${WASIX_SYSROOT}/usr/local/lib/wasm32-wasi/pkgconfig WASIX_FORCE_STATIC_DEPENDENCIES=true
$(call whl,pillow): BUILD_EXTRA_FLAGS = -Cplatform-guessing=disable

# We need to install, because we can only specify one sysroot in pkgconfig
$(call targz,lxml): $(call lib,libxml2) $(call lib,libxslt) | install-libxml2 install-libxslt
$(call targz,lxml): BUILD_ENV_VARS = PKG_CONFIG_SYSROOT_DIR=${WASIX_SYSROOT} PKG_CONFIG_PATH=${PWD}/$(call lib,libxml2)/usr/local/lib/wasm32-wasi/pkgconfig:${PWD}/$(call lib,libxslt)/usr/local/lib/wasm32-wasi/pkgconfig WASIX_FORCE_STATIC_DEPENDENCIES=true
$(call whl,lxml): BUILD_ENV_VARS = PKG_CONFIG_SYSROOT_DIR=${WASIX_SYSROOT} PKG_CONFIG_PATH=${PWD}/$(call lib,libxml2)/usr/local/lib/wasm32-wasi/pkgconfig:${PWD}/$(call lib,libxslt)/usr/local/lib/wasm32-wasi/pkgconfig WASIX_FORCE_STATIC_DEPENDENCIES=true

$(call targz,dateutil): PREPARE = python3 updatezinfo.py

# Needs to run a cython command before building the wheel	
$(call targz,msgpack-python): PREPARE = make cython

# Depends on a meson crossfile
$(call targz,numpy): BUILD_EXTRA_FLAGS = -Csetup-args="--cross-file=${MESON_CROSSFILE}"
$(call targz,numpy): ${MESON_CROSSFILE}
$(call whl,numpy): BUILD_EXTRA_FLAGS = -Csetup-args="--cross-file=${MESON_CROSSFILE}"
$(call whl,numpy): ${MESON_CROSSFILE}

# Depends on a meson crossfile
$(call targz,numpy1): BUILD_EXTRA_FLAGS = -Csetup-args="--cross-file=${MESON_CROSSFILE}"
$(call targz,numpy1): ${MESON_CROSSFILE}
$(call whl,numpy1): BUILD_EXTRA_FLAGS = -Csetup-args="--cross-file=${MESON_CROSSFILE}"
$(call whl,numpy1): ${MESON_CROSSFILE}

$(call targz,numpy2-0-2): BUILD_EXTRA_FLAGS = -Csetup-args="--cross-file=${MESON_CROSSFILE}" -Cbuild-dir=build
$(call targz,numpy2-0-2): ${MESON_CROSSFILE}
$(call whl,numpy2-0-2): BUILD_EXTRA_FLAGS = -Csetup-args="--cross-file=${MESON_CROSSFILE}" -Cbuild-dir=build
$(call whl,numpy2-0-2): ${MESON_CROSSFILE}

$(call targz,numpy2-3-2): BUILD_EXTRA_FLAGS = -Csetup-args="--cross-file=${MESON_CROSSFILE}" -Cbuild-dir=build
$(call targz,numpy2-3-2): ${MESON_CROSSFILE}
$(call whl,numpy2-3-2): BUILD_EXTRA_FLAGS = -Csetup-args="--cross-file=${MESON_CROSSFILE}" -Cbuild-dir=build
$(call whl,numpy2-3-2): ${MESON_CROSSFILE}

$(call whl,shapely): $(call lib,geos)
# TODO: Static build don't work yet, because we would have to specify recursive dependencies manually
# $(call whl,shapely): BUILD_ENV_VARS += WASIX_FORCE_STATIC_DEPENDENCIES=true
# Set geos paths
$(call whl,shapely): BUILD_ENV_VARS += GEOS_INCLUDE_PATH="${PWD}/$(call lib,geos)/usr/local/include"
$(call whl,shapely): BUILD_ENV_VARS += GEOS_LIBRARY_PATH="${PWD}/$(call lib,geos)/usr/local/lib/wasm32-wasi"
# Use numpy dev build from our registry. Our patches have been merged upstream, so for the next numpy release we can remove this.
$(call whl,shapely): BUILD_ENV_VARS += PIP_CONSTRAINT=$$(F=$$(mktemp) ; echo numpy==2.4.0.dev0 > $$F ; echo $$F)
$(call whl,shapely): BUILD_ENV_VARS += PIP_EXTRA_INDEX_URL=https://pythonindex.wasix.org/simple
$(call whl,shapely): BUILD_ENV_VARS += NUMPY_ONLY_GET_INCLUDE=1
$(call whl,shapely): BUILD_EXTRA_FLAGS = --skip-dependency-check

# Needs to have the pypandoc executable in the repo
$(call whl,pypandoc_binary): $(call sdist,pypandoc_binary)/pypandoc/files/pandoc
$(call sdist,pypandoc_binary)/pypandoc/files/pandoc: $(call sdist,pypandoc_binary) $(call tarxz,pandoc)
	mkdir -p $(call sdist,pypandoc_binary)/pypandoc/files
	tar xfJ $(call tarxz,pandoc) -C $(call sdist,pypandoc_binary)/pypandoc/files --strip-components=1 bin/pandoc
	touch $@

$(call whl,uvloop): BUILD_ENV_VARS = WASIX_FORCE_STATIC_DEPENDENCIES=true
$(call whl,uvloop): BUILD_EXTRA_FLAGS = '-C--build-option=build_ext --use-system-libuv'

$(call whl,mysqlclient): BUILD_ENV_VARS = WASIX_FORCE_STATIC_DEPENDENCIES=true PKG_CONFIG_SYSROOT_DIR=${WASIX_SYSROOT} PKG_CONFIG_PATH=${WASIX_SYSROOT}/usr/local/lib/wasm32-wasi/pkgconfig

# Use numpy dev build from our registry. Our patches have been merged upstream, so for the next numpy release we can remove this.
$(call targz,pandas): BUILD_ENV_VARS += PIP_CONSTRAINT=$$(F=$$(mktemp) ; echo numpy==2.4.0.dev0 > $$F ; echo $$F)
$(call targz,pandas): BUILD_ENV_VARS += PIP_EXTRA_INDEX_URL=https://pythonindex.wasix.org/simple
# $(call targz,pandas): BUILD_ENV_VARS += PIP_NO_CACHE_DIR=1
$(call targz,pandas): BUILD_ENV_VARS += NUMPY_ONLY_GET_INCLUDE=1
$(call targz,pandas): BUILD_EXTRA_FLAGS = -Csetup-args="--cross-file=${MESON_CROSSFILE}"
$(call targz,pandas): ${MESON_CROSSFILE}
$(call whl,pandas): BUILD_ENV_VARS += PIP_CONSTRAINT=$$(F=$$(mktemp) ; echo numpy==2.4.0.dev0 > $$F ; echo $$F)
$(call whl,pandas): BUILD_ENV_VARS += PIP_EXTRA_INDEX_URL=https://pythonindex.wasix.org/simple
$(call whl,pandas): BUILD_ENV_VARS += NUMPY_ONLY_GET_INCLUDE=1
$(call whl,pandas): BUILD_EXTRA_FLAGS = -Csetup-args="--cross-file=${MESON_CROSSFILE}"
$(call whl,pandas): ${MESON_CROSSFILE}

$(call targz,protobuf):
	mkdir -p pkgs
	cd $(call build,protobuf)/python && bazel clean --expunge
	cd $(call build,protobuf)/python && CC=/usr/bin/clang CXX=/usr/bin/clang++ LD=/usr/bin/ld AR=/usr/bin/ar AS=/usr/bin/as bazel build //python/dist:source_wheel --crosstool_top=//wasix-toolchain:wasix_toolchain --host_crosstool_top=@bazel_tools//tools/cpp:toolchain --cpu=wasm32-wasi
	mkdir -p artifacts
	install -m666 $(call build,protobuf)/bazel-bin/python/dist/protobuf.tar.gz artifacts
	ln -rsf ${PWD}/artifacts/protobuf.tar.gz $@

$(call targz,pyarrow19-0-1): BUILD_ENV_VARS += PIP_CONSTRAINT=$$(F=$$(mktemp) ; echo numpy==2.4.0.dev0 > $$F ; echo $$F)
$(call targz,pyarrow19-0-1): BUILD_ENV_VARS += PIP_EXTRA_INDEX_URL=https://pythonindex.wasix.org/simple
$(call targz,pyarrow19-0-1): BUILD_ENV_VARS += NUMPY_ONLY_GET_INCLUDE=1
$(call targz,pyarrow19-0-1): PYPROJECT_PATH = python
$(call whl,pyarrow19-0-1): BUILD_ENV_VARS += PIP_CONSTRAINT=$$(F=$$(mktemp) ; echo numpy==2.4.0.dev0 > $$F ; echo $$F)
$(call whl,pyarrow19-0-1): BUILD_ENV_VARS += PIP_EXTRA_INDEX_URL=https://pythonindex.wasix.org/simple
$(call whl,pyarrow19-0-1): BUILD_ENV_VARS += NUMPY_ONLY_GET_INCLUDE=1
$(call whl,pyarrow19-0-1): BUILD_ENV_VARS += CMAKE_PREFIX_PATH=${PWD}/$(call lib,arrow19-0-1)/usr/local/lib/wasm32-wasi/cmake
$(call whl,pyarrow19-0-1): $(call lib,arrow19-0-1)
$(call targz,pyarrow): BUILD_ENV_VARS += PIP_CONSTRAINT=$$(F=$$(mktemp) ; echo numpy==2.4.0.dev0 > $$F ; echo $$F)
$(call targz,pyarrow): BUILD_ENV_VARS += PIP_EXTRA_INDEX_URL=https://pythonindex.wasix.org/simple
$(call targz,pyarrow): BUILD_ENV_VARS += NUMPY_ONLY_GET_INCLUDE=1
$(call targz,pyarrow): PYPROJECT_PATH = python
$(call whl,pyarrow): BUILD_ENV_VARS += PIP_CONSTRAINT=$$(F=$$(mktemp) ; echo numpy==2.4.0.dev0 > $$F ; echo $$F)
$(call whl,pyarrow): BUILD_ENV_VARS += PIP_EXTRA_INDEX_URL=https://pythonindex.wasix.org/simple
$(call whl,pyarrow): BUILD_ENV_VARS += NUMPY_ONLY_GET_INCLUDE=1
$(call whl,pyarrow): BUILD_ENV_VARS += CMAKE_PREFIX_PATH=${PWD}/$(call lib,arrow)/usr/local/lib/wasm32-wasi/cmake
$(call whl,pyarrow): $(call lib,arrow)

$(call targz,matplotlib): BUILD_ENV_VARS += PIP_CONSTRAINT=$$(F=$$(mktemp) ; echo numpy==2.4.0.dev0 > $$F ; echo $$F)
$(call targz,matplotlib): BUILD_ENV_VARS += PIP_EXTRA_INDEX_URL=https://pythonindex.wasix.org/simple
$(call targz,matplotlib): BUILD_ENV_VARS += NUMPY_ONLY_GET_INCLUDE=1
$(call targz,matplotlib): BUILD_EXTRA_FLAGS = -Csetup-args="--cross-file=${MESON_CROSSFILE}"
$(call targz,matplotlib): ${MESON_CROSSFILE}
$(call whl,matplotlib): BUILD_ENV_VARS += PIP_CONSTRAINT=$$(F=$$(mktemp) ; echo numpy==2.4.0.dev0 > $$F ; echo $$F)
$(call whl,matplotlib): BUILD_ENV_VARS += PIP_EXTRA_INDEX_URL=https://pythonindex.wasix.org/simple
$(call whl,matplotlib): BUILD_ENV_VARS += NUMPY_ONLY_GET_INCLUDE=1
$(call whl,matplotlib): BUILD_EXTRA_FLAGS = -Csetup-args="--cross-file=${MESON_CROSSFILE}"
$(call whl,matplotlib): ${MESON_CROSSFILE}
# TODO: When arrow supports setting rpath for all its libs, we can enable this and start working on shared builds
# $(call whl,pyarrow): BUILD_ENV_VARS += PYARROW_BUNDLE_ARROW_CPP=ON PYARROW_BUNDLE_CYTHON_CPP=ON

# TODO: Remove patch for python-crc32c once
#   A: We dont store libs in the wasm32-wasi subdir anymore OR
#   B: wasix-clang supports automatically adding the wasm32-wasi subdir of every linker path to the linker path
$(call whl,python-crc32c): $(call lib,google-crc32c)
$(call whl,python-crc32c): BUILD_ENV_VARS = CRC32C_INSTALL_PREFIX=${PWD}/$(call lib,google-crc32c)/usr/local WASIX_FORCE_STATIC_DEPENDENCIES=true

$(call whl,charset_normalizer): BUILD_ENV_VARS = CHARSET_NORMALIZER_USE_MYPYC=1

#####     Building libraries     #####

$(UNPACKED_LIBS): $(call lib,%): $(call build,%)
$(BUILT_LIBS): $(call tarxz,%): $(call lib,%)
$(call lib,%): $(call build,%)
	echo "Missing build script for $@" >&2 && exit 1
$(call tarxz,%): $(call lib,%)
	$(package_lib)
	touch $@

# TODO: Add libjpeg support
$(call lib,zbar):
	cd $(call build,$@) && autoreconf -vfi
	# Force configure to build shared libraries. This is a hack, but it works.
	cd $(call build,$@) && sed -i 's/^  archive_cmds=$$/  archive_cmds='\''$$CC -shared $$pic_flag $$libobjs $$deplibs $$compiler_flags $$wl-soname $$wl$$soname -o $$lib'\''/' configure
	cd $(call build,$@) && ./configure --prefix=/usr/local --libdir='$${exec_prefix}/lib/wasm32-wasi' --enable-static --enable-shared --disable-video --disable-rpath --without-imagemagick --without-java --without-qt --without-gtk --without-xv --without-xshm --without-python
	cd $(call build,$@) && make
	$(reset_install_dir) $@
	cd $(call build,$@) && make install DESTDIR=${PWD}/$@
	touch $@

$(call lib,libffi):
	cd $(call build,$@) && autoreconf -vfi
	cd $(call build,$@) && ./configure --prefix=/usr/local --libdir='$${exec_prefix}/lib/wasm32-wasi' --host="wasm32-wasi" --enable-static --disable-shared --disable-dependency-tracking --disable-builddir --disable-multi-os-directory --disable-raw-api --disable-docs
	cd $(call build,$@) && make
	$(reset_install_dir) $@
	cd $(call build,$@) && make install DESTDIR=${PWD}/$@
	touch $@

$(call lib,zlib):
	cd $(call build,$@) && rm -rf combined
	cd $(call build,$@) && cmake -B combined -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi' -DCMAKE_SKIP_RPATH=YES -DZLIB_BUILD_MINIZIP=OFF
	cd $(call build,$@) && cmake --build combined -j16
	$(reset_install_dir) $@
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install combined
	touch $@

$(call lib,pandoc):
	cd $(call build,$@) && ${RUN_WITH_HASKELL} wasm32-wasi-cabal update
	cd $(call build,$@) && ${RUN_WITH_HASKELL} wasm32-wasi-cabal build pandoc-cli
	# Most of these options are copied from https://github.com/tweag/pandoc-wasm/blob/master/.github/workflows/build.yml
	wasm-opt --experimental-new-eh --low-memory-unused --converge --gufa --flatten --rereloop -Oz $$(find $(call build,$@) -type f -name pandoc.wasm) -o $(call build,$@)/pandoc.opt.wasm
	$(reset_install_dir) $@
	mkdir -p $@/bin
	install -m 755 $(call build,$@)/pandoc.opt.wasm $@/bin/pandoc
	touch $@

$(call lib,postgresql):
	cd $(call build,$@) && ./configure --prefix=/usr/local --libdir='$${exec_prefix}/lib/wasm32-wasi' --without-icu --without-zlib --without-readline
	cd $(call build,$@) && make MAKELEVEL=0 -C src/interfaces
	cd $(call build,$@) && make MAKELEVEL=0 -C src/include
	$(reset_install_dir) $@
	cd $(call build,$@) && make MAKELEVEL=0 -C src/interfaces install DESTDIR=${PWD}/$@
	cd $(call build,$@) && make MAKELEVEL=0 -C src/include install DESTDIR=${PWD}/$@
	touch $@

$(call lib,brotli):
	cd $(call build,$@) && rm -rf out
	cd $(call build,$@) && cmake -DCMAKE_BUILD_TYPE=Release -B out -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi'
# Brotli always tries to build the executable (which we dont need), which imports `chown` and `clock`, which we don't provide.
# This workaround makes that work during linking, but it is not a proper solution.
# CCC_OVERRIDE_OPTIONS should not be set during cmake setup, because it will erroneously detect emscripten otherwise.
# TODO: Implement chown in wasix and unset CCC_OVERRIDE_OPTIONS
	cd $(call build,$@) && CCC_OVERRIDE_OPTIONS='^-Wl,--unresolved-symbols=import-dynamic' make -C out
	$(reset_install_dir) $@
	cd $(call build,$@) && CCC_OVERRIDE_OPTIONS='^-Wl,--unresolved-symbols=import-dynamic' make -C out install DESTDIR=${PWD}/$@
	touch $@

$(call lib,libjpeg-turbo):
	cd $(call build,$@) && rm -rf out
	# They use a custom version of GNUInstallDirs.cmake does not support libdir starting with prefix.
	# TODO: Add a sed command to fix that
	cd $(call build,$@) && cmake -DCMAKE_BUILD_TYPE=Release -B out -DCMAKE_INSTALL_PREFIX=/usr/local -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi'
	cd $(call build,$@) && make -C out
	$(reset_install_dir) $@
	cd $(call build,$@) && make -C out install DESTDIR=${PWD}/$@
	touch $@

$(call lib,xz):
	cd $(call build,$@) && rm -rf static shared
	cd $(call build,$@) && cmake -B shared -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi' -DBUILD_SHARED_LIBS=ON -DCMAKE_SKIP_INSTALL_RPATH=YES -DCMAKE_SKIP_RPATH=YES
	cd $(call build,$@) && cmake -B static -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi' -DBUILD_SHARED_LIBS=OFF -DCMAKE_SKIP_INSTALL_RPATH=YES -DCMAKE_SKIP_RPATH=YES
	cd $(call build,$@) && cmake --build shared -j16
	cd $(call build,$@) && cmake --build static -j16
	$(reset_install_dir) $@
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install shared
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install static
	touch $@

$(call lib,libtiff):
	cd $(call build,$@) && bash autogen.sh
	# Force configure to build shared libraries. This is a hack, but it works.
	cd $(call build,$@) && sed -i 's/^  archive_cmds=$$/  archive_cmds='\''$$CC -shared $$pic_flag $$libobjs $$deplibs $$compiler_flags $$wl-soname $$wl$$soname -o $$lib'\''/' configure
	cd $(call build,$@) && PKG_CONFIG_SYSROOT_DIR=${WASIX_SYSROOT} PKG_CONFIG_PATH=${WASIX_SYSROOT}/usr/local/lib/wasm32-wasi/pkgconfig ./configure --prefix=/usr/local --libdir='$${exec_prefix}/lib/wasm32-wasi'
	cd $(call build,$@) && PKG_CONFIG_SYSROOT_DIR=${WASIX_SYSROOT} PKG_CONFIG_PATH=${WASIX_SYSROOT}/usr/local/lib/wasm32-wasi/pkgconfig make -j4
	$(reset_install_dir) $@
	cd $(call build,$@) && PKG_CONFIG_SYSROOT_DIR=${WASIX_SYSROOT} PKG_CONFIG_PATH=${WASIX_SYSROOT}/usr/local/lib/wasm32-wasi/pkgconfig make install DESTDIR=${PWD}/$@
	touch $@

$(call lib,libwebp):
	cd $(call build,$@) && bash autogen.sh
	# Force configure to build shared libraries. This is a hack, but it works.
	cd $(call build,$@) && sed -i 's/^  archive_cmds=$$/  archive_cmds='\''$$CC -shared $$pic_flag $$libobjs $$deplibs $$compiler_flags $$wl-soname $$wl$$soname -o $$lib'\''/' configure
	cd $(call build,$@) && ./configure --prefix=/usr/local --libdir='$${exec_prefix}/lib/wasm32-wasi'
	cd $(call build,$@) && make
	$(reset_install_dir) $@
	cd $(call build,$@) && PKG_CONFIG_SYSROOT_DIR=${WASIX_SYSROOT} PKG_CONFIG_PATH=${WASIX_SYSROOT}/usr/local/lib/wasm32-wasi/pkgconfig make install DESTDIR=${PWD}/$@
	touch $@

$(call lib,giflib): resources/giflib.pc
	cd $(call build,$@) && make
	$(reset_install_dir) $@
	cd $(call build,$@) && make install PREFIX=/usr/local LIBDIR=/usr/local/lib/wasm32-wasi DESTDIR=${PWD}/$@
	# $(call build,$@) does not include a pkg-config file, so we need to install it manually. We need to bump the version in that file as well, when we update the version
	install -Dm644 ${PWD}/resources/giflib.pc ${PWD}/$@/usr/local/lib/wasm32-wasi/pkgconfig/giflib.pc
	touch $@

$(call lib,libpng):
	# Force configure to build shared libraries. This is a hack, but it works.
	cd $(call build,$@) && sed -i 's/^  archive_cmds=$$/  archive_cmds='\''$$CC -shared $$pic_flag $$libobjs $$deplibs $$compiler_flags $$wl-soname $$wl$$soname -o $$lib'\''/' configure
	cd $(call build,$@) && ./configure --prefix=/usr/local --libdir='$${exec_prefix}/lib/wasm32-wasi'
	cd $(call build,$@) && make
	$(reset_install_dir) $@
	cd $(call build,$@) && make install DESTDIR=${PWD}/$@
	touch $@

$(call lib,SDL3):
	cd $(call build,$@) && cmake . -DSDL_UNIX_CONSOLE_BUILD=ON -DSDL_RENDER_GPU=OFF -DSDL_VIDEO=OFF -DSDL_AUDIO=OFF -DSDL_JOYSTICK=OFF -DSDL_HAPTIC=OFF -DSDL_HIDAPI=OFF -DSDL_SENSOR=OFF -DSDL_POWER=OFF -DSDL_DIALOG=OFF -DSDL_STATIC=ON -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi'
	cd $(call build,$@) && make
	$(reset_install_dir) $@
	cd $(call build,$@) && make install DESTDIR=${PWD}/$@
	touch $@

$(call lib,openjpeg):
	cd $(call build,$@) && PKG_CONFIG_SYSROOT_DIR=${WASIX_SYSROOT} PKG_CONFIG_PATH=${WASIX_SYSROOT}/usr/local/lib/wasm32-wasi/pkgconfig cmake . -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi'
	cd $(call build,$@) && make
	$(reset_install_dir) $@
	cd $(call build,$@) && make install DESTDIR=${PWD}/$@
	touch $@

$(call lib,libuv):
	cd $(call build,$@) && rm -rf out
	cd $(call build,$@) && cmake -B out -DLIBUV_BUILD_TESTS=OFF -DCMAKE_SYSTEM_NAME=WASI -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi'
	cd $(call build,$@) && make -C out
	$(reset_install_dir) $@
	cd $(call build,$@) && make -C out install DESTDIR=${PWD}/$@
	touch $@

# TODO: Improve, after openssl is building
$(call lib,mariadb-connector-c):
	# cd $(call build,$@) && rm -rf out
	cd $(call build,$@) && PKG_CONFIG_SYSROOT_DIR=${WASIX_SYSROOT} PKG_CONFIG_PATH=${WASIX_SYSROOT}/usr/local/lib/wasm32-wasi/pkgconfig cmake -B out \
	 -DCMAKE_SYSTEM_NAME=WASI \
	 -DOPENSSL_INCLUDE_DIR=${WASIX_SYSROOT}/usr/local/include \
	 -DOPENSSL_SSL_LIBRARY=${WASIX_SYSROOT}/usr/local/lib/wasm32-wasi/libcrypto.a \
	 -DOPENSSL_CRYPTO_LIBRARY=${WASIX_SYSROOT}/usr/local/lib/wasm32-wasi/libcrypto.a \
	 -DZLIB_INCLUDE_DIR=${WASIX_SYSROOT}/usr/local/include \
	 -DZLIB_LIBRARY=${WASIX_SYSROOT}/usr/local/lib/wasm32-wasi/libz.a \
	 -DWITH_MYSQLCOMPAT=ON \
	 -DCLIENT_PLUGIN_DIALOG=static \
     -DCLIENT_PLUGIN_SHA256_PASSWORD=static \
     -DCLIENT_PLUGIN_CACHING_SHA2_PASSWORD=static \
     -DCLIENT_PLUGIN_CLIENT_ED25519=static \
     -DCLIENT_PLUGIN_PARSEC=static \
     -DCLIENT_PLUGIN_MYSQL_CLEAR_PASSWORD=static \
	 -DWITH_EXTERNAL_ZLIB=ON \
	 -DWITH_UNIT_TESTS=OFF \
	 -DCMAKE_BUILD_TYPE=Release \
	 -DINSTALL_INCLUDEDIR='include' \
	 -DINSTALL_LIBDIR='lib/wasm32-wasi' \
	 -DINSTALL_PCDIR='lib/wasm32-wasi/pkgconfig'
	cd $(call build,$@) && make -j16 -C out
	$(reset_install_dir) $@
	cd $(call build,$@) && make -j16 -C out install DESTDIR=${PWD}/$@
	cd ${PWD}/$@/usr/local/lib/wasm32-wasi/pkgconfig && sed -i "s|${WASIX_SYSROOT}/usr/local/lib/wasm32-wasi|\$${libdir}|g" libmariadb.pc
	cd ${PWD}/$@/usr/local/lib/wasm32-wasi/pkgconfig && sed "s|libmariadb|libmysql|g" libmariadb.pc > libmysql.pc
	cd ${PWD}/$@/usr/local/lib/wasm32-wasi && ln -s libmariadbclient.a ./libmysqlclient.a
	cd ${PWD}/$@/usr/local/lib/wasm32-wasi && ln -s libmariadb.so ./libmysql.so
	touch ${PWD}/$@/usr/local/lib/wasm32-wasi

$(call lib,openssl):
	# Options adapted from https://github.com/wasix-org/openssl/commit/52cc90976bea2e4f224250ef72cfa992c42bf410
	# Add no-pic to disable PIC
	cd $(call build,$@) && ./Configure no-asm no-tests no-apps no-afalgeng no-dgram no-secure-memory --prefix /usr/local --libdir=lib/wasm32-wasi
	cd $(call build,$@) && make -j8
	$(reset_install_dir) $@
	cd $(call build,$@) && make install_sw DESTDIR=${PWD}/$@
	touch $@

# We only build a static libuuid for now
$(call lib,util-linux):
	cd $(call build,$@) && bash autogen.sh
	cd $(call build,$@) && ./configure --disable-all-programs --enable-libuuid --host=wasm32-wasi --enable-static --prefix=/usr/local --libdir='$${exec_prefix}/lib/wasm32-wasi'
	cd $(call build,$@) && make
	$(reset_install_dir) $@
	cd $(call build,$@) && make install DESTDIR=${PWD}/$@
	touch $@


$(call lib,dropbear):
	cd $(call build,$@) && autoreconf -vfi
	cd $(call build,$@) && ./configure --prefix=/usr/local --libdir='$${exec_prefix}/lib/wasm32-wasi' --enable-bundled-libtom --without-pam --enable-static --disable-utmp --disable-utmpx --disable-wtmp --disable-wtmpx --disable-lastlog --disable-loginfunc
	cd $(call build,$@) && make -j8
	$(reset_install_dir) $@
	cd $(call build,$@) && make install DESTDIR=${PWD}/$@
	touch $@

$(call lib,tinyxml2):
	cd $(call build,$@) && rm -rf shared static
	cd $(call build,$@) && cmake -B static -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi' -DBUILD_SHARED_LIBS=OFF
	cd $(call build,$@) && cmake -B shared -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi' -DBUILD_SHARED_LIBS=ON
	cd $(call build,$@) && cmake --build static -j16
	cd $(call build,$@) && cmake --build shared -j16
	$(reset_install_dir) $@
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install static
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install shared
	touch $@

$(call lib,geos):
	cd $(call build,$@) && rm -rf static shared
	cd $(call build,$@) && cmake -B static -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi' -DBUILD_GEOSOP=OFF -DBUILD_TESTING=OFF -DBUILD_SHARED_LIBS=OFF -DCMAKE_SKIP_INSTALL_RPATH=YES -DCMAKE_SKIP_RPATH=YES
	cd $(call build,$@) && cmake -B shared -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi' -DBUILD_GEOSOP=OFF -DBUILD_TESTING=OFF -DBUILD_SHARED_LIBS=ON -DCMAKE_SKIP_INSTALL_RPATH=YES -DCMAKE_SKIP_RPATH=YES
	cd $(call build,$@) && cmake --build static -j16
	cd $(call build,$@) && cmake --build shared -j16
	$(reset_install_dir) $@
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install static
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install shared
	touch $@

$(call lib,libxslt): $(call lib,xz) $(call lib,libxml2) $(call lib,zlib)
	cd $(call build,$@) && rm -rf static shared
	cd $(call build,$@) && CMAKE_PREFIX_PATH=${PWD}/$(call lib,xz)/usr/local/lib/wasm32-wasi/cmake:${PWD}/$(call lib,libxml2)/usr/local/lib/wasm32-wasi/cmake:${PWD}/$(call lib,zlib)/usr/local/lib/wasm32-wasi/cmake cmake -B static -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi' -DBUILD_SHARED_LIBS=OFF -DCMAKE_SKIP_RPATH=YES -DLIBXSLT_WITH_PYTHON=OFF
	cd $(call build,$@) && CMAKE_PREFIX_PATH=${PWD}/$(call lib,xz)/usr/local/lib/wasm32-wasi/cmake:${PWD}/$(call lib,libxml2)/usr/local/lib/wasm32-wasi/cmake:${PWD}/$(call lib,zlib)/usr/local/lib/wasm32-wasi/cmake cmake -B shared -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi' -DBUILD_SHARED_LIBS=ON -DCMAKE_SKIP_RPATH=YES -DLIBXSLT_WITH_PYTHON=OFF
	cd $(call build,$@) && cmake --build static -j16
	cd $(call build,$@) && cmake --build shared -j16
	$(reset_install_dir) $@
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install static
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install shared
	touch $@

$(call lib,libxml2):
	cd $(call build,$@) && rm -rf shared static
	cd $(call build,$@) && cmake -B static -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi' -DCMAKE_SKIP_RPATH=YES -DBUILD_SHARED_LIBS=OFF -DLIBXML2_WITH_PYTHON=OFF
	cd $(call build,$@) && cmake -B shared -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi' -DCMAKE_SKIP_RPATH=YES -DBUILD_SHARED_LIBS=ON -DLIBXML2_WITH_PYTHON=OFF
	cd $(call build,$@) && cmake --build static -j16
	cd $(call build,$@) && cmake --build shared -j16
	$(reset_install_dir) $@
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install static
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install shared
	touch $@

$(call lib,google-crc32c):
	cd $(call build,$@) && rm -rf shared static
	cd $(call build,$@) && cmake -B static -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi' -DCMAKE_SKIP_RPATH=YES -DBUILD_SHARED_LIBS=OFF -DCRC32C_BUILD_TESTS=OFF -DCRC32C_USE_GLOG=OFF -DCRC32C_BUILD_BENCHMARKS=OFF 
	cd $(call build,$@) && cmake -B shared -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR='lib/wasm32-wasi' -DCMAKE_SKIP_RPATH=YES -DBUILD_SHARED_LIBS=ON -DCRC32C_BUILD_TESTS=OFF -DCRC32C_USE_GLOG=OFF -DCRC32C_BUILD_BENCHMARKS=OFF
	cd $(call build,$@) && cmake --build static -j16
	cd $(call build,$@) && cmake --build shared -j16
	$(reset_install_dir) $@
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install static
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install shared
	touch $@

# Two patches two make it work with bundled
# A: Manually add rpath origin to libarrow_compute
# B: Add symlinks to versioned libraries in the install dir
#
# TODO: Upstream ARROW_RPATH_ORIGIN currently only sets the rpath for libarrow.so, but not for other libraries like libarrow_compute.so.
# Once that is fixed, we can start looking into the bundling options for pyarrow.
#
# ARROW_BUILD_SHARED=ON here also makes the pyarrow build shared.
$(call lib,arrow19-0-1):
	cd $(call build,$@)/cpp && rm -rf static
	cd $(call build,$@)/cpp && cmake -B static -DRapidJSON_SOURCE=BUNDLED -DCMAKE_SYSTEM_PROCESSOR="wasm32" -DCMAKE_SYSTEM_NAME="WASI" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR=lib/wasm32-wasi -DARROW_BUILD_SHARED=OFF -DARROW_BUILD_STATIC=ON --preset ninja-release-python-minimal -DARROW_IPC=ON
	cd $(call build,$@)/cpp && cmake --build static -j16 -v
	$(reset_install_dir) $@
	cd $(call build,$@)/cpp && DESTDIR=${PWD}/$@ cmake --install static
	touch $@
$(call lib,arrow):
	cd $(call build,$@)/cpp && rm -rf static
	cd $(call build,$@)/cpp && cmake -B static -DRapidJSON_SOURCE=BUNDLED -DCMAKE_SYSTEM_PROCESSOR="wasm32" -DCMAKE_SYSTEM_NAME="WASI" -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_LIBDIR=lib/wasm32-wasi -DARROW_BUILD_SHARED=OFF -DARROW_BUILD_STATIC=ON --preset ninja-release-python-minimal -DARROW_IPC=ON
	cd $(call build,$@)/cpp && cmake --build static -j16 -v
	$(reset_install_dir) $@
	cd $(call build,$@)/cpp && DESTDIR=${PWD}/$@ cmake --install static
	touch $@

$(call lib,rapidjson):
	cd $(call build,$@) && rm -rf header_only
	cd $(call build,$@) && cmake -B header_only -DCMAKE_BUILD_TYPE=Release -DRAPIDJSON_BUILD_TESTS=OFF -DRAPIDJSON_BUILD_EXAMPLES=OFF
	cd $(call build,$@) && cmake --build header_only -j16
	$(reset_install_dir) $@
	cd $(call build,$@) && DESTDIR=${PWD}/$@ cmake --install header_only
	sed -i 's|/usr/local/include|$${CMAKE_CURRENT_LIST_DIR}/../../../include|' ${PWD}/$@/usr/local/lib/cmake/RapidJSON/RapidJSONConfig.cmake
	touch $@

$(call lib,icu):
	cd $(call build,$@)/icu4c && rm -rf target && mkdir -p target
	cd $(call build,$@)/icu4c && cd target && ../source/runConfigureICU Linux --prefix=/usr/local --libdir='$${exec_prefix}/lib/wasm32-wasi' --disable-tools  --disable-tests  --disable-samples --disable-extras --enable-shared --enable-static
	cd $(call build,$@)/icu4c && cd target && make -j8
	$(reset_install_dir) $@
	cd $(call build,$@)/icu4c && cd target && make install DESTDIR=${PWD}/$@
	touch $@

$(call lib,ncurses):
	cd $(call build,$@) && ./configure --prefix=/usr/local --libdir='$${exec_prefix}/lib/wasm32-wasi' --with-normal --with-debug --without-tests --disable-home-terminfo  --enable-pc-files --enable-ext-colors --enable-const --enable-symlinks --with-pkg-config-libdir=/usr/local/lib/wasm32-wasi/pkgconfig # Shared is working but disabled for now --with-shared
	cd $(call build,$@) && make -j8
	cd $(call build,$@) && mv progs/tic progs/tic.old && cp /usr/bin/tic progs/tic # Use host tic for building
	$(reset_install_dir) $@
	cd $(call build,$@) && make install DESTDIR=${PWD}/$@
	cd $(call build,$@) && cp progs/tic.old ${PWD}/$@/usr/local/bin/tic # Restore the wasm tic
	touch $@

#####     Installing wheels and libs     #####

# Use `install` to install everything
# Use `install-SUBMODULE` to install a specific submodule
# Use `install-wheels` to install all wheels
# Use `install-libs` to install all libs

${WASIX_SYSROOT}/.%.installed: $(call tarxz,%)
	test -n "${WASIX_SYSROOT}" || (echo "You must set WASIX_SYSROOT to your wasix sysroot" && exit 1)
	tar mxJf $< -C ${WASIX_SYSROOT}
	touch $@

${INSTALL_DIR}/.%.installed: $(call whl,%)
	test -n "${INSTALL_DIR}" || (echo "You must set INSTALL_DIR to the python library path" && exit 1)
	unzip -oq $< -d ${INSTALL_DIR}
	touch $@

${INSTALL_DIR}/.pwb-%.installed: ${PYTHON_WASIX_BINARIES}/wheels/%.whl
	test -n "${INSTALL_DIR}" || (echo "You must set INSTALL_DIR to the python library path" && exit 1)
	unzip -oq $< -d ${INSTALL_DIR}
	touch $@

INSTALL_WHEELS_TARGETS=$(addprefix install-,$(WHEELS))
INSTALL_LIBS_TARGETS=$(addprefix install-,$(LIBS))
$(INSTALL_WHEELS_TARGETS): install-%: ${INSTALL_DIR}/.%.installed
$(INSTALL_LIBS_TARGETS): install-%: ${WASIX_SYSROOT}/.%.installed
# Install a wheel from python-wasix-binaries
INSTALL_PYTHON_WASIX_BINARIES_WHEELS_TARGETS=$(addprefix install-pwb-,$(PYTHON_WASIX_BINARIES_WHEELS))
$(INSTALL_PYTHON_WASIX_BINARIES_WHEELS_TARGETS): install-pwb-%: ${INSTALL_DIR}/.pwb-%.installed

init: $(addsuffix /.git,$(SUBMODULES))

clean: init
	rm -rf python python.webc
	rm -rf cross-venv native-venv
	rm -rf python-with-packages
	# Remove patched source repos
	rm -rf $(call prepared,*)
	# Remove active build directories
	rm -rf $(call build,*)
	# Remove unpacked packages
	rm -rf $(call lib,*)
	rm -rf $(call wheel,*)
	rm -rf $(call sdist,*)

clean-artifacts:
	rm -rf artifacts
	mkdir -p artifacts
	rm -rf $(call tarxz,*)
	rm -rf $(call targz,*)
	rm -rf $(call whl,*)

.SECONDARY: $(BUILT_SDISTS) $(BUILT_LIBS) $(BUILT_WHEELS) $(SUBMODULES) $(UNPACKED_LIBS)
.PHONY: all wheels libs external-wheels test install install-wheels install-libs clean init $(INSTALL_WHEELS_TARGETS) $(INSTALL_LIBS_TARGETS)