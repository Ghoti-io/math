#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Real wrapper defects must fail both C++ and C17, only in affected format."""
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys


def run(args,log,allowed=(0,)):
    with log.open('w') as out:r=subprocess.run(args,stdout=out,stderr=subprocess.STDOUT,timeout=120,check=False)
    if r.returncode not in allowed:raise RuntimeError('unexpected planted status '+str(args)+'\n'+log.read_text()[-3000:])
    return r.returncode


def main():
    env=os.environ;work=Path(env['PLANT_WORK']);work.mkdir(parents=True,exist_ok=True)
    original=Path('src/elementary/long_scale.c').read_text();plants=[('control',original,None,False)]
    markers={64:'double gmath_scalbln(double x, long n) {',32:'float gmath_scalblnf(float x, long n) {'}
    for width in (64,32):
        marker=markers[width];start=original.index(marker);end=original.index(markers[32]) if width==64 else len(original);body=original[start:end]
        cap='5000' if width==64 else '512';fn='gmath_scalbn' if width==64 else 'gmath_scalbnf'
        declaration='int k = n > '+cap+'L ? '+cap+' : (n < -'+cap+'L ? -'+cap+' : (int)n);'
        changes=[('positive-cap','? '+cap+' :','? 0 :',False),('negative-cap','? -'+cap+' :','? 0 :',False),
          ('reverse-exponent',fn+'(x, k)',fn+'(x, -k)',False),('ignore-exponent','return '+fn+'(x, k);','(void)k; return '+fn+'(x, 0);',False),
          ('narrow-short',declaration,'long m=(short)n; '+declaration.replace('n >','m >').replace('n <','m <').replace('(int)n','(int)m'),False),
          ('narrow-int64',declaration,'long m=(int)n; '+declaration.replace('n >','m >').replace('n <','m <').replace('(int)n','(int)m'),True),
          ('errno',marker,marker+'\n  errno=0;',False),('zero-errno',marker,marker+'\n  if(errno==0)errno=911;',False),
          ('mode',marker,marker+'\n  (void)fesetround(FE_TONEAREST);',False),('incoming',marker,marker+'\n  (void)feclearexcept(FE_ALL_EXCEPT);',False),
          ('mixed-incoming',marker,marker+'\n  if((fetestexcept(FE_ALL_EXCEPT)&(FE_INVALID|FE_DIVBYZERO))==(FE_INVALID|FE_DIVBYZERO)) (void)feclearexcept(FE_INVALID);',False),
          ('zero-sign','return '+fn+'(x, k);','return x==0 ? 0 : '+fn+'(x, k);',False),
          ('wrong-kernel','return '+fn+'(x, k);','return '+('(double)gmath_scalbnf((float)x, k);' if width==64 else '(float)gmath_scalbn((double)x, k);'),False)]
        ctype='double' if width==64 else 'float';wordtype='uint64_t' if width==64 else 'uint32_t'
        wordmacro='UINT64_C' if width==64 else 'UINT32_C';size='8' if width==64 else '4'
        absolute='0x7fffffffffffffff' if width==64 else '0x7fffffff';inf='0x7ff0000000000000' if width==64 else '0x7f800000'
        quiet='0x0008000000000000' if width==64 else '0x00400000';nan='0x7ff8000000000000' if width==64 else '0x7fc00000'
        decode='\n  '+wordtype+' b;memcpy(&b,&x,'+size+'); '
        is_nan='(b&'+wordmacro+'('+absolute+'))>'+wordmacro+'('+inf+')'
        qcond=is_nan+'&&(b&'+wordmacro+'('+quiet+'))'
        scond=is_nan+'&&!(b&'+wordmacro+'('+quiet+'))'
        for name,condition,payload,flags in [('quiet-payload',qcond,nan+'|1',''),('signaling-invalid',scond,nan,''),('quiet-invalid',qcond,None,'(void)feraiseexcept(FE_INVALID);')]:
            if payload is None:plant=decode+'if('+condition+'){'+flags+'}'
            else:plant=decode+'if('+condition+'){'+wordtype+' result='+wordmacro+'('+payload+');'+ctype+' y;memcpy(&y,&result,'+size+');return y;}'
            changes.append((name,marker,marker+plant,False))
        for name,old,new,long64 in changes:
            if body.count(old)!=1:raise RuntimeError('nonunique long scale anchor '+str(width)+name)
            plants.append((str(width)+'-'+name,original[:start]+body.replace(old,new,1)+original[end:],width,long64))
    cc=shlex.split(env['PLANT_CC']);flags=shlex.split(env['PLANT_CFLAGS']);cxx=shlex.split(env['PLANT_CXX']);ld=shlex.split(env['PLANT_LDFLAGS']);rawld=shlex.split(env['PLANT_RAW_LDFLAGS'])
    macros=subprocess.run(cc+flags+['-dM','-E','-x','c','/dev/null'],capture_output=True,text=True,check=True).stdout
    match=re.search(r'^#define __SIZEOF_LONG__ (4|8)$',macros,re.M)
    if not match:raise RuntimeError('compiler native-long width unavailable')
    longbits=int(match[1])*8;count=0
    for portable in (False,True):
        kernels=[]
        for source in ('scale','float_scale'):
            obj=work/((source+'-portable' if portable else source)+'.o')
            run(cc+flags+(['-DGMATH_FLOATSCALE_PORTABLE_BITS'] if portable else [])+['-c','src/elementary/'+source+'.c','-o',str(obj)],obj.with_suffix('.log'));kernels.append(str(obj))
        for name,text,width,long64 in plants:
            if long64 and longbits!=64:
                print('  SKIPPED equivalent long32 '+name,flush=True);continue
            stage=work/(('portable-' if portable else 'default-')+name);stage.mkdir(exist_ok=True)
            source=stage/'long_scale.c';source.write_text('#include <errno.h>\n#include <fenv.h>\n#include <stdint.h>\n#include <string.h>\n'+text)
            obj=stage/'long_scale.o';unit=stage/'unit';raw=stage/'raw'
            run(cc+flags+['-c',str(source),'-o',str(obj)],stage/'compile.log')
            run(cxx+['-o',str(unit),env['PLANT_TEST_OBJ'],str(obj)]+kernels+ld,stage/'unit-link.log')
            run(cc+flags+['tools/probe-long-scale.c',str(obj)]+kernels+rawld+['-lm','-o',str(raw)],stage/'raw-link.log')
            expected=0 if name=='control' else 1
            if run([str(unit),'--gtest_brief=1'],stage/'unit.log',(0,1))!=expected or run([str(raw)],stage/'raw.log',(0,1))!=expected:raise RuntimeError('long scale plant outcome '+name)
            if expected:
                u=(stage/'unit.log').read_text();r=(stage/'raw.log').read_text()
                for which,label in ((64,'Double'),(32,'Float')):
                    if ('[  FAILED  ] LongScale.'+label+'PinnedAndCallerState' in u)!=(which==width) or ('long scale mismatch width'+str(which) in r)!=(which==width):raise RuntimeError('wrong affected format '+name)
                count+=1
            print('  ok   long scale '+stage.name+(' passes' if not expected else ' detected')+' (unit and C17)',flush=True)
    print('long scale: %d native source/state plant executions detected; compiler long%d'%(count,longbits))

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,KeyError,subprocess.TimeoutExpired) as error:
        print('long scale plants: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
