#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Prove the exact-remainder tests reject individual implementation defects.

Stage remainder.c and its private header, never changing working sources.
Both ordinary and forced-portable unmodified controls must pass. Each literal
replacement must occur exactly once; build/link errors, crashes and timeouts
are failures of this instrument, never evidence of a detected arithmetic bug.
The test object needs only remainder.o, not the other math objects.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

SOURCE = Path('src/elementary')
PLANTS = [
    ('subnormal-modulo', 'return ax % ay;', 'return ax;'),
    ('chunk-modulo', 'r = (r << shift) % my;', 'r = (r << shift);'),
    ('normal-exponent', '((uint64_t)(ey + bias) << fraction)',
     '((uint64_t)(ey + bias + 1) << fraction)'),
    ('subnormal-scale', 'r >> (unsigned)(1 - bias - ey)',
     'r >> (unsigned)(2 - bias - ey)'),
    ('power-two-cutoff', 'if (gap >= (int)fraction)', 'if (gap >= 1)'),
    ('equal-exponent-subtraction', 'r = mx - my; /* ax > ay',
     'r = mx; /* ax > ay'),
    ('dividend-sign',
     'gmath_double(sign | remainder_magnitude(ax, ay, 52, 1023))',
     'gmath_double(remainder_magnitude(ax, ay, 52, 1023))'),
    ('signed-zero', 'return gmath_double(sign);', 'return gmath_double(0);'),
    ('invalid-flag', 'return gmath_invalid();',
     'return gmath_double(GMATH_QNAN_BITS);'),
    ('second-signaling-nan', '(void)gmath_nan_of(y);', '(void)y;'),
    ('float-canonical-nan', 'bits = 0x7fc00000u;\n  }\n  else if (ax == 0x7f800000u',
     'bits = 0x7fc00001u;\n  }\n  else if (ax == 0x7f800000u'),
    ('float-signaling-invalid', '      (void)gmath_invalid();\n    }\n    bits = 0x7fc00000u;',
     '      (void)0;\n    }\n    bits = 0x7fc00000u;'),
    ('float-sign', 'uint32_t sign = xb & 0x80000000u;', 'uint32_t sign = 0;'),
]


def output_tail(path):
    with path.open('rb') as stream:
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - 4000))
        return stream.read().decode('utf-8', errors='replace')


def command(argv, log, env=None):
    with log.open('w') as stream:
        try:
            result = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT,
                                    env=env, timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError('%s: %s' % (log, error)) from error
    return result.returncode


