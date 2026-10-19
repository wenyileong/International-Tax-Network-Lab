#!/usr/bin/env sh
# Regenerate the hashed lock files. Requires uv (pip install uv).
set -e
cd "$(dirname "$0")/.."
uv pip compile requirements/build.in --python-platform windows --python-version 3.12 --generate-hashes -o requirements/windows-build.lock
uv pip compile requirements/build.in --python-platform linux --python-version 3.12 --generate-hashes -o requirements/linux-build.lock
