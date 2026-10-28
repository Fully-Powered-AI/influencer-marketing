#!/usr/bin/env bash
# Runs every affiliate-onboarding fixture case with no network; exits non-zero on any miss.
set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -I "$here/run_cases.py"
