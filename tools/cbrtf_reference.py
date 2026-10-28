#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact Float reference certificates and deterministic inputs, no runtime kernel."""
from fractions import Fraction
import random
import struct
SIGN=0x80000000
INF=0x7f800000
QNAN=0x7fc00000
def power(e): return Fraction(2)**e
def value(raw): return struct.unpack('>f',struct.pack('>I',raw))[0]
def wide(raw): return struct.unpack('>Q',struct.pack('>d',value(raw)))[0]
def fraction(raw): return Fraction.from_float(value(raw))
def floor_log2(x):
    x=abs(x);e=x.numerator.bit_length()-x.denominator.bit_length()
    return e-(x<power(e))
def round32(x):
    sign=SIGN if x<0 else 0;x=abs(x)
    if not x: return sign
    e=max(floor_log2(x),-126);v=x/power(e-23);q,r=divmod(v.numerator,v.denominator)
    if 2*r>v.denominator or (2*r==v.denominator and q&1): q+=1
    if q==1<<24: q>>=1;e+=1
    if e>127: return sign|INF
    return sign|q if q<1<<23 else sign|((e+127)<<23)|(q-(1<<23))
def error_neighbor(word,upward):
    if not word&~SIGN: return 1 if upward else SIGN|1
    return word-1 if bool(word&SIGN)==upward else word+1

def inputs(seed, count):
    rng = random.Random(seed)
    population = {0, SIGN, INF, INF|SIGN, QNAN, QNAN|SIGN|7, INF|1, INF|SIGN|1, 0x7fffffff, 0xffffffff}
    for bit in range(22):
        population.update((INF|(1<<bit), INF|SIGN|(1<<bit)))
    population.update((0x7fbfffff,0xffbfffff))
    def near(raw):
        for a in (raw-1, raw, raw+1):
            if 0<a<INF: population.update((a,a|SIGN))
    for exponent in range(255):
        for tail in (0,1,0x3fffff,0x7ffffe,0x7fffff): near((exponent<<23)|tail)
    for bit in range(23): near(1<<bit)
    for exponent in (0,1,2):
        for j in range(129): near(round32((1+Fraction(j,128))*power(exponent)))
    # Every odd exact root significand and every representable cube scale.
    for root in range(1,256,2):
        for q in range(-50,43):
            x=Fraction(root**3)*power(3*q)
            raw=round32(x)
            if raw and raw<INF and fraction(raw)==x: near(raw)
    # Inverse image of exact adjacent-output midpoints, with rational cubes.
    for _ in range(256):
        r=(rng.randrange(77,170)<<23)|rng.getrandbits(23)
        midpoint=(fraction(r)+fraction(r+1))/2
        raw=round32(midpoint**3)
        if raw<INF: near(raw)
    for _ in range(count):
        raw=rng.getrandbits(32)
        if (raw&~SIGN)>INF: raw|=0x00400000
        population.add(raw)
    return sorted(population)

def flags(raw):
    a=raw&~SIGN
    if a>INF: return int(not a&0x00400000)
    if not a or a==INF: return 0
    x=abs(fraction(raw));n=x.numerator
    exact_power=(n&(n-1))==0 and floor_log2(x)%3==0
    return 0 if exact_power else 16

def certify(raw, target, error):
    x=fraction(raw);r=fraction(target)
    # All finite nonzero roots are normal. Signed order of neighboring floats.
    previous=target-1 if not target&SIGN else target+1
    following=target+1 if not target&SIGN else target-1
    low=(fraction(previous)+r)/2;high=(fraction(following)+r)/2
    if not low**3<=x<=high**3 or ((x==low**3 or x==high**3) and target&1):
        raise RuntimeError('cbrtf nearest-target cube certificate failed')
    if r**3==x:
        if error!=0: raise RuntimeError('cbrtf exact cube has nonzero signed error')
        return
    unit=power(floor_log2(abs(x))//3-23)
    ef=fraction(error);before=fraction(error_neighbor(error,False));after=fraction(error_neighbor(error,True))
    low=r+(before+ef)*unit/2;high=r+(ef+after)*unit/2
    if not low**3<=x<=high**3 or ((x==low**3 or x==high**3) and error&1):
        raise RuntimeError('cbrtf signed-error cube certificate failed')
