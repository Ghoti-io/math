#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Require hypotf tests and supplemental hash checks to reject planted defects.

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
PLANTS = [('first-signaling-mask', '(hf_x & 0x00400000u) == 0', '(hf_x & 0x00200000u) == 0'),
 ('second-signaling-mask', '(hf_y & 0x00400000u) == 0', '(hf_y & 0x00200000u) == 0'),
 ('signaling-invalid',
  '(void)gmath_invalid();\n    return hf_value(0x7fc00000u);',
  '(void)0;\n    return hf_value(0x7fc00000u);'),
 ('canonical-nan',
  'if (hf_x > 0x7f800000u || hf_y > 0x7f800000u) return hf_value(0x7fc00000u);',
  'if (hf_x > 0x7f800000u || hf_y > 0x7f800000u) return hf_value(0x7fc00001u);'),
 ('infinity-dominance',
  'if (hf_x == 0x7f800000u || hf_y == 0x7f800000u) return hf_value(0x7f800000u);',
  'if ((hf_x == 0x7f800000u || hf_y == 0x7f800000u) && hf_x <= 0x7f800000u && hf_y <= 0x7f800000u) '
  'return hf_value(0x7f800000u);'),
 ('lost-absolute-sign', 'hf_x &= 0x7fffffffu;', 'hf_x &= 0xffffffffu;'),
 ('zero-result-sign',
  'if (hf_b == 0) return hf_value(hf_a);',
  'if (hf_b == 0) return hf_value(hf_a | 0x80000000u);'),
 ('sort-smaller',
  'uint32_t hf_b = hf_x > hf_y ? hf_y : hf_x;',
  'uint32_t hf_b = hf_x > hf_y ? hf_x : hf_y;'),
 ('gap-threshold', 'if (hf_gap >= 13u)', 'if (hf_gap >= 1u)'),
 ('gap-inexact',
  'else hf_inexact();\n    return hf_value(hf_a);',
  'else (void)0;\n    return hf_value(hf_a);'),
 ('subnormal-normalization',
  '*hf_exponent = -149 - (int)hf_shift_bits;',
  '*hf_exponent = -148 - (int)hf_shift_bits;'),
 ('square-alignment', 'hf_shift(hf_aa, 2u * hf_gap)', 'hf_shift(hf_aa, hf_gap)'),
 ('sum-carry',
  'hf_s.high += (uint32_t)(hf_s.low < hf_before);',
  'hf_s.high += (uint32_t)(hf_s.low < hf_before) & 0u;'),
 ('high-word-extraction',
  '((uint64_t)hf_value.high << (64u - hf_shift_bits))',
  '((uint64_t)hf_value.high << (63u - hf_shift_bits))'),
 ('subnormal-grid',
  'int hf_subnormal_grid = -149 - hf_kb;',
  'int hf_subnormal_grid = -148 - hf_kb;'),
 ('root-target', 'hf_isqrt48(hf_targ);', 'hf_isqrt48(hf_targ >> 1);'),
 ('midpoint-direction', 'if (hf_upper > hf_mid ||', 'if (hf_upper < hf_mid ||'),
 ('midpoint-tie', '(hf_sticky || (hf_q & 1u))', '(hf_sticky || ((hf_q & 1u) ^ 1u))'),
 ('packed-exponent', '(uint32_t)(hf_e + 127) << 23', '(uint32_t)(hf_e + 126) << 23'),
 ('overflow-flags',
  '(void)gmath_overflow(0);\n    return hf_value(0x7f800000u);',
  'hf_inexact();\n    return hf_value(0x7f800000u);'),
 ('false-exactness',
  'unsigned hf_exact = hf_square.low == hf_s.low && hf_square.high == hf_s.high;',
  'unsigned hf_exact = (hf_square.low == hf_s.low && hf_square.high == hf_s.high) || 1u;'),
 ('exact-results-inexact', 'if (!hf_exact) {', 'if (!hf_exact || 1u) {'),
 ('tininess-before-round',
  'if (!hf_exact) {\n    if (hf_result < 0x00800000u)',
  'if (!hf_exact) {\n    if (hf_a < 0x00800000u)'),
 ('underflow-flags',
  'if (hf_result < 0x00800000u) (void)gmath_underflow(0);',
  'if (hf_result < 0x00800000u) hf_inexact();'),
 ('forced-inexact',
  'volatile double hf_ignored = hf_big + 1.0;',
  'volatile double hf_ignored = hf_big + 0.0;')]
