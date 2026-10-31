# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent binary64 arctangent population and exact rational encoding.

No candidate source, fitted coefficients or implementation tables are read.
Inverse-cell inputs use a separate Decimal sine/cosine Taylor construction;
two precisions must agree on the selected input word.
"""
from decimal import Decimal, localcontext
from fractions import Fraction
import random
SIGN=1<<63
INF=0x7ff0000000000000
QNAN=0x7ff8000000000000
TINY=0x3e10000000000000
LARGE=0x4350000000000000
PIO2=0x3ff921fb54442d18
SEED=20261028
COUNT=2000

def power(e):return Fraction(2)**e

def floor_log2(q):
 q=abs(q);e=q.numerator.bit_length()-q.denominator.bit_length()
 return e-int(q<power(e))

def fraction(raw):
 a=raw&(SIGN-1);field,m=divmod(a,1<<52)
 if field==2047:raise ValueError('nonfinite atan rational')
 if field:m+=1<<52
 return (-1 if raw&SIGN else 1)*Fraction(m)*power((field or 1)-1075)

def round_word(q,width=64,negative_zero=False):
 p,bias,eb=(52,1023,11) if width==64 else (23,127,8)
 sign=1<<(width-1) if q<0 or (not q and negative_zero) else 0;q=abs(q)
 if not q:return sign
 e=max(floor_log2(q),1-bias);scaled=q/power(e-p)
 n,r=divmod(scaled.numerator,scaled.denominator)
 n+=int(2*r>scaled.denominator or (2*r==scaled.denominator and n%2))
 if n==1<<(p+1):n>>=1;e+=1
 if e>bias:return sign|(((1<<eb)-1)<<p)
 return sign|(n if n<1<<p else ((e+bias)<<p)|(n-(1<<p)))

def flags(raw):
 a=raw&(SIGN-1)
 if a>INF:return int(not a&(1<<51))
 return 0 if not a else 6 if a<1<<52 else 2

def strict(raw):
 a=raw&(SIGN-1)
 return a<TINY or a>=LARGE

def inverse_cell(midpoint,precision):
 with localcontext() as ctx:
  ctx.prec=precision
  x=Decimal(midpoint.numerator)/Decimal(midpoint.denominator);xx=x*x
  sine=st=x;cosine=ct=Decimal(1)
  for n in range(1,400):
   st=-st*xx/Decimal((2*n)*(2*n+1));ct=-ct*xx/Decimal((2*n-1)*(2*n))
   old_s,old_c=sine,cosine;sine+=st;cosine+=ct
   if sine==old_s and cosine==old_c:break
  else:raise RuntimeError('atan inverse Taylor population failed to converge')
  result=sine/cosine
  if result<=0:raise RuntimeError('atan inverse cell outside principal range')
  return round_word(Fraction(result))

def inverse_centers():
 centers=[]
 strata=[(power(-100),power(-30)),(Fraction(1,1024),Fraction(1,8)),
         (Fraction(1,8),Fraction(3,4)),(Fraction(4,5),Fraction(31,20))]
 for low,high in strata:
  selected=set()
  for i in range(128):
   word=round_word(low+(high-low)*Fraction(2*i+1,256))
   midpoint=(fraction(word)+fraction(word+1))/2
   a,b=inverse_cell(midpoint,160),inverse_cell(midpoint,200)
   if a!=b:raise RuntimeError('atan inverse population precision disagreement')
   centers.append((word,a));selected.add(a)
  if len(selected)<120:raise RuntimeError('atan inverse population strata collapsed')
 for word in range(PIO2-17,PIO2):
  midpoint=(fraction(word)+fraction(word+1))/2
  a,b=inverse_cell(midpoint,160),inverse_cell(midpoint,200)
  if a!=b:raise RuntimeError('atan endpoint inverse precision disagreement')
  centers.append((word,a))
 return centers

def population(seed,count):
 if not 0<=seed<1<<64 or not 0<=count<=50000:raise ValueError('atan seed/count outside bounds')
 rng=random.Random(seed);words={0,SIGN,INF,SIGN|INF,QNAN,QNAN|SIGN}
 def add(a):
  if 0<=a<INF:words.update((a,a|SIGN))
 for field in range(2047):
  for mantissa in [0,1,(1<<51)-1,(1<<52)-2,(1<<52)-1]:add((field<<52)|mantissa)
 for bit in range(52):
  for delta in [-1,0,1]:add((1<<bit)+delta)
 for center in [1<<52,TINY,0x3fc0000000000000,0x3ff0000000000000,LARGE]:
  for delta in range(-8,9):add(center+delta)
 for j in range(8,65):
  for q in [Fraction(j,64),Fraction(2*j+1,128)]:
   for v in [q,1/q]:
    center=round_word(v)
    for delta in [-2,-1,0,1,2]:add(center+delta)
 for _,center in inverse_centers():
  for delta in [-1,0,1]:add(center+delta)
 for bit in range(51):words.update((INF|(1<<bit),SIGN|INF|(1<<bit)))
 words.update((INF+(1<<51)-1,SIGN|INF+(1<<51)-1))
 words.update(rng.getrandbits(64) for _ in range(count))
 return sorted(words)


def selected(raw,index):
 a=raw&(SIGN-1)
 return (index%61==0 or a<1<<52 or a>=INF or
         TINY-8<=a<=TINY+8 or LARGE-8<=a<=LARGE+8)
