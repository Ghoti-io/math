/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Finite exponent-domain checks, separate from raw input coverage.
 */
#ifndef GHOTI_IO_GMATH_TEST_EXPONENT_VALUE_DOMAIN_H
#define GHOTI_IO_GMATH_TEST_EXPONENT_VALUE_DOMAIN_H
#include "exponent_value_probe.h"

/* Independent exact encoding of a small integer, using only unsigned bits. */
static uint64_t expv_integer_bits(int value, unsigned width) {
  if (!value) {
    return 0;
  }
  unsigned p = width == 64 ? 52u : 23u, bias = width == 64 ? 1023u : 127u;
  unsigned magnitude = (unsigned)(value < 0 ? -value : value), top = 0;
  for (unsigned n = magnitude; n >> 1; n >>= 1) {
    ++top;
  }
  uint64_t sign = value < 0 ? UINT64_C(1) << (width - 1) : 0;
  uint64_t fraction = ((uint64_t)magnitude ^ (UINT64_C(1) << top)) << (p - top);
  return sign | ((uint64_t)(bias + top) << p) | fraction;
}
static int expv_domain(unsigned width, int verbose) {
  fenv_t saved;
  int saved_errno = errno, status = 1;
  if (fegetenv(&saved)) {
    return 1;
  }
  int low = width == 64 ? -1074 : -149, high = width == 64 ? 1023 : 127;
  int minimum = width == 64 ? -1022 : -126, bias = width == 64 ? 1023 : 127;
  unsigned p = width == 64 ? 52u : 23u;
  int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  int flags[] = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
                 FE_INEXACT};
  uint64_t hash = GMATH_FNV_BASIS, cases = 0;
  if (expv_reference_alias()) {
    fputs("exponent domain reference aliases current function\n", stderr);
    goto done;
  }
  for (int exponent = low; exponent <= high; exponent++) {
    uint64_t a = exponent < minimum ? UINT64_C(1) << (unsigned)(exponent - low)
                                    : (uint64_t)(exponent + bias) << p;
    uint64_t target = expv_integer_bits(exponent, width);
    for (unsigned negative = 0; negative < 2; negative++) {
      uint64_t raw = a | ((uint64_t)negative << (width - 1));
      for (unsigned mode = 0; mode < 4; mode++) {
        for (unsigned subset = 0; subset < 32; subset++) {
          int incoming = 0;
          for (unsigned bit = 0; bit < 5; bit++) {
            if (subset & (1u << bit)) {
              incoming |= flags[bit];
            }
          }
          for (unsigned error = 0; error < 2; error++) {
            if (expv_call(raw, target, 0, width, modes[mode], incoming,
                          error ? 733 : 0, &hash)) {
              goto done;
            }
            ++cases;
          }
        }
      }
    }
  }
  if (cases != (uint64_t)(high - low + 1) * UINT64_C(512)) {
    fputs("exponent domain accounting mismatch\n", stderr);
    goto done;
  }
  if (verbose) {
    printf("exponent.domain%u values %u modes 4 signs 2 subsets 32 errno 2 "
           "cases %" PRIu64 " hash %016" PRIx64 "\n",
           width, (unsigned)(high - low + 1), cases, hash);
  }
  status = 0;
done:
  if (fesetenv(&saved)) {
    status = 1;
  }
  errno = saved_errno;
  return status;
}
#endif
