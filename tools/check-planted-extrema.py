#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Require extrema tests and supplemental hash checks to reject planted defects.

Stages sources privately. Compile/link errors, crashes and timeouts are errors
of this instrument, never successful mutation detection.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

SOURCE = Path('src/elementary')
PLANTS = [
    ('negative-order', '(sx & magnitude)', '(sx & 0u)'),
    ('positive-order', 'x ^ (sign | (sx & magnitude))',
     'x ^ (sign | (~sx & magnitude))'),
    ('selection-direction', 'maximum ? kx > ky : kx < ky',
     'maximum ? kx < ky : kx > ky'),
    ('zero-order', 'x ^ (sign | (sx & magnitude))',
     '((x & magnitude) == 0 ? sign : (x ^ (sign | (sx & magnitude))))'),
    ('single-quiet-nan', 'return nx ? y : x;', 'return nx ? x : y;'),
    ('both-nan-canonical', 'if (nx && ny) {\n      return canonical;',
     'if (nx && ny) {\n      return x;'),
    ('signaling-invalid', '(void)gmath_invalid();', '(void)0;'),
    ('second-signaling-nan', '(ny && (y & quiet) == 0)', '(0 && ny && (y & quiet) == 0)'),
    ('float-canonical', '0x7fc00000u, maximum', '0x7fc00001u, maximum'),
    ('float-quiet-mask', '0x00400000u, 0x7fc00000u', '0x00200000u, 0x7fc00000u'),
    ('float-maximum-direction', 'return extrema_float(x, y, 1);',
     'return extrema_float(x, y, 0);'),
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
    original = (SOURCE / 'extrema.c').read_text()
    run_env = dict(env, LD_LIBRARY_PATH=ld_path)

    def build_run(name, replacement=None):
        stage = work / name
        stage.mkdir(parents=True, exist_ok=True)
        text = original
        if replacement is not None:
            old, new = replacement
            if old == new or text.count(old) != 1:
                raise RuntimeError('%s: replacement must match once (found %d)' %
                                   (name, text.count(old)))
            text = text.replace(old, new, 1)
        (stage / 'extrema.c').write_text(text)
        shutil.copyfile(SOURCE / 'elem_common.h', stage / 'elem_common.h')
        compile_log = stage / 'compile.log'
        rc = command(cc + cflags + ['-I', str(stage), '-c', str(stage / 'extrema.c'),
                                   '-o', str(stage / 'extrema.o')], compile_log)
        if rc != 0:
            raise RuntimeError('%s: compile failed:\n%s' % (name, output_tail(compile_log)))
        link_log = stage / 'link.log'
        binary = stage / 'testExtrema'
        rc = command(cxx + ['-o', str(binary), test_object, str(stage / 'extrema.o')] +
                     ldflags, link_log)
        if rc != 0:
            raise RuntimeError('%s: link failed:\n%s' % (name, output_tail(link_log)))
        test_log = stage / 'test.log'
        rc = command([str(binary), '--gtest_filter=Extrema.*', '--gtest_brief=1'],
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
    for name, old, new in PLANTS:
        build_run(name, (old, new))
    # The generator must reject a wrong signed-zero rule before writing data.
    generator = Path('tools/oracle/gen_corpus_extrema.py').read_text()
    zero_rule = 'return (x | y) if minimum else (x & y)'
    wrong_rule = 'return (x & y) if minimum else (x | y)'
    if generator.count(zero_rule) != 1:
        raise RuntimeError('generator signed-zero mutation must match once')
    for changed in (False, True):
        name = 'oracle-mutated' if changed else 'oracle-control'
        stage = work / name
        stage.mkdir(parents=True, exist_ok=True)
        script = stage / 'generator.py'
        script.write_text(generator.replace(zero_rule, wrong_rule, 1) if changed else generator)
        log = stage / 'test.log'
        rc = command([sys.executable, str(script), '--out', str(stage / 'corpus'),
                      '--seed', '20261026', '--count', '0'], log)
        if changed:
            if rc != 1 or 'RuntimeError: extrema oracle self-check failed:' not in output_tail(log):
                raise RuntimeError('generator defect was not rejected by its self-check:\n' + output_tail(log))
        elif rc != 0:
            raise RuntimeError('unmodified generator failed:\n' + output_tail(log))
        print('  ok   %s %s' % (name, 'detected' if changed else 'passes'), flush=True)

    # Supplemental hash entries must be enforced, separately for each format.
    hash_source = Path('tests/corpus/trig.hash')
    hash_text = hash_source.read_text()
    hash_stage = work / 'hash-gate'
    hash_stage.mkdir(parents=True, exist_ok=True)
    for name in ('control', 'fmin', 'fmax', 'fminf', 'fmaxf'):
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
        if name != 'control' and ('check-corpus-hash: FAIL: %s:' % name) not in output_tail(log):
            raise RuntimeError('hash gate %s failed without detecting its corruption:\n%s' %
                               (name, output_tail(log)))
        print('  ok   hash-%s %s' % (name, 'passes' if name == 'control' else 'detected'), flush=True)
    # A dropped probe entry must not silently evade the committed name set.
    for name in ('fmin', 'fmax', 'fminf', 'fmaxf'):
        wrapper = hash_stage / ('omit-' + name)
        wrapper.write_text(
            '#!/usr/bin/env python3\n'
            'import subprocess, sys\n'
            'result = subprocess.run([' + repr(str(Path(probe).resolve())) +
            '] + sys.argv[1:], stdout=subprocess.PIPE)\n'
            'omitted = ' + repr({('math.' + name + '.hash').encode(),
                                 ('math.' + name + '.count').encode()}) + '\n'
            'for line in result.stdout.splitlines(keepends=True):\n'
            '    words = line.split()\n'
            '    if not words or words[0] not in omitted:\n'
            '        sys.stdout.buffer.write(line)\n'
            'sys.exit(result.returncode)\n')
        wrapper.chmod(0o755)
        log = hash_stage / ('omit-' + name + '.log')
        rc = command(['sh', 'tools/check-corpus-hash.sh', str(wrapper),
                      'tests/corpus', str(hash_source)], log, run_env)
        if rc != 1 or 'per-function name lists differ' not in output_tail(log):
            raise RuntimeError('omitted %s probe entry was not rejected by its name set:\n%s' %
                               (name, output_tail(log)))
        print('  ok   hash-omit-%s detected' % name, flush=True)
    print('check-planted-extrema: all %d implementation plants, oracle plant, 4 hash corruptions and 4 omitted probe entries detected; controls pass' % len(PLANTS))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as error:
        print('check-planted-extrema: FAIL: %s' % error, file=sys.stderr)
        sys.exit(1)
