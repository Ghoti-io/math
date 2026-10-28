#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact Fraction certification of emitted benchmark cases and real guard controls."""
import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
from positive_difference_reference import answer, layout, rational, signaling
RANGES=['ordinary','ordered-zero','cancellation','far-gap','subnormal','tie-neighbors','overflow','infinity','qNaN','sNaN']

def semantics(api,range_,index,x,y,result,flags):
 width=64 if api=='fdim' else 32;p,bias,eb=layout(width);sign=1<<(width-1);mask=sign-1;hidden=1<<p;inf=((1<<eb)-1)<<p
 a=x&mask;b=y&mask;fx=a>>p;fy=b>>p;normal=lambda field:0<field<(1<<eb)-1
 good=False
 if range_=='ordinary':good=normal(fx) and normal(fy) and -4<=fx-bias<=4 and -4<=fy-bias<=4
 elif range_=='ordered-zero':good=normal(fx) and normal(fy) and bool(x&sign)==bool(y&sign) and abs(a-b)==1 and rational(x,width)<=rational(y,width) and result==0 and flags==0
 elif range_=='cancellation':good=normal(fx) and normal(fy) and bool(x&sign)==bool(y&sign) and abs(a-b)==1 and -8<=max(fx,fy)-bias<=8 and rational(x,width)>rational(y,width) and result!=0 and flags==0
 elif range_=='far-gap':good=not(x&sign) and normal(fx) and normal(fy) and fx-fy in [p+1,p+2,p+3,p+4] and flags==2
 elif range_=='subnormal':good=not(x&sign) and 0<a<hidden and b<hidden and flags==0
 elif range_=='tie-neighbors':
  centers=[(bias-p-1-side)<<p for side in [0,1]]
  good=not(x&sign) and a in [bias<<p,(bias<<p)+1] and any(abs(b-center)<=1 and bool(y&sign)==(side==0) for side,center in enumerate(centers)) and flags==2
 elif range_=='overflow':
  half=(bias+bias-p-1)<<p;power=(bias+bias)<<p
  good=not(x&sign) and bool(y&sign) and ((a==inf-1 and abs(b-half)<=1) or (a==power and b==power)) and flags in [2,6]
 elif range_=='infinity':good=(x,y) in [(inf,inf),(inf,sign|inf),(sign|inf,0),(0,sign|inf)] and flags==0
 elif range_=='qNaN':good=(a>inf or b>inf) and not signaling(x,width) and not signaling(y,width) and flags==0
 elif range_=='sNaN':good=(signaling(x,width) or signaling(y,width)) and flags==1
 if not good:raise RuntimeError('fdim benchmark workload semantics differs '+repr((api,range_,index,hex(x),hex(y))))

def coverage(groups):
 for api in ['fdim','fdimf']:
  width=64 if api=='fdim' else 32;p,bias,eb=layout(width);sign=1<<(width-1);mask=sign-1;inf=((1<<eb)-1)<<p
  if {bool(x&sign) for x,y in groups[api,'cancellation']}!={False,True}:raise RuntimeError('fdim benchmark cancellation signs omitted')
  tie=groups[api,'tie-neighbors']
  for side in [0,1]:
   center=(bias-p-1-side)<<p
   offsets={(y&mask)-center for x,y in tie if abs((y&mask)-center)<=1}
   if offsets!={-1,0,1}:raise RuntimeError('fdim benchmark midpoint neighbors omitted')
  if {x&1 for x,y in tie}!={0,1}:raise RuntimeError('fdim benchmark tie parity omitted')
  for range_ in ['qNaN','sNaN']:
   positions={position for x,y in groups[api,range_] for position,word in enumerate([x,y]) if ((word&mask)>inf if range_=='qNaN' else signaling(word,width))}
   if positions!={0,1}:raise RuntimeError('fdim benchmark NaN operand coverage omitted')

def certify(binary,n=4096,pairs=401):
 r=subprocess.run([str(Path(binary).resolve()),'--emit-reference'],capture_output=True,text=True,timeout=120)
 lines=r.stdout.splitlines()
 if r.returncode or r.stderr or len(lines)!=1+20*n or lines[0]!='fdim.reference N%d pairs%d ranges10 APIs2'%(n,pairs):raise RuntimeError('fdim benchmark reference metadata/count differs')
 seen=set();groups={}
 for line in lines[1:]:
  m=re.fullmatch(r'fdim.reference (fdimf?) (\S+) ([0-9]+) ([0-9a-f]{16}) ([0-9a-f]{16}) ([0-9a-f]{16}) (0|1|2|6)',line)
  if not m:raise RuntimeError('fdim benchmark reference schema differs')
  api,range_,index,x,y,result,flags=m.groups();width=64 if api=='fdim' else 32;x,y,result=map(lambda w:int(w,16),[x,y,result]);key=(api,range_,int(index))
  if range_ not in RANGES or not 0<=int(index)<n or key in seen or max(x,y,result)>=(1<<width):raise RuntimeError('fdim benchmark reference coverage differs')
  semantics(api,range_,int(index),x,y,result,int(flags))
  groups.setdefault((api,range_),[]).append((x,y))
  if answer(x,y,width)!=(result,int(flags)):raise RuntimeError('fdim benchmark exact Fraction reference differs '+line)
  seen.add(key)
 expected={(api,range_,i) for api in ['fdim','fdimf'] for range_ in RANGES for i in range(n)}
 if seen!=expected:raise RuntimeError('fdim benchmark reference workload omission')
 coverage(groups)
 return len(seen)

