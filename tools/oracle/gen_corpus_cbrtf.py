#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Float cube-root references: independent MPFR/mpmath and exact cube certificates."""
import argparse
from pathlib import Path
import random
from fractions import Fraction
import gmpy2
from mpmath import mp
import mpmath
from gen_corpus_floattrig import (SIGN, INF, QNAN, fraction, power, value, wide,
                                 round32, rational, mpmath_fraction, floor_log2)
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cbrtf_reference import inputs, flags, certify
from gen_corpus_float_scale import publish_set

PROVENANCE = '# Pinned oracle: tools/oracle/gen_corpus_cbrtf.py; MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1'

def answer(raw):
    a=raw&~SIGN
    if a>INF: return QNAN,0,flags(raw)
    if not a or a==INF: return raw,0,0
    x=fraction(raw);unit=power(floor_log2(abs(x))//3-23)
    with gmpy2.context(precision=1200):
        root=rational(gmpy2.cbrt(gmpy2.mpfr(x.numerator)/x.denominator))
    with mp.workprec(1240):
        other=mpmath_fraction(mp.root(mp.mpf(abs(x.numerator))/x.denominator,3))
        if x<0: other=-other
    rb=round32(root);mb=round32(other)
    eb=round32((root-fraction(rb))/unit);me=round32((other-fraction(mb))/unit)
    if (eb&~SIGN)==0: eb=0
    if (me&~SIGN)==0: me=0
    # Exact cubes can acquire tiny high-precision residuals; exact arithmetic settles them.
    if fraction(rb)**3==x: eb=0
    if fraction(mb)**3==x: me=0
    if (rb,eb)!=(mb,me): raise RuntimeError('cbrtf independent oracle disagreement')
    certify(raw,rb,eb)
    return rb,eb,flags(raw)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seed',type=int,default=20261028);p.add_argument('--count',type=int,default=1000);p.add_argument('--fresh',action='store_true');a=p.parse_args()
    if not 0<=a.count<=50000 or not 0<=a.seed<1<<64: p.error('bounded count/seed required')
    if (gmpy2.mpfr_version(),gmpy2.version(),mpmath.__version__)!=('MPFR 4.2.2','2.3.2','1.4.1'):
        raise RuntimeError('incorrect pinned MPFR/gmpy2')
    # Fixed independent controls protect special classes and exact/non-power policy.
    for x,y,e,f in ((0,0,0,0),(SIGN,SIGN,0,0),(INF,INF,0,0),
                    (INF|1,QNAN,0,1),(QNAN|7,QNAN,0,0),
                    (0x3f800000,0x3f800000,0,0),(0x41d80000,0x40400000,0,16)):
        if answer(x)!=(y,e,f): raise RuntimeError('cbrtf fixed reference control failed')
    population=inputs(a.seed,a.count);raw=[];generic=[]
    for word in population:
        result,error,flag=answer(word);raw.append(f'{word:08x} {result:08x} {error:08x} {flag:02x}\n')
        if not ((word&~SIGN)>INF and not word&0x00400000):
            generic.append(f'{wide(word):016x} {wide(result):016x} {error:08x}\n')
    meta=f'# seed {a.seed} count {a.count} fresh {a.fresh} entries '
    payloads={'cbrtf-special.corpus':PROVENANCE+'\n'+meta+str(len(raw))+'\n'+''.join(raw),
              'cbrtf.corpus':PROVENANCE+'\n'+meta+str(len(generic))+'\n'+''.join(generic)}
    a.out.mkdir(parents=True,exist_ok=True);publish_set(a.out,payloads)
    print(f'cbrtf: {len(raw)} raw, {len(generic)} widened rows')
if __name__=='__main__': main()
