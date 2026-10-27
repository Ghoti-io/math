#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent proof evidence; run in the pinned oracle image.

This checks implementation constants and a mathematical error budget. It is
separate from gen_corpus_logf.py, whose reference values never read tables.
All inequalities below use exact Fractions or directed MPFR enclosures.
"""
if not __debug__:
    raise SystemExit("logf budget certificate requires assertions; run without -O/PYTHONOPTIMIZE")

from fractions import Fraction as F
from pathlib import Path
import re
import struct
import gmpy2
from mpmath import mp

root = Path(__file__).resolve().parents[2]
text = (root / 'src/elementary/explog_tables.h').read_text()
def fraction(v):
    n, d = v.as_integer_ratio()
    return F(int(n), int(d))
def mp_fraction(v):
    sign, mantissa, exponent, _ = v._mpf_
    return (-1 if sign else 1) * F(int(mantissa)) * F(2) ** exponent
def directed_log(v):
    out = []
    for mode in (gmpy2.RoundDown, gmpy2.RoundUp):
        with gmpy2.context(precision=600, round=mode):
            arg = gmpy2.mpfr(v.numerator) / v.denominator
            assert fraction(arg) == v
            out.append(fraction(gmpy2.log(arg)))
    with mp.workprec(640):
        independent = mp_fraction(mp.log(mp.mpf(v.numerator) / v.denominator))
    assert out[0] <= independent <= out[1]
    return out
def bits_fraction(bits):
    return F.from_float(struct.unpack('>d', struct.pack('>Q', bits))[0])

body = text.split('static const double gmath_log_rows', 1)[1].split('{', 1)[1].split('};', 1)[0]
rows = re.findall(r'\{([^{}]+)\}', body)
assert len(rows) == 128
ones, maximum, denominator = [], F(0), 0
for j, row in enumerate(rows):
    words = re.findall(r'-?0x[0-9a-f]+\.[0-9a-f]+p[+-][0-9]+', row)
    c, hi, lo = [F.from_float(float.fromhex(x)) for x in words[:3]]
    assert F(1, 2) < c < 2
    lower, upper = directed_log(c)
    assert max(abs(hi + lo + lower), abs(hi + lo + upper)) < F(2) ** -90
    if c == 1:
        assert hi == lo == 0
        ones.append(j)
    for bits in (0x3fe6a00000000000 + (j << 45),
                 0x3fe6a00000000000 + ((j + 1) << 45) - (1 << 29)):
        z = bits_fraction(bits) * c - 1
        maximum = max(maximum, abs(z))
        denominator = max(denominator, z.denominator.bit_length() - 1)
assert ones == [74, 75] and maximum < F(1, 128) and denominator <= 49
assert bits_fraction(0x3fe6a00000000000 + (74 << 45)) == F(255, 256)
assert bits_fraction(0x3fe6a00000000000 + (76 << 45)) == F(129, 128)

hi, lo = [F.from_float(float.fromhex(re.search(r'#define ' + name + r' (\S+)', text).group(1)))
          for name in ('GMATH_LN2_HI', 'GMATH_LN2_LO')]
assert max(abs(hi + lo - v) for v in directed_log(F(2))) < F(2) ** -90
assert (hi + lo).numerator.bit_length() == 93
c5 = F.from_float(float.fromhex('0x1.999999999999ap-3'))
assert c5 == F(3602879701896397, 1 << 54) and 3 * c5.numerator > 1 << 53

# The polynomial's expanded terms have fewer than16 rounded factors.
# Remainder T and evaluation P are absolute; gamma8 covers reconstruction.
R, u = F(1, 128), F(1, 1 << 53)
g16, g8 = 16*u/(1-16*u), 8*u/(1-8*u)
T = R**6 / (6*(1-R))
P = g16*R/(1-R)
constant = F(2)**-90
# Near one: |ln(1+z)| >= |z|/(1+R), with no table/exponent cancellation.
near = R**5*(1+R)/(6*(1-R)) + g16*(1+R)/(1-R)
# Else e=0 gives |ln x|>=1/256 and term majorant<1. For e!=0,
# m in[181/256,181/128) gives |ln x|>1/4 and majorant<150.
other_e0 = 256*(T+P+g8+constant)
other_e = 4*(T+P+150*g8+150*constant)
worst = max(near, other_e0, other_e)
assert worst < F(2)**-36
for label, value in (('near-one relative', near), ('other/e0 relative', other_e0),
                     ('e!=0 relative', other_e), ('float-ULP budget', F(1,2)+worst*(1<<24))):
    print(label, '%.14g' % float(value))
print('PASS: directed constants, exact front, one-region, IX arithmetic and budget')
