/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff */
#ifndef GMATH_REMAINING_PROBE_H
#define GMATH_REMAINING_PROBE_H
#include "corpus_hash.h"
#include "fp_controls.h"
#include <errno.h>
#include <fenv.h>
#include <float.h>
#include <ghoti.io/math/basic.h>
#include <ghoti.io/math/elementary.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static const char * const rp_names[15] = {"erf", "erfc", "tgamma", "lgamma",
    "erff", "erfcf", "tgammaf", "lgammaf", "powf", "fma", "fmaf", "nexttoward",
    "nexttowardf", "nan", "nanf"};
static uint64_t rp_bits(double x) {
  uint64_t u;
  memcpy(&u, &x, 8);
  return u;
}
static double rp_double(uint64_t u) {
  double x;
  memcpy(&x, &u, 8);
  return x;
}
static float rp_float(uint64_t u) {
  uint32_t b = (uint32_t)u;
  float x;
  memcpy(&x, &b, 4);
  return x;
}
static uint64_t rp_fbits(float x) {
  uint32_t u;
  memcpy(&u, &x, 4);
  return u;
}
static unsigned rp_flags(int flags) {
  return ((flags & FE_INVALID) ? 1u : 0u) | ((flags & FE_INEXACT) ? 2u : 0u) |
      ((flags & FE_UNDERFLOW) ? 4u : 0u) | ((flags & FE_OVERFLOW) ? 8u : 0u) |
      ((flags & FE_DIVBYZERO) ? 16u : 0u);
}
/* Corpus flags use OF=8 independently from UF=4. */
static unsigned rp_expected(unsigned flags) {
  return flags;
}
/* Exact binary64 object expansion; no floating conversion may quiet sNaNs. */
static void rp_direction_bytes(unsigned char * bytes, size_t size, uint64_t y) {
  memset(bytes, 0, size);
#if LDBL_MANT_DIG == 53 && LDBL_MAX_EXP == 1024
  memcpy(bytes, &y, 8);
#elif LDBL_MANT_DIG == 106 && LDBL_MAX_EXP == 1024
  memcpy(bytes, &y, 8);
#elif (LDBL_MANT_DIG == 64 || LDBL_MANT_DIG == 113) && LDBL_MAX_EXP == 16384
  uint64_t fraction = y & UINT64_C(0x000fffffffffffff), m = fraction;
  unsigned field = (unsigned)((y >> 52) & 2047);
  int exponent = 0;
  if (field && field != 2047) {
    m |= UINT64_C(0x0010000000000000);
    exponent = (int)field - 1023;
  }
  else if (!field && m) {
    unsigned top = 0;
    uint64_t t = m;
    while (t >> 1) {
      t >>= 1;
      ++top;
    }
    unsigned shift = 52 - top;
    m <<= shift;
    exponent = -1022 - (int)shift;
  }
  unsigned native_exp = field == 2047 ? 32767
      : m                             ? (unsigned)(exponent + 16383)
                                      : 0;
#if LDBL_MANT_DIG == 64
  uint64_t mant =
      field == 2047 ? (fraction | UINT64_C(0x0010000000000000)) << 11 : m << 11;
  uint16_t se = (uint16_t)((y >> 48) & UINT64_C(0x8000));
  se |= (uint16_t)native_exp;
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
  memcpy(bytes, &se, 2);
  memcpy(bytes + size - 8, &mant, 8);
#else
  memcpy(bytes, &mant, 8);
  memcpy(bytes + 8, &se, 2);
#endif
#else
  uint64_t f = field == 2047 ? fraction : m & UINT64_C(0x000fffffffffffff);
  uint64_t hi = (y & UINT64_C(0x8000000000000000)) |
      ((uint64_t)native_exp << 48) | (f >> 4),
           lo = f << 60;
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
  memcpy(bytes, &hi, 8);
  memcpy(bytes + 8, &lo, 8);
#else
  memcpy(bytes, &lo, 8);
  memcpy(bytes + 8, &hi, 8);
#endif
#endif
#else
#error Unsupported native long double representation in raw test caller
#endif
}

