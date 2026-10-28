#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Compile actual Float cube-root arithmetic/special/state defects and run C/C++."""
import os
from pathlib import Path
import shlex
import subprocess
import sys

def words(name): return shlex.split(os.environ[name])
def command(argv,label,expect=0):
    p=subprocess.run(argv,capture_output=True,text=True,timeout=60)
    (work/(label+'.log')).write_text(p.stdout+p.stderr)
    if expect is not None and p.returncode!=expect: raise RuntimeError(label+': status '+str(p.returncode))
    return p.returncode

def build(source,label):
    src=work/(label+'.c');src.write_text('#include <errno.h>\n#include <fenv.h>\n'+source);obj=work/(label+'.o')
    command(words('PLANT_CC')+words('PLANT_CFLAGS')+['-Isrc/elementary','-c',str(src),'-o',str(obj)],label+'-compile')
    raw=work/(label+'-raw');unit=work/(label+'-unit');archive=os.environ['PLANT_ARCHIVE']
    command(words('PLANT_CC')+words('PLANT_CFLAGS')+['tools/probe-cbrtf.c',str(obj),archive]+words('PLANT_RAW_LDFLAGS')+['-lm','-o',str(raw)],label+'-raw-link')
    command(words('PLANT_CXX')+[os.environ['PLANT_TEST_OBJ'],str(obj),archive]+words('PLANT_LDFLAGS')+['-o',str(unit)],label+'-unit-link')
    return command([str(raw)],label+'-raw-run',None),command([str(unit),'--gtest_filter=Cbrtf.PinnedCorpusAndCallerState','--gtest_brief=1'],label+'-unit-run',None)

def main():
    source=Path('src/elementary/float_cbrt.c').read_text()
    if build(source,'control')!=(0,0): raise RuntimeError('valid source control failed')
    plants=[('returninput','float result=(float)gmath_cbrt((double)x);','float result=x;'),
      ('sign','return result;','return -result;'),
      ('zero-sign','return fc_value(word);','return fc_value(a);'),
      ('NaN-payload','return fc_value(0x7fc00000u);','return fc_value(word|0x00400000u);'),
      ('signaling-invalid','if (!(a&0x00400000u)) (void)gmath_invalid();','if (0) (void)gmath_invalid();'),
      ('quiet-invalid','if (!(a&0x00400000u)) (void)gmath_invalid();','(void)gmath_invalid();'),
      ('exact-power-IX','return exponent%3==0;','return exponent%3!=0;'),
      ('errno','uint32_t word=fc_word(x), a=word&0x7fffffffu;','uint32_t word=fc_word(x), a=word&0x7fffffffu; errno=0;'),
      ('zero-errno','uint32_t word=fc_word(x), a=word&0x7fffffffu;','uint32_t word=fc_word(x), a=word&0x7fffffffu; if (!errno) errno=732;'),
      ('rounding','uint32_t word=fc_word(x), a=word&0x7fffffffu;','uint32_t word=fc_word(x), a=word&0x7fffffffu; (void)fesetround(FE_TONEAREST);'),
      ('mixed-flags','uint32_t word=fc_word(x), a=word&0x7fffffffu;','uint32_t word=fc_word(x), a=word&0x7fffffffu; if ((fetestexcept(FE_INVALID|FE_DIVBYZERO)&(FE_INVALID|FE_DIVBYZERO))==(FE_INVALID|FE_DIVBYZERO)) (void)feclearexcept(FE_INVALID|FE_DIVBYZERO);'),
      ('observable-IX-loss','return result;','(void)feclearexcept(FE_INEXACT); return result;')]
    for label,old,new in plants:
        if source.count(old)!=1: raise RuntimeError('mutation anchor not unique: '+label)
        if build(source.replace(old,new),label)!=(1,1): raise RuntimeError('source plant escaped C/C++: '+label)
    old='volatile double big=0x1p100;\n    volatile double ignored=big+1.0;\n    (void)ignored;'
    if source.count(old)!=1: raise RuntimeError('force-only anchor')
    state=build(source.replace(old,'(void)0;'),'force-only-deletion')
    if state not in ((0,0),(1,1)): raise RuntimeError('force-only results disagree')
    print(f'cbrtf: {len(plants)} source/state plants detect in C/C++; control passes')
    print('cbrtf: force-only deletion '+('detected on this sample' if state==(1,1) else 'NOT detected; narrow witness coverage remains unverified'))
if __name__=='__main__':
    work=Path(os.environ['PLANT_WORK']);work.mkdir(parents=True,exist_ok=True)
    try: main()
    except (OSError,RuntimeError,subprocess.SubprocessError) as e:
        print('cbrtf plants: FAIL: '+str(e),file=sys.stderr);sys.exit(1)
