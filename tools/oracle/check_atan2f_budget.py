#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Source-linked applicability checks and rational atan2f error certificate.

The source fingerprints guard the operation model, rather than claiming to
formally verify C. Table and polynomial values are checked numerically against
independent rational derivatives and directed MPFR constants. Reference corpus
values are independent and never use this file or the candidate table.
"""
if not __debug__:
    raise SystemExit("atan2f budget certificate requires assertions; run without -O/PYTHONOPTIMIZE")

import argparse
import hashlib
from pathlib import Path
import random
import re
import struct
from fractions import Fraction as F
import gmpy2
from gen_corpus_floattrig import fraction, power, rational, round32, floor_log2
ROOT=Path(__file__).resolve().parents[2]
INF=0x7f800000
SIGN=0x80000000
MODES=(gmpy2.RoundToNearest,gmpy2.RoundDown,gmpy2.RoundUp,gmpy2.RoundToZero)
# These are applicability guards for the independently described arithmetic
# and classification models below. A source change needs a reviewed model.
FINGERPRINTS={'af_value': '55f6d78182c5c57040e4b5012828743a6aac4105648a1c16f95998961ceca3de', 'af_widen': '91ad5d9380cb2b62b2d0453ab3b9c56ba64f001fcac62187a7281dfbab7a6d49', 'af_inexact': '4080e3863108db3c7ccfeca163b49fead3fc065e34e3f090d24bfdbd8056dc56', 'af_angle': '005ba6ae5fa904df524cb50c3719f829bb02a564adc56f57f9774b797b7db31c', 'af_tiny': '8f44f94978e16bbfcdcf011adbf75e40868307804640bfcb48394761b6365b3b', 'af_kernel': '2b2928e6d27998028d6928199a026cfc87e75d20b1de5e7f4dad7490b22b00c8', 'gmath_atan2f': 'fbdb38e0d3b128d2d47a0f554f04dad8f92ed82f4cc34fc323d831e51be6cf60'}


def function(source,name):
    match=re.search(r'\b'+name+r'\([^;{}]*\)\s*\{',source)
    assert match,'missing modeled function '+name
    start=match.start();level=1;end=match.end()
    while level:
        level+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


def source_guard(path):
    source=path.read_text()
    for name,expected in FINGERPRINTS.items():
        actual=hashlib.sha256(function(source,name).encode()).hexdigest()
        assert actual==expected,'source-model applicability drift: '+name
    for name,value in (('MAGIC','0x1.8p52'),('DIRECT','0.125'),('TINY','0x1p-30')):
        assert re.search(r'#define GMATH_ATAN2_'+name+r'\s+([^\s]+)',source).group(1)==value,'threshold/model drift: '+name
    kernel=function(source,'af_kernel')
    coefficient=[F.from_float(float.fromhex(x)) for x in re.findall(r'-?0x[0-9a-f.]+p[+-]\d+',kernel)]
    expected=[-F(1,3),F(1,5),-F(1,7),F(1,9)]
    assert coefficient[:4]==[F.from_float(float(v)) for v in expected],'direct coefficient drift'
    for actual,exact in zip(coefficient,expected): assert abs(actual-exact)<=abs(exact)*power(-53)
    return source


def table_guard(path):
    text=path.read_text()
    assert '#define GMATH_ATAN2_ROWS 128' in text
    rows=[]
    for line in text.splitlines():
        if re.match(r'\s*/\*\s*\d+\s*\*/\s*\{',line):
            rows.append([F.from_float(float.fromhex(x)) for x in re.findall(r'-?0x[0-9a-f.]+p[+-]\d+',line)])
    assert len(rows)==128 and all(len(row)==10 for row in rows)
    for j,row in enumerate(rows):
        if j>64: assert row==rows[64];continue
        f=F(j,64);den=1+f*f
        exact=[1/den,-f/den**2,(3*f*f-1)/(3*den**3),f*(1-f*f)/den**4]
        for actual,value in zip(row[2:6],exact):
            assert actual==F.from_float(float(value)),'Taylor coefficient drift at row '+str(j)
        for mode in (gmpy2.RoundDown,gmpy2.RoundUp):
            with gmpy2.context(precision=600,round=mode):
                angle=rational(gmpy2.atan(gmpy2.mpfr(j)/64))
            assert abs(row[0]+row[1]-angle)<=power(-106),'atan split drift'
    with gmpy2.context(precision=600):pi=rational(gmpy2.const_pi())
    for name,multiple,word in (('PIO4',F(1,4),0x3f490fdb),('PIO2_HI',F(1,2),0x3fc90fdb),
                               ('3PIO4',F(3,4),0x4016cbe4),('PI_HI',F(1),0x40490fdb)):
        value=re.search(r'#define GMATH_'+name+r'\s+([^\s]+)',text).group(1)
        stored=F.from_float(float.fromhex(value))
        assert abs(stored-pi*multiple)<=pi*multiple*power(-53)
        assert round32(pi*multiple)==word and round32(stored)==word


def tiny_pack(quotient):
    # Arithmetic rendition of the source's integer Double unpacking. The
    # comparison is strict: an exact Float midpoint rounds toward zero.
    q=rational(quotient);e=floor_log2(q)
    if e < -150:return 0
    step=power(max(e,-126)-23);scaled=q/step
    integer,remainder=divmod(scaled.numerator,scaled.denominator)
    if 2*remainder>scaled.denominator:integer+=1
    return round32(integer*step)


def tiny_target(y,x):
    result=[]
    for mode in (gmpy2.RoundDown,gmpy2.RoundUp):
        with gmpy2.context(precision=1200,round=mode):
            result.append(round32(rational(gmpy2.atan2(gmpy2.mpfr(float(fraction(y))),gmpy2.mpfr(float(fraction(x)))))))
    assert result[0]==result[1]
    return result[0]


def tiny_checks(samples):
    rng=random.Random(1793115000)
    pairs=[(1,0x40000000),(3,0x40000000),(0xffffff,0x40000000),(1,INF-1)]
    # Every subnormal midpoint can be represented by an odd numerator/2;
    # include exponent boundaries and both tie parities at all scales.
    for e in range(-149,-29):
        for n in (1,3,0x7fffff,0xffffff):
            y=round32(n*power(e-23));x=round32(power(1))
            if y and fraction(y)/fraction(x)<power(-30):pairs.append((y,x))
    for _ in range(samples):
        y=rng.randrange(1,INF);x=rng.randrange(1,INF)
        if fraction(y)/fraction(x)<power(-30):pairs.append((y,x))
    for y,x in pairs:
        exact=fraction(y)/fraction(x);target=tiny_target(y,x)
        for mode in MODES:
            with gmpy2.context(precision=53,round=mode):
                quotient=gmpy2.mpfr(float(fraction(y)))/gmpy2.mpfr(float(fraction(x)))
            assert tiny_pack(quotient)==target,(hex(y),hex(x),mode)
            # Explicit IX is required even for a dyadic quotient and a zero
            # stored error. UF is exactly the returned NN result's class.
            # The source's explicit branch supplies IX even when division
            # is exact; underflow is forced only for an NN tiny output.
            modeled={'IX','UF'} if tiny_pack(quotient)<0x800000 else {'IX'}
            mathematical={'IX'}
            if target<0x800000: mathematical.add('UF')
            assert modeled==mathematical
    return len(pairs)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'src/elementary/atan2.c')
    parser.add_argument('--table',type=Path,default=ROOT/'src/elementary/atan2_table.h')
    parser.add_argument('--samples',type=int,default=5000)
    args=parser.parse_args();source_guard(args.source);table_guard(args.table)
    # atan(q)>=q/(1+q²), including true-angle binade crossings. The
    # alternating direct Taylor remainder is q^11/11 for q<=1/8.
    direct=F(2)**24*F(1,8)**10*(1+F(1,8)**2)/11
    assert direct==F(65,45056)
    # Complex-log Taylor coefficients obey |G_n|<=1/n: the nearest poles
    # are at distance sqrt(1+F²)>=1. Sum the geometric order>=5 tail.
    radius=F(1,128)
    table=radius**5/(5*(1-radius))*2**27
    assert table<F(788,1000000)
    # Quotient and direct/table evaluation have at most32 rounded operations,
    # |G_n|<=1, and no cancellation of the leading angle. Reflections have
    # angle>=pi/4 and magnitude at mostpi. A4096u relative allowance covers
    # quotient, coefficient, split-sum and two reflections, including their
    # gamma32 accumulation. The magic addition only selects a center;
    # it is excluded from numerical gamma32 propagation. Every selected
    # center is exact and beta is exact by Sterbenz. A deliberately loose
    # absolute table-evaluation bound4gamma32 includes the rounded stored
    # coefficients, split addition and Horner products. atan(q)>=8/65;
    # reflections add at most24u relative. Direct evaluation factors out
    # q, has bounded coefficients, and costs less than8gamma32+8u.
    u=power(-53);gamma32=32*u/(1-32*u)
    table_relative=(4*gamma32+u+power(-106))*F(65,8)+24*u
    direct_relative=8*gamma32+8*u
    assert max(table_relative,direct_relative)<4096*u
    double_allowance=power(-16)
    assert 4096*u*2**24<double_allowance
    # A q<2^-30 reaching the general helper is reflected into a normal
    # angle>=pi/4. Replacing atan(q) by q costs <2^-66/3 FloatULP,
    # safely covered by the same reserved allowance.
    assert power(-66)/3<double_allowance/2
    total=F(1,2)+max(direct,table)+double_allowance
    assert total<F(50146,100000) and total<F(51,100)
    # Normalize24-bit Ma,Mb. In normal FloatULPs, r/h has denominator
    # Mb<2^24 and a nonnegative binary scale. Above halfminsub the scale
    # is at least−1. Thus a nonzero distance to a midpoint >2^-25ULP;
    # use the weaker2^-26 bound uniformly. Allmode Double division is
    # <=2^-29ULP and atan correction <2^-36/3ULP.
    assert power(-29)+power(-36)/3<power(-26)
    # q<=1 exactly in all modes. The magic addition selects j0..64;
    # nearest beta<=1/128, directed beta<=1/64. No old-table size claim.
    for mode in MODES:
        for j in range(8,65):
            for q in (F(j,64),F(2*j-1,128),F(2*j+1,128)):
                if q>1:continue
                with gmpy2.context(precision=53,round=mode):
                    t=gmpy2.mpfr(q.numerator)/q.denominator*64+gmpy2.mpfr(3)*2**51
                index=int(t-gmpy2.mpfr(3)*2**51)
                assert 0<=index<=64
                assert abs(q-F(index,64))<=(F(1,128) if mode==gmpy2.RoundToNearest else F(1,64))
    # Every Float ratio lies in (2^-277,1]; all are normal Doubles.
    # The only q^2/q^3 products occur for q>=2^-30. Reflected tiny
    # angles use q directly. No modeled Double operation reaches a
    # Double underflow/overflow; general Float results exceed2^-31.
    assert power(-149)/(power(128)-power(104))>power(-277)
    assert power(-90)>power(-1022) and 4<power(1023)
    assert power(-30)/(1+power(-60))>power(-31)>power(-126)
    # Nonzero angles are transcendental: if an algebraic nonzero angle
    # had algebraic tan, exp(2i*angle)=(1+i*tan)/(1-i*tan) would be
    # algebraic, contrary to Lindemann. Axes are nonzero rational*pi.
    # Thus all valid nonzero angles need IX. The explicit1+2^100
    # operation is inexact in every mode and has no range exception.
    assert power(100)+1!=F.from_float(float(power(100)+1))
    count=tiny_checks(args.samples)
    print('PASS: source/table/constants, Taylor/reflection budget %.9f FloatULP; index0..64 all modes'%float(total))
    print('tiny midpoint spacing/NN/after-round flags: %d pairs, four modes'%count)


if __name__=='__main__':main()
