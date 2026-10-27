/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Copyright (C) 2026 Corey Pennycuff
 *
 * This file is part of Ghoti.io Math.
 *
 * Ghoti.io Math is free software: you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * Ghoti.io Math is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

/**
 * @file
 *
 * gmath_atan2.
 *
 * Written from the published algorithms, not from any library's source:
 * Tang's table-driven reduction for the arctangent (Muller, Elementary
 * Functions, chapter 11), the exact remainder of a quotient from a short
 * multiplier (Dekker, 1971; Muller, chapter 4) and the octant reflections of
 * C99 Annex F.9.1.4.
 *
 * With u = min(|y|, |x|), v = max(|y|, |x|) and q = u/v in [0, 1]:
 *
 *   atan2(y, x) = +-(B + s atan q),  (B, s) = (0, +), (pi/2, -), (pi, -) or
 *                                    (pi/2, +) by the signs and the swap.
 *
 *   q in [1/8, 1] (table): F is the nearest multiple of 1/64 to q, beta =
 *       (u - F v)/v, atan q = atan F + G1 beta + ... + G8 beta^8, the Taylor
 *       series at F with |beta| <= 2^-7.  u - F v is formed exactly in two
 *       parts (v split in two, F has seven bits), beta = that times 1/v.  The
 *       only inexact quantity is beta itself, relative error about 3 * 2^-53,
 *       against a result of at least atan(1/8): 0.03 ulp at most.
 *   q below 1/8 (direct): atan q = q + q^3 P(q^2).  The result is as large as
 *       q, so q must be better than one double: q = qh + ql with qh of 26 bits
 *       (from the rounded quotient u * (1/v)), the exact remainder u - qh v
 *       (qh v is a product of 26 and 53 bits, formed in two exact parts), and
 *       ql = remainder * (1/v).  qh + ql is q to about 2^-76 relative.
 *   q below 2^-30: atan q is q to within 2^-61 relative (q^2/3), so the correctly rounded
 *       quotient u/v is the answer (and it handles every exponent).
 *
 * The reflection is added in a double-double: B hi and lo from a four entry
 * table, FastTwoSum of B hi and the table's atan F hi, and the rest of the
 * terms (all below 2^-6 of the result) in plain double.
 *
 * Error budget (measured, not proved; the contract is 1 ulp).  The final addition is 0.5 ulp.  In the
 * table path beta is rounded (its relative error is about 3 * 2^-53), G1 is a double, and the sum of
 * the correction is rounded: together up to 2^-57 of the result at the first rows (atan(1/8) is
 * 0.124, ulp 2^-56), so the worst result is within about 0.56 ulp (measured 0.5545 over 8e5 inputs),
 * and the rows with larger results are better.  In the direct path q is better than 2^-76 and the
 * polynomial 2^-61.8 of q: 0.5000x ulp.  The reflection adds a double-double constant to the term
 * and its low part, a FastTwoSum, so an axis or a multiple of pi/2 loses nothing.
 *
 * Special values follow C99 Annex F.9.1.4 exactly (the table in the code).
 * Every NaN returned is the quiet NaN 0x7ff8000000000000.
 */

#include <ghoti.io/math/macros.h>

#include <ghoti.io/math/elementary.h>
#include <float.h>

#include "atan2_table.h"
#include "elem_common.h"

/* Added to q * 64, it leaves the nearest integer in the low bits of the sum. */
#define GMATH_ATAN2_MAGIC 0x1.8p52

#define GMATH_ATAN2_DIRECT 0.125
/* Below this ratio u/v the quotient u/v is atan(u/v) to within 2^-55. */
#define GMATH_ATAN2_TINY 0x1p-30

/* The low 27 stored bits cleared leave 26 significant bits: a qh or c that
 * multiplies a 27-bit half of v exactly. */
#define GMATH_ATAN2_LOW27 0x7ffffffull
/* The low 26 stored bits cleared leave 27 significant bits (the halves of v). */
#define GMATH_ATAN2_LOW26 0x3ffffffull

/* v is scaled into [2^-600, 2^600] when it is outside it: rx = 1/v and the
 * partial products then neither overflow nor lose bits to underflow. */
