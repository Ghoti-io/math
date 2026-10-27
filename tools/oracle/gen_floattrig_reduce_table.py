#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Certify the private binary32 2/pi residue table in the pinned oracle image.

For e = 0..127, C[e] = floor(((2/pi * 2**(e-23)) mod 4) * 2**80).
MPFR directed pi bounds give exact rational bounds on 2/pi (the reciprocal
reverses the endpoints). Modulo and floor use exact Fraction arithmetic.
A row is accepted only if the entire closed interval has the same modulo-4
quotient and the same scaled floor. Independent higher-precision mpmath
arithmetic must lie inside that interval and produce the same row. Uncertain
floor or modulo boundaries escalate precision, then fail closed.

--out names a complete header path. Without --out, write to stdout.
"""
import argparse
from fractions import Fraction
from math import factorial
from pathlib import Path
import sys

import gmpy2
import mpmath
from mpmath import mp
from fitlib import HEADER

FRACTION_BITS = 80
ROW_BITS = FRACTION_BITS + 2
SCALE = 1 << FRACTION_BITS


def rational(value):
    numerator, denominator = value.as_integer_ratio()
    return Fraction(int(numerator), int(denominator))


def mp_rational(value):
    sign, mantissa, exponent, _ = value._mpf_
    return (-1 if sign else 1) * Fraction(int(mantissa)) * Fraction(2) ** exponent


def reciprocal_bounds(pi_low, pi_high):
    if not 0 < pi_low <= pi_high:
        raise ValueError('invalid positive pi interval')
    return Fraction(2) / pi_high, Fraction(2) / pi_low


def certify(low, high):
    """Return the one scaled floor proved by a closed interval, or None."""
    if not 0 <= low <= high:
        raise ValueError('invalid nonnegative phase interval')
    quotient = low // 4
    if quotient != high // 4:
        return None
    low_floor = (low - 4 * quotient) * SCALE // 1
    high_floor = (high - 4 * quotient) * SCALE // 1
    if low_floor != high_floor:
        return None
    result = int(low_floor)
    if not 0 <= result < 1 << ROW_BITS:
        raise RuntimeError('certified residue exceeds 82 bits')
    return result


def independent_floor(value):
    return int((value % 4) * SCALE // 1)


def limbs(coefficient):
    if not 0 <= coefficient < 1 << ROW_BITS:
        raise ValueError('coefficient outside 82-bit range')
    return tuple((coefficient >> shift) & 0xffffffff for shift in (0, 32, 64))


def check_independent(low, high, independent, coefficient, exponent):
    if not low <= independent <= high or independent_floor(independent) != coefficient:
        raise RuntimeError('MPFR/mpmath residue disagreement for exponent %d' % exponent)


def row(exponent):
    for precision in (600, 1200, 2400):
        pi_bounds = []
        for mode in (gmpy2.RoundDown, gmpy2.RoundUp):
            with gmpy2.context(precision=precision, round=mode):
                pi_bounds.append(rational(gmpy2.const_pi()))
        low, high = reciprocal_bounds(*pi_bounds)
        factor = Fraction(2) ** (exponent - 23)
        low, high = low * factor, high * factor
        coefficient = certify(low, high)
        if coefficient is None:
            continue
        with mp.workprec(precision + 40):
            independent = mp_rational(mp.ldexp(2 / mp.pi, exponent - 23))
        check_independent(low, high, independent, coefficient, exponent)
        return limbs(coefficient), precision
    raise RuntimeError('uncertified residue boundary for exponent %d' % exponent)


def require(condition, description):
    if not condition:
        raise RuntimeError('floattrig reduction table self-check failed: ' + description)


def error_budget():
    """Exact nearest-mode bounds for the admitted wide estimate and old path.

    With |stored phase| >= 2^-12, its <2^-56 table error is at most
    2^-44 relative. Binary64 phase construction truncates 53 bits (<=2u),
    then the pi/2 constant and multiplication contribute u each. Both true
    and computed remainders have magnitude <R=.786, including half-phase
    crossings; the chosen quadrant still describes the same angle.

    Expand Horner's rule into weighted Taylor terms. Each sine term has at
    most 17 rounding factors: coefficient 1, reused z error up to 5,
    Horner products 4, Horner sums 4, x*z and final product 2, final sum 1.
    A cosine term has at most 19: coefficient 1, reused z error up to 6,
    Horner products 5, Horner sums 5, final product 1, final sum 1.
    gamma32 bounds either count, even with signed sums, by applying it to
    the absolute term majorant. Geometric majorants bound sinh(R)/R by
    1/(1-R²/6), and cosh(R) by 1/(1-R²/2). Alternating lower bounds for sin
    and cos provide the second denominator in each roundoff bound.
    """
    R = Fraction(393, 500)
    z = R * R
    u = Fraction(1, 1 << 53)
    gamma32 = 32 * u / (1 - 32 * u)
    phase = Fraction(1, 1 << 44)
    construction = (1 + 2 * u) * (1 + u) ** 2 - 1
    reduced_relative = (phase + construction) / (1 - phase)
    sin_polynomial = R ** 12 / (factorial(13) * (1 - z / 6))
    sin_polynomial += gamma32 / (1 - z / 6) ** 2
    cos_polynomial = R ** 14 / (factorial(14) * (1 - z / 2))
    cos_polynomial += gamma32 / (1 - z / 2) ** 2
    # Both sin and cos are 1-Lipschitz. Divide the absolute perturbation by
    # their alternating-series lower bounds on this interval.
    sin_reduction = reduced_relative / (1 - z / 6)
    cos_reduction = R * reduced_relative / (1 - z / 2)
    sine = (1 + sin_polynomial) * (1 + sin_reduction) - 1
    cosine = (1 + cos_polynomial) * (1 + cos_reduction) - 1
    # tan and -cot exchange the numerator and denominator; include the one
    # rounded binary64 division and select the worse relative bound.
    tangent = max((1 + sine) / (1 - cosine),
                  (1 + cosine) / (1 - sine)) * (1 + u) - 1
    estimate = max(sine, cosine, tangent)
    require(estimate < Fraction(1, 1 << 36), 'wide estimate relative budget <2^-36')
    # The established double contract is one true binary64 ULP, <=2u
    # relative on this admitted normal range. Express the combined bound
    # relative to the estimate, which is the gate's scaling value.
    old_difference = (estimate + 2 * u) / (1 - estimate)
    require(old_difference < Fraction(1, 1 << 34), 'legacy compatibility gate budget <2^-34')
    return estimate, old_difference


def self_check():
    require(reciprocal_bounds(Fraction(3), Fraction(4)) ==
            (Fraction(1, 2), Fraction(2, 3)), 'reciprocal endpoint reversal')
    require(certify(Fraction(5, 4), Fraction(5, 4)) == 5 * (1 << 78),
            'known exact floor')
    require(certify(Fraction(21, 4), Fraction(21, 4)) == 5 * (1 << 78),
            'known exact modulo')
    quantum = Fraction(1, SCALE)
    # An endpoint exactly at the next floor is uncertainty, even if almost
    # the entire interval would select the preceding coefficient.
    require(certify(7 * quantum, 8 * quantum) is None,
            'adversarial closed upper endpoint rejected')
    require(certify(Fraction(4) - quantum / 8, Fraction(4) + quantum / 8) is None,
            'adversarial modulo wrap rejected')
    require(certify(7 * quantum - quantum / 8, 7 * quantum + quantum / 8) is None,
            'adversarial interior floor boundary rejected')
    require(certify(7 * quantum, 8 * quantum - quantum / 8) == 7,
            'one floor interval accepted')
    require(limbs((1 << ROW_BITS) - 1) == (0xffffffff, 0xffffffff, 0x3ffff),
            'little-significance limbs and top 18 bits')
    try:
        check_independent(Fraction(1), Fraction(2), Fraction(3, 2), 0, 0)
    except RuntimeError:
        pass
    else:
        raise RuntimeError('floattrig reduction table self-check accepted mismatching row')
    try:
        reciprocal_bounds(Fraction(4), Fraction(3))
    except ValueError:
        pass
    else:
        raise RuntimeError('floattrig reduction table self-check accepted reversed bounds')
    return error_budget()


def render(rows, precision):
    lines = [HEADER.rstrip(), '''/**
 * @file
 * Private 2/pi residues generated by tools/oracle/gen_floattrig_reduce_table.py.
 * Regenerate with oracle.py fit-floattrig-reduce; do not edit.
 * Pinned oracle: MPFR %s gmpy2 %s mpmath %s.
 * Directed MPFR pi bounds at %d bits certify each exact rational floor;
 * independent mpmath at %d bits agrees with every coefficient.
 * C[e] = floor(((2/pi * 2^(e-23)) mod 4) * 2^80), e = 0..127.
 * Three uint32_t limbs are ordered least significant first; the top limb
 * contains 18 significant bits. The stored coefficient has 80 fraction bits.
 */
#ifndef GHOTI_IO_GMATH_SRC_ELEMENTARY_FLOATTRIG_REDUCE_TABLE_H
#define GHOTI_IO_GMATH_SRC_ELEMENTARY_FLOATTRIG_REDUCE_TABLE_H

#include <ghoti.io/math/macros.h>
#include <stdint.h>

static const uint32_t floattrig_reduce_table[128][3] = {''' %
        (gmpy2.mpfr_version().split()[-1], gmpy2.version(), mpmath.__version__,
         precision, precision + 40)]
    for exponent, entry in enumerate(rows):
        lines.append('  /* %3d */ {0x%08xu, 0x%08xu, 0x%08xu},' %
                     ((exponent,) + entry))
    lines += ['};', '', '#endif /* GHOTI_IO_GMATH_SRC_ELEMENTARY_FLOATTRIG_REDUCE_TABLE_H */', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    estimate_budget, old_budget = self_check()
    certified = [row(exponent) for exponent in range(128)]
    rows = [entry for entry, _ in certified]
    precision = max(bits for _, bits in certified)
    output = render(rows, precision)
    if args.out is None:
        sys.stdout.write(output)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output)
    print('floattrig reduction table: 128 certified 82-bit residues; maximum precision %d bits' % precision,
          file=sys.stderr)
    print('floattrig exact-Fraction relative budgets: estimate %.9g < 2^-36; old-path difference %.9g < 2^-34' %
          (float(estimate_budget), float(old_budget)), file=sys.stderr)


if __name__ == '__main__':
    main()
