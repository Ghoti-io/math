#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact rounding implementation/state defects and fresh selection controls."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


def run(args,log,environment=None):
    with log.open('w') as out:
        r=subprocess.run(args,stdout=out,stderr=subprocess.STDOUT,env=environment,timeout=60,check=False)
    if r.returncode not in (0,1):raise RuntimeError('unexpected status %d: %s\n%s'%(r.returncode,args,log.read_text()[-4000:]))
    return r.returncode


def fresh(binary,directory,seed,count):
    directory=Path(directory).resolve()
    with tempfile.TemporaryDirectory(prefix='intround-selection-') as temporary:
        stage=Path(temporary);env=dict(os.environ,GMATH_INTROUND_CORPUS_DIR=str(directory))
        expected=[]
        for width in (32,64):
            lines=(directory/('intround%d.corpus'%width)).read_text().splitlines()
            population=sum(bool(line) and not line.startswith('#') for line in lines)
            if lines[2]!='# seed %d count %d fresh True entries %d'%(int(seed),int(count),population):
                raise RuntimeError('fresh metadata/population mismatch')
            expected.append('intround%d: %d reference entries from %s'%(width,population,directory))
        argv=[str(Path(binary).resolve()),'--gtest_filter=IntegerRound.ExactReferencesAndAllModeState','--gtest_brief=1']
        log=stage/'selected.log'
        if run(argv,log,env) or any(text not in log.read_text() for text in expected):raise RuntimeError('requested fresh corpus not selected')
        empty=stage/'empty';empty.mkdir();env['GMATH_INTROUND_CORPUS_DIR']=str(empty);log=stage/'empty.log'
        if run(argv,log,env)!=1 or 'missing integer-rounding corpus: '+str(empty) not in log.read_text():
            raise RuntimeError('ignored corpus directory escaped empty control')
    print('intround fresh: requested metadata, populations and directory verified',flush=True)


