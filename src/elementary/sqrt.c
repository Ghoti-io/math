/*
 * SPDX-License-Identifier: LGPL-3.0-only
 *
 * Copyright (C) 2026 Corey Pennycuff
 *
 * This file is part of Ghoti.io Math.
 *
 * Ghoti.io Math is free software: you can redistribute it and/or modify it
 * under the terms of the GNU Lesser General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * Ghoti.io Math is distributed in the hope that it will be useful, but
 * WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
 * or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

/**
 * @file
 *
 * gmath_sqrt and its two variants.  The methods are described in sqrt_impl.h.
 */

#include <ghoti.io/math/macros.h>

#include <ghoti.io/math/basic.h>

#include "sqrt_impl.h"

double gmath_sqrt(double x) {
  return gmath_sqrt_impl(x);
}

double gmath_sqrt_portable(double x) {
  return gmath_sqrt_portable_impl(x);
}

double gmath_sqrt_hardware(double x) {
#ifdef GMATH_HW_SQRT
  return gmath_sqrt_hardware_impl(x);
#else
  return gmath_sqrt_portable_impl(x);
#endif
}

int gmath_sqrt_has_hardware(void) {
#ifdef GMATH_HW_SQRT
  return 1;
#else
  return 0;
#endif
}
