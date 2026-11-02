#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent directed MPFR/mpmath sinh/cosh/tanh targets and error cells."""
import argparse,hashlib,sys
from pathlib import Path
from fractions import Fraction
import gmpy2
from mpmath import mp
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hyperbolic_reference import SEED,decode,encode,population

def rat(x):
    n,d=x.as_integer_ratio();return Fraction(int(n),int(d))

def certify_overflow():
    for width,cut in [(64,0x408633ce8fb9f87e),(32,0x42b2d4fd)]:
        p,bias=(52,1023) if width==64 else (23,127)
        maximum=decode(((2*bias+1)<<p)-1,width)
        boundary=Fraction(2)**(bias+1)-Fraction(2)**(bias-p-1)
        for fn in [gmpy2.sinh,gmpy2.cosh]:
            for word,over in [(cut-1,False),(cut,True)]:
                q=decode(word,width);bounds=[]
                for mode in [gmpy2.RoundDown,gmpy2.RoundUp]:
                    with gmpy2.context(precision=1200,round=mode):bounds.append(rat(fn(gmpy2.mpfr(q.numerator)/q.denominator)))
                if (over and bounds[0]<boundary) or (not over and bounds[1]>maximum):raise RuntimeError('uncertified hyperbolic overflow/max cutoff')
    print('adjacent Double/Float sinh/cosh overflow inputs certified; predecessors <=MAX')

def answer(word,width,kind):
    p,bias=(52,1023) if width==64 else (23,127)
    sign=1<<(width-1);a=word&(sign-1);inf=(2*bias+1)<<p;nan=inf|(1<<(p-1));one=bias<<p
    outsign=word&sign if kind!=1 else 0
    if a>inf:return nan,int(not(a&(1<<(p-1)))),0,0
    if not a:return one if kind==1 else word,0,0,0
    if a==inf:return outsign|(one if kind==2 else inf),0,0,0
    cut=0x408633ce8fb9f87e if width==64 else 0x42b2d4fd
    if kind!=2 and a>=cut:return outsign|inf,10,0,0
    x=decode(word,width)
    if kind==2 and abs(x)>=1280:
        # e>2 and 1-tanh(a)<2*exp(-2a) imply <2^-30 of either
        # target spacing; keep outward signed cells without huge exponents.
        return outsign|one,2,0 if outsign else -1,1 if outsign else 0
    fn=[gmpy2.sinh,gmpy2.cosh,gmpy2.tanh][kind]
    other_fn=[mp.sinh,mp.cosh,mp.tanh][kind]
    for precision in [1200,2400]:
        bounds=[]
        for mode in [gmpy2.RoundDown,gmpy2.RoundUp]:
            with gmpy2.context(precision=precision,round=mode):
                arg=gmpy2.mpfr(x.numerator)/x.denominator
                if rat(arg)!=x:raise RuntimeError('input decoding drift')
                bounds.append(rat(fn(arg)))
        with mp.workprec(precision+80):
            value=other_fn(mp.mpf(x.numerator)/x.denominator)
            s,m,e,_=value._mpf_;other=(-1 if s else 1)*Fraction(int(m))*Fraction(2)**int(e)
        targets=[encode(v,width) for v in bounds+[other]]
        if len(set(targets))!=1:continue
        target=targets[0];absolute=target&(sign-1)
        if absolute>=inf:raise RuntimeError('unexpected finite-input overflow')
        unit=Fraction(2)**max((absolute>>p)-bias-p,1-bias-p)
        if other<bounds[0]-unit*Fraction(2)**-100 or other>bounds[1]+unit*Fraction(2)**-100:raise RuntimeError('MPFR/mpmath disagreement')
        errors=[(v-decode(target,width))/unit for v in bounds]
        scaled=errors[0]*(1<<30);low=scaled.numerator//scaled.denominator
        scaled=-errors[1]*(1<<30);high=-(scaled.numerator//scaled.denominator)
        return target,2|(4 if absolute<(1<<p) else 0),low,high
    raise RuntimeError('uncertified result rounding')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out','--output',type=Path,required=True)
    parser.add_argument('--midpoint-search',action='store_true')
    parser.add_argument('--seed',type=int,default=SEED);parser.add_argument('--count',type=int,default=512);a=parser.parse_args()
    if not(0<=a.seed<1<<64 and 0<=a.count<=10000):raise SystemExit('seed/count outside bounds')
    certify_overflow();lines=['# hyperbolic-v1 seed=%d count=%d MPFR-directed-1200/2400 mpmath-independent'%(a.seed,a.count),
        '# width input sinh-target/flags/residual-low/high cosh-target/flags/residual-low/high tanh-target/flags/residual-low/high; residual scale=2^30 ULP']
    if a.midpoint_search:lines[0]+=' midpoint-search=1'
    for width in [64,32]:
        for word in population(width,a.seed,a.count,adversarial=not a.midpoint_search):
            values=[]
            for kind in range(3):
                target,flags,low,high=answer(word,width,kind);values.extend([format(target,'0%dx'%(width//4)),str(flags),str(low),str(high)])
            lines.append('%d %s %s'%(width,format(word,'0%dx'%(width//4)),' '.join(values)))
    data=('\n'.join(lines)+'\n').encode();a.out.mkdir(parents=True,exist_ok=True)
    (a.out/'hyperbolic.corpus').write_bytes(data);(a.out/'hyperbolic.sha256').write_text(hashlib.sha256(data).hexdigest()+'  hyperbolic.corpus\n')
    print('independent hyperbolic rows',len(lines)-2)
if __name__=='__main__':main()
