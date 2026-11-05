# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Deterministic raw input population and exact mathematical edge contracts.

This population is reconstructed independently of corpus manifests/answers.
Only rational packing and representation geometry are reused from prior tests.
"""
import importlib.util,math,sys,functools
from fractions import Fraction as F
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('seventeen population requires assertion-enabled Python')
z=importlib.util.spec_from_file_location('seventeen_population_scale',Path(__file__).with_name('check-long-double-scale.py'))
s=importlib.util.module_from_spec(z);z.loader.exec_module(s);b=s.base
FORMATS=(64,80,128,106)
NAMES='sin cos tan asin acos atan atan2 sinh cosh tanh asinh acosh atanh erf erfc gamma lgamma'.split()
PIN='mpfr 4.2.2 gmpy2 2.3.2 mpmath 1.4.1 python 3.14.7'
def raw(fmt,x,sign=0):return b.pack(fmt,'finite',int(x<0)if x else sign,F(x))
def nan(fmt,signaling=False,sign=0):
 if signaling:return {64:(0x7ff0000000000001|(sign<<63),0),80:(0x7fff|(sign<<15),0x8000000000000001),128:(0x7fff000000000000|(sign<<63),1),106:(0x7ff0000000000001|(sign<<63),0)}[fmt]
 hi,lo=b.pack(fmt,'nan',0,F(0));return(hi|(sign<<(15 if fmt==80 else 63)),lo)
def overflow_input_seed(fmt):
 # Construct the input transition independently of stored reference answers.
 # asinh(L) and acosh(L) differ from log(2L) by less than1/L^2.
 limit=finite_limit(fmt);bits=512
 while True:
  scale=1<<bits;n=bits//2+32
  def atanh_bounds(t):
   lo=(t.numerator*scale)//t.denominator;hi=-((-t.numerator*scale)//t.denominator)
   qlo=lo*lo//scale;qhi=-((-hi*hi)//scale)
   termlo,termhi=lo,hi;sumlo=sumhi=0
   for j in range(n):
    sumlo+=termlo//(2*j+1);sumhi+=-((-termhi)//(2*j+1))
    termlo=termlo*qlo//scale;termhi=-((-termhi*qhi)//scale)
   assert (1<<bits)*9<8*(2*n+1)*3**(2*n+1)
   return 2*sumlo,2*(sumhi+1)
  exponent=b.exponent(2*limit);mantissa=(2*limit)/b.scale(1,exponent)
  ml,mh=atanh_bounds((mantissa-1)/(mantissa+1));ll,lh=atanh_bounds(F(1,3))
  low=F(ml+exponent*ll,scale)-1/(limit*limit)
  high=F(mh+exponent*lh,scale)+1/(limit*limit)
  left=s.rounded(fmt,low,0);right=s.rounded(fmt,high,0)
  if left==right:return left
  bits*=2

# Representative certified root brackets are fixed input recipes, independent
# of the numerical answer manifest. Distances duplicate n=3,8 left/right
# root-registry brackets; required MPFR/mpmath regeneration checks their outputs.
_ROOT_SEEDS=(
 (3,'left',int('812fbd7909bfcd0cd4b69737c2a28169fe96fac0d3c37af59832a5f6979bdb8d64954b33aa5f4404dfae3b00d2feafb1ce9a9a606efb2dbeed8821978c339f9f6ea063d55629adc781b5f8a22eb6f2a7b2da3212edcfc5d7349948c3c3c2ab2575c464763c3f5d2576fe45b021f214d52dadea8821a1ccf6c1b9e893d585b376c1bd16e6ed96501291c324fe27bc7e2d',16),-1153),
 (3,'right',int('e9ff25803e1b0557d93e62be340e258669009b34f396ba8c129a8afe76afbfba00c9250c941ea68c2159c6c30e4b4aaf243255f926fdcb9862d2932a8f5c3ba4b2d33ee911f478bd122ec7623516340217929065ec9869c55a4eb28dd16d790dc26409e1baf541a5f1f388d77d3439ab58e688c62b47694a193fce94b37096a1bb86318c3f0b519a861ab226f8314bba',16),-1153),
 (8,'left',int('d00fd4c61e1ab0bea56ea79ab168bbe4197075a1617d7fe8d8a2bf5c47a8cc364e71eb3e0ac5c7ba0ad7b9a27c26b86c73c73242fd6a46895aa82cdb4d0a10cc6f1ac3093af54ac061ef2bc94874527cd3e3711ed13e5c84173cb9f6c075da4e73f9f85eee261df41992c1dce0d350f44094b748d98afa2454994b6f7e029886a7f4c1271789e802a60e325d20dc0615',16),-1167),
 (8,'right',int('cff7b7f87adf4482dcdb98782ab2661ca58b29bf847fd6d20e660bd56f9560639ce05c49584ccc93826086a3410a5b53a005cf8e31269ae1c1ff7523b91c4eb5b0a768847f9c3a0c443e74d841f6cb22d0526e09165d27a189d6adb2b4e959205e604d17b2a559ebb9c5a10c70245fd2a8109baa1dae313fbb282c9c7a300dc28a0e143a596242e951f0f64a191af24c',16),-1164),
)

@functools.lru_cache(maxsize=1)
def pi_bounds():
 def atan_bounds(q):
  value=sum((F(1 if i%2==0 else-1,(2*i+1)*q**(2*i+1))for i in range(256)),F(0))
  return value,value+F(1,513*q**513)
 a,bb=atan_bounds(5);cc,d=atan_bounds(239)
 return 16*a-4*d,16*bb-4*cc

def enclosing_neighbors(fmt,lo,hi):
 seed=s.rounded(fmt,(lo+hi)/2,int(hi<0));value=b.decode(fmt,seed)[3]
 lower=seed if value<lo else s.neighbor(fmt,value,-1)
 lv=b.decode(fmt,lower)[3];upper=s.neighbor(fmt,lv,1);uv=b.decode(fmt,upper)[3]
 assert lv<lo<hi<uv,'input bracket must separate immediate representable neighbors'
 return lower,upper

# Required-oracle-derived transition input seeds are fixed below, separately
# from output references; generation certifies both brackets before packing.
_GAMMA_SEEDS=(
 (64,'overflow',(0x406573fae561f647,0x0)),
 (64,'normal-sign0',(0xc0657ffe45f8aa76,0x0)),
 (64,'normal-sign1',(0xc0659ffffd729afe,0x0)),
 (64,'underflow-sign0',(0xc0667ffffbc63256,0x0)),
 (64,'underflow-sign1',(0xc0665ffd05edca00,0x0)),
 (80,'overflow',(0x4009,0xdb718c066b352e21)),
 (80,'normal-sign0',(0xc009,0xdb7ffff5c5ffcdf5)),
 (80,'normal-sign1',(0xc009,0xdb9ffffffe829047)),
 (80,'underflow-sign0',(0xc009,0xdc3ffff9a465074a)),
 (80,'underflow-sign1',(0xc009,0xdc5fffffff13aa65)),
 (128,'overflow',(0x4009b6e3180cd66a,0x5c4206f128ba77f5)),
 (128,'normal-sign0',(0xc009b6ffffeb8bff,0x9be98e5cd1b61365)),
 (128,'normal-sign1',(0xc009b73ffffffd05,0x208d58d9b2e47e8e)),
 (128,'underflow-sign0',(0xc009b97ffd1c9713,0x588cde7b42b06957)),
 (128,'underflow-sign1',(0xc009b9bfffff9504,0x3dd1443bfd637e1e)),
 (106,'overflow',(0x406573fae561f647,0x3d04eedf869c027c)),
 (106,'normal-sign0',(0xc064bffffed67adc,0x3cfb8219ba40eca8)),
 (106,'normal-sign1',(0xc0649fff3efc93c0,0xbce101a671678bf4)),
 (106,'underflow-sign0',(0xc0667ffffbc63256,0x3d0f0452e4e6d11d)),
 (106,'underflow-sign1',(0xc0665ffd05edca00,0x3cfb96776300a2fe)),
)

def population():
 rows=[];seen=set()
 def add(fmt,op,tag,a,bb=(0,0)):
  row=(fmt,op,*a,*bb)
  if row not in seen:rows.append([f'{fmt}/{NAMES[op]}/{tag}',*row]);seen.add(row)
 for fmt in FORMATS:
  ordinary=F(1,2);one=raw(fmt,1)
  minimum=-1074 if fmt in(64,106)else-16445 if fmt==80 else-16494
  for op in range(17):
   add(fmt,op,'ordinary',raw(fmt,F(3,2)if op==11 else ordinary),raw(fmt,F(3,4))if op==6 else(0,0))
   add(fmt,op,'negative',raw(fmt,2 if op==11 else-F(1,2)))
   for value,tag,sg in[(F(0),'zero',0),(F(0),'negative-zero',1),(F(1),'one',0),(F(2),'two',0),(b.scale(1,minimum),'minimum-subnormal',0),(-b.scale(1,minimum),'negative-minimum-subnormal',1)]:add(fmt,op,tag,raw(fmt,value,sg))
   for sign in(0,1):
    add(fmt,op,'infinity'+str(sign),b.pack(fmt,'inf',sign,F(0)))
    add(fmt,op,'quiet-nan'+str(sign),nan(fmt,False,sign))
    add(fmt,op,'signaling-nan'+str(sign),nan(fmt,True,sign))
   if fmt==80:add(fmt,op,'malformed80',(1,1))
   if fmt==106:
    add(fmt,op,'malformed-dd',(0x7ff0000000000000,1))
    add(fmt,op,'overlapping-out-of-range',(0x7fefffffffffffff,0x7fefffffffffffff))
  normal=-969 if fmt==106 else -1022 if fmt==64 else -16382
  for op in(0,2,3,5,7,9,10,12,13):
   value=b.scale(1,normal)
   for direction in(-1,0,1):add(fmt,op,'normal-boundary'+str(direction),raw(fmt,value)if not direction else s.neighbor(fmt,value,direction))
  for op in(0,1,2):
   for e in(127,1023)if fmt in(64,106)else(127,1023,16383):
    for sign in(0,1):add(fmt,op,'full-exponent'+str(e)+'-'+str(sign),raw(fmt,b.scale(-1 if sign else 1,e)))
  for op in(3,4,11,12):
   for sign in(1,-1):
    for direction in(-1,0,1):
     a=one if not direction else s.neighbor(fmt,F(1),direction)
     v=b.decode(fmt,a)[3]*sign;add(fmt,op,'endpoint'+str(sign)+'-'+str(direction),raw(fmt,v))
  for op in(7,8,9):
   for value in(512,12000,20000,-512,-12000,-20000):add(fmt,op,'range'+str(value),raw(fmt,value))
  seed=overflow_input_seed(fmt);value=b.decode(fmt,seed)[3]
  for op in(7,8):
   for direction in(-1,0,1):
    a=seed if not direction else s.neighbor(fmt,value,direction)
    for sign in(1,-1):add(fmt,op,'overflow-boundary'+str(direction)+'-'+str(sign),raw(fmt,b.decode(fmt,a)[3]*sign))
  for op in(13,14):
   for value in(16,27,28,100,F(427,4),107,128,-16,-128):add(fmt,op,'tail'+str(value),raw(fmt,value))
   for direction in(-1,1):
    a=s.neighbor(fmt,F(16),direction)
    for sign in(1,-1):add(fmt,op,'error-transition16-'+str(direction)+'-'+str(sign),raw(fmt,b.decode(fmt,a)[3]*sign))
  pl,ph=pi_bounds()
  for denominator in(2,4):
   for k in(1,3):
    lo,hi=k*pl/denominator,k*ph/denominator
    for index,a in enumerate(enclosing_neighbors(fmt,lo,hi)):
     for sign in(1,-1):
      for op in(0,1,2):add(fmt,op,f'pi-over{denominator}-{k}-neighbor{index}-{sign}',raw(fmt,b.decode(fmt,a)[3]*sign))
  for n,side,m,e in _ROOT_SEEDS:
   low,high=m*b.scale(1,e),(m+1)*b.scale(1,e);pole=-n if side=='left'else 1-n;direction=1 if side=='left'else-1
   lo,hi=sorted((F(pole)+direction*low,F(pole)+direction*high))
   for index,a in enumerate(enclosing_neighbors(fmt,lo,hi)):add(fmt,16,f'negative-root{n}-{side}-neighbor{index}',a)
  for layout,tag,a in _GAMMA_SEEDS:
   if layout==fmt:
    value=b.decode(fmt,a)[3]
    for direction in(-1,0,1):add(fmt,15,'gamma-transition-'+tag+'-'+str(direction),a if not direction else s.neighbor(fmt,value,direction))
  # Gamma(z)=1/z-EulerGamma+O(z): this reciprocal-power input is a
  # genuine finite-max/virtual-next edge for the single binary formats.
  # DD's different finite maximum makes its corresponding case far overflow.
  add(fmt,15,'reciprocal-overflow-edge',raw(fmt,b.scale(1,-(1024 if fmt in(64,106)else 16384))))
  for op in(15,16):
   add(fmt,op,'huge-positive-gamma',raw(fmt,b.scale(1,1023 if fmt in(64,106)else 16383)))
   for value in(-1,-2,-256,3,4,F(-4001,2),F(4001,2)):add(fmt,op,'gamma-ladder'+str(value),raw(fmt,value))
  ladder=[raw(fmt,0),raw(fmt,0,1),raw(fmt,1),raw(fmt,-1),b.pack(fmt,'inf',0,F(0)),b.pack(fmt,'inf',1,F(0))]
  for i,a in enumerate(ladder):
   for j,bb in enumerate(ladder):add(fmt,6,f'quadrant{i}-{j}',a,bb)
  maximum=1023 if fmt in(64,106)else 16383
  for sign in(1,-1):
   for xsign in(1,-1):add(fmt,6,'selected-tiny-angle'+str(sign)+'-'+str(xsign),raw(fmt,sign*b.scale(1,minimum)),raw(fmt,xsign*b.scale(1,maximum)))
  for invalid in(nan(fmt,True), *(([(1,1)]if fmt==80 else[(0x7ff0000000000000,1)]if fmt==106 else[]))):
   add(fmt,6,'second-invalid-priority',nan(fmt),invalid)
  if fmt==106:
   for op in range(17):
    for a,tag in[((0x3ff0000000000000,1),'remote-one-plus'),((0x3ff0000000000000,0x8000000000000001),'remote-one-minus'),((0xbff0000000000000,1),'remote-negative-pole-plus')]:add(fmt,op,tag,a,one if op==6 else(0,0))
   for op in(0,1,2):add(fmt,op,'huge-remote-tail',(0x7fe0000000000000,1))
   for op in(15,16):
    add(fmt,op,'remote-256-pole',(0xc070000000000000,1))
    add(fmt,op,'huge-negative-remote',(0xffe0000000000000,1))
    add(fmt,op,'huge-negative-remote-below',(0xffe0000000000000,0x8000000000000001))
 return rows

def special(row):
 _,fmt,op,ah,al,bh,bl=row
 k,sg,iv,x=b.decode(fmt,(ah,al));kb,sb,ib,y=b.decode(fmt,(bh,bl))if op==6 else('finite',0,False,F(0))
 def result(kind,sign=0,value=F(0),flags=0):return {'exact':[*(f'{v:016x}'for v in b.pack(fmt,kind,sign,value)),flags]}
 if iv or ib:return result('nan',flags=1)
 if k=='nan'or kb=='nan':return result('nan')
 zero=k=='finite'and not x
 if op<=2:
  if k=='inf':return result('nan',flags=1)
  if zero:return result('finite',0,F(1))if op==1 else result('finite',sg)
 if op in(3,4):
  if k=='inf'or abs(x)>1:return result('nan',flags=1)
  if op==3 and zero:return result('finite',sg)
  if op==4 and x==1:return result('finite')
 if op==5 and zero:return result('finite',sg)
 if op==6:
  bz=kb=='finite'and not y
  if zero and not sb:return result('finite',sg)
  if kb=='inf'and not sb and k!='inf':return result('finite',sg)
  # All remaining quadrant/limit cases are nonzero angles and addIX.
 if op in(7,8,9,10,11,12):
  if op==11 and(sg or k!='inf'and x<1):return result('nan',flags=1)
  if op==12 and(k=='inf'or abs(x)>=1):return result('inf',sg,flags=2)if k=='finite'and abs(x)==1 else result('nan',flags=1)
  if op==11 and x==1:return result('finite')
  if zero:return result('finite',0,F(1))if op==8 else result('finite',sg)
  if k=='inf':return result('finite',sg,F(-1 if sg else 1))if op==9 else result('inf',0 if op==8 else sg)
 if op in(13,14):
  if zero:return result('finite',0,F(1))if op==14 else result('finite',sg)
  if k=='inf':return result('finite',sg,F(-1 if sg else 1))if op==13 else result('finite',0,F(2 if sg else 0))
 if op in(15,16):
  if k=='inf':return result('nan',flags=1)if op==15 and sg else result('inf')
  if zero:return result('inf',sg if op==15 else 0,flags=2)
  if x<0 and x.denominator==1:return result('nan',flags=1)if op==15 else result('inf',flags=2)
  if x in(1,2):return result('finite',0,F(1 if op==15 else 0))
  if op==15 and abs(x)>=4096:
   # Monotonic Gamma for x>=2 and reflection on the representable
   # noninteger grid give rigorous far-range answers without constructing
   # Gamma's potentially astronomical binary exponent.
   assert math.factorial(4095)>(1<<18000)
   if x>0:return result('inf',flags=20)
   parity=(abs(x).numerator//abs(x).denominator)&1
   minimum=-1074 if fmt in(64,106)else-16445 if fmt==80 else-16494
   return {'tiny':[minimum-2,int(not parity)]}
 return None

def finite_limit(fmt):
 return s.LIMIT if fmt==106 else b.scale(1,1024 if fmt==64 else 16384)-b.scale(1,(1023 if fmt==64 else 16383)-(52 if fmt==64 else 63 if fmt==80 else 112))
def overflow_threshold(fmt):
 gap=b.scale(1,917 if fmt==106 else(1023 if fmt==64 else 16383)-(52 if fmt==64 else 63 if fmt==80 else 112))
 return finite_limit(fmt)+gap/2
