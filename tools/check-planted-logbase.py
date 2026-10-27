#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Require logbase tests and supplemental hash checks to reject planted defects.

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
    ('log2-reciprocal-sign', 'logbase_positive(x, GMATH_LOG2_INV_HI, GMATH_LOG2_INV_LO)', 'logbase_positive(x, -GMATH_LOG2_INV_HI, GMATH_LOG2_INV_LO)'),
    ('log10-wrong-base', 'logbase_positive(x, GMATH_LOG10_INV_HI, GMATH_LOG10_INV_LO)', 'logbase_positive(x, GMATH_LOG2_INV_HI, GMATH_LOG2_INV_LO)'),
    ('product-sign', 'return p.hi + tail;', 'return -p.hi + tail;'),
    ('normal-power-exponent', 'gmath_small_int((int)(xb >> 52) - 1023)', 'gmath_small_int((int)(xb >> 52) - 1022)'),
    ('subnormal-power-exponent', 'int e = -1074;', 'int e = -1073;'),
    ('power-sign', '    return exact;\n  }\n  return logbase_positive', '    return -exact;\n  }\n  return logbase_positive'),
    ('negative-invalid', '  if (xb & GMATH_SIGN_BIT) {\n    return gmath_invalid();\n  }\n  return x; /* +infinity */', '  if (xb & GMATH_SIGN_BIT) {\n    return gmath_double(GMATH_QNAN_BITS);\n  }\n  return x; /* +infinity */'),
    ('zero-divide-flag', '    return gmath_div_by_zero(GMATH_SIGN_BIT);\n  }\n  if (xb & GMATH_SIGN_BIT)', '    return gmath_double(GMATH_SIGN_BIT | GMATH_INF_BITS);\n  }\n  if (xb & GMATH_SIGN_BIT)'),
    ('float-signaling-invalid', '      (void)gmath_invalid();\n    }\n    result = 0x7fc00000u;', '      (void)0;\n    }\n    result = 0x7fc00000u;'),
    ('float-canonical-nan', '    result = 0x7fc00000u;\n  }\n  else if (ax == 0)', '    result = 0x7fc00001u;\n  }\n  else if (ax == 0)'),
    ('float-zero-sign', 'result = 0xff800000u;', 'result = 0x7f800000u;'),
    ('float-negative-invalid', '    (void)gmath_invalid();\n    result = 0x7fc00000u;\n  }\n  else if (ax == 0x7f800000u)', '    (void)0;\n    result = 0x7fc00000u;\n  }\n  else if (ax == 0x7f800000u)'),
    ('float-taylor-quadratic', 'double p = z + (z * z) * (-0.5 + z *', 'double p = z + (z * z) * (-0.25 + z *'),
    ('float-final-exponent', 'return gmath_small_int((int)e) + logm * GMATH_LOG2_INV_HI;', 'return gmath_small_int((int)e + 1) + logm * GMATH_LOG2_INV_HI;'),
    ('float-wrong-base', 'logm * GMATH_LOG2_INV_HI;', 'logm * GMATH_LOG10_INV_HI;'),
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
        binary = stage / 'testLogbase'
        rc = command(cxx + ['-o', str(binary), test_object, str(stage / 'explog.o')] +
                     ldflags, link_log)
        if rc != 0:
            raise RuntimeError('%s: link failed:\n%s' % (name, output_tail(link_log)))
        test_log = stage / 'test.log'
        rc = command([str(binary), '--gtest_filter=Logbase.*', '--gtest_brief=1'],
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
    # Run the generator's fixed answers in its pinned image, with both base
    # choices swapped together so its independent arithmetic still agrees.
    import importlib.util
    spec = importlib.util.spec_from_file_location('logbase_oracle', 'tools/oracle/oracle.py')
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
        generator = Path('tools/oracle/gen_corpus_logbase.py').read_text()
        base_rule = "fn == 'log10'"
        wrong_rule = "fn == 'log2'"
        if generator.count(base_rule) != 2:
            raise RuntimeError('generator wrong-base mutation must match twice')
        for changed in (False, True):
            name = 'oracle-mutated' if changed else 'oracle-control'
            stage = work / name
            stage.mkdir(parents=True, exist_ok=True)
            script = stage / 'generator.py'
            script.write_text(generator.replace(base_rule, wrong_rule) if changed else generator)
            log = stage / 'test.log'
            run = "import runpy; runpy.run_path(%r)['self_check']()" % str(script)
            argv = [oracle.ENGINE, 'run', '--rm', '--userns=keep-id',
                    '-v', '%s:%s:z' % (oracle.ROOT, oracle.ROOT), '-w', oracle.ROOT,
                    ref, 'python', '-c', run]
            rc = command(argv, log)
            if changed:
                if rc != 1 or 'RuntimeError: logbase oracle self-check failed:' not in output_tail(log):
                    raise RuntimeError('generator defect was not rejected by its self-check:\n' + output_tail(log))
            elif rc != 0:
                raise RuntimeError('unmodified generator failed:\n' + output_tail(log))
            print('  ok   %s %s' % (name, 'detected' if changed else 'passes'), flush=True)

    # Supplemental hash entries must be enforced, separately for each format.
    hash_source = Path('tests/corpus/trig.hash')
    hash_text = hash_source.read_text()
    hash_stage = work / 'hash-gate'
    hash_stage.mkdir(parents=True, exist_ok=True)
    for name in ('control', 'log2', 'log10', 'log2f'):
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
    for name in ('log2', 'log10', 'log2f'):
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
    oracle_status = 'oracle plant detected' if ref is not None else 'oracle plant SKIPPED (no pinned image)'
    print('check-planted-logbase: all %d implementation plants, 3 hash corruptions and 3 omitted probe entries detected; %s; controls pass' %
          (len(PLANTS), oracle_status))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as error:
        print('check-planted-logbase: FAIL: %s' % error, file=sys.stderr)
        sys.exit(1)
