#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Require floatbasic tests and supplemental hash checks to reject planted defects.

Stages sources privately. Compile/link errors, crashes and timeouts are errors
of this instrument, never successful mutation detection.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time

SOURCE = Path('src/elementary')
FUNCTIONS = ('floorf', 'ceilf', 'truncf', 'roundf', 'rintf', 'fabsf', 'copysignf', 'sqrtf')
PLANTS = [
    ('floor-direction', 'return floatbasic_round(x, FLOAT_BASIC_FLOOR);', 'return floatbasic_round(x, FLOAT_BASIC_CEIL);'),
    ('ceil-direction', 'return floatbasic_round(x, FLOAT_BASIC_CEIL);', 'return floatbasic_round(x, FLOAT_BASIC_FLOOR);'),
    ('trunc-direction', 'return floatbasic_round(x, FLOAT_BASIC_TRUNC);', 'return floatbasic_round(x, FLOAT_BASIC_ROUND);'),
    ('round-half-away', 'increment = a >= FLOAT_BASIC_HALF;', 'increment = a > FLOAT_BASIC_HALF;'),
    ('rint-small-even-tie', 'increment = a > FLOAT_BASIC_HALF;', 'increment = a >= FLOAT_BASIC_HALF;'),
    ('rint-integer-parity', '((base >> cut) & 1u)', '(((base >> cut) & 1u) == 0)'),
    ('fraction-cut', 'unsigned cut = 150u - (a >> 23);', 'unsigned cut = 149u - (a >> 23);'),
    ('fraction-mask', 'uint32_t mask = unit - 1u;', 'uint32_t mask = unit;'),
    ('negative-zero-floor', 'increment = sign != 0 && a != 0;', 'increment = sign != 0;'),
    ('large-integral-fast-path', 'if (a >= FLOAT_BASIC_TWO23)', 'if (a >= FLOAT_BASIC_ONE)'),
    ('rounded-sign', 'return floatbasic_value(sign | (base + (increment ? unit : 0)));', 'return floatbasic_value(base + (increment ? unit : 0));'),
    ('canonical-nan', '#define FLOAT_BASIC_NAN 0x7fc00000u', '#define FLOAT_BASIC_NAN 0x7fc00001u'),
    ('signaling-nan-invalid', 'volatile float t = x - x;', 'volatile float t = x;'),
    ('fabs-sign', 'float gmath_fabsf(float x) {\n  uint32_t a = floatbasic_word(x) & FLOAT_BASIC_ABS;', 'float gmath_fabsf(float x) {\n  uint32_t a = floatbasic_word(x);'),
    ('copysign-direction', 'a | (floatbasic_word(y) & FLOAT_BASIC_SIGN)', 'a | ((floatbasic_word(y) ^ FLOAT_BASIC_SIGN) & FLOAT_BASIC_SIGN)'),
    ('copysign-second-nan', 'float gmath_copysignf(float x, float y) {', 'float gmath_copysignf(float x, float y) {\n  volatile float t = y - y;\n  (void)t;'),
    ('sqrt-result', 'double root = gmath_sqrt_impl((double)x);', 'double root = 2.0 * gmath_sqrt_impl((double)x);'),
    ('sqrt-one-ulp', 'return (float)root;', 'uint32_t result = floatbasic_word((float)root);\n  if (result > 0 && result < FLOAT_BASIC_INF) {\n    ++result;\n  }\n  return floatbasic_value(result);'),
]

