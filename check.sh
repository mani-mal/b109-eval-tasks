#!/usr/bin/env bash
# Run the full test suite. Exits non-zero if any test fails.
set -euo pipefail
cd "$(dirname "$0")"
exec python3 -m unittest discover -s tests -v
