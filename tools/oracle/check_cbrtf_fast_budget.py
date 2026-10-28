#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Source-linked all-mode seed-to-old-kernel bound, using exact rational arithmetic.

Applicability guards bind the modeled C expressions; this is not a C verifier.
No runtime output or existing kernel supplies independent reference answers.
"""
if not __debug__:
    raise SystemExit('cbrtf_fast budget certificate requires assertions; run without -O/PYTHONOPTIMIZE')
import argparse
from fractions import Fraction as F
import hashlib
from pathlib import Path
import re
import struct
ROOT=Path(__file__).resolve().parents[2]
FLOAT_SOURCE='a93dd281ffb84f83ccd1fc631024d88e46d224bf26d5172a2845949a05c499ed'
OLD={'double': '301e75643ffb684a7db8059905e0692624154e26e4a41e132f1e931210945841', 'helpers': '1c5133eec6e6d4c8016779f9575e84c45d212d3b8ffc94fa36f6cbf7d0596992', 'table': '20f5db307c5e0008ecd8bed2165ab6652ccbfe21eb00278877515703ea5920b7'}
MODELS={'fc_word': '7bdb37aadc962939eff24510a7834f1f5cecaa348652a64710ad28c376a318cf', 'fc_value': '30ba48ee242cc51328ab025d555e7704e63b59153eeeebd103e7186c50926d94', 'fc_exact_power': '472dd92d57a04eb9b74164218d17244c579ae1def1b90306502293a81ea1e119', 'fc_seed': '137f4ea992b3609b2b31ea3e09b7af6e2fee58cd71e7b56183a2f2ba978dbc96', 'fc_ix': 'aed1c467155167b5860703d1d3072965f3624552acb265fb40254c0e14d6d146', 'gmath_cbrtf': 'b313d8a3b8af073efba8b734b16fc1ab3200d7a3513aad93c9a01726634d2862'}

def function(source,name):
    m=re.search(r'\b'+name+r'\([^;{}]*\)\s*\{',source)
    assert m,'missing modeled function '+name
    i=m.end();depth=1
    while depth and i<len(source):
        depth+=(source[i]=='{')-(source[i]=='}');i+=1
    assert not depth,'unterminated modeled function '+name
    return re.sub(r'\s+','',re.sub(r'/\*.*?\*/','',source[m.start():i],flags=re.S))
def digest(data): return hashlib.sha256(data.encode()).hexdigest()
def power(n): return F(2)**n

def rounded_node(bound,error=F(0)): return bound,error
def mul(a,b,u):
    x,ex=a;y,ey=b
    return x*y,x*ey+y*ex+ex*ey+u*(x+ex)*(y+ey)
def add(a,b,u):
    x,ex=a;y,ey=b
    return x+y,ex+ey+u*(x+ex+y+ey)

def budget(coefficients):
    u=power(-52);s=F(1,128)
    # Exact midpoint subtraction; nearest reciprocal constant plus a directed multiply.
    se=s*((1+u)**2-1);sn=rounded_node(s,se)
    ideals=(F(1,3),-F(1,9),F(5,81))
    cs=[rounded_node(abs(c),abs(c-a)+u*abs(a)) for c,a in zip(ideals,coefficients)]
    polynomial=add(rounded_node(F(1)),mul(sn,add(cs[0],mul(sn,add(cs[1],mul(sn,cs[2],u),u),u),u),u),u)
    pmin=1-s*(F(1,3)+s*(F(1,9)+s*F(5,81)))
    assert pmin>F(99,100),'polynomial range'
    fp=(1+polynomial[1]/pmin)*(1+u)**4-1
    taylor=F(10,243*127**4)
    assert fp<128*u,'seed operation allowance'
    assert (1+taylor)*(1+fp)-1<power(-32),'seed relative error exceeds bound'
    # Normal Float inputs have e=-126..127 and quotient q=-42..42.
    # Seed arguments/tables stay positive. The following dyadic grid ledger
    # bounds nonzero helper lows without presuming an error-free product.
    # y has grid 2^-53 and square.hi grid 2^-54. Split high grids are coarser;
    # square.lo grid >=2^-106, product.lo >=2^-107, and square.lo*y plus
    # cube_low/residual >=2^-159. The positive denominator is below32, hence
    # a nonzero rounded correction >=2^-164. Zero intermediates are harmless.
    # These bounds exclude new IV/DZ/UF/OF in the fast path.
    exponents=range(-126,128)
    assert min(e//3 for e in exponents)==-42 and max(e//3 for e in exponents)==42
    y_grid=power(-53);square_hi_grid=power(-54)
    square_low_grid=y_grid*y_grid;product_low_grid=square_hi_grid*y_grid
    residual_grid=min(product_low_grid,square_low_grid*y_grid)
    assert square_low_grid==power(-106) and product_low_grid==power(-107)
    assert residual_grid==power(-159) and residual_grid/32==power(-164)
    assert residual_grid/32>power(-165)>power(-1022)
    # Normalized arithmetic and IX force are below2^110; exact widening of
    # the original Float argument can approach2^128, still a normal Double.
    assert power(110)<power(128)<power(1023) and power(-149)>power(-1022)
    assert power(-43)>power(-126) and power(44)<power(127)
    # 2^100+1 is inexact in every mode, finite and normal; the force cannot
    # introduce another exception. Exact-power dispatch bypasses it entirely.
    assert power(100)+1>power(100) and power(100)+1<power(100)+power(48)
    B=power(-31)
    # Splits reconstruct exactly by Sterbenz in every mode. Low-part bounds
    # follow from the ulps of fl(T-b), with T=fl((2^27+1)*b).
    a=F(3);la=power(-24);h=a+la
    # Square helper, preserving cancellation bounds of the exact identities.
    e1=u*h*h
    d2=la*(2*a+la)+u*a*a;e2=e1+u*(d2+e1)
    e3=u*h*la
    e5=e2+2*e3+u*(u*a*a+la*la+e2+2*e3)
    e6=u*la*la
    es=e5+e6+u*(u*a*a+e5+e6)
    assert es<power(-48),'directed square reconstruction error'
    square_low=u*a*a+es
    assert square_low<power(-47),'square low-part range'
    # General product: square.hi<10, y<3. Do not assume an error-free product.
    a=F(10);b=F(3);la=power(-22);lb=power(-24);ha=a+la;hb=b+lb
    e1=u*ha*hb
    d2=u*a*b+ha*lb+la*hb+la*lb;e2=e1+u*(d2+e1)
    e3=u*ha*lb;e4=e2+e3+u*(u*a*b+la*b+e2+e3)
    e5=u*la*hb;e6=e4+e5+u*(u*a*b+la*lb+e4+e5)
    e7=u*la*lb;ep=e6+e7+u*(u*a*b+e6+e7)
    assert ep<power(-46),'directed product reconstruction error'
    product_low=u*a*b+ep
    assert product_low<power(-45),'product low-part range'
    em=u*square_low*3
    elow=em+u*(product_low+square_low*3+em)
    cube_error=ep+3*es+elow
    assert cube_error<power(-44),'directed cube reconstruction error'
    # |t-y|<B, t<2, y<3 implies |t^3-y^3|<19B. First subtraction is Sterbenz-exact.
    assert 19*B+57*u<F(1,2),'first residual subtraction applicability'
    residual_error=cube_error+u*(19*B+cube_error)
    assert residual_error<power(-43),'directed residual reconstruction error'
    ideal=B*(1+2*B+F(4,3)*B*B)
    correction=(ideal/(1-3*u)+power(-42))*(1+u)
    assert correction<power(-30),'directed correction magnitude'
    distance=correction+power(-51)
    assert distance<power(-29),'old result to seed bound'
    return dict(u=u,taylor=taylor,fp=fp,square=es,product=ep,cube=cube_error,residual=residual_error,correction=correction,distance=distance)

def bits(x):return struct.unpack('>Q',struct.pack('>d',x))[0]
def dyadic(word):return F.from_float(struct.unpack('>d',struct.pack('>Q',word))[0])
def constant(text):return F.from_float(float.fromhex(text))
def certify_root(v,x):
    w=bits(float(v));low=(dyadic(w-1)+v)/2;high=(v+dyadic(w+1))/2
    assert low**3<=x<=high**3 and not((x==low**3 or x==high**3) and w&1),'cube-root table constant is not nearest'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,default=ROOT/'src/elementary/float_cbrt.c')
    p.add_argument('--double-source',type=Path,default=ROOT/'src/elementary/cbrt.c');p.add_argument('--helpers',type=Path,default=ROOT/'src/elementary/elem_common.h');p.add_argument('--table',type=Path,default=ROOT/'src/elementary/cbrt_table.h');a=p.parse_args()
    assert set(OLD)=={'double','helpers','table'}, 'incomplete old source models'
    assert set(MODELS)=={'fc_word','fc_value','fc_exact_power','fc_seed','fc_ix','gmath_cbrtf'}, 'incomplete Float operation models'
    source=a.source.read_text();seed=function(source,'fc_seed');body=function(source,'gmath_cbrtf')
    pairs=re.findall(r'(-?[0-9]+)\.0/([0-9]+)\.0',seed)
    assert len(pairs)==3,'modeled cubic coefficients missing'
    result=budget([F(int(n),int(d)) for n,d in pairs])
    lo=re.search(r'residue>UINT64_C\(0x([0-9a-f]+)\)',body);hi=re.search(r'residue<UINT64_C\(0x([0-9a-f]+)\)',body)
    assert lo and hi,'strict rounding-cell comparisons missing'
    lower,upper=int(lo[1],16),int(hi[1],16)
    assert lower*power(-52)>result['distance'],'rounding-cell margin does not enclose old correction'
    assert upper==(1<<28)-lower,'asymmetric rounding-cell guard'
    assert 'bits&UINT64_C(0x0fffffff)' in body,'half-Float-cell residue mask changed'
    assert 'bits>=UINT64_C(0x3ff0000000000000)&&bits<UINT64_C(0x4000000000000000)' in body,'normalized seed range guard changed'
    # Reconstruct the conservative performance prefilter independently.
    masks=[0]*64
    for n in range(3,256,2):
        c=n**3;sig=c<<(24-c.bit_length());index=(sig&0x7fffff)>>11;masks[index>>6]|=1<<(index&63)
    block=re.search(r'fc_cube_mask\[64\]\s*=\s*\{(.*?)\};',source,re.S)
    assert block,'missing exact-cube performance mask'
    actual=[int(v,16) for v in re.findall(r'UINT64_C\(0x([0-9a-f]+)\)',block[1])]
    assert actual==masks,'exact-cube performance mask differs from dyadic cube classes'
    # Verify every existing reciprocal/root/factor constant using exact midpoint inequalities.
    table=a.table.read_text();hexes=re.findall(r'0x[0-9a-f.]+p[+-][0-9]+',table)
    assert len(hexes)==131,'unexpected cube-root table population'
    for j in range(64):
        inv,root=map(constant,hexes[2*j:2*j+2]);midpoint=1+F(2*j+1,128)
        w=bits(float(inv));low=(dyadic(w-1)+inv)/2;high=(inv+dyadic(w+1))/2
        exact=1/midpoint
        assert low<=exact<=high and not((exact==low or exact==high) and w&1),'reciprocal table constant is not nearest'
        certify_root(root,midpoint)
    for r,v in enumerate(hexes[128:]):certify_root(constant(v),F(1<<r))
    for name,path in [('double',a.double_source),('helpers',a.helpers),('table',a.table)]:
        assert hashlib.sha256(path.read_bytes()).hexdigest()==OLD[name],'old '+name+' source model changed'
    for name,wanted in MODELS.items():assert digest(function(source,name))==wanted,'Float source operation model changed: '+name
    assert hashlib.sha256(a.source.read_bytes()).hexdigest()==FLOAT_SOURCE,'complete Float translation unit changed'
    print('PASS: cbrtf all-mode seed/old-correction bound %.12g < 2^-29; guard %d Double words; mask %d occupied buckets'%(float(result['distance']),lower,sum(v.bit_count() for v in masks)))
    print('  rational seed FP allowance %.6gu; square %.4g product %.4g cube %.4g residual %.4g'%(float(result['fp']/result['u']),float(result['square']),float(result['product']),float(result['cube']),float(result['residual'])))
if __name__=='__main__':main()