STATE_PLANTS = [
    ('errno-change', 'errno = EDOM;', 'result_errno'),
    ('incoming-flags-cleared', '(void)feclearexcept(FE_ALL_EXCEPT);', 'result_flags & (policy.required | existing)'),
    ('rounding-mode-change', '(void)fesetround(FE_DOWNWARD);', 'result_mode'),
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
    original = (SOURCE / 'floatbasic.c').read_text()
    run_env = dict(env, LD_LIBRARY_PATH=ld_path)

    def build_run(name, replacement=None, portable=False, diagnostic=None, test_filter='Floatbasic.*'):
        stage = work / name
        stage.mkdir(parents=True, exist_ok=True)
        text = original
        if replacement is not None:
            old, new = replacement
            if old == new or text.count(old) != 1:
                raise RuntimeError('%s: replacement must match once (found %d)' %
                                   (name, text.count(old)))
            text = text.replace(old, new, 1)
        text = '#include <errno.h>\n#include <fenv.h>\n' + text
        (stage / 'floatbasic.c').write_text(text)
        for header in ('elem_common.h', 'sqrt_impl.h', 'hypot_table.h'):
            shutil.copyfile(SOURCE / header, stage / header)
        planted = replacement is not None
        compile_log = stage / 'compile.log'
        flags = cflags + (['-DGMATH_SQRT_PORTABLE'] if portable else [])
        rc = command(cc + flags + ['-I', str(stage), '-c', str(stage / 'floatbasic.c'),
                                   '-o', str(stage / 'floatbasic.o')], compile_log)
        if rc != 0:
            raise RuntimeError('%s: compile failed:\n%s' % (name, output_tail(compile_log)))
        link_log = stage / 'link.log'
        binary = stage / 'testFloatbasic'
        rc = command(cxx + ['-o', str(binary), test_object, str(stage / 'floatbasic.o')] +
                     ldflags, link_log)
        if rc != 0:
            raise RuntimeError('%s: link failed:\n%s' % (name, output_tail(link_log)))
        test_log = stage / 'test.log'
        rc = command([str(binary), '--gtest_filter=' + test_filter, '--gtest_brief=1'],
                     test_log, run_env)
        if rc not in (0, 1):
            raise RuntimeError('%s: test crashed or exited unexpectedly (%d):\n%s' %
                               (name, rc, output_tail(test_log)))
        if not planted and rc != 0:
            raise RuntimeError('%s: unmodified control failed:\n%s' %
                               (name, output_tail(test_log)))
        if planted and rc != 1:
            raise RuntimeError('%s: defect escaped the tests' % name)
        if diagnostic is not None and diagnostic not in test_log.read_text():
            raise RuntimeError('%s: state defect failed without its specific assertion %r:\n%s' %
                               (name, diagnostic, output_tail(test_log)))
        print('  ok   %s %s' % (name, 'detected' if planted else 'passes'), flush=True)
        return binary

    control_binary = build_run('control')
    portable_binary = build_run('control-portable', portable=True)
    for name, old, new in PLANTS:
        build_run(name, (old, new), diagnostic='sqrtf input ' if name == 'sqrt-one-ulp' else None,
                  test_filter='Floatbasic.CorpusIsExact' if name == 'sqrt-one-ulp' else 'Floatbasic.*')
    for name, statement, diagnostic in STATE_PLANTS:
        signature = 'float gmath_floorf(float x) {'
        build_run(name, (signature, signature + '\n  ' + statement), diagnostic=diagnostic)
    # Check both unary and binary input populations with otherwise valid files.
    for function in ('floorf', 'copysignf'):
        original_corpus = Path('tests/corpus') / (function + '.corpus')
        corpus_lines = original_corpus.read_text().splitlines()
        rows = [i for i, line in enumerate(corpus_lines)
                if line.strip() and not line.lstrip().startswith('#')]
        headers = [i for i, line in enumerate(corpus_lines)
                   if line.lstrip().startswith('#') and 'entries' in line.split()]
        if len(headers) != 1 or len(rows) <= 1001:
            raise RuntimeError('%s instrument needs one entries header and more than 1001 rows' % function)
        missing_header = [line for i, line in enumerate(corpus_lines) if i != headers[0]]
        truncated = [line for i, line in enumerate(corpus_lines) if i != rows[-1]]
        duplicated = list(corpus_lines)
        duplicated[rows[-1]] = corpus_lines[rows[0]]
        duplicate_header = list(corpus_lines)
        duplicate_header.insert(headers[0], corpus_lines[headers[0]])
        invalid_header = list(corpus_lines)
        tokens = invalid_header[headers[0]].split()
        tokens[tokens.index('entries') + 1] = 'garbage'
        invalid_header[headers[0]] = ' '.join(tokens)
        malformed = {}
        for kind in ('incomplete', 'extra', 'overflow', 'not-binary32'):
            lines = list(corpus_lines)
            fields = lines[rows[-1]].split()
            if kind == 'incomplete':
                fields.pop()
            elif kind == 'extra':
                fields.append('0')
            elif kind == 'overflow':
                fields[0] = '10000000000000000'
            else:
                fields[0] = '3ff0000000000001'
            lines[rows[-1]] = ' '.join(fields)
            malformed[kind] = lines
        corpus_plants = (
            ('missing-header', missing_header, '1000',
             'missing required %s entries header' % function),
            ('truncated', truncated, '1000', '%s corpus count disagrees with header' % function),
            ('duplicate', duplicated, '1000', 'duplicate %s input' % function),
            ('invalid-minimum', corpus_lines, 'garbage',
             'GMATH_FLOATBASIC_MIN_ENTRIES must be a complete positive decimal integer'),
            ('duplicate-header', duplicate_header, '1000', 'duplicate %s entries header' % function),
            ('invalid-header', invalid_header, '1000', 'invalid %s entries header' % function),
            ('incomplete', malformed['incomplete'], '1000', 'bad %s corpus row' % function),
            ('extra', malformed['extra'], '1000', 'bad %s corpus row' % function),
            ('overflow', malformed['overflow'], '1000', 'bad %s corpus row' % function),
            ('not-binary32', malformed['not-binary32'], '1000', 'invalid %s binary32 representation' % function),
        )
        for defect, lines, minimum, diagnostic in corpus_plants:
            name = 'corpus-' + function + '-' + defect
            stage = work / name
            stage.mkdir(parents=True, exist_ok=True)
            for other in FUNCTIONS:
                shutil.copyfile(Path('tests/corpus') / (other + '.corpus'), stage / (other + '.corpus'))
            (stage / (function + '.corpus')).write_text('\n'.join(lines) + '\n')
            log = stage / 'test.log'
            test_env = dict(run_env, GMATH_FLOATBASIC_CORPUS_DIR=str(stage),
                            GMATH_FLOATBASIC_MIN_ENTRIES=minimum)
            rc = command([str(control_binary), '--gtest_filter=Floatbasic.CorpusIsExact',
                          '--gtest_brief=1'], log, test_env)
            if rc != 1 or diagnostic not in output_tail(log):
                raise RuntimeError('%s corpus defect was not specifically detected (exit %d):\n%s' %
                                   (name, rc, output_tail(log)))
            print('  ok   %s detected' % name, flush=True)


    # Run fixed oracle answers in the pinned image; test exact sqrt certification.
    import importlib.util
    spec = importlib.util.spec_from_file_location('floatbasic_oracle', 'tools/oracle/oracle.py')
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    try:
        ref, _ = oracle.check_pin()
    except oracle.Unavailable as error:
        if oracle.REQUIRED:
            raise RuntimeError('pinned generator self-check required: %s' % error) from error
        print('  SKIPPED pinned generator mutation: %s; committed corpus and implementation plants still checked' % error,
              flush=True)
        ref = None
    if ref is not None:
        generator = Path('tools/oracle/gen_corpus_floatbasic.py').read_text()
        oracle_plants = (
            ('oracle-sqrt-certificate',
             "raise RuntimeError('floatbasic sqrt exact midpoint-square certificate failed')", 'pass',
             'RuntimeError: floatbasic oracle self-check failed: sqrt certificate accepted wrong result'),
            ('oracle-fraction-rounding', 'result = n // d', 'result = (n + d - 1) // d',
             'RuntimeError: floatbasic Fraction/MPFR rounding disagreement'),
            ('oracle-signed-zero', 'rb = (raw & SIGN) if result == 0 else word(float(result))',
             'rb = 0 if result == 0 else word(float(result))',
             'RuntimeError: floatbasic Fraction/MPFR rounding disagreement'),
            ('oracle-copy-sign', 'result = (x & ~SIGN) | (y & SIGN)',
             'result = (x & ~SIGN) | ((y ^ SIGN) & SIGN)',
             'RuntimeError: floatbasic copy-sign bit/reference disagreement'),
            ('oracle-wrong-sqrt', 'result = word(float(reference))',
             'result = word(float(reference)) + 1',
             'RuntimeError: floatbasic sqrt exact midpoint-square certificate failed'),
        )
        for name, old, new, diagnostic in oracle_plants:
            if generator.count(old) != 1:
                raise RuntimeError('%s generator mutation must match once' % name)
        for name, replacement, diagnostic in [('oracle-control', None, None)] + [
                (name, (old, new), diagnostic) for name, old, new, diagnostic in oracle_plants]:
            changed = replacement is not None
            stage = work / name
            stage.mkdir(parents=True, exist_ok=True)
            script = stage / 'generator.py'
            text = generator.replace(*replacement, 1) if changed else generator
            script.write_text(text)
            log = stage / 'test.log'
            run = "import runpy; runpy.run_path(%r)['self_check']()" % str(script)
            argv = [oracle.ENGINE, 'run', '--rm', '--userns=keep-id',
                    '-v', '%s:%s:z' % (oracle.ROOT, oracle.ROOT), '-w', oracle.ROOT,
                    ref, 'python', '-c', run]
            rc = command(argv, log)
            if changed:
                if rc != 1 or diagnostic not in output_tail(log):
                    raise RuntimeError('generator defect was not rejected by its self-check:\n' + output_tail(log))
            elif rc != 0:
                raise RuntimeError('unmodified generator failed:\n' + output_tail(log))
            print('  ok   %s %s' % (name, 'detected' if changed else 'passes'), flush=True)

        fresh = work / 'fresh-corpus'
        fresh.mkdir(parents=True, exist_ok=True)
        seed = env.get('GMATH_ORACLE_SEED', str(time.time_ns() & 0xffffffff))
        print('  fresh floatbasic ordinary/portable seed %s' % seed, flush=True)
        log = fresh / 'generate.log'
        argv = [oracle.ENGINE, 'run', '--rm', '--userns=keep-id',
                '-v', '%s:%s:z' % (oracle.ROOT, oracle.ROOT), '-w', oracle.ROOT,
                ref, 'python', 'tools/oracle/gen_corpus_floatbasic.py', '--fresh',
                '--out', str(fresh), '--seed', seed, '--count', '3000']
        rc = command(argv, log)
        if rc != 0:
            raise RuntimeError('fresh generator failed for seed %s (exit %d):\n%s' %
                               (seed, rc, output_tail(log)))
        for label, binary in (('ordinary', control_binary), ('portable', portable_binary)):
            log = fresh / (label + '.log')
            test_env = dict(run_env, GMATH_FLOATBASIC_CORPUS_DIR=str(fresh),
                            GMATH_FLOATBASIC_MIN_ENTRIES='1000')
            rc = command([str(binary), '--gtest_filter=Floatbasic.*', '--gtest_brief=1'], log, test_env)
            if rc != 0:
                raise RuntimeError('fresh %s control failed for seed %s (exit %d):\n%s' %
                                   (label, seed, rc, output_tail(log)))
            print('  ok   fresh-%s control passes' % label, flush=True)

    # Supplemental hash entries must be enforced, separately for each format.
    hash_source = Path('tests/corpus/trig.hash')
    hash_text = hash_source.read_text()
    hash_stage = work / 'hash-gate'
    hash_stage.mkdir(parents=True, exist_ok=True)
    for name in ('control',) + FUNCTIONS:
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
    for name in FUNCTIONS:
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
    oracle_status = 'all 5 oracle plants detected; fresh ordinary/portable controls pass' if ref is not None else '5 oracle plants and fresh ordinary/portable controls SKIPPED (no pinned image)'
    print('check-planted-floatbasic: all %d implementation plants, 20 corpus-loader plants, 8 hash corruptions and 8 omitted probe entries detected; %s; controls pass' %
          (len(PLANTS) + len(STATE_PLANTS), oracle_status))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as error:
        print('check-planted-floatbasic: FAIL: %s' % error, file=sys.stderr)
        sys.exit(1)
