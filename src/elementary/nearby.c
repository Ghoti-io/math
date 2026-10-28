/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Mode-aware integral rounding from binary positional arithmetic. Old rint is
 * deliberately mode-independent and remains unchanged. Valid paths use no FP
 * arithmetic and never clear or raise exceptions; only signaling NaNs add IV.
 */
#include "elem_common.h"
#include "nearby_mode.h"
#include <float.h>
#include <ghoti.io/math/basic.h>
GMATH_STATIC_ASSERT(sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 &&
        FLT_MANT_DIG == 24 && FLT_MAX_EXP == 128,
    "nearbyintf requires IEEE binary32");

static uint64_t nearby_word(
    uint64_t raw, unsigned p, unsigned eb, unsigned bias) {
  uint64_t sign_bit = UINT64_C(1) << (p + eb), sign = raw & sign_bit,
           a = raw & (sign_bit - 1);
  uint64_t inf = ((UINT64_C(1) << eb) - 1) << p, quiet = UINT64_C(1) << (p - 1);
  if (a > inf) {
    if (!(a & quiet))
      (void)gmath_invalid();
    return inf | quiet;
  }
  uint64_t one = (uint64_t)bias << p;
  if (!a || a >= ((uint64_t)(bias + p) << p))
    return raw;
  uint64_t unit = 0, fraction = 0, base = 0;
  if (a >= one) {
    unsigned cut = bias + p - (unsigned)(a >> p); /* 1<=cut<=p<=52. */
    unit = UINT64_C(1) << cut;
    fraction = a & (unit - 1);
    base = a & ~(unit - 1);
    if (!fraction)
      return raw;
  }
  int mode = nearby_mode();
  unsigned increment;
  if (mode == 2)
    increment = (sign == 0);
  else if (mode == 1)
    increment = (sign != 0);
  else if (mode == 3)
    increment = 0;
  else if (a < one)
    increment = a > ((uint64_t)(bias - 1) << p);
  else
    increment = fraction > (unit >> 1) ||
        (fraction == (unit >> 1) && ((base & unit) != 0));
  if (a < one)
    return sign | (increment ? one : 0);
  /* Incrementing one encoded integer unit can carry only as far as 2^p. */
  return sign | (base + (increment ? unit : 0));
}
double gmath_nearbyint(double x) {
  return gmath_double(nearby_word(gmath_bits(x), 52, 11, 1023));
}
float gmath_nearbyintf(float x) {
  uint32_t raw;
  memcpy(&raw, &x, sizeof raw);
  raw = (uint32_t)nearby_word(raw, 23, 8, 127);
  float result;
  memcpy(&result, &raw, sizeof result);
  return result;
}
