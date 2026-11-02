/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Raw Float dispatch, existing own Double pow, integer final Float packing.
 */
#include "elem_common.h"
#include "remaining_mp.h"
#include <ghoti.io/math/elementary.h>
/* A dyadic result of a positive power has an odd part with at most24 bits.
 * Remove an exact 2^q-th root first; then the remaining odd power is bounded
 * by3^15<2^24. Negative powers with odd base>1 cannot be dyadic. */
static int fp_exact_dyadic(
    uint32_t ax, uint32_t by, uint32_t sign, uint32_t * out) {
  if (by >> 31)
    return 0;
  uint32_t ay = by & UINT32_C(0x7fffffff);
  unsigned xf = ax >> 23, yf = ay >> 23;
  uint32_t xm = (ax & UINT32_C(0x7fffff)) | (xf ? UINT32_C(0x800000) : 0),
           ym = (ay & UINT32_C(0x7fffff)) | (yf ? UINT32_C(0x800000) : 0);
  int xe = xf ? (int)xf - 150 : -149, ye = yf ? (int)yf - 150 : -149;
  while (!(xm & 1)) {
    xm >>= 1;
    ++xe;
  }
  while (!(ym & 1)) {
    ym >>= 1;
    ++ye;
  }
  if (xm == 1)
    return 0;
  if (ye < 0) {
    unsigned q = (unsigned)(-ye);
    if (q > 4)
      return 0;
    int divisor = 1 << (unsigned)q;
    if (xe % divisor)
      return 0;
    xe /= divisor;
    for (unsigned i = 0; i < q; ++i) {
      uint32_t lo = 1, hi = 4096;
      while (hi - lo > 1) {
        uint32_t mid = lo + (hi - lo) / 2;
        if ((uint64_t)mid * mid <= xm)
          lo = mid;
        else
          hi = mid;
      }
      if ((uint64_t)lo * lo != xm)
        return 0;
      xm = lo;
    }
    ye = 0;
  }
  if (ye > 3 || ym > (15u >> (unsigned)ye))
    return 0;
  unsigned n = ym << (unsigned)ye;
  uint32_t odd_power = 1;
  for (unsigned i = 0; i < n; ++i) {
    if (odd_power > UINT32_C(0xffffff) / xm)
      return 0;
    odd_power *= xm;
  }
  int exponent = xe * (int)n;
  if (exponent < -149 || exponent + (int)rm_top(odd_power) > 127)
    return 0;
  rmp exact = rm_uint(odd_power);
  exact.e += exponent;
  exact.s = sign != 0;
  *out = (uint32_t)rm_pack(exact, 23, 127);
  return 1;
}

