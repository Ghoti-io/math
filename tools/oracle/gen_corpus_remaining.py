#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""MPFR directed1200/2400 and independent mpmath; FMA exact Fraction/MPFR5000."""
import sys
if sys.flags.optimize:
 raise SystemExit('remaining-fifteen: optimized Python execution is unsupported')
import argparse,hashlib,sys,subprocess,tempfile
from pathlib import Path
from fractions import Fraction as F
import gmpy2 as g
from mpmath import mp
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from remaining_reference import SEED,NAMES,params,decode,encode,population,special

def rat(v):
 n,d=v.as_integer_ratio();return F(int(n),int(d))
def answer(row):
 name,w,mode,x,y,z=row;p,b,s,inf=params(w)
 sp=special(name,w,x,y,z,mode)
 if sp:
  if name.startswith('fma') and all((v&(s-1))<inf for v in (x,y,z)):
   with g.context(precision=5000,round=[g.RoundToNearest,g.RoundDown,g.RoundUp,g.RoundToZero][mode]):
    vals=[g.mpfr(decode(v,w).numerator)/decode(v,w).denominator for v in (x,y,z)];v=g.fma(*vals)
    exact=decode(x,w)*decode(y,w)+decode(z,w)
    assert rat(v)==exact,'MPFR5000 disagrees with exact FMA Fraction'
  return *sp,0,0
 xx=decode(x,w);yy=decode(y,w) if name=='powf' else None
 # Bound gigantic power exponents before asking either independent instrument.
 if name=='powf':
  ax=abs(xx)
  if ax==1:return encode(F(-1) if xx<0 and yy.numerator%2 else F(1),w),0,0,0,0
  with g.context(precision=1200):q=yy*g.log2(g.mpfr(ax.numerator)/ax.denominator)
  if abs(q)>2048:
   neg=xx<0 and yy.denominator==1 and yy.numerator%2
   return ((s if neg else 0)|(inf if q>0 else 0)),(10 if q>0 else 6),(10 if q>0 else 6),0,0
 fn={'erf':g.erf,'erfc':g.erfc,'tgamma':g.gamma,'lgamma':lambda x:g.lgamma(x)[0],'powf':lambda x:x**(g.mpfr(yy.numerator)/yy.denominator)}
 other={'erf':mp.erf,'erfc':mp.erfc,'tgamma':mp.gamma,'lgamma':lambda x:mp.log(abs(mp.gamma(x))),'powf':lambda x:mp.power(x,mp.mpf(yy.numerator)/yy.denominator)}
 kind=name[:-1] if w==32 and name!='powf' else name
 results=[]
 for prec in [1200,2400]:
  bounds=[]
  for rnd in [g.RoundDown,g.RoundUp]:
   with g.context(precision=prec,round=rnd):bounds.append(rat(fn[kind](g.mpfr(xx.numerator)/xx.denominator)))
  with mp.workprec(prec+80):
   v=other[kind](mp.mpf(xx.numerator)/xx.denominator);sg,m,e,_=v._mpf_;mval=F((-1 if sg else 1)*int(m))*F(2)**int(e)
  targets=[encode(v,w) for v in bounds+[mval]]
  assert len(set(targets))==1,('oracle rounding disagreement',row,targets)
  target=targets[0];mag=target&(s-1)
  if mag==inf:results.append((target,10,10,0,0));continue
  unit=F(2)**max((mag>>p)-b-p,1-b-p)
  assert bounds[0]-unit*F(2)**-100<=mval<=bounds[1]+unit*F(2)**-100,('independent disagreement',row)
  errors=[(v-decode(target,w))/unit for v in bounds]
  low=(errors[0]*(1<<30)).__floor__();high=(errors[1]*(1<<30)).__ceil__()
  flags=2|(4 if mag<1<<p else 0)
  if name=='powf':
   exact=bounds[0]==bounds[1]==decode(target,w)
   required=flags if not exact else 0;allowed=flags if not exact else 2
  else:required=allowed=flags
  results.append((target,required,allowed,low,high))
 assert results[0]==results[1],('two-precision disagreement',row)
 return results[0]
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--seed',type=int,default=SEED);p.add_argument('--count',type=int,default=128);a=p.parse_args()
 assert 0<=a.seed<1<<64 and 0<=a.count<=2048
 lines=['# remaining-fifteen-v1 seed=%d count=%d MPFR-directed1200/2400 mpmath Fraction-FMA/MPFR5000'%(a.seed,a.count),'# name width mode x y z target required allowed residual-low residual-high; residual scale=2^30 ULP']
 for row in population(a.seed,a.count):
  t,req,allow,lo,hi=answer(row);name,w,mode,x,y,z=row
  lines.append('%s %d %d %016x %016x %016x %016x %d %d %d %d'%(name,w,mode,x,y,z,t,req,allow,lo,hi))
 data=('\n'.join(lines)+'\n').encode();a.out.mkdir(parents=True,exist_ok=True);
 with tempfile.TemporaryDirectory(prefix='remaining-seams-',dir=a.out) as temp:
  selected=Path(temp)/'remaining_seams.py'
  subprocess.run([sys.executable,str(Path(__file__).with_name('select_remaining_seams.py')),'--out',str(selected)],check=True)
  assert selected.read_bytes()==(Path(__file__).resolve().parents[1]/'remaining_seams.py').read_bytes(),'selected seams differ'
 (a.out/'remaining-fifteen.corpus').write_bytes(data);(a.out/'remaining-fifteen.sha256').write_text(hashlib.sha256(data).hexdigest()+'  remaining-fifteen.corpus\n');print('remaining-fifteen independent rows',len(lines)-2)
if __name__=='__main__':main()
