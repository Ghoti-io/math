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
    anchor = 'return gmath_atan2f(x, 1.0f);'
    if original.count(anchor) != 1: raise RuntimeError('unary wrapper anchor must match once')
    plants = [('control', None), ('zero', '(void)x; return 0.0f;'),
              ('swapped', 'return gmath_atan2f(1.0f, x);'),
              ('wrong-abscissa', 'return gmath_atan2f(x, 2.0f);'),
              ('wrong-sign', 'return gmath_atan2f(-x, 1.0f);'),
              ('errno', 'errno = 0; return gmath_atan2f(x, 1.0f);'),
              ('mode', '(void)fesetround(FE_TONEAREST); return gmath_atan2f(x, 1.0f);'),
              ('flags', 'float result = gmath_atan2f(x, 1.0f); (void)feclearexcept(FE_ALL_EXCEPT); return result;')]
    for name, replacement in plants:
        stage = work/name;stage.mkdir(parents=True, exist_ok=True)
        source = stage/'atan2.c'
        source.write_text('#include <errno.h>\n#include <fenv.h>\n'+(original if replacement is None else original.replace(anchor, replacement)))
        for header in ('elem_common.h', 'atan2_table.h'):
            shutil.copyfile(Path('src/elementary')/header, stage/header)
        obj = stage/'atan2.o';binary = stage/'testAtanf'
        if command(cc+cflags+['-c', str(source), '-o', str(obj)], stage/'compile.log'):
            raise RuntimeError('plant compile failed: '+name)
        if command(cxx+['-o', str(binary), env['PLANT_TEST_OBJ'], str(obj)]+ldflags, stage/'link.log'):
            raise RuntimeError('plant link failed: '+name)
        status = command([str(binary), '--gtest_filter=Atanf.PinnedAccuracyAndAllModeState:Atanf.RawSpecialsAndIncomingState', '--gtest_brief=1'], stage/'test.log')
        if status != (0 if replacement is None else 1): raise RuntimeError('plant outcome wrong: '+name)
        print('  ok   atanf '+name+(' passes' if replacement is None else ' detected'), flush=True)
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
