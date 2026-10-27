#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Require exp2 tests and supplemental hash checks to reject planted defects.

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
    ('overflow-threshold', 'ax >= gmath_bits(1024.0)', 'ax >= gmath_bits(1023.0)'),
    ('underflow-threshold', 'ax >= gmath_bits(1075.0)', 'ax >= gmath_bits(1074.0)'),
    ('tiny-guard', 'if (ax <= gmath_bits(0x1p-54))', 'if (ax <= gmath_bits(0x1p-4))'),
    ('reduction-scale', 'double t = x * 128.0 + GMATH_EXP_MAGIC;', 'double t = x * 64.0 + GMATH_EXP_MAGIC;'),
    ('reduction-residual', 'double d = x - nd * 0x1p-7;', 'double d = x - nd * 0x1p-6;'),
    ('normal-integer-exponent', 'return gmath_double((uint64_t)(k + 1023) << 52);\n    }\n    return gmath_double(1ull', 'return gmath_double((uint64_t)(k + 1022) << 52);\n    }\n    return gmath_double(1ull'),
    ('subnormal-integer-exponent', 'return gmath_double(1ull << (unsigned)(k + 1074));', 'return gmath_double(2ull << (unsigned)(k + 1074));'),
    ('residual-conversion-sign', 'double r = d * GMATH_LN2_HI + d * GMATH_LN2_LO;', 'double r = -d * GMATH_LN2_HI + d * GMATH_LN2_LO;'),
    ('table-index', 'double y = exp_reconstruct(r, j);\n  uint64_t yb', 'double y = exp_reconstruct(r, 0);\n  uint64_t yb'),
    ('normal-packed-exponent', 'return gmath_double(yb + ((uint64_t)(int64_t)k << 52));', 'return gmath_double(yb + ((uint64_t)(int64_t)(k - 1) << 52));'),
    ('subnormal-scale', 'uint64_t scaled_bits = yb + ((uint64_t)(int64_t)(k + 1000) << 52);', 'uint64_t scaled_bits = yb + ((uint64_t)(int64_t)(k + 999) << 52);'),
    ('noninteger-underflow-flag', '  (void)gmath_underflow(0);\n  return result;\n}', '  (void)0;\n  return result;\n}'),
    ('negative-infinity', 'return (xb & GMATH_SIGN_BIT) ? 0.0 : x;', 'return (xb & GMATH_SIGN_BIT) ? 1.0 : x;'),
    ('signaling-nan-invalid', '    if (ax > GMATH_INF_BITS) {\n      return gmath_nan_of(x);\n    }\n    if (ax == GMATH_INF_BITS)', '    if (ax > GMATH_INF_BITS) {\n      return gmath_double(GMATH_QNAN_BITS);\n    }\n    if (ax == GMATH_INF_BITS)'),
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
    original = (SOURCE / 'explog.c').read_text()
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
        (stage / 'explog.c').write_text(text)
        for header in ('elem_common.h', 'explog_tables.h', 'logbase_constants.h'):
            shutil.copyfile(SOURCE / header, stage / header)
        compile_log = stage / 'compile.log'
        rc = command(cc + cflags + ['-I', str(stage), '-c', str(stage / 'explog.c'),
                                   '-o', str(stage / 'explog.o')], compile_log)
        if rc != 0:
            raise RuntimeError('%s: compile failed:\n%s' % (name, output_tail(compile_log)))
        link_log = stage / 'link.log'
        binary = stage / 'testExp2'
        rc = command(cxx + ['-o', str(binary), test_object, str(stage / 'explog.o')] +
                     ldflags, link_log)
        if rc != 0:
            raise RuntimeError('%s: link failed:\n%s' % (name, output_tail(link_log)))
        test_log = stage / 'test.log'
        rc = command([str(binary), '--gtest_filter=Exp2.*', '--gtest_brief=1'],
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
        return binary

    control_binary = build_run('control')
    for name, old, new in PLANTS:
        build_run(name, (old, new))
    # Prove the corpus loader rejects metadata, population and setting damage.
    corpus_lines = Path('tests/corpus/exp2.corpus').read_text().splitlines()
    rows = [i for i, line in enumerate(corpus_lines)
            if line.strip() and not line.lstrip().startswith('#')]
    headers = [i for i, line in enumerate(corpus_lines)
               if line.lstrip().startswith('#') and 'entries' in line.split()]
    if len(headers) != 1 or len(rows) <= 1001:
        raise RuntimeError('corpus instrument needs one entries header and more than 1001 rows')
    missing_header = [line for i, line in enumerate(corpus_lines) if i != headers[0]]
    truncated = [line for i, line in enumerate(corpus_lines) if i != rows[-1]]
    duplicated = list(corpus_lines)
    duplicated[rows[-1]] = corpus_lines[rows[0]]
    corpus_plants = (
        ('corpus-missing-header', missing_header, '1000',
         'missing required exp2 entries header'),
        ('corpus-truncated', truncated, '1000',
         'exp2 corpus count disagrees with header'),
        ('corpus-duplicate', duplicated, '1000', 'duplicate exp2 input word'),
        ('corpus-invalid-minimum', corpus_lines, 'garbage',
         'GMATH_EXP2_MIN_ENTRIES must be a complete positive decimal integer'),
    )
    for name, lines, minimum, diagnostic in corpus_plants:
        stage = work / name
        stage.mkdir(parents=True, exist_ok=True)
        (stage / 'exp2.corpus').write_text('\n'.join(lines) + '\n')
        log = stage / 'test.log'
        test_env = dict(run_env, GMATH_EXP2_CORPUS_DIR=str(stage),
                        GMATH_EXP2_MIN_ENTRIES=minimum)
        rc = command([str(control_binary),
                      '--gtest_filter=Exp2.CorpusIsWithinOneUlpAndRegressionBounds',
                      '--gtest_brief=1'], log, test_env)
        if rc != 1 or diagnostic not in output_tail(log):
            raise RuntimeError('%s corpus defect was not specifically detected (exit %d):\n%s' %
                               (name, rc, output_tail(log)))
        print('  ok   %s detected' % name, flush=True)

    # Run fixed oracle answers in the pinned image; test rounding and error signs.
    import importlib.util
    spec = importlib.util.spec_from_file_location('exp2_oracle', 'tools/oracle/oracle.py')
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    try:
        ref, _ = oracle.check_pin()
    except oracle.Unavailable as error:
        if oracle.REQUIRED:
            raise RuntimeError('pinned generator self-check required: %s' % error) from error
        print('  SKIPPED both pinned generator mutations: %s; committed corpus and implementation plants still checked' % error,
              flush=True)
        ref = None
    if ref is not None:
        generator = Path('tools/oracle/gen_corpus_exp2.py').read_text()
        oracle_plants = (
            ('oracle-odd-tie', 'q & 1', 'q & 0'),
            ('oracle-error-sign', 'error = (fr - exact_rounded) / unit',
             'error = (exact_rounded - fr) / unit'),
        )
        for name, old, new in oracle_plants:
            if generator.count(old) != 1:
                raise RuntimeError('%s generator mutation must match once' % name)
        for name, replacement in [('oracle-control', None)] + [
                (name, (old, new)) for name, old, new in oracle_plants]:
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
                if rc != 1 or 'RuntimeError: exp2 oracle self-check failed:' not in output_tail(log):
                    raise RuntimeError('generator defect was not rejected by its self-check:\n' + output_tail(log))
            elif rc != 0:
                raise RuntimeError('unmodified generator failed:\n' + output_tail(log))
            print('  ok   %s %s' % (name, 'detected' if changed else 'passes'), flush=True)

    # Supplemental hash entries must be enforced, separately for each format.
    hash_source = Path('tests/corpus/trig.hash')
    hash_text = hash_source.read_text()
    hash_stage = work / 'hash-gate'
    hash_stage.mkdir(parents=True, exist_ok=True)
    for name in ('control', 'exp2'):
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
    for name in ('exp2',):
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
    oracle_status = 'both oracle plants detected' if ref is not None else 'both oracle plants SKIPPED (no pinned image)'
    print('check-planted-exp2: all %d implementation plants, 4 corpus-loader plants, 1 hash corruption and 1 omitted probe entry detected; %s; controls pass' %
          (len(PLANTS), oracle_status))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as error:
        print('check-planted-exp2: FAIL: %s' % error, file=sys.stderr)
        sys.exit(1)
