/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Exact integer-return rounding from binary representations, with no
 * floating conversions or arithmetic on valid paths.
 */
#include <ghoti.io/math/macros.h>
#include <ghoti.io/math/basic.h>
#include "elem_common.h"
#include <float.h>
#include <limits.h>

GMATH_STATIC_ASSERT((LONG_MAX == INT32_MAX || LONG_MAX == INT64_MAX) &&
                    LONG_MIN == -LONG_MAX - 1, "lround requires signed 32/64-bit long");
GMATH_STATIC_ASSERT(LLONG_MAX == INT64_MAX && LLONG_MIN == -LLONG_MAX - 1,
                    "llround requires signed 64-bit long long");
GMATH_STATIC_ASSERT(sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 &&
                    FLT_MANT_DIG == 24 && FLT_MIN_EXP == -125 && FLT_MAX_EXP == 128,
                    "integer Float rounding requires IEEE binary32");

static inline int64_t ir_invalid(uint64_t ir_maximum) {
  (void)gmath_invalid();
  return -(int64_t)ir_maximum - 1;
}

static inline int64_t ir_round(uint64_t ir_word, uint64_t ir_maximum) {
  uint64_t ir_absolute = ir_word & GMATH_ABS_MASK;
  unsigned ir_negative = (unsigned)(ir_word >> 63);
  uint64_t ir_magnitude;
  /* This bound catches all nonfinite encodings before arithmetic on input.
   * The sole admitted endpoint is the exact negative 2^63. */
  if (ir_absolute >= UINT64_C(0x43e0000000000000)) {
    if (ir_absolute == UINT64_C(0x43e0000000000000) && ir_negative &&
        ir_maximum == INT64_MAX) return INT64_MIN;
    return ir_invalid(ir_maximum);
  }
  if (ir_absolute < UINT64_C(0x3fe0000000000000)) return 0;
  if (ir_absolute < UINT64_C(0x3ff0000000000000)) {
    ir_magnitude = 1;
  }
  else {
    unsigned ir_exponent = (unsigned)(ir_absolute >> 52) - 1023u;
    uint64_t ir_significand = (ir_absolute & UINT64_C(0x000fffffffffffff)) |
        (UINT64_C(1) << 52);
    if (ir_exponent >= 52u) {
      /* Exponent <=62 by the early bound, so left shift <=10. */
      ir_magnitude = ir_significand << (ir_exponent - 52u);
    }
    else {
      unsigned ir_shift = 52u - ir_exponent; /* 1..52. */
      uint64_t ir_fraction = ir_significand & ((UINT64_C(1) << ir_shift) - 1u);
      ir_magnitude = (ir_significand >> ir_shift) +
          (uint64_t)(ir_fraction >= (UINT64_C(1) << (ir_shift - 1u)));
    }
  }
  if (ir_magnitude > ir_maximum + ir_negative) return ir_invalid(ir_maximum);
  if (ir_negative && ir_magnitude == ir_maximum + 1u) return -(int64_t)ir_maximum - 1;
  return ir_negative ? -(int64_t)ir_magnitude : (int64_t)ir_magnitude;
}

/* Inputs below half, including every subnormal, become zero bits;
 * all other finite inputs are normal and widen by exact field mapping.
 * Nonfinite payloads are transported as integers, without quieting sNaNs. */
static inline uint64_t ir_float_word(float ir_x) {
  uint32_t ir_raw;
  memcpy(&ir_raw, &ir_x, sizeof ir_raw);
  uint32_t ir_absolute = ir_raw & 0x7fffffffu;
  if (ir_absolute < 0x3f000000u) return 0;
  unsigned ir_field = ir_absolute >> 23;
  uint64_t ir_exponent = ir_field == 255u ? 2047u : ir_field + 896u;
  return ((uint64_t)(ir_raw >> 31) << 63) | (ir_exponent << 52) |
      ((uint64_t)(ir_absolute & 0x007fffffu) << 29);
}

long gmath_lround(double x) {return (long)ir_round(gmath_bits(x), LONG_MAX);}
long gmath_lroundf(float x) {return (long)ir_round(ir_float_word(x), LONG_MAX);}
long long gmath_llround(double x) {return (long long)ir_round(gmath_bits(x), LLONG_MAX);}
long long gmath_llroundf(float x) {return (long long)ir_round(ir_float_word(x), LLONG_MAX);}