#define GMATH_ATAN2_SCALE_LIMIT 0x1p600
#define GMATH_ATAN2_SCALE 0x1p700

GMATH_STATIC_ASSERT(GMATH_ATAN2_TAYLOR == 8, "the Estrin evaluation is written for eight Taylor coefficients");
GMATH_STATIC_ASSERT(GMATH_ATAN2_DIRECT_DEGREE == 6, "the Estrin evaluation is written for a degree 6 polynomial");

/* B hi, B lo and the sign bit of s, by the octant code 2 * (x < 0) + (|y| > |x|). */
static const double reflect_hi[4] = {0.0, GMATH_PIO2_HI, GMATH_PI_HI, GMATH_PIO2_HI};
static const double reflect_lo[4] = {0.0, GMATH_PIO2_LO, GMATH_PI_LO, GMATH_PIO2_LO};
static const uint64_t reflect_sign[4] = {0, GMATH_SIGN_BIT, GMATH_SIGN_BIT, 0};

/* The special values: a NaN, a zero or an infinity in either argument. */
static double atan2_special(double y, double x, uint64_t yb, uint64_t xb) {
  uint64_t ay = yb & GMATH_ABS_MASK;
  uint64_t ax = xb & GMATH_ABS_MASK;
  uint64_t ys = yb & GMATH_SIGN_BIT;
  if (ax > GMATH_INF_BITS || ay > GMATH_INF_BITS) {
    return gmath_nan_of(ax > GMATH_INF_BITS ? x : y);
  }
  int xneg = (xb & GMATH_SIGN_BIT) != 0;
  if (ay == 0) {
    /* atan2(+-0, x): +-0 for x >= +0, +-pi for x <= -0 (a NaN x is above) */
    return gmath_double(xneg ? (gmath_bits(GMATH_PI_HI) | ys) : ys);
  }
  if (ax == 0) {
    return gmath_double(gmath_bits(GMATH_PIO2_HI) | ys);
  }
  if (ay == GMATH_INF_BITS) {
    if (ax == GMATH_INF_BITS) {
      return gmath_double(gmath_bits(xneg ? GMATH_3PIO4 : GMATH_PIO4) | ys);
    }
    return gmath_double(gmath_bits(GMATH_PIO2_HI) | ys);
  }
  /* ax is infinite, y finite and nonzero */
  return gmath_double(xneg ? (gmath_bits(GMATH_PI_HI) | ys) : ys);
}

double gmath_atan2(double y, double x) {
  uint64_t yb = gmath_bits(y);
  uint64_t xb = gmath_bits(x);
  uint64_t ay = yb & GMATH_ABS_MASK;
  uint64_t ax = xb & GMATH_ABS_MASK;
  if (ay - 1 >= GMATH_INF_BITS - 1 || ax - 1 >= GMATH_INF_BITS - 1) {
    /* a zero, an infinity or a NaN in either argument (zero wraps to the top) */
    return atan2_special(y, x, yb, xb);
  }
  uint64_t ys = yb & GMATH_SIGN_BIT;
  int swap = ay > ax;
  double u = gmath_double(swap ? ax : ay);
  double v = gmath_double(swap ? ay : ax);
  unsigned code = (unsigned)((xb >> 62) & 2u) | (unsigned)swap;
  double bh = reflect_hi[code];
  double bl = reflect_lo[code];
  uint64_t sbit = reflect_sign[code];

  double hi, c; /* atan q = hi + c, c below 2^-6 of the result */
  if (u < v * GMATH_ATAN2_TINY) {
    hi = u / v;
    c = 0.0;
  } else {
    if (v > GMATH_ATAN2_SCALE_LIMIT || v < 1 / GMATH_ATAN2_SCALE_LIMIT) {
      double sc = v > 1.0 ? 1 / GMATH_ATAN2_SCALE : GMATH_ATAN2_SCALE;
      u *= sc;
      v *= sc;
    }
    double rx = 1.0 / v;
    double qa = u * rx;
    uint64_t vb = gmath_bits(v);
    double vh = gmath_double(vb & ~GMATH_ATAN2_LOW26);
    double vl = v - vh;
    if (qa >= GMATH_ATAN2_DIRECT) {
      double t = qa * 64.0 + GMATH_ATAN2_MAGIC;
      unsigned j = (unsigned)(gmath_bits(t) & 0x7fu);
      double f = (t - GMATH_ATAN2_MAGIC) * 0x1p-6;
      double num = (u - f * vh) - f * vl;
      double beta = num * rx;
      const double * g = gmath_atan2_rows[j];
      double b2 = beta * beta;
      double b4 = b2 * b2;
      double e1 = (g[2] + g[3] * beta) + (g[4] + g[5] * beta) * b2;
      double e2 = (g[6] + g[7] * beta) + (g[8] + g[9] * beta) * b2;
      hi = g[0];
      c = g[1] + beta * (e1 + e2 * b4);
    } else {
      double qm = gmath_double(gmath_bits(qa) & ~GMATH_ATAN2_LOW27);
      double rem = (u - qm * vh) - qm * vl;
      double ql = rem * rx;
      const double * p = gmath_atan2_poly;
      double w = qa * qa;
      double w2 = w * w;
      double e1 = (p[0] + p[1] * w) + (p[2] + p[3] * w) * w2;
      double e2 = (p[4] + p[5] * w) + p[6] * w2;
      double poly = e1 + e2 * (w2 * w2);
      hi = qm;
      c = ql + (qa * w) * poly;
    }
  }
  gmath_pair s = gmath_fast_two_sum(bh, gmath_double(gmath_bits(hi) ^ sbit));
  double tail = (s.lo + bl) + gmath_double(gmath_bits(c) ^ sbit);
  return gmath_double(gmath_bits(s.hi + tail) | ys);
}

/* Binary32 has a dedicated short kernel; the established double path above
 * retains its own evaluation and table use unchanged. */
GMATH_STATIC_ASSERT(sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 &&
                    FLT_MANT_DIG == 24 && FLT_MIN_EXP == -125 &&
                    FLT_MAX_EXP == 128, "atan2f requires IEEE binary32");

static inline float af_value(uint32_t af_word) {
  float af_result;
  memcpy(&af_result, &af_word, sizeof af_result);
  return af_result;
}

/* Integer widening also avoids denormal-operand conversion penalties. */
static inline double af_widen(uint32_t af_word) {
  unsigned af_field = af_word >> 23;
  uint32_t af_m = af_word & 0x007fffffu;
  if (af_field != 0) {
    return gmath_double(((uint64_t)(af_field + 896u) << 52) | ((uint64_t)af_m << 29));
  }
  unsigned af_shift;
#if defined(__GNUC__) || defined(__clang__)
  af_shift = (unsigned)__builtin_clz(af_m) - 8u; /* Nonzero finite input. */
#else
  af_shift = 0;
  while ((af_m << af_shift) < 0x00800000u) ++af_shift;
#endif
  af_m <<= af_shift;
  return gmath_double(((uint64_t)(897u - af_shift) << 52) |
      ((uint64_t)(af_m & 0x007fffffu) << 29));
}

static inline void af_inexact(void) {
  volatile double af_big = 0x1p100;
  volatile double af_ignored = af_big + 1.0;
  (void)af_ignored;
}

static inline float af_angle(uint32_t af_magnitude, uint32_t af_sign) {
  af_inexact();
  return af_value(af_magnitude | af_sign);
}

/* For q<2^-30, atan(q)<q by <2^-36 Float ULP. A non-midpoint
 * rational Float ratio is >2^-25 Float ULP from a midpoint, much farther
 * than quotient roundoff. At an exact midpoint choose the lower magnitude. */
static inline uint32_t af_tiny(double af_q) {
  uint64_t af_bits = gmath_bits(af_q);
  int af_e = (int)(af_bits >> 52) - 1023;
  if (af_e < -150) return 0;
  unsigned af_cut = af_e >= -126 ? 29u : (unsigned)(-97 - af_e);
  uint64_t af_sig = (af_bits & UINT64_C(0x000fffffffffffff)) | (UINT64_C(1) << 52);
  uint64_t af_fraction = af_sig & ((UINT64_C(1) << af_cut) - 1u);
  uint64_t af_half = UINT64_C(1) << (af_cut - 1u);
  uint32_t af_qword = (uint32_t)(af_sig >> af_cut) + (uint32_t)(af_fraction > af_half);
  return af_e >= -126 ? ((uint32_t)(af_e + 126) << 23) + af_qword : af_qword;
}

