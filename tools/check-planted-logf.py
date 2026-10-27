#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Require logf tests and supplemental hash checks to reject planted defects.

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
PLANTS = [('quiet-mask', '(lf_abs & 0x00400000u) == 0', '(lf_abs & 0x00200000u) == 0'),
 ('canonical-nan',
  '    return logf_value(0x7fc00000u);\n  }\n  if (lf_abs == 0)',
  '    return logf_value(0x7fc00001u);\n  }\n  if (lf_abs == 0)'),
 ('signaling-invalid',
  'if ((lf_abs & 0x00400000u) == 0) {\n      (void)gmath_invalid();',
  'if ((lf_abs & 0x00400000u) == 0) {\n      (void)0;'),
 ('nan-sign-priority',
  'if (lf_abs > 0x7f800000u) {',
  'if (lf_abs > 0x7f800000u && !(lf_word & 0x80000000u)) {'),
 ('zero-divide-flags',
  '(void)gmath_div_by_zero(GMATH_SIGN_BIT);\n    return logf_value(0xff800000u);',
  '(void)0;\n    return logf_value(0xff800000u);'),
 ('zero-result-sign', 'return logf_value(0xff800000u);', 'return logf_value(0x7f800000u);'),
 ('negative-domain',
  'if (lf_word & 0x80000000u) {\n    (void)gmath_invalid();',
  'if (lf_word & 0x80000000u) {\n    (void)0;'),
 ('positive-infinity',
  'if (lf_abs == 0x7f800000u) {\n    return x;',
  'if (lf_abs == 0x7f800000u) {\n    return 0.0f;'),
 ('one-zero-sign',
  'return 0.0f; /* Explicit +0 even with downward rounding. */',
  'return -0.0f; /* Wrong zero sign. */'),
 ('normalization-exponent',
  'int64_t lf_e = (int64_t)lf_tmp >> 52;',
  'int64_t lf_e = ((int64_t)lf_tmp >> 52) + 1;'),
 ('row-index',
  'const double * lf_row = gmath_log_rows[lf_j];',
  'const double * lf_row = gmath_log_rows[lf_j ^ 64u];'),
 ('normalization-scale',
  'gmath_double(lf_xb - ((uint64_t)lf_e << 52))',
  'gmath_double(lf_xb - ((uint64_t)lf_e << 51))'),
 ('front-sign', 'double lf_z = lf_m * lf_row[0] - 1.0;', 'double lf_z = 1.0 - lf_m * lf_row[0];'),
 ('quadratic-coefficient',
  'double lf_p = lf_z + (lf_z * lf_z) * (-0.5 + lf_z *',
  'double lf_p = lf_z + (lf_z * lf_z) * (-0.25 + lf_z *'),
 ('cubic-coefficient',
  '(0x1.5555555555555p-2 + lf_z * (-0.25 + lf_z * 0x1.999999999999ap-3))',
  '(0x1.5555555555555p-1 + lf_z * (-0.25 + lf_z * 0x1.999999999999ap-3))'),
 ('ln2-high',
  'double lf_a = lf_ed * GMATH_LN2_HI + lf_row[1];',
  'double lf_a = lf_ed * (2.0 * GMATH_LN2_HI) + lf_row[1];'),
 ('tail-sign', 'return lf_a + lf_tail;', 'return lf_a - lf_tail;'),
 ('final-float-ulp',
  'return (float)logf_positive((double)x);',
  'float lf_result = (float)logf_positive((double)x);\n'
  '  uint32_t lf_mutant;\n'
  '  memcpy(&lf_mutant, &lf_result, sizeof lf_mutant);\n'
  '  return logf_value(lf_mutant + 1u);'),
 ('normal-inexact-suppressed',
  'return (float)logf_positive((double)x);',
  'float lf_result = (float)logf_positive((double)x);\n'
  '  (void)feclearexcept(FE_INEXACT);\n'
  '  return lf_result;'),
 ('false-positive-underflow',
  'return (float)logf_positive((double)x);',
  'float lf_result = (float)logf_positive((double)x);\n'
  '  (void)feraiseexcept(FE_UNDERFLOW);\n'
  '  return lf_result;')]

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



