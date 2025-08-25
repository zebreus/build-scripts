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

package_list = 'package-list.jsonl'

wheel_files = glob.glob(os.path.join("artifacts", '*.whl'))
wheel_files += glob.glob(os.path.join("artifacts", '*.tar.gz')) # SDists
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'aiohttp*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'cryptography*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'ddtrace*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'httptools*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'jiter*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'orjson*.whl'))
wheel_files += glob.glob(os.path.join("python-wasix-binaries/wheels", 'peewee*.whl'))
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
    'artifacts/psycopg',  # For now we use psycopg builds from python-wasix-binaries
)
wheel_files = [f for f in wheel_files if not f.startswith(excluded_prefixes)]

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