#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent directed MPFR/mpmath binary64 unary arctangent references."""
import argparse
from pathlib import Path
import sys
import struct
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import gmpy2
import mpmath
from mpmath import mp
from fractions import Fraction
from atan_reference import (SIGN,INF,QNAN,PIO2,SEED,COUNT,power,floor_log2,fraction,
                            round_word,flags,population,inverse_centers)
from gen_corpus_floattrig import rational,mpmath_fraction
from gen_corpus_float_scale import publish_set

def evaluate(raw,precision):
 x=fraction(raw);a=abs(x);bounds=[]
 for mode in [gmpy2.RoundDown,gmpy2.RoundUp]:
  with gmpy2.context(precision=precision,round=mode):
   arg=gmpy2.mpfr(struct.unpack('>d',raw.to_bytes(8,'big'))[0])
   if rational(arg)!=x:raise RuntimeError('atan independent input decoding differs')
   bounds.append(rational(gmpy2.atan(arg)))
 with mp.workprec(precision+40):independent=mpmath_fraction(mp.atan(mp.mpf(x.numerator)/x.denominator))
 low,high=bounds
 if abs(independent-(low+high)/2)>max(a,power(-1074))*power(-precision+8):raise RuntimeError('atan MPFR/mpmath disagreement')
 target=round_word(low,negative_zero=bool(raw&SIGN))
 if target!=round_word(high,negative_zero=bool(raw&SIGN)) or target!=round_word(independent,negative_zero=bool(raw&SIGN)):return None
 # The exact sign of atan(x)-x is known even when finite precision returns x.
 # Below2^-104 the absolute error is <half a minimum binary32 error subnormal.
 unit=power(max(floor_log2(a)-1,-1022)-52)
 if a<power(-104):
  if a**3/(3*unit)>=power(-150):raise RuntimeError('atan tiny signed-error bound failed')
  if target!=raw:raise RuntimeError('atan tiny target differs')
  return target,0 if raw&SIGN else 0x80000000
 if not low or not high or floor_log2(low)!=floor_log2(high):return None
 unit=power(max(floor_log2(low),-1022)-52);rounded=fraction(target)
 errors=[(v-rounded)/unit for v in [low,high,independent]]
 error=round_word(errors[0],32)
 if any(round_word(v,32)!=error for v in errors[1:]):return None
 return target,error

def answer(raw):
 a=raw&(SIGN-1)
 if a>INF:return QNAN,0
 if not a:return raw,0
 if a==INF:
  for precision in [1200,2400]:
   vals=[]
   for mode in [gmpy2.RoundDown,gmpy2.RoundUp]:
    with gmpy2.context(precision=precision,round=mode):vals.append(rational(gmpy2.const_pi()/2))
   with mp.workprec(precision+40):other=mpmath_fraction(mp.pi/2)
   if raw&SIGN:vals=[-vals[1],-vals[0]];other=-other
   result=round_word(vals[0]);unit=power(-52);err=round_word((vals[0]-fraction(result))/unit,32)
   if any(round_word(v)!=result or round_word((v-fraction(result))/unit,32)!=err for v in vals[1:]+[other]):continue
   return result,err
  raise RuntimeError('atan infinity constant failed certification')
 for precision in [1200,2400,4800]:
  result=evaluate(raw,precision)
  if result is not None:return result
 raise RuntimeError('uncertified atan target/error rounding boundary %016x'%raw)

def self_check():
 fixed=[(0,(0,0)),(SIGN,(SIGN,0)),(QNAN,(QNAN,0)),
        (INF|1,(QNAN,0)),(1,(1,0x80000000)),(SIGN|1,(SIGN|1,0)),
        (INF,(PIO2,0x3e8d3132)),(SIGN|INF,(SIGN|PIO2,0xbe8d3132)),
        (0x3ff0000000000000,(0x3fe921fb54442d18,0x3e8d3132)),
        (0xbff0000000000000,(0xbfe921fb54442d18,0xbe8d3132))]
 for raw,expected in fixed:
  if answer(raw)!=expected:raise RuntimeError('atan oracle fixed target/error differs')

