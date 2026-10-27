#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Require cbrt tests and supplemental hash checks to reject planted defects.

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
    ('subnormal-normalization', 'e = -1022 - (int)shift;', 'e = -1021 - (int)shift;'),
    ('negative-exponent-decomposition', '    --q;', '    ++q;'),
    ('residue-factor', '* gmath_cbrt_factor[r];', '* gmath_cbrt_factor[0];'),
    ('seed-linear-coefficient', 's * (1.0 / 3.0 + s *', 's * (1.0 / 2.0 + s *'),
    ('seed-midpoint', '(double)(2 * j + 1) * 0x1p-7', '(double)(j + 1) * 0x1p-7'),
    ('cube-low-tail', 'double cube_low = cube.lo + square.lo * y;', 'double cube_low = 0.0;'),
    ('newton-denominator', 'residual / ((3.0 * y) * y)', 'residual / ((2.0 * y) * y)'),
    ('newton-correction-sign', 'double root = y + correction;', 'double root = y - correction;'),
    ('dividend-sign', 'uint64_t sign = xb & GMATH_SIGN_BIT;', 'uint64_t sign = 0;'),
    ('signed-zero', 'if (ax == 0) {\n    return x;', 'if (ax == 0) {\n    return 0.0;'),
    ('infinity', 'return ax == GMATH_INF_BITS ? x : gmath_nan_of(x);', 'return ax == GMATH_INF_BITS ? 0.0 : gmath_nan_of(x);'),
    ('nan-canonical', 'return ax == GMATH_INF_BITS ? x : gmath_nan_of(x);', 'return ax == GMATH_INF_BITS ? x : x;'),
    ('signaling-nan-invalid', 'return ax == GMATH_INF_BITS ? x : gmath_nan_of(x);', 'return ax == GMATH_INF_BITS ? x : gmath_double(GMATH_QNAN_BITS);'),
    ('exact-binary-cube-exponent', '((uint64_t)(q + 1023) << 52) | sign', '((uint64_t)(q + 1022) << 52) | sign'),
    ('final-packed-exponent', '((uint64_t)(int64_t)q << 52)) | sign', '((uint64_t)(int64_t)(q + 1) << 52)) | sign'),
]

