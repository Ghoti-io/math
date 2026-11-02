# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Raw populations and exact Fraction FMA/adjacency/Float-power semantics."""
from fractions import Fraction as F
import random
from log1p_expm1_reference import decode,encode
from remaining_seams import SEAMS,MIDPOINTS,POW_MIDPOINTS
SEED=20261109
NAMES=['erf','erfc','tgamma','lgamma','erff','erfcf','tgammaf','lgammaf','powf','fma','fmaf','nexttoward','nexttowardf','nan','nanf']
def params(w):
 p,b=(52,1023) if w==64 else (23,127);return p,b,1<<(w-1),(2*b+1)<<p

def base_population(seed=SEED,count=128):
 for w in (64,32):
  p,b,s,inf=params(w);one=b<<p
  words={0,s,inf,s|inf,inf|1,s|inf|1,inf|(1<<(p-1)),s|inf|(1<<(p-1)),1,s|1,(1<<p)-1,1<<p,inf-1,s|(inf-1)}
  for v in [F(1),F(2),F(4),F(7),F(28),F(64),F(172),F(256),F(1,2),F(3,2),F(5,2),F(27),F(9),F(13),F(171),F(143,10),F(1461632144968362,10**15),F(1,1<<60),F(1,1<<26)]:
   c=encode(v,w)
   for d in [-2,-1,0,1,2]:
    if 0<c+d<inf:words.update([c+d,s|(c+d)])
  for center in SEAMS[w]:
   for delta in range(-4,5):
    if 0<=center+delta<1<<w:words.add(center+delta)
  for bit in range(p):
   for sg in [0,s]:words.update([sg|inf|(1<<bit),sg|inf|(1<<(p-1))|(1<<bit)])
  rng=random.Random(seed+w)
  for _ in range(count):
   words.add(rng.randrange(inf)|rng.choice([0,s]));words.add(encode(F(rng.randrange(-300000,300001),1024),w))
  for word in sorted(words):
   for base in ['erf','erfc','tgamma','lgamma']:yield base+('f' if w==32 else ''),w,0,word,0,0
  # Exact cancellation, tie, minnormal, extreme alignment, huge canceled products.
  minimum=1<<p;maximum=inf-1;two=(b+1)<<p;half=(b-1)<<p
  triples=[(0,inf,inf|(1<<(p-1))),(inf,0,0),(inf,one,s|inf),(maximum,two,s|maximum),(maximum,maximum,s|inf),
   (minimum,one-2,s|minimum),(minimum,one-1,s|minimum),(minimum,one,s|minimum),(1,half,0),(1,half,1),
   (maximum,one,encode(F(2)**(b-p-2),w)),(maximum,one,encode(F(2)**(b-p-1),w)),
   (one,one,s|one),(s,one,s),(one,one,1),(one,one,s|1),
   (one+1,one-1,s|one),(minimum,minimum,maximum)]
  specials=[0,s,one,s|one,inf,s|inf,inf|1,inf|(1<<(p-1))]
  for bit in range(p):
   for sg in [0,s]:
    for payload in [1<<bit,(1<<(p-1))|(1<<bit)]:
     n=sg|inf|payload;triples.extend([(n,one,one),(one,n,one),(one,one,n)])
  triples += [(a,c,d) for a in specials for c in specials for d in [0,inf,s|inf,inf|(1<<(p-1))]]
  triples += [tuple(rng.getrandbits(w) for _ in range(3)) for _ in range(count)]
  for triple in triples:
   for mode in range(4):yield 'fma'+('f' if w==32 else ''),w,mode,*triple
  directions=[0,1<<63,0x3ff0000000000000,0xbff0000000000000,0x7ff0000000000000,0xfff0000000000000,0x7ff0000000000001,0x7ff8000000000000]
  for word in sorted(words):
   for direction in [directions[rng.randrange(len(directions))]]:yield 'nexttoward'+('f' if w==32 else ''),w,0,word,direction,0
  for bit in range(52):
   for sg in [0,1<<63]:
    for payload in [1<<bit,(1<<51)|(1<<bit)]:yield 'nexttoward'+('f' if w==32 else ''),w,0,one,sg|0x7ff0000000000000|payload,0
  for tag in range(4):yield 'nan'+('f' if w==32 else ''),w,0,tag,0,0
 p,b,s,inf=params(32);one=b<<p
 vals=[0,s,1,s|1,one,s|one,one-1,one+1,(b+1)<<p,s|((b+1)<<p),inf,s|inf,inf|1,inf|(1<<(p-1)),encode(F(3),32),encode(F(5),32),encode(F(1,2),32)]
 for a in vals:
  for c in vals:yield 'powf',32,0,a,c,0
 for bit in range(p):
  for sg in [0,s]:
   for payload in [1<<bit,(1<<(p-1))|(1<<bit)]:
    n=sg|inf|payload
    for a,c in [(n,one),(one,n),(n,0),(0,n)]:yield 'powf',32,0,a,c,0
 rng=random.Random(seed)
 for _ in range(count*2):yield 'powf',32,0,rng.getrandbits(32),rng.getrandbits(32),0

