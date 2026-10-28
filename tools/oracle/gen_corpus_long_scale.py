#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Native-long scaling: exact rational quantization versus pinned MPFR.

No production kernel is imported or inspected. Raw signed64 exponents cover
native long32/64; common signed32 exponents supply portable numeric hashes.
Flags follow the explicit before-round Double/after-round Float contracts.
"""
import argparse
from fractions import Fraction
from pathlib import Path
import sys
import gmpy2
from gen_corpus_fraction_split import value,bits,feed
from gen_corpus_float_scale import publish_set
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from long_scale_population import pairs


def parameters(width):
    return (52,1023,2047) if width==64 else (23,127,255)


def power(n):return Fraction(1<<n) if n>=0 else Fraction(1,1<<-n)


def rational(raw,width):
    p,bias,emax=parameters(width);sign=1<<(width-1)
    stored,tail=divmod(raw&(sign-1),1<<p)
    if stored==emax:raise RuntimeError('nonfinite rational input')
    q=Fraction(tail if not stored else tail+(1<<p))*power((stored or 1)-bias-p)
    return -q if raw&sign else q


def exponent(q):
    q=abs(q);e=q.numerator.bit_length()-q.denominator.bit_length()
    return e-1 if q<power(e) else e


def encode(q,width,sign):
    """Integer nearest/ties-even grid quantization, including overflow."""
    p,bias,emax=parameters(width);minimum=1-bias-p;inf=emax<<p
    if not q:return sign
    q=abs(q);e=exponent(q);step=max(e-p,minimum);scaled=q/power(step)
    k,r=divmod(scaled.numerator,scaled.denominator)
    if r*2>scaled.denominator or (r*2==scaled.denominator and k&1):k+=1
    if not k:return sign
    rounded=Fraction(k)*power(step);e=exponent(rounded)
    if e>bias:return sign|inf
    if e<1-bias:
        raw=rounded/power(minimum)
        if raw.denominator!=1:raise RuntimeError('subnormal grid encoding failed')
        return sign|int(raw)
    sig=rounded/power(e-p)
    if sig.denominator!=1 or not 1<<p<=sig<1<<(p+1):raise RuntimeError('normal grid encoding failed')
    return sign|((e+bias)<<p)|(int(sig)-(1<<p))


def expected(raw,n,width):
    p,bias,emax=parameters(width);sign=raw&(1<<(width-1));a=raw^sign;inf=emax<<p;quiet=1<<(p-1)
    if a>inf:return inf|quiet,int(not a&quiet)
    if not a or a==inf:return raw,0
    q=rational(raw,width);e=exponent(q);minimum=1-bias-p
    exact=None
    if e+n>bias:result=sign|inf
    elif e+n<minimum-1:result=sign
    else:
        exact=q*power(n);result=encode(exact,width,sign)
    # This independent bound is wider than either production clamp. It keeps
    # exponents representable by MPFR while preserving every possible tail.
    m_n=max(-8192,min(8192,n))
    with gmpy2.context(precision=p+1,emin=minimum+1,emax=bias+1,
                       subnormalize=True,round=gmpy2.RoundToNearest):
        m=gmpy2.mul_2exp(gmpy2.mpfr(value(raw,width)),m_n)
    if gmpy2.is_infinite(m):other=sign|inf
    elif gmpy2.is_zero(m):other=sign
    else:
        num,den=m.as_integer_ratio();other=encode(Fraction(int(num),int(den)),width,sign)
    if result!=other:raise RuntimeError('Fraction/MPFR scaling disagreement')
    if result&((1<<(width-1))-1)==inf:return result,20
    inexact=exact is None or rational(result,width)!=exact
    if not inexact:return result,0
    tiny=(abs(exact)<power(1-bias)) if width==64 and exact is not None else (result&((1<<(width-1))-1))<(1<<p)
    return result,16|(8 if tiny else 0)




def selected(raw,n,width,index):
    p,bias,emax=parameters(width);a=raw&((1<<(width-1))-1);inf=emax<<p
    return index%127==0 or (a in (0,1,3,5,(1<<p)-1,1<<p,(1<<(p+1))-1,bias<<p,inf-1) and n in
      (-(1<<63),-(1<<32),-(1<<31),-5000,-512,-1,0,1,512,5000,(1<<31)-1,1<<32,(1<<63)-1)) or a>=inf


def hash_record(rows,width,longbits):
    nearest=state=0xcbf29ce484222325;count=skipped=calls=0
    for index,(raw,n,result,flags) in enumerate(rows,1):
        if not -(1<<(longbits-1))<=n<1<<(longbits-1):skipped+=1;continue
        nearest=feed(nearest,result);count+=1
        repeats=8*(32 if selected(raw,n,width,index) else 1)
        for _ in range(repeats):state=feed(state,result)
        calls+=repeats
    return 'longscale.%d.long%d %016x %d skipped %d state %016x %d\n'%(width,longbits,nearest,count,skipped,state,calls)


def self_check():
    known=[(64,1,-1,0,24),(64,3,-1,2,24),(64,5,-1,2,24),
      (64,0x001fffffffffffff,-1,0x0010000000000000,24),(32,0x00ffffff,-1,0x00800000,16),
      (64,0x0010000000000000,-1,0x0008000000000000,0),(32,0x00800000,-1,0x00400000,0),
      (64,0x3ff0000000000000,1<<32,0x7ff0000000000000,20),(64,0x3ff0000000000000,-(1<<32),0,24),
      (32,0x3f800000,1<<32,0x7f800000,20),(32,0x3f800000,-(1<<32),0,24),
      (64,0x8000000000000000,(1<<63)-1,0x8000000000000000,0),(32,0x7fc00001,-(1<<63),0x7fc00000,0),
      (64,0x7ff0000000000001,0,0x7ff8000000000000,1)]
    for width,raw,n,r,f in known:
        if expected(raw,n,width)!=(r,f):raise RuntimeError('fixed long scaling reference failed')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--seed',type=int,default=20261028);ap.add_argument('--count',type=int,default=1000)
    ap.add_argument('--fresh',action='store_true');a=ap.parse_args()
    if not 0<=a.count<=50000 or not 0<=a.seed<1<<64:ap.error('count0..50000 and unsigned64 seed required')
    if gmpy2.version()!='2.3.2' or gmpy2.mpfr_version().split()[-1]!='4.2.2':raise RuntimeError('pinned MPFR4.2.2/gmpy2 2.3.2 required')
    self_check();payloads={};hashes=[]
    for width in (64,32):
        name='scalbln' if width==64 else 'scalblnf';rows=[(raw,n,*expected(raw,n,width)) for raw,n in pairs(width,a.seed,a.count)]
        def header(entries):return '# Pinned oracle: long_scale MPFR 4.2.2 gmpy2 2.3.2\n# function %s\n# seed %d count %d fresh %s entries %d\n'%(name,a.seed,a.count,a.fresh,entries)
        payloads[name+'-special.corpus']=header(len(rows))+'# raw x signed64 n result normalized-flags\n'+''.join('%0*x %016x %0*x %d\n'%(width//4,x,n&((1<<64)-1),width//4,r,f) for x,n,r,f in rows)
        generic=[];p,bias,emax=parameters(width);inf=emax<<p
        for x,n,r,f in rows:
            if not -(1<<31)<=n<1<<31:continue
            if width==32 and f==1:continue
            def widen(word):return bits(value(word,width),64) if width==32 else word
            generic.append((widen(x),n&((1<<64)-1),widen(r)))
        payloads[name+'.corpus']=header(len(generic))+''.join('%016x %016x %016x\n'%row for row in generic)
        for longbits in (32,64):hashes.append(hash_record(rows,width,longbits))
        print('%s: %d raw rows; %d common-int32 rows'%(name,len(rows),len(generic)),flush=True)
    payloads['long_scale-special.hash']=''.join(hashes);a.out.mkdir(parents=True,exist_ok=True);publish_set(a.out,payloads)

if __name__=='__main__':main()
