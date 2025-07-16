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

package_list = 'package-list.jsonl'

wheel_files = glob.glob(os.path.join("artifacts", '*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'cryptography*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'pydantic_core*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'jiter*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'lxml*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'rpds_py*.whl'))

# Create JSON for each wheel file
with open(package_list, 'w') as package_list_file:
    for filepath in wheel_files:
        filename = os.path.basename(filepath)

        with open(filepath, 'rb') as f:
            content = f.read()
            sha256_hash = hashlib.sha256(content).hexdigest()

        upload_timestamp = int(os.path.getmtime(filepath))

        entry = {
            "filename": filename,
            "hash": f"sha256={sha256_hash}",
            "uploaded_by": "wasmer",
            "upload_timestamp": upload_timestamp
        }

        json.dump(entry, package_list_file)
        package_list_file.write('\n')

main.main((
        '--package-list-json', package_list,
        '--output-dir', 'dist',
        '--packages-url', '../packages/',
        '--title', 'WASIX Python native wheels',
))

# Copy all packages to dist/packages
os.makedirs('dist/packages', exist_ok=True)
for entry in wheel_files:
    dst = os.path.join('dist/packages', os.path.basename(entry))
    shutil.copy2(entry, dst)