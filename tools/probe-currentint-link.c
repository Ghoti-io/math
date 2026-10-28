/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 */
#include <ghoti.io/math/basic.h>
#include "../src/elementary/nearby_mode.h"
#include <stdio.h>
int main(void) {
#if !GMATH_NEARBY_QUERY_NATIVE && !defined(GMATH_CURRENTINT_LINK_ALLOW_FENV)
  puts("currentint native no-libm client SKIPPED: platform-query configuration");
  return 0;
#else
  long (*volatile b)(double)=gmath_lrint;
  long (*volatile c)(float)=gmath_lrintf;
  long long (*volatile d)(double)=gmath_llrint;
  long long (*volatile e)(float)=gmath_llrintf;
  if (b(1.0)!=1 || c(-2.0f)!=-2 || d(3.0)!=3 || e(-4.0f)!=-4) {return 1;}
#ifdef GMATH_CURRENTINT_LINK_ALLOW_FENV
  puts("currentint platform client calls all four APIs");
#else
  puts("currentint native client links/runs without libm");
#endif
  return 0;
#endif
}
