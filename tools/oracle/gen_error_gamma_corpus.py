#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Required pinned directed MPFR and independent mpmath focused oracle."""
import argparse, hashlib, importlib.util, json, platform, sys
from fractions import Fraction as F
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import error_gamma_reference as r
import gmpy2 as g
import mpmath as mp
spec=importlib.util.spec_from_file_location('error_gamma_independent',Path(__file__).with_name('gen_long_double_seventeen_corpus.py'))
o=importlib.util.module_from_spec(spec);spec.loader.exec_module(o)

def runtime():
    actual=f'{g.mpfr_version().lower()} gmpy2 {g.version()} mpmath {mp.__version__} python {platform.python_version()}'
    if actual!=r.PIN:raise SystemExit('required error/gamma oracle runtime mismatch: '+actual)

def invert(fmt,op,tag,threshold,left,right,negative_pole=None,input_scale=F(1)):
    # Compare directed function enclosures against an exact dyadic threshold.
    for iteration in range(4096):
        mid=(left+right)/2;x=(mid if negative_pole is None else mid-negative_pole)*input_scale
        bounds=[]
        for rounding in (g.RoundDown,g.RoundUp):
            with g.context(precision=4096,round=rounding):
                xx=g.mpfr(g.mpq(x.numerator,x.denominator));assert o.exact(xx)==x,'exact seam input projection'
                v=g.erfc(xx)if op==14 else g.lgamma(xx)[0]
                if op==15:
                    with g.context(precision=4096,round=g.RoundUp if rounding==g.RoundDown else g.RoundDown):
                        tt=g.mpfr(g.mpq(threshold.numerator,threshold.denominator));assert o.exact(tt)==threshold,'exact threshold projection'
                        log_threshold=g.log(tt)
                    v-=log_threshold
                bounds.append(o.exact(v))
        target=threshold if op in (14,16)else F(0)
        if bounds[1]<target:below=True
        elif bounds[0]>target:below=False
        else:raise ValueError('unresolved directed seam inversion')
        increasing=op in (15,16)and negative_pole is None
        if below==increasing:left=mid
        else:right=mid
        lo,hi=(left,right)if negative_pole is None else(left-negative_pole,right-negative_pole)
        lo*=input_scale;hi*=input_scale
        if negative_pole is not None and left==0:continue
        a=r.raw(fmt,lo);b=r.raw(fmt,hi)
        if a==b:break
    else:raise ValueError('bounded seam inversion exhausted')
    with mp.workprec(8192):
        def evaluate(v):
            xx=mp.mpf(v.numerator)/v.denominator
            return mp.erfc(xx)-mp.mpf(threshold.numerator)/threshold.denominator if op==14 else mp.re(mp.loggamma(xx))-(mp.log(mp.mpf(threshold.numerator)/threshold.denominator)if op==15 else mp.mpf(threshold.numerator)/threshold.denominator)
        values=evaluate(lo),evaluate(hi)
        assert values[0]<0<values[1]if increasing else values[0]>0>values[1],'independent seam inversion bracket'
    return [fmt,op,tag,list(a)]

def lgamma_seeds():
    out=[]
    for fmt in (32,64,80,128,106):
        exponent=128 if fmt==32 else 1024 if fmt in (64,106)else 16384
        # x=s*y,1<=y<=2. Common power-of-two scaling keeps every exact
        # bisection significand small even for extended exponent ranges.
        scale=F(2)**(exponent-(exponent.bit_length()-1))
        out.append(invert(fmt,16,'lgamma-rounded-overflow',(r.limit(fmt)+r.virtual(fmt))/2,F(1),F(2),input_scale=scale))
    return out

