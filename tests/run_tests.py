#!/usr/bin/env python3
"""Run all skill fixture suites offline; Python standard library, Bash and POSIX utilities."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main():
    scratch = ROOT / '.test-tmp'
    results = ROOT / '.test-results'
    scratch.mkdir(exist_ok=True)
    results.mkdir(exist_ok=True)
    env = dict(os.environ, TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE='1')
    runners = sorted(ROOT.glob('skills/*/scripts/fixtures/run_fixtures.sh'))
    if len(runners) != 14:
        print(f'FAIL: expected 14 fixture suites, found {len(runners)}')
        return 1
    failed = []
    for runner in runners:
        name = runner.parents[2].name
        run = subprocess.run(['bash', str(runner)], cwd=ROOT, env=env,
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (results / f'{name}.log').write_text(run.stdout, encoding='utf-8')
        print(f'{"PASS" if run.returncode == 0 else "FAIL"} {name} (exit {run.returncode})', flush=True)
        if run.returncode:
            failed.append(name)
            print('\n'.join(run.stdout.splitlines()[-12:]), flush=True)
    focused = ROOT / 'tests/test_configuration.py'
    if not focused.is_file():
        print('FAIL: tests/test_configuration.py is missing')
        return 1
    if focused.is_file():
        run = subprocess.run([sys.executable, '-B', str(focused)], cwd=ROOT, env=env,
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (results / 'configuration.log').write_text(run.stdout, encoding='utf-8')
        print(f'{"PASS" if run.returncode == 0 else "FAIL"} configuration', flush=True)
        if run.returncode:
            failed.append('configuration')
            print(run.stdout, flush=True)
    print(f'Fixture suites: {14 - len([n for n in failed if n != "configuration"])}/14 passed. Logs: {results}')
    return 1 if failed else 0

if __name__ == '__main__':
    raise SystemExit(main())
