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
 * `double`, plus binary32 square root, rounding, sign and remainder: the
 * functions of `<math.h>` that C and
 * IEEE 754 specify exactly, implemented here so that no shape library takes
 * anything from libm (AD-22).
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
 * @brief Correctly rounded binary32 square root under round-to-nearest.
 *
 * Signed zeros and +infinity return unchanged; negative arguments raise invalid
 * and give the canonical float NaN. Other NaNs canonicalize; signaling NaNs
 * raise invalid. Positive finite results are normal and may raise inexact,
 * including exact roots when the portable double kernel is used. No other
 * exception is raised. errno, incoming flags and the rounding mode survive.
 * Numerical accuracy assumes round-to-nearest, as for ::gmath_sqrt.
 *
 * @param x The binary32 argument.
 * @return sqrt(@p x), rounded once to binary32.
 */
GMATH_API float gmath_sqrtf(float x);

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
 * @brief Binary32 floor, independent of the host rounding mode.
 *
 * Signed zeros/infinities survive. The following state/NaN rules also apply
 * to ceilf, truncf, roundf, rintf, fabsf and copysignf: a NaN x becomes
 * 0x7fc00000; signaling x NaNs raise invalid; no other exception is raised.
 * errno, existing flags and rounding mode survive. copysignf additionally
 * ignores signaling status of y.
 *
 * @param x The argument.
 * @return The largest integer not greater than @p x.
 */
GMATH_API float gmath_floorf(float x);

/**
 * @brief Binary32 ceil with the state/NaN policy of ::gmath_floorf.
 * @param x The argument.
 * @return The smallest integer not less than @p x; negative zero is preserved.
 */
GMATH_API float gmath_ceilf(float x);

/**
 * @brief Binary32 truncation with the state/NaN policy of ::gmath_floorf.
 * @param x The argument.
 * @return @p x with its fraction removed, preserving a zero's sign.
 */
GMATH_API float gmath_truncf(float x);

/**
 * @brief Binary32 nearest integer, ties away from zero, in every mode.
 * @param x The argument; state/NaN policy is that of ::gmath_floorf.
 * @return The nearest integer, preserving a zero's sign.
 */
GMATH_API float gmath_roundf(float x);

/**
 * @brief Binary32 nearest integer, ties to even, in every mode.
 * @param x The argument; state/NaN policy is that of ::gmath_floorf.
 * @return The nearest even integer on a tie, preserving a zero's sign.
 */
GMATH_API float gmath_rintf(float x);

/**
 * @brief Binary32 absolute value with the state/NaN policy of ::gmath_floorf.
 * @param x The argument.
 * @return The magnitude of @p x, or the canonical float NaN.
 */
GMATH_API float gmath_fabsf(float x);

/**
 * @brief Binary32 sign copy with the state/NaN policy of ::gmath_floorf.
 * @param x The magnitude argument; its signaling NaN raises invalid.
 * @param y Supplies only sign bits; even a signaling NaN raises nothing.
 * @return The magnitude of @p x with @p y's sign, or canonical NaN for NaN x.
 */
GMATH_API float gmath_copysignf(float x, float y);

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
 * @brief Nearest integer as long, ties away from zero, independent of mode.
 *
 * Valid results are exact and raise no new exceptions, including inexact.
 * Any NaN, infinity or rounded result outside the destination range returns
 * LONG_MIN and raises invalid only. errno, rounding mode and incoming flags
 * are preserved. Supports 32-/64-bit long; full libm errno semantics are not
 * promised. The range check applies after rounding.
 * The integer return alone cannot distinguish a valid minimum from invalid
 * input. Clear FE_INVALID before the call and inspect it afterward to detect
 * this call's invalid result; an already-set invalid flag is preserved and
 * cannot identify whether this call raised it. This also applies to LLONG_MIN
 * in the long-long forms.
 * @param x The argument.
 * @return Rounded integer, or LONG_MIN on invalid input.
 */
GMATH_API long gmath_lround(double x);
/** @brief Binary32 input form of ::gmath_lround with the same contract.
 * @param x The argument.
 * @return Rounded integer, or LONG_MIN on invalid input.
 */
GMATH_API long gmath_lroundf(float x);
/** @brief 64-bit long long form of ::gmath_lround; invalid returns LLONG_MIN.
 * @param x The argument.
 * @return Rounded integer, or LLONG_MIN on invalid input.
 */
GMATH_API long long gmath_llround(double x);
/** @brief Binary32 input form of ::gmath_llround with the same contract.
 * @param x The argument.
 * @return Rounded integer, or LLONG_MIN on invalid input.
 */
GMATH_API long long gmath_llroundf(float x);

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

