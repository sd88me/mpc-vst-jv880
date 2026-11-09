#!/usr/bin/env bash
# The release zip. Builds the release identity ("JV-880", uid JV88) first, runs the offline test, then packs.
#   tools/package.sh   -> dist/JV-880-<version>-VST2-Plugins.zip   (version from plugin.json)
set -euo pipefail
cd "$(dirname "$0")/.."
./build-sdk.sh test
python3 tools/package.py