def population(seed=SEED,count=128):
 # Append only: every prior row/answer/order remains unchanged.
 seen=set()
 for row in base_population(seed,count):seen.add(row);yield row
 for width,name,center in MIDPOINTS:
  for delta in [-1,0,1]:
   row=(name+('f' if width==32 else ''),width,0,center+delta,0,0)
   if row not in seen:seen.add(row);yield row
 for x,y in POW_MIDPOINTS:
  for dx in [-1,0,1]:
   for dy in [-1,0,1]:
    row=('powf',32,0,x+dx,y+dy,0)
    if row not in seen:seen.add(row);yield row
 # Explicit exact-subnormal powers cover exponent/parity state branches.
 for x,y in [(F(2)**-64,F(2)),(F(2)**127,F(-1)),(F(2)**-70,F(2)),(F(1,2),F(149)),(-F(1,2),F(149)),(-F(2)**-49,F(3)),(F(2)**-148,F(1,2)),(3*F(2)**-70,F(2)),(9*F(2)**-96,F(3,2))]:
  row=('powf',32,0,encode(x,32),encode(y,32),0)
  if row not in seen:seen.add(row);yield row

def fma_answer(w,mode,x,y,z):
 p,b,s,inf=params(w);ax=x&(s-1);ay=y&(s-1);az=z&(s-1);q=inf|(1<<(p-1));ps=(x^y)&s
 invalid=(ax==inf and not ay) or (ay==inf and not ax) or any(a>inf and not(v&(1<<(p-1))) for a,v in [(ax,x),(ay,y),(az,z)])
 if invalid:return q,1
 if max(ax,ay,az)>inf:return q,0
 if ax==inf or ay==inf:
  return (q,1) if az==inf and (z&s)!=ps else (inf|ps,0)
 if az==inf:return z,0
 value=decode(x,w)*decode(y,w)+decode(z,w)
 if not value:
  same=ps==(z&s);return (ps if same else s if mode==1 else 0),0
 neg=value<0;a=abs(value);e=a.numerator.bit_length()-a.denominator.bit_length()
 if a<F(2)**e:e-=1
 unit=F(2)**max(e-p,1-b-p);v=a/unit;n=v.numerator//v.denominator;rem=v-n
 if mode==0:n+=int(rem>F(1,2) or (rem==F(1,2) and n%2))
 elif (mode==1 and neg) or (mode==2 and not neg):n+=int(bool(rem))
 rounded=n*unit;out=encode(-rounded if neg else rounded,w)|(s if neg else 0)
 if rounded>=F(2)**(b+1):return ((s if neg else 0)|(inf-1 if mode==3 or mode==1 and not neg or mode==2 and neg else inf)),10
 flags=2 if rem else 0
 if flags and (out&(s-1))<1<<p:flags|=4
 return out,flags

def special(name,w,x,y=0,z=0,mode=0):
 p,b,s,inf=params(w);a=x&(s-1);one=b<<p;nan=inf|(1<<(p-1));neg=bool(x&s)
 if name.startswith('nan'):return nan,0,0
 if name.startswith('fma'):
  out,flags=fma_answer(w,mode,x,y,z);return out,flags,flags
 if name.startswith('nexttoward'):
  ay=y&((1<<63)-1);iy=0x7ff0000000000000
  if a>inf or ay>iy:
   flags=int(a>inf and not(x&(1<<(p-1))) or ay>iy and not(y&(1<<51)));return nan,flags,flags
  if a==inf:cmp=0 if ay==iy and neg==bool(y>>63) else -1 if neg else 1
  elif ay==iy:cmp=1 if y>>63 else -1
  else:
   xx=decode(x,w);yy=decode(y,64);cmp=(xx>yy)-(xx<yy)
  if not cmp:return (x if a else s if y>>63 else 0),0,0
  if not a:return (s if cmp>0 else 0)|1,6,6
  out=x+(1 if (cmp>0 if neg else cmp<0) else -1);mag=out&(s-1);flags=10 if mag==inf else 6 if mag<1<<p else 0
  return out,flags,flags
 if name=='powf':
  ay=y&(s-1);ny=bool(y&s)
  if a>inf and not(x&(1<<(p-1))) or ay>inf and not(y&(1<<(p-1))):return nan,1,1
  if not ay or x==one or a==one and ay==inf:return one,0,0
  if a>inf or ay>inf:return nan,0,0
  if ay==inf:return (inf if (a>one)==(not ny) else 0) if a!=one else one,(16 if not a and ny else 0),(16 if not a and ny else 0)
  yy=decode(y,w);integer=yy.denominator==1;odd=integer and bool(yy.numerator%2);sg=s if neg and odd else 0
  if not a:return (inf|sg,16,16) if ny else (sg,0,0)
  if a==inf:return (sg if ny else inf|sg),0,0
  if neg and not integer:return nan,1,1
  return None
 if a>inf:return nan,int(not(x&(1<<(p-1)))),int(not(x&(1<<(p-1))))
 kind=name[:-1] if w==32 else name
 if a==inf:
  if kind=='erf':return one|(x&s),0,0
  if kind=='erfc':return ((b+1)<<p if neg else 0),0,0
  if kind=='lgamma' or not neg:return inf,0,0
  return nan,1,1
 if not a:
  if kind=='erf':return x,0,0
  if kind=='erfc':return one,0,0
  return inf|(x&s if kind=='tgamma' else 0),16,16
 xx=decode(x,w)
 if kind in ('tgamma','lgamma'):
  if neg and xx.denominator==1:return (nan,1,1) if kind=='tgamma' else (inf,16,16)
  if xx in (1,2):return (one if kind=='tgamma' else 0),0,0
  if kind=='tgamma' and xx>=172:return inf,10,10
  if kind=='tgamma' and xx<=-256:return (s if (-xx).__floor__()%2==0 else 0),6,6
 if kind=='erf' and abs(xx)>=7:return one|(x&s),2,2
 if kind=='erfc' and abs(xx)>=28:return (((b+1)<<p),2,2) if neg else (0,6,6)
 return None
