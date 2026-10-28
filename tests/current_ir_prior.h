/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 */
#ifndef GMATH_TEST_CURRENT_IR_PRIOR_H
#define GMATH_TEST_CURRENT_IR_PRIOR_H
#if defined(GMATH_CURRENTINT_REFERENCE)
#ifndef GMATH_CURRENTINT_BASELINE_IDENTITY
#error Actual-prior hooks require a validated generated identity header
#endif
#ifdef __cplusplus
extern "C" {
#endif
long gmath_lrint_prior(double);
long gmath_lrintf_prior(float);
long long gmath_llrint_prior(double);
long long gmath_llrintf_prior(float);
#ifdef __cplusplus
}
#endif
#endif
#endif
