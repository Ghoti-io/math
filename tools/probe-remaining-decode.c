/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Synthetic word fixtures execute every private representation decoder on the
 * host. These are not a substitute for another native ABI/runtime execution. */
#include "../src/elementary/remaining_exact.c"
#include <fenv.h>
#include <inttypes.h>
#include <stdio.h>
typedef struct {
  unsigned format;
  uint64_t hi, lo;
  int kind, sign, exponent, invalid;
  uint64_t x, target64, target32;
  unsigned flags;
} fixture;
static rx_direction decode(fixture v) {
  if (v.format == 64)
    return rx_decode64(v.hi);
  if (v.format == 80)
    return rx_decode80(v.lo, (uint16_t)v.hi);
  if (v.format == 128)
    return rx_decode128(v.hi, v.lo);
  return rx_decode_dd(v.hi, v.lo);
}
int main(void) {
  fixture cases[128];
  unsigned count = 0;
  for (unsigned format = 0; format < 4; ++format)
    for (unsigned sign = 0; sign < 2; ++sign) {
      unsigned fmt = (unsigned[]){64, 80, 128, 106}[format];
      uint64_t sb = (uint64_t)sign << 63;
      for (unsigned kind = 0; kind < 6; ++kind) {
        fixture v = {fmt, 0, 0, 0, (int)sign, 0, 0, 0, 0, 0, 0};
        /* zero,one,minsub,infinity,quietNaN,signalingNaN */
        v.kind = kind >= 3 ? (kind == 3 ? 2 : 3) : kind == 0 ? 0 : 1;
        v.invalid = kind == 5;
        v.exponent = kind == 2 ? (fmt == 80           ? -16445
                                         : fmt == 128 ? -16494
                                                      : -1074)
                               : 0;
        if (fmt == 64 || fmt == 106) {
          v.hi = sb |
              (kind == 1          ? UINT64_C(0x3ff0000000000000)
                      : kind == 2 ? 1
                      : kind >= 3 ? GMATH_INF_BITS
                                  : 0);
          if (kind >= 4)
            v.hi |= kind == 4 ? UINT64_C(0x0008000000000001) : 1;
        }
        if (fmt == 80) {
          v.hi = (sign ? 32768u : 0u) |
              (kind == 1          ? 16383u
                      : kind >= 3 ? 32767u
                                  : 0u);
          v.lo = kind == 1 || kind >= 3 ? UINT64_C(0x8000000000000000)
              : kind == 2               ? 1
                                        : 0;
          if (kind >= 4)
            v.lo |= kind == 4 ? UINT64_C(0x4000000000000001) : 1;
        }
        if (fmt == 128) {
          v.hi = sb |
              (kind == 1          ? UINT64_C(0x3fff000000000000)
                      : kind >= 3 ? UINT64_C(0x7fff000000000000)
                                  : 0);
          v.lo = kind == 2 || kind >= 4 ? 1 : 0;
          if (kind == 4)
            v.hi |= UINT64_C(0x0000800000000000);
        }
        v.target64 = kind == 0 ? sb : kind < 4 ? sb | 1 : GMATH_QNAN_BITS;
        v.target32 = kind == 0 ? (uint64_t)sign << 31
            : kind < 4         ? ((uint64_t)sign << 31) | 1
                               : UINT64_C(0x7fc00000);
        v.flags = kind > 3 ? (unsigned)v.invalid : kind ? 6 : 0;
        cases[count++] = v;
      }
    }
  for (unsigned sign = 0; sign < 2; ++sign) {
    fixture a = {80, (uint64_t)(sign ? 32769 : 1), UINT64_C(0x8000000000000000),
        1, (int)sign, -16382, 0, 0, ((uint64_t)sign << 63) | 1,
        ((uint64_t)sign << 31) | 1, 6};
    cases[count++] = a;
    a.hi = sign ? 32768 : 0;
    cases[count++] = a;
    fixture q = {128, ((uint64_t)sign << 63) | UINT64_C(0x0001000000000000), 0,
        1, (int)sign, -16382, 0, 0, ((uint64_t)sign << 63) | 1,
        ((uint64_t)sign << 31) | 1, 6};
    cases[count++] = q;
  }
  /* Low DD components decide direction beyond binary64; signs/exponents of
   * each component remain distinct rather than being rounded into a leader. */
  for (unsigned neg = 0; neg < 2; ++neg) {
    fixture d = {106, UINT64_C(0x3ff0000000000000),
        UINT64_C(0x3c30000000000000) | ((uint64_t)neg << 63), 1, 0, 0, 0,
        UINT64_C(0x3ff0000000000000),
        neg ? UINT64_C(0x3fefffffffffffff) : UINT64_C(0x3ff0000000000001),
        neg ? UINT64_C(0x3f7fffff) : UINT64_C(0x3f800001), 0};
    cases[count++] = d;
  }
  fixture quad = {128, UINT64_C(0x3fff000000000000), 1, 1, 0, 0, 0,
      UINT64_C(0x3ff0000000000000), UINT64_C(0x3ff0000000000001),
      UINT64_C(0x3f800001), 0};
  cases[count++] = quad;
  fixture bad = {106, UINT64_C(0x3ff0000000000000), GMATH_INF_BITS, 3, 0, 0, 1,
      0, GMATH_QNAN_BITS, UINT64_C(0x7fc00000), 1};
  cases[count++] = bad;
  bad.lo = GMATH_QNAN_BITS;
  cases[count++] = bad;
  for (unsigned fmt_index = 0; fmt_index < 4; ++fmt_index)
    for (unsigned negative = 0; negative < 2; ++negative)
      for (unsigned maximum = 0; maximum < 2; ++maximum) {
        unsigned fmt = (unsigned[]){64, 80, 128, 106}[fmt_index];
        uint64_t sign = (uint64_t)negative << 63;
        fixture v = {fmt, 0, 0, 1, (int)negative,
            maximum ? (fmt == 64 || fmt == 106 ? 1023 : 16383)
                    : (fmt == 64 || fmt == 106 ? -1022 : -16382),
            0, 0, sign | 1, ((uint64_t)negative << 31) | 1, 6};
        if (fmt == 64 || fmt == 106)
          v.hi = sign |
              (maximum ? UINT64_C(0x7fefffffffffffff)
                       : UINT64_C(0x0010000000000000));
        else if (fmt == 80) {
          v.hi = (negative ? 32768 : 0) | (maximum ? 32766 : 1);
          v.lo = maximum ? UINT64_MAX : UINT64_C(0x8000000000000000);
        }
        else {
          v.hi = sign |
              (maximum ? UINT64_C(0x7ffeffffffffffff)
                       : UINT64_C(0x0001000000000000));
          v.lo = maximum ? UINT64_MAX : 0;
        }
        cases[count++] = v;
      }
  if (rm_pack(rx_decode64(UINT64_C(0x7fefffffffffffff)).a, 52, 1023) !=
          UINT64_C(0x7fefffffffffffff) ||
      rm_pack(rx_decode128(UINT64_C(0x3fff800000000000), 0).a, 52, 1023) !=
          UINT64_C(0x3ff8000000000000) ||
      rm_pack(rx_decode128(
                  UINT64_C(0x3fff000000000000), UINT64_C(0x8000000000000000))
                  .a,
          52, 1023) != UINT64_C(0x3ff0000000000008) ||
      rm_pack(rx_decode80(UINT64_C(0xc000000000000000), 16383).a, 52, 1023) !=
          UINT64_C(0x3ff8000000000000)) {
    fprintf(stderr, "remaining-decode: exact finite significand rejected\n");
    return 1;
  }
  fenv_t saved;
  if (fegetenv(&saved))
    return 2;
  for (unsigned i = 0; i < count; ++i) {
    fixture v = cases[i];
    rx_direction d = decode(v);
    int kind = d.nan ? 3 : d.inf ? 2 : rm_nonzero(d.a) ? 1 : 0;
    if (kind != v.kind || d.sign != v.sign || d.invalid != v.invalid ||
        (kind == 1 && (d.a.e != v.exponent || d.a.s != v.sign))) {
      fprintf(stderr,
          "remaining-decode: rejected metadata vector %u format%u\n", i,
          v.format);
      return 1;
    }
    if (v.format == 106 && v.x &&
        (!rm_nonzero(d.b) || d.b.e != -60 || d.b.s != (int)(v.lo >> 63))) {
      fprintf(
          stderr, "remaining-decode: rejected low component vector %u\n", i);
      return 1;
    }
    for (unsigned width = 32; width <= 64; width += 32) {
      if (feclearexcept(FE_ALL_EXCEPT))
        return 2;
      uint64_t x = v.x ? (width == 64 ? v.x : UINT64_C(0x3f800000)) : 0;
      uint64_t got = rx_toward_direction(
          x, d, width == 64 ? 52 : 23, width == 64 ? 1023 : 127);
      int flags = fetestexcept(FE_ALL_EXCEPT);
      unsigned actual = ((flags & FE_INVALID) ? 1u : 0u) |
          ((flags & FE_INEXACT) ? 2u : 0u) | ((flags & FE_UNDERFLOW) ? 4u : 0u);
      if (got != (width == 64 ? v.target64 : v.target32) || actual != v.flags) {
        fprintf(stderr,
            "remaining-decode: rejected value vector %u width%u got%016" PRIx64
            " flags%u\n",
            i, width, got, actual);
        return 1;
      }
    }
  }
  if (fesetenv(&saved))
    return 2;
  printf("remaining-fifteen: %u synthetic decoder vectors, both result formats "
         "passed\n",
      count);
  return 0;
}
