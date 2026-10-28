# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact rational current-mode integer targets, independent of the C kernel."""
from fractions import Fraction
from nearby_reference import layout, rational, bits, population as nearby_population, coverage, feed
MASK=(1<<64)-1
SEED=20261028
COUNT=2000

def population(width,seed,count):
 words=set(nearby_population(width,seed,count));sign=1<<(width-1)
 for center in [Fraction(1<<31)+d for d in [Fraction(-5,4),Fraction(-1),Fraction(-3,4),Fraction(-1,2),Fraction(-1,4),Fraction(0),Fraction(1,4),Fraction(1,2),Fraction(3,4),Fraction(1),Fraction(5,4)]]+[Fraction(1<<63),Fraction((1<<63)-(1<<10))]:
  raw=bits(float(center),width)
  for delta in [-2,-1,0,1,2]:
   words.add(raw+delta);words.add((raw+delta)|sign)
 return sorted(words)

def answer(raw,width):
 p,bias,eb=layout(width);a=raw&((1<<(width-1))-1)
 if a>=((1<<eb)-1)<<p:return tuple([1<<63 if b==64 else (-1<<31)&MASK,1] for _ in range(4) for b in [32,64])
 x=rational(raw,width);lo=x.numerator//x.denominator;hi=-((-x.numerator)//x.denominator);r=x-lo
 near=lo+int(r>Fraction(1,2) or (r==Fraction(1,2) and lo%2))
 out=[]
 for n in [near,lo,hi,int(x)]:
  for b in [32,64]:
   invalid=not -(1<<(b-1))<=n<(1<<(b-1))
   out.append([(-(1<<(b-1)) if invalid else n)&MASK,1 if invalid else (2 if x!=n else 0)])
 return tuple(out)

def selected(raw,width,index):
 p,bias,eb=layout(width);a=raw&((1<<(width-1))-1);field=a>>p
 return index%127==0 or field in [0,(1<<eb)-1,bias-1,bias,bias+30,bias+31,bias+62,bias+63]

def hashes(rows,width,longbits):
 h=state=14695981039346656037;calls=0
 for i,(raw,out) in enumerate(rows,1):
  for target,flag in [out[0 if longbits==32 else 1],out[1]]:h=feed(feed(h,target),flag)
  for mode in range(4):
   for _ in range((32 if selected(raw,width,i) else 1)*2):
    for target,flag in [out[mode*2+(0 if longbits==32 else 1)],out[mode*2+1]]:
     state=feed(feed(state,target),flag);calls+=1
 return h,state,calls

def fixed_controls():
 for raw,width,expected in [
  (0x41dfffffffe00000,64,[[(-1<<31)&MASK,1],[2147483648,2],[2147483647,2],[2147483647,2],[(-1<<31)&MASK,1],[2147483648,2],[2147483647,2],[2147483647,2]]),
  (0x80000001,32,[[0,2],[0,2],[MASK,2],[MASK,2],[0,2],[0,2],[0,2],[0,2]]),
  (0x43e0000000000000,64,[[(-1<<31)&MASK,1],[1<<63,1]]*4),
  (0xc3e0000000000000,64,[[(-1<<31)&MASK,1],[1<<63,0]]*4)]:
  if list(answer(raw,width))!=expected:raise RuntimeError('current integer literal reference differs')

def payloads(seed=SEED,count=COUNT,fresh=False,oracle=None):
 fixed_controls();out={};manifest=''
 for width,suffix in [(64,''),(32,'f')]:
  words=population(width,seed,count);coverage(words,width);rows=[(raw,answer(raw,width)) for raw in words]
  if oracle:
   for raw,target in rows:oracle(raw,width,target)
  header='# Pinned oracle: currentint MPFR 4.2.2 gmpy2 2.3.2\n# function currentint%d\n# seed %d count %d fresh %s entries %d\n'%(width,seed,count,str(fresh).lower(),len(rows))
  out['currentint%d-special.corpus'%width]=header+'# input four-modes each signed32-result flags signed64-result flags\n'+''.join('%0*x '%(width//4,raw)+' '.join('%016x %d'%(v,f) for v,f in targets)+'\n' for raw,targets in rows)
  common=[]
  for raw,targets in rows:
   result,flag=targets[0]
   if flag==1:continue
   signed=result if result<1<<63 else result-(1<<64)
   x=float(rational(raw,width));common.append((bits(x,64),bits(float(signed),64)))
  for family in ['lrint','llrint']:
   out[family+suffix+'.corpus']=header.replace('# function currentint%d'%width,'# function '+family+suffix).replace('entries %d'%len(rows),'entries %d'%len(common))+''.join('%016x %016x\n'%r for r in common)
  for longbits in [32,64]:
   h,s,c=hashes(rows,width,longbits);manifest+='currentint.long%d.%d %016x %d state %016x %d\n'%(longbits,width,h,len(rows),s,c)
 out['currentint-special.hash']=manifest
 return out