/**
 * @brief Binary32 x*2^n, nearest/ties-even in every rounding mode.
 *
 * Exact finite results add no flags, including exact subnormals. Finite
 * overflow returns signed infinity with overflow/inexact. Inexact rounded
 * zero/subnormal results require underflow/inexact; rounding up to minimum
 * normal requires inexact only (tininess after rounding). Signed zeros and
 * infinities are preserved; NaNs canonicalize, invalid only for sNaNs.
 * errno, mode and incoming flags are preserved. Full directed/errno libm
 * semantics are not promised. Existing Double scaling is unchanged.
 * @param x The significand.
 * @param n The exponent, including INT_MIN/INT_MAX.
 * @return The scaled Float result.
 */
GMATH_API float gmath_scalbnf(float x, int n);
/** @brief Alias of ::gmath_scalbnf with the same contract.
 * @param x The significand.
 * @param n The exponent.
 * @return The scaled Float result.
 */
GMATH_API float gmath_ldexpf(float x, int n);
/**
 * @brief Exact binary32 fraction/exponent decomposition, like ::gmath_frexp.
 *
 * A zero/infinity is preserved; NaNs canonicalize, invalid only for sNaNs.
 * For every special value the output exponent is zero. Finite nonzero values
 * return a signed fraction of magnitude [0.5,1) and reconstruct exactly.
 * No other new flags; errno, mode and incoming flags are preserved.
 * @param x The argument.
 * @param e Receives the exponent; may be NULL.
 * @return The signed fraction or canonical special value.
 */
GMATH_API float gmath_frexpf(float x, int * e);
/**
 * @brief Exact binary32 unbiased exponent, including subnormal inputs.
 *
 * Zero returns GMATH_ILOGB0, infinity INT_MAX, and NaN GMATH_ILOGBNAN;
 * each raises invalid (including quiet NaNs). Finite nonzero values add
 * no flags. errno, rounding mode and incoming flags are preserved.
 * @param x The argument.
 * @return The integer exponent or special-value sentinel.
 */
GMATH_API int gmath_ilogbf(float x);

/**
 * @brief The exact remainder x - n*y, with n the quotient truncated to zero.
 *
 * For finite @p x and finite nonzero @p y the result has the sign of @p x
 * (including zero), its magnitude is less than |y|, and no floating-point
 * exception is raised, even for a subnormal result. The rounding mode has no
 * effect. A finite @p x with infinite @p y returns @p x. An infinite @p x or
 * zero @p y gives the library's canonical quiet NaN and raises invalid unless
 * an argument is a quiet NaN. A NaN argument gives that canonical NaN; a
 * signaling NaN in either argument always raises invalid. errno is unchanged.
 *
 * @param x The dividend.
 * @param y The divisor.
 * @return The remainder, with the sign of @p x.
 */
GMATH_API double gmath_fmod(double x, double y);

/**
 * @brief The exact binary32 remainder, with the rules of ::gmath_fmod.
 *
 * The canonical quiet NaN has bits 0x7fc00000. The reduction operates directly
 * on the binary32 significands and exponents using integer arithmetic.
 *
 * @param x The dividend.
 * @param y The divisor.
 * @return The float remainder, with the sign of @p x.
 */
GMATH_API float gmath_fmodf(float x, float y);

/**
 * @brief The smaller of @p x and @p y, with -0 ordered below +0.
 *
 * A single quiet NaN yields the other argument; two quiet NaNs yield the
 * library's canonical NaN. A signaling NaN in either argument raises invalid
 * and yields the canonical NaN, even when the other argument is numeric.
 * Otherwise the selected input is returned exactly, without raising any
 * exception. The rounding mode has no effect and errno is unchanged.
 *
 * @param x The first value.
 * @param y The second value.
 * @return The minimum, or the canonical NaN as described above.
 */
GMATH_API double gmath_fmin(double x, double y);

/**
 * @brief The larger of @p x and @p y, with +0 ordered above -0.
 *
 * NaNs, exceptions, errno and rounding modes follow ::gmath_fmin.
 *
 * @param x The first value.
 * @param y The second value.
 * @return The maximum, or the library's canonical NaN.
 */
GMATH_API double gmath_fmax(double x, double y);

/**
 * @brief The binary32 minimum, following the rules of ::gmath_fmin.
 *
 * Any returned NaN has bits 0x7fc00000. Finite and infinite results are
 * selected directly from the input encodings, without conversion to double.
 *
 * @param x The first value.
 * @param y The second value.
 * @return The minimum, or the canonical float NaN.
 */
GMATH_API float gmath_fminf(float x, float y);

/**
 * @brief The binary32 maximum, following the rules of ::gmath_fmax.
 *
 * Any returned NaN has bits 0x7fc00000.
 *
 * @param x The first value.
 * @param y The second value.
 * @return The maximum, or the canonical float NaN.
 */
GMATH_API float gmath_fmaxf(float x, float y);

#ifdef __cplusplus
}
#endif

#endif /* GHOTI_IO_GMATH_BASIC_H */
