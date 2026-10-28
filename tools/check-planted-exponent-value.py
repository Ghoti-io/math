#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Require format-specific failures from real exact-exponent source/state defects."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def run(args,log,allowed=(0,)):
    with log.open('w') as out:r=subprocess.run(args,stdout=out,stderr=subprocess.STDOUT,timeout=120,check=False)
    if r.returncode not in allowed:raise RuntimeError('unexpected process status '+str(args)+'\n'+log.read_text()[-3000:])
    return r.returncode


def main():
    env=os.environ;work=Path(env['PLANT_WORK']);work.mkdir(parents=True,exist_ok=True)
    original=Path('src/elementary/exponent_value.c').read_text();plants=[('control',original,None)]
    marker32='float gmath_logbf(float x) {';marker64='double gmath_logb(double x) {'
    for width,marker in ((64,marker64),(32,marker32)):
        start=original.index(marker);end=original.index(marker32) if width==64 else len(original)
        body=original[start:end]
        changes=[('snan','(void)gmath_invalid();','(void)0;'),
          ('snan-payload','(void)gmath_invalid();','(void)gmath_invalid(); return '+('gmath_double(word|UINT64_C(0x0008000000000000));' if width==64 else 'lb_float(word|UINT32_C(0x00400000));')),
          ('errno',marker,marker+'\n  errno=0;'),('zero-errno',marker,marker+'\n  if (errno==0) errno=7;'),
          ('mode',marker,marker+'\n  (void)fesetround(FE_TONEAREST);'),
          ('incoming',marker,marker+'\n  (void)feclearexcept(FE_ALL_EXCEPT);'),
          ('mixed-incoming',marker,marker+'\n  if ((fetestexcept(FE_ALL_EXCEPT)&(FE_INVALID|FE_DIVBYZERO))==(FE_INVALID|FE_DIVBYZERO)) (void)feclearexcept(FE_INVALID);'),
          ('spurious-ix',marker,marker+'\n  (void)feraiseexcept(FE_INEXACT);')]
        if width==64:
            changes += [('quiet-invalid','if (!(word & UINT64_C(0x0008000000000000)))','if ((word & UINT64_C(0x0008000000000000))) (void)gmath_invalid();\n    if (!(word & UINT64_C(0x0008000000000000)))'),('normal-bias','- 1023','- 1022'),('subnormal-bias','- 1074','- 1073'),
              ('subnormal-cut','a < UINT64_C(0x0010000000000000)','a < UINT64_C(0x0004000000000000)'),
              ('canonical','return gmath_double(GMATH_QNAN_BITS);','return gmath_double(GMATH_QNAN_BITS|1);'),
              ('infinity-sign','return gmath_double(GMATH_INF_BITS);','return x;'),
              ('zero-flags','return gmath_div_by_zero(GMATH_SIGN_BIT);','return gmath_double(GMATH_INF_BITS|GMATH_SIGN_BIT);'),
              ('zero-sign','return gmath_div_by_zero(GMATH_SIGN_BIT);','return gmath_div_by_zero(0);'),
              ('positive-zero','return exponent ? (double)exponent : gmath_double(0);','return exponent ? (double)exponent : -0.0;')]
        else:
            changes += [('mask-polarity','exponent != 0','exponent == 0'),('mask-zero','UINT32_C(0) - (uint32_t)(exponent != 0)','UINT32_C(0)'),('zero-conversion-ix','float converted = (float)exponent;','float converted = (float)exponent; if (exponent == 0) (void)feraiseexcept(FE_INEXACT);'),('quiet-invalid','if (!(word & UINT32_C(0x00400000)))','if ((word & UINT32_C(0x00400000))) (void)gmath_invalid();\n    if (!(word & UINT32_C(0x00400000)))'),('normal-bias','- 127','- 126'),('subnormal-bias','- 149','- 148'),
              ('subnormal-cut','a < UINT32_C(0x00800000)','a < UINT32_C(0x00200000)'),
              ('canonical','return lb_float(UINT32_C(0x7fc00000));','return lb_float(UINT32_C(0x7fc00001));'),
              ('infinity-sign','return lb_float(UINT32_C(0x7f800000));','return x;'),
              ('zero-flags','(void)gmath_div_by_zero(0);','(void)0;'),
              ('zero-sign','return lb_float(UINT32_C(0xff800000));','return lb_float(UINT32_C(0x7f800000));'),
              ('positive-zero','return lb_float(bits & mask);','return lb_float((bits & mask) | ((uint32_t)(exponent == 0) << 31));')]
        for name,old,new in changes:
            if body.count(old)!=1:raise RuntimeError('nonunique source anchor '+str(width)+name)
            plants.append((str(width)+'-'+name,original[:start]+body.replace(old,new,1)+original[end:],width))
    # Shared top-bit faults must fail both formats; forced-loop compilation
    # additionally exercises the fallback rather than trusting its presence.
    for name,old,new in [('builtin-count','return 63u - (unsigned)__builtin_clzll','return 62u - (unsigned)__builtin_clzll'),
                         ('portable-count','unsigned top = 0;','unsigned top = 1;')]:
        if original.count(old)!=1:raise RuntimeError('nonunique shared anchor '+name)
        plants.append((name,original.replace(old,new,1),0))
    cc=shlex.split(env['PLANT_CC']);cxx=shlex.split(env['PLANT_CXX'])
    for portable in (False,True):
        for name,text,width in plants:
            if (portable and name=='builtin-count') or (not portable and name=='portable-count'):continue
            stage=work/(('portable-' if portable else 'default-')+name);stage.mkdir(exist_ok=True)
            source=stage/'exponent_value.c';source.write_text('#include <errno.h>\n#include <fenv.h>\n'+text)
            shutil.copyfile('src/elementary/elem_common.h',stage/'elem_common.h')
            obj=stage/'exponent_value.o';binary=stage/'testExponent'
            run(cc+shlex.split(env['PLANT_CFLAGS'])+(['-DGMATH_LOGB_PORTABLE_BITS'] if portable else [])+['-c',str(source),'-o',str(obj)],stage/'compile.log')
            run(cxx+['-o',str(binary),env['PLANT_TEST_OBJ'],str(obj)]+shlex.split(env['PLANT_LDFLAGS']),stage/'link.log')
            status=run([str(binary),'--gtest_brief=1'],stage/'test.log',(0,1))
            if status!=(0 if name=='control' else 1):raise RuntimeError('plant outcome '+str(stage))
            if name!='control':
                log=(stage/'test.log').read_text()
                if 'exponent mismatch' not in log:raise RuntimeError('missing numerical/state failure '+name)
                for which,label in ((64,'Double'),(32,'Float')):
                    failed='[  FAILED  ] ExponentValue.'+label+'PinnedAndCallerState' in log
                    if failed!=(width==0 or width==which):raise RuntimeError('wrong affected format '+name)
            raw=stage/'probeExponent'
            run(cc+shlex.split(env['PLANT_CFLAGS'])+['tools/probe-exponent-value.c',str(obj),'-lm','-o',str(raw)],stage/'raw-compile.log')
            raw_status=run([str(raw)],stage/'raw.log',(0,1))
            if raw_status!=(0 if name=='control' else 1):raise RuntimeError('C17 plant outcome '+name)
            if name!='control':
                log=(stage/'raw.log').read_text()
                for which in (64,32):
                    failed='exponent mismatch width'+str(which) in log
                    if failed!=(width==0 or width==which):raise RuntimeError('C17 wrong affected format '+name)
            print('  ok   exponent '+stage.name+(' passes' if name=='control' else ' detected')+' (unit and C17)',flush=True)


if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,KeyError,subprocess.TimeoutExpired) as error:
        print('exponent plants: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
