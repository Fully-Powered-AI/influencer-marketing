#!/usr/bin/env bash
# Runs every fixture case for check_terms.py and scan_incoming.py and the drift checks.
# Exits non-zero if any case misses.
set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -I -B "$here/run_cases.py"
