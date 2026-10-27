#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Require numerical certificates to reject assertion-stripping execution.

Optimized probes run before optional dependency imports, so they are mandatory
without the pinned image too. Normal positive controls run in that image.
This instrument uses explicit failures and remains effective under python -O.
"""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
ORACLE_DIR = ROOT / 'tools' / 'oracle'
REQUIRED = {'check_logf_budget.py', 'check_log10f_budget.py',
            'check_hypotf_budget.py', 'check_atan2f_budget.py'}
# Block target imports even when the caller happens to have dependencies.
# compile() inherits the child interpreter's optimization level.
OPTIMIZED_BOOTSTRAP = """
import builtins, sys
def checked_import(name, *args, **kwargs):
    raise RuntimeError('import before optimization rejection: ' + name)
builtins.__import__ = checked_import
script = sys.argv[1]
sys.argv = sys.argv[1:]
with open(script) as stream:
    code = compile(stream.read(), script, 'exec')
exec(code, {'__name__': '__main__', '__file__': script, '__package__': None})
"""
sys.path.insert(0, str(ORACLE_DIR))
import oracle


def run(argv, env=None):
    try:
        return subprocess.run(argv, cwd=ROOT, env=env, capture_output=True,
                              text=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError('certificate instrument failed: %s' % error) from error


def check_optimized(script, label, flags, optimize):
    environment = dict(os.environ)
    environment.pop('PYTHONOPTIMIZE', None)
    if optimize is not None:
        environment['PYTHONOPTIMIZE'] = optimize
    result = run([sys.executable] + flags + ['-c', OPTIMIZED_BOOTSTRAP, str(script)], environment)
    family = script.name[len('check_'):-len('_budget.py')]
    diagnostic = family + ' budget certificate requires assertions; run without -O/PYTHONOPTIMIZE'
    output = result.stdout + result.stderr
    if result.returncode != 1 or result.stdout or result.stderr.strip() != diagnostic:
        raise RuntimeError('%s %s did not reject optimized execution before PASS (status %d):\n%s' %
                           (script.name, label, result.returncode, output[-4000:]))
    print('  ok   %s %s rejected before certificate work' % (script.name, label), flush=True)


def main():
    scripts = sorted(ORACLE_DIR.glob('check_*_budget.py'))
    missing = REQUIRED - {script.name for script in scripts}
    if missing:
        raise RuntimeError('required numerical certificates missing: ' + ', '.join(sorted(missing)))
    for script in scripts:
        for label, flags, optimize in (('-O', ['-O'], None), ('-OO', ['-OO'], None),
                                      ('PYTHONOPTIMIZE=1', [], '1'),
                                      ('PYTHONOPTIMIZE=2', [], '2')):
            check_optimized(script, label, flags, optimize)
    try:
        image, provenance = oracle.check_pin(timeout=60)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError('pinned image discovery/version check timed out: %s' % error) from error
    except oracle.Unavailable as error:
        if oracle.REQUIRED:
            raise RuntimeError('normal pinned certificate controls required: %s' % error) from error
        print('check-budget-optimization: %d optimized probes rejected; normal pinned controls SKIPPED: %s' %
              (len(scripts) * 4, error))
        return 0
    print('check-budget-optimization: ' + provenance, flush=True)
    for script in scripts:
        argv = [oracle.ENGINE, 'run', '--rm', '--userns=keep-id',
                '-v', '%s:%s:z' % (ROOT, ROOT), '-w', str(ROOT), image,
                'env', '-u', 'PYTHONOPTIMIZE', 'python', str(script.relative_to(ROOT))]
        result = run(argv)
        output = result.stdout + result.stderr
        if result.returncode != 0 or 'PASS:' not in result.stdout:
            raise RuntimeError('%s normal pinned control failed (status %d):\n%s' %
                               (script.name, result.returncode, output[-4000:]))
        print('  ok   %s normal pinned control passes' % script.name, flush=True)
    print('check-budget-optimization: %d optimized probes rejected; %d normal pinned controls pass' %
          (len(scripts) * 4, len(scripts)))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as error:
        print('check-budget-optimization: FAIL: %s' % error, file=sys.stderr)
        sys.exit(1)