HW_PLANTS = [('fast-midpoint-gate',
  'if (hf_distance <= 32u) return 0;',
  'if (hf_distance <= 32u && 0u) return 0;'),
 ('fast-square-weight',
  'double hf_sum = hf_da * hf_da + hf_db * hf_db;',
  'double hf_sum = hf_da * hf_da + 2.0 * hf_db * hf_db;'),
 ('fast-root-scale',
  'double hf_root = gmath_sqrt_instruction(hf_sum);',
  'double hf_root = 0.5 * gmath_sqrt_instruction(hf_sum);'),
 ('fast-normal-inexact',
  'volatile float hf_ignored = (float)hf_root;',
  'volatile float hf_ignored = 0.0f;'),
 ('fast-underflow-classifier',
  'if ((uint64_t)hf_result * hf_result != hf_exact_sum)',
  'if ((uint64_t)hf_result * hf_result == hf_exact_sum)'),
 ('fast-tininess-boundary',
  'hf_bits >= gmath_bits(0x1p-126) && hf_bits <= gmath_bits(0x1.fffffep127)',
  'hf_bits <= gmath_bits(0x1.fffffep127)'),
 ('fast-overflow-flags',
  'if (hf_e >= 128) {\n    (void)gmath_overflow(0);\n    *hf_output',
  'if (hf_e >= 128) {\n    (void)0;\n    *hf_output'),
 ('fast-packed-exponent',
  '((uint32_t)(hf_e + 126) << 23) + hf_q',
  '((uint32_t)(hf_e + 125) << 23) + hf_q'),
 ('fast-output-sign', '*hf_output = hf_result;', '*hf_output = hf_result | 0x80000000u;'),
 ('fast-rounded-overflow-flags',
  'if (hf_result >= 0x7f800000u) {\n    (void)gmath_overflow(0);',
  'if (hf_result >= 0x7f800000u) {\n    (void)0;'),
 ('fast-boundary-inexact-deleted',
  '    hf_inexact();\n  }\n  *hf_output = hf_result;',
  '    (void)0;\n  }\n  *hf_output = hf_result;')]

PORTABLE_PLANTS = [('portable-trial',
  'uint64_t hf_trial = (hf_root << 2) | 1u;',
  'uint64_t hf_trial = (hf_root << 3) | 1u;'),
 ('portable-input-digits', '((hf_t >> (2 * hf_digit)) & 3u)', '(((hf_t >> (2 * hf_digit)) & 3u) | 1u)'),
 ('portable-root-bit', 'hf_root <<= 1;', 'hf_root = (hf_root << 1) | 1u;')]

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
                            test_filter='Hypotf.*'):
    """Check the selected population, then prove that its path is consulted."""
    stage.mkdir(parents=True, exist_ok=True)
    selected_env = dict(run_env, GMATH_HYPOTF_CORPUS_DIR=str(directory),
                        GMATH_HYPOTF_MIN_ENTRIES='1000')
    log = stage / 'loaded.log'
    argv = [str(binary), '--gtest_filter=' + test_filter, '--gtest_brief=1']
    rc = command(argv, log, selected_env)
    marker = 'hypotf: %d corpus entries,' % expected_count
    if rc != 0 or log.read_text().count(marker) != 1:
        raise RuntimeError('requested corpus population was not loaded (%s, expected %d):\n%s' %
                           (directory, expected_count, output_tail(log)))
    # Count alone cannot distinguish equal-size corpora. Temporarily hide the
    # selected file: a loader that falls back to committed data must fail here.
    corpus, hidden = directory / 'hypotf.corpus', directory / 'hypotf.corpus.guard-hidden'
    if hidden.exists():
        raise RuntimeError('corpus override guard already has a hidden file: ' + str(hidden))
    corpus.rename(hidden)
    try:
        log = stage / 'missing.log'
        rc = command([str(binary), '--gtest_filter=Hypotf.CorpusIsCorrectlyRoundedInEveryMode',
                      '--gtest_brief=1'], log, selected_env)
    finally:
        hidden.rename(corpus)
    if rc not in (0, 1):
        raise RuntimeError('corpus selection probe crashed or exited unexpectedly (%d):\n%s' %
                           (rc, output_tail(log)))
    diagnostic = 'missing hypotf corpus: ' + str(directory)
    if rc != 1 or diagnostic not in log.read_text():
        raise RuntimeError('requested corpus directory was ignored (%s):\n%s' %
                           (directory, output_tail(log)))


