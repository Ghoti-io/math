#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Actual exact-remainder source/state plants, C17/C++ and both formats."""
import os
from pathlib import Path
import shlex
import subprocess
import sys

def words(name):return shlex.split(os.environ[name])
def run(argv,label,expected=0):
 p=subprocess.run(argv,capture_output=True,text=True,timeout=90);(work/(label+'.log')).write_text(p.stdout+p.stderr)
 if expected is not None and p.returncode!=expected:raise RuntimeError(label+': unexpected status '+str(p.returncode))
 return p.returncode

def build(source,label):
 file=work/(label+'.c');obj=work/(label+'.o');file.write_text('#include <errno.h>\n#include <fenv.h>\n'+source)
 run(words('PLANT_CC')+words('PLANT_CFLAGS')+['-Isrc/elementary','-c',str(file),'-o',str(obj)],label+'-compile')
 raw=work/(label+'-raw');unit=work/(label+'-unit');archive=os.environ['PLANT_ARCHIVE']
 run(words('PLANT_CC')+words('PLANT_CFLAGS')+['tools/probe-ieee-remainder.c',str(obj),archive]+words('PLANT_RAW_LDFLAGS')+['-lm','-o',str(raw)],label+'-raw-link')
 run(words('PLANT_CXX')+[os.environ['PLANT_TEST_OBJ'],str(obj),archive]+words('PLANT_LDFLAGS')+['-o',str(unit)],label+'-unit-link')
 statuses=[]
 for width,name in [('64','Double'),('32','Float')]:
  statuses.append(run([str(raw),'tests/corpus',width],label+'-raw-'+width,None))
  statuses.append(run([str(unit),'--gtest_filter=IeeeRemainder.Pinned'+name+'CorpusAndCallerState','--gtest_brief=1'],label+'-unit-'+width,None))
 return tuple(statuses)

def main():
 source=Path('src/elementary/ieee_remainder.c').read_text()
 if build(source,'control')!=(0,0,0,0):raise RuntimeError('valid source control failed')
 faults=[
 ('initial-equality-zero-sign','q=(mx>=my);','q=(mx>my);',1),
 ('initial-direction','q=(mx>=my);','q=(mx<my);',1),
 ('initial-quotient','q=(mx>=my);','q=0;',1),
 ('initial-residual','r=mx-(q?my:0);','r=mx;',1),
 ('return-input','return sign|irq_pack(r,e,p,bias);','(void)r;(void)e;(void)sign;return xb;',1),
 ('ties-always','(q&1u)','1u',1),('ties-never','(q&1u)','0u',1),
 ('three-bit-quotient','&127u','&7u',3),
 ('quotient-sign','((xb^yb)&sign_bit)','(xb&sign_bit)',1),
 ('result-sign','return sign|irq_pack(r,e,p,bias);','(void)sign;return irq_pack(r,e,p,bias);',1),
 ('rounded-sign','r=my-r;q=(q+1u)&127u;sign^=sign_bit;','r=my-r;q=(q+1u)&127u;',1),
 ('small-sign','e=ex;q=1;sign^=sign_bit;','e=ex;q=1;',1),
 ('early-zero','if(gap>0)q=gap>=7?0:(q<<(unsigned)gap)&127u;','if(gap>0)q&=127u;',1),
 ('small-half','gap<-1||mx<=my','gap<-1||mx<my',1),
 ('small-unit','r=2*my-mx;e=ex;q=1;','r=2*my-mx;e=ey;q=1;',1),
 ('special-quotient','if(quo)*quo=0;','if(quo)*quo=17;',1),
 ('missing-quotient','if(quo)*quo=((xb^yb)&sign_bit)?-(int)q:(int)q;','if(quo)(void)q;',1),
 ('invalid-loss','(void)gmath_invalid();','(void)0;',2),
 ('second-signaling','||(ay>inf&&!(ay&quiet))','',1),
 ('quiet-invalid','if(ax>inf||ay>inf) {','if(ax>inf||ay>inf) {(void)gmath_invalid();',1),
 ('errno','uint64_t sign_bit=','errno=0;uint64_t sign_bit=',1),
 ('zero-errno','uint64_t sign_bit=','if(!errno){errno=732;}uint64_t sign_bit=',1),
 ('mode','uint64_t sign_bit=','(void)fesetround(FE_TONEAREST);uint64_t sign_bit=',1),
 ('mixed-incoming','uint64_t sign_bit=','if((fetestexcept(FE_INVALID|FE_DIVBYZERO)&(FE_INVALID|FE_DIVBYZERO))==(FE_INVALID|FE_DIVBYZERO)){(void)feclearexcept(FE_INVALID|FE_DIVBYZERO);}uint64_t sign_bit=',1),
 ('subnormal-underflow','return r>>(unsigned)(1-bias-e);','(void)feraiseexcept(FE_UNDERFLOW|FE_INEXACT);return r>>(unsigned)(1-bias-e);',1),
 ('chunk-overflow','gap>(int)(63u-p)?63u-p','gap>(int)(64u-p)?64u-p',1)]
 for name,old,new,count in faults:
  if source.count(old)!=count:raise RuntimeError('plant anchor count differs: '+name+' '+str(source.count(old)))
  if build(source.replace(old,new),name)!=(1,1,1,1):raise RuntimeError('source/state plant escaped C/C++ or format: '+name)
 for width,expected in [('52',(1,1,0,0)),('23',(0,0,1,1))]:
  changed=source.replace('return sign|irq_pack(r,e,p,bias);','return p=='+width+'?sign:(sign|irq_pack(r,e,p,bias));')
  if build(changed,'format-'+width)!=expected:raise RuntimeError('format-local defect/other-format control failed')
 probe='#include <limits.h>\n#include <stdint.h>\n#if (defined(__GNUC__)||defined(__clang__)) && ULLONG_MAX==UINT64_MAX && !defined(GMATH_IEEE_REMAINDER_PORTABLE_BITS)\nIRQ_INTRINSIC_ACTIVE\n#else\nIRQ_LOOP_ACTIVE\n#endif\n'
 pre=subprocess.run(words('PLANT_CC')+words('PLANT_CFLAGS')+['-E','-P','-x','c','-'],input=probe,capture_output=True,text=True,timeout=30)
 if pre.returncode or ('IRQ_LOOP_ACTIVE' in pre.stdout)==('IRQ_INTRINSIC_ACTIVE' in pre.stdout):raise RuntimeError('normalization compiler-branch probe failed')
 loop='IRQ_LOOP_ACTIVE' in pre.stdout
 if os.environ.get('PLANT_EXPECT_PORTABLE')=='1' and not loop:raise RuntimeError('requested portable normalization is not active')
 old='while(m<(UINT64_C(1)<<p))'
 if source.count(old)!=1:raise RuntimeError('loop-only mutation anchor')
 expected=(1,1,1,1) if loop else (0,0,0,0)
 if build(source.replace(old,'while(m<=(UINT64_C(1)<<p))'),'loop-only')!=expected:raise RuntimeError('loop-only real defect did not match actual compiler branch')
 print('IEEE remainder loop-only defect '+('detects on actual fallback' if loop else 'is inactive/equivalent under actual intrinsic branch'))
 print('IEEE remainder: '+str(len(faults))+' shared source/state plants detect in both formats/C/C++; two format-local defects retain passing other format')
if __name__=='__main__':
 work=Path(os.environ['PLANT_WORK']);work.mkdir(parents=True,exist_ok=True)
 try:main()
 except (OSError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('IEEE remainder plants: FAIL: '+str(e))
