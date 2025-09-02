#!/usr/bin/env bash
shopt -s extglob
set -xe

test -n "$BASH_VERSION" || { echo "This script requires bash"; exit 1; }
test -f "generate-index.py" || { echo "This script must be run from the root of the build-scripts directory"; exit 1; }
test -z "$(git status --porcelain)" || { echo "There are uncommitted changes in the repository. Please commit or stash them before running this script."; exit 1; }

# lib = C library
# wheel = python wheel with complex build steps
# pure-wheel = pure python wheel
TYPE="$1"
URL="$2"
NAME="$3"
VERSION="$4"

if [[ "$TYPE" != "wheel" && "$TYPE" != "lib" && "$TYPE" != "pure-wheel" ]]; then
    echo "Usage: $0 <lib|wheel|pure-wheel> <url> <name> [version]"
    exit 1
fi

test -n "$URL" || { echo "Usage: $0 <lib|wheel|pure-wheel> <url> <name> [version]"; exit 1; }
test -n "$NAME" || { echo "Usage: $0 <lib|wheel|pure-wheel> <url> <name> [version]"; exit 1; }

LIB_MARKER='<!-- LIB_VERSIONS_END -->'
WHEEL_MARKER='<!-- WHEEL_VERSIONS_END -->'
if [ "$TYPE" == "lib" ]; then
    MARKER="$LIB_MARKER"
else
    MARKER="$WHEEL_MARKER"
fi
README_FILE="README.md"

if [ ! -f "$README_FILE" ]; then
    echo "README.md file not found. Please run this script from the root of the build-scripts directory."
    exit 1
fi
grep -vq "${MARKER}" "$README_FILE" || { echo "The marker ${MARKER} does nto exist in the README.md file. Please add it before running this script."; exit 1; }

BUILD_SCRIPTS_ROOT="$(pwd)"
DIRECTORY="pkgs/$NAME.source"

test -e "$DIRECTORY" && { echo "Directory $DIRECTORY already exists. Please remove it before adding a new submodule."; exit 1; }

if ! git ls-remote "$URL" &>/dev/null; then
    echo "The URL $URL does not point to a valid git repository."
    exit 1
fi

git submodule add "$URL" "$DIRECTORY"


function resolve_version() {
    cd "$DIRECTORY"
    if [ -n "$VERSION" ]; then
        git checkout "$VERSION"
        return $?
    fi

    VERSION="$(git tag -l | sort -Vr | head -n 1)"
    if [ -n "$VERSION" ]; then
        echo "No tags found in the repository."
        return 1
    fi
    if [[ $VERSION == *-[[:alpha:]]* ]] then
        echo "The latest tag may not be the correct version: $VERSION"
        read -p "Do you want to use this version? (y/n): " choice
        if [[ "$choice" != "y" && "$choice" != "Y" ]]; then
            return 1
        fi
    fi
}

if ! resolve_version; then
    VERSION=
    echo "Failed to resolve version. Please specify a version manually."
    bash
    COMMIT=$(git rev-parse HEAD)
    echo "Continuing with the current commit: $COMMIT"
    echo "Please name the version for the readme file."
    while true; do
        read -p "Version name: " VERSION
        if [[ -n "$VERSION" ]]; then
            break
        else
            echo "Version name cannot be empty. Please try again."
        fi
    done
fi
echo "Using version: $VERSION"
cd ${BUILD_SCRIPTS_ROOT}
git add "$DIRECTORY" .gitmodules

README_VERSION="$(echo "$VERSION" | sed 's/[^0-9.]*//g')"

# Insert the version before the end marker
sed -i "/${MARKER}/i* $NAME: $README_VERSION" "$README_FILE"

git add "$README_FILE"
git commit -m "Add $NAME submodule at version $README_VERSION"

if [ "$TYPE" == "pure-wheel" ]; then
    set -xe
    MAKEFILE_WHEELS_MARKER='# WHEELS_END'
    sed -i "/${MAKEFILE_WHEELS_MARKER}/iWHEELS+=$NAME" "Makefile"

    make -B "pkgs/$NAME.source"
    make "pkgs/$NAME.tar.gz"
    make "pkgs/$NAME.whl"

    git add "Makefile"
    git commit -m "Add $NAME to the buildscripts"

    git add "pkgs/$NAME.tar.gz" "pkgs/$NAME.whl" artifacts/${NAME}*.whl artifacts/${NAME}*.tar.gz
    git commit -m "Add prebuilt wheel for $NAME"
fi