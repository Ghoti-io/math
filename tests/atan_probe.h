/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Raw unary arctangent state calls; no signaling-input widening.
 */
#ifndef GMATH_TEST_ATAN_PROBE_H
#define GMATH_TEST_ATAN_PROBE_H
#include <ghoti.io/math/elementary.h>
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include "fp_controls.h"

static int a64_observe(uint64_t input, uint64_t expected, unsigned flags,
    int strict, int mode, unsigned subset, int error, uint64_t * output) {
  fenv_t saved;
  int saved_errno = errno, status = 1;
  if (fegetenv(&saved)) {return 1;}
  const int kinds[] = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW, FE_INEXACT};
  int seed = 0;
  for (unsigned i = 0; i < 5; ++i) {
    if (subset & (1u << i)) {seed |= kinds[i];}
  }
  if (fesetround(mode) || feclearexcept(FE_ALL_EXCEPT) || feraiseexcept(seed)) {goto done;}
  {
    int incoming = fetestexcept(FE_ALL_EXCEPT);
    uint64_t controls = gmath_test_controls();
    double argument, result;
    uint64_t got;
    memcpy(&argument, &input, sizeof argument);
    errno = error;
    result = gmath_atan(argument);
    memcpy(&got, &result, sizeof got);
    int observed = fetestexcept(FE_ALL_EXCEPT), got_errno = errno;
    int got_mode = fegetround();
    uint64_t got_controls = gmath_test_controls();
    int want = incoming | ((flags & 1u) ? FE_INVALID : 0) |
        ((flags & 2u) ? FE_INEXACT : 0) | ((flags & 4u) ? FE_UNDERFLOW : 0);
    uint64_t magnitude = got & UINT64_C(0x7fffffffffffffff);
    int numerical = strict ? got == expected :
        (magnitude >= UINT64_C(0x0010000000000000) &&
         magnitude < UINT64_C(0x7ff0000000000000) &&
         (got >> 63) == (input >> 63));
    if (!numerical || observed != want || got_errno != error ||
        got_mode != mode || got_controls != controls) {
      fprintf(stderr, "atan mismatch x%016" PRIx64 " got%016" PRIx64
          "/%016" PRIx64 " flags%x/%x errno%d/%d mode%d/%d\n",
          input, got, expected, observed, want, got_errno, error, got_mode, mode);
      goto done;
    }
    if (output) {*output = got;}
    status = 0;
  }
done:
  if (fesetenv(&saved)) {status = 1;}
  errno = saved_errno;
  return status;
}
static int a64_call(uint64_t input, uint64_t expected, unsigned flags,
    int strict, int mode, unsigned subset, int error) {
  return a64_observe(input, expected, flags, strict, mode, subset, error, NULL);
}
#endif
