/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 */
#include "../tests/exponent_value_domain.h"
#ifndef GMATH_LOGB_REFERENCE
#error "Actual prior exponent reference functions and identity are required"
#endif
int main(int argc, char ** argv) {
  (void)argv;
  if (argc != 1) {
    return 2;
  }
  fputs(GMATH_EXPONENT_BASELINE_IDENTITY, stdout);
  int d = expv_domain(64, 1), f = expv_domain(32, 1);
  return d || f ? 1 : 0;
}
