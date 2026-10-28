# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent unbounded rational quotient/cell certificates, never runtime code."""
from fractions import Fraction
import random
import struct

def layout(width):return (52,1023,11) if width==64 else (23,127,8)
def value(raw,width):return struct.unpack('>d' if width==64 else '>f',raw.to_bytes(width//8,'big'))[0]
def bits(x,width):return int.from_bytes(struct.pack('>d' if width==64 else '>f',x),'big')
def dyadic(raw,width):
 p,bias,eb=layout(width);sign=raw>>(width-1);a=raw&((1<<(width-1))-1);field,m=divmod(a,1<<p)
 if field==(1<<eb)-1:raise RuntimeError('nonfinite rational operand')
 if field:m+=1<<p
 exponent=(field or 1)-bias-p
 return (-1 if sign else 1)*Fraction(m)*(Fraction(2)**exponent)
def answer(x,y,width):
 p,bias,eb=layout(width);sign=1<<(width-1);inf=((1<<eb)-1)<<p;quiet=1<<(p-1);a=x&(sign-1);b=y&(sign-1)
 invalid=int((a>inf and not a&quiet) or (b>inf and not b&quiet))
 if a>inf or b>inf:return inf|quiet,0,invalid
 if a==inf or not b:return inf|quiet,0,1
 if not a or b==inf:return x,0,0
 xx,yy=dyadic(x,width),dyadic(y,width);ratio=abs(xx/yy)
 q,r=divmod(ratio.numerator,ratio.denominator)
 if 2*r>ratio.denominator or (2*r==ratio.denominator and q&1):q+=1
 n=-q if (x^y)&sign else q;remainder=xx-n*yy
 output=bits(float(remainder),width) if remainder else x&sign
 if dyadic(output,width)!=remainder:raise RuntimeError('exact remainder not representable')
 fragment=(q&127)*(-1 if (x^y)&sign else 1)
 return output,fragment,0

def widen(raw,width):
 p,bias,eb=layout(width);a=raw&((1<<(width-1))-1);inf=((1<<eb)-1)<<p
 if a>inf:return 0x7ff8000000000000
 return bits(value(raw,width),64)
def signaling(raw,width):
 p,bias,eb=layout(width);a=raw&((1<<(width-1))-1)
 return a>((1<<eb)-1)<<p and not a&(1<<(p-1))
def population(width,seed,count):
 if not 0<=count<=50000:raise RuntimeError('count outside0..50000')
 p,bias,eb=layout(width);sign=1<<(width-1);inf=((1<<eb)-1)<<p;maxfinite=inf-1;hidden=1<<p
 pairs=set()
 def add(a,b):
  for sx in (0,sign):
   for sy in (0,sign):pairs.add((a|sx,b|sy))
 specials=[0,1,hidden-1,hidden,hidden+1,maxfinite,inf,inf|(1<<(p-1)),inf|(1<<(p-1))|1,inf|((1<<p)-1),inf|1,inf|((1<<(p-1))-1)]+[inf|(1<<k) for k in range(p-1)]
 for a in specials:
  for b in specials:add(a,b)
 # Every representable binade, nearest half neighbors, and adjacent divisor.
 for e in range(1-bias-p,bias+1):
  power=(e+bias)<<p if e>=1-bias else 1<<(e-(1-bias-p))
  for d in (-1,0,1):
   if 0<power+d<inf:
    add(power+d,power);add(power,power+d)
  if power<=maxfinite>>1:add(power,power<<1) if power<hidden else None
  if e>1-bias-p:
   half=((e-1+bias)<<p) if e-1>=1-bias else 1<<(e-1-(1-bias-p))
   for d in (-1,0,1):
    if 0<half+d<inf:add(half+d,power)
 # Exact small quotient halves and wrap transitions, varied dyadic divisors.
 for n in list(range(260))+[511,512,1023,1024,4095]:
  for divisor in [1.0,3.0,2.0**(1-bias),2.0**(-p),2.0**(bias-20)]:
   x=(n+0.5)*divisor
   try:a=bits(x,width);b=bits(divisor,width)
   except OverflowError:continue
   if a>=inf:continue
   for d in (-1,0,1):
    if 0<a+d<inf:add(a+d,b)
 # Early exact residual, arbitrary quotient low bits, long/chunk seams.
 for gap in [0,1,2,6,7,8,10,11,12,39,40,41,p-1,p,p+1,p+6,p+7,100,200,bias]:
  for m in [1,3,5,127]:
   try:a=bits(float(m)*2.0**gap,width);b=bits(float(m),width)
   except OverflowError:continue
   if a<inf:add(a,b)
 for a in [1,hidden-1,hidden,hidden+1,maxfinite-1,maxfinite]:
  for b in [1,2,3,hidden-1,hidden,hidden+1,maxfinite]:add(a,b)
 rng=random.Random(seed^(width<<32))
 for _ in range(count):pairs.add((rng.getrandbits(width),rng.getrandbits(width)))
 # Odd unequal normalized significands cannot divide mx*2^gap exactly.
 for gap in [0,1,6,7,10,11,12,13,22,23,24,39,40,41,80,100,200,2*bias-1]:
  if gap>2*bias-1:continue
  for mx in [hidden+1,hidden+3,2*hidden-1]:
   for my in [hidden+5,hidden+7,2*hidden-3]:
    add(((gap+1)<<p)|(mx-hidden),hidden|(my-hidden))
 for x,y,r,q,invalid in known_cases(width):pairs.add((x,y))
 return sorted(pairs)

FNV_BASIS=14695981039346656037
MASK64=(1<<64)-1
def fnv(hash,word):
 for byte in int(word&MASK64).to_bytes(8,'little'):hash=((hash^byte)*1099511628211)&MASK64
 return hash
def state_selections(index,x,y,width):
 p,bias,eb=layout(width);mask=(1<<(width-1))-1;inf=((1<<eb)-1)<<p;a=x&mask;b=y&mask
 if index%257==0:return range(32)
 if index%31==0 or ((a>=inf or b>=inf) and (a&((1<<p)-1)==1 or b<=1)):return (0,24,3)
 return ()
def reference_hashes(rows,width):
 raw=state=FNV_BASIS;calls=0
 for index,(x,y,r,q,invalid) in enumerate(rows):
  for word in (x,y,r,q,invalid):raw=fnv(raw,word)
  for mode in range(4):
   for subset in state_selections(index,x,y,width):
    for error in (0,733):
     for kind in range(3):
      for word in (index,mode,subset,error,kind,r,q if kind==1 else 0):state=fnv(state,word)
      calls+=1
 return raw,state,len(rows)*3,calls

def known_cases(width):
 # Exact literal certificates, independently chosen from the constructor.
 result=[]
 for x,y,r,q in [(0.5,1.,0.5,0),(1.5,1.,-0.5,2),(2.5,1.,0.5,2),(8.,1.,0.,8),(9.,-2.,1.,-4),(-128.,1.,-0.,0),(127.5,1.,-0.5,0)]:result.append((bits(x,width),bits(y,width),bits(r,width),q,0))
 p,bias,eb=layout(width);inf=((1<<eb)-1)<<p;nan=inf|(1<<(p-1));sign=1<<(width-1)
 return result+[(3,2,sign|1,2,0),(bits(1.,width),0,nan,0,1),(nan|3,0,nan,0,0),(inf|1,nan,nan,0,1)]

def self_check():
 for width in (64,32):
  for x,y,r,q,f in known_cases(width):
   if answer(x,y,width)!=(r,q,f):raise RuntimeError('fixed reference contract control failed')
 for raw,expected in [(0,0),(0x80000000,0x8000000000000000),(1,0x36a0000000000000),(0x007fffff,0x380fffffc0000000),(0x00800000,0x3810000000000000),(0x3f800000,0x3ff0000000000000),(0x7f7fffff,0x47efffffe0000000),(0x7f800000,0x7ff0000000000000),(0xff800000,0xfff0000000000000),(0x7fc00003,0x7ff8000000000000),(0xffc00003,0x7ff8000000000000)]:
  if widen(raw,32)!=expected:raise RuntimeError('fixed widening control failed')
 for raw,expected in [(0,False),(0x7f800000,False),(0x7fc00000,False),(0xffc00003,False),(0x7f800001,True),(0xffbfffff,True)]:
  if bool(signaling(raw,32))!=expected:raise RuntimeError('fixed signaling classification control failed')

def coverage(rows,width):
 # Independently inspect actual rows rather than regenerate their population.
 p,bias,eb=layout(width);sign=1<<(width-1);inf=((1<<eb)-1)<<p;hidden=1<<p
 exponents=set();nonzero_gaps=set();fragments=set();pairs={(x,y) for x,y,r,q,f in rows}
 for x,y,r,q,f in rows:
  if not f:fragments.add(q)
  for raw in (x,y):
   a=raw&(sign-1);field=a>>p
   if 0<a<inf:exponents.add((bool(raw&sign),field-bias if field else a.bit_length()-1+1-bias-p))
  a=x&(sign-1);b=y&(sign-1)
  if 0<a<inf and 0<b<inf and a>>p and b>>p:
   mx=(a&(hidden-1))|hidden;my=(b&(hidden-1))|hidden
   if my&1 and mx!=my:nonzero_gaps.add((a>>p)-(b>>p))
 required={(s,e) for s in (False,True) for e in range(1-bias-p,bias+1)}
 if exponents!=required:raise RuntimeError('coverage missing signed exponent binades')
 if fragments!=set(range(-127,128)):raise RuntimeError('coverage missing quotient fragments/signs')
 if not {10,11,12,39,40,41,2*bias-1}<=nonzero_gaps:raise RuntimeError('coverage missing guaranteed nonzero chunk seams')
 if not {(x,y) for x,y,*_ in known_cases(width)}<=pairs:raise RuntimeError('coverage missing fixed tie/wrap/special cases')
 for k in range(p-1):
  snan=inf|(1<<k)
  for signed in (snan,snan|sign):
   if (signed,1) not in pairs or (1,signed) not in pairs:raise RuntimeError('coverage missing signaling payload/operand order')