static inline double af_kernel(double af_q) {
  if (af_q < GMATH_ATAN2_TINY) return af_q; /* Reflected normal angles only. */
  if (af_q < GMATH_ATAN2_DIRECT) {
    double af_z = af_q * af_q;
    double af_p = -0x1.5555555555555p-2 + af_z *
        (0x1.999999999999ap-3 + af_z *
        (-0x1.2492492492492p-3 + af_z * 0x1.c71c71c71c71cp-4));
    return af_q + (af_q * af_z) * af_p;
  }
  double af_t = af_q * 64.0 + GMATH_ATAN2_MAGIC;
  unsigned af_j = (unsigned)(gmath_bits(af_t) & 0x7fu);
  double af_f = (af_t - GMATH_ATAN2_MAGIC) * 0x1p-6;
  double af_beta = af_q - af_f;
  const double * af_row = gmath_atan2_rows[af_j];
  double af_p = af_row[2] + af_beta *
      (af_row[3] + af_beta * (af_row[4] + af_beta * af_row[5]));
  return (af_row[0] + af_row[1]) + af_beta * af_p;
}

float gmath_atan2f(float y, float x) {
  uint32_t af_yw, af_xw;
  memcpy(&af_yw, &y, sizeof af_yw);
  memcpy(&af_xw, &x, sizeof af_xw);
  uint32_t af_ay = af_yw & 0x7fffffffu;
  uint32_t af_ax = af_xw & 0x7fffffffu;
  uint32_t af_ys = af_yw & 0x80000000u;
  unsigned af_xneg = (af_xw >> 31) != 0;
  if ((af_ay > 0x7f800000u && (af_ay & 0x00400000u) == 0) ||
      (af_ax > 0x7f800000u && (af_ax & 0x00400000u) == 0)) {
    (void)gmath_invalid();
    return af_value(0x7fc00000u);
  }
  if (af_ay > 0x7f800000u || af_ax > 0x7f800000u) return af_value(0x7fc00000u);
  if (af_ay == 0) {
    return af_xneg ? af_angle(0x40490fdbu, af_ys) : af_value(af_ys);
  }
  if (af_ax == 0) return af_angle(0x3fc90fdbu, af_ys);
  if (af_ay == 0x7f800000u) {
    if (af_ax == 0x7f800000u) return af_angle(af_xneg ? 0x4016cbe4u : 0x3f490fdbu, af_ys);
    return af_angle(0x3fc90fdbu, af_ys);
  }
  if (af_ax == 0x7f800000u) {
    return af_xneg ? af_angle(0x40490fdbu, af_ys) : af_value(af_ys);
  }
  if (af_ay == af_ax) return af_angle(af_xneg ? 0x4016cbe4u : 0x3f490fdbu, af_ys);
  double af_dy = af_widen(af_ay);
  double af_dx = af_widen(af_ax);
  if (!af_xneg && af_dy < af_dx * GMATH_ATAN2_TINY) {
    uint32_t af_magnitude = af_tiny(af_dy / af_dx);
    if (af_magnitude < 0x00800000u) (void)gmath_underflow(0);
    else af_inexact();
    return af_value(af_magnitude | af_ys);
  }
  unsigned af_swap = af_ay > af_ax;
  double af_q = af_swap ? af_dx / af_dy : af_dy / af_dx;
  double af_result = af_kernel(af_q);
  if (af_swap) af_result = GMATH_PIO2_HI - af_result;
  if (af_xneg) af_result = GMATH_PI_HI - af_result;
  af_result = gmath_double(gmath_bits(af_result) | ((uint64_t)af_ys << 32));
  float af_narrow = (float)af_result;
  af_inexact();
  return af_narrow;
}

/* Reuse the binary32 kernel and its raw special/exception handling. */
float gmath_atanf(float x) {
  return gmath_atan2f(x, 1.0f);
}
