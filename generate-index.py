#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "dumb-pypi>=1.15.0"
# ]
# requires-python = ">=3.10"
# ///
from dumb_pypi import main
import glob
import os
import json
import hashlib
import shutil
import subprocess
import zipfile

package_list = 'package-list.jsonl'

wheel_files = glob.glob(os.path.join("artifacts", '*.whl'))
wheel_files += glob.glob(os.path.join("artifacts", '*.tar.gz')) # SDists
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'aiohttp*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'cryptography*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'ddtrace*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'httptools*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'jiter*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'orjson*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'primp*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'psycopg*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'pydantic_core*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'pynacl*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'pyyaml*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'rpds_py*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'tiktoken*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'tokenizers*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'tornado*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'watchdog*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'watchfiles*.whl'))

# These packages will be excluded from the index
excluded_prefixes = (
    'artifacts/psycopg',  # For now we use psycopg builds from python-wasix-binaries,
)

# These packages will be included even if they don't contain native binaries
included_prefixes = (
    # Add package prefixes here that should always be included
    # Example: 'artifacts/somepackage',
)

def contains_native_binaries(file_path):
    """Check if a wheel file contains native binaries (.so, .so.*, or .wasm files).
    For tar.gz files, finds the corresponding wheel and checks that instead."""
    
    if not file_path.startswith('artifacts/'):
        # Only check files in artifacts/
        return True

    # If it's a tar.gz, find the corresponding wheel
    if file_path.endswith('.tar.gz'):
        basename = os.path.basename(file_path)
        package_version = basename.replace('.tar.gz', '')
        # Look for matching -none-any.whl file
        wheel_path = glob.glob(f'artifacts/{package_version}-*.whl')
        if len(wheel_path) == 0:
            # No matching wheel found
            print(f"WARNING: No matching wheel found for {basename}")
            exit(1)
        if len(wheel_path) > 1:
            print(f"WARNING: Multiple matching wheels found for {basename}, using the first one")
            exit(1)
        file_path = wheel_path[0]
    
    if not file_path.endswith('-none-any.whl'):
        # Only check none-any wheels
        return True
    
    try:
        with zipfile.ZipFile(file_path, 'r') as zip_file:
            for file_info in zip_file.namelist():
                # Check for .so, .so.*, or .wasm files
                if file_info.endswith('.so') or '.so.' in file_info or file_info.endswith('.wasm'):
                    return True
        return False
    except Exception as e:
        print(f"Warning: Could not check {file_path}: {e}")
        # If we can't check, include it to be safe
        return True

# Filter out excluded prefixes
wheel_files = [f for f in wheel_files if not f.startswith(excluded_prefixes)]

# Filter out -none-any.whl and corresponding tar.gz files that don't contain native binaries
filtered_wheel_files = []

for f in wheel_files:
    if (f.endswith('-none-any.whl') or f.endswith('.tar.gz')) and f.startswith('artifacts/'):
        # Always include if it matches included_prefixes
        if any(f.startswith(prefix) for prefix in included_prefixes):
            filtered_wheel_files.append(f)
        elif contains_native_binaries(f):
            print(f"Including {os.path.basename(f)} even though it's `none-any` - native binaries found")
            filtered_wheel_files.append(f)
        else:
            print(f"Excluding {os.path.basename(f)} - no native binaries found")
    else:
        filtered_wheel_files.append(f)

wheel_files = filtered_wheel_files

# Create JSON for each wheel file
with open(package_list, 'w') as package_list_file:
    for filepath in wheel_files:
        filename = os.path.basename(filepath)
        filedir = os.path.dirname(filepath)

        with open(filepath, 'rb') as f:
            content = f.read()
            sha256_hash = hashlib.sha256(content).hexdigest()

        timestamp_result = subprocess.run(["git", "log", "-1", "--pretty=%at", filename], capture_output=True, cwd=filedir)
        upload_timestamp = int(timestamp_result.stdout.decode('utf-8').partition('\n')[0] or "0") or None
        
        name_result = subprocess.run(["git", "log", "-1", "--pretty=%aN", filename], capture_output=True, cwd=filedir)
        uploader_name = name_result.stdout.decode('utf-8').partition('\n')[0] or "wasmer"

        entry = {
            "filename": filename,
            "hash": f"sha256={sha256_hash}",
            "uploaded_by": uploader_name,
            "upload_timestamp": upload_timestamp
        }

        json.dump(entry, package_list_file)
        package_list_file.write('\n')

main.main((
        '--package-list-json', package_list,
        '--output-dir', 'dist',
        '--packages-url', '../../packages/',
        '--title', 'WASIX Python native wheels',
))

# Copy all packages to dist/packages
os.makedirs('dist/packages', exist_ok=True)
for entry in wheel_files:
    dst = os.path.join('dist/packages', os.path.basename(entry))
    shutil.copy2(entry, dst)
