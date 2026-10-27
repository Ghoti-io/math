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
 * Each function uses IEEE 754 addition, subtraction, multiplication and
 * division in a fixed order, integer arithmetic and, in `gmath_hypot`, this
 * library's own correctly rounded square root (basic.h).  It never calls the
 * C library's `<math.h>` (`make check-libm` refuses every libm symbol), never
 * relies on a fused multiply-add, and never computes in extended precision, so
 * the result does not depend on the libm, the CPU or the byte order of the host
 * (AD-17, AD-22).  The library must be built with `-ffp-contract=off` and, on
 * 32-bit x86, with SSE math;
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
 * so a huge @p x near a multiple of pi/2 is as accurate as any other (below 2^20
 * a cheaper reduction is used where it gives the same bits).  The kernel is a
 * table of the leading bits of the reduced argument with a short correction in
 * double, so the result is not always the correctly rounded one: measured over
 * `tests/corpus` it is at most 0.52 ulp, and over hundreds of millions of random
 * arguments at most 0.53 ulp.
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
 * argument reduction of ::gmath_sin; at most 0.52 ulp over `tests/corpus`, 0.53
 * over random arguments.
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
 * argument reduction of ::gmath_sin; at most 0.53 ulp over `tests/corpus`, 0.57
 * over random arguments.
 * `gmath_tan(+-0)` is `+-0` and a subnormal @p x is returned unchanged.  The
 * result is always finite: no double is close enough to an odd multiple of
 * pi/2 for the tangent to overflow.  An infinite or NaN @p x gives the NaN
 * described at ::gmath_sin.
 *
 * @param x The angle, in radians.
 * @return tan(@p x).
 */
GMATH_API double gmath_tan(double x);

/**
 * @brief Binary32 sine in radians, within 1 ulp under round-to-nearest.
 *
 * Signed zeros return unchanged without exceptions. Infinity gives canonical
 * float NaN with invalid; NaNs canonicalize, with invalid only for signaling
 * NaNs. Nonzero subnormal inputs return x with underflow and inexact. Other
 * inexact tiny results raise underflow/inexact; other finite calls may raise
 * inexact. errno, incoming flags and rounding mode are preserved. Accuracy
 * assumes the default IEEE round-to-nearest environment.
 *
 * @param x The binary32 angle, in radians.
 * @return sin(@p x), in binary32.
 */
GMATH_API float gmath_sinf(float x);

/**
 * @brief Binary32 cosine in radians, within 1 ulp under round-to-nearest.
 *
 * Both zeros give 1 without exceptions; subnormal arguments give 1 without
 * underflow. The NaN, infinity and state policy is that of ::gmath_sinf.
 * Inexact tiny results raise underflow/inexact; other finite calls may raise
 * inexact. Accuracy assumes round-to-nearest.
 *
 * @param x The binary32 angle, in radians.
 * @return cos(@p x), in binary32.
 */
GMATH_API float gmath_cosf(float x);

/**
 * @brief Binary32 tangent in radians, within 1 ulp under round-to-nearest.
 *
 * Signed zeros, NaNs, infinities, tiny inputs/results and state preservation
 * follow ::gmath_sinf. A final float overflow raises overflow and inexact.
 * Accuracy assumes round-to-nearest; larger finite arguments use the full
 * argument reduction of ::gmath_tan before a single float narrowing.
 *
 * @param x The binary32 angle, in radians.
 * @return tan(@p x), in binary32.
 */
GMATH_API float gmath_tanf(float x);

/**
 * @brief e raised to the power @p x.
 *
 * Within 1 ulp of the true value for every finite @p x: measured at most 0.51
 * ulp over `tests/corpus` and over 750,000 random arguments, and 0.75 for a
 * result in the subnormal range, which is rounded twice (once to 53 bits and
 * once by the scaling).  The reduction `x = n ln2/128 + r` is Tang's
 * table-driven one with a 128-entry double-double table, so the result is not
 * always the correctly rounded one.
 *
 * Special values follow C99 Annex F.  `gmath_exp(+-0)` is 1, `gmath_exp(+inf)`
 * is `+inf`, `gmath_exp(-inf)` is `+0`.  A @p x above about 709.78 overflows to
 * `+inf` (raising overflow and inexact) and one below about -745.13 underflows
 * to `+0` (raising underflow and inexact); between -745.13 and -708.40 the
 * result is subnormal.  A NaN gives the quiet NaN described at ::gmath_sin.
 *
 * @param x The exponent.
 * @return e^@p x.
 */
