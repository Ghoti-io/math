#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact adjacent IEEE targets: rational spacing versus pinned directed MPFR.

WG14 N1570 7.12.11.3/F.10.8.3 supplies value/flag rules. Canonical NaNs and
preserved errno are own-library policy. Never inspects implementation source.
"""
import argparse
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
import random
import struct
import gmpy2
from gen_corpus_float_scale import publish_set


def format_info(single):
    m,bias,expmax=(23,127,255) if single else (52,1023,2047)
    sign=1<<(m+(8 if single else 11));inf=expmax<<m
    return m,bias,expmax,sign,inf,1<<(m-1),1<<m


def power(e):return Fraction(1<<e) if e>=0 else Fraction(1,1<<-e)

def floor_log2(q):
    q=abs(q);k=q.numerator.bit_length()-q.denominator.bit_length()
    return k-1 if q<power(k) else k


@lru_cache(maxsize=200000)
def rational(raw,single):
    m,bias,_,sign,inf,_,_=format_info(single);a=raw&~sign
    if a>=inf:raise RuntimeError('nonfinite rational request')
    exponent=a>>m;sig=a&((1<<m)-1)
    if exponent:sig|=1<<m
    q=Fraction(sig)*power((exponent if exponent else 1)-bias-m)
    return -q if raw&sign else q


def bits(value,single):
    return struct.unpack('>I' if single else '>Q',struct.pack('>f' if single else '>d',value))[0]


def encode(q,single,zero_sign=0):
    _,_,_,sign,inf,_,_=format_info(single)
    maximum=rational(inf-1,single)
    if abs(q)>maximum:return (sign if q<0 else 0)|inf
    if not q:return zero_sign
    result=bits(float(q),single)
    if rational(result,single)!=q:raise RuntimeError('reference neighbor not exactly representable')
    return result


@lru_cache(maxsize=200000)
def fractional_neighbor(raw,up,single):
    m,bias,_,sign,inf,_,_=format_info(single);a=raw&~sign
    if a==inf:return (raw&sign)|(inf-1)
    x=rational(raw,single)
    if not x:return (0 if up else sign)|1
    magnitude=abs(x);k=floor_log2(magnitude)
    shrinking=(x<0)==up
    step_exp=max(k-m-(1 if shrinking and magnitude==power(k) else 0),1-bias-m)
    return encode(x+(1 if up else -1)*power(step_exp),single,raw&sign)


with gmpy2.context(precision=2600,emin=-100000,emax=100000):
    EPS=gmpy2.mpfr(2)**-1200
    NEG_EPS=-EPS  # Construct before restricted range; unary minus can underflow.


@lru_cache(maxsize=200000)
def mpfr_neighbor(raw,up,single):
    m,bias,_,sign,inf,_,_=format_info(single);a=raw&~sign
    if a<inf:
        q=rational(raw,single)
        with gmpy2.context(precision=2600,emin=-100000,emax=100000):
            x=gmpy2.mpfr(q.numerator)/q.denominator
    with gmpy2.context(precision=m+1,emin=2-bias-m,emax=bias+1,
                       subnormalize=True,round=gmpy2.RoundUp if up else gmpy2.RoundDown):
        if a==inf:
            v=gmpy2.mpfr('-inf' if raw&sign else 'inf')
            result=gmpy2.next_above(v) if up else gmpy2.next_below(v)
        else:result=gmpy2.add(x,EPS if up else NEG_EPS)
    return bits(float(result),single)


def expected(x,y,single):
    _,_,_,sign,inf,quiet,minimum=format_info(single);a=x&~sign;b=y&~sign
    if a>inf or b>inf:
        invalid=(a>inf and not x&quiet) or (b>inf and not y&quiet)
        return inf|quiet,int(invalid)
    if x==y or not (a|b):return y,0
    # Rational comparisons handle finite values; infinities are direction bounds.
    if b==inf:up=not bool(y&sign)
    elif a==inf:up=bool(x&sign)
    else:up=rational(x,single)<rational(y,single)
    result=fractional_neighbor(x,up,single);other=mpfr_neighbor(x,up,single)
    if result!=other:raise RuntimeError('adjacent Fraction/MPFR disagreement: %x %x %x %x'%(x,y,result,other))
    r=result&~sign
    flags=20 if a<inf and r==inf else (24 if r<minimum else 0)
    return result,flags


def population(single,seed,count):
    m,bias,expmax,sign,inf,quiet,minimum=format_info(single)
    rng=random.Random(seed^int(single));pairs=set();one=bias<<m
    def add(x,y):pairs.add((x,y))
    for exponent in range(expmax+1):
        for tail in (0,1,(1<<m)-1):
            for negative in (0,sign):
                x=negative|(exponent<<m)|tail
                for y in (0,sign,x,x^sign,inf,sign|inf,one,sign|one):add(x,y)
                if (x&~sign)<inf:
                    for up in (False,True):add(x,fractional_neighbor(x,up,single))
    special=(0,1,2,3,minimum-1,minimum,minimum+1,one,inf-1,inf,inf|1,inf|quiet,inf|quiet|1)
    points=[word|negative for word in special for negative in (0,sign)]
    for x in points:
        for y in points:add(x,y)
    for _ in range(count):add(rng.getrandbits(32 if single else 64),rng.getrandbits(32 if single else 64))
    return sorted(pairs)


def selected(x,y,index,single):
    _,bias,_,sign,inf,quiet,minimum=format_info(single)
    points={0,1,2,3,minimum-1,minimum,minimum+1,bias<<(23 if single else 52),inf-1,inf,inf|1,inf|quiet,inf|quiet|1}
    return index%127==0 or ((x&~sign) in points and (y&~sign) in points)


def hash_word(h,word):
    for i in range(8):h=((h^((word>>(8*i))&255))*0x100000001b3)&((1<<64)-1)
    return h


def probe_reference(rows,single):
    name='nextafterf' if single else 'nextafter';full=allm=0xcbf29ce484222325;states=0
    for index,(x,y,result,flags) in enumerate(rows):
        full=hash_word(hash_word(full,result),flags)
        if selected(x,y,index,single):
            for _ in range(4):allm=hash_word(hash_word(allm,result),flags)
            states+=4*32*2
    return 'math.%s_raw.hash %016x\nmath.%s_raw.count %d\nmath.%s_all_modes.hash %016x\nmath.%s_state.count %d\n'%(name,full,name,len(rows),name,allm,name,states)


def self_check():
    for single in (False,True):
        m,bias,_,sign,inf,quiet,minimum=format_info(single);one=bias<<m
        fixed=((0,sign,sign,0),(sign,0,0,0),(0,one,1,24),(sign,sign|one,sign|1,24),
          (1,0,0,24),(sign|1,one,sign,24),(minimum-1,one,minimum,0),
          (minimum,0,minimum-1,24),(one,0,one-1,0),(one,inf,one+1,0),(1,2,2,24),(1,1,1,0),(inf-1,inf,inf,20),
          (inf,0,inf-1,0),(sign|inf,0,sign|(inf-1),0),
          (inf,sign|inf,inf-1,0),(sign|inf,inf,sign|(inf-1),0),
          (inf|quiet,inf|1,inf|quiet,1),(inf|1,inf|quiet,inf|quiet,1),
          (inf|quiet,one,inf|quiet,0),(one,inf|quiet,inf|quiet,0))
        for x,y,result,flags in fixed:
            if expected(x,y,single)!=(result,flags):raise RuntimeError('adjacent fixed boundary control failed')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seed',type=int,default=20261027)
    parser.add_argument('--count',type=int,default=2000);parser.add_argument('--fresh',action='store_true');args=parser.parse_args()
    if not 0<=args.seed<1<<64:parser.error('--seed must be unsigned64')
    if not 0<=args.count<=50000:parser.error('--count must be in0..50000')
    self_check();payloads={};probe=''
    for single in (False,True):
        name='nextafterf' if single else 'nextafter';rows=[];wide_rows=[]
        _,_,_,sign,inf,quiet,_=format_info(single)
        for x,y in population(single,args.seed,args.count):
            result,flags=expected(x,y,single);rows.append((x,y,result,flags))
            snan=lambda raw:(raw&~sign)>inf and not raw&quiet
            if not single or not (snan(x) or snan(y)):
                def widen(raw):
                    if not single:return raw
                    value=struct.unpack('>f',struct.pack('>I',raw))[0]
                    return bits(float(value),False)
                wide_rows.append('%016x %016x %016x\n'%(widen(x),widen(y),widen(result)))
        def header(family,size):
            return '# Pinned oracle: tools/oracle/gen_corpus_adjacent.py; MPFR %s gmpy2 %s\n# function %s\n# seed %d count %d fresh %s entries %d\n'%(gmpy2.mpfr_version().split()[-1],gmpy2.version(),family,args.seed,args.count,args.fresh,size)
        payloads[name+'-special.corpus']=header(name+'_raw',len(rows))+'# raw x y result normalized-flags\n'+''.join('%016x %016x %016x %016x\n'%row for row in rows)
        payloads[name+'.corpus']=header(name,len(wide_rows))+'# binary64 words; binary32 inputs/results exactly widened and sNaNs excluded\n'+''.join(wide_rows)
        probe+=probe_reference(rows,single)
        print('%s: %d raw pairs; %d widened pairs'%(name,len(rows),len(wide_rows)),flush=True)
    payloads['adjacent-special.hash']=probe;args.out.mkdir(parents=True,exist_ok=True);publish_set(args.out,payloads)


if __name__=='__main__':main()
