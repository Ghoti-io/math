#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Require exp2f tests and supplemental hash checks to reject planted defects.

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
PLANTS = [
    ('quiet-mask', '(f_abs & 0x00400000u) == 0', '(f_abs & 0x00200000u) == 0'),
    ('canonical-nan', 'return exp2f_value(0x7fc00000u);', 'return exp2f_value(0x7fc00001u);'),
    ('signaling-invalid', 'if ((f_abs & 0x00400000u) == 0) {\n      (void)gmath_invalid();', 'if ((f_abs & 0x00400000u) == 0) {\n      (void)0;'),
    ('infinity-polarity', 'return (f_word & 0x80000000u) ? 0.0f : x;', 'return (f_word & 0x80000000u) ? x : 0.0f;'),
    ('overflow-threshold', 'if (x >= 128.0f)', 'if (x >= 127.0f)'),
    ('underflow-threshold', 'if (x <= -150.0f)', 'if (x <= -149.0f)'),
    ('overflow-flags', '(void)gmath_overflow(0);\n    return exp2f_value(0x7f800000u);', '(void)0;\n    return exp2f_value(0x7f800000u);'),
    ('underflow-tail-flags', 'if (x <= -150.0f) {\n    (void)gmath_underflow(0);', 'if (x <= -150.0f) {\n    (void)0;'),
    ('tiny-range', 'if (f_abs <= 0x32800000u)', 'if (f_abs <= 0x3d800000u)'),
    ('tiny-inexact', 'return (float)(1.0 + f_wide);', 'return 1.0f;'),
    ('reduction-scale', 'double f_t = f_wide * 128.0 + GMATH_EXP_MAGIC;', 'double f_t = f_wide * 64.0 + GMATH_EXP_MAGIC;'),
    ('residual-grid', 'double f_d = f_wide - f_nd * 0x1p-7;', 'double f_d = f_wide - f_nd * 0x1p-6;'),
    ('normal-integer-pack', 'return exp2f_value((uint32_t)(f_k + 127) << 23);', 'return exp2f_value((uint32_t)(f_k + 126) << 23);'),
    ('subnormal-integer-pack', 'return exp2f_value(1u << (unsigned)(f_k + 149));', 'return exp2f_value(2u << (unsigned)(f_k + 149));'),
    ('residual-sign', 'double f_r = f_d * GMATH_LN2_HI + f_d * GMATH_LN2_LO;', 'double f_r = -f_d * GMATH_LN2_HI + f_d * GMATH_LN2_LO;'),
    ('table-index', 'exp_reconstruct(f_r, f_j)', 'exp_reconstruct(f_r, 0)'),
    ('scale-exponent', '(uint64_t)(f_k + 1023) << 52', '(uint64_t)(f_k + 1022) << 52'),
    ('final-float-ulp', 'float f_result = (float)f_scaled;', 'float f_result = (float)f_scaled;\n  uint32_t f_mutant;\n  memcpy(&f_mutant, &f_result, sizeof f_mutant);\n  if (f_mutant > 0 && f_mutant < 0x7f800000u) {\n    f_result = exp2f_value(f_mutant + 1u);\n  }'),
    ('subnormal-underflow-suppressed', '    (void)gmath_underflow(0);\n  }\n  return f_result;', '    (void)feclearexcept(FE_UNDERFLOW);\n  }\n  return f_result;'),
    ('normal-inexact-suppressed', '  return f_result;', '  if (f_result_word >= 0x00800000u) {\n    (void)feclearexcept(FE_INEXACT);\n  }\n  return f_result;'),
]
STATE_PLANTS = [('errno-change', 'errno = EDOM;', 'error'),
                ('incoming-flags-cleared', '(void)feclearexcept(FE_ALL_EXCEPT);', 'flags'),
                ('rounding-mode-change', '(void)fesetround(FE_UPWARD);', 'rounding')]


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

    def build_run(name, replacement=None, diagnostic=None, test_filter='Exp2f.*'):
        stage = work / name
        stage.mkdir(parents=True, exist_ok=True)
        text = original
        if replacement is not None:
            old, new = replacement
            if old == new or text.count(old) != 1:
                raise RuntimeError('%s: replacement must match once (found %d)' %
                                   (name, text.count(old)))
            text = text.replace(old, new, 1)
        (stage / 'explog.c').write_text('#include <errno.h>\n#include <fenv.h>\n' + text)
        for header in ('elem_common.h', 'explog_tables.h', 'logbase_constants.h'):
            shutil.copyfile(SOURCE / header, stage / header)
        compile_log = stage / 'compile.log'
        rc = command(cc + cflags + ['-I', str(stage), '-c', str(stage / 'explog.c'),
                                   '-o', str(stage / 'explog.o')], compile_log)
        if rc != 0:
            raise RuntimeError('%s: compile failed:\n%s' % (name, output_tail(compile_log)))
        link_log = stage / 'link.log'
        binary = stage / 'testExp2f'
        rc = command(cxx + ['-o', str(binary), test_object, str(stage / 'explog.o')] +
                     ldflags, link_log)
        if rc != 0:
            raise RuntimeError('%s: link failed:\n%s' % (name, output_tail(link_log)))
        test_log = stage / 'test.log'
        rc = command([str(binary), '--gtest_filter=' + test_filter, '--gtest_brief=1'],
                     test_log, run_env)
        if rc not in (0, 1):
            raise RuntimeError('%s: test crashed or exited unexpectedly (%d):\n%s' %
                               (name, rc, output_tail(test_log)))
        if replacement is None and rc != 0:
            raise RuntimeError('%s: unmodified control failed:\n%s' %
                               (name, output_tail(test_log)))
        if replacement is not None and rc != 1:
            raise RuntimeError('%s: defect escaped the tests' % name)
        if diagnostic is not None and diagnostic not in test_log.read_text():
            raise RuntimeError('%s lacks its specific assertion %r:\n%s' %
                               (name, diagnostic, output_tail(test_log)))
        print('  ok   %s %s' % (name, 'passes' if replacement is None else 'detected'), flush=True)
        return binary

    control_binary = build_run('control')
    for name, old, new in PLANTS:
        diagnostic = 'ulp from exact' if name == 'final-float-ulp' else None
        test_filter = 'Exp2f.CorpusIsWithinOneUlp' if name == 'final-float-ulp' else 'Exp2f.*'
        if name in ('subnormal-underflow-suppressed', 'normal-inexact-suppressed'):
            diagnostic, test_filter = 'grid n=', 'Exp2f.ReductionGridFlagsAndMonotonicity'
        build_run(name, (old, new), diagnostic, test_filter)
    for name, statement, diagnostic in STATE_PLANTS:
        signature = 'float gmath_exp2f(float x) {'
        build_run(name, (signature, signature + '\n  ' + statement), diagnostic,
                  'Exp2f.ExactPowersAndRawSpecialState')

    # Damage exactly one field in otherwise valid committed corpus metadata/data.
    lines = Path('tests/corpus/exp2f.corpus').read_text().splitlines()
    rows = [i for i, line in enumerate(lines) if line and not line.startswith('#')]
    if len(rows) <= 1001:
        raise RuntimeError('loader plants need more than 1001 committed rows')
    def header(prefix):
        found = [i for i, line in enumerate(lines) if line.startswith(prefix)]
        if len(found) != 1:
            raise RuntimeError('expected one %r corpus header' % prefix)
        return found[0]
    provenance, function = header('# Pinned oracle:'), header('# function')
    metadata, format_index = header('# seed'), header('# binary32')
    def replace(index, value):
        copy = list(lines)
        copy[index] = value
        return copy
    def remove(index):
        return [line for i, line in enumerate(lines) if i != index]
    def duplicate(index):
        copy = list(lines)
        copy.insert(index, lines[index])
        return copy
    loader_plants = []
    for label, index, diagnostic in (
            ('provenance', provenance, 'duplicate exp2f provenance'),
            ('function', function, 'duplicate exp2f function header'),
            ('sample', metadata, 'duplicate exp2f sample metadata'),
            ('format', format_index, 'duplicate exp2f format header')):
        loader_plants.append(('missing-' + label, remove(index), '1000',
                              'missing required exp2f corpus metadata'))
        loader_plants.append(('duplicate-' + label, duplicate(index), '1000', diagnostic))
    for package, version in (('MPFR', '4.2.2'), ('gmpy2', '2.3.2'), ('mpmath', '1.4.1')):
        token = package + ' ' + version
        if lines[provenance].count(token) != 1:
            raise RuntimeError('expected pinned version ' + token)
        loader_plants.append(('wrong-version-' + package.lower(),
            replace(provenance, lines[provenance].replace(token, package + ' 0.0.0')), '1000',
            'invalid exp2f pinned provenance'))
    loader_plants.extend((
        ('invalid-function', replace(function, '# function exp2'), '1000', 'invalid exp2f function header'),
        ('invalid-format', replace(format_index, '# binary32 wrong'), '1000', 'invalid exp2f binary32 format header'),
        ('invalid-minimum', lines, 'garbage', 'GMATH_EXP2F_MIN_ENTRIES must be a complete positive decimal integer'),
        ('truncated', remove(rows[-1]), '1000', 'exp2f corpus count disagrees with header'),
        ('duplicate-input', replace(rows[-1], lines[rows[0]]), '1000', 'duplicate exp2f input word'),
    ))
    for field, value in (('entries', 'garbage'), ('fresh', 'garbage'), ('seed', 'garbage'), ('count', '-1')):
        tokens = lines[metadata].split()
        tokens[tokens.index(field) + 1] = value
        loader_plants.append(('invalid-sample-' + field, replace(metadata, ' '.join(tokens)),
                              '1000', 'invalid exp2f sample metadata'))
    fields = lines[rows[-1]].split()
    malformed = {'incomplete': fields[:-1], 'extra': fields + ['0']}
    for label, index, value in (('overflow-input', 0, '10000000000000000'),
                              ('non-binary32-input', 0, '3ff0000000000001'),
                              ('overflow-error', 2, '100000000'),
                              ('nan-error', 2, '7fc00000')):
        damaged = list(fields)
        damaged[index] = value
        malformed[label] = damaged
    for label, fields in malformed.items():
        loader_plants.append((label, replace(rows[-1], ' '.join(fields)), '1000',
                              'bad exp2f corpus row or binary32 representation'))
    integer_rows = [i for i in rows if lines[i].split()[0] == '3ff0000000000000']
    if len(integer_rows) != 1:
        raise RuntimeError('integer reference fixture needs unique x=1 row')
    for label, column, value in (('integer-wrong-result', 1, '4000000020000000'),
                                  ('integer-nonzero-error', 2, '3e800000')):
        damaged = lines[integer_rows[0]].split()
        damaged[column] = value
        loader_plants.append((label, replace(integer_rows[0], ' '.join(damaged)), '1000',
                              'bad exp2f corpus row or binary32 representation'))
    for name, corpus, minimum, diagnostic in loader_plants:
        stage = work / ('corpus-' + name)
        stage.mkdir(parents=True, exist_ok=True)
        (stage / 'exp2f.corpus').write_text('\n'.join(corpus) + '\n')
        log = stage / 'test.log'
        test_env = dict(run_env, GMATH_EXP2F_CORPUS_DIR=str(stage), GMATH_EXP2F_MIN_ENTRIES=minimum)
        rc = command([str(control_binary), '--gtest_filter=Exp2f.CorpusIsWithinOneUlp',
                      '--gtest_brief=1'], log, test_env)
        if rc != 1 or diagnostic not in output_tail(log):
            raise RuntimeError('corpus %s failed without its specific assertion (exit %d):\n%s' %
                               (name, rc, output_tail(log)))
        print('  ok   corpus-%s detected' % name, flush=True)

    # A complete-payload pin must catch even parse-valid reference corruption.
    reference_stage = work / 'reference-payload'
    reference_stage.mkdir(parents=True, exist_ok=True)
    log = reference_stage / 'control.log'
    rc = command([sys.executable, 'tools/check-exp2f-reference.py'], log)
    if rc != 0 or 'complete committed payload SHA256 verified' not in output_tail(log):
        raise RuntimeError('reference checksum control failed:\n' + output_tail(log))
    half_rows = [i for i in rows if lines[i].split()[0] == '3fe0000000000000']
    if len(half_rows) != 1:
        raise RuntimeError('reference corruption needs unique noninteger x=0.5')
    for label, column in (('result', 1), ('error', 2)):
        fields = lines[half_rows[0]].split()
        if column == 1:
            fields[column] = '%016x' % (int(fields[column], 16) + (1 << 29))
        else:
            fields[column] = '%08x' % (int(fields[column], 16) ^ 0x80000000)
        stage = reference_stage / label
        stage.mkdir(parents=True, exist_ok=True)
        target = stage / 'exp2f.corpus'
        target.write_text('\n'.join(replace(half_rows[0], ' '.join(fields))) + '\n')
        log = stage / 'parse.log'
        rc = command([str(control_binary), '--gtest_filter=Exp2f.CorpusIsWithinOneUlp',
                      '--gtest_brief=1'], log,
                     dict(run_env, GMATH_EXP2F_CORPUS_DIR=str(stage), GMATH_EXP2F_MIN_ENTRIES='1000'))
        # Numerical rejection is allowed here; the full parsed population must
        # still be reported, so this proves checksum coverage beyond syntax.
        if rc not in (0, 1) or ('exp2f: %d corpus entries' % len(rows)) not in log.read_text():
            raise RuntimeError('reference %s mutation did not remain parse-valid:\n%s' %
                               (label, output_tail(log)))
        log = stage / 'checksum.log'
        rc = command([sys.executable, 'tools/check-exp2f-reference.py', str(target)], log)
        if rc != 1 or 'committed payload checksum differs' not in output_tail(log):
            raise RuntimeError('reference %s corruption escaped checksum:\n%s' %
                               (label, output_tail(log)))
        print('  ok   reference-%s parse-valid corruption detected' % label, flush=True)

    # Demonstrate the raw probe's exact-output cmp gate with a positive control.
    raw_stage = work / 'raw-hash'
    raw_stage.mkdir(parents=True, exist_ok=True)
    raw_probe = raw_stage / 'probe-exp2f-special'
    log = raw_stage / 'build.log'
    rc = command(cc + cflags + ['tools/probe-exp2f-special.c', str(work / 'control' / 'explog.o'),
                               '-o', str(raw_probe)] + ldflags, log)
    if rc != 0: raise RuntimeError('raw probe build failed:\n' + output_tail(log))
    actual = raw_stage / 'actual'
    rc = command([str(raw_probe)], actual, run_env)
    if rc != 0: raise RuntimeError('raw probe control failed:\n' + output_tail(actual))
    log = raw_stage / 'control.log'
    rc = command(['cmp', 'tests/corpus/exp2f-special.hash', str(actual)], log)
    if rc != 0: raise RuntimeError('raw hash control failed:\n' + output_tail(log))
    expected = Path('tests/corpus/exp2f-special.hash').read_text().splitlines()
    matches = [i for i, line in enumerate(expected) if line.startswith('math.exp2f_special.hash ')]
    if len(matches) != 1: raise RuntimeError('raw hash pin needs unique hash line')
    words = expected[matches[0]].split()
    words[1] = '%016x' % (int(words[1], 16) ^ 1)
    expected[matches[0]] = ' '.join(words)
    corrupt = raw_stage / 'corrupt.hash'
    corrupt.write_text('\n'.join(expected) + '\n')
    log = raw_stage / 'corruption.log'
    rc = command(['cmp', str(corrupt), str(actual)], log)
    if rc != 1 or 'differ' not in output_tail(log):
        raise RuntimeError('raw hash corruption escaped cmp gate:\n' + output_tail(log))
    print('  ok   raw hash control passes and corruption detected', flush=True)

    # Run fixed oracle answers in the pinned image; test rounding and error signs.
    import importlib.util
    spec = importlib.util.spec_from_file_location('exp2f_oracle', 'tools/oracle/oracle.py')
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    try:
        ref, _ = oracle.check_pin()
    except oracle.Unavailable as error:
        if oracle.REQUIRED:
            raise RuntimeError('pinned generator self-check required: %s' % error) from error
        print('  SKIPPED pinned generator mutations and fresh control: %s; committed corpus and implementation plants still checked' % error,
              flush=True)
        ref = None
    if ref is not None:
        generator = Path('tools/oracle/gen_corpus_exp2f.py').read_text()
        common = Path('tools/oracle/gen_corpus_floattrig.py').read_text()
        oracle_plants = (
            ('oracle-rounding', 'common', 'q & 1', 'q & 0',
             'RuntimeError: exp2f oracle self-check failed:'),
            ('oracle-rational-error', 'generator',
             'error = (exact - fraction(result)) / power(ulp_exp(exact))',
             'error = (fraction(result) - exact) / power(ulp_exp(exact))',
             'RuntimeError: exp2f oracle self-check failed:'),
            ('oracle-transcendental-error', 'generator', '(v - fraction(result)) / unit',
             '(fraction(result) - v) / unit', 'RuntimeError: exp2f oracle self-check failed:'),
            ('oracle-wrong-mpfr-value', 'generator',
             'bounds.append(rational(gmpy2.exp2(gmpy2.mpfr(x))))',
             'bounds.append(rational(gmpy2.exp2(gmpy2.mpfr(x) + 1)))',
             'RuntimeError: MPFR/mpmath value disagreement:'),
        )
        for name, target, old, new, diagnostic in oracle_plants:
            text = common if target == 'common' else generator
            if text.count(old) != 1:
                raise RuntimeError('%s oracle mutation must match once' % name)
        cases = [('oracle-control', None, None)] + [
            (name, (target, old, new), diagnostic) for name, target, old, new, diagnostic in oracle_plants]
        for name, replacement, diagnostic in cases:
            stage = work / name
            stage.mkdir(parents=True, exist_ok=True)
            text, shared = generator, common
            if replacement is not None:
                target, old, new = replacement
                if target == 'common': shared = shared.replace(old, new, 1)
                else: text = text.replace(old, new, 1)
            script = stage / 'generator.py'
            script.write_text(text)
            (stage / 'gen_corpus_floattrig.py').write_text(shared)
            log = stage / 'test.log'
            run = "import sys,runpy; sys.path.insert(0,%r); runpy.run_path(%r)['self_check']()" % (str(stage.resolve()), str(script))
            argv = [oracle.ENGINE, 'run', '--rm', '--userns=keep-id',
                    '-v', '%s:%s:z' % (oracle.ROOT, oracle.ROOT), '-w', oracle.ROOT,
                    ref, 'python', '-c', run]
            rc = command(argv, log)
            if replacement is None:
                if rc != 0: raise RuntimeError('oracle control failed:\n' + output_tail(log))
            elif rc != 1 or diagnostic not in output_tail(log):
                raise RuntimeError('%s was not specifically rejected:\n%s' % (name, output_tail(log)))
            print('  ok   %s %s' % (name, 'passes' if replacement is None else 'detected'), flush=True)
        fresh = work / 'fresh-corpus'
        fresh.mkdir(parents=True, exist_ok=True)
        seed = env.get('GMATH_ORACLE_SEED', str(time.time_ns() & 0xffffffff))
        print('  fresh exp2f seed %s' % seed, flush=True)
        log = fresh / 'generate.log'
        argv = [oracle.ENGINE, 'run', '--rm', '--userns=keep-id',
                '-v', '%s:%s:z' % (oracle.ROOT, oracle.ROOT), '-w', oracle.ROOT,
                ref, 'python', 'tools/oracle/gen_corpus_exp2f.py', '--fresh', '--out', str(fresh),
                '--seed', seed, '--count', '3000']
        rc = command(argv, log)
        if rc != 0: raise RuntimeError('fresh oracle generation failed (seed %s):\n%s' % (seed, output_tail(log)))
        log = fresh / 'control.log'
        fresh_env = dict(run_env, GMATH_EXP2F_CORPUS_DIR=str(fresh), GMATH_EXP2F_MIN_ENTRIES='1000')
        rc = command([str(control_binary), '--gtest_filter=Exp2f.*', '--gtest_brief=1'], log, fresh_env)
        if rc != 0: raise RuntimeError('fresh control failed (seed %s):\n%s' % (seed, output_tail(log)))
        print('  ok   fresh control passes', flush=True)

    # Supplemental hash entries must be enforced, separately for each format.
    hash_source = Path('tests/corpus/trig.hash')
    hash_text = hash_source.read_text()
    hash_stage = work / 'hash-gate'
    hash_stage.mkdir(parents=True, exist_ok=True)
    for name in ('control', 'exp2f'):
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
    for name in ('exp2f',):
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
    oracle_status = '4 oracle plants detected; fresh control passed' if ref is not None else '4 oracle plants and fresh control SKIPPED (no pinned image)'
    print('check-planted-exp2f: all %d implementation plants, %d corpus-loader plants, 2 parse-valid reference corruptions, 1 raw hash corruption, 1 supplemental hash corruption and 1 omitted probe entry detected; %s; controls pass' %
          (len(PLANTS) + len(STATE_PLANTS), len(loader_plants), oracle_status))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as error:
        print('check-planted-exp2f: FAIL: %s' % error, file=sys.stderr)
        sys.exit(1)