GMATH_API double gmath_exp(double x);

/**
 * @brief Binary32 e raised to @p x, within 1 float ulp under nearest rounding.
 *
 * Both zeros return 1, +infinity returns infinity and -infinity returns +0,
 * without exceptions. NaNs canonicalize, raising invalid only for signaling
 * NaNs. Every other finite nonzero input raises inexact, with overflow for
 * overflowing results and underflow for tiny results. The first overflowing
 * float input is 0x1.62e430p+6; inputs <=-0x1.9fe36ap+6 round to zero. Those
 * classified tails return infinity/zero in every mode. errno, mode and incoming
 * flags are preserved. Numerical accuracy assumes the default nearest
 * environment; full libm errno/directed-rounding compatibility is not promised.
 *
 * @param x The exponent.
 * @return e^@p x as a float.
 */
GMATH_API float gmath_expf(float x);

/**
 * @brief Two raised to @p x, within 1 ulp under round-to-nearest.
 *
 * Every integer exponent from -1074 through 1023 returns its exact binary
 * power without exceptions. Both zeros return 1; +infinity returns infinity,
 * and -infinity returns +0, without exceptions. NaNs are canonicalized, with
 * invalid raised for signaling NaNs. Finite x>=1024 overflows with overflow
 * and inexact; x<=-1075 rounds to +0 with underflow and inexact. Other inexact
 * subnormal results raise underflow and inexact. errno, the rounding mode and
 * incoming exceptions are preserved. Like the other elementary kernels, the
 * numerical contract assumes the default IEEE round-to-nearest environment.
 *
 * @param x The exponent.
 * @return 2^@p x.
 */
GMATH_API double gmath_exp2(double x);

/**
 * @brief Binary32 two raised to @p x, within 1 float ulp under nearest rounding.
 *
 * Integer exponents -149 through 127 return exact binary powers without
 * exceptions in every rounding mode. Both zeros return 1; +infinity returns
 * infinity and -infinity returns +0 without exceptions. NaNs canonicalize,
 * raising invalid only for signaling NaNs. Finite x>=128 returns infinity
 * with overflow/inexact; x<=-150 returns +0 with underflow/inexact. Other
 * inexact subnormal results raise underflow/inexact; noninteger normal results
 * raise inexact without underflow. errno, rounding mode and incoming flags
 * are preserved. Numerical accuracy assumes the default nearest environment;
 * full libm errno and directed-rounding compatibility are not promised.
 *
 * @param x The exponent.
 * @return 2^@p x as a float.
 */
GMATH_API float gmath_exp2f(float x);

/**
 * @brief Real cube root of @p x, within 1 ulp under round-to-nearest.
 *
 * The function is odd. Signed zeros and infinities preserve their bits without
 * exceptions. NaNs are canonicalized; signaling NaNs raise invalid. Every
 * finite nonzero input gives a normal finite result without invalid,
 * divide-by-zero, overflow or underflow. Binary powers whose exponent is a
 * multiple of three return exactly without exceptions; other exact cubes may
 * raise inexact. errno, incoming exceptions and the rounding mode are preserved.
 * Numerical accuracy assumes the default IEEE round-to-nearest environment.
 *
 * @param x The argument, of either sign.
 * @return The real cube root.
 */
GMATH_API double gmath_cbrt(double x);

/**
 * @brief The natural logarithm of @p x.
 *
 * Within 1 ulp of the true value for every positive finite @p x, subnormals
 * included: measured at most 0.51 ulp.  Near 1 the relative accuracy is kept
 * (the table has two rows whose multiplier is exactly 1).  `gmath_log(1)` is `+0`, `gmath_log(+-0)` is `-inf` (raising
 * divide-by-zero), a negative @p x (and `-inf`) gives the NaN described at
 * ::gmath_sin and raises invalid, `gmath_log(+inf)` is `+inf`, a NaN gives
 * that NaN.
 *
 * @param x The argument.
 * @return ln(@p x).
 */
GMATH_API double gmath_log(double x);