static uint64_t rp_call(unsigned fn, uint64_t x, uint64_t y, uint64_t z) {
  double dx = rp_double(x), dy = rp_double(y), dz = rp_double(z);
  float fx = rp_float(x), fy = rp_float(y), fz = rp_float(z);
  switch (fn) {
  case 0:
    return rp_bits(gmath_erf(dx));
  case 1:
    return rp_bits(gmath_erfc(dx));
  case 2:
    return rp_bits(gmath_tgamma(dx));
  case 3:
    return rp_bits(gmath_lgamma(dx));
  case 4:
    return rp_fbits(gmath_erff(fx));
  case 5:
    return rp_fbits(gmath_erfcf(fx));
  case 6:
    return rp_fbits(gmath_tgammaf(fx));
  case 7:
    return rp_fbits(gmath_lgammaf(fx));
  case 8:
    return rp_fbits(gmath_powf(fx, fy));
  case 9:
    return rp_bits(gmath_fma(dx, dy, dz));
  case 10:
    return rp_fbits(gmath_fmaf(fx, fy, fz));
  /* Raw source double NaNs must retain signaling classification while widening
   * a direction. Construct native representation rather than floating convert.
   */
  case 11:
  case 12: {
    long double direction;
    unsigned char bytes[sizeof direction];
    rp_direction_bytes(bytes, sizeof bytes, y);
    memcpy(&direction, bytes, sizeof direction);
    return fn == 11 ? rp_bits(gmath_nexttoward(dx, direction))
                    : rp_fbits(gmath_nexttowardf(fx, direction));
  }
  case 13:
  case 14: {
    const char * tags[] = {NULL, "", "payload", (const char *)(uintptr_t)1};
    return fn == 13 ? rp_bits(gmath_nan(tags[x % 4]))
                    : rp_fbits(gmath_nanf(tags[x % 4]));
  }
  }
  return 0;
}
static int rp_accuracy(uint64_t got, uint64_t target, unsigned width,
    int64_t low, int64_t high, double * maximum) {
  unsigned p = width == 64 ? 52 : 23, bias = width == 64 ? 1023 : 127;
  uint64_t sign = UINT64_C(1) << (width - 1), a = target & (sign - 1),
           inf = (uint64_t)(2 * bias + 1) << p;
  if (a >= inf || !a)
    return got != target;
  if ((got & (sign - 1)) >= inf)
    return 1;
  uint64_t b = got & (sign - 1), distance = a > b ? a - b : b - a;
  int power = !(a & ((UINT64_C(1) << p) - 1)) && a > (UINT64_C(1) << p);
  if (((got ^ target) & sign) && b)
    return 1;
  if (distance > 1 && !(power && b < a && distance == 2))
    return 1;
  /* Adjacent words differ by exactly one target ULP, except the half-step
   * below a normal power of two. Integer ranks avoid subnormal arithmetic
   * and remain exact with both DAZ and FTZ enabled. */
  double delta = (double)distance * (b < a ? -1.0 : 1.0);
  if (power && b < a)
    delta *= 0.5;
  if (target & sign)
    delta = -delta;
  double left = delta - (double)low / 0x1p30,
         right = delta - (double)high / 0x1p30;
  if (left < 0)
    left = -left;
  if (right < 0)
    right = -right;
  double error = left > right ? left : right;
  /* If the real answer lies below a binade endpoint, its spacing is half
   * the spacing used for the stored residual. Avoid a factor-two loophole. */
  int towardzero = target & sign ? high > 0 : low < 0;
  double limit =
      (!(a & ((UINT64_C(1) << p) - 1)) && a > (UINT64_C(1) << p) && towardzero)
      ? 0.5
      : 1.0;
  double normalized = error / limit;
  if (normalized > *maximum)
    *maximum = normalized;
  return !(error <= limit);
}