def verify_corpus_selection(binary, run_env, directory, expected_count, stage,
                            test_filter='Logf.*'):
    """Check the selected population, then prove that its path is consulted."""
    stage.mkdir(parents=True, exist_ok=True)
    selected_env = dict(run_env, GMATH_LOGF_CORPUS_DIR=str(directory),
                        GMATH_LOGF_MIN_ENTRIES='1000')
    log = stage / 'loaded.log'
    argv = [str(binary), '--gtest_filter=' + test_filter, '--gtest_brief=1']
    rc = command(argv, log, selected_env)
    marker = 'logf: %d corpus entries,' % expected_count
    if rc != 0 or log.read_text().count(marker) != 1:
        raise RuntimeError('requested corpus population was not loaded (%s, expected %d):\n%s' %
                           (directory, expected_count, output_tail(log)))
    # Count alone cannot distinguish equal-size corpora. Temporarily hide the
    # selected file: a loader that falls back to committed data must fail here.
    corpus, hidden = directory / 'logf.corpus', directory / 'logf.corpus.guard-hidden'
    if hidden.exists():
        raise RuntimeError('corpus override guard already has a hidden file: ' + str(hidden))
    corpus.rename(hidden)
    try:
        log = stage / 'missing.log'
        rc = command([str(binary), '--gtest_filter=Logf.CorpusIsWithinOneUlp',
                      '--gtest_brief=1'], log, selected_env)
    finally:
        hidden.rename(corpus)
    if rc not in (0, 1):
        raise RuntimeError('corpus selection probe crashed or exited unexpectedly (%d):\n%s' %
                           (rc, output_tail(log)))
    diagnostic = 'missing logf corpus: ' + str(directory)
    if rc != 1 or diagnostic not in log.read_text():
        raise RuntimeError('requested corpus directory was ignored (%s):\n%s' %
                           (directory, output_tail(log)))


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

    def build_run(name, replacement=None, diagnostic=None, test_filter='Logf.*'):
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
        binary = stage / 'testLogf'
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
    # This guard runs even without the pinned image. Rebuild the actual test
    # loader with its former environment-variable typo and require rejection.
    override = work / 'corpus-override'
    override.mkdir(parents=True, exist_ok=True)
    shutil.copyfile('tests/corpus/logf.corpus', override / 'logf.corpus')
    committed_count = sum(bool(line) and not line.startswith('#') for line in
                          Path('tests/corpus/logf.corpus').read_text().splitlines())
    verify_corpus_selection(control_binary, run_env, override, committed_count,
                            override / 'control', 'Logf.CorpusIsWithinOneUlp')
    print('  ok   requested corpus directory and population control passes', flush=True)
    typo = override / 'typo'
    typo.mkdir(parents=True, exist_ok=True)
    loader = Path('tests/unit/test_logf.cpp').read_text()
    correct = 'std::getenv("GMATH_LOGF_CORPUS_DIR")'
    if loader.count(correct) != 1:
        raise RuntimeError('corpus override typo must match one loader lookup')
    (typo / 'test_logf.cpp').write_text(loader.replace(
        correct, 'std::getenv("GMATH_EXPF_CORPUS_DIR")', 1))
    includes, index = [], 0
    include_flags = cflags + ldflags
    while index < len(include_flags):
        flag = include_flags[index]
        if flag in ('-I', '-isystem', '-iquote'):
            includes.extend(include_flags[index:index + 2])
            index += 2
        else:
            if flag.startswith(('-I', '-isystem', '-iquote')):
                includes.append(flag)
            index += 1
    log = typo / 'compile.log'
    rc = command(cxx + includes + ['-Itests', '-c', str(typo / 'test_logf.cpp'),
                                  '-o', str(typo / 'test_logf.o')], log)
    if rc != 0: raise RuntimeError('loader typo compile failed:\n' + output_tail(log))
    binary = typo / 'testLogf'
    log = typo / 'link.log'
    rc = command(cxx + ['-o', str(binary), str(typo / 'test_logf.o'),
                       str(work / 'control' / 'explog.o')] + ldflags, log)
    if rc != 0: raise RuntimeError('loader typo link failed:\n' + output_tail(log))
    try:
        verify_corpus_selection(binary, run_env, override, committed_count,
                                typo / 'guard', 'Logf.CorpusIsWithinOneUlp')
    except RuntimeError as error:
        if 'requested corpus directory was ignored' not in str(error):
            raise
    else:
        raise RuntimeError('old corpus override typo escaped the selection guard')
    print('  ok   former corpus-directory typo rejected by selection guard', flush=True)
    for name, old, new in PLANTS:
        diagnostic = 'ulp from exact' if name == 'final-float-ulp' else None
        test_filter = 'Logf.CorpusIsWithinOneUlp' if name == 'final-float-ulp' else 'Logf.*'
        if name in ('normal-inexact-suppressed', 'false-positive-underflow'):
            diagnostic, test_filter = 'flags', 'Logf.CorpusIsWithinOneUlp'
        build_run(name, (old, new), diagnostic, test_filter)
    for name, statement, diagnostic in STATE_PLANTS:
        signature = 'float gmath_logf(float x) {'
        build_run(name, (signature, signature + '\n  ' + statement), diagnostic,
                  'Logf.ExactSpecialsAndState')

    # Damage exactly one field in otherwise valid committed corpus metadata/data.
    lines = Path('tests/corpus/logf.corpus').read_text().splitlines()
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
            ('provenance', provenance, 'duplicate logf provenance'),
            ('function', function, 'duplicate logf function header'),
            ('sample', metadata, 'duplicate logf sample metadata'),
            ('format', format_index, 'duplicate logf format header')):
        loader_plants.append(('missing-' + label, remove(index), '1000',
                              'missing required logf corpus metadata'))
        loader_plants.append(('duplicate-' + label, duplicate(index), '1000', diagnostic))
    for package, version in (('MPFR', '4.2.2'), ('gmpy2', '2.3.2'), ('mpmath', '1.4.1')):
        token = package + ' ' + version
        if lines[provenance].count(token) != 1:
            raise RuntimeError('expected pinned version ' + token)
        loader_plants.append(('wrong-version-' + package.lower(),
            replace(provenance, lines[provenance].replace(token, package + ' 0.0.0')), '1000',
            'invalid logf pinned provenance'))
    loader_plants.extend((
        ('invalid-function', replace(function, '# function exp2'), '1000', 'invalid logf function header'),
        ('invalid-format', replace(format_index, '# binary32 wrong'), '1000', 'invalid logf binary32 format header'),
        ('invalid-minimum', lines, 'garbage', 'GMATH_LOGF_MIN_ENTRIES must be a complete positive decimal integer'),
        ('truncated', remove(rows[-1]), '1000', 'logf corpus count disagrees with header'),
        ('duplicate-input', replace(rows[-1], lines[rows[0]]), '1000', 'duplicate logf input word'),
    ))
    for field, value in (('entries', 'garbage'), ('fresh', 'garbage'), ('seed', 'garbage'), ('count', '-1')):
        tokens = lines[metadata].split()
        tokens[tokens.index(field) + 1] = value
        loader_plants.append(('invalid-sample-' + field, replace(metadata, ' '.join(tokens)),
                              '1000', 'invalid logf sample metadata'))
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
                              'bad logf corpus row or binary32 representation'))
    zero_rows = [i for i in rows if lines[i].split()[0] == '3ff0000000000000']
    if len(zero_rows) != 1:
        raise RuntimeError('one reference fixture needs unique x=1 row')
    for label, column, value in (('one-wrong-result', 1, '3e70000000000000'),
                                  ('one-nonzero-error', 2, '3e800000')):
        damaged = lines[zero_rows[0]].split()
        damaged[column] = value
        loader_plants.append((label, replace(zero_rows[0], ' '.join(damaged)), '1000',
                              'bad logf corpus row or binary32 representation'))
    for name, corpus, minimum, diagnostic in loader_plants:
        stage = work / ('corpus-' + name)
        stage.mkdir(parents=True, exist_ok=True)
        (stage / 'logf.corpus').write_text('\n'.join(corpus) + '\n')
        log = stage / 'test.log'
        test_env = dict(run_env, GMATH_LOGF_CORPUS_DIR=str(stage), GMATH_LOGF_MIN_ENTRIES=minimum)
        rc = command([str(control_binary), '--gtest_filter=Logf.CorpusIsWithinOneUlp',
                      '--gtest_brief=1'], log, test_env)
        if rc != 1 or diagnostic not in output_tail(log):
            raise RuntimeError('corpus %s failed without its specific assertion (exit %d):\n%s' %
                               (name, rc, output_tail(log)))
        print('  ok   corpus-%s detected' % name, flush=True)

    # A complete-payload pin must catch even parse-valid reference corruption.
    reference_stage = work / 'reference-payload'
    reference_stage.mkdir(parents=True, exist_ok=True)
    log = reference_stage / 'control.log'
    rc = command([sys.executable, 'tools/check-logf-reference.py'], log)
    if rc != 0 or 'complete committed payload SHA256 verified' not in output_tail(log):
        raise RuntimeError('reference checksum control failed:\n' + output_tail(log))
    reference_rows = [i for i in rows if lines[i].split()[0] == '4000000000000000']
    if len(reference_rows) != 1:
        raise RuntimeError('reference corruption needs unique x=2')
    for label, column in (('result', 1), ('error', 2)):
        fields = lines[reference_rows[0]].split()
        if column == 1:
            fields[column] = '%016x' % (int(fields[column], 16) + (1 << 29))
        else:
            fields[column] = '%08x' % (int(fields[column], 16) ^ 0x80000000)
        stage = reference_stage / label
        stage.mkdir(parents=True, exist_ok=True)
        target = stage / 'logf.corpus'
        target.write_text('\n'.join(replace(reference_rows[0], ' '.join(fields))) + '\n')
        log = stage / 'parse.log'
        rc = command([str(control_binary), '--gtest_filter=Logf.CorpusIsWithinOneUlp',
                      '--gtest_brief=1'], log,
                     dict(run_env, GMATH_LOGF_CORPUS_DIR=str(stage), GMATH_LOGF_MIN_ENTRIES='1000'))
        # Numerical rejection is allowed here; the full parsed population must
        # still be reported, so this proves checksum coverage beyond syntax.
        if rc not in (0, 1) or ('logf: %d corpus entries' % len(rows)) not in log.read_text():
            raise RuntimeError('reference %s mutation did not remain parse-valid:\n%s' %
                               (label, output_tail(log)))
        log = stage / 'checksum.log'
        rc = command([sys.executable, 'tools/check-logf-reference.py', str(target)], log)
        if rc != 1 or 'committed payload checksum differs' not in output_tail(log):
            raise RuntimeError('reference %s corruption escaped checksum:\n%s' %
                               (label, output_tail(log)))
        print('  ok   reference-%s parse-valid corruption detected' % label, flush=True)

    # Demonstrate the raw probe's exact-output cmp gate with a positive control.
    raw_stage = work / 'raw-hash'
    raw_stage.mkdir(parents=True, exist_ok=True)
    raw_probe = raw_stage / 'probe-logf-special'
    log = raw_stage / 'build.log'
    rc = command(cc + cflags + ['tools/probe-logf-special.c', str(work / 'control' / 'explog.o'),
                               '-o', str(raw_probe)] + ldflags, log)
    if rc != 0: raise RuntimeError('raw probe build failed:\n' + output_tail(log))
    actual = raw_stage / 'actual'
    rc = command([str(raw_probe)], actual, run_env)
    if rc != 0: raise RuntimeError('raw probe control failed:\n' + output_tail(actual))
    log = raw_stage / 'control.log'
    rc = command(['cmp', 'tests/corpus/logf-special.hash', str(actual)], log)
    if rc != 0: raise RuntimeError('raw hash control failed:\n' + output_tail(log))
    expected = Path('tests/corpus/logf-special.hash').read_text().splitlines()
    matches = [i for i, line in enumerate(expected) if line.startswith('math.logf_special.hash ')]
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
    spec = importlib.util.spec_from_file_location('logf_oracle', 'tools/oracle/oracle.py')
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
        generator = Path('tools/oracle/gen_corpus_logf.py').read_text()
        common = Path('tools/oracle/gen_corpus_floattrig.py').read_text()
        oracle_plants = (
            ('oracle-rounding', 'common', 'q & 1', 'q & 0',
             'RuntimeError: logf oracle self-check failed:'),
            ('oracle-negative-domain', 'generator',
             'if raw & SIGN:\n        return QNAN, 0', 'if raw & SIGN:\n        return INF, 0',
             'RuntimeError: logf oracle self-check failed:'),
            ('oracle-transcendental-error', 'generator', '(v - fraction(result)) / unit',
             '(fraction(result) - v) / unit', 'RuntimeError: logf oracle self-check failed:'),
            ('oracle-wrong-mpfr-value', 'generator',
             'bounds.append(rational(gmpy2.log(gmpy2.mpfr(x))))',
             'bounds.append(rational(gmpy2.log(gmpy2.mpfr(x) + 1)))',
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
        print('  fresh logf seed %s' % seed, flush=True)
        log = fresh / 'generate.log'
        argv = [oracle.ENGINE, 'run', '--rm', '--userns=keep-id',
                '-v', '%s:%s:z' % (oracle.ROOT, oracle.ROOT), '-w', oracle.ROOT,
                ref, 'python', 'tools/oracle/gen_corpus_logf.py', '--fresh', '--out', str(fresh),
                '--seed', seed, '--count', '3000']
        rc = command(argv, log)
        if rc != 0: raise RuntimeError('fresh oracle generation failed (seed %s):\n%s' % (seed, output_tail(log)))
        fresh_lines = (fresh / 'logf.corpus').read_text().splitlines()
        metadata = [line.split() for line in fresh_lines if line.startswith('# seed ')]
        fresh_count = sum(bool(line) and not line.startswith('#') for line in fresh_lines)
        if (len(metadata) != 1 or metadata[0] !=
                ['#', 'seed', str(int(seed)), 'count', '3000', 'fresh', 'True', 'entries', str(fresh_count)]):
            raise RuntimeError('fresh corpus metadata/count disagrees with requested sample')
        verify_corpus_selection(control_binary, run_env, fresh, fresh_count, fresh / 'selection')
        print('  ok   fresh control loads requested directory and %d entries' % fresh_count, flush=True)

    # Supplemental hash entries must be enforced, separately for each format.
    hash_source = Path('tests/corpus/trig.hash')
    hash_text = hash_source.read_text()
    hash_stage = work / 'hash-gate'
    hash_stage.mkdir(parents=True, exist_ok=True)
    for name in ('control', 'logf'):
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
    for name in ('logf',):
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
    print('check-planted-logf: all %d implementation plants, %d corpus-loader plants, 2 parse-valid reference corruptions, 1 raw hash corruption, 1 supplemental hash corruption and 1 omitted probe entry and former corpus-directory typo detected; %s; controls pass' %
          (len(PLANTS) + len(STATE_PLANTS), len(loader_plants), oracle_status))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as error:
        print('check-planted-logf: FAIL: %s' % error, file=sys.stderr)
        sys.exit(1)