/**
 * @brief Binary32 natural logarithm, within 1 float ulp under nearest rounding.
 *
 * Both zeros return negative infinity with divide-by-zero. Negative finite
 * inputs and negative infinity return canonical NaN with invalid. Quiet NaNs
 * canonicalize without invalid; signaling NaNs raise invalid. Positive infinity
 * passes through, and input 1 returns explicit positive zero without flags in
 * every mode. Other positive finite inputs give nonzero normal results and
 * raise only inexact. errno, mode and incoming flags are preserved. Numerical
 * accuracy assumes the default nearest environment; full libm errno and
 * directed-rounding compatibility are not promised.
 *
 * @param x The argument.
 * @return ln(x) as a float.
 */
GMATH_API float gmath_logf(float x);

/**
 * @brief The base-two logarithm of @p x, within 1 ulp of the true value.
 *
 * Round to nearest is assumed, as for the other elementary kernels. Positive
 * binary powers, including subnormals, return their exact integer exponent
 * without inexact. Both zeros give -infinity and raise divide-by-zero;
 * negative values give the canonical NaN and raise invalid; +infinity is
 * returned unchanged. NaNs are canonicalized, with invalid for signaling NaNs.
 * errno and incoming exceptions are preserved.
 *
 * @param x The argument.
 * @return log2(@p x).
 */
GMATH_API double gmath_log2(double x);

/**
 * @brief The base-ten logarithm of @p x, within 1 ulp of the true value.
 *
 * The special values and default rounding-mode assumption follow ::gmath_log2.
 * log10(1) is exact +0 without exceptions. Other positive finite inputs may
 * raise inexact, including when their rounded result is an integer. errno and
 * incoming exceptions are preserved.
 *
 * @param x The argument.
 * @return log10(@p x).
 */
GMATH_API double gmath_log10(double x);

/**
 * @brief Binary32 base-ten logarithm, within 1 float ulp under nearest rounding.
 *
 * Raw NaNs, signed zeros, negative arguments and positive infinity follow
 * ::gmath_logf. Exactly representable decimal powers 10^n, n=0..10, return
 * the exact integer n without new exceptions in every mode; n=0 gives +0.
 * All other positive finite arguments give nonzero normal results with
 * inexact only. errno, mode and incoming flags are preserved. Numerical
 * accuracy assumes nearest rounding; full libm errno and directed-rounding
 * compatibility are not promised.
 *
 * @param x The argument.
 * @return log10(x) as a float.
 */
GMATH_API float gmath_log10f(float x);

/**
 * @brief The binary32 base-two logarithm, within 1 binary32 ulp.
 *
 * The special values and default rounding-mode assumption follow ::gmath_log2.
 * Every positive binary32 power of two returns its exact exponent without
 * inexact. Any returned NaN has bits 0x7fc00000. Positive finite inputs widen
 * exactly to a short polynomial evaluated in binary64, using the logarithm
 * table's exact multiplier product; the final narrowing has a one-ulp float
 * error budget. Correct rounding of every float input is not promised.
 *
 * @param x The argument.
 * @return The binary32 logarithm of @p x.
 */
GMATH_API float gmath_log2f(float x);

/**
 * @brief @p x raised to the power @p y.
 *
 * Within 1 ulp of the true value whenever the result is finite or rounds to
 * zero or infinity: measured at most 0.51 ulp, 0.75 for a result in the
 * subnormal range.  A result that is exactly representable (an integer power
 * of two, `3^5`) is returned exactly.  The special cases are C99 Annex F.9.4.4,
 * including `pow(x, +-0) == 1` and `pow(1, y) == 1` for every @p x and @p y,
 * NaNs among them; `pow(-1, +-inf) == 1`; a finite negative @p x with a finite
 * non-integer @p y is invalid and gives the NaN described at ::gmath_sin;
 * `pow(+-0, y)` is `+-inf` (divide-by-zero) for a negative @p y and `+-0` for a
 * positive one, signed when @p y is an odd integer.  Overflow and underflow
 * raise the exceptions IEEE 754 names.
 *
 * @param x The base.
 * @param y The exponent.
 * @return @p x raised to @p y.
 */
GMATH_API double gmath_pow(double x, double y);

