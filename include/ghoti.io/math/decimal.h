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
 * @file decimal.h
 *
 * Exact conversion between decimal numbers and `double`: a decimal is rounded
 * to the nearest `double`, ties to even, and a `double` is written as the
 * shortest decimal that rounds back to it.  The two are inverses: for every
 * finite `x`, ::gmath_decimal_to_double of ::gmath_decimal_shortest's digits is
 * `x` again, bit for bit.
 *
 * Both are integer arithmetic throughout, so the result is the same on every
 * target, in every rounding mode, and for every input length: a decimal of any
 * number of digits is rounded correctly, not only one of 17 or 20.  Nothing
 * reads the locale, nothing allocates, and nothing raises a floating-point
 * exception; what IEEE 754 would signal (inexact, overflow, underflow) is
 * returned as flags instead.  The algorithms are in documentation/design.md,
 * "Decimal conversion".
 */

#ifndef GHOTI_IO_GMATH_DECIMAL_H
#define GHOTI_IO_GMATH_DECIMAL_H

#include <ghoti.io/math/macros.h>

#include <ghoti.io/math/core.h>

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** The result differs from the decimal's exact value. */
#define GMATH_DECIMAL_INEXACT 1u
/** The decimal's magnitude rounded to infinity. */
#define GMATH_DECIMAL_OVERFLOW 2u
/**
 * The decimal's exact magnitude is nonzero and below 2^-1022, the smallest
 * normal `double` (tininess before rounding), and the result is inexact.
 */
#define GMATH_DECIMAL_UNDERFLOW 4u

/**
 * @brief Round `(-1)^negative * digits * 10^exponent` to the nearest `double`,
 * ties to even.
 *
 * @p digits is @p length ASCII decimal digits, most significant first, with no
 * sign, point or exponent; leading and trailing zeros are allowed, and so is any
 * length.  A magnitude beyond the largest `double` by half a unit in the last
 * place or more is infinity; one at most half the smallest subnormal is zero
 * (half exactly is the tie, which rounds to the even zero).  A zero, of any
 * spelling, keeps the sign @p negative gives it.
 *
 * @param negative Whether the value is negative.
 * @param digits   The digits; not NUL-terminated.  May be NULL only when
 *                 @p length is 0, which is refused.
 * @param length   The number of digits, at least 1.
 * @param exponent The power of ten the digits are multiplied by.
 * @param out      Receives the result, only on success.
 * @param flags    If not NULL, receives a set of `GMATH_DECIMAL_` flags, only
 *                 on success.
 * @return ::GMATH_OK; ::GMATH_ERR_INVALID for a NULL @p out, a zero @p length,
 *         a NULL @p digits or a character that is not a digit (nothing is
 *         written).
 */
GMATH_API GMATH_Result gmath_decimal_to_double(bool negative, const char * digits,
                                               size_t length, int64_t exponent,
                                               double * out, unsigned * flags);

/**
 * @brief Read the longest decimal number at the start of @p text and round it
 * to the nearest `double`, ties to even.
 *
 * The grammar is the one CSS, SVG and C's `strtod` share for decimal numbers:
 *
 *     [+-]? ( digit+ ( "." digit* )? | "." digit+ ) ( [eE] [+-]? digit+ )?
 *
 * The exponent part is taken only when it is complete, so "1e", "1e+" and "1ex"
 * read as 1 and stop before the "e".  Nothing else is accepted: no leading
 * space, no hexadecimal, no `inf` or `nan`, no digit separators.  A format
 * stricter than this one (JSON forbids "+1", ".5" and "01") checks its own
 * rules before or after calling.  The exponent may have any number of digits;
 * an exponent too large to matter gives infinity or zero, as the value says.
 * The value is rounded exactly as ::gmath_decimal_to_double rounds it.
 *
 * @param text     The text; not NUL-terminated.  May be NULL only when
 *                 @p length is 0.
 * @param length   The bytes available, at most 2^62.
 * @param out      Receives the result, only on success.
 * @param consumed If not NULL, receives the number of bytes read, only on
 *                 success.
 * @param flags    If not NULL, receives a set of `GMATH_DECIMAL_` flags, only
 *                 on success.
 * @return ::GMATH_OK; ::GMATH_ERR_FORMAT when the text does not start with a
 *         number; ::GMATH_ERR_INVALID for a NULL @p out or a NULL @p text with
 *         a nonzero @p length.  Nothing is written on failure.
 */
GMATH_API GMATH_Result gmath_decimal_parse(const char * text, size_t length,
                                           double * out, size_t * consumed,
                                           unsigned * flags);

/** The most significant digits a shortest spelling of a `double` can need. */
#define GMATH_DECIMAL_MAX_DIGITS 17

/**
 * A finite `double` as a decimal: `(-1)^negative * digits * 10^exponent`.
 */
typedef struct GMATH_Decimal {
  bool negative; ///< The sign bit of the `double`, so -0 is negative.
  /**
   * @brief The digits, most significant first, NUL-terminated.
   *
   * No leading zero and no trailing zero, except that zero is the one digit
   * "0" with an exponent of 0.
   */
  char digits[GMATH_DECIMAL_MAX_DIGITS + 1];
  size_t length;   ///< The number of digits, from 1 to ::GMATH_DECIMAL_MAX_DIGITS.
  int exponent;    ///< The power of ten the digits are multiplied by.
} GMATH_Decimal;

/**
 * @brief The shortest decimal that rounds to @p x.
 *
 * Of all decimals that ::gmath_decimal_to_double rounds to @p x, this is one
 * with the fewest significant digits; of those, the one closest to @p x; and of
 * two equally close, the one whose last digit is even.  The interval of
 * decimals that round to @p x includes its ends when @p x's significand is even
 * (ties go to it) and excludes them when it is odd, and the interval below a
 * power of two is half the width of the one above it.
 *
 * How the decimal is spelled (`1e23`, `1.0E+23`, `100000000000000000000000`)
 * is the caller's; this gives the digits and the exponent.
 *
 * @param x   A finite `double`.
 * @param out Receives the decimal, only on success.
 * @return ::GMATH_OK; ::GMATH_ERR_INVALID for a NULL @p out, an infinity or a
 *         NaN (how a format spells those is its own).
 */
GMATH_API GMATH_Result gmath_decimal_shortest(double x, GMATH_Decimal * out);

#ifdef __cplusplus
}
#endif

#endif /* GHOTI_IO_GMATH_DECIMAL_H */
