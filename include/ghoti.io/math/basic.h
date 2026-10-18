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
 * @file basic.h
 *
 * The square root, the rounding functions and the exponent functions on
 * `double`: the functions of `<math.h>` that C and IEEE 754 specify exactly,
 * implemented here so that no shape library takes anything from libm (AD-22).
 *
 * Each has one correct answer (the square root is correctly rounded), so each
 * is exact, not within an error: the result is the same on every target, at
 * every optimization level and in every rounding mode that matters to the
 * result (none of them reads the rounding mode; `gmath_rint` is half to even).
 * Every NaN returned is the same quiet NaN (all bits fixed), so results hash
 * identically on every target; the sign of a NaN argument is not preserved.
 * There is no `fma`: fusing is forbidden (AD-17).  See elementary.h for the
 * transcendental functions.
 */

#ifndef GHOTI_IO_GMATH_BASIC_H
#define GHOTI_IO_GMATH_BASIC_H

#include <ghoti.io/math/macros.h>

#include <limits.h>

#ifdef __cplusplus
extern "C" {
#endif

/** What ::gmath_ilogb returns for a zero. */
#define GMATH_ILOGB0 INT_MIN
/** What ::gmath_ilogb returns for a NaN.  (An infinity gives `INT_MAX`.) */
#define GMATH_ILOGBNAN INT_MAX

/**
 * @brief The correctly rounded square root of @p x.
 *
 * Where the target has a square-root instruction that rounds correctly (x86-64
 * and i686 with SSE math, aarch64, s390x, powerpc with the optional instruction,
 * sparc64, riscv with a double-precision FPU) it is used; elsewhere, and in a
 * build with `-DGMATH_SQRT_PORTABLE`, ::gmath_sqrt_portable is.  Both give the
 * same bits for every argument.  `gmath_sqrt(+-0)` is `+-0`, `gmath_sqrt(+inf)` is
 * `+inf`, a negative @p x (and `-inf`) gives the quiet NaN of the library and
 * raises invalid, a NaN gives that NaN.  Round to nearest is assumed (the
 * instruction obeys the rounding mode of the machine and the portable method
 * assumes the default).  The inexact exception is raised for an inexact
 * result by the instruction; the portable method raises it whatever the
 * result, because its arithmetic is inexact on the way.  No other exception is
 * raised but invalid.
 *
 * @param x The argument.
 * @return sqrt(@p x).
 */
GMATH_API double gmath_sqrt(double x);

/**
 * @brief The square root by the portable method (integer and double arithmetic
 * only), whatever the target: the variant that every host can run, and the
 * reference the hardware one is gated against.  Same bits as ::gmath_sqrt.
 *
 * @param x The argument.
 * @return sqrt(@p x).
 */
GMATH_API double gmath_sqrt_portable(double x);

/**
 * @brief The square root by the hardware instruction, forced.  On a target
 * without one (see ::gmath_sqrt_has_hardware) this is ::gmath_sqrt_portable.
 *
 * @param x The argument.
 * @return sqrt(@p x).
 */
GMATH_API double gmath_sqrt_hardware(double x);

/**
 * @brief Whether ::gmath_sqrt and ::gmath_sqrt_hardware use a square-root
 * instruction in this build.
 *
 * @return 1 if they do, 0 if they use the portable method.
 */
GMATH_API int gmath_sqrt_has_hardware(void);

/**
 * @brief The largest integer not greater than @p x.  `floor(-0)` is `-0`,
 * `floor(x)` for `-1 < x < 0` is `-1`, an infinity is returned unchanged, a
 * NaN gives the library's NaN.
 *
 * @param x The argument.
 * @return floor(@p x).
 */
GMATH_API double gmath_floor(double x);

/**
 * @brief The smallest integer not less than @p x.  `ceil(-0)` is `-0`, and so
 * is `ceil(x)` for `-1 < x < 0`.
 *
 * @param x The argument.
 * @return ceil(@p x).
 */
GMATH_API double gmath_ceil(double x);

/**
 * @brief @p x with its fraction dropped (rounded toward zero), keeping the sign
 * of a zero result.
 *
 * @param x The argument.
 * @return trunc(@p x).
 */
GMATH_API double gmath_trunc(double x);

/**
 * @brief @p x rounded to the nearest integer, halfway cases away from zero
 * (`round(0.5)` is 1, `round(-2.5)` is -3).  A zero result keeps the sign of
 * @p x.
 *
 * @param x The argument.
 * @return round(@p x).
 */
GMATH_API double gmath_round(double x);

/**
 * @brief @p x rounded to the nearest integer, halfway cases to the even integer
 * (`rint(0.5)` is 0, `rint(1.5)` is 2, `rint(2.5)` is 2).  The current rounding
 * mode is not used.  A zero result keeps the sign of @p x.  No exception is
 * raised for an inexact result.
 *
 * @param x The argument.
 * @return rint(@p x).
 */
GMATH_API double gmath_rint(double x);

/**
 * @brief The magnitude of @p x.  A NaN gives the library's NaN.
 *
 * @param x The argument.
 * @return |@p x|.
 */
GMATH_API double gmath_fabs(double x);

/**
 * @brief The magnitude of @p x with the sign bit of @p y (the sign of a zero or
 * a NaN @p y included).  A NaN @p x gives the library's NaN, whatever @p y.
 *
 * @param x The magnitude.
 * @param y The sign.
 * @return |@p x| with the sign of @p y.
 */
GMATH_API double gmath_copysign(double x, double y);

/**
 * @brief @p x times 2 to the @p n, exactly unless the result overflows (an
 * infinity of the sign of @p x, with overflow raised) or is subnormal (rounded
 * once, to nearest, ties to even, with underflow raised when inexact).  A zero,
 * an infinity and a NaN are returned as they are (a NaN as the library's).
 *
 * @param x The significand.
 * @param n The exponent.
 * @return @p x * 2^@p n.
 */
GMATH_API double gmath_scalbn(double x, int n);

/**
 * @brief The same as ::gmath_scalbn (the radix is 2).
 *
 * @param x The significand.
 * @param n The exponent.
 * @return @p x * 2^@p n.
 */
GMATH_API double gmath_ldexp(double x, int n);

/**
 * @brief Splits @p x into a fraction of magnitude in [0.5, 1) and a power of two:
 * `x = f * 2^*e`.  A subnormal @p x is split exactly.  For a zero, an infinity
 * or a NaN the result is @p x (a NaN as the library's) and `*e` is 0.
 *
 * @param x The argument.
 * @param e Receives the exponent; may be NULL.
 * @return The fraction, with the sign of @p x.
 */
GMATH_API double gmath_frexp(double x, int * e);

/**
 * @brief The unbiased exponent of @p x as an integer: `floor(log2(|x|))`, for a
 * subnormal as well.  A zero gives ::GMATH_ILOGB0, an infinity `INT_MAX`, a NaN
 * ::GMATH_ILOGBNAN, each raising invalid.
 *
 * @param x The argument.
 * @return The exponent.
 */
GMATH_API int gmath_ilogb(double x);

#ifdef __cplusplus
}
#endif

#endif /* GHOTI_IO_GMATH_BASIC_H */
