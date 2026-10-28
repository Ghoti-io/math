/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * This client deliberately links without -lm; independent raw probes use fenv.
 */
#include "../src/elementary/nearby_mode.h"
#include <ghoti.io/math/basic.h>
#include <stdio.h>
int main(void) {
#if GMATH_NEARBY_QUERY_NATIVE || defined(GMATH_NEARBY_LINK_ALLOW_FENV)
  double (*volatile d)(double) = gmath_nearbyint;
  float (*volatile f)(float) = gmath_nearbyintf;
  if (d(1.5) != 2.0 || f(-1.5f) != -2.0f)
    return 1;
#if defined(GMATH_NEARBY_LINK_ALLOW_FENV)
  puts("nearby platform client calls both APIs with its required runtime");
#else
  puts("nearby native client links/runs without libm");
#endif
#else
  puts("nearby no-libm link: SKIPPED platform fenv-query fallback "
       "configuration");
#endif
  return 0;
}