def publication_self_check():
 import gen_corpus_float_scale as publisher
 names=['atan.corpus','atan-special.corpus'];texts={name:'new '+name+'\n' for name in names}
 def prepare(directory,existing):
  if existing:
   for index,name in enumerate(names):
    path=directory/name;path.write_bytes(('old '+name+'\n').encode());path.chmod(0o640 if not index else 0o644)
 def unchanged(directory,existing):
  for index,name in enumerate(names):
   path=directory/name
   if existing:
    if path.read_bytes()!=('old '+name+'\n').encode() or path.stat().st_mode&0o777!=(0o640 if not index else 0o644):raise RuntimeError('atan publisher rollback changed destination')
   elif path.exists():raise RuntimeError('atan publisher rollback created destination')
  if list(directory.glob('.float-scale-set.*')):raise RuntimeError('atan publisher leaked staging')
 for existing in [False,True]:
  with tempfile.TemporaryDirectory(prefix='atan-publish-positive-') as t:
   directory=Path(t);prepare(directory,existing);publish_set(directory,texts)
   for index,name in enumerate(names):
    path=directory/name;mode=(0o640 if not index else 0o644) if existing else 0o644
    if path.read_text()!=texts[name] or path.stat().st_mode&0o777!=mode:raise RuntimeError('atan publisher positive failed')
  for kind in ['stage-write','final-replace']:
   for position in [1,2]:
    with tempfile.TemporaryDirectory(prefix='atan-publish-fault-') as t:
     directory=Path(t);prepare(directory,existing);count=0
     original_replace=Path.replace;original_publish=publisher.publish
     def replace(source,target):
      nonlocal count
      target=Path(target)
      if target.parent==directory and target.name in names:
       count+=1
       if count==position:raise RuntimeError('injected atan final replacement')
      return original_replace(source,target)
     def write(path,text):
      if Path(path).name=='new%d'%(position-1):raise RuntimeError('injected atan staged write')
      return original_publish(path,text)
     try:
      if kind=='stage-write':publisher.publish=write
      else:Path.replace=replace
      try:publish_set(directory,texts)
      except RuntimeError as error:
       if not str(error).startswith('injected atan '):raise
      else:raise RuntimeError('atan publication failure escaped')
     finally:Path.replace=original_replace;publisher.publish=original_publish
     unchanged(directory,existing)
 print('atan publisher2positives/8ordinary-exception rollback controls pass; not crash-atomic',flush=True)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path);p.add_argument('--seed',type=int,default=SEED);p.add_argument('--count',type=int,default=COUNT);p.add_argument('--fresh',action='store_true');p.add_argument('--self-test',action='store_true');a=p.parse_args()
 if gmpy2.mpfr_version()!='MPFR 4.2.2' or gmpy2.version()!='2.3.2' or mpmath.__version__!='1.4.1':raise RuntimeError('atan oracle pin differs')
 self_check()
 if a.self_test:publication_self_check();return
 if a.out is None:p.error('--out is required')
 words=population(a.seed,a.count)
 # Independently check every Decimal-generated inverse-cell center.
 with mp.workprec(1240):
  for word,center in inverse_centers():
   midpoint=(fraction(word)+fraction(word+1))/2
   other=round_word(mpmath_fraction(mp.tan(mp.mpf(midpoint.numerator)/midpoint.denominator)))
   if center!=other:raise RuntimeError('atan inverse population independent disagreement')
 header='# Pinned oracle: atan MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1\n# function %s\n# seed %d count %d fresh %s entries %d\n'
 rows=[]
 for raw in words:
  result,error=answer(raw);rows.append((raw,result,error,flags(raw)))
 generic=[r for r in rows if not ((r[0]&(SIGN-1))>INF and not r[0]&(1<<51))]
 data={'atan-special.corpus':header%('atan64',a.seed,a.count,str(a.fresh).lower(),len(rows))+'# input nearest-target signed-error32 normalized-flags\n'+''.join('%016x %016x %08x %d\n'%r for r in rows),
       'atan.corpus':header%('atan',a.seed,a.count,str(a.fresh).lower(),len(generic))+'# binary64 input/result; signed binary32 error in true binary64 ULP\n'+''.join('%016x %016x %08x\n'%r[:3] for r in generic)}
 a.out.mkdir(parents=True,exist_ok=True);publish_set(a.out,data)
 print('atan: %d raw / %d generic certified rows'%(len(rows),len(generic)),flush=True)
if __name__=='__main__':main()
