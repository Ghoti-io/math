#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact nearest-even remainder: Fraction versus direct pinned MPFR APIs."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ieee_remainder_reference import answer,population,value,bits,dyadic,layout,widen,signaling,reference_hashes,self_check,coverage
import gmpy2
from gen_corpus_float_scale import publish_set

def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--seed',type=int,default=20261028);p.add_argument('--count',type=int,default=1000);p.add_argument('--fresh',action='store_true');a=p.parse_args()
 if gmpy2.version()!='2.3.2' or gmpy2.mpfr_version().split()[-1]!='4.2.2':raise RuntimeError('requires pinned gmpy2 2.3.2/MPFR4.2.2')
 if not 0<=a.seed<1<<64:raise RuntimeError("seed outside uint64")
 self_check()
 payloads={};manifest=[]
 for width,name in [(64,'remainder'),(32,'remainderf')]:
  fraction,bias,eb=layout(width);inf=((1<<eb)-1)<<fraction;sign=1<<(width-1);rows=[]
  for x,y in population(width,a.seed,a.count):
   result,quo,invalid=answer(x,y,width)
   ax=x&(sign-1);ay=y&(sign-1)
   if ax<inf and 0<ay<=inf:
    with gmpy2.context(precision=fraction+1,emin=-100000,emax=100000,round=gmpy2.RoundToNearest):
     xx,yy=gmpy2.mpfr(value(x,width)),gmpy2.mpfr(value(y,width))
     rr,qq=gmpy2.remquo(xx,yy);rr2=gmpy2.remainder(xx,yy)
     observed=bits(float(rr),width);other=bits(float(rr2),width)
     q=(abs(qq)&127)*(-1 if qq<0 else 1)
    if (observed,q)!=(result,quo) or other!=result:raise RuntimeError('Fraction/MPFR remainder/quotient disagreement: %x,%x'%(x,y))
   rows.append((x,y,result,quo,invalid))
  coverage(rows,width)
  header='# Pinned oracle: ieee_remainder MPFR 4.2.2 gmpy2 2.3.2\n# function %s\n# seed %d count %d fresh %s entries %d\n'%(name,a.seed,a.count,a.fresh,len(rows))
  payloads[name+'-special.corpus']=header+'# x y result quotient invalid\n'+''.join('%0*x %0*x %0*x %d %d\n'%(width//4,x,width//4,y,width//4,r,q,f) for x,y,r,q,f in rows)
  generic=[(widen(x,width),widen(y,width),widen(r,width),bits(float(q),64)) for x,y,r,q,f in rows if width==64 or not(signaling(x,width) or signaling(y,width))]
  for index,suffix in [(2,''),(3,'_quotient')]:payloads[name+suffix+'.corpus']=header.replace('entries %d'%len(rows),'entries %d'%len(generic))+''.join('%016x %016x %016x\n'%(x,y,v[index]) for v in generic for x,y in [v[:2]])
  raw,state,nearest,calls=reference_hashes(rows,width)
  manifest.append('ieeeraw %s %016x %d %d %016x %d\n'%(name,raw,len(rows),nearest,state,calls))
  print(name,len(rows),'raw',len(generic),'widened',flush=True)
 payloads['ieee_remainder-special.hash']=''.join(manifest)
 a.out.mkdir(parents=True,exist_ok=True);publish_set(a.out,payloads)
if __name__=='__main__':main()
