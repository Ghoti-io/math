#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Shared independent directed MPFR/mpmath asin/acos reference family.

The population uses raw words, dyadic grids and endpoint neighbours. It reads
no candidate code, coefficients or tables. All seeded answers are retained.
"""
import argparse
import hashlib
import random
import struct
from pathlib import Path
import gmpy2
from mpmath import mp
from fractions import Fraction

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from inverse_trig_reference import SEED, decode, encode, population

def rat(value):
    n,d=value.as_integer_ratio();return Fraction(int(n),int(d))

def answer(word,width,cosine):
    p,bias=(52,1023) if width==64 else (23,127)
    sign=1<<(width-1);a=word&(sign-1);one=bias<<p;inf=(2*bias+1)<<p;nan=inf|(1<<(p-1))
    if a>inf:return nan,int(not a&(1<<(p-1)))
    if a>one:return nan,1
    if not cosine and not a:return word,0
    if cosine and word==one:return 0,0
    flags=2|(4 if not cosine and a<(1<<p) else 0)
    x=decode(word,width)
    for precision in (1200,2400):
        bounds=[]
        for mode in (gmpy2.RoundDown,gmpy2.RoundUp):
            with gmpy2.context(precision=precision,round=mode):
                # Every binary32/64 argument is exactly representable here.
                arg=gmpy2.mpfr(x.numerator)/x.denominator
                if rat(arg)!=x:raise RuntimeError('inexact independent argument')
                bounds.append(rat((gmpy2.acos if cosine else gmpy2.asin)(arg)))
        with mp.workprec(precision+80):
            value=(mp.acos if cosine else mp.asin)(mp.mpf(x.numerator)/x.denominator)
            s,m,e,_=value._mpf_;other=(-1 if s else 1)*Fraction(int(m))*Fraction(2)**int(e)
        targets=[encode(v,width,word==sign and not cosine) for v in bounds+[other]]
        if len(set(targets))!=1:continue
        # Independently agree far more closely than one output ulp, including
        # tiny inputs whose cubic difference needs more than 1200 bits.
        unit=Fraction(2)**max(((targets[0]&(sign-1))>>p)-bias-p,1-bias-p)
        if other<bounds[0]-unit*Fraction(2)**-100 or other>bounds[1]+unit*Fraction(2)**-100:
            raise RuntimeError('MPFR/mpmath disagreement')
        target=targets[0]
        # Outward signed real residual in units of the target's binade ulp.
        errors=[(v-decode(target,width))/unit for v in bounds]
        low=(errors[0]*(1<<30)).numerator//(errors[0]*(1<<30)).denominator
        high=-((-errors[1]*(1<<30)).numerator//(-errors[1]*(1<<30)).denominator)
        return target,flags,low,high
    raise RuntimeError('uncertified reference rounding')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output','--out',type=Path,required=True)
    parser.add_argument('--seed',type=int,default=SEED);parser.add_argument('--count',type=int,default=512)
    args=parser.parse_args()
    if not 0<=args.count<=10000:raise SystemExit('count outside bounds')
    args.output.mkdir(parents=True,exist_ok=True)
    lines=['# inverse-trig-v1 seed=%d count=%d MPFR-directed-1200/2400 mpmath-independent'% (args.seed,args.count),
           '# width input asin-target asin-flags asin-residual-low/high acos-target acos-flags acos-residual-low/high; residual scale=2^30 ULP']
    for width in (64,32):
        for word in population(width,args.seed,args.count):
            values=[]
            for cosine in (False,True):
                result=answer(word,width,cosine)
                if len(result)==2:result=(*result,0,0)
                target,flags,low,high=result;values.extend([format(target,'0%dx'%(width//4)),str(flags),str(low),str(high)])
            lines.append('%d %s %s'%(width,format(word,'0%dx'%(width//4)),' '.join(values)))
    text='\n'.join(lines)+'\n';path=args.output/'inverse-trig.corpus';path.write_text(text)
    (args.output/'inverse-trig.sha256').write_text(hashlib.sha256(text.encode()).hexdigest()+'  inverse-trig.corpus\n')
    print('independent inverse-trig rows',len(lines)-2)
if __name__=='__main__':main()