static unsigned rp_operand_class(uint64_t raw, unsigned width) {
  unsigned p = width == 64 ? 52 : 23, bias = width == 64 ? 1023 : 127;
  uint64_t sign = UINT64_C(1) << (width - 1), a = raw & (sign - 1),
           inf = (uint64_t)(2 * bias + 1) << p, one = (uint64_t)bias << p;
  unsigned c = !a                      ? 0
      : a < (UINT64_C(1) << p)         ? 1
      : a == one                       ? 2
      : a < inf                        ? 3
      : a == inf                       ? 4
      : (a & (UINT64_C(1) << (p - 1))) ? 5
                                       : 6;
  return c * 2 + (raw & sign ? 1u : 0u);
}
static unsigned rp_pow_parity(uint64_t raw) {
  uint32_t a = (uint32_t)raw & UINT32_C(0x7fffffff);
  unsigned f = a >> 23;
  if (f < 127)
    return !a ? 1 : 0;
  if (f >= 151)
    return 1;
  unsigned cut = 150 - f;
  uint32_t m = (a & UINT32_C(0x7fffff)) | UINT32_C(0x800000);
  if (m & ((UINT32_C(1) << cut) - 1))
    return 0;
  return (m >> cut) & 1 ? 2 : 1;
}
static uint64_t rp_state_key(unsigned fn, unsigned width, uint64_t x,
    uint64_t y, uint64_t z, unsigned required, unsigned allowed) {
  uint64_t key = rp_operand_class(x, width);
  if (fn == 8) {
    uint32_t ax = (uint32_t)x & UINT32_C(0x7fffffff),
             ay = (uint32_t)y & UINT32_C(0x7fffffff);
    unsigned region = ay < UINT32_C(0x21800000) ? 0
        : ay < UINT32_C(0x3f800000)             ? 1
        : ay < UINT32_C(0x4b800000)             ? 2
        : ay < UINT32_C(0x5f800000)             ? 3
                                                : 4;
    key = key * 14 + rp_operand_class(y, width);
    key = key * 3 + rp_pow_parity(y);
    key = key * 5 + region;
    key = key * 3 +
        (ax < UINT32_C(0x3f800000)           ? 0
                : ax == UINT32_C(0x3f800000) ? 1
                                             : 2);
  }
  else if (fn == 9 || fn == 10) {
    key = (key * 14 + rp_operand_class(y, width)) * 14 +
        rp_operand_class(z, width);
  }
  return ((key * 32 + required) * 32 + allowed) + 1;
}

