#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Compile real source/state defects and require specific unit-test failures."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def run(args, log, allowed=(0,)):
    with log.open('w') as output:
        result=subprocess.run(args,stdout=output,stderr=subprocess.STDOUT,timeout=120,check=False)
    if result.returncode not in allowed:
        raise RuntimeError('unexpected process status: '+str(args)+'\n'+log.read_text()[-3000:])
    return result.returncode


def main():
    env=os.environ;work=Path(env['PLANT_WORK']);work.mkdir(parents=True,exist_ok=True)
    text=Path('src/elementary/fraction_split.c').read_text()
    plants=[('control',None,None)]
    # Replacements are deliberately format-specific, checked exactly once.
    for width,sign,qnan in ((64,'GMATH_SIGN_BIT','GMATH_QNAN_BITS'),(32,'UINT32_C(0x80000000)','UINT32_C(0x7fc00000)')):
        source=text[:text.index('float gmath_modff')] if width==64 else text[text.index('float gmath_modff'):]
        changes=[('snan','(void)gmath_invalid();','(void)0;'),
                 ('mask','<< shift) - 1','<< shift) - 2'),
                 ('subtract','x - whole','whole - x')]
        if width==64:
            changes += [('small-sign','whole = gmath_double(sign);','whole = gmath_double(0);'),
                        ('zero-sign','fraction = gmath_double(sign);','fraction = gmath_double(0);'),
                        ('canonical','whole = fraction = gmath_double(GMATH_QNAN_BITS);','whole = fraction = gmath_double(GMATH_QNAN_BITS | 1);'),
                        ('fraction-bypass','fraction = x;','fraction = 0.0;')]
        else:
            changes += [('small-sign','whole_word = sign;','whole_word = 0;'),
                        ('zero-sign','fraction_word = sign;','fraction_word = 0;'),
                        ('canonical','whole_word = fraction_word = UINT32_C(0x7fc00000);','whole_word = fraction_word = UINT32_C(0x7fc00001);'),
                        ('fraction-bypass','fraction_word = word;','fraction_word = 0;')]
        marker='double gmath_modf(double x, double * integral) {' if width==64 else 'float gmath_modff(float x, float * integral) {'
        changes += [('null-result',marker,marker+'\n  if (!integral) return 0.0;'),
                    ('null-flags',marker,marker+'\n  if (!integral) (void)feraiseexcept(FE_INEXACT);'),
                    ('zero-errno',marker,marker+'\n  if (errno == 0) errno = 7;'),
                    ('mixed-flags',marker,marker+'\n  if ((fetestexcept(FE_ALL_EXCEPT) & (FE_INVALID|FE_DIVBYZERO)) == (FE_INVALID|FE_DIVBYZERO)) (void)feclearexcept(FE_INVALID);'),
                    ('errno',marker,marker+'\n  errno = 0;'),
                    ('mode',marker,marker+'\n  (void)fesetround(FE_TONEAREST);'),
                    ('incoming',marker,marker+'\n  (void)feclearexcept(FE_ALL_EXCEPT);'),
                    ('spurious-inexact',marker,marker+'\n  (void)feraiseexcept(FE_INEXACT);'),
                    ('omit-output','*integral = whole;','(void)whole;')]
        for name,old,new in changes:
            if source.count(old)!=1:raise RuntimeError('nonunique anchor '+str(width)+name)
            changed=text.replace(source,source.replace(old,new,1),1)
            plants.append((str(width)+'-'+name,text,changed))
    cc=shlex.split(env['PLANT_CC']);cxx=shlex.split(env['PLANT_CXX'])
    for name,old,new in plants:
        stage=work/name;stage.mkdir(exist_ok=True)
        source=stage/'fraction_split.c';source.write_text('#include <errno.h>\n#include <fenv.h>\n'+(text if old is None else new))
        shutil.copyfile('src/elementary/elem_common.h',stage/'elem_common.h')
        obj=stage/'fraction_split.o';binary=stage/'testSplit'
        run(cc+shlex.split(env['PLANT_CFLAGS'])+['-c',str(source),'-o',str(obj)],stage/'compile.log')
        run(cxx+['-o',str(binary),env['PLANT_TEST_OBJ'],str(obj)]+shlex.split(env['PLANT_LDFLAGS']),stage/'link.log')
        result=run([str(binary),'--gtest_brief=1'],stage/'test.log',(0,1))
        if result!=(0 if old is None else 1):raise RuntimeError('wrong plant outcome '+name)
        if old is not None and ('[  FAILED  ]' not in (stage/'test.log').read_text() or 'split mismatch' not in (stage/'test.log').read_text()):
            raise RuntimeError('plant did not fail a numerical/state assertion '+name)
        if old is not None:
            affected='Double' if name.startswith('64-') else 'Float'
            unaffected='Float' if affected=='Double' else 'Double'
            log=(stage/'test.log').read_text()
            if '[  FAILED  ] FractionSplit.'+affected+'PinnedAndCallerState' not in log or '[  FAILED  ] FractionSplit.'+unaffected+'PinnedAndCallerState' in log:
                raise RuntimeError('plant failure is not specific to its format '+name)
        print('  ok   split '+name+(' passes' if old is None else ' detected'),flush=True)
    print('split: %d source/state plants detected'%(len(plants)-1))


if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,KeyError,subprocess.TimeoutExpired) as error:
        print('split plants: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
