#!/usr/bin/env bash
# Runs every creator-vetting fixture case; exits non-zero on any miss.
set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -I "$here/run_fixtures.py"
