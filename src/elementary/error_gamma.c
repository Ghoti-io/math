/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Independently derived Taylor/Laplace continued fraction and
 * recurrence/Stirling/reflection. All approximation arithmetic is integer
 * MP256, isolated from caller rounding, flags and floating controls.
 */
#include "elem_common.h"
#include "remaining_mp.h"
#include "remaining_mp_coeff.h"
#include <ghoti.io/math/elementary.h>

static rmp eg_log(rmp x) {
  int e = x.e;
  x.e = 0;
  rmp one = rm_uint(1), z = rm_div(rm_sub(x, one), rm_add(x, one)),
      z2 = rm_mul(z, z), t = z, sum = z;
  for (unsigned k = 3; k <= 401; k += 2) {
    t = rm_mul(t, z2);
    sum = rm_add(sum, rm_over(t, k));
  }
  return rm_add(rm_scale(sum, 1), rm_mul(rm_int(e), rm_ln2));
}
static rmp eg_exp(rmp x) {
  /* Reduce with a small integer found through MP comparison, not a host cast.
   */
  rmp q = rm_div(x, rm_ln2);
  int n = 0;
  if (rm_nonzero(q) && q.e >= 0) {
    for (int i = 255; i >= 255 - q.e; --i)
      n = (n << 1) | (int)rm_bit(q, i);
    if (q.s)
      n = -n;
  }
  rmp r = rm_sub(x, rm_mul(rm_int(n), rm_ln2)), term = rm_uint(1), sum = term;
  for (unsigned k = 1; k <= 128; ++k) {
    term = rm_over(rm_mul(term, r), k);
    sum = rm_add(sum, term);
  }
  return rm_scale(sum, n);
}
static rmp eg_erf(rmp x) {
  rmp xx = rm_neg(rm_mul(x, x)), term = x, sum = x;
  for (unsigned k = 1; k < 160; ++k) {
    term = rm_over(rm_mul(term, xx), k);
    sum = rm_add(sum, rm_over(term, 2 * k + 1));
  }
  return rm_mul(sum, rm_two_sqrtpi);
}
static rmp eg_erfc(rmp x) {
  if (x.e < 2 || (x.e == 2 && rm_cmp(x, rm_uint(4)) <= 0))
    return rm_sub(rm_uint(1), eg_erf(x));
  /* Laplace: exp(-x*x)/sqrt(pi)/(x+(1/2)/(x+1/(x+...))). */
  rmp c = rm_zero();
  for (int k = 256; k >= 1; --k)
    c = rm_div(rm_scale(rm_uint((unsigned)k), -1), rm_add(x, c));
  return rm_over(
      rm_mul(rm_div(eg_exp(rm_neg(rm_mul(x, x))), rm_add(x, c)), rm_two_sqrtpi),
      2);
}
static rmp eg_lgamma_positive(rmp x) {
  rmp product = rm_uint(1), y = x, one = rm_uint(1);
  while (rm_cmp(y, rm_uint(64)) < 0) {
    product = rm_mul(product, y);
    y = rm_add(y, one);
  }
  rmp inv = rm_div(one, y), inv2 = rm_mul(inv, inv), power = inv,
      sum = rm_zero();
  for (unsigned k = 0; k < 64; ++k) {
    sum = rm_add(sum, rm_mul(rm_stirling[k], power));
    power = rm_mul(power, inv2);
  }
  return rm_sub(
      rm_add(rm_sub(rm_mul(rm_sub(y, rm_scale(one, -1)), eg_log(y)), y),
          rm_add(rm_logsqrt2pi, sum)),
      eg_log(product));
}
/* Fractional reduction is exact in MP256 for every noninteger binary64.
 * sin(pi*f) uses f<=1/2; the sign is determined by floor(abs(x)). */