def verify_fresh_corpus(binary, directory, seed, count, stage, run_env=None):
    """Require the requested fresh metadata, row count, and selected test path."""
    try:
        seed, count = int(seed), int(count)
    except (TypeError, ValueError) as error:
        raise RuntimeError('fresh requested seed/count must be decimal integers') from error
    if count < 0:
        raise RuntimeError('fresh requested count must be nonnegative')
    directory = Path(directory)
    try:
        lines = (directory / 'hypotf.corpus').read_text().splitlines()
    except OSError as error:
        raise RuntimeError('cannot read requested fresh corpus: %s' % error) from error
    metadata = [line.split() for line in lines if line.startswith('# seed ')]
    population = sum(bool(line) and not line.startswith('#') for line in lines)
    expected = ['#', 'seed', str(seed), 'count', str(count), 'fresh', 'True',
                'entries', str(population)]
    if len(metadata) != 1 or metadata[0] != expected:
        raise RuntimeError('fresh corpus metadata/count disagrees with requested sample')
    verify_corpus_selection(Path(binary), os.environ if run_env is None else run_env,
                            directory, population, Path(stage))
    return population


def main():
    env = os.environ
    if len(sys.argv) > 1:
        if len(sys.argv) != 7 or sys.argv[1] != '--verify-fresh':
            print('usage: check-planted-hypotf.py --verify-fresh BINARY DIRECTORY SEED COUNT STAGE',
                  file=sys.stderr)
            return 2
        population = verify_fresh_corpus(sys.argv[2], sys.argv[3], sys.argv[4],
                                         sys.argv[5], sys.argv[6])
        print('fresh hypotf requested metadata, directory and %d entries verified' % population)
        return 0
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
    original = (SOURCE / 'hypot.c').read_text()
    run_env = dict(env, LD_LIBRARY_PATH=ld_path)

    def build_run(name, replacement=None, diagnostic=None, test_filter='Hypotf.*', portable=False):
        stage = work / name
        stage.mkdir(parents=True, exist_ok=True)
        text = original
        if replacement is not None:
            old, new = replacement
            if old == new or text.count(old) != 1:
                raise RuntimeError('%s: replacement must match once (found %d)' %
                                   (name, text.count(old)))
            text = text.replace(old, new, 1)
        (stage / 'hypot.c').write_text('#include <errno.h>\n#include <fenv.h>\n' + text)
        for header in ('elem_common.h', 'hypot_table.h', 'sqrt_impl.h'):
            shutil.copyfile(SOURCE / header, stage / header)
        compile_log = stage / 'compile.log'
        rc = command(cc + cflags + (['-DGMATH_SQRT_PORTABLE'] if portable else []) + ['-I', str(stage), '-c', str(stage / 'hypot.c'),
                                   '-o', str(stage / 'hypot.o')], compile_log)
        if rc != 0:
            raise RuntimeError('%s: compile failed:\n%s' % (name, output_tail(compile_log)))
        link_log = stage / 'link.log'
        binary = stage / 'testHypotf'
        rc = command(cxx + ['-o', str(binary), test_object, str(stage / 'hypot.o')] +
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
    shutil.copyfile('tests/corpus/hypotf.corpus', override / 'hypotf.corpus')
    committed_count = sum(bool(line) and not line.startswith('#') for line in
                          Path('tests/corpus/hypotf.corpus').read_text().splitlines())
    verify_corpus_selection(control_binary, run_env, override, committed_count,
                            override / 'control', 'Hypotf.CorpusIsCorrectlyRoundedInEveryMode')
    print('  ok   requested corpus directory and population control passes', flush=True)
    typo = override / 'typo'
    typo.mkdir(parents=True, exist_ok=True)
    loader = Path('tests/unit/test_hypotf.cpp').read_text()
    correct = 'std::getenv("GMATH_HYPOTF_CORPUS_DIR")'
    if loader.count(correct) != 1:
        raise RuntimeError('corpus override typo must match one loader lookup')
    (typo / 'test_hypotf.cpp').write_text(loader.replace(
        correct, 'std::getenv("GMATH_LOG10F_CORPUS_DIR")', 1))
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
    rc = command(cxx + includes + ['-Itests', '-c', str(typo / 'test_hypotf.cpp'),
                                  '-o', str(typo / 'test_hypotf.o')], log)
    if rc != 0: raise RuntimeError('loader typo compile failed:\n' + output_tail(log))
    binary = typo / 'testHypotf'
    log = typo / 'link.log'
    rc = command(cxx + ['-o', str(binary), str(typo / 'test_hypotf.o'),
                       str(work / 'control' / 'hypot.o')] + ldflags, log)
    if rc != 0: raise RuntimeError('loader typo link failed:\n' + output_tail(log))
    try:
        verify_corpus_selection(binary, run_env, override, committed_count,
                                typo / 'guard', 'Hypotf.CorpusIsCorrectlyRoundedInEveryMode')
    except RuntimeError as error:
        if 'requested corpus directory was ignored' not in str(error):
            raise
    else:
        raise RuntimeError('old corpus override typo escaped the selection guard')
    print('  ok   former corpus-directory typo rejected by selection guard', flush=True)
    build_run('portable-control', portable=True)
    macros = work / 'control' / 'macros.log'
    rc = command(cc + cflags + ['-dM', '-E', 'src/elementary/hypot.c'], macros)
    if rc != 0: raise RuntimeError('hardware-path macro probe failed:\n' + output_tail(macros))
    hardware = any(line.split()[:2] == ['#define', 'GMATH_HW_SQRT']
                   for line in macros.read_text().splitlines())
    integer_only = {'square-alignment', 'sum-carry', 'high-word-extraction',
                    'subnormal-grid', 'root-target', 'midpoint-direction', 'midpoint-tie',
                    'packed-exponent', 'overflow-flags', 'false-exactness',
                    'exact-results-inexact', 'tininess-before-round', 'underflow-flags'}
    for name, old, new in PLANTS:
        build_run(name, (old, new), portable=name in integer_only)
    for name, old, new in PORTABLE_PLANTS:
        build_run(name, (old, new), portable=True)
    if hardware:
        for name, old, new in HW_PLANTS:
            if name == 'fast-boundary-inexact-deleted':
                build_run(name, (old, new), 'flags', 'Hypotf.ExactTriplesTinyCarryAndOverflowTie')
            else:
                build_run(name, (old, new))
    else:
        print('  SKIPPED %d hardware admission plants (no GMATH_HW_SQRT)' % len(HW_PLANTS), flush=True)
    for name, statement, diagnostic in STATE_PLANTS:
        signature = 'float gmath_hypotf(float x, float y) {'
        build_run(name, (signature, signature + '\n  ' + statement), diagnostic,
                  'Hypotf.ExactSpecialsAndState')

    # Damage exactly one field in otherwise valid committed corpus metadata/data.
    lines = Path('tests/corpus/hypotf.corpus').read_text().splitlines()
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
            ('provenance', provenance, 'duplicate hypotf provenance'),
            ('function', function, 'duplicate hypotf function header'),
            ('sample', metadata, 'duplicate hypotf sample metadata'),
            ('format', format_index, 'duplicate hypotf format header')):
        loader_plants.append(('missing-' + label, remove(index), '1000',
                              'missing required hypotf corpus metadata'))
        loader_plants.append(('duplicate-' + label, duplicate(index), '1000', diagnostic))
    for package, version in (('MPFR', '4.2.2'), ('gmpy2', '2.3.2'), ('mpmath', '1.4.1')):
        token = package + ' ' + version
        if lines[provenance].count(token) != 1:
            raise RuntimeError('expected pinned version ' + token)
        loader_plants.append(('wrong-version-' + package.lower(),
            replace(provenance, lines[provenance].replace(token, package + ' 0.0.0')), '1000',
            'invalid hypotf pinned provenance'))
    loader_plants.extend((
        ('invalid-function', replace(function, '# function exp2'), '1000', 'invalid hypotf function header'),
        ('invalid-format', replace(format_index, '# binary32 wrong'), '1000', 'invalid hypotf binary32 format header'),
        ('invalid-minimum', lines, 'garbage', 'GMATH_HYPOTF_MIN_ENTRIES must be a complete positive decimal integer'),
        ('truncated', remove(rows[-1]), '1000', 'hypotf corpus count disagrees with header'),
        ('duplicate-input', replace(rows[-1], lines[rows[0]]), '1000', 'duplicate hypotf input word'),
    ))
    for field, value in (('entries', 'garbage'), ('fresh', 'garbage'), ('seed', 'garbage'), ('count', '-1')):
        tokens = lines[metadata].split()
        tokens[tokens.index(field) + 1] = value
        loader_plants.append(('invalid-sample-' + field, replace(metadata, ' '.join(tokens)),
                              '1000', 'invalid hypotf sample metadata'))
    fields = lines[rows[-1]].split()
    malformed = {'incomplete': fields[:-1], 'extra': fields + ['0']}
    for label, index, value in (('overflow-input', 0, '10000000000000000'),
                              ('non-binary32-input', 0, '3ff0000000000001'),
                              ('overflow-second-input', 1, '10000000000000000'),
                              ('non-binary32-second-input', 1, '3ff0000000000001'),
                              ('non-binary32-result', 2, '3ff0000000000001'),
                              ('overflow-error', 3, '100000000'),
                              ('nan-error', 3, '7fc00000')):
        damaged = list(fields)
        damaged[index] = value
        malformed[label] = damaged
    for label, fields in malformed.items():
        loader_plants.append((label, replace(rows[-1], ' '.join(fields)), '1000',
                              'bad hypotf corpus row or binary32 representation'))
    for xword, yword, label, wrong_result in (
            ('0000000000000000', '0000000000000000', 'zero-pair', '3ff0000000000000'),
            ('36b8000000000000', '36c0000000000000', 'subnormal-triple', '36c8000000000000'),
            ('4008000000000000', '4010000000000000', 'normal-triple', '4018000000000000')):
        exact_rows = [i for i in rows if lines[i].split()[:2] == [xword, yword]]
        if len(exact_rows) != 1:
            raise RuntimeError('exact-root fixture needs unique ' + label + ' row')
        for field, column, value in (('wrong-result', 2, wrong_result),
                                     ('nonzero-error', 3, '3e800000')):
            damaged = lines[exact_rows[0]].split()
            damaged[column] = value
            loader_plants.append((label + '-' + field,
                                  replace(exact_rows[0], ' '.join(damaged)), '1000',
                                  'bad hypotf corpus row or binary32 representation'))
    for name, corpus, minimum, diagnostic in loader_plants:
        stage = work / ('corpus-' + name)
        stage.mkdir(parents=True, exist_ok=True)
        (stage / 'hypotf.corpus').write_text('\n'.join(corpus) + '\n')
        log = stage / 'test.log'
        test_env = dict(run_env, GMATH_HYPOTF_CORPUS_DIR=str(stage), GMATH_HYPOTF_MIN_ENTRIES=minimum)
        rc = command([str(control_binary), '--gtest_filter=Hypotf.CorpusIsCorrectlyRoundedInEveryMode',
                      '--gtest_brief=1'], log, test_env)
        if rc != 1 or diagnostic not in output_tail(log):
            raise RuntimeError('corpus %s failed without its specific assertion (exit %d):\n%s' %
                               (name, rc, output_tail(log)))
        print('  ok   corpus-%s detected' % name, flush=True)

    # A complete-payload pin must catch even parse-valid reference corruption.
    reference_stage = work / 'reference-payload'
    reference_stage.mkdir(parents=True, exist_ok=True)
    log = reference_stage / 'control.log'
    rc = command([sys.executable, 'tools/check-hypotf-reference.py'], log)
    if rc != 0 or 'complete committed payload SHA256 verified' not in output_tail(log):
        raise RuntimeError('reference checksum control failed:\n' + output_tail(log))
    reference_rows = [i for i in rows if lines[i].split()[:2] ==
                      ['3ff0000000000000', '3ff0000000000000']]
    if len(reference_rows) != 1:
        raise RuntimeError('reference corruption needs unique x=y=1')
    for label, column in (('result', 2), ('error', 3)):
        fields = lines[reference_rows[0]].split()
        if column == 2:
            fields[column] = '%016x' % (int(fields[column], 16) + (1 << 29))
        else:
            fields[column] = '%08x' % (int(fields[column], 16) ^ 1)
        stage = reference_stage / label
        stage.mkdir(parents=True, exist_ok=True)
        target = stage / 'hypotf.corpus'
        target.write_text('\n'.join(replace(reference_rows[0], ' '.join(fields))) + '\n')
        log = stage / 'parse.log'
        rc = command([str(control_binary), '--gtest_filter=Hypotf.CorpusIsCorrectlyRoundedInEveryMode',
                      '--gtest_brief=1'], log,
                     dict(run_env, GMATH_HYPOTF_CORPUS_DIR=str(stage), GMATH_HYPOTF_MIN_ENTRIES='1000'))
        # The independent integer parser certifies nearest target bits, so
        # a wrong result is rejected by syntax/semantics before numerical use.
        # An error-magnitude perturbation preserves its sign and valid range.
        if column == 2:
            if rc != 1 or 'bad hypotf corpus row or binary32 representation' not in log.read_text():
                raise RuntimeError('wrong reference target escaped independent parser:\n' + output_tail(log))
        elif rc not in (0, 1) or ('hypotf: %d corpus entries' % len(rows)) not in log.read_text():
            raise RuntimeError('reference error mutation did not remain parse-valid:\n' + output_tail(log))
        log = stage / 'checksum.log'
        rc = command([sys.executable, 'tools/check-hypotf-reference.py', str(target)], log)
        if rc != 1 or 'committed payload checksum differs' not in output_tail(log):
            raise RuntimeError('reference %s corruption escaped checksum:\n%s' %
                               (label, output_tail(log)))
        print('  ok   reference-%s corruption detected by checksum (%s)' %
              (label, 'also rejected by exact-target parser' if column == 2 else 'parse-valid'), flush=True)

    # Demonstrate the raw probe's exact-output cmp gate with a positive control.
    raw_stage = work / 'raw-hash'
    raw_stage.mkdir(parents=True, exist_ok=True)
    raw_probe = raw_stage / 'probe-hypotf-special'
    log = raw_stage / 'build.log'
    rc = command(cc + cflags + ['tools/probe-hypotf-special.c', str(work / 'control' / 'hypot.o'),
                               '-o', str(raw_probe)] + ldflags, log)
    if rc != 0: raise RuntimeError('raw probe build failed:\n' + output_tail(log))
    actual = raw_stage / 'actual'
    rc = command([str(raw_probe)], actual, run_env)
    if rc != 0: raise RuntimeError('raw probe control failed:\n' + output_tail(actual))
    log = raw_stage / 'control.log'
    rc = command(['cmp', 'tests/corpus/hypotf-special.hash', str(actual)], log)
    if rc != 0: raise RuntimeError('raw hash control failed:\n' + output_tail(log))
    expected = Path('tests/corpus/hypotf-special.hash').read_text().splitlines()
    matches = [i for i, line in enumerate(expected) if line.startswith('math.hypotf_special.hash ')]
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
    spec = importlib.util.spec_from_file_location('hypotf_oracle', 'tools/oracle/oracle.py')
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
        generator = Path('tools/oracle/gen_corpus_hypotf.py').read_text()
        common = Path('tools/oracle/gen_corpus_floattrig.py').read_text()
        oracle_plants = (
            ('oracle-rounding', 'common', 'q & 1', 'q & 0',
             'RuntimeError: hypotf oracle self-check failed:'),
            ('oracle-infinity-policy', 'generator',
             'if a == INF or b == INF:\n        return INF, 0',
             'if a == INF or b == INF:\n        return QNAN, 0',
             'RuntimeError: hypotf oracle self-check failed:'),
            ('oracle-transcendental-error', 'generator', '(v - fraction(result)) / unit',
             '(fraction(result) - v) / unit', 'RuntimeError: hypotf oracle self-check failed:'),
            ('oracle-wrong-mpfr-value', 'generator',
             'bounds.append(rational(gmpy2.sqrt(argument)))',
             'bounds.append(rational(gmpy2.sqrt(argument + 1)))',
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
        print('  fresh hypotf seed %s' % seed, flush=True)
        log = fresh / 'generate.log'
        argv = [oracle.ENGINE, 'run', '--rm', '--userns=keep-id',
                '-v', '%s:%s:z' % (oracle.ROOT, oracle.ROOT), '-w', oracle.ROOT,
                ref, 'python', 'tools/oracle/gen_corpus_hypotf.py', '--fresh', '--out', str(fresh),
                '--seed', seed, '--count', '3000']
        rc = command(argv, log)
        if rc != 0: raise RuntimeError('fresh oracle generation failed (seed %s):\n%s' % (seed, output_tail(log)))
        fresh_count = verify_fresh_corpus(control_binary, fresh, seed, 3000,
                                          fresh / 'selection', run_env)
        print('  ok   fresh control loads requested directory and %d entries' % fresh_count, flush=True)

    # Supplemental hash entries must be enforced, separately for each format.
    hash_source = Path('tests/corpus/trig.hash')
    hash_text = hash_source.read_text()
    hash_stage = work / 'hash-gate'
    hash_stage.mkdir(parents=True, exist_ok=True)
    for name in ('control', 'hypotf'):
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
    for name in ('hypotf',):
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
    print('check-planted-hypotf: all %d implementation plants, %d corpus-loader plants, 2 reference corruptions (wrong target parser-rejected; error magnitude parse-valid), 1 raw hash corruption, 1 supplemental hash corruption and 1 omitted probe entry and former corpus-directory typo detected; %s; controls pass' %
          (len(PLANTS) + len(PORTABLE_PLANTS) + (len(HW_PLANTS) if hardware else 0) + len(STATE_PLANTS), len(loader_plants), oracle_status))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as error:
        print('check-planted-hypotf: FAIL: %s' % error, file=sys.stderr)
        sys.exit(1)
