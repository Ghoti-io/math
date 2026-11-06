#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Compile the direct-source corpus client with strict downstream flags."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cc', default='cc')
    parser.add_argument('--fp-flags', default='')
    parser.add_argument('--runner', default='')
    parser.add_argument('--platform-libs', default='', help='test-client link libraries, e.g. -lm for fenv')
    parser.add_argument('--generated', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    (work / 'status.json').unlink(missing_ok=True)
    expected = {}
    for line in (root / 'tests/corpus/trig.hash').read_text().splitlines():
        fields = line.split()
        if fields and fields[0] == 'fn':
            expected[fields[1]] = (fields[2], int(fields[3]))
        elif fields and fields[0] == 'hash':
            aggregate_hash = fields[1]
        elif fields and fields[0] == 'count':
            aggregate_count = int(fields[1])
    expected['trig'] = (aggregate_hash, aggregate_count)
    sources = [root / 'tools/corpus-hash.c']
    for directory in ('elementary', 'decimal'):
        sources.extend(sorted((root / 'src' / directory).glob('*.c')))
    flags = ['-std=c17', '-O2', '-pedantic-errors', '-Wall', '-Wextra',
             '-Werror', '-ffp-contract=off', '-DGMATH_BUILD',
             '-I' + str(root / 'include'), '-I' + str(args.generated.resolve())]
    extra = shlex.split(args.fp_flags)
    if any(flag not in ('-msse2', '-mfpmath=sse') for flag in extra):
        raise RuntimeError('floating-point flags must not override strict warnings')
    # Calibrate the exact warning policy before compiling the real population.
    for tag, body, should_pass in [
            ('clean', 'int strict_clean(void) { return 0; }\n', True),
            ('unused', 'static int strict_unused(void) { return 0; }\n', False)]:
        source = work / (tag + '.c')
        source.write_text(body)
        command = shlex.split(args.cc) + flags + extra + ['-c', str(source), '-o', str(work / (tag + '.o'))]
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=60)
        (work / (tag + '.log')).write_text(result.stdout + result.stderr)
        if should_pass and result.returncode != 0:
            raise RuntimeError('strict warning clean control did not compile')
        if not should_pass and (result.returncode == 0 or 'unused-function' not in result.stderr):
            raise RuntimeError('strict unused-function warning control was not rejected')
    libraries = shlex.split(args.platform_libs)
    if any(not flag.startswith('-l') or len(flag) <= 2 for flag in libraries):
        raise RuntimeError('platform libraries must be -l options, not compiler overrides')
    records = []
    for tag, portable, planted in [('default', False, False),
                                    ('portable', True, False),
                                    ('planted', False, True),
                                    ('portable-planted', True, True)]:
        binary = work / tag
        command = shlex.split(args.cc) + flags + extra
        if portable:
            command.append('-DGMATH_SQRT_PORTABLE')
        if planted:
            command.append('-DGMATH_PLANT_BIT')
        command += [str(path) for path in sources] + ['-o', str(binary)] + libraries
        with (work / (tag + '.compile.log')).open('w') as stream:
            subprocess.run(command, cwd=root, stdout=stream, stderr=subprocess.STDOUT,
                           timeout=600, check=True)
        run_command = shlex.split(args.runner) + [str(binary), str(root / 'tests/corpus')]
        with (work / (tag + '.stdout')).open('w') as stdout, \
                (work / (tag + '.stderr')).open('w') as stderr:
            subprocess.run(run_command, cwd=root, stdout=stdout, stderr=stderr,
                           timeout=300, check=True)
        fields = {}
        for line in (work / (tag + '.stdout')).read_text().splitlines():
            words = line.split()
            if len(words) == 2:
                if words[0] in fields:
                    raise RuntimeError('duplicate corpus result: ' + words[0])
                fields[words[0]] = words[1]
        for name, (digest, count) in expected.items():
            observed_hash = fields['math.' + name + '.hash']
            observed_count = int(fields['math.' + name + '.count'])
            if observed_count != count:
                raise RuntimeError(tag + ': corpus count changed: ' + name)
            if (not planted or name not in ('sin', 'trig')) and observed_hash != digest:
                raise RuntimeError(tag + ': corpus hash changed: ' + name)
        if planted and any(fields['math.' + name + '.hash'] == expected[name][0]
                           for name in ('sin', 'trig')):
            raise RuntimeError(tag + ': planted bit escaped detection')
        records.append({'variant': tag, 'compile': command, 'run': run_command,
                        'hash': fields['math.trig.hash'], 'count': aggregate_count,
                        'planted': planted})
        print('strict-build: ' + tag + ' ' + fields['math.trig.hash'] + ' ' +
              str(aggregate_count) + (' (planted mismatch detected)' if planted else ''), flush=True)
    (work / 'status.json').write_text(json.dumps({'actual_exit': 0, 'variants': records},
                                                sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