def controls():
 e=os.environ;work=Path(e['BENCH_WORK']);work.mkdir(parents=True,exist_ok=True)
 source=Path('tools/bench-positive-difference.c').read_text().replace('#define N 4096','#define N 16',1).replace('#define PAIRS 401','#define PAIRS 3',1)
 variants=[('control',source,0,''),('checksum',source.replace('hash += call(api, i);','hash += call(api, i) + 1;',1),2,'timed checksum mismatch'),('disabled-checksum',source.replace('hash += call(api, i);','hash += call(api, i) + 1;',1).replace('if (hash != expected)','if (0 && hash != expected)',1),0,''),('classifier',source.replace('classes[i] = (observed & FE_INEXACT) ? 2u : 0u;','classes[i] = 0; (void)observed;',1),2,'own per-input value/state mismatch'),('range-semantic',source.replace('y = x - 1;','y = x;',1),0,'')]
 marker='  sink ^= hash;'
 for label,operation in [('timed-errno','errno=17;'),('timed-inexact','(void)feclearexcept(FE_INEXACT);'),('timed-mode','(void)fesetround(FE_DOWNWARD);')]:
  if source.count(marker)!=1:raise RuntimeError('benchmark state guard anchor absent')
  variants.append((label,source.replace(marker,marker+'\n  if(!host){'+operation+'}',1),2,'timed state mismatch'))
 macros=subprocess.run(shlex.split(e['BENCH_CC'])+shlex.split(e['BENCH_CFLAGS'])+['-dM','-E','tools/bench-positive-difference.c'],capture_output=True,text=True,timeout=60)
 if macros.returncode:raise RuntimeError('benchmark target macro query failed')
 if '#define __SSE__' in macros.stdout:
  operation='uint32_t control;__asm__ volatile("stmxcsr %0":"=m"(control)::"memory");control^=UINT32_C(0x8000);__asm__ volatile("ldmxcsr %0"::"m"(control):"memory");'
  variants.append(('timed-control',source.replace(marker,marker+'\n  if(!host){'+operation+'}',1),2,'timed state mismatch'))
 else:print('positive difference timed SSE control fault SKIPPED: actual target lacks SSE',flush=True)
 for label,text,status,diagnostic in variants:
  if label!='control' and text==source:raise RuntimeError('benchmark control anchor absent')
  file=work/(label+'.c');binary=work/label;file.write_text(text)
  cmd=shlex.split(e['BENCH_CC'])+shlex.split(e['BENCH_CFLAGS'])+[str(file),e['BENCH_ARCHIVE']]+shlex.split(e['BENCH_LDFLAGS'])+['-lm','-o',str(binary)]
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(work/(label+'-compile.log')).write_text(r.stdout+r.stderr)
  if r.returncode:raise RuntimeError('benchmark control compile failed '+label+r.stderr[-400:])
  if label=='control':certify(binary,16,3)
  elif label in ['classifier','range-semantic']:
   try:certify(binary,16,3)
   except RuntimeError as error:
    if not any(d in str(error) for d in ['exact Fraction reference differs','workload semantics differs']):raise
   else:raise RuntimeError('benchmark reference classifier fault escaped exact certificate')
  r=subprocess.run([str(binary.resolve())],capture_output=True,text=True,timeout=60);(work/(label+'.log')).write_text(r.stdout+r.stderr)
  if r.returncode!=status or (diagnostic and diagnostic not in r.stderr):raise RuntimeError('benchmark guard outcome differs '+label)
  print('positive difference reduced benchmark '+label+' passes',flush=True)
 print('positive difference reduced benchmark controls are accounting, not final timing evidence')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path);p.add_argument('--controls',action='store_true');a=p.parse_args()
 if a.controls:controls()
 if a.binary:print('positive difference benchmark%d actual emitted input/target/flag rows independently certified by Fraction'%certify(a.binary))
 if not a.controls and not a.binary:p.error('choose --binary or --controls')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:raise SystemExit('positive difference benchmark checks: FAIL: '+str(error))
