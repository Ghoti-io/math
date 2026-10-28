# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact rational positive-difference targets and complete reproducible populations.

No runtime limb arithmetic is reused. Targets quantize an exact Fraction to
its binade spacing, then independently encode the rounded dyadic value.
"""
from fractions import Fraction
import random
from nearby_reference import layout, rational, value, bits, feed
SEED=20261028
COUNT=2000

def power(e):return Fraction(2)**e

def floor_log2(q):
 e=q.numerator.bit_length()-q.denominator.bit_length()
 return e-1 if q<power(e) else e

def signaling(raw,width):
 p,bias,eb=layout(width);a=raw&((1<<(width-1))-1)
 return a>((1<<eb)-1)<<p and not a&(1<<(p-1))

def answer(x,y,width):
 p,bias,eb=layout(width);sign=1<<(width-1);inf=((1<<eb)-1)<<p;quiet=1<<(p-1)
 ax=x&(sign-1);ay=y&(sign-1)
 if ax>inf or ay>inf:return inf|quiet,int(signaling(x,width) or signaling(y,width))
 if value(x,width)<=value(y,width):return 0,0
 if ax==inf or ay==inf:return inf,0
 exact=rational(x,width)-rational(y,width)
 if exact<=0:raise RuntimeError('positive difference finite order certificate differs')
 e=floor_log2(exact);quantum=power(max(1-bias-p,e-p))
 integer=exact//quantum;residue=exact-integer*quantum
 integer+=int(2*residue>quantum or (2*residue==quantum and integer%2))
 rounded=integer*quantum
 if rounded>=power(bias+1):return inf,6
 if rounded<=0:raise RuntimeError('positive finite difference rounded to zero')
 if rounded<power(1-bias):
  raw=int(rounded/power(1-bias-p))
  if rounded!=exact:raise RuntimeError('tiny positive difference is not exact')
 else:
  e=floor_log2(rounded);raw=((e+bias)<<p)+int(rounded/power(e-p))-(1<<p)
 if rational(raw,width)!=rounded:raise RuntimeError('positive difference dyadic encoding differs')
 return raw,2 if rounded!=exact else 0

def population(width,seed,count):
 if not 0<=seed<=0xffffffff or not 0<=count<=50000:raise ValueError('positive difference seed/count outside bounds')
 p,bias,eb=layout(width);sign=1<<(width-1);hidden=1<<p;inf=((1<<eb)-1)<<p
 rng=random.Random(seed^width);pairs=set()
 def add(x,y):
  if not 0<=x<(1<<width) or not 0<=y<(1<<width):raise RuntimeError('positive difference population word exceeds width')
  pairs.add((x,y))
 special=[0,1,2,hidden-1,hidden,hidden+1,bias<<p,(bias<<p)-1,inf-1,inf,inf+1,inf+(hidden>>1),inf+hidden-1]
 special +=[v|sign for v in special]
 for x in special:
  for y in special:add(x,y)
 # Every normal exponent, both-sign subtraction, and opposite-sign addition.
 # Include the corrected predecessor seam cutoff and its adjacent gaps.
 for field in range(1,(1<<eb)-1):
  for gap in [p,p+1,p+2,p+3]:
   if field<=gap:continue
   for ma in [0,hidden-1]:
    for mb in [0,hidden-1]:
     x=(field<<p)|ma;y=((field-gap)<<p)|mb
     add(x,y);add(x,y|sign);add(y|sign,x|sign)
 # Exact tiny differences cover every subnormal leading exponent.
 for bit in range(p):
  for delta in [-1,0,1]:
   x=(1<<bit)+delta
   if x:
    add(x,0);add(x,1);add(0,x|sign);add(x,x|sign)
 # Each signaling payload bit in both positions and signs, with quiet NaNs,
 # infinities, zeros and finite arguments. Generic Float widening excludes it.
 for bit in range(p-1):
  for polarity in [0,sign]:
   x=polarity|inf|(1<<bit)
   for y in [0,bias<<p,inf,sign|inf,inf|(hidden>>1)]:add(x,y);add(y,x)
 # Every attainable normal rounding cut: half cells, parity and carry.
 one=bias<<p
 for gap in range(1,p+4):
  y=(bias-gap)<<p
  for dx in [0,1,2,hidden-1]:
   for dy in [-1,0,1]:
    add(one+dx,(y+dy)|sign);add(one+dx,y+dy)
 # Rounded-overflow midpoint neighbors, including values above maximum finite
 # which still round back to it, and exact unrepresentable sums.
 half=(bias+bias-p-1)<<p
 for delta in [-1,0,1]:add(inf-1,(half+delta)|sign)
 add((bias+bias)<<p,sign|((bias+bias)<<p))
 for _ in range(count):
  add(rng.getrandbits(width),rng.getrandbits(width))
  x=rng.randrange(1,inf-32);y=x+rng.randrange(1,32);add(y,x);add(x|sign,y|sign)
 return sorted(pairs)

def selected(x,y,width,index):
 p,bias,eb=layout(width);mask=(1<<(width-1))-1;inf=((1<<eb)-1)<<p
 return index%127==0 or (x&mask)>=inf or (y&mask)>=inf or (x&mask)==0 or (y&mask)==0

def hashes(rows,width):
 raw=ordered=14695981039346656037;calls=0
 for index,(x,y,result,flags) in enumerate(rows,1):
  raw=feed(feed(raw,result),flags)
  for mode in range(4):
   for subset in range(32 if selected(x,y,width,index) else 1):
    for error in [0,733]:
     for word in [result,flags,mode,subset,error]:ordered=feed(ordered,word)
     calls+=1
 return raw,ordered,calls

def payloads(seed=SEED,count=COUNT,fresh=False,oracle=None):
 out={};manifest=''
 for width,suffix in [(64,''),(32,'f')]:
  pairs=population(width,seed,count);rows=[]
  for x,y in pairs:
   result,flags=answer(x,y,width)
   if oracle:oracle(x,y,width,result,flags)
   rows.append((x,y,result,flags))
  header='# Pinned oracle: positive_difference MPFR 4.2.2 gmpy2 2.3.2\n# function fdim%d\n# seed %d count %d fresh %s entries %d\n'%(width,seed,count,str(fresh).lower(),len(rows))
  out['fdim%d-special.corpus'%width]=header+'# x y nearest-result flags\n'+''.join(('%0*x %0*x %0*x %d\n'%(width//4,x,width//4,y,width//4,r,f)) for x,y,r,f in rows)
  widened=[]
  for x,y,r,f in rows:
   if width==32 and (signaling(x,width) or signaling(y,width)):continue
   widened.append((x,y,r) if width==64 else tuple(bits(value(w,32),64) for w in [x,y,r]))
  out['fdim'+suffix+'.corpus']=header.replace('# function fdim%d'%width,'# function fdim'+suffix).replace('entries %d'%len(rows),'entries %d'%len(widened))+''.join('%016x %016x %016x\n'%row for row in widened)
  raw,state,calls=hashes(rows,width);manifest+='positive_difference%d raw %016x rows %d state %016x calls %d\n'%(width,raw,len(rows),state,calls)
 out['fdim-special.hash']=manifest
 return out