/**
 * @brief The angle of the point (@p x, @p y), in radians, in (-pi, pi].
 *
 * Within 1 ulp of the true value: measured at most 0.56 ulp.  Follows C99 Annex F.9.1.4: the quadrant is
 * chosen by the signs of both arguments, including the signs of zeros
 * (`atan2(+-0, -0) == +-pi`, `atan2(+-0, +0) == +-0`), `atan2(+-inf, -inf)` is
 * `+-3pi/4`, `atan2(+-inf, +inf)` is `+-pi/4`, an infinite and a finite
 * argument give `0`, `+-pi/2` or `+-pi`.  The results for the multiples of
 * pi/4 are the correctly rounded constants.  A NaN gives the NaN described at
 * ::gmath_sin.
 *
 * @param y The ordinate.
 * @param x The abscissa.
 * @return atan2(@p y, @p x).
 */
GMATH_API double gmath_atan2(double y, double x);

/**
 * @brief Binary32 atan2(y,x), within 1 float ulp under nearest rounding.
 *
 * Any signaling NaN gives canonical NaN with invalid; other NaNs canonicalize
 * without invalid. Signed zeros and infinities follow atan2's quadrants.
 * Zero angles are exact; all nonzero mathematical angles require inexact,
 * including tiny angles rounded to signed zero. Positive-x ratios below
 * 2^-30 use true nearest tiny results in every mode, with underflow exactly
 * when the rounded magnitude is zero/subnormal (tininess after rounding).
 * Axis, infinite and equal-magnitude angles return nearest float constants
 * in every mode. Other valid results are normal; no overflow or divide-by-zero
 * is raised. errno, mode and incoming flags are preserved. General accuracy
 * assumes nearest; full directed libm numerical/errno semantics are not promised.
 *
 * @param y The ordinate.
 * @param x The abscissa.
 * @return The angle in [-pi,pi], with the sign of y.
 */
GMATH_API float gmath_atan2f(float y, float x);

/**
 * @brief Binary32 arctangent, within 1 float ulp under nearest rounding.
 *
 * Signaling NaNs give canonical NaN with invalid; quiet NaNs canonicalize
 * without invalid. Signed zeros are exact. Infinities return nearest signed
 * pi/2 in every mode. Every nonzero valid angle requires inexact; subnormal
 * inputs also require underflow (tininess after rounding). For |x| < 2^-30,
 * the result is exactly the input bits in every mode. errno, rounding mode
 * and incoming flags are preserved. General accuracy assumes nearest;
 * full directed libm numerical/errno semantics are not promised.
 *
 * @param x The tangent of the angle.
 * @return The angle in [-pi/2,pi/2], with the sign of x.
 */
GMATH_API float gmath_atanf(float x);

/**
 * @brief sqrt(@p x * @p x + @p y * @p y), without spurious overflow or underflow.
 *
 * Within 1 ulp of the true value: measured at most 0.5000 ulp over the corpus and
 * 0.75 for a subnormal result, which is rounded twice.  The result is
 * infinite if either argument is infinite, even if the other is a NaN; it is
 * otherwise NaN if either is a NaN; and `gmath_hypot(+-0, +-0)` is `+0`.
 * Overflow is raised only when the result does not fit.  The square root is
 * ::gmath_sqrt (the instruction where the target's rounds correctly, the portable
 * method elsewhere; the same bits), not libm's.
 *
 * @param x One leg.
 * @param y The other leg.
 * @return The length of the hypotenuse.
 */
GMATH_API double gmath_hypot(double x, double y);

/**
 * @brief Binary32 hypotenuse, correctly rounded to nearest with ties to even.
 *
 * Finite-result bits use nearest rounding independently of the current mode.
 * A signaling NaN gives canonical NaN and invalid, even with infinity.
 * Otherwise infinity dominates quiet NaNs; remaining quiet NaNs canonicalize
 * without invalid. Signs are ignored; two zeros give +0. Exact finite results
 * raise no new exceptions. Inexact results raise inexact, plus underflow only
 * when the rounded result is subnormal (tininess after rounding). Rounded
 * overflow gives infinity with overflow/inexact in every mode. errno, mode
 * and incoming flags are preserved. Full directed libm numerical/errno
 * semantics are not promised.
 *
 * @param x One leg.
 * @param y The other leg.
 * @return The length of the hypotenuse as a float.
 */
GMATH_API float gmath_hypotf(float x, float y);

#ifdef __cplusplus
}
#endif

#endif /* GHOTI_IO_GMATH_ELEMENTARY_H */
