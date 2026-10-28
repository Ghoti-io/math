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
 * @file Native-long power-of-two scaling using the existing exact kernels.
 * Long comparisons precede narrowing; the saturated tails are equivalent
 * for every finite binary64/binary32 input. See documentation/design.md.
 */
#include <ghoti.io/math/basic.h>
#include <ghoti.io/math/macros.h>

double gmath_scalbln(double x, long n) {
  int k = n > 5000L ? 5000 : (n < -5000L ? -5000 : (int)n);
  return gmath_scalbn(x, k);
}
float gmath_scalblnf(float x, long n) {
  int k = n > 512L ? 512 : (n < -512L ? -512 : (int)n);
  return gmath_scalbnf(x, k);
}