static rmp eg_sinpi(rmp x, int * negative) {
  rmp integer = x;
  for (int i = 0; i < 256; ++i)
    if (i < 255 - x.e)
      integer.w[i / 32] &= ~(UINT32_C(1) << (i % 32));
  *negative = (int)rm_bit(x, 255 - x.e);
  rmp f = rm_sub(x, integer), half = rm_scale(rm_uint(1), -1);
  if (rm_cmp(f, half) > 0)
    f = rm_sub(rm_uint(1), f);
  rmp t = rm_mul(rm_pi, f), sum = t, sq = rm_neg(rm_mul(t, t));
  for (unsigned k = 1; k <= 100; ++k) {
    t = rm_over(rm_over(rm_mul(t, sq), 2 * k), 2 * k + 1);
    sum = rm_add(sum, t);
  }
  return sum;
}
static void eg_inexact(void) {
  volatile double one = 1.0, tiny = 0x1p-54;
  volatile double ignored = one + tiny;
  (void)ignored;
}
static uint64_t eg_finish(rmp a, unsigned p, int bias) {
  uint64_t result = rm_pack(a, p, bias),
           sign = UINT64_C(1) << (p + (p == 52 ? 11 : 8)),
           mag = result & (sign - 1), inf = (uint64_t)(2 * bias + 1) << p;
  if (mag == inf)
    (void)gmath_overflow(0);
  else if (mag < (UINT64_C(1) << p))
    (void)gmath_underflow(0);
  else
    eg_inexact();
  return result;
}
static uint64_t eg_core(uint64_t raw, unsigned p, int bias, unsigned kind) {
  uint64_t sign = UINT64_C(1) << (p + (p == 52 ? 11 : 8)), a = raw & (sign - 1),
           inf = (uint64_t)(2 * bias + 1) << p, quiet = UINT64_C(1) << (p - 1),
           one = (uint64_t)bias << p;
  int neg = (raw & sign) != 0;
  if (a > inf) {
    if (!(raw & quiet))
      (void)gmath_invalid();
    return inf | quiet;
  }
  if (a == inf) {
    if (kind == 0)
      return one | (raw & sign);
    if (kind == 1)
      return neg ? ((uint64_t)(bias + 1) << p) : 0;
    if (kind == 3 || !neg)
      return inf;
    (void)gmath_invalid();
    return inf | quiet;
  }
  if (!a) {
    if (kind == 0)
      return raw;
    if (kind == 1)
      return one;
    (void)gmath_div_by_zero(0);
    return inf | (kind == 2 ? (raw & sign) : 0);
  }
  rmp x = rm_raw(a, p, bias);
  if (kind >= 2) {
    int integer = x.e >= (int)p;
    if (!integer && x.e >= 0) {
      integer = 1;
      for (int i = 0; i < 255 - x.e; ++i)
        if (rm_bit(x, i)) {
          integer = 0;
          break;
        }
    }
    if (neg && integer) {
      if (kind == 2) {
        (void)gmath_invalid();
        return inf | quiet;
      }
      (void)gmath_div_by_zero(0);
      return inf;
    }
    if (!neg && (a == one || a == ((uint64_t)(bias + 1) << p))) {
      if (kind == 3)
        return 0;
      return one;
    }
    if (kind == 2 && !neg && rm_cmp(x, rm_uint(172)) >= 0) {
      (void)gmath_overflow(0);
      return inf;
    }
    /* Protect exp and the independent instruments from astronomical powers. */
    int sine_negative = 0;
    rmp sine = rm_zero();
    if (neg)
      sine = eg_sinpi(x, &sine_negative);
    int result_negative = neg && !sine_negative;
    if (kind == 2 && neg && rm_cmp(x, rm_uint(256)) >= 0) {
      (void)gmath_underflow(0);
      return result_negative ? sign : 0;
    }
    rmp value;
    if (neg)
      value = rm_sub(rm_sub(rm_logpi, eg_log(sine)),
          eg_lgamma_positive(rm_add(x, rm_uint(1))));
    else
      value = eg_lgamma_positive(x);
    if (kind == 2) {
      if (rm_cmp(value, rm_uint(800)) > 0 && !value.s) {
        (void)gmath_overflow(0);
        return inf | (result_negative ? sign : 0);
      }
      if (value.s && rm_cmp(value, rm_uint(800)) > 0) {
        (void)gmath_underflow(0);
        return result_negative ? sign : 0;
      }
      value = eg_exp(value);
      value.s = result_negative;
    }
    return eg_finish(value, p, bias);
  }
  if (kind == 0) {
    if (rm_cmp(x, rm_uint(7)) >= 0) {
      eg_inexact();
      return one | (raw & sign);
    }
    rmp value =
        rm_cmp(x, rm_uint(4)) <= 0 ? eg_erf(x) : rm_sub(rm_uint(1), eg_erfc(x));
    value.s = neg;
    return eg_finish(value, p, bias);
  }
  if (rm_cmp(x, rm_uint(28)) >= 0) {
    if (neg) {
      eg_inexact();
      return (uint64_t)(bias + 1) << p;
    }
    (void)gmath_underflow(0);
    return 0;
  }
  rmp value = eg_erfc(x);
  if (neg)
    value = rm_sub(rm_uint(2), value);
  return eg_finish(value, p, bias);
}
#define EG_DOUBLE(name, kind)                                                  \
  double gmath_##name(double x) {                                              \
    return gmath_double(eg_core(gmath_bits(x), 52, 1023, kind));               \
  }
#define EG_FLOAT(name, kind)                                                   \
  float gmath_##name##f(float x) {                                             \
    uint32_t b;                                                                \
    memcpy(&b, &x, 4);                                                         \
    b = (uint32_t)eg_core(b, 23, 127, kind);                                   \
    memcpy(&x, &b, 4);                                                         \
    return x;                                                                  \
  }
EG_DOUBLE(erf, 0)
EG_DOUBLE(erfc, 1) EG_DOUBLE(tgamma, 2) EG_DOUBLE(lgamma, 3) EG_FLOAT(erf, 0)
    EG_FLOAT(erfc, 1) EG_FLOAT(tgamma, 2) EG_FLOAT(lgamma, 3)
