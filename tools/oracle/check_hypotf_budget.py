#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Check the source-linked integer hypotenuse and native admission certificate.

Run in the pinned oracle image. Source-model fingerprints bind the manually
analyzed expressions to this certificate; they are an applicability guard,
not a formal C verifier. Changed source requires reviewing the derivation and
updating its fingerprints. Reference corpus values never read this source.
The independent target below binary-searches Float midpoint squares on the
common2^-150 integer grid, rather than reproducing the96-bit reduction.
"""
if not __debug__:
    raise SystemExit("hypotf budget certificate requires assertions; run without -O/PYTHONOPTIMIZE")

import argparse
from fractions import Fraction as F
import hashlib
from math import isqrt
from pathlib import Path
import random
import re
import struct
import gmpy2

ROOT=Path(__file__).resolve().parents[2]
SIGN,INF=0x80000000,0x7f800000
IX,UF,OF=1,2,4
MASK64=(1<<64)-1
MODEL_FINGERPRINTS = {'hf_bitlen': 'b72ec9bd167aea20862ed6afb960cb8fb76285a7a0d041f534a05b9085354664', 'hf_shift': 'c451644473f3ea701aee05025c5991ee346b37230a23a14971af969d3d3af88a', 'hf_right': '1fb141fd88cee59431f28eddd06ae352ea3cba85196451023431ca20e8c13691', 'hf_value': 'cc293860fb7ce4e9de06129f028c30e74571d4808fe08122a0a68a973dfa57dd', 'hf_inexact': 'c15d7d42d8b1ec72fe16099c9c06554e6b133109c642f370c6389948e58daec9', 'hf_normalize': '33a2ffc58718334ffbe727641da9baa67787654c3660b6ad57f4562ca20d0450', 'hf_isqrt48': '93e356b37ab684e28417265d538de91a958c2bf55335c7b1000b3f5b8cdc581c', 'hf_fast': '11866aa2cca08028a6a485a6ef395be43004c2202f172830c23819d53356c513', 'gmath_hypotf': '626dc7c047ed686b9a3ce453d4e44d1acb92e332682d69cb8331cbe1750d2f61'}


def compact(source):
    return re.sub(r'\s+','',re.sub(r'/\*.*?\*/|//[^\n]*','',source,flags=re.S))


def function_body(source,name):
    source=re.sub(r'/\*.*?\*/|//[^\n]*','',source,flags=re.S)
    match=re.search(r'\b'+re.escape(name)+r'\s*\([^)]*\)\s*\{',source)
    if match is None:raise RuntimeError('source-model guard: missing '+name)
    start=match.end();depth=1
    for end in range(start,len(source)):
        depth+=(source[end]=='{')-(source[end]=='}')
        if not depth:return source[start:end]
    raise RuntimeError('source-model guard: unbalanced '+name)


def source_guard(path):
    source=path.read_text()
    for name,expected in MODEL_FINGERPRINTS.items():
        actual=hashlib.sha256(compact(function_body(source,name)).encode()).hexdigest()
        if actual!=expected:raise RuntimeError('source-model guard: numerical model drift in '+name)
    raw=compact(source)
    assert '#ifdefGMATH_HW_SQRTstaticinlineinthf_fast' in raw
    assert 'typedefstruct{uint64_tlow;uint32_thigh;}hypotf_uint96;' in raw


def units(raw):
    field=raw>>23;m=raw&0x7fffff
    return (m|0x800000)<<field if field else m<<1


def upper_square(raw):
    field=raw>>23;m=raw&0x7fffff
    coefficient=2*(m|0x800000)+1 if field else 2*m+1
    shift=field-1 if field else 0
    return coefficient*coefficient<<(2*shift)


def independent_target(a,b):
    exact=units(a)**2+units(b)**2
    lo,hi=0,INF
    while lo<hi:
        mid=(lo+hi)//2
        boundary=upper_square(mid)
        if exact<boundary or (exact==boundary and not mid&1):hi=mid
        else:lo=mid+1
    result=lo
    if result==INF:return result,IX|OF
    flags=0 if units(result)**2==exact else IX|(UF if result<0x800000 else 0)
    return result,flags


def normalize(raw):
    field=raw>>23;m=raw&0x7fffff
    if field:return m|0x800000,field-150
    shift=24-m.bit_length()
    return m<<shift,-149-shift


def portable_isqrt(t):
    root=remainder=0
    for digit in range(23,-1,-1):
        remainder=(remainder<<2)|((t>>(2*digit))&3)
        trial=(root<<2)|1;root<<=1
        if remainder>=trial:remainder-=trial;root|=1
    return root


def integer_model(a,b):
    if a<b:a,b=b,a
    if not b:return a,0
    ma,ka=normalize(a);mb,kb=normalize(b);d=ka-kb
    assert 0<=d and 1<<23<=ma<1<<24 and 1<<23<=mb<1<<24
    if d>=13:return a,IX|(UF if a<0x800000 else 0)
    aa,bb=ma*ma,mb*mb
    shifted=aa<<(2*d);low=shifted&MASK64;high=shifted>>64
    previous=low;low=(low+bb)&MASK64;high+=low<previous
    s=(high<<64)|low
    assert s==shifted+bb and s.bit_length()<=73
    length=s.bit_length();t=max((length-1)//2-23,-149-kb)
    assert 0<=t<=23
    target=s>>(2*t)
    assert 1<=target<1<<48
    q=portable_isqrt(target)
    assert q==isqrt(target) and q<1<<24
    mid=(2*q+1)**2
    upper=s<<2 if not t else s>>(2*t-2)
    sticky=0 if not t else bool(s&((1<<(2*t-2))-1))
    assert upper<1<<50
    up=upper>mid or (upper==mid and (sticky or q&1))
    direct=(s<<2)>((2*q+1)**2<<(2*t)) or ((s<<2)==((2*q+1)**2<<(2*t)) and q&1)
    assert bool(up)==bool(direct)
    q+=bool(up)
    qbits=q.bit_length();e=kb+t+qbits-1
    assert (q*q<<(2*t)).bit_length()<=95
    if e>=128:return INF,IX|OF
    if e>=-126:
        m=q>>(qbits-24) if qbits>24 else q<<(24-qbits)
        result=((e+127)<<23)|(m&0x7fffff)
    else:
        assert kb+t==-149
        result=q
    exact=(q*q<<(2*t))==s
    if exact:assert target==isqrt(target)**2
    return result,0 if exact else IX|(UF if result<0x800000 else 0)


def rational(v):
    n,d=v.as_integer_ratio();return F(int(n),int(d))


def native_admission(a,b,mode,omit=None):
    """Model FP state and every admitted flag branch, separately from target.

    Normalized flags here are IX/UF/OF, not host FE_* values. The optional
    omission removes only one branch's effect, for real-input deletion
    controls; it does not change the applicability guard or returned bits.
    """
    with gmpy2.context(precision=53,round=mode) as ctx:
        ctx.clear_flags()
        x=gmpy2.mpfr(units(a))/gmpy2.mpfr(1<<150)
        y=gmpy2.mpfr(units(b))/gmpy2.mpfr(1<<150)
        root=gmpy2.sqrt(x*x+y*y)
        initial=IX if ctx.inexact else 0
    bits=struct.unpack('>Q',struct.pack('>d',float(root)))[0]
    e=(bits>>52)-1023
    expected,expected_flags=independent_target(a,b)
    if expected_flags==0:
        assert initial==0 and rational(root)==F(units(expected),1<<150)
    if e>=128:
        assert expected==INF
        final=initial if omit=='early-overflow' else initial|IX|OF
        return True,INF,final,'early-overflow',initial
    cut=29 if e>=-126 else -97-e
    assert 29<=cut<=52
    sig=(bits&((1<<52)-1))|(1<<52)
    fraction=sig&((1<<cut)-1);half=1<<(cut-1)
    if abs(fraction-half)<=32:
        # A midpoint fallback cannot be mathematically exactFloat: that
        # would make all initial operations exact and root a cell centre.
        assert expected_flags&IX
        result,fallback=integer_model(a,b)
        return False,result,initial|fallback,'fallback',initial
    q=(sig>>cut)+(fraction>half)
    result=((e+126)<<23)+q if e>=-126 else q
    assert result==expected
    final=initial
    if result>=INF:
        branch='rounded-overflow'
        if omit!=branch:final|=IX|OF
    elif result<0x800000:
        branch='subnormal'
        assert a<0x800000 and b<0x800000
        exact=(a*a+b*b)==result*result
        assert exact==(expected_flags==0)
        if not exact and omit!=branch:final|=IX|UF
    elif F(1,1<<126)<=rational(root)<=F(units(INF-1),1<<150):
        branch='normal-cast'
        if omit!=branch:
            # The source ignores this ambient-mode Float conversion. Inside
            # the closed normal range it can set IX, never UF or OF.
            with gmpy2.context(precision=24,round=mode) as ctx:
                ctx.clear_flags()
                ignored=gmpy2.mpfr(root,24)
                cast_inexact=ctx.inexact
            assert F(1,1<<126)<=rational(ignored)<=F(units(INF-1),1<<150)
            if cast_inexact:final|=IX
    else:
        branch='boundary-inexact'
        # NNminnormal/maxfinite can lie beyond the mathematical normal
        # interval; force IX without an ambient narrowing's incidental UF/OF.
        if omit!=branch:final|=IX
    if not initial and result<INF and rational(root)==F(units(result),1<<150):assert expected_flags==0
    return True,result,final,branch,initial


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'src/elementary/hypot.c')
    parser.add_argument('--samples',type=int,default=5000)
    args=parser.parse_args();source_guard(args.source)
    # Gap13 is strictlybelow a quarter of the normalized Float step;
    # subnormal spacing is no smaller. No boundary/overflow can be crossed.
    assert F(((1<<24)-1)**2,2*(1<<23))*F(2)**-26<F(1,4)
    assert (((1<<24)-1)**2<<24)+((1<<24)-1)**2<1<<73
    # All-mode Double sum/sqrt relative error <4u, or<8DoubleULPs of
    # the estimate. Rejecting32ULPs around exact Float midpoints is safe.
    u=F(1,1<<53);error=3*u/(1-u)
    assert error<4*u and (4*u/(1-4*u))*(1<<53)<8<32
    # Non-square integerT<2^48 is >=2^-25 from either integer endpoint;
    # instruction rounding moves at most one DoubleULP<=2^-29.
    assert F(1,2*(1<<24))==F(2)**-25 and F(2)**-25>F(2)**-29
    rng=random.Random(1793111000)
    ts=list(range(1,1<<16))+[(1<<48)-1]
    ts += [rng.randrange(1,1<<48) for _ in range(10000)]
    for t in ts:assert portable_isqrt(t)==isqrt(t)
    modes=(gmpy2.RoundToNearest,gmpy2.RoundDown,gmpy2.RoundUp,gmpy2.RoundToZero)
    for n in [1,2,3,4095,4096,(1<<23)-1,1<<23,(1<<24)-1]:
        for t in (n*n-1,n*n,n*n+1):
            if not 1<=t<1<<48:continue
            for mode in modes:
                with gmpy2.context(precision=53,round=mode):root=gmpy2.sqrt(gmpy2.mpfr(t))
                assert int(gmpy2.floor(root))==isqrt(t)
    pairs=[(3,4),(1,1),(0x007fffff,0xfff),(0x7f6eccf8,0x7eb8807f),
           (0x3fffffff,0x3b800000),(0x4b7fffff,0x46000000),
           (0x4a9ff14a,0x4b896bb0),(0x4c3eb25c,0x461c3c00),
           (INF-1,1),(INF-1,INF-1)]
    for e in range(1,255):
        for m in (0,1,0x7fffff):pairs.append(((e<<23)|m,1))
        if e>=14:
            for gap in (12,13):pairs.append((e<<23,(e-gap)<<23))
    pairs += [(rng.randrange(1,INF),rng.randrange(1,INF)) for _ in range(args.samples)]
    admitted=eligible=0
    for a,b in pairs:
        assert integer_model(a,b)==independent_target(a,b),(hex(a),hex(b))
        ma,ka=normalize(max(a,b));mb,kb=normalize(min(a,b))
        if ka-kb<=12:
            for mode in modes:
                decision,result,flags,branch,initial=native_admission(a,b,mode)
                assert (result,flags)==independent_target(a,b),(hex(a),hex(b),branch,flags)
                admitted+=decision;eligible+=1
    # Each deletion control is a valid public Float input, not an invented
    # FP state. The maxfinite boundary triple has an exact26-bit Double root:
    # 8659189^2+66547860^2=67108861^2, scaled by2^204.
    controls=(('early-overflow',0x7f6e0000,0x7f700000),
              ('rounded-overflow',0x7f6eccf8,0x7eb88080),
              ('subnormal',1,1),
              ('normal-cast',0x4c3eb25c,0x461c3c00),
              ('boundary-inexact',0x7e0420f5,0x7f7ddc25))
    assert 8659189**2+66547860**2==67108861**2
    for label,a,b in controls:
        for mode in modes:
            accepted,result,flags,branch,initial=native_admission(a,b,mode)
            assert accepted and branch==label
            assert (result,flags)==independent_target(a,b)
            accepted,result,deleted,branch,initial=native_admission(a,b,mode,omit=label)
            assert accepted and deleted!=independent_target(a,b)[1],(label,mode,initial,deleted)
        print('real-input flag deletion rejected: %s (%08x,%08x), all four modes' %(label,a,b))
    print('PASS: source model,96-bit bounds, radix4/native floor, exactness, gap13, roundcells and flags')
    print('independent integer midpoint checks %d; native admissions %d/%d; all four modes' %(len(pairs),admitted,eligible))


if __name__=='__main__':main()
