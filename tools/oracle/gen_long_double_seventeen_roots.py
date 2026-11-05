#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Pinned MPFR/mpmath reference-only root/grid certificates.

No constants or approximations from this program enter runtime kernels.
Root proposals use mpmath; directed MPFR signs certify both adjacent dyadic
endpoints. Every retained value has an independent higher precision mpmath
cross-check. Existing output is never overwritten or repaired.
"""
import argparse,hashlib,json,os,platform,sys
from fractions import Fraction as F
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('root certificates require assertion-enabled Python')
import gmpy2 as g
import mpmath as mp
PIN='mpfr 4.2.2 gmpy2 2.3.2 mpmath 1.4.1 python 3.14.7'
PREC=4096
OTHER_PREC=8192
DISTANCE_BITS=1152
GRID_BITS=1074

def pow2(e):return F(1<<e)if e>=0 else F(1,1<<-e)
def exponent(x):
 x=abs(x);e=x.numerator.bit_length()-x.denominator.bit_length()
 return e-1 if x<pow2(e)else e

def exact_g(x):
 v=g.mpfr(g.mpq(x.numerator,x.denominator))
 assert F(*(int(z) for z in v.as_integer_ratio()))==x,'oracle input lost a bit'
 return v

def bounds(x):
 out=[]
 for rnd in (g.RoundDown,g.RoundUp):
  with g.context(precision=PREC,round=rnd,emin=-100000,emax=100000):
   v=g.lgamma(exact_g(x))[0]
   assert g.is_finite(v),'nonfinite oracle endpoint'
   out.append(F(*(int(z) for z in v.as_integer_ratio())))
 lo,hi=out;assert lo<=hi and (lo>0 or hi<0),'endpoint interval includes zero'
 with mp.workprec(OTHER_PREC):
  xx=mp.mpf(x.numerator)/x.denominator
  other=mp.re(mp.loggamma(xx))
  sign,man,ex,_=other._mpf_;value=pow2(ex)*(-int(man) if sign else int(man))
  pad=pow2(-5800)*max(F(1),abs(value))
  assert lo-pad<=value<=hi+pad,'independent mpmath disagreement'
 # Compact outward64-bit dyadic enclosure; compression never decides a sign.
 e=exponent(max(abs(lo),abs(hi)))-63;unit=pow2(e)
 a=lo//unit;b=-((-hi)//unit)
 assert a>0 or b<0
 return [format(a,'x'),format(b,'x'),e]

def root_distance(n,side):
 proposal_precision=4096
 while True:
  with mp.workprec(proposal_precision):
   initial=-mp.loggamma(n+1 if side=='left'else n)
   def fun(t):
    d=mp.exp(t)
    y=n+1-d if side=='left'else n+d
    return mp.log(mp.pi)-mp.log(mp.sin(mp.pi*d))-mp.loggamma(y)
   t=mp.findroot(fun,(initial-mp.mpf('0.125'),initial+mp.mpf('0.125')),solver='secant',verify=True)
   d=mp.exp(t);_,e=mp.frexp(d);e-=DISTANCE_BITS
   m=int(mp.floor(mp.ldexp(d,-e)))
   assert m.bit_length()==DISTANCE_BITS
  lo=m*pow2(e);hi=(m+1)*pow2(e)
  assert 0<lo<hi<F(1,2)
  pole=-n if side=='left'else 1-n;direction=1 if side=='left'else -1
  endpoints=[F(pole)+direction*d for d in (lo,hi)]
  bb=[bounds(x)for x in endpoints]
  # Positive near the pole, negative toward the half-integer minimum witness.
  if int(bb[0][0],16)>0 and int(bb[1][1],16)<0:break
  proposal_precision+=512
 xlo,xhi=sorted(endpoints);cell=xlo//pow2(-GRID_BITS)
 assert xhi//pow2(-GRID_BITS)==cell,'root bracket crosses universal local grid'
 grid=[]
 for index in (cell,cell+1):
  x=index*pow2(-GRID_BITS)
  grid.append(None if x.denominator==1 and x<=0 else bounds(x))
 return {'n':n,'side':side,'distance':[format(m,'x'),e],'bracket_lgamma':bb,'grid_lgamma':grid}

def derive():
 actual=f'{g.mpfr_version().lower()} gmpy2 {g.version()} mpmath {mp.__version__} python {platform.python_version()}'
 if actual!=PIN:raise SystemExit('required root oracle mismatch: '+actual)
 roots=[]
 for n in range(3,257):
  for side in ('left','right'):roots.append(root_distance(n,side))
  if n%16==0:print('root interval',n,'of256 certified',file=sys.stderr,flush=True)
 positive=[]
 for integer in (1,2):
  for direction in (-1,1):
   x=F(integer)+direction*pow2(-GRID_BITS)
   positive.append({'integer':integer,'direction':direction,'lgamma':bounds(x)})
 def magnitude(v):
  lo=int(v[0],16)*pow2(v[2]);hi=int(v[1],16)*pow2(v[2])
  return lo if lo>0 else -hi
 minimum=min([F(1,4),*(magnitude(v)for r in roots for v in r['grid_lgamma']if v is not None),*(magnitude(r['lgamma'])for r in positive)])
 G=0
 while minimum<=pow2(-G):G+=1
 assert G+2098+2<4100,'lgamma/Stirling relative precision reserve insufficient'
 return {'cancellation_region':'negative[-256,-2] excluding poles; positive[1/2,3]','schema':1,'oracle':PIN,'mpfr_precision':PREC,'mpmath_precision':OTHER_PREC,'mpmath_absolute_crosscheck_tolerance_exponent':-5800,'distance_bits':DISTANCE_BITS,'grid_bits':GRID_BITS,'roots':roots,'positive':positive,'minimum_nonzero_lgamma_exponent':-G,'cancellation_region_absolute_width_exponent':-4100,'dd_relative_population_gap_exponent':-2098,'relative_precision_reserve_bits':4100-G-2098}

def encoded(data):return (json.dumps(data,sort_keys=True,separators=(',',':'))+'\n').encode()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--verify',action='store_true');args=ap.parse_args()
 data=encoded(derive());sha=hashlib.sha256(data).hexdigest()
 if args.verify:
  if not args.out.exists()or args.out.read_bytes()!=data:raise SystemExit('root registry regeneration differs (no repair performed)')
 else:
  fd=os.open(args.out,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
  try:
   position=0
   while position<len(data):
    n=os.write(fd,data[position:])
    if n<=0:raise OSError('root registry short write')
    position+=n
   os.fsync(fd)
  finally:os.close(fd)
  if args.out.read_bytes()!=data:raise SystemExit('root registry short write verification failed')
 print('root registry:508 roots and4 positive grid points; SHA256',sha,flush=True)
if __name__=='__main__':main()
