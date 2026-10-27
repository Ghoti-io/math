#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Prove unary API/state defects fail; verify requested fresh selection."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


def command(args, path, environment=None):
    with path.open('w') as out:
        result = subprocess.run(args, stdout=out, stderr=subprocess.STDOUT,
                                env=environment, timeout=60, check=False)
    if result.returncode not in (0, 1):
        raise RuntimeError('unexpected status %d: %s\n%s' % (result.returncode, args, path.read_text()[-4000:]))
    return result.returncode


def verify_fresh(binary, directory, seed, count):
    directory = Path(directory).resolve()
    lines = (directory/'atanf.corpus').read_text().splitlines()
    population = sum(bool(line) and not line.startswith('#') for line in lines)
    expected = '# seed %d count %d fresh True entries %d' % (int(seed), int(count), population)
    if lines[2] != expected: raise RuntimeError('fresh requested metadata/count mismatch')
    with tempfile.TemporaryDirectory(prefix='atanf-selection-') as temporary:
        stage = Path(temporary)
        env = dict(os.environ, GMATH_ATANF_CORPUS_DIR=str(directory))
        args = [str(Path(binary).resolve()), '--gtest_filter=Atanf.PinnedAccuracyAndAllModeState', '--gtest_brief=1']
        log = stage/'selected.log'
        if command(args, log, env) != 0 or ('%d reference entries from %s' % (population, directory)) not in log.read_text():
            raise RuntimeError('fresh sample not selected: '+log.read_text()[-4000:])
        # Disposable empty directory detects ignored/typo overrides even when
        # committed and fresh samples happen to have identical row counts.
        empty = stage/'empty';empty.mkdir()
        env['GMATH_ATANF_CORPUS_DIR'] = str(empty)
        log = stage/'empty.log'
        if command(args, log, env) != 1 or 'missing atanf corpus: '+str(empty) not in log.read_text():
            raise RuntimeError('empty-directory selection control escaped')
    print('atanf fresh: requested metadata, %d entries and directory selection verified' % population)


