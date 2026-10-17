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
 * @file elementary.h
 *
 * Elementary functions on `double` that give the same bits on every target.
 *
 * Each function uses only IEEE 754 addition, subtraction, multiplication and
 * division in a fixed order, and integer arithmetic.  It never calls the C
 * library's `<math.h>`, never relies on a fused multiply-add, and never
 * computes in extended precision, so the result does not depend on the libm,
 * the CPU or the byte order of the host (AD-17, AD-22).  The library must be
 * built with `-ffp-contract=off` and, on 32-bit x86, with SSE math;
 * `make check-fp-contract` and `make check-no-x87` enforce both.
 */

#ifndef GHOTI_IO_GMATH_ELEMENTARY_H
#define GHOTI_IO_GMATH_ELEMENTARY_H

#include <ghoti.io/math/macros.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief The sine of @p x, in radians.
 *
 * The result is within 1 unit in the last place of the true value for every
 * finite @p x, up to `DBL_MAX`: the argument is reduced exactly (Payne-Hanek),
 * so a huge @p x near a multiple of pi/2 is as accurate as any other.  Measured
 * over `tests/corpus` it is at most 0.51 ulp.
 *
 * Special values follow C99 Annex F.  `gmath_sin(+-0)` is `+-0` and a
 * subnormal @p x is returned unchanged.  An infinite @p x raises the invalid
 * exception and gives a NaN; a NaN gives a NaN.  Every NaN returned is the
 * same quiet NaN (all bits of the sign and payload fixed), so results hash
 * identically on every target.
 *
 * @param x The angle, in radians.
 * @return sin(@p x).
 */
GMATH_API double gmath_sin(double x);

/**
 * @brief The cosine of @p x, in radians.
 *
 * Within 1 ulp of the true value for every finite @p x, with the exact
 * argument reduction of ::gmath_sin; at most 0.51 ulp over `tests/corpus`.
 * `gmath_cos(+-0)` and the cosine of any @p x below 2^-27 in magnitude is 1.
 * An infinite or NaN @p x gives the NaN described at ::gmath_sin.
 *
 * @param x The angle, in radians.
 * @return cos(@p x).
 */
GMATH_API double gmath_cos(double x);

/**
 * @brief The tangent of @p x, in radians.
 *
 * Within 1 ulp of the true value for every finite @p x, with the exact
 * argument reduction of ::gmath_sin; at most 0.51 ulp over `tests/corpus`.
 * `gmath_tan(+-0)` is `+-0` and a subnormal @p x is returned unchanged.  The
 * result is always finite: no double is close enough to an odd multiple of
 * pi/2 for the tangent to overflow.  An infinite or NaN @p x gives the NaN
 * described at ::gmath_sin.
 *
 * @param x The angle, in radians.
 * @return tan(@p x).
 */
GMATH_API double gmath_tan(double x);

#ifdef __cplusplus
}
#endif

#endif /* GHOTI_IO_GMATH_ELEMENTARY_H */
