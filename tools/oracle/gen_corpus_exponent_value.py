#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact rational exponent inequalities versus pinned MPFR get_exp.

NaN/zero/infinity bits and new-flag classes follow explicit library contracts.
No production implementation source is inspected.
"""
import argparse
from fractions import Fraction
from pathlib import Path
import gmpy2
from gen_corpus_fraction_split import bits,value,population,feed
from gen_corpus_float_scale import publish_set


def expected(raw,width):
    p,expmax=(52,2047) if width==64 else (23,255)
    sign=1<<(width-1);a=raw&(sign-1);inf=expmax<<p;quiet=1<<(p-1)
    if a>inf:return inf|quiet,int(not a&quiet)
    if a==inf:return inf,0
    if a==0:return sign|inf,2
    # Integer field decoding is independent of MPFR's struct/Python-float path.
    bias=1023 if width==64 else 127
    stored,mantissa=divmod(a,1<<p)
    if stored:mantissa|=1<<p
    scale=(stored or 1)-bias-p
    q=Fraction(mantissa<<scale) if scale>=0 else Fraction(mantissa,1<<-scale)
    e=q.numerator.bit_length()-q.denominator.bit_length()
    power=lambda k:Fraction(1<<k) if k>=0 else Fraction(1,1<<-k)
    if q<power(e):e-=1
    if not power(e)<=q<power(e+1):raise RuntimeError('rational exponent inequality failed')
    with gmpy2.context(precision=1200,emin=-100000,emax=100000):
        other=int(gmpy2.get_exp(gmpy2.mpfr(abs(value(raw,width)))))-1
    if e!=other:raise RuntimeError('Fraction/MPFR exponent disagreement')
    result=bits(float(e),width)
    if Fraction(value(result,width))!=e:raise RuntimeError('exponent conversion not exact')
    return result,0


def inputs(width,seed,count):
    words=set(population(width,seed,count))
    p=52 if width==64 else 23;sign=1<<(width-1)
    # All subnormal leading-bit transitions with immediate neighbors.
    for bit in range(p):
        for delta in (-1,0,1):
            x=(1<<bit)+delta
            words.add(x);words.add(x|sign)
    return sorted(words)


def selected(raw,width,index):
    p=52 if width==64 else 23;bias=1023 if width==64 else 127
    sign=1<<(width-1);a=raw&(sign-1);inf=(2047 if width==64 else 255)<<p
    hidden=1<<p;one=bias<<p;two=(bias+1)<<p
    return index%61==0 or a>=inf or a in (0,1,2,3,hidden-1,hidden,hidden+1,one-1,one,one+1,two-1,two,two+1,inf-1)


def reference_hash(rows,width):
    h=state=0xcbf29ce484222325;calls=0
    inf=0x7ff0000000000000 if width==64 else 0x7f800000;sign=1<<(width-1)
    for n,(raw,result,flags) in enumerate(rows,1):
        h=feed(h,result)
        sets=32 if selected(raw,width,n) else 1
        for _ in range(8*sets):state=feed(state,result)
        calls+=8*sets
    return '%016x %d state %016x %d'%(h,len(rows),state,calls)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--seed',type=int,default=20261027);ap.add_argument('--count',type=int,default=2000)
    ap.add_argument('--fresh',action='store_true');a=ap.parse_args()
    if not 0<=a.count<=200000 or not 0<=a.seed<1<<64:ap.error('count0..200000 and unsigned64 seed required')
    if gmpy2.version()!='2.3.2' or gmpy2.mpfr_version().split()[-1]!='4.2.2':raise RuntimeError('pinned MPFR4.2.2/gmpy2 2.3.2 required')
    known=[(64,0,0xfff0000000000000,2),(32,0x80000000,0xff800000,2),
      (64,0xfff0000000000000,0x7ff0000000000000,0),(32,0xff800000,0x7f800000,0),
      (64,1,bits(-1074.,64),0),(32,1,bits(-149.,32),0),
      (64,0xbff0000000000000,0,0),(32,0xbfffffff,0,0),
      (64,0x000fffffffffffff,bits(-1023.,64),0),(32,0x00800000,bits(-126.,32),0),
      (64,0x7ff0000000000001,0x7ff8000000000000,1),(32,0x7fc00001,0x7fc00000,0)]
    for width,raw,result,flags in known:
        if expected(raw,width)!=(result,flags):raise RuntimeError('fixed exponent oracle control failed')
    payloads={};hashes=[]
    for width in (64,32):
        name='logb' if width==64 else 'logbf'
        rows=[(raw,*expected(raw,width)) for raw in inputs(width,a.seed,a.count)]
        def header(count):return '# Pinned oracle: exponent_value MPFR 4.2.2 gmpy2 2.3.2\n# function %s\n# seed %d count %d fresh %s entries %d\n'%(name,a.seed,a.count,a.fresh,count)
        payloads[name+'-special.corpus']=header(len(rows))+'# input result normalized-flags\n'+''.join('%0*x %0*x %d\n'%(width//4,x,width//4,r,f) for x,r,f in rows)
        wide=[]
        for x,r,f in rows:
            if width==32 and f==1:continue
            def widen(word):
                v=value(word,width)
                return bits(v,64) if v==v else 0x7ff8000000000000
            wide.append((widen(x),widen(r)))
        payloads[name+'.corpus']=header(len(wide))+''.join('%016x %016x\n'%row for row in wide)
        hashes.append('exponent.%s %s\n'%(name,reference_hash(rows,width)))
        print('%s: %d raw; %d widened rows'%(name,len(rows),len(wide)),flush=True)
    payloads['exponent_value-special.hash']=''.join(hashes)
    a.out.mkdir(parents=True,exist_ok=True);publish_set(a.out,payloads)

if __name__=='__main__':main()