def main():
    if len(sys.argv) > 1:
        if len(sys.argv) != 6 or sys.argv[1] != '--verify-fresh': raise RuntimeError('usage: --verify-fresh BINARY DIR SEED COUNT')
        verify_fresh(*sys.argv[2:]);return 0
    env = os.environ
    cc, cflags = shlex.split(env['PLANT_CC']), shlex.split(env['PLANT_CFLAGS'])
    cxx, ldflags = shlex.split(env['PLANT_CXX']), shlex.split(env['PLANT_LDFLAGS'])
    work = Path(env['PLANT_WORK']);work.mkdir(parents=True, exist_ok=True)
    original = Path('src/elementary/atan2.c').read_text()
    marker = 'float gmath_atanf(float x) {'
    if original.count(marker) != 1: raise RuntimeError('unary function marker must match once')
    anchor = original[original.index(marker):]
    wrappers = [('zero', '(void)x; return 0.0f;'),
                ('swapped', 'return gmath_atan2f(1.0f, x);'),
                ('wrong-abscissa', 'return gmath_atan2f(x, 2.0f);'),
                ('wrong-sign', 'return gmath_atan2f(-x, 1.0f);'),
                ('errno', 'errno = 0; return gmath_atan2f(x, 1.0f);'),
                ('mode', '(void)fesetround(FE_TONEAREST); return gmath_atan2f(x, 1.0f);'),
                ('flags', 'float result = gmath_atan2f(x, 1.0f); (void)feclearexcept(FE_ALL_EXCEPT); return result;')]
    plants = [('control', None, None)] + [(name,anchor,marker+'\n  '+body+'\n}\n') for name,body in wrappers]
    plants += [
      ('unary-snan','if ((uf_absolute & 0x00400000u) == 0) (void)gmath_invalid();','if ((uf_absolute & 0x00400000u) == 0) (void)0;'),
      ('unary-qnan','return af_value(0x7fc00000u);','return af_value(0x7fc00001u);'),
      ('unary-infinity','return af_angle(0x3fc90fdbu, uf_sign);','return af_angle(0x3f490fdbu, uf_sign);'),
      ('unary-zero','if (uf_absolute == 0) return af_value(uf_word);','if (uf_absolute == 0) return af_value(0);'),
      ('unary-underflow','if (uf_absolute < 0x00800000u) (void)gmath_underflow(0);','if (uf_absolute < 0x00800000u) af_inexact();'),
      ('unary-underflow-boundary','if (uf_absolute < 0x00800000u)','if (uf_absolute <= 0x00800000u)'),
      ('unary-tiny-inexact','else af_inexact();','else (void)0;'),
      ('unary-tiny-bits','    return af_value(uf_word);\n  }','    return af_value(uf_word & 0x7fffffffu);\n  }'),
      ('unary-one','return af_angle(0x3f490fdbu, uf_sign);','return af_angle(0x3fc90fdbu, uf_sign);'),
      ('unary-reciprocal','1.0 / uf_d : uf_d','1.0 / uf_d : 0.5 * uf_d'),
      ('unary-reflection','uf_result = GMATH_PIO2_HI - uf_result;','uf_result = GMATH_PI_HI - uf_result;'),
      ('unary-normal-inexact-loss','  af_inexact();\n  return uf_narrow;','  (void)feclearexcept(FE_INEXACT);\n  return uf_narrow;'),
      ('unary-sign-before-narrow',
       '  uf_result = gmath_double(gmath_bits(uf_result) | ((uint64_t)uf_sign << 32));\n  float uf_narrow = (float)uf_result;',
       '  float uf_narrow = (float)uf_result;\n  uint32_t uf_raw_narrow; memcpy(&uf_raw_narrow,&uf_narrow,sizeof uf_raw_narrow);\n  uf_narrow = af_value(uf_raw_narrow | uf_sign);')]
    for name,old,new in plants:
        stage = work/name;stage.mkdir(parents=True, exist_ok=True)
        text=original
        if old is not None:
            # Local unary anchors are checked only in the unary function,
            # preserving binary mutation fingerprints even for shared literals.
            if anchor.count(old)!=1: raise RuntimeError('unary plant anchor must match once: '+name)
            text=original.replace(anchor,anchor.replace(old,new,1),1)
        source = stage/'atan2.c';source.write_text('#include <errno.h>\n#include <fenv.h>\n'+text)
        for header in ('elem_common.h', 'atan2_table.h'):
            shutil.copyfile(Path('src/elementary')/header, stage/header)
        obj = stage/'atan2.o';binary = stage/'testAtanf'
        if command(cc+cflags+['-c', str(source), '-o', str(obj)], stage/'compile.log'):
            raise RuntimeError('plant compile failed: '+name)
        if command(cxx+['-o', str(binary), env['PLANT_TEST_OBJ'], str(obj)]+ldflags, stage/'link.log'):
            raise RuntimeError('plant link failed: '+name)
        status = command([str(binary), '--gtest_filter=Atanf.PinnedAccuracyAndAllModeState:Atanf.RawSpecialsAndIncomingState:Atanf.OldPathBitAndStateCompatibility', '--gtest_brief=1'], stage/'test.log')
        if status != (0 if old is None else 1): raise RuntimeError('plant outcome wrong: '+name)
        print('  ok   atanf '+name+(' passes' if old is None else ' detected'), flush=True)
    payload=Path('tests/corpus/atanf.corpus').read_text()
    rows=payload.splitlines(keepends=True)
    first=next(i for i,line in enumerate(rows) if not line.startswith('#'))
    for name, changed in (
            ('metadata',payload.replace('# function atanf','# function atan2f',1)),
            ('truncation',''.join(rows[:-1])),
            ('input',''.join(rows[:first])+rows[first].replace('0000000000000000','8000000000000000',1)+''.join(rows[first+1:])),
            ('result',''.join(rows[:first])+rows[first][:17]+'8000000000000000'+rows[first][33:]+''.join(rows[first+1:])),
            ('error',''.join(rows[:first])+rows[first][:-9]+'00000001\n'+''.join(rows[first+1:]))):
        path=work/('reference-'+name+'.corpus');path.write_text(changed)
        if changed==payload or command([sys.executable,'tools/check-atanf-reference.py',str(path)],work/('reference-'+name+'.log'))!=1:
            raise RuntimeError('reference checksum defect escaped: '+name)
        print('  ok   atanf reference '+name+' detected',flush=True)
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except (RuntimeError, OSError, KeyError, subprocess.TimeoutExpired) as error:
        print('check-planted-atanf: FAIL: '+str(error), file=sys.stderr);sys.exit(1)
