# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent exact rational nearby-integer targets and reproducible population."""
from fractions import Fraction
import random
import struct

def layout(width):return (52,1023,11) if width==64 else (23,127,8)
def bits(x,width):return int.from_bytes(struct.pack('>d' if width==64 else '>f',x),'big')
def value(raw,width):return struct.unpack('>d' if width==64 else '>f',raw.to_bytes(width//8,'big'))[0]
def rational(raw,width):
 p,bias,eb=layout(width);a=raw&((1<<(width-1))-1);field,m=divmod(a,1<<p)
 if field==(1<<eb)-1:raise ValueError('nonfinite rational')
 if field:m+=1<<p
 e=(field or 1)-bias-p
 return (-1 if raw>>(width-1) else 1)*Fraction(m)*(Fraction(2)**e)
def answer(raw,width):
 p,bias,eb=layout(width);sign=raw&1<<(width-1);a=raw^sign;inf=((1<<eb)-1)<<p;quiet=1<<(p-1)
 if a>inf:return (inf|quiet,)*4+(int(not a&quiet),)
 if a==inf:return (raw,)*4+(0,)
 x=rational(raw,width);floor=x.numerator//x.denominator;ceil=-((-x.numerator)//x.denominator);trunc=int(x)
 residue=x-floor;nearest=floor+int(residue>Fraction(1,2) or (residue==Fraction(1,2) and floor%2))
 outputs=tuple(bits(float(n),width) if n else sign for n in [nearest,floor,ceil,trunc])
 for raw_result,n in zip(outputs,[nearest,floor,ceil,trunc]):
  if rational(raw_result,width)!=n:raise RuntimeError('integral result not exactly representable')
 return outputs+(0,)
def fixed_controls():
 for width,x,targets in [
  (64,0xbff8000000000000,(0xc000000000000000,0xc000000000000000,0xbff0000000000000,0xbff0000000000000,0)),
  (64,0x3fe0000000000000,(0,0,0x3ff0000000000000,0,0)),
  (32,0x80000001,(0x80000000,0xbf800000,0x80000000,0x80000000,0)),
  (32,0x40200000,(0x40000000,0x40000000,0x40400000,0x40000000,0)),
  (64,0x7ff0000000000001,(0x7ff8000000000000,)*4+(1,)),
  (32,0xffc00001,(0x7fc00000,)*4+(0,))]:
  if answer(x,width)!=targets:raise RuntimeError('fixed nearby reference differs')

def population(width,seed,count):
 if not 0<=count<=50000 or not 0<=seed<1<<64:raise ValueError('seed/count out of bounds')
 p,bias,eb=layout(width);sign=1<<(width-1);inf=((1<<eb)-1)<<p;hidden=1<<p
 words={0,1,2,hidden-1,hidden,inf-1,inf,inf+1,inf+(hidden>>1)-1,inf+(hidden>>1),inf+(hidden>>1)+1,sign-1}
 for field in range((1<<eb)-1):
  for mantissa in [0,1,2,(hidden>>1)-1,hidden>>1,hidden-2,hidden-1]:words.add((field<<p)|mantissa)
 # Every half/mask endpoint, even/odd ties and carry across integral binades.
 for e in range(p):
  for odd in [1,3,5,7,13]:
   x=bits(odd*2.0**(e-1),width)
   words.update(x+d for d in [-2,-1,0,1,2] if 0<=x+d<inf)
 # Explicit fractional half cells at every cut, both integer parities and
 # the last half before the next integral binade. Edge significands alone
 # do not cover these interior ties for large integer magnitudes.
 for e in range(p):
  cut=p-e;unit=1<<cut;half=unit>>1;base=(bias+e)<<p
  for center in [base+half,base+unit+half,((bias+e+1)<<p)-half]:
   words.update(center+d for d in [-2,-1,0,1,2] if 0<center+d<inf)
 for k in range(p-1):words.add(inf|(1<<k))
 words|={x|sign for x in tuple(words)}
 rng=random.Random(seed^width)
 words.update(rng.getrandbits(width) for _ in range(count))
 return sorted(words)
def coverage(words,width):
 p,bias,eb=layout(width);sign=1<<(width-1);available=set(words)
 for exponent in range(p):
  for integer in [1<<exponent,(1<<exponent)+1,(1<<(exponent+1))-1]:
   cell=Fraction(integer)+Fraction(1,2);center=bits(float(cell),width)
   if rational(center,width)!=cell:raise RuntimeError('half-cell certificate not representable')
   for delta in [-2,-1,0,1,2]:
    for polarity in [0,sign]:
     if ((center+delta)|polarity) not in available:raise RuntimeError('nearby half-cell coverage missing')
 return True

def selected(raw,width,index):
 p,bias,eb=layout(width);a=raw&((1<<(width-1))-1);inf=((1<<eb)-1)<<p;half=(bias-1)<<p;one=bias<<p
 return index%61==0 or a>=inf or a in [0,1,(1<<p)-1,1<<p,half-1,half,half+1,one-1,one,one+1]
def feed(h,w):
 for shift in range(0,64,8):h=((h^((w>>shift)&255))*1099511628211)&((1<<64)-1)
 return h
def hashes(rows,width):
 raw=state=14695981039346656037;calls=0
 for index,(x,*targets) in enumerate(rows,1):
  raw=feed(raw,targets[0]);sets=32 if selected(x,width,index) else 1
  for target in targets[:4]:
   for _ in range(sets*2):state=feed(state,target);calls+=1
 return raw,state,calls
def payloads(seed,count,fresh=False,oracle=None):
 fixed_controls()
 out={};manifest=''
 for width,name in [(64,'nearbyint'),(32,'nearbyintf')]:
  words=population(width,seed,count);coverage(words,width)
  rows=[(x,*answer(x,width)) for x in words]
  if oracle:
   for row in rows:oracle(row,width)
  header='# Pinned oracle: nearby MPFR 4.2.2 gmpy2 2.3.2\n# function %s\n# seed %d count %d fresh %s entries %d\n'%(name,seed,count,'true' if fresh else 'false',len(rows))
  out[name+'-special.corpus']=header+'# input nearest downward upward towardzero normalized-flags\n'+''.join(' '.join('%0*x'%(width//4,v) for v in row[:5])+' %d\n'%row[5] for row in rows)
  widened=[]
  for row in rows:
   x,*targets,flag=row
   if flag:continue
   def widen(raw):
    v=value(raw,width)
    return 0x7ff8000000000000 if v!=v else bits(v,64)
   widened.append((widen(x),widen(targets[0])))
  out[name+'.corpus']=header.replace('entries %d'%len(rows),'entries %d'%len(widened))+''.join('%016x %016x\n'%r for r in widened)
  h,s,calls=hashes(rows,width);manifest+='nearby.%s %016x %d state %016x %d\n'%(name,h,len(rows),s,calls)
 out['nearby-special.hash']=manifest
 return out