float gmath_powf(float x, float y) {
  uint32_t bx, by, r;
  memcpy(&bx, &x, 4);
  memcpy(&by, &y, 4);
  uint32_t ax = bx & UINT32_C(0x7fffffff), ay = by & UINT32_C(0x7fffffff),
           inf = UINT32_C(0x7f800000), one = UINT32_C(0x3f800000);
  int sn = (ax > inf && !(bx & UINT32_C(0x00400000))) ||
      (ay > inf && !(by & UINT32_C(0x00400000)));
  if (sn) {
    (void)gmath_invalid();
    r = inf | UINT32_C(0x00400000);
    goto done;
  }
  if (!ay || bx == one || (ax == one && ay == inf)) {
    r = one;
    goto done;
  }
  if (ax > inf || ay > inf) {
    r = inf | UINT32_C(0x00400000);
    goto done;
  }
  if (by == one) {
    r = bx;
    goto done;
  }
  int integer = 0, odd = 0;
  unsigned field = ay >> 23;
  if (field >= 127) {
    int e = (int)field - 127;
    if (e >= 24) {
      integer = 1;
    }
    else {
      uint32_t m = (ay & UINT32_C(0x007fffff)) | UINT32_C(0x00800000);
      unsigned cut = 23 - (unsigned)e;
      if (!(m & ((UINT32_C(1) << cut) - 1))) {
        integer = 1;
        odd = (int)((m >> cut) & 1);
      }
    }
  }
  uint32_t sign = (bx & UINT32_C(0x80000000)) && odd ? UINT32_C(0x80000000) : 0;
  if (ay == inf) {
    if (!ax && (by >> 31))
      (void)gmath_div_by_zero(0);
    r = ax == one ? one : ((ax > one) == !(by >> 31) ? inf : 0);
    goto done;
  }
  if (!ax) {
    if (by >> 31) {
      (void)gmath_div_by_zero(0);
      r = inf | sign;
    }
    else
      r = sign;
    goto done;
  }
  if (ax == inf) {
    r = (by >> 31 ? 0 : inf) | sign;
    goto done;
  }
  if ((bx >> 31) && !integer) {
    (void)gmath_invalid();
    r = inf | UINT32_C(0x00400000);
    goto done;
  }
  /* Exact binary-power results must not inherit Double approximation tails,
   * especially when an exact Float subnormal is approached from below. */
  unsigned xf = ax >> 23;
  uint32_t fraction = ax & UINT32_C(0x007fffff);
  if ((xf && !fraction) || (!xf && !(ax & (ax - 1)))) {
    int k = xf ? (int)xf - 127 : (int)rm_top(ax) - 149;
    if (!k) {
      r = one | sign;
      goto done;
    }
    uint32_t ym =
        (ay & UINT32_C(0x007fffff)) | (field ? UINT32_C(0x00800000) : 0);
    int ye = field ? (int)field - 127 - 23 : -149;
    uint64_t product = (uint64_t)(k < 0 ? -k : k) * ym, n = 0;
    int negative = (k < 0) ^ ((by >> 31) != 0), integral = 1, huge = 0;
    if (ye >= 0) {
      if (ye > 7 || product > (UINT64_C(149) >> (unsigned)ye))
        huge = 1;
      else
        n = product << (unsigned)ye;
    }
    else {
      unsigned cut = (unsigned)(-ye);
      if (cut >= 64 || product & ((UINT64_C(1) << cut) - 1))
        integral = 0;
      else
        n = product >> cut;
    }
    if (integral) {
      if (huge || (negative ? n >= 150 : n >= 128)) {
        if (negative) {
          (void)gmath_underflow(0);
          r = sign;
        }
        else {
          (void)gmath_overflow(0);
          r = inf | sign;
        }
        goto done;
      }
      int exponent = negative ? -(int)n : (int)n;
      r = (exponent >= -126 ? (uint32_t)(exponent + 127) << 23
                            : UINT32_C(1) << (unsigned)(exponent + 149)) |
          sign;
      goto done;
    }
  }
  if (fp_exact_dyadic(ax, by, sign, &r))
    goto done;
  {
    double wide_x = gmath_double(rm_pack(rm_raw(bx, 23, 127), 52, 1023));
    double wide_y = gmath_double(rm_pack(rm_raw(by, 23, 127), 52, 1023));
    double value = gmath_pow(wide_x, wide_y);
    uint64_t b = gmath_bits(value), a = b & GMATH_ABS_MASK;
    if (a >= GMATH_INF_BITS) {
      r = (a > GMATH_INF_BITS ? inf | UINT32_C(0x00400000) : inf) | sign;
      goto done;
    }
    r = (uint32_t)rm_pack(rm_raw(b, 52, 1023), 23, 127);
    uint32_t ar = r & UINT32_C(0x7fffffff);
    if (ar == inf)
      (void)gmath_overflow(0);
    else if (ar < UINT32_C(0x00800000)) {
      /* Every exact dyadic Float result has already dispatched. A remaining
       * tiny result is inexact even if its Double approximation lands on the
       * Float lattice, so final tininess requires UF/IX unconditionally. */
      (void)gmath_underflow(0);
    }
    else if (rm_cmp(rm_raw(r, 23, 127), rm_raw(b, 52, 1023)) != 0) {
      volatile double one_value = 1.0, tiny = 0x1p-54;
      volatile double ignored = one_value + tiny;
      (void)ignored;
    }
  }
done:
  memcpy(&x, &r, 4);
  return x;
}