TABLE_PLANTS = [
    ('table-reciprocal', '0x1.fc07f01fc07f0p-1', '0x1.fc07f01fc07f0p+0'),
    ('table-root', '0x1.00aa396152144p+0', '0x1.00aa396152144p+1'),
    ('table-residue-factor', '0x1.428a2f98d728bp+0', '0x1.428a2f98d728bp+1'),
]
STATE_PLANTS = [
    ('errno-change', 'errno = EDOM;', 'result_errno'),
    ('incoming-flags-cleared', '(void)feclearexcept(FE_ALL_EXCEPT);',
     'result_flags & (policy.required | existing)'),
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
    original = (SOURCE / 'cbrt.c').read_text()
    run_env = dict(env, LD_LIBRARY_PATH=ld_path)

    def build_run(name, replacement=None, portable=False, table_replacement=None, diagnostic=None):
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
        (stage / 'cbrt.c').write_text(text)
        for header in ('elem_common.h', 'cbrt_table.h'):
            shutil.copyfile(SOURCE / header, stage / header)
        if table_replacement is not None:
            old, new = table_replacement
            table = (stage / 'cbrt_table.h').read_text()
            if old == new or table.count(old) != 1:
                raise RuntimeError('%s: table replacement must match once (found %d)' %
                                   (name, table.count(old)))
            (stage / 'cbrt_table.h').write_text(table.replace(old, new, 1))
        planted = replacement is not None or table_replacement is not None
        compile_log = stage / 'compile.log'
        flags = cflags + (['-DGMATH_CBRT_PORTABLE_BITS'] if portable else [])
        rc = command(cc + flags + ['-I', str(stage), '-c', str(stage / 'cbrt.c'),
                                   '-o', str(stage / 'cbrt.o')], compile_log)
        if rc != 0:
            raise RuntimeError('%s: compile failed:\n%s' % (name, output_tail(compile_log)))
        link_log = stage / 'link.log'
        binary = stage / 'testCbrt'
        rc = command(cxx + ['-o', str(binary), test_object, str(stage / 'cbrt.o')] +
                     ldflags, link_log)
        if rc != 0:
            raise RuntimeError('%s: link failed:\n%s' % (name, output_tail(link_log)))
        test_log = stage / 'test.log'
        rc = command([str(binary), '--gtest_filter=Cbrt.*', '--gtest_brief=1'],
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
    build_run('control-portable', portable=True)
    for name, old, new in PLANTS:
        build_run(name, (old, new))
    for name, old, new in TABLE_PLANTS:
        build_run(name, table_replacement=(old, new), diagnostic='cbrt input')
    for name, statement, diagnostic in STATE_PLANTS:
        signature = 'double gmath_cbrt(double x) {'
        build_run(name, (signature, signature + '\n  ' + statement), diagnostic=diagnostic)
    # Prove the corpus loader rejects metadata, population and setting damage.
    corpus_lines = Path('tests/corpus/cbrt.corpus').read_text().splitlines()
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
         'missing required cbrt entries header'),
        ('corpus-truncated', truncated, '1000',
         'cbrt corpus count disagrees with header'),
        ('corpus-duplicate', duplicated, '1000', 'duplicate cbrt input word'),
        ('corpus-invalid-minimum', corpus_lines, 'garbage',
         'GMATH_CBRT_MIN_ENTRIES must be a complete positive decimal integer'),
    )
    for name, lines, minimum, diagnostic in corpus_plants:
        stage = work / name
        stage.mkdir(parents=True, exist_ok=True)
        (stage / 'cbrt.corpus').write_text('\n'.join(lines) + '\n')
        log = stage / 'test.log'
        test_env = dict(run_env, GMATH_CBRT_CORPUS_DIR=str(stage),
                        GMATH_CBRT_MIN_ENTRIES=minimum)
        rc = command([str(control_binary),
                      '--gtest_filter=Cbrt.CorpusIsWithinOneUlp',
                      '--gtest_brief=1'], log, test_env)
        if rc != 1 or diagnostic not in output_tail(log):
            raise RuntimeError('%s corpus defect was not specifically detected (exit %d):\n%s' %
                               (name, rc, output_tail(log)))
        print('  ok   %s detected' % name, flush=True)

    # Run fixed oracle answers in the pinned image; test rounding and error signs.
    import importlib.util
    spec = importlib.util.spec_from_file_location('cbrt_oracle', 'tools/oracle/oracle.py')
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
        generator = Path('tools/oracle/gen_corpus_cbrt.py').read_text()
        oracle_plants = (
            ('oracle-midpoint-tie', 'q & 1', '1'),
            ('oracle-error-sign', 'error = (fr - rf) / unit',
             'error = (rf - fr) / unit'),
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
                if rc != 1 or 'RuntimeError: cbrt oracle self-check failed:' not in output_tail(log):
                    raise RuntimeError('generator defect was not rejected by its self-check:\n' + output_tail(log))
            elif rc != 0:
                raise RuntimeError('unmodified generator failed:\n' + output_tail(log))
            print('  ok   %s %s' % (name, 'detected' if changed else 'passes'), flush=True)

    # Supplemental hash entries must be enforced, separately for each format.
    hash_source = Path('tests/corpus/trig.hash')
    hash_text = hash_source.read_text()
    hash_stage = work / 'hash-gate'
    hash_stage.mkdir(parents=True, exist_ok=True)
    for name in ('control', 'cbrt'):
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
    for name in ('cbrt',):
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
    print('check-planted-cbrt: all %d implementation plants, 4 corpus-loader plants, 1 hash corruption and 1 omitted probe entry detected; %s; controls pass' %
          (len(PLANTS) + len(TABLE_PLANTS) + len(STATE_PLANTS), oracle_status))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as error:
        print('check-planted-cbrt: FAIL: %s' % error, file=sys.stderr)
        sys.exit(1)
