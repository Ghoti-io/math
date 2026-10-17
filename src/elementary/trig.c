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
 * gmath_sin, gmath_cos and gmath_tan.
 *
 * Written from the published algorithms, not from any library's source:
 *
 *   - Argument reduction by Payne and Hanek (1983, "Radian reduction for
 *     trigonometric functions"): x * 2/pi is formed exactly enough, from the
 *     bits of 2/pi that matter for this x, to give the quadrant and the
 *     fraction to more than 100 bits even when x is within 2^-62 of a multiple
 *     of pi/2.  Done in 32-bit limbs with 64-bit products, so it is the same
 *     integer arithmetic on every target (no 128-bit type, no integer to
 *     double conversion, which an i686 build would do on the x87 stack).
 *   - For moderate arguments (below 2^20), the cheaper reduction of Cody and
 *     Waite (1980; Muller, Elementary Functions, chapter 11): the quotient
 *     n from one multiplication, and the remainder from n times a pi/2 split
 *     into parts short enough that every product is exact.  It is used only
 *     when it provably agrees with Payne-Hanek (see reduce_fast); everything
 *     else, including every argument it declines, goes the exact way.
 *   - Error-free transformations (Dekker's FastTwoSum, split and product;
 *     Muller, Elementary Functions, chapter 4) for the few terms that need
 *     more than a double: the reduced argument, r^3/6 and 1 - r^2/2.
 *   - Minimax polynomials for the rest, fitted by tools/oracle/fit_coeffs.py
 *     against a multiple-precision value and held in trig_tables.h.
 *
 * Nothing here calls libm, uses a fused multiply-add or leaves the double
 * format.  Every double expression is one operation per statement or an
 * explicit sequence, and the library is built with -ffp-contract=off.
 */

#include <ghoti.io/math/macros.h>

#include <ghoti.io/math/elementary.h>

#include <stdint.h>
#include <string.h>

#include "trig_tables.h"

/* pi/4 rounded to a double (0x1.921fb54442d18p-1): the argument below which no
 * reduction is needed. */
#define GMATH_PIO4 0x1.921fb54442d18p-1

/* A double-double: hi + lo, with |lo| <= ulp(hi)/2 when normalized. */
typedef struct {
  double hi;
  double lo;
} gmath_dd;

static const uint64_t SIGN_BIT = 0x8000000000000000ull;
static const uint64_t ABS_MASK = 0x7fffffffffffffffull;
static const uint64_t INF_BITS = 0x7ff0000000000000ull;
static const uint64_t QNAN_BITS = 0x7ff8000000000000ull;

static uint64_t bits_of(double d) {
  uint64_t u;
  memcpy(&u, &d, sizeof u);
  return u;
}

static double double_of(uint64_t u) {
  double d;
  memcpy(&d, &u, sizeof d);
  return d;
}

/* An integer below 2^53 as a double, exactly, with no integer to double
 * conversion: 2^52 + k has the bit pattern 0x4330... | k for k < 2^52. */
static double small_to_double(uint64_t k) {
  const double two52 = 0x1p52;
  uint64_t hi = k >> 26;
  uint64_t lo = k & 0x3ffffffull;
  double dh = double_of(0x4330000000000000ull | hi) - two52;
  double dl = double_of(0x4330000000000000ull | lo) - two52;
  return dh * 0x1p26 + dl;
}

/* Knuth's FastTwoSum, valid when |a| >= |b| (every use here): s + e == a + b
 * exactly, s = fl(a + b). */
static gmath_dd fast_two_sum(double a, double b) {
  gmath_dd r;
  double s = a + b;
  double e = b - (s - a);
  r.hi = s;
  r.lo = e;
  return r;
}

/* Veltkamp's split: a == hi + lo, each with at most 26 significant bits. */
static void split(double a, double * hi, double * lo) {
  double t = 134217729.0 * a; /* 2^27 + 1 */
  double h = t - (t - a);
  *hi = h;
  *lo = a - h;
}

/* Dekker's product: p + e == a * b exactly, p = fl(a * b), barring overflow
 * and underflow, which the ranges here do not reach. */
static gmath_dd two_prod(double a, double b) {
  gmath_dd r;
  double ah, al, bh, bl;
  double p = a * b;
  split(a, &ah, &al);
  split(b, &bh, &bl);
  double e = ((ah * bh - p) + ah * bl + al * bh) + al * bl;
  r.hi = p;
  r.lo = e;
  return r;
}

/* (ah + al) * (bh + bl), relative error about 2^-103. */
static gmath_dd dd_mul(double ah, double al, double bh, double bl) {
  gmath_dd p = two_prod(ah, bh);
  double cross = ah * bl + al * bh;
  return fast_two_sum(p.hi, p.lo + cross);
}

/*
 * Reduction.  For a finite ax > pi/4, find the integer N nearest ax * 2/pi
 * and the remainder r = ax - N * pi/2, |r| <= pi/4, as a double-double.
 * Returns N mod 4.
 *
 * ax = m * 2^q with m a 53-bit integer.  ax * (2/pi) = m * 2^q * F, F the
 * binary fraction 0.b1 b2 b3 ...  A bit b_i of F contributes m * 2^(q-i) * b_i,
 * a multiple of 4 once i <= q - 2, so only bits past position 32*j0, with
 * 32*j0 <= q - 2, matter for the quadrant and the fraction.  Take 8 words
 * (256 bits) from there.  Their truncation changes the product by less than
 * 2^(53 + q - 32*(j0+8)) < 2^-168, against a fraction no smaller than about
 * 2^-62 for any double.  Shifting m left by sh = q - 32*j0 puts the binary
 * point of the 256-bit-fraction product on a word boundary: the word above
 * the fraction holds N mod 4 in its low two bits.
 */
static int reduce(double ax, double * rh, double * rl) {
  uint64_t b = bits_of(ax);
  int e = (int)(b >> 52); /* ax > pi/4 >= 2^-1 so e >= 1022 */
  uint64_t m = (b & 0xfffffffffffffull) | 0x10000000000000ull;
  int q = e - 1075;
  int t = q - 2;
  int j0 = t >= 0 ? t / 32 : -((-t + 31) / 32); /* floor(t / 32) */
  int sh = t - 32 * j0 + 2;                     /* 2 .. 33 */

  /* m << sh, as four 32-bit words, least significant first. */
  uint32_t mm[4];
  {
    int rem = sh & 31;
    int wsh = sh >> 5;
    uint64_t a0 = m & 0xffffffffull;
    uint64_t a1 = m >> 32;
    uint64_t t0 = a0 << rem;
    uint64_t t1 = (a1 << rem) + (t0 >> 32);
    uint32_t w[3];
    w[0] = (uint32_t)t0;
    w[1] = (uint32_t)t1;
    w[2] = (uint32_t)(t1 >> 32);
    mm[0] = mm[1] = mm[2] = mm[3] = 0;
    for (int i = 0; i < 3; i++) {
      mm[i + wsh] = w[i];
    }
  }

  /* The product with the 256-bit window of 2/pi. */
  uint32_t a[8];
  for (int i = 0; i < 8; i++) {
    a[i] = gmath_two_over_pi[j0 + 2 + 7 - i]; /* least significant first */
  }
  uint32_t res[12];
  for (int i = 0; i < 12; i++) {
    res[i] = 0;
  }
  for (int i = 0; i < 4; i++) {
    uint64_t carry = 0;
    for (int j = 0; j < 8; j++) {
      uint64_t cur = (uint64_t)res[i + j] + (uint64_t)mm[i] * a[j] + carry;
      res[i + j] = (uint32_t)cur;
      carry = cur >> 32;
    }
    res[i + 8] = (uint32_t)carry;
  }

  int n = (int)(res[8] & 3u);
  uint32_t f[8];
  for (int i = 0; i < 8; i++) {
    f[i] = res[i];
  }
  int negative = 0;
  if (f[7] & 0x80000000u) {
    /* fraction >= 1/2: round up to the next integer and use 1 - fraction. */
    n = (n + 1) & 3;
    negative = 1;
    uint64_t carry = 1;
    for (int i = 0; i < 8; i++) {
      uint64_t v = (uint64_t)(uint32_t)~f[i] + carry;
      f[i] = (uint32_t)v;
      carry = v >> 32;
    }
  }

  /* Normalize: the leading one of the 256-bit fraction to bit 255. */
  int lead = 255;
  while (lead > 0 && !((f[lead >> 5] >> (lead & 31)) & 1u)) {
    lead--;
  }
  int s = 255 - lead;
  int ws = s >> 5;
  int bs = s & 31;
  uint32_t g[8];
  for (int i = 0; i < 8; i++) {
    int k = i - ws;
    uint64_t v = 0;
    if (k >= 0) {
      v = (uint64_t)f[k] << bs;
      if (k > 0) {
        v |= (uint64_t)f[k - 1] >> (32 - bs); /* 32 - bs == 32 gives 0 */
      }
    }
    g[i] = (uint32_t)v;
  }
  uint64_t a1 = ((uint64_t)g[7] << 32) | g[6];
  uint64_t a2 = ((uint64_t)g[5] << 32) | g[4];

  /* fraction = a1 * 2^(-64-s) + a2 * 2^(-128-s): hi takes the top 53 bits of
   * a1, lo the next 53. */
  double hi = double_of(((uint64_t)(1022 - s) << 52) | ((a1 >> 11) & 0xfffffffffffffull));
  uint64_t lo_int = ((a1 & 0x7ffull) << 42) | (a2 >> 22);
  double lo = small_to_double(lo_int) * double_of((uint64_t)(1023 - 106 - s) << 52);
  if (negative) {
    hi = -hi;
    lo = -lo;
  }

  /* r = fraction * pi/2. */
  gmath_dd p = two_prod(hi, GMATH_PIO2_HI);
  double low = p.lo + (hi * GMATH_PIO2_LO + lo * GMATH_PIO2_HI);
  gmath_dd r = fast_two_sum(p.hi, low);
  *rh = r.hi;
  *rl = r.lo;
  return n;
}

/* Knuth's TwoSum: s + e == a + b exactly, in any order of magnitudes. */
static gmath_dd two_sum(double a, double b) {
  gmath_dd r;
  double s = a + b;
  double bb = s - a;
  double e = (a - (s - bb)) + (b - bb);
  r.hi = s;
  r.lo = e;
  return r;
}

/* The fast reduction takes arguments strictly below this, which bounds the
 * quotient n below 2^20 (x * 2/pi < 667,545) and so lets n * P1, n * P2 and
 * n * P3 (n of 20 bits, Pk of 33) be exact products. */
#define GMATH_CW_LIMIT 0x1p20

/* The remainder is declined when it is smaller than this: its error is a
 * fixed absolute amount (below), so the relative error grows as it shrinks.
 * Below 2^20 no double is closer than 2^-60 to a multiple of pi/2, so this
 * hands over only a small part of the doubles near one; it is a margin of the
 * proof, not a boundary a result can tell. */
#define GMATH_CW_MIN_R 0x1p-55

/* Added to 2/pi * x, it leaves round-to-nearest-even(2/pi * x) in the low
 * bits of the sum: 1.5 * 2^52, so the sum's ulp is 1 and its value is
 * 2^52 + 2^51 + n for any integer n below 2^31. */
#define GMATH_CW_MAGIC 0x1.8p52

/*
 * Fast reduction for pi/4 < ax < 2^20.  Gives the same n mod 4 and the same
 * remainder (rh, rl) as reduce(), to within 2^-79 |rh| in rl, or
 * declines (returns -1) and leaves the work to reduce().
 *
 * n is the nearest integer to ax * 2/pi, taken by the 2^52 + 2^51 trick: no
 * integer to double conversion, no x87.  The product and the sum are each
 * rounded, so n can be one off when ax * 2/pi is within about 2^-33 of a
 * half-integer; that case has |r| > pi/4 (or within 2^-33 of it) and is
 * declined by the range test at the end.  Where the test passes, |r| is below
 * the double pi/4, which is below the true pi/4, and so n is the nearest
 * integer exactly as reduce() takes it.
 *
 * With P1 + P2 + P3 + P4 = pi/2 (three parts of 33 bits and a double):
 *
 *   d  = ax - n*P1   exact.  n*P1 is exact (20 + 33 bits).  ax and n*P1 are
 *                    both multiples of ulp(ax) (ulp(ax) <= 2^-33 below 2^20 and
 *                    P1 is a multiple of 2^-32), and |d| is below 2^53 ulp(ax)
 *                    (|d| < pi/4 + n * 2^-33), so d needs at most 53 bits.
 *   t2 = n*P2, t3 = n*P3   exact (20 + 33 bits).
 *   (s, e1) = TwoSum(d, -t2); (s, e2) = TwoSum(s, -t3)   exact.
 *   t4 = n*P4        rounded: |t4| < 2^20 * 2^-103, so the error is below
 *                    2^-136.
 *   lo = (e1 + e2) - t4   rounded: |e1|, |e2| <= 2^-53 (|r| + 2^-45) and
 *                    |t4| < 2^-83, so the error is below 2^-106 |r| + 2^-135.
 *
 * and P4 stops at 2^-156, so the sum of the four parts misses pi/2 by less
 * than n * 2^-156 < 2^-136.  The absolute error of s + lo as the remainder is
 * therefore below 2^-106 |r| + 2^-134, and for |r| >= 2^-55 that is below
 * 2^-79 |r|.  The
 * remainder reduce() returns is good to 2^-106 |r|, so the two agree to
 * about 2^-79 |r| at the floor and to 2^-106 for ordinary r.  (Measured
 * against reduce() over 6e7 arguments and over the corpus's worst cases,
 * whose smallest |r| is 2^-60.5, they differ by at most 2^-87 |r|; the bound
 * above is the one relied on.)  Below the floor the fast path declines.
 */
static int reduce_fast(double ax, double * rh, double * rl) {
  double t = ax * GMATH_CW_INV_PIO2;
  t = t + GMATH_CW_MAGIC;
  int n = (int)(bits_of(t) & 0xffffffffu);
  double nd = t - GMATH_CW_MAGIC;
  double d = ax - nd * GMATH_CW_P1;
  gmath_dd a = two_sum(d, -(nd * GMATH_CW_P2));
  gmath_dd b = two_sum(a.hi, -(nd * GMATH_CW_P3));
  double lo = (a.lo + b.lo) - nd * GMATH_CW_P4;
  gmath_dd r = fast_two_sum(b.hi, lo);
  double mag = double_of(bits_of(r.hi) & ABS_MASK);
  if (!(mag >= GMATH_CW_MIN_R && mag <= GMATH_PIO4)) {
    return -1;
  }
  *rh = r.hi;
  *rl = r.lo;
  return n & 3;
}

/* The reduction every function uses: n mod 4, with (rh, rl) = ax - n*pi/2 for
 * the nearest integer n.  ax > pi/4. */
static int reduce_any(double ax, double * rh, double * rl) {
  if (ax < GMATH_CW_LIMIT) {
    int n = reduce_fast(ax, rh, rl);
    if (n >= 0) {
      return n;
    }
  }
  return reduce(ax, rh, rl);
}

/* sin(rh + rl) for |rh| <= pi/4 + a little, as a double-double. */
static gmath_dd kernel_sin(double rh, double rl) {
  gmath_dd z = two_prod(rh, rh);
  z.lo += 2.0 * rh * rl;
  gmath_dd r3 = dd_mul(rh, rl, z.hi, z.lo);
  gmath_dd u = dd_mul(r3.hi, r3.lo, GMATH_M1_6_HI, GMATH_M1_6_LO);
  double zz = z.hi;
  double poly = gmath_sin_coeff[GMATH_SIN_DEGREE];
  for (int i = GMATH_SIN_DEGREE - 1; i >= 0; i--) {
    poly = poly * zz + gmath_sin_coeff[i];
  }
  double tail = rh * (zz * zz) * poly;
  gmath_dd s = fast_two_sum(rh, u.hi);
  return fast_two_sum(s.hi, s.lo + (u.lo + (tail + rl)));
}

/* cos(rh + rl), as a double-double: 1 - z/2 + z^2/24 + z^3 * C(z), z = r^2.
 * The z^2/24 term is 1% of the result and so carried in double-double: in a
 * double alone its rounding costs 0.04 ulp, which showed in the corpus. */
static gmath_dd kernel_cos(double rh, double rl) {
  gmath_dd z = two_prod(rh, rh);
  z.lo += 2.0 * rh * rl;
  double zz = z.hi;
  gmath_dd w = two_prod(zz, zz);
  w.lo += 2.0 * zz * z.lo;
  gmath_dd a = dd_mul(w.hi, w.lo, GMATH_1_24_HI, GMATH_1_24_LO);
  double poly = gmath_cos_coeff[GMATH_COS_DEGREE];
  for (int i = GMATH_COS_DEGREE - 1; i >= 0; i--) {
    poly = poly * zz + gmath_cos_coeff[i];
  }
  double b = (zz * w.hi) * poly;
  gmath_dd s = fast_two_sum(1.0, -0.5 * z.hi);
  gmath_dd t = fast_two_sum(s.hi, a.hi);
  return fast_two_sum(t.hi, t.lo + (s.lo + (a.lo + (b - 0.5 * z.lo))));
}

/* (nh + nl) / (dh + dl) to within about 2^-100 relative. */
static gmath_dd dd_div(gmath_dd n, gmath_dd d) {
  double q1 = n.hi / d.hi;
  gmath_dd p = two_prod(q1, d.hi);
  double rem = ((n.hi - p.hi) - p.lo) + (n.lo - q1 * d.lo);
  double q2 = rem / d.hi;
  return fast_two_sum(q1, q2);
}

static double quiet_nan(double x) {
  /* sin(+-inf) is invalid by Annex F, and a signalling NaN raises it too:
   * x - x does both.  The value returned is the same on every target. */
  volatile double t = x - x;
  (void)t;
  return double_of(QNAN_BITS);
}

static double apply_sign(double r, uint64_t sign) {
  return double_of(bits_of(r) ^ sign);
}

double gmath_sin(double x) {
  uint64_t sign = bits_of(x) & SIGN_BIT;
  double ax = double_of(bits_of(x) & ABS_MASK);
  if (bits_of(ax) >= INF_BITS) {
    return quiet_nan(x);
  }
  if (ax < 0x1p-28) {
    return x;
  }
  double rh = ax;
  double rl = 0.0;
  int n = 0;
  if (ax > GMATH_PIO4) {
    n = reduce_any(ax, &rh, &rl);
  }
  gmath_dd r = (n & 1) ? kernel_cos(rh, rl) : kernel_sin(rh, rl);
  return apply_sign(r.hi, (n & 2) ? sign ^ SIGN_BIT : sign);
}

double gmath_cos(double x) {
  double ax = double_of(bits_of(x) & ABS_MASK);
  if (bits_of(ax) >= INF_BITS) {
    return quiet_nan(x);
  }
  if (ax < 0x1p-27) {
    return 1.0;
  }
  double rh = ax;
  double rl = 0.0;
  int n = 0;
  if (ax > GMATH_PIO4) {
    n = reduce_any(ax, &rh, &rl);
  }
  gmath_dd r = (n & 1) ? kernel_sin(rh, rl) : kernel_cos(rh, rl);
  /* cos: + sin(r)... by quadrant: n=0 cos, 1 -sin, 2 -cos, 3 sin. */
  return apply_sign(r.hi, ((n + 1) & 2) ? SIGN_BIT : 0);
}

double gmath_tan(double x) {
  uint64_t sign = bits_of(x) & SIGN_BIT;
  double ax = double_of(bits_of(x) & ABS_MASK);
  if (bits_of(ax) >= INF_BITS) {
    return quiet_nan(x);
  }
  if (ax < 0x1p-28) {
    return x;
  }
  double rh = ax;
  double rl = 0.0;
  int n = 0;
  if (ax > GMATH_PIO4) {
    n = reduce_any(ax, &rh, &rl);
  }
  gmath_dd s = kernel_sin(rh, rl);
  gmath_dd c = kernel_cos(rh, rl);
  gmath_dd t = (n & 1) ? dd_div(c, s) : dd_div(s, c);
  /* tan(x) = tan(r) for even n, -cot(r) for odd n. */
  return apply_sign(t.hi, (n & 1) ? sign ^ SIGN_BIT : sign);
}
