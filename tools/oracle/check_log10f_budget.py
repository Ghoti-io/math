#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Certify the binary32 base-ten logarithm's mathematical error budget.

Run in the pinned oracle image. The natural-log front uses exact24x26-bit
products and a five-term log1p series. This check is separate from the corpus
oracle: expected log10f values never read implementation tables/constants.
All inequalities use exact Fractions or independently checked directed MPFR
bounds. The calculation assumes nearest binary64 arithmetic and disabled
contraction, matching the library's numerical build contract.
"""
import argparse
from fractions import Fraction as F
from pathlib import Path
import re
import struct
import gmpy2
from mpmath import mp

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=root / 'src/elementary/explog.c',
                    help='source whose numerical model is certified (supports staged checks)')
args = parser.parse_args()

# This is a deliberately narrow source-model guard, not formal C verification.
# The error budget counts operations and assumes these exact rounded Taylor
# coefficients. Whitespace/comments may change; evaluation/coefficient drift
# requires a reviewed update of both the analytical budget and this model.
def compact(source):
    source = re.sub(r'/\*.*?\*/|//[^\n]*', '', source, flags=re.S)
    return re.sub(r'\s+', '', source)
def function_body(source, name):
    match = re.search(r'\b' + re.escape(name) + r'\s*\([^)]*\)\s*\{', source)
    if match is None:
        raise RuntimeError('source-model guard: missing ' + name)
    start = match.end()
    depth = 1
    for end in range(start, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end]
    raise RuntimeError('source-model guard: unbalanced ' + name)
source = re.sub(r'/\*.*?\*/|//[^\n]*', '', args.source.read_text(), flags=re.S)
helper = function_body(source, 'logf_positive')
model = """
uint64_t lf_xb = gmath_bits(lf_x);
uint64_t lf_tmp = lf_xb - GMATH_LOG_OFF;
int64_t lf_e = (int64_t)lf_tmp >> 52;
unsigned lf_j = (unsigned)((lf_tmp >> (52 - GMATH_LOG_ROW_BITS)) & ((1u << GMATH_LOG_ROW_BITS) - 1u));
double lf_m = gmath_double(lf_xb - ((uint64_t)lf_e << 52));
const double * lf_row = gmath_log_rows[lf_j];
double lf_z = lf_m * lf_row[0] - 1.0;
double lf_p = lf_z + (lf_z * lf_z) * (-0.5 + lf_z * (0x1.5555555555555p-2 + lf_z * (-0.25 + lf_z * 0x1.999999999999ap-3)));
double lf_ed = gmath_small_int((int)lf_e);
double lf_a = lf_ed * GMATH_LN2_HI + lf_row[1];
double lf_tail = (lf_ed * GMATH_LN2_LO + lf_row[2]) + lf_p;
return lf_a + lf_tail;
"""
if compact(helper) != compact(model):
    raise RuntimeError('source-model guard: logf_positive coefficient/evaluation structure drift')
conversion = compact(function_body(source, 'gmath_log10f'))
if not conversion.endswith('return(float)(logf_positive((double)x)*GMATH_LOG10_INV_HI);'):
    raise RuntimeError('source-model guard: log10f final conversion drift')
coefficients = re.findall(r'0x[0-9a-f]+\.[0-9a-f]+p[+-][0-9]+', helper)
if len(coefficients) != 2:
    raise RuntimeError('source-model guard: unexpected polynomial constants')
actual_c3, actual_c5 = [F.from_float(float.fromhex(v)) for v in coefficients]
text = (root / 'src/elementary/explog_tables.h').read_text()
offset = re.search(r'#define GMATH_LOG_OFF (\S+)', text).group(1).rstrip('uUlL')
row_bits = re.search(r'#define GMATH_LOG_ROW_BITS (\d+)', text).group(1)
assert int(offset, 16) == 0x3fe6a00000000000 and int(row_bits) == 7
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
    assert c.numerator.bit_length() <= 26
    assert (hi * (1 << 41)).denominator == 1 and abs(hi) < F(1,2)
    assert abs(lo) <= F(2) ** -42
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
assert 0 < hi < 1 and hi.numerator.bit_length() <= 41 and abs(lo) < F(2) ** -41
assert (hi * (1 << 41)).denominator == 1
assert abs(actual_c3 / F(1,3) - 1) <= F(1,1 << 53)
assert actual_c5 == F(3602879701896397, 1 << 54) and 3 * actual_c5.numerator > 1 << 53

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
# Existing rounded high reciprocal is sufficient at binary32 precision.
base_constants = (root / 'src/elementary/logbase_constants.h').read_text()
inv_word = re.search(r'#define GMATH_LOG10_INV_HI (\S+)', base_constants).group(1)
inv = F.from_float(float.fromhex(inv_word))
log10_bounds = directed_log(F(10))
assert max(abs(inv * v - 1) for v in log10_bounds) < u
converted = (1 + worst) * (1 + u) ** 2 - 1
float_budget = F(1,2) + converted * (1 << 24)
assert converted < F(2) ** -36
assert float_budget < F(51,100)
# Exact input powers10^n need the odd significand5^n to fit24 bits.
assert (5 ** 10).bit_length() == 24 and (5 ** 11).bit_length() == 26
for label, value in (('near-one natural relative', near), ('other/e0 natural relative', other_e0),
                     ('e!=0 natural relative', other_e), ('base-ten relative', converted),
                     ('float-ULP budget', float_budget),
                     ('conversion ULP increment', (converted - worst) * (1 << 24))):
    print(label, '%.14g' % float(value))
print('PASS: source-model guard, directed constants, exact front, one-region, IX arithmetic, decimal powers and log10f budget')