def main():
    if len(sys.argv)>1:
        if len(sys.argv)!=6 or sys.argv[1]!='--verify-fresh':raise RuntimeError('usage: --verify-fresh BINARY DIR SEED COUNT')
        fresh(*sys.argv[2:]);return 0
    env=os.environ;work=Path(env['PLANT_WORK']);work.mkdir(parents=True,exist_ok=True)
    cc,cflags=shlex.split(env['PLANT_CC']),shlex.split(env['PLANT_CFLAGS'])
    cxx,ldflags=shlex.split(env['PLANT_CXX']),shlex.split(env['PLANT_LDFLAGS'])
    original=Path('src/elementary/intround.c').read_text()
    plants=[('half-equality','ir_absolute < UINT64_C(0x3fe0000000000000)','ir_absolute <= UINT64_C(0x3fe0000000000000)'),
      ('fraction-tie','ir_fraction >= (UINT64_C(1) << (ir_shift - 1u))','ir_fraction > (UINT64_C(1) << (ir_shift - 1u))'),
      ('integer-significand','ir_magnitude = ir_significand <<','ir_magnitude = (ir_significand >> 1) <<'),
      ('range-bound','ir_absolute >= UINT64_C(0x43e0000000000000)','ir_absolute >= UINT64_C(0x43d0000000000000)'),
      ('positive-endpoint','&& ir_negative &&','&& 1u &&'),
      ('missing-invalid','(void)gmath_invalid();','(void)0;'),
      ('float-half','ir_absolute < 0x3f000000u','ir_absolute < 0x3f800000u'),
      ('float-widening','ir_field + 896u','ir_field + 895u'),
      ('float-sign','((uint64_t)(ir_raw >> 31) << 63)','((uint64_t)0 << 63)'),
      ('errno','long gmath_lround(double x) {return','long gmath_lround(double x) {errno = 0; return'),
      ('mode','long gmath_lround(double x) {return','long gmath_lround(double x) {(void)fesetround(FE_TONEAREST); return'),
      ('incoming-flags','long gmath_lround(double x) {return','long gmath_lround(double x) {(void)feclearexcept(FE_ALL_EXCEPT); return'),
      ('spurious-inexact','long gmath_lround(double x) {return','long gmath_lround(double x) {(void)feraiseexcept(FE_INEXACT); return')]
    width_check=work/'compiler-width.c';width_check.write_text('#include <limits.h>\n#if LONG_MAX == 2147483647L\nIR_LONG32\n#else\nIR_LONG64\n#endif\n')
    width_log=work/'compiler-width.log'
    if run(cc+cflags+['-E','-P',str(width_check)],width_log):raise RuntimeError('compiler width query failed')
    if 'IR_LONG32' in width_log.read_text():
        plants.extend([('range-equality','ir_magnitude > ir_maximum + ir_negative','ir_magnitude >= ir_maximum + ir_negative'),
                       ('range-sign-allowance','ir_magnitude > ir_maximum + ir_negative','ir_magnitude > ir_maximum')])
    else:
        print('  SKIPPED native signed32 range plants: compiler long is64; run dedicated ILP32 controls',flush=True)
    for name,old,new in [('control',None,None)]+plants:
        stage=work/name;stage.mkdir(parents=True,exist_ok=True);text=original
        if old is not None:
            if text.count(old)!=1:raise RuntimeError(name+': nonunique plant anchor')
            text=text.replace(old,new,1)
        source=stage/'intround.c';source.write_text('#include <errno.h>\n#include <fenv.h>\n'+text)
        shutil.copyfile('src/elementary/elem_common.h',stage/'elem_common.h')
        obj=stage/'intround.o';binary=stage/'testIntround'
        if run(cc+cflags+['-c',str(source),'-o',str(obj)],stage/'compile.log'):raise RuntimeError(name+': compile failed')
        if run(cxx+['-o',str(binary),env['PLANT_TEST_OBJ'],str(obj)]+ldflags,stage/'link.log'):raise RuntimeError(name+': link failed')
        status=run([str(binary),'--gtest_brief=1'],stage/'test.log')
        if status!=(0 if old is None else 1):raise RuntimeError(name+': defect escaped/control failed')
        print('  ok   intround '+name+(' passes' if old is None else ' detected'),flush=True)
    raw=work/'raw-output-control.txt'
    if run([env['PLANT_RAW_PROBE']],raw):raise RuntimeError('raw output control failed')
    if run([sys.executable,'tools/check-intround-output.py',str(raw)],work/'raw-control.log'):
        raise RuntimeError('raw comparison control failed')
    lines=raw.read_text().splitlines(keepends=True)
    for index in range(len(lines)):
        changed=list(lines)
        if index==0:changed[index]='math.intround_long.bits '+('64' if '32' in lines[0] else '32')+'\n'
        else:
            label,value=changed[index].split();changed[index]=label+' '+('0' if value!='0' else '1')+'\n'
        path=work/('raw-output-%d.txt'%index);path.write_text(''.join(changed))
        if run([sys.executable,'tools/check-intround-output.py',str(path)],work/('raw-output-%d.log'%index))!=1:
            raise RuntimeError('raw comparison defect escaped field%d'%index)
        print('  ok   intround raw comparison field%d detected'%index,flush=True)
    reference=Path('tests/corpus')
    for name in ('intround32.corpus','intround64.corpus','lround.corpus','lroundf.corpus','intround-long32.hash','intround-long64.hash'):
        stage=work/('checksum-'+name);stage.mkdir(parents=True,exist_ok=True)
        for payload in ('intround32.corpus','intround64.corpus','lround.corpus','lroundf.corpus','intround-long32.hash','intround-long64.hash'):
            shutil.copyfile(reference/payload,stage/payload)
        path=stage/name;data=path.read_bytes();path.write_bytes(data[:-1]+(b'x' if data[-1:]!=b'x' else b'y'))
        if run([sys.executable,'tools/check-intround-reference.py',str(stage)],stage/'test.log')!=1:raise RuntimeError(name+': checksum corruption escaped')
        print('  ok   intround checksum '+name+' detected',flush=True)
    sys.path.insert(0,str(Path('tools/oracle').resolve()))
    import oracle
    try:image,_=oracle.check_pin(timeout=60)
    except oracle.Unavailable as error:
        if oracle.REQUIRED:raise RuntimeError('pinned integer oracle controls required: '+str(error)) from error
        print('  SKIPPED pinned integer oracle fault controls: '+str(error),flush=True)
        return 0
    generator=Path('tools/oracle/gen_corpus_intround.py').read_text()
    faults=[('fraction-ties','2*remainder>=q.denominator','2*remainder>q.denominator'),
            ('mpfr-ties','gmpy2.rint_round(','gmpy2.rint('),
            ('destination-range','invalid=not -(1<<(bits-1))<=rounded<(1<<(bits-1))','invalid=False'),
            ('raw-decoding','(52,1023,11)','(52,1024,11)')]
    for name,old,new in [('control',None,None)]+faults:
        stage=work/('oracle-'+name);stage.mkdir(parents=True,exist_ok=True)
        if old is not None and generator.count(old)!=1:raise RuntimeError('oracle fault anchor must match once: '+name)
        source=stage/'gen.py';source.write_text(generator if old is None else generator.replace(old,new,1))
        result=oracle.engine_run(image,['python',str(source.resolve()),'--out',str((stage/'references').resolve()),'--seed','777','--count','0'],capture=True,timeout=60)
        (stage/'test.log').write_text(result.stdout+result.stderr)
        if old is None:
            if result.returncode!=0:raise RuntimeError('pinned oracle positive control failed: '+result.stderr[-2000:])
        elif result.returncode!=1 or not any(text in result.stderr for text in ('Fraction/MPFR integer disagreement','integer oracle fixed-case disagreement')):
            raise RuntimeError('pinned oracle fault escaped/wrong failure: '+name)
        print('  ok   intround oracle '+name+(' passes' if old is None else ' detected'),flush=True)
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,OSError,KeyError,subprocess.TimeoutExpired) as error:
        print('check-planted-intround: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