def seeds():
    out=[]
    for fmt in (32,64,80,128,106):
        precision={32:24,64:53,80:64,128:113,106:106}[fmt]
        for tag,threshold in [('erfc-normal',r.normal(fmt)),('erfc-zero',F(2)**(r.minimum(fmt)-1)),('erf-saturation',F(2)**(-precision-1))]:
            item=invert(fmt,14,tag,threshold,F(0),F(256));out.append(item)
            if tag=='erf-saturation':out.append([fmt,13,tag,item[3]])
        out.append(invert(fmt,15,'gamma-overflow',r.limit(fmt),F(2),F(20000)))
        # The actual component-sum DD grid has remote subnormal tails near1.
        # A nominal106-bit spacing does not locate rounding to exactly1.
        if fmt==106:
            dd=invert(fmt,14,'erf-dd-saturation',F(2)**(-1075),F(0),F(256))
            out.append([fmt,13,'erf-dd-saturation',dd[3]])
        predecessor=r.value(fmt,r.neighbor(fmt,r.normal(fmt),-1))
        midpoint=(r.normal(fmt)+predecessor)/2
        out.append(invert(fmt,14,'erfc-rounded-normal',midpoint,F(0),F(256)))
        out.append(invert(fmt,15,'gamma-rounded-overflow',(r.limit(fmt)+r.virtual(fmt))/2,F(2),F(20000)))
        # Saturation of erfc(-x) at2 uses the actual gap below2.
        previous_two=r.value(fmt,r.neighbor(fmt,F(2),-1))
        negative=invert(fmt,14,'erfc-negative-saturation',(2-previous_two)/2,F(0),F(256))
        negative[3]=list(r.raw(fmt,-r.value(fmt,tuple(negative[3]))));out.append(negative)
        for tag,threshold in [('gamma-normal',r.normal(fmt)),('gamma-zero',F(2)**(r.minimum(fmt)-1))]:
            n=0;upper=F(2)
            while upper>=threshold/4:n+=1;upper*=F(2,2*n-1)
            for parity in (0,1):
                pole=n if n%2==parity else n+1
                out.append(invert(fmt,15,tag+'-sign'+str(parity),threshold,F(0),F(1,2),pole))
                if tag=='gamma-normal':out.append(invert(fmt,15,'gamma-rounded-normal-sign'+str(parity),midpoint,F(0),F(1,2),pole))
    out.extend(lgamma_seeds())
    for fmt,op,tag,a in list(out):
        if op==13:out.append([fmt,op,tag+'-negative',list(r.raw(fmt,-r.value(fmt,tuple(a))))])
    return out

def oracle(row):
    direct=r.special(row)
    if direct is not None:return direct
    _,fmt,op,*_=row
    # Reuse the independently implemented instrument, projecting Float inputs
    # exactly into binary64. No finite production cutoff supplies an answer.
    projected=row if fmt!=32 else [row[0],64,op,*r.c.raw(64,r.value(32,tuple(row[3:5]))),0,0]
    reference=o.oracle(projected)
    if fmt==32 and 'interval'in reference:
        lo,hi=(int(v,16)*F(2)**reference['interval'][2]for v in reference['interval'][:2])
        reference['range']='overflow'if min(abs(lo),abs(hi))>=r.virtual(32)else'finite'if max(abs(lo),abs(hi))<=r.limit(32)else'edge'
    return reference

def derive():
    runtime();actual=seeds()
    assert actual==r.SEAMS,'independently inverted seam input recipes differ'
    rows=r.population();cells=[]
    for i,row in enumerate(rows):
        try:ref=oracle(row)
        except Exception as error:raise RuntimeError('focused oracle input '+repr(row))from error
        cells.append({'input':row,'reference':ref})
        if i%64==0:print('error/gamma reference',i,'of',len(rows),file=sys.stderr,flush=True)
    return {'schema':1,'oracle':r.PIN,'mpfr_precision':4096,'independent_min_precision':8192,'bound_bits':2304,'population_sha256':hashlib.sha256(r.canonical(rows)).hexdigest(),'cells':cells}

def verify_bytes(committed,derived):
    if committed!=derived:raise ValueError('independent error/gamma regeneration mismatch (no repair performed)')

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--seeds',action='store_true');p.add_argument('--lgamma-seeds',action='store_true');p.add_argument('--verify',action='store_true');a=p.parse_args()
    runtime();data=lgamma_seeds()if a.lgamma_seeds else seeds()if a.seeds else derive();payload=r.canonical(data)
    if a.verify:
        verify_bytes(a.out.read_bytes(),payload)
    else:o.write_new(a.out,payload)
    if a.verify and not(a.seeds or a.lgamma_seeds):
        import copy
        changed=copy.deepcopy(data);cell=next(v for v in changed['cells']if 'interval'in v['reference']);cell['reference']['interval'][2]+=1
        try:
            verify_bytes(r.canonical(changed),payload)
        except ValueError as error:assert 'independent error/gamma regeneration mismatch'in str(error)
        else:raise AssertionError('fully repinned wrong reference escaped required instrument')
    print('error/gamma oracle SHA256',hashlib.sha256(payload).hexdigest(),flush=True)
if __name__=='__main__':main()