static int remaining_probe(const char * directory, int emit, int hashes) {
  char path[4096];
  if (snprintf(path, sizeof path, "%s/remaining-fifteen.corpus", directory) >=
      (int)sizeof path)
    return 1;
  FILE * f = fopen(path, "rb");
  if (!f) {
    fprintf(stderr, "remaining-fifteen: open failed %s\n", path);
    return 1;
  }
  char line[1024];
  if (fseek(f, 0, SEEK_END) || ftell(f) > 16 * 1024 * 1024 ||
      fseek(f, 0, SEEK_SET) || !fgets(line, sizeof line, f) ||
      gmath_parse_remaining_header(line)) {
    fclose(f);
    return 1;
  }
  if (!fgets(line, sizeof line, f) ||
      strcmp(line,
          "# name width mode x y z target required allowed residual-low "
          "residual-high; residual scale=2^30 ULP\n")) {
    fclose(f);
    return 1;
  }
  fenv_t saved;
  if (fegetenv(&saved)) {
    fclose(f);
    return 1;
  }
  int saved_errno = errno;
  unsigned long rows = 0, counts[15] = {0}, state_calls = 0;
  uint64_t selected[4][15][1024] = {{{0}}};
  unsigned selected_count[4][15] = {{0}};
  uint64_t hs[15];
  for (unsigned i = 0; i < 15; ++i)
    hs[i] = UINT64_C(14695981039346656037);
  int status = 0, reported = 0;
  const int modes[4] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  while (fgets(line, sizeof line, f)) {
    gmath_remaining_row row;
    if (rows >= 100000 || gmath_parse_remaining_row(line, &row)) {
      status = 1;
      break;
    }
    unsigned fn = row.fn, width = row.width, mode = row.mode,
             required = row.required, allowed = row.allowed;
    uint64_t x = row.x, y = row.y, z = row.z, target = row.target;
    int64_t lo = row.low, hi = row.high;
    const char * name = rp_names[fn];
    if (fesetround(modes[mode]) || feclearexcept(FE_ALL_EXCEPT)) {
      status = 1;
      break;
    }
    errno = 123;
    uint64_t controls = gmath_test_controls();
    uint64_t result = rp_call(fn, x, y, z);
    int observed_errno = errno, observed_mode = fegetround();
    unsigned flags = rp_flags(fetestexcept(FE_ALL_EXCEPT));
    unsigned expected = rp_expected(required), permitted = rp_expected(allowed);
    const char * stage = "accuracy";
    int bad = 0;
    if ((flags & expected) != expected || (flags & ~permitted)) {
      bad = 1;
      stage = "flags";
    }
    else if (observed_errno != 123) {
      bad = 1;
      stage = "errno";
    }
    else if (observed_mode != modes[mode]) {
      bad = 1;
      stage = "mode";
    }
    else if (gmath_test_controls() != controls) {
      bad = 1;
      stage = "controls";
    }
    uint64_t sign = UINT64_C(1) << (width - 1),
             inf = width == 64 ? UINT64_C(0x7ff0000000000000)
                               : UINT64_C(0x7f800000),
             mag = target & (sign - 1);
    if (fn == 9 || fn == 10 || fn >= 11 || mag >= inf || (!lo && !hi)) {
      if (result != target)
        bad = 1;
    }
    else {
      double maximum = 0;
      if (rp_accuracy(result, target, width, lo, hi, &maximum))
        bad = 1;
    }
    if (bad) {
      fprintf(stderr,
          "remaining-fifteen: rejected at row %lu stage=%s fn=%s x=%016" PRIx64
          " y=%016" PRIx64 " z=%016" PRIx64 " result=%016" PRIx64
          " target=%016" PRIx64 " flags=%u required=%u allowed=%u\n",
          rows + 1, stage, name, x, y, z, result, target, flags, expected,
          permitted);
      reported = 1;
      status = 1;
      break;
    }
    uint64_t key = rp_state_key(fn, width, x, y, z, required, allowed);
    unsigned slot = (fn == 9 || fn == 10) ? mode : 0, index = 0;
    while (index < selected_count[slot][fn] && selected[slot][fn][index] != key)
      ++index;
    if (index == selected_count[slot][fn]) {
      if (index == 1024) {
        status = 1;
        break;
      }
      selected[slot][fn][index] = key;
      ++selected_count[slot][fn];
      unsigned begin = (fn == 9 || fn == 10) ? mode : 0,
               end = (fn == 9 || fn == 10) ? mode + 1 : 4;
      for (unsigned m = begin; m < end; ++m)
        for (unsigned subset = 0; subset < 32; ++subset) {
          int incoming = ((subset & 1) ? FE_INVALID : 0) |
              ((subset & 2) ? FE_INEXACT : 0) |
              ((subset & 4) ? FE_UNDERFLOW : 0) |
              ((subset & 8) ? FE_OVERFLOW : 0) |
              ((subset & 16) ? FE_DIVBYZERO : 0);
          if (fesetround(modes[m]) || feclearexcept(FE_ALL_EXCEPT) ||
              feraiseexcept(incoming)) {
            status = 1;
            break;
          }
          unsigned seeded = rp_flags(fetestexcept(FE_ALL_EXCEPT));
          uint64_t state_controls = gmath_test_controls();
          errno = 991;
          ++state_calls;
          uint64_t again = rp_call(fn, x, y, z);
          unsigned state_flags = rp_flags(fetestexcept(FE_ALL_EXCEPT));
          if ((state_flags & (required | seeded)) != (required | seeded) ||
              (state_flags & ~(allowed | seeded)) || errno != 991 ||
              fegetround() != modes[m] ||
              gmath_test_controls() != state_controls ||
              ((fn != 8 || (allowed != 2 && required != 2)) &&
                  again != result)) {
            fprintf(stderr,
                "remaining-fifteen: rejected at row %lu stage=state fn=%s "
                "mode=%u incoming=%u flags=%u\n",
                rows + 1, name, m, subset, state_flags);
            reported = 1;
            status = 1;
            break;
          }
        }
      if (status)
        break;
    }
    if (emit)
      printf("remaining-result %lu %016" PRIx64 " %u\n", rows, result, flags);
    if (!mode) {
      for (unsigned j = 0; j < 8; ++j) {
        hs[fn] ^= (result >> (j * 8)) & 255;
        hs[fn] *= UINT64_C(1099511628211);
      }
      ++counts[fn];
    }
    ++rows;
  }
  if (ferror(f) || !rows || !feof(f))
    status = 1;
  for (unsigned i = 0; i < 15; ++i)
    if (!counts[i])
      status = 1;
  if (status && !reported)
    fprintf(stderr,
        "remaining-fifteen: rejected at row %lu "
        "stage=loader\n",
        rows + 1);
  fclose(f);
  if (fesetenv(&saved))
    status = 1;
  errno = saved_errno;
  if (!status) {
    fprintf(stderr,
        "remaining-fifteen: loaded %s\nremaining-fifteen: %lu rows; "
        "caller-state passed; %lu selected state calls\n",
        path, rows, state_calls);
    if (hashes)
      for (unsigned i = 0; i < 15; ++i)
        printf("math.%s.hash  %016" PRIx64 "\nmath.%s.count  %lu\n",
            rp_names[i], hs[i], rp_names[i], counts[i]);
  }
  return status;
}
#endif
