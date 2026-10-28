#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
#
# Copyright (C) 2026 Corey Pennycuff
#
# This file is part of Ghoti.io Math.
#
# Ghoti.io Math is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
"""Show that the checks of the exact functions fail on planted defects (story 4a).

The companion of check-planted-elem.py for src/elementary/sqrt_impl.h, sqrt.c,
round.c and scale.c: gmath_sqrt and its two variants, floor, ceil, trunc,
round, rint, fabs, copysign, scalbn, ldexp, frexp and ilogb.  A test that has
never been seen to fail may measure nothing.  For each defect below, this
builds a copy of those sources with one literal replacement applied (the
replacement must match exactly once and must change the file), links testBasic
against the copy and requires the check named for it to fail.  The unplanted
copy is the control: it must pass.

Four families:

  test     the defect must fail testBasic (the corpus, the exact reference, the
           Annex F rows, the exceptions); several are also required to change the
           corpus hash, which is what the cross-target gate compares
  variant  a defect in one square-root variant only: the probe must report
           math.variants.mismatch (and exit 1), and testBasic must fail
  build    a build flag that silently loses the hardware path
  corpus   a defect in the oracle's data, not the library: a wrong answer, a
           truncated file, a missing file and a changed hash line, which the
           tests must refuse

What is NOT planted, and why (story 4a).  The portable square root ends in an
exact test of the residual, so everything that only makes its first estimate
worse is absorbed as long as the estimate stays within one unit of the last place
of the answer, and cannot be seen by any test that runs the function:

  - the term (1 + (s0 - c) r / 2) of the estimate, dropped altogether: it is a
    2^-26 relative change of the correction, which is itself 2^-26 of y, so 2^-52
    of y, a unit in the last place, which the correction then repairs; its
    wrong sign is planted and seen (by the internal test, which bounds the
    estimate)
  - that gmath_sqrt_hardware runs the instruction and not the portable method:
    the two are bit-identical by design, so no result shows it.  The inexact
    flag does (the instruction raises it only for an inexact root, the portable
    method always) and testBasic checks that, which is the plant that is
    seen; a build that loses the instruction altogether is the build plant
  - the starting table of the reciprocal square root: a start off by less than
    2^-9 changes no result (as for hypot); a start off by more is seen by
    testElementary_tables, which checks every entry
  - the number of Newton steps beyond what the estimate needs: a third step
    changes no bit
  - the underflow flag raised by scalbn for a tiny inexact result (no test of
    the flag distinguishes the planted omission from the compiler dropping the
    volatile read; the Annex F rows check the value, and testBasic checks the flag
    for the one case) and the threshold s > 54 of its shift (a shift of 55 gives
    the same zero)
  - gmath_ldexp's body is gmath_scalbn's, and a plant that makes it differ is
    planted below
  - scalbn's threshold between the normal path and the subnormal one at a
    biased exponent of 1: at that exponent the two paths give the same bits (a
    shift by 0 leaves the significand with its hidden bit in the exponent's
    lowest bit), so moving the threshold by one changes no result
  - the factor 2^54 that normalizes a subnormal argument: any factor of 2^52 or
    more gives the same significand and exponent (2^53 is the plant that was
    tried and changed nothing); 2^50 is planted and seen
  - that the exponent of a zero, an infinity or a NaN is stored as 0 by frexp is
    seen by the corpus test, not by the hash probe, which initializes the
    exponent itself

Run by `make check-planted` from the library directory, with the build's
compile and link flags in the PLANT_* environment variables.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SRC = Path("src/elementary")
CORPUS = Path("tests/corpus")
SOURCES = ("elem_common.h", "hypot_table.h", "sqrt_impl.h", "sqrt.c", "round.c", "scale.c", "hypot.c")
# The objects built from the staged copy; the Makefile's own objects stand in for the others.
STAGED_OBJECTS = ("sqrt", "round", "scale", "hypot")
OTHER_OBJECTS = ("explog", "atan2", "remainder", "extrema", "cbrt", "floatbasic", "floattrig", "intround", "float_scale", "adjacent", "fraction_split", "exponent_value", "long_scale", "float_cbrt", "ieee_remainder")
CORPUS_TEST = "Basic.CorpusIsExact"
VARIANT_TEST = "Basic.SqrtVariantsAgreeWithEachOtherAndWithTheExactSquareRoot"

failures = []
lock = threading.Lock()


def say(msg, err=False):
    with lock:
        (sys.stderr if err else sys.stdout).write(msg + "\n")
        (sys.stderr if err else sys.stdout).flush()


def fail(msg):
    failures.append(msg)
    say("check-planted-exact: FAIL: %s" % msg, err=True)


S = "sqrt_impl.h"
R = "round.c"
C = "scale.c"
K = "sqrt.c"

# (name, file, old, new, tests that may catch it); the first test named is the one required.
TEST_PLANTS = [
    # --- the portable square root ---
    ("sqrt/portable: one Newton step", S, "  r = r * (1.5 - hm * (r * r));\n  r = r * (1.5 - hm * (r * r));\n", "  r = r * (1.5 - hm * (r * r));\n", (CORPUS_TEST,)),
    ("sqrt/portable: no round-up step", S, "    y += 0x1p-52;\n", "    y += 0.0;\n", (CORPUS_TEST,)),
    ("sqrt/portable: the residual's u/2 for the up test", S, "  if (rho > yu) {", "  if (rho > 0.5 * yu) {", (CORPUS_TEST,)),
    ("sqrt/portable: y split by truncation, not rounding", S, "(gmath_bits(y) + 0x4000000ull) & ~GMATH_SQRT_LOW27", "gmath_bits(y) & ~GMATH_SQRT_LOW27", (CORPUS_TEST, VARIANT_TEST)),
    ("sqrt/portable: the low square dropped from the residual", S, "double e = ((yh * yh - p) + 2.0 * (yh * yl)) + yl * yl;", "double e = ((yh * yh - p) + 2.0 * (yh * yl));", (CORPUS_TEST, VARIANT_TEST)),
    ("sqrt/portable: the cross term dropped from the residual", S, "double e = ((yh * yh - p) + 2.0 * (yh * yl)) + yl * yl;", "double e = ((yh * yh - p)) + yl * yl;", (CORPUS_TEST,)),
    ("sqrt/portable: odd exponents scaled into [1, 2)", S, "uint64_t field = 1024u - ((uint64_t)ex & 1u);", "uint64_t field = 1023u;", (CORPUS_TEST,)),
    ("sqrt/portable: parity the wrong way", S, "uint64_t field = 1024u - ((uint64_t)ex & 1u);", "uint64_t field = 1023u + ((uint64_t)ex & 1u);", (CORPUS_TEST,)),
    ("sqrt/portable: half exponent off by one", S, "int64_t half = (ex - 1023) >> 1;", "int64_t half = (ex - 1022) >> 1;", (CORPUS_TEST,)),
    ("sqrt/portable: subnormal result exponent", S, "    shift = -27;\n", "    shift = -26;\n", (CORPUS_TEST,)),
    ("sqrt/portable: subnormal scaled by 2^52", S, "a = gmath_bits(x * 0x1p54) & GMATH_ABS_MASK;", "a = gmath_bits(x * 0x1p52) & GMATH_ABS_MASK;", (CORPUS_TEST,)),
    ("sqrt/portable: sqrt(-0) is +0", S, "  if (a == 0) {\n    return x; /* sqrt(+-0) is +-0 */\n  }\n", "  if (a == 0) {\n    return 0.0;\n  }\n", (CORPUS_TEST,)),
    ("sqrt/portable: sqrt(-inf) is -inf", S, "return (b & GMATH_SIGN_BIT) ? gmath_invalid() : x; /* sqrt(-inf) is invalid, sqrt(+inf) is +inf */", "return x;", (CORPUS_TEST,)),
    ("sqrt/portable: sqrt(negative) is a number", S, "  if (b & GMATH_SIGN_BIT) {\n    return gmath_invalid();\n  }\n", "  if (b & GMATH_SIGN_BIT) {\n    b &= GMATH_ABS_MASK;\n  }\n", (CORPUS_TEST,)),
    ("sqrt/portable: a signalling NaN is returned as it is", S, "      return gmath_nan_of(x);\n    }\n    return (b & GMATH_SIGN_BIT)", "      return x;\n    }\n    return (b & GMATH_SIGN_BIT)", (CORPUS_TEST, "Basic.SqrtSpecialValues")),
    ("sqrt/portable: invalid not raised for a negative argument", S, "  if (b & GMATH_SIGN_BIT) {\n    return gmath_invalid();\n  }\n", "  if (b & GMATH_SIGN_BIT) {\n    return gmath_double(GMATH_QNAN_BITS);\n  }\n", ("Basic.SqrtRaisesInvalidForANegativeArgumentAndNothingElseButInexact",)),
    # --- the hardware square root ---
    ("sqrt/hardware: a NaN left as the instruction made it", S, "    return gmath_double(GMATH_QNAN_BITS);\n  }\n  return r;", "    return r;\n  }\n  return r;", (CORPUS_TEST, "Basic.SqrtSpecialValues")),
    ("sqrt/hardware: one unit in the last place high for a result above 8", S, "  return r;\n}\n#define gmath_sqrt_impl gmath_sqrt_hardware_impl", "  return r > 8.0 ? r * (1.0 + 0x1p-52) : r;\n}\n#define gmath_sqrt_impl gmath_sqrt_hardware_impl", (CORPUS_TEST, VARIANT_TEST)),
    # --- gmath_sqrt, the entry points ---
    ("sqrt/gmath_sqrt_portable calls the hardware", K, "double gmath_sqrt_portable(double x) {\n  return gmath_sqrt_portable_impl(x);", "double gmath_sqrt_portable(double x) {\n  return gmath_sqrt_impl(x) * 1.0 + (x == 3.0 ? 1e-9 : 0.0);", (CORPUS_TEST,)),
    ("sqrt/gmath_sqrt_hardware runs the portable method (seen by the inexact flag)", K, "double gmath_sqrt_hardware(double x) {\n#ifdef GMATH_HW_SQRT\n  return gmath_sqrt_hardware_impl(x);", "double gmath_sqrt_hardware(double x) {\n#ifdef GMATH_HW_SQRT\n  return gmath_sqrt_portable_impl(x);", ("Basic.SqrtRaisesInvalidForANegativeArgumentAndNothingElseButInexact",)),
    # --- floor, ceil, trunc, round, rint, fabs, copysign ---
    ("round/keep: the fraction mask one bit short", R, "uint64_t frac = ((GMATH_MANT_MASK >> (e & 63u)) & ~neg) | (GMATH_ABS_MASK & neg);", "uint64_t frac = ((GMATH_MANT_MASK >> ((e + 1u) & 63u)) & ~neg) | (GMATH_ABS_MASK & neg);", (CORPUS_TEST,)),
    ("round/keep: the fraction mask one bit long", R, "uint64_t frac = ((GMATH_MANT_MASK >> (e & 63u)) & ~neg) | (GMATH_ABS_MASK & neg);", "uint64_t frac = ((GMATH_MANT_MASK >> ((e - 1u) & 63u)) & ~neg) | (GMATH_ABS_MASK & neg);", (CORPUS_TEST,)),
    ("round/keep: a magnitude below one keeps its exponent", R, "| (GMATH_ABS_MASK & neg);", "| (GMATH_MANT_MASK & neg);", (CORPUS_TEST,)),
    ("round/keep: a magnitude below one is not told from the rest", R, "uint64_t neg = (uint64_t)0 - (e >> 63);", "uint64_t neg = 0;", (CORPUS_TEST,)),
    ("round/trunc: the threshold of the integers is 2^51", R, "double gmath_trunc(double x) {\n  uint64_t b = gmath_bits(x);\n  uint64_t a = b & GMATH_ABS_MASK;\n  if (a >= GMATH_TWO52_BITS) {", "double gmath_trunc(double x) {\n  uint64_t b = gmath_bits(x);\n  uint64_t a = b & GMATH_ABS_MASK;\n  if (a >= 0x4320000000000000ull) {", (CORPUS_TEST,)),
    ("round/trunc: the sign of a zero result lost", R, "  return gmath_double(b & gmath_keep_mask(a));", "  return gmath_double((b & gmath_keep_mask(a)) & GMATH_ABS_MASK);", (CORPUS_TEST,)),
    ("round/floor: a fraction is not taken as one", R, "uint64_t has_frac = (uint64_t)((a & ~keep) != 0);", "uint64_t has_frac = 0;", (CORPUS_TEST,)),
    ("round/floor: every number is taken as having a fraction", R, "uint64_t has_frac = (uint64_t)((a & ~keep) != 0);", "uint64_t has_frac = 1;", (CORPUS_TEST,)),
    ("round/floor: the direction inverted", R, "uint64_t add = (uint64_t)0 - (has_frac & (((b >> 63) ^ away_sign) ^ 1u));", "uint64_t add = (uint64_t)0 - (has_frac & ((b >> 63) ^ away_sign));", (CORPUS_TEST,)),
    ("round/floor: floor moves the positive numbers", R, "  return gmath_floor_or_ceil(b, a, 1u);", "  return gmath_floor_or_ceil(b, a, 0u);", (CORPUS_TEST,)),
    ("round/ceil: ceil moves the negative numbers", R, "  return gmath_floor_or_ceil(b, a, 0u);", "  return gmath_floor_or_ceil(b, a, 1u);", (CORPUS_TEST,)),
    ("round/floor: the sign put back is lost", R, "  return gmath_double(gmath_bits(mag) | (b & GMATH_SIGN_BIT));", "  return mag;", (CORPUS_TEST,)),
    ("round/floor: the sign put back is that of the result's, always positive", R, "  return gmath_double(gmath_bits(mag) | (b & GMATH_SIGN_BIT));", "  return gmath_double(gmath_bits(mag) | (a != 0 ? (b & GMATH_SIGN_BIT) : 0));", (CORPUS_TEST,)),
    ("round/floor: the unit added is 1.5", R, "gmath_double(GMATH_ONE_BITS & add)", "gmath_double(0x3ff8000000000000ull & add)", (CORPUS_TEST,)),
    ("round/floor: the threshold of the integers is 2^51", R, "double gmath_floor(double x) {\n  uint64_t b = gmath_bits(x);\n  uint64_t a = b & GMATH_ABS_MASK;\n  if (a >= GMATH_TWO52_BITS) {", "double gmath_floor(double x) {\n  uint64_t b = gmath_bits(x);\n  uint64_t a = b & GMATH_ABS_MASK;\n  if (a >= 0x4320000000000000ull) {", (CORPUS_TEST,)),
    ("round/ceil: the threshold of the integers is 2^51", R, "double gmath_ceil(double x) {\n  uint64_t b = gmath_bits(x);\n  uint64_t a = b & GMATH_ABS_MASK;\n  if (a >= GMATH_TWO52_BITS) {", "double gmath_ceil(double x) {\n  uint64_t b = gmath_bits(x);\n  uint64_t a = b & GMATH_ABS_MASK;\n  if (a >= 0x4320000000000000ull) {", (CORPUS_TEST,)),
    ("round/rint: ties away from zero", R, "uint64_t up = (uint64_t)(fr > half) | ((uint64_t)(fr == half) & odd);", "uint64_t up = (uint64_t)(fr >= half); (void)odd;", (CORPUS_TEST,)),
    ("round/rint: ties to odd", R, "((uint64_t)(fr == half) & odd);", "((uint64_t)(fr == half) & (odd ^ 1u));", (CORPUS_TEST,)),
    ("round/rint: ties down", R, "uint64_t up = (uint64_t)(fr > half) | ((uint64_t)(fr == half) & odd);", "uint64_t up = (uint64_t)(fr > half); (void)odd;", (CORPUS_TEST,)),
    ("round/rint: just over a half rounds down", R, "uint64_t up = (uint64_t)(fr > half) | ((uint64_t)(fr == half) & odd);", "uint64_t up = ((uint64_t)(fr == half) & odd);", (CORPUS_TEST,)),
    ("round/rint: one half rounds to 1", R, "(uint64_t)(a > GMATH_HALF_BITS)));", "(uint64_t)(a >= GMATH_HALF_BITS)));", (CORPUS_TEST,)),
    ("round/rint: three quarters rounds to 0", R, "(uint64_t)(a > GMATH_HALF_BITS)));", "(uint64_t)(a > 0x3fe8000000000000ull)));", (CORPUS_TEST,)),
    ("round/rint: the sign of a small result lost", R, "uint64_t r_small = sign | (GMATH_ONE_BITS", "uint64_t r_small = (sign & 0) | (GMATH_ONE_BITS", (CORPUS_TEST,)),
    ("round/rint: the carry added is one unit short", R, "uint64_t r_big = t + ((half << 1) & ((uint64_t)0 - up));", "uint64_t r_big = t + (half & ((uint64_t)0 - up));", (CORPUS_TEST,)),
    ("round/rint: the half is read from the wrong bit", R, "uint64_t half = GMATH_HALF_UNIT >> (e & 63u);", "uint64_t half = GMATH_HALF_UNIT >> ((e + 1u) & 63u);", (CORPUS_TEST,)),
    ("round/rint: the parity is read from the wrong bit", R, "uint64_t odd = (t >> ((52u - e) & 63u)) & 1u;", "uint64_t odd = (t >> ((51u - e) & 63u)) & 1u;", (CORPUS_TEST,)),
    ("round/rint: the small and the large are told apart at 2", R, "uint64_t small = (uint64_t)0 - (uint64_t)(a < GMATH_ONE_BITS);", "uint64_t small = (uint64_t)0 - (uint64_t)(a < 0x4000000000000000ull);", (CORPUS_TEST,)),
    ("round/rint: the threshold of the integers is 2^51", R, "double gmath_rint(double x) {\n  uint64_t b = gmath_bits(x);\n  uint64_t a = b & GMATH_ABS_MASK;\n  if (a >= GMATH_TWO52_BITS) {", "double gmath_rint(double x) {\n  uint64_t b = gmath_bits(x);\n  uint64_t a = b & GMATH_ABS_MASK;\n  if (a >= 0x4320000000000000ull) {", (CORPUS_TEST,)),
    ("round/round: the half unit is 2^50", R, "  b += GMATH_HALF_UNIT >> e;", "  b += (GMATH_HALF_UNIT >> 1) >> e;", (CORPUS_TEST,)),
    ("round/round: a magnitude from 0.25 rounds up", R, "  if (a < GMATH_HALF_BITS) {\n    return gmath_double(b & GMATH_SIGN_BIT);\n  }\n  if (a < GMATH_ONE_BITS) {\n    return gmath_double((b & GMATH_SIGN_BIT) | GMATH_ONE_BITS);\n  }\n  uint64_t e = (a >> 52) - 1023;\n  /* add one half", "  if (a < 0x3fd0000000000000ull) {\n    return gmath_double(b & GMATH_SIGN_BIT);\n  }\n  if (a < GMATH_ONE_BITS) {\n    return gmath_double((b & GMATH_SIGN_BIT) | GMATH_ONE_BITS);\n  }\n  uint64_t e = (a >> 52) - 1023;\n  /* add one half", (CORPUS_TEST,)),
    ("round/round: the sign of a result of magnitude 1 lost", R, "  if (a < GMATH_ONE_BITS) {\n    return gmath_double((b & GMATH_SIGN_BIT) | GMATH_ONE_BITS);\n  }\n  uint64_t e = (a >> 52) - 1023;\n  /* add one half", "  if (a < GMATH_ONE_BITS) {\n    return gmath_double(GMATH_ONE_BITS);\n  }\n  uint64_t e = (a >> 52) - 1023;\n  /* add one half", (CORPUS_TEST,)),
    ("round/round: round of a small negative is +0", R, "  if (a < GMATH_HALF_BITS) {\n    return gmath_double(b & GMATH_SIGN_BIT);\n  }\n  if (a < GMATH_ONE_BITS) {\n    return gmath_double((b & GMATH_SIGN_BIT) | GMATH_ONE_BITS);\n  }\n  uint64_t e = (a >> 52) - 1023;\n  /* add one half", "  if (a < GMATH_HALF_BITS) {\n    return gmath_double(0);\n  }\n  if (a < GMATH_ONE_BITS) {\n    return gmath_double((b & GMATH_SIGN_BIT) | GMATH_ONE_BITS);\n  }\n  uint64_t e = (a >> 52) - 1023;\n  /* add one half", (CORPUS_TEST,)),
    ("round/fabs: a NaN keeps its payload", R, "  return a > GMATH_INF_BITS ? gmath_nan_of(x) : gmath_double(a);", "  return gmath_double(a);", (CORPUS_TEST,)),
    ("round/fabs: the sign kept", R, "  return a > GMATH_INF_BITS ? gmath_nan_of(x) : gmath_double(a);", "  return a > GMATH_INF_BITS ? gmath_nan_of(x) : x;", (CORPUS_TEST,)),
    ("round/copysign: the sign of x kept", R, "  return gmath_double(a | (gmath_bits(y) & GMATH_SIGN_BIT));", "  return gmath_double(a | (gmath_bits(x) & GMATH_SIGN_BIT) | (gmath_bits(y) & 0));", (CORPUS_TEST,)),
    ("round/copysign: the sign of a zero y ignored", R, "  return gmath_double(a | (gmath_bits(y) & GMATH_SIGN_BIT));", "  return gmath_double(a | (y < 0 ? GMATH_SIGN_BIT : 0));", (CORPUS_TEST,)),
    ("round/copysign: a NaN x keeps its payload", R, "  if (a > GMATH_INF_BITS) {\n    return gmath_nan_of(x);\n  }\n  return gmath_double(a | (gmath_bits(y)", "  return gmath_double(a | (gmath_bits(y)", (CORPUS_TEST,)),
    # --- scalbn, ldexp, frexp, ilogb ---
    ("scale/scalbn: overflow one binade late", C, "  if (ne >= 2047) {", "  if (ne >= 2048) {", (CORPUS_TEST,)),
        ("scale/scalbn: a tie in the subnormals rounds up", C, "  if (rem > half || (rem == half && (q & 1u))) {", "  if (rem >= half) {", (CORPUS_TEST,)),
    ("scale/scalbn: a tie in the subnormals rounds down", C, "  if (rem > half || (rem == half && (q & 1u))) {", "  if (rem > half) {", (CORPUS_TEST,)),
    ("scale/scalbn: a tie in the subnormals rounds to odd", C, "  if (rem > half || (rem == half && (q & 1u))) {", "  if (rem > half || (rem == half && !(q & 1u))) {", (CORPUS_TEST,)),
    ("scale/scalbn: the subnormal result truncated", C, "  if (rem > half || (rem == half && (q & 1u))) {\n    q++;\n  }\n", "  (void)half;\n", (CORPUS_TEST,)),
    ("scale/scalbn: a subnormal argument scaled by 2^50", C, "    uint64_t s = gmath_bits(x * 0x1p54) & GMATH_ABS_MASK;\n    *ex = (int64_t)(s >> 52) - 54;", "    uint64_t s = gmath_bits(x * 0x1p50) & GMATH_ABS_MASK;\n    *ex = (int64_t)(s >> 52) - 50;", (CORPUS_TEST,)),
    ("scale/scalbn: a subnormal argument's exponent off by one", C, "    *ex = (int64_t)(s >> 52) - 54;", "    *ex = (int64_t)(s >> 52) - 53;", (CORPUS_TEST,)),
    ("scale/scalbn: n clamped at 50", C, "int64_t k = n > 5000 ? 5000 : (n < -5000 ? -5000 : (int64_t)n);", "int64_t k = n > 50 ? 50 : (n < -50 ? -50 : (int64_t)n);", (CORPUS_TEST,)),
    ("scale/scalbn: n clamped at 1500", C, "int64_t k = n > 5000 ? 5000 : (n < -5000 ? -5000 : (int64_t)n);", "int64_t k = n > 1500 ? 1500 : (n < -1500 ? -1500 : (int64_t)n);", (CORPUS_TEST,)),
    ("scale/scalbn: the sign of a zero lost", C, "  if (a == 0) {\n    return x;\n  }\n  int64_t ex;\n  uint64_t mant;\n  gmath_unpack(x, a, &ex, &mant);\n  /* no double", "  if (a == 0) {\n    return 0.0;\n  }\n  int64_t ex;\n  uint64_t mant;\n  gmath_unpack(x, a, &ex, &mant);\n  /* no double", (CORPUS_TEST,)),
    ("scale/scalbn: the sign of an underflow to zero lost", C, "    (void)gmath_underflow(sign);\n    return gmath_double(sign);", "    (void)gmath_underflow(sign);\n    return 0.0;", (CORPUS_TEST,)),
    ("scale/scalbn: underflow beyond 2^-1100 only", C, "  if (s > 54) {", "  if (s > 20) {", (CORPUS_TEST,)),
    ("scale/scalbn: overflow raises nothing", C, "    return gmath_overflow(sign);", "    return gmath_double(GMATH_INF_BITS | sign);", ("Basic.ScalbnSpecialValuesAndExceptions",)),
    ("scale/scalbn: the exact subnormal raises underflow", C, "  if (rem != 0) {\n    (void)gmath_underflow(sign); /* tiny and inexact */\n  }\n", "  (void)gmath_underflow(sign);\n", ("Basic.ScalbnSpecialValuesAndExceptions",)),
    ("scale/scalbn: a tiny inexact result raises nothing", C, "  if (rem != 0) {\n    (void)gmath_underflow(sign); /* tiny and inexact */\n  }\n", "", ("Basic.ScalbnSpecialValuesAndExceptions",)),
    ("scale/scalbn: a NaN keeps its payload", C, "    return a > GMATH_INF_BITS ? gmath_nan_of(x) : x;\n  }\n  if (a == 0) {\n    return x;\n  }\n  int64_t ex;\n  uint64_t mant;\n  gmath_unpack(x, a, &ex, &mant);\n  /* no double", "    return x;\n  }\n  if (a == 0) {\n    return x;\n  }\n  int64_t ex;\n  uint64_t mant;\n  gmath_unpack(x, a, &ex, &mant);\n  /* no double", (CORPUS_TEST,)),
    ("scale/ldexp scales the other way", C, "double gmath_ldexp(double x, int n) {\n  return gmath_scalbn(x, n);", "double gmath_ldexp(double x, int n) {\n  return gmath_scalbn(x, -n);", (CORPUS_TEST,)),
    ("scale/frexp: the exponent one high", C, "  *e = (int)(ex - 1022);", "  *e = (int)(ex - 1021);", (CORPUS_TEST,)),
    ("scale/frexp: the fraction in [1, 2)", C, "| ((uint64_t)1022 << 52) | mant);", "| ((uint64_t)1023 << 52) | mant);", (CORPUS_TEST,)),
    ("scale/frexp: the sign of the fraction lost", C, "return gmath_double((b & GMATH_SIGN_BIT) | ((uint64_t)1022 << 52) | mant);", "return gmath_double(((uint64_t)1022 << 52) | mant);", (CORPUS_TEST,)),
    ("scale/frexp: the exponent of a zero left alone", C, "  *e = 0;\n  if (a >= GMATH_INF_BITS) {", "  if (a >= GMATH_INF_BITS) {", (CORPUS_TEST, "Basic.FrexpAndIlogbSpecialValues"), False),
    ("scale/frexp: a NaN keeps its payload", C, "    return a > GMATH_INF_BITS ? gmath_nan_of(x) : x;\n  }\n  if (a == 0) {\n    return x;\n  }\n  int64_t ex;\n  uint64_t mant;\n  gmath_unpack(x, a, &ex, &mant);\n  *e =", "    return x;\n  }\n  if (a == 0) {\n    return x;\n  }\n  int64_t ex;\n  uint64_t mant;\n  gmath_unpack(x, a, &ex, &mant);\n  *e =", (CORPUS_TEST,)),
    ("scale/frexp: a null exponent pointer is stored through", C, "  if (e == NULL) {\n    e = &dummy;\n  }\n", "  (void)dummy;\n", ("*",), False),
    ("scale/ilogb: the exponent one high", C, "  return (int)(ex - 1023);", "  return (int)(ex - 1022);", (CORPUS_TEST,)),
    ("scale/ilogb: a zero gives 0", C, "  return GMATH_ILOGB0;", "  return 0;", (CORPUS_TEST,)),
    ("scale/ilogb: an infinity gives INT_MIN", C, "return a > GMATH_INF_BITS ? GMATH_ILOGBNAN : INT_MAX;", "return a > GMATH_INF_BITS ? GMATH_ILOGBNAN : INT_MIN;", (CORPUS_TEST,)),
    ("scale/ilogb: a NaN gives INT_MIN", C, "return a > GMATH_INF_BITS ? GMATH_ILOGBNAN : INT_MAX;", "return a > GMATH_INF_BITS ? INT_MIN : INT_MAX;", (CORPUS_TEST,)),
    ("scale/ilogb: a zero raises nothing", C, "  if (a == 0) {\n    (void)gmath_invalid();\n    return GMATH_ILOGB0;", "  if (a == 0) {\n    return GMATH_ILOGB0;", ("Basic.FrexpAndIlogbSpecialValues",)),
]

# Plants in the correction after the estimate, which only the internal test reaches (gmath_sqrt_correct is
# given an estimate wrong in each direction): (name, old, new, test).
INTERNAL_PLANTS = [
    ("sqrt/correction: no round-down step", "    y -= 0x1p-52;\n", "    y -= 0.0;\n", "SqrtInternal.TheCorrectionRepairsAnEstimateOneUlpLowHighOrRight"),
    ("sqrt/correction: no round-up step", "    y += 0x1p-52;\n", "    y += 0.0;\n", "SqrtInternal.TheCorrectionRepairsAnEstimateOneUlpLowHighOrRight"),
    ("sqrt/correction: round-down only below -y u", "  } else if (rho <= -yu) {", "  } else if (rho < -yu) {", "SqrtInternal.TheEqualityCasesOfTheResidualRoundTheRightWay"),
    ("sqrt/correction: round-up on equality", "  if (rho > yu) {", "  if (rho >= yu) {", "SqrtInternal.TheEqualityCasesOfTheResidualRoundTheRightWay"),
    ("sqrt/estimate: no estimate of 2 allowed (y = 2 sent to 1)", "  double yu = y * 0x1p-52;\n", "  double yu = y * 0x1p-52;\n  if (y >= 2.0) {\n    y = 1.0;\n  }\n", "SqrtInternal.AnEstimateOfTwoForTheLargestArgument"),
    ("sqrt/estimate: one Newton step", "  r = r * (1.5 - hm * (r * r));\n  r = r * (1.5 - hm * (r * r));\n", "  r = r * (1.5 - hm * (r * r));\n", "SqrtInternal.TheEstimateIsWithinOneUlpOfTheRoot"),
    ("sqrt/estimate: the correction without the second-order term and with a wrong sign", "(hr * (1.0 + (s0 - c) * hr))", "(hr * (1.0 - (s0 - c) * hr))", "SqrtInternal.TheEstimateIsWithinOneUlpOfTheRoot"),
    ("sqrt/estimate: c and the split of y cut at 26 bits (c^2 inexact)", "#define GMATH_SQRT_LOW27 0x7ffffffull", "#define GMATH_SQRT_LOW27 0x3ffffffull", "SqrtInternal.TheCorrectionRepairsAnEstimateOneUlpLowHighOrRight"),
]


def main():
    env = os.environ
    work = Path(env["PLANT_WORK"])
    cc = shlex.split(env["PLANT_CC"])
    cflags = shlex.split(env["PLANT_CFLAGS"])
    cxx = shlex.split(env["PLANT_CXX"])
    ldflags = shlex.split(env["PLANT_LDFLAGS"])
    test_obj = env["PLANT_TEST_OBJ"]
    cxx_include = shlex.split(env["PLANT_CXX_INCLUDE"])
    probe_cflags = shlex.split(env["PLANT_PROBE_CFLAGS"])
    ld_path = env["PLANT_LD_PATH"]
    trig_obj = env["PLANT_TRIG_OBJ"]
    obj_dir = Path(env["PLANT_OBJ_DIR"])
    jobs = int(env.get("PLANT_JOBS", "4"))

    def stage(name, patches, extra_flags=()):
        d = work / name
        d.mkdir(parents=True)
        for f in SOURCES:
            shutil.copy(SRC / f, d / f)
        for fname, old, new in patches:
            text = (d / fname).read_text()
            if old == "" or text.count(old) != 1:
                fail("%s: the text matches %d times in %s, not once; the plant has rotted" % (name, text.count(old) if old else 0, fname))
                return None
            (d / fname).write_text(text.replace(old, new))
            if (d / fname).read_text() == (SRC / fname).read_text():
                fail("%s: the replacement changed nothing" % name)
                return None
        objs = []
        for o in STAGED_OBJECTS:
            r = subprocess.run(cc + cflags + list(extra_flags) + ["-c", str(d / (o + ".c")), "-o", str(d / (o + ".o"))], capture_output=True, text=True)
            if r.returncode != 0:
                fail("%s: the planted library does not compile:\n%s" % (name, r.stderr))
                return None
            objs.append(str(d / (o + ".o")))
        objs += [str(obj_dir / (o + ".o")) for o in OTHER_OBJECTS]
        (d / "objs.txt").write_text("\n".join(objs))
        r = subprocess.run(cxx + ["-o", str(d / "testBasic"), test_obj] + [o for o in objs if "/sqrt." in o or "/round." in o or "/scale." in o] + ldflags,
                           capture_output=True, text=True)
        if r.returncode != 0:
            fail("%s: the planted test does not link:\n%s%s" % (name, r.stdout, r.stderr))
            return None
        return d

    def run_env(corpus_dir=None):
        e = dict(env)
        e["LD_LIBRARY_PATH"] = ld_path + (":" + e["LD_LIBRARY_PATH"] if e.get("LD_LIBRARY_PATH") else "")
        if corpus_dir is not None:
            e["GMATH_TRIG_CORPUS_DIR"] = str(corpus_dir)
        return e

    def run_test(d, corpus_dir=None):
        r = subprocess.run([str(d / "testBasic"), "--gtest_brief=1"], capture_output=True, text=True, env=run_env(corpus_dir))
        failed = sorted(set(re.findall(r"\[\s*FAILED\s*\]\s+(Basic\.\w+)", r.stdout)))
        return r.returncode, failed, r.stdout

    def build_probe(d):
        exe = d / "corpus-hash"
        objs = (d / "objs.txt").read_text().split("\n")
        r = subprocess.run(cc + probe_cflags + ["tools/corpus-hash.c"] + objs + [trig_obj] + shlex.split(os.environ["PLANT_DECIMAL_OBJS"]) + ["-o", str(exe), "-lm"], capture_output=True, text=True)
        if r.returncode != 0:
            fail("%s: the probe does not build:\n%s" % (d.name, r.stderr))
            return None
        return exe

    def hash_gate(exe, hash_file=CORPUS / "trig.hash"):
        r = subprocess.run(["tools/check-corpus-hash.sh", str(exe), str(CORPUS), str(hash_file)], capture_output=True, text=True, env=run_env())
        return r.returncode, r.stdout + r.stderr

    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    print("check-planted-exact")
    tasks = []

    def queued(f):
        def wrapper(*a, **k):
            tasks.append(lambda: f(*a, **k))
        return wrapper

    @queued
    def expect_test_fails(name, patches, wanted, also_hash=True):
        d = stage(name, patches)
        if d is None:
            return
        rc, failed, out = run_test(d)
        if rc == 0:
            fail("%s: testBasic passed with the defect planted" % name)
            return
        if "*" not in wanted and not any(w in failed for w in wanted):
            fail("%s: testBasic failed (%s) but not %s:\n%s" % (name, failed, "/".join(wanted), out[-1500:]))
            return
        note = "caught by %s" % ", ".join(failed)
        if also_hash and CORPUS_TEST in failed:
            exe = build_probe(d)
            if exe is None:
                return
            hrc, hout = hash_gate(exe)
            if hrc == 0 and "variants" not in hout:
                fail("%s: the corpus hash gate passed although the corpus test failed" % name)
                return
            note += " and by the corpus hash"
        say("  ok   %-62s %s" % (name, note))

    @queued
    def expect_variant_mismatch(name, patches):
        d = stage(name, patches)
        if d is None:
            return
        exe = build_probe(d)
        if exe is None:
            return
        r = subprocess.run([str(exe), str(CORPUS)], capture_output=True, text=True, env=run_env())
        if r.returncode == 0 or "math.variants.mismatch" not in r.stdout:
            fail("%s: the probe did not report a variant mismatch (exit %d)" % (name, r.returncode))
            return
        hrc, hout = hash_gate(exe)
        if hrc == 0:
            fail("%s: the corpus hash gate passed with a variant that differs" % name)
            return
        say("  ok   %-62s the probe reports the mismatch, and the hash gate fails" % name)

    # The control: the unplanted copy builds the same way, passes testBasic and has the committed hash.
    ctl = stage("control", [])
    if ctl is None:
        sys.exit(1)
    rc, failed, out = run_test(ctl)
    if rc != 0:
        fail("control: testBasic fails on the unplanted copy:\n%s" % out[-1500:])
    else:
        print("  ok   control: the unplanted copy passes testBasic")
    exe = build_probe(ctl)
    if exe is not None:
        hrc, hout = hash_gate(exe)
        if hrc != 0:
            fail("control: the unplanted copy fails the corpus hash:\n%s" % hout)
        else:
            print("  ok   control: the unplanted copy has the committed hash")

    for plant in TEST_PLANTS:
        name, fname, old, new, wanted = plant[:5]
        expect_test_fails(name, [(fname, old, new)], wanted, also_hash=(plant[5] if len(plant) > 5 else True))

    # The correction and the estimate, by the internal test.
    @queued
    def expect_internal_fails(name, patches, wanted):
        d = stage(name, patches)
        if d is None:
            return
        text = Path("tests/unit/test_sqrt_internal.cpp").read_text()
        inc = '#include "../../src/elementary/sqrt_impl.h"'
        if text.count(inc) != 1:
            fail("%s: test_sqrt_internal.cpp no longer includes sqrt_impl.h by that name" % name)
            return
        (d / "test_sqrt_internal.cpp").write_text(text.replace(inc, '#include "%s"' % (d / "sqrt_impl.h").resolve()))
        r = subprocess.run(cxx + cxx_include + ["-c", str(d / "test_sqrt_internal.cpp"), "-o", str(d / "test_sqrt_internal.o")], capture_output=True, text=True)
        if r.returncode != 0:
            fail("%s: the planted internal test does not compile:\n%s" % (name, r.stderr))
            return
        r = subprocess.run(cxx + ["-o", str(d / "testSqrtInternal"), str(d / "test_sqrt_internal.o")] + ldflags, capture_output=True, text=True)
        if r.returncode != 0:
            fail("%s: the planted internal test does not link:\n%s%s" % (name, r.stdout, r.stderr))
            return
        r = subprocess.run([str(d / "testSqrtInternal"), "--gtest_brief=1"], capture_output=True, text=True, env=run_env())
        failed = sorted(set(re.findall(r"\[\s*FAILED\s*\]\s+(SqrtInternal\.\w+)", r.stdout)))
        if r.returncode == 0:
            fail("%s: testSqrt_internal passed with the defect planted" % name)
        elif wanted not in failed:
            fail("%s: testSqrt_internal failed (%s) but not %s" % (name, failed, wanted))
        else:
            say("  ok   %-62s caught by %s" % (name, wanted))

    ictl = stage("internal-control", [])
    for name, old, new, wanted in INTERNAL_PLANTS:
        expect_internal_fails(name, [(S, old, new)], wanted)

    # Variants: a defect in one square root only.
    expect_variant_mismatch("variant/the hardware path one unit high for a result above 8",
                            [(S, "  return r;\n}\n#define gmath_sqrt_impl gmath_sqrt_hardware_impl", "  return r > 8.0 ? r * (1.0 + 0x1p-52) : r;\n}\n#define gmath_sqrt_impl gmath_sqrt_hardware_impl")])
    expect_variant_mismatch("variant/the portable path has one Newton step",
                            [(S, "  r = r * (1.5 - hm * (r * r));\n  r = r * (1.5 - hm * (r * r));\n", "  r = r * (1.5 - hm * (r * r));\n")])
    expect_variant_mismatch("variant/ldexp scales the other way",
                            [(C, "double gmath_ldexp(double x, int n) {\n  return gmath_scalbn(x, n);", "double gmath_ldexp(double x, int n) {\n  return gmath_scalbn(x, -n);")])

    # Build: the hardware path silently lost.
    @queued
    def expect_build_fails(name, wanted):
        d = stage(name, [], extra_flags=["-DGMATH_SQRT_PORTABLE"])
        if d is None:
            return
        rc, failed, out = run_test(d)
        if rc == 0 or wanted not in failed:
            fail("%s: testBasic did not fail %s (exit %d, failed %s)" % (name, wanted, rc, failed))
            return
        say("  ok   %-62s caught by %s" % (name, wanted))

    expect_build_fails("build/the hardware path lost to -DGMATH_SQRT_PORTABLE, which the test does not know", "Basic.SqrtReportsWhetherItUsesTheInstruction")

    # Corpus: the oracle's data is wrong or missing.
    def corpus_variant(name, edit):
        d = work / name
        shutil.copytree(CORPUS, d)
        edit(d)
        return d

    @queued
    def expect_corpus_refused(name, edit):
        d = corpus_variant("corpus-" + name, edit)
        rc, failed, out = run_test(ctl, d)
        if rc == 0:
            fail("corpus/%s: testBasic passed on a damaged corpus" % name)
        elif CORPUS_TEST not in failed:
            fail("corpus/%s: testBasic failed (%s) but not the corpus test" % (name, failed))
        else:
            say("  ok   %-62s refused by %s" % ("corpus/" + name, CORPUS_TEST))

    def wrong_answer(fn, col):
        def edit(d):
            lines = (d / (fn + ".corpus")).read_text().split("\n")
            i = next(k for k, l in enumerate(lines) if not l.startswith("#") and l.strip() and k > 600)
            f = lines[i].split()
            f[col] = "%016x" % (int(f[col], 16) ^ 1)
            lines[i] = " ".join(f)
            (d / (fn + ".corpus")).write_text("\n".join(lines))
        return edit

    def short_file(fn):
        def edit(d):
            lines = (d / (fn + ".corpus")).read_text().split("\n")
            (d / (fn + ".corpus")).write_text("\n".join(lines[:200]) + "\n")
        return edit

    def missing_file(fn):
        def edit(d):
            (d / (fn + ".corpus")).unlink()
        return edit

    def empty_file(fn):
        def edit(d):
            (d / (fn + ".corpus")).write_text("# nothing\n")
        return edit

    cols = {"sqrt": 1, "floor": 1, "ceil": 1, "trunc": 1, "round": 1, "rint": 1, "fabs": 1, "copysign": 2, "scalbn": 2, "frexp": 1, "ilogb": 1}
    d = corpus_variant("corpus-control", lambda d: None)
    rc, failed, out = run_test(ctl, d)
    if rc != 0:
        fail("corpus control: a copy of the committed corpus fails testBasic:\n%s" % out[-1500:])
    else:
        print("  ok   control: a copy of the committed corpus passes testBasic")
    for fn, col in cols.items():
        expect_corpus_refused("%s one wrong answer (one bit)" % fn, wrong_answer(fn, col))
        expect_corpus_refused("%s truncated file" % fn, short_file(fn))
        expect_corpus_refused("%s missing file" % fn, missing_file(fn))
        expect_corpus_refused("%s empty file" % fn, empty_file(fn))

    def expect_hash_file_refused(hf, fn, label):
        rc, out = hash_gate(probe_exe, hf)
        if rc == 0:
            fail("hash file/%s %s: the gate passed" % (fn, label))
        else:
            say("  ok   %-62s refused by check-corpus-hash" % ("hash file/%s %s" % (fn, label)))

    # The committed hash file: a changed fn line of the new functions.
    real = (CORPUS / "trig.hash").read_text()
    probe_exe = ctl / "corpus-hash"
    for fn in ("sqrt", "floor", "scalbn", "frexp", "sqrt_hardware", "ldexp"):
        m = re.search(r"^fn %s (\w+) (\d+)" % fn, real, re.M)
        for label, content in (("changed hash", real.replace(m.group(0), "fn %s 0000000000000000 %s" % (fn, m.group(2)))),
                               ("changed count", real.replace(m.group(0), "fn %s %s 1" % (fn, m.group(1)))),
                               ("line removed", real.replace(m.group(0) + "\n", ""))):
            hf = work / ("hash-%s-%s" % (fn, label.replace(" ", "-")))
            hf.write_text(content)
            tasks.append(lambda hf=hf, fn=fn, label=label: expect_hash_file_refused(hf, fn, label))

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for fut in [pool.submit(t) for t in tasks]:
            fut.result()

    if failures:
        print("check-planted-exact: %d failure(s)" % len(failures), file=sys.stderr)
        sys.exit(1)
    print("check-planted-exact: every planted defect is caught, and the control passes")


if __name__ == "__main__":
    main()
