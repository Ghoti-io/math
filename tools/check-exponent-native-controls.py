#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Optional native actual/wrong/aliased prior controls for all three C tools."""
import os
from pathlib import Path
import shlex
import subprocess
import sys
from adjacent_baseline import load,validate,write_header


def run(command,path,expected=0,diagnostic=None):
    with path.open('w') as out:r=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,timeout=120,check=False)
    if r.returncode!=expected or (diagnostic and diagnostic not in path.read_text()):
        raise RuntimeError('native control status/diagnostic wrong: '+str(command)+'\n'+path.read_text()[-3000:])


def main():
    env=os.environ;cc=shlex.split(env['NATIVE_CC']);flags=shlex.split(env['NATIVE_CFLAGS']);libflags=shlex.split(env['NATIVE_LIB_CFLAGS']);ld=shlex.split(env['NATIVE_LDFLAGS'])
    library=Path(env['NATIVE_LIBRARY']);reference=Path(env['NATIVE_REFERENCE']);metadata=load(env['NATIVE_METADATA'])
    validate(metadata,reference,env['NATIVE_LIB_CFLAGS'],env['NATIVE_CC'])
    work=Path(env['NATIVE_WORK']);work.mkdir(parents=True,exist_ok=True)
    header=work/'identity.h';write_header(header,metadata,'exponent')
    # Independent one-format defects ensure short-circuiting cannot hide Float.
    fixtures={'valid':reference}
    for name,body_d,body_f in (
        ('wrong-d','return 0;','return gmath_logbf(x);'),
        ('wrong-f','return gmath_logb(x);','return 0;'),
        ('nan-d','double y=gmath_logb(x); uint64_t u;memcpy(&u,&y,8);if((u&UINT64_C(0x7fffffffffffffff))>UINT64_C(0x7ff0000000000000))u^=1;memcpy(&y,&u,8);return y;','return gmath_logbf(x);'),
        ('nan-f','return gmath_logb(x);','float y=gmath_logbf(x);uint32_t u;memcpy(&u,&y,4);if((u&UINT32_C(0x7fffffff))>UINT32_C(0x7f800000))u^=1;memcpy(&y,&u,4);return y;'),
        ('flags-d','double y=gmath_logb(x);feraiseexcept(FE_INVALID);return y;','return gmath_logbf(x);'),
        ('flags-f','return gmath_logb(x);','float y=gmath_logbf(x);feraiseexcept(FE_INVALID);return y;'),
        ('errno-d','double y=gmath_logb(x);errno=991;return y;','return gmath_logbf(x);'),
        ('errno-f','return gmath_logb(x);','float y=gmath_logbf(x);errno=991;return y;'),
        ('mode-d','double y=gmath_logb(x);fesetround(FE_UPWARD);return y;','return gmath_logbf(x);'),
        ('mode-f','return gmath_logb(x);','float y=gmath_logbf(x);fesetround(FE_UPWARD);return y;')):
        source=work/(name+'.c');obj=work/(name+'.o')
        source.write_text('#include <stdint.h>\n#include <string.h>\n#include <fenv.h>\n#include <errno.h>\n#include <ghoti.io/math/basic.h>\ndouble gmath_exponent_prior_logb(double x){(void)x;'+body_d+'}\nfloat gmath_exponent_prior_logbf(float x){(void)x;'+body_f+'}\n')
        run(cc+libflags+['-c',str(source),'-o',str(obj)],work/(name+'-compile.log'))
        fixtures[name]=obj
    fixtures.update({'alias-d':reference,'alias-f':reference})
    tools=[('domain','tools/compare-exponent-domain.c',1,'implementation prior'),
           ('raw','tools/probe-exponent-value.c',1,'implementation prior'),
           ('bench','tools/bench-exponent-value.c',2,'bit/class guard failed')]
    count=0
    for kind,source,bad_status,bad_diagnostic in tools:
        for fixture,object_path in fixtures.items():
            # NaNs are outside the finite domain. Timing tools check raw NaN bits;
            # caller-state corruption is calibrated in domain/raw tools separately.
            if (kind=='domain' and fixture.startswith('nan-')) or (kind=='bench' and fixture.startswith(('flags-','errno-','mode-'))):continue
            baseline='BASELINE' if kind=='bench' else 'REFERENCE'
            d='gmath_logb' if fixture=='alias-d' else 'gmath_exponent_prior_logb'
            f='gmath_logbf' if fixture=='alias-f' else 'gmath_exponent_prior_logbf'
            binary=work/(kind+'-'+fixture)
            definitions=['-DGMATH_LOGB_'+baseline+'='+d,'-DGMATH_LOGBF_'+baseline+'='+f]
            run(cc+flags+['-include',str(header)]+definitions+[source,str(object_path),str(library)]+ld+['-lm','-o',str(binary)],work/(kind+'-'+fixture+'-compile.log'))
            status=0 if fixture=='valid' else (2 if kind=='bench' else 1) if fixture.startswith('alias-') else bad_status
            diagnostic=None if fixture=='valid' else 'aliases current function' if fixture.startswith('alias-') else bad_diagnostic
            arguments=[str(binary)]+([env['NATIVE_CORPUS']] if kind=='raw' else [])
            run(arguments,work/(kind+'-'+fixture+'.log'),status,diagnostic)
            print('  ok   exponent native '+kind+' '+fixture+(' passes' if fixture=='valid' else ' detected'),flush=True)
            count+=1
    print('exponent native controls: '+str(count)+' valid/individual-format numerical/NaN/state/alias controls pass')



if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,KeyError,ValueError,subprocess.TimeoutExpired) as error:
        print('exponent native controls: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
