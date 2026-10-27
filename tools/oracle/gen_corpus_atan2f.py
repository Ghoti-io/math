#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent pinned binary32 atan2(y,x) references.

Directed MPFR1200 atan2 and independent mpmath1240 certify direct rational
Float result/error rounding; ambiguous boundaries escalate to2400 bits.
Expected references never read candidate source or implementation tables.
Rows hold exact widened binary64 y/x/result and signed Float true-ULP error.
"""
import argparse
from pathlib import Path
import random
import tempfile
import gmpy2
import mpmath
from mpmath import mp
from gen_corpus_floattrig import (SIGN, INF, QNAN, Fraction, value, wide,
                                 power, fraction, round32, rational,
                                 mpmath_fraction, ulp_exp)
ONE = 0x3f800000
WITNESSES = ((1,0x40000000),(3,0x40000000),(0x00ffffff,0x40000000),
             (1,INF-1),(ONE,ONE),(0x30800000,ONE),(0x3e000000,ONE),
             (0x3e080000,ONE),(0x007fffff,ONE),(0x00800000,ONE))


def signaling(raw):
    return (raw & ~SIGN) > INF and not raw & 0x00400000


def zero_angle(y,x):
    a,b=y & ~SIGN,x & ~SIGN
    return (a==0 and not x & SIGN) or (a<INF and x==INF)


def pi_multiple(y,x):
    a,b=y & ~SIGN,x & ~SIGN
    negative=bool(x & SIGN)
    if a==0: return Fraction(1)
    if b==0 or (a==INF and b!=INF): return Fraction(1,2)
    if b==INF: return Fraction(3 if negative else 1,4) if a==INF else Fraction(1)
    if a==b: return Fraction(3 if negative else 1,4)
    return None


def evaluate(y,x,precision):
    factor=pi_multiple(y,x)
    bounds=[]
    for mode in (gmpy2.RoundDown,gmpy2.RoundUp):
        with gmpy2.context(precision=precision,round=mode):
            if factor is not None:
                angle=gmpy2.const_pi()*factor.numerator/factor.denominator
            else:
                angle=gmpy2.atan2(gmpy2.mpfr(value(y & ~SIGN)),gmpy2.mpfr(value(x)))
            bounds.append(rational(angle))
    low,high=bounds
    with mp.workprec(precision+40):
        independent=mpmath_fraction(mp.pi*factor.numerator/factor.denominator if factor is not None else
                                   mp.atan2(mp.mpf(value(y & ~SIGN)),mp.mpf(value(x))))
    if y & SIGN: low,high,independent=-high,-low,-independent
    if abs(independent-(low+high)/2)>max(abs(low),abs(high))*power(-precision+8):
        raise RuntimeError('MPFR/mpmath value disagreement: atan2f(%08x,%08x)'%(y,x))
    if not low or not high or (low<0)!=(high<0) or ulp_exp(low)!=ulp_exp(high): return None
    result=round32(low)
    if result!=round32(high) or result!=round32(independent): return None
    unit=power(ulp_exp(low))
    errors=[(v-fraction(result))/unit for v in (low,high,independent)]
    error=round32(errors[0])
    if any(round32(v)!=error for v in errors[1:]): return None
    return result,error


def answer(y,x):
    if (y & ~SIGN)>INF or (x & ~SIGN)>INF: return QNAN,0
    if zero_angle(y,x): return y & SIGN,0
    for precision in (1200,2400):
        result=evaluate(y,x,precision)
        if result is not None: return result
    raise RuntimeError('uncertified binary32 rounding boundary: atan2f(%08x,%08x)'%(y,x))


def require(condition,description):
    if not condition: raise RuntimeError('atan2f oracle self-check failed: '+description)


def write_corpus(destination, population, seed, count, fresh, reference=answer):
    maximum, temporary = (Fraction(0), (0, 0)), None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=destination.parent,
                                         prefix='.' + destination.name + '.',
                                         suffix='.tmp', delete=False) as out:
            temporary = Path(out.name)
            out.write('# Pinned oracle: tools/oracle/gen_corpus_atan2f.py; MPFR %s gmpy2 %s mpmath %s\n' %
                      (gmpy2.mpfr_version().split()[-1], gmpy2.version(), mpmath.__version__))
            out.write('# function atan2f\n')
            out.write('# seed %d count %d fresh %s entries %d\n' % (seed, count, fresh, len(population)))
            out.write('# binary32 y/x/results widened exactly to binary64; signed binary32 error in true binary32 ULP\n')
            for x, y in population:
                result, error = reference(x, y)
                out.write('%016x %016x %016x %08x\n' % (wide(x), wide(y), wide(result), error))
                if abs(fraction(error)) > maximum[0]:
                    maximum = abs(fraction(error)), (x, y)
        temporary.chmod(destination.stat().st_mode & 0o777 if destination.exists() else 0o644)
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return maximum


def self_check():
    for y,x,result in ((0,0,0),(SIGN,0,SIGN),(0,SIGN,0x40490fdb),
            (SIGN,SIGN,0xc0490fdb),(ONE,INF,0),(ONE|SIGN,INF,SIGN),
            (INF,INF,0x3f490fdb),(INF,INF|SIGN,0x4016cbe4),
            (INF,ONE,0x3fc90fdb),(QNAN,INF,QNAN),(INF,QNAN,QNAN),
            (INF|1,ONE,QNAN),(ONE,INF|1,QNAN),
            (1,0x40000000,0),(3,0x40000000,1),(0xffffff,0x40000000,0x7fffff)):
        require(answer(y,x)[0]==result,'special/tiny target')
    for y,x in ((ONE,ONE),(ONE|SIGN,ONE),(ONE,ONE|SIGN),(ONE,0),(0,ONE|SIGN)):
        result,error=answer(y,x)
        require(error & ~SIGN !=0,'nonzero pi angle actual signed error')
        require(answer(y^SIGN,x)==(result^SIGN,error^SIGN),'actual angle/error sign symmetry')
    require(answer(1,ONE)==(1,SIGN),'actual tiny negative-zero error')
    require(answer(1|SIGN,ONE)==(1|SIGN,0),'actual tiny positive-zero error')
    require(answer(ONE,ONE)==(0x3f490fdb,0xbebbbd2e),'actual pi/4 signed-error pair')
    require(answer(ONE|SIGN,ONE)==(0xbf490fdb,0x3ebbbd2e),'actual negative pi/4 signed-error pair')
    require(answer(ONE,0x40000000)==(0x3eed6338,0x3e2c376a),'actual atan half signed-error pair')
    for lower in (0,1,2,0x007fffff,0x00800000,0x3f7fffff,ONE):
        midpoint=(fraction(lower)+fraction(lower+1))/2
        require(round32(midpoint)==lower+(lower&1),'direct odd/even tie rounding')
    # First/second/late failures preserve absence or existing bytes and clean
    # temporary output; successful atomic publication preserves readable modes.
    for population, fail_at, existing in (([(0, 0)], (0, 0), False),
            ([(0, 0), (0, ONE)], (0, ONE), True),
            ([(0, 0), (0, ONE), (ONE, ONE)], (ONE, ONE), True)):
        with tempfile.TemporaryDirectory(prefix='atan2f-atomic-selfcheck-') as directory:
            destination = Path(directory) / 'atan2f.corpus'
            original = b'previous certified corpus\n'
            if existing:
                destination.write_bytes(original)
            def failure(x, y):
                if (x, y) == fail_at:
                    raise ArithmeticError('planted reference failure')
                return answer(x, y)
            try:
                write_corpus(destination, population, 1, 0, False, failure)
            except ArithmeticError:
                pass
            else:
                raise RuntimeError('atan2f oracle accepted planted failure')
            require(destination.read_bytes() == original if existing else not destination.exists(),
                    'failed publication preserves destination')
            require(list(Path(directory).iterdir()) == ([destination] if existing else []),
                    'failed publication cleans temporary file')
    for mode in (None, 0o640, 0o644):
        with tempfile.TemporaryDirectory(prefix='atan2f-mode-selfcheck-') as directory:
            destination = Path(directory) / 'atan2f.corpus'
            if mode is not None:
                destination.write_bytes(b'previous\n'); destination.chmod(mode)
            write_corpus(destination, [(0, 0)], 1, 0, False)
            require(destination.stat().st_mode & 0o777 == (0o644 if mode is None else mode),
                    'atomic readable permissions')


def inputs(seed,count,fresh):
    rng=random.Random(seed);seen=set();rows=[]
    def add(y,x):
        if not 0<=y<=0xffffffff or not 0<=x<=0xffffffff: return
        if signaling(y) or signaling(x) or (y,x) in seen: return
        seen.add((y,x));rows.append((y,x))
    def symmetries(y,x):
        for sy in (0,SIGN):
            for sx in (0,SIGN):
                add(y|sy,x|sx);add(x|sx,y|sy)
    specials=(0,SIGN,1,SIGN|1,0x7fffff,0x800000,ONE,ONE|SIGN,INF-1,INF,INF|SIGN,QNAN,QNAN|SIGN|7)
    for y in specials:
        for x in specials: add(y,x)
    for pair in WITNESSES: symmetries(*pair)
    for exponent in range(1,255):
        a=(exponent<<23)|rng.getrandbits(23)
        for mantissa in (0,1,0x7fffff):
            symmetries((exponent<<23)|mantissa,a)
            symmetries((exponent<<23)|mantissa,1)
            symmetries((exponent<<23)|mantissa,ONE)
    for bit in range(23):
        for a in (1<<bit,(1<<(bit+1))-1): symmetries(a,1);symmetries(a,ONE)
    # Tiny/direct thresholds and every table center/half-seam, with both
    # adjacent Float words; all quadrants and swaps are included.
    for raw in (0x30800000,0x3e000000):
        for delta in range(-2,3): symmetries(raw+delta,ONE)
    for j in range(8,65):
        for q in (Fraction(j,64),Fraction(2*j+1,128)):
            raw=round32(q)
            for delta in (-1,0,1): symmetries(raw+delta,ONE)
    for exponent in (-149,-140,-126,-100,-30,-1,0,1,100,127):
        for gap in (0,1,29,30,31,125,126,149,150,151,276):
            a=round32(power(exponent));b=round32(power(exponent-gap))
            if a<INF and b: symmetries(b,a)
    # Invert output midpoints in a bounded positive first-octant angle range.
    # Stratification keeps fresh samples meaningful rather than collapsing
    # tiny inverse angles onto the same denominator/zero pair.
    midpoint_pairs=set()
    with mp.workprec(1240):
        for i in range(120 if fresh else 384):
            exponent=rng.randrange(-149,0)
            raw=round32(Fraction(rng.randrange(1<<23,1<<24))*power(exponent-23))
            midpoint=(fraction(raw)+fraction(raw+1))/2
            if not 0<midpoint<Fraction(3,4): continue
            angle=mp.mpf(midpoint.numerator)/midpoint.denominator
            denominator=round32(power(rng.randrange(-120,121)))
            ratio=mp.tan(angle)*mp.mpf(value(denominator))
            y=round32(mpmath_fraction(ratio))
            for delta in (-1,0,1):
                if 0<y+delta<INF: symmetries(y+delta,denominator);midpoint_pairs.add((y+delta,denominator))
    require(len(midpoint_pairs)>=50,'distinct finite inverse midpoint candidates')
    for _ in range(count):
        add(rng.getrandbits(32),rng.getrandbits(32))
        add(round32(Fraction.from_float(rng.uniform(-1000,1000))),round32(Fraction.from_float(rng.uniform(-1000,1000))))
    return rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir','--out',dest='outdir',required=True,type=Path)
    parser.add_argument('--seed',type=int,default=20261027)
    parser.add_argument('--count',type=int,default=3000)
    parser.add_argument('--fresh',action='store_true')
    args=parser.parse_args()
    if args.count<0:parser.error('--count must be nonnegative')
    self_check()
    population=inputs(args.seed,args.count,args.fresh)
    args.outdir.mkdir(parents=True,exist_ok=True)
    maximum=write_corpus(args.outdir/'atan2f.corpus',population,args.seed,args.count,args.fresh)
    print('atan2f: %d entries; max reference error %.9g ULP at %08x,%08x' %
          (len(population),float(maximum[0]),*maximum[1]),flush=True)


if __name__=='__main__':main()