def main():
    env = os.environ
    try:
        work = Path(env['PLANT_WORK'])
        cc = shlex.split(env['PLANT_CC'])
        cflags = shlex.split(env['PLANT_CFLAGS'])
        cxx = shlex.split(env['PLANT_CXX'])
        ldflags = shlex.split(env['PLANT_LDFLAGS'])
        test_object = env['PLANT_TEST_OBJ']
        ld_path = env['PLANT_LD_PATH']
        probe = env['PLANT_PROBE']
    except KeyError as error:
        raise RuntimeError('missing required environment setting %s' % error) from error
    original = (SOURCE / 'remainder.c').read_text()
    run_env = dict(env, LD_LIBRARY_PATH=ld_path)

    def build_run(name, replacement=None, portable=False):
        stage = work / name
        stage.mkdir(parents=True, exist_ok=True)
        text = original
        if replacement is not None:
            old, new = replacement
            if old == new or text.count(old) != 1:
                raise RuntimeError('%s: replacement must match once (found %d)' %
                                   (name, text.count(old)))
            text = text.replace(old, new, 1)
        (stage / 'remainder.c').write_text(text)
        shutil.copyfile(SOURCE / 'elem_common.h', stage / 'elem_common.h')
        flags = cflags + (['-DGMATH_REMAINDER_PORTABLE_BITS'] if portable else [])
        compile_log = stage / 'compile.log'
        rc = command(cc + flags + ['-I', str(stage), '-c', str(stage / 'remainder.c'),
                                   '-o', str(stage / 'remainder.o')], compile_log)
        if rc != 0:
            raise RuntimeError('%s: compile failed:\n%s' % (name, output_tail(compile_log)))
        link_log = stage / 'link.log'
        binary = stage / 'testRemainder'
        rc = command(cxx + ['-o', str(binary), test_object, str(stage / 'remainder.o')] +
                     ldflags, link_log)
        if rc != 0:
            raise RuntimeError('%s: link failed:\n%s' % (name, output_tail(link_log)))
        test_log = stage / 'test.log'
        rc = command([str(binary), '--gtest_filter=Remainder.*', '--gtest_brief=1'],
                     test_log, run_env)
        if rc not in (0, 1):
            raise RuntimeError('%s: test crashed or exited unexpectedly (%d):\n%s' %
                               (name, rc, output_tail(test_log)))
        if replacement is None and rc != 0:
            raise RuntimeError('%s: unmodified control failed:\n%s' %
                               (name, output_tail(test_log)))
        if replacement is not None and rc != 1:
            raise RuntimeError('%s: defect escaped the tests' % name)
        print('  ok   %s %s' % (name, 'passes' if replacement is None else 'detected'), flush=True)

    build_run('control')
    build_run('control-portable', portable=True)
    for name, old, new in PLANTS:
        build_run(name, (old, new))
    # A broken oracle must reject its fixed IEEE answers before writing data.
    generator = Path('tools/oracle/gen_corpus_remainder.py').read_text()
    quotient = 'n = abs(ratio.numerator) // ratio.denominator'
    wrong = 'n = (abs(ratio.numerator) + ratio.denominator // 2) // ratio.denominator'
    if generator.count(quotient) != 1:
        raise RuntimeError('generator quotient mutation must match once')
    for changed in (False, True):
        name = 'oracle-mutated' if changed else 'oracle-control'
        stage = work / name
        stage.mkdir(parents=True, exist_ok=True)
        script = stage / 'generator.py'
        script.write_text(generator.replace(quotient, wrong, 1) if changed else generator)
        log = stage / 'test.log'
        rc = command([sys.executable, str(script), '--out', str(stage / 'corpus'),
                      '--seed', '20261026', '--count', '0'], log)
        if changed:
            if rc != 1 or 'RuntimeError: remainder oracle self-check failed:' not in output_tail(log):
                raise RuntimeError('generator defect was not rejected by its self-check:\n' + output_tail(log))
        elif rc != 0:
            raise RuntimeError('unmodified generator failed:\n' + output_tail(log))
        print('  ok   %s %s' % (name, 'detected' if changed else 'passes'), flush=True)

    # Supplemental hash entries must be enforced, separately for each format.
    hash_source = Path('tests/corpus/trig.hash')
    hash_text = hash_source.read_text()
    hash_stage = work / 'hash-gate'
    hash_stage.mkdir(parents=True, exist_ok=True)
    for name in ('control', 'fmod', 'fmodf'):
        target = hash_source
        if name != 'control':
            lines = hash_text.splitlines()
            matches = [i for i, line in enumerate(lines)
                       if line.split()[:2] == ['fn', name]]
            if len(matches) != 1:
                raise RuntimeError('hash mutation for %s must match one entry' % name)
            words = lines[matches[0]].split()
            if words[2] == '0000000000000000':
                raise RuntimeError('hash mutation for %s would change nothing' % name)
            words[2] = '0000000000000000'
            lines[matches[0]] = ' '.join(words)
            target = hash_stage / (name + '.hash')
            target.write_text('\n'.join(lines) + '\n')
        log = hash_stage / (name + '.log')
        rc = command(['sh', 'tools/check-corpus-hash.sh', probe, 'tests/corpus',
                      str(target)], log, run_env)
        if rc != (0 if name == 'control' else 1):
            raise RuntimeError('hash gate %s returned %d:\n%s' % (name, rc, output_tail(log)))
        print('  ok   hash-%s %s' % (name, 'passes' if name == 'control' else 'detected'), flush=True)
    print('check-planted-remainder: all %d implementation plants, oracle plant and 2 hash corruptions seen; controls pass' % len(PLANTS))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as error:
        print('check-planted-remainder: FAIL: %s' % error, file=sys.stderr)
        sys.exit(1)
