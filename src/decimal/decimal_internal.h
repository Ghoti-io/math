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
 * The tiers of the decimal conversions, for the tests.  Each public function in
 * decimal.h is one of these with every tier allowed; a test forces the general
 * tier and requires the same bits (AD-13), and reads which tier ran to show the
 * fast one is taken.
 */

#ifndef GHOTI_IO_GMATH_SRC_DECIMAL_DECIMAL_INTERNAL_H
#define GHOTI_IO_GMATH_SRC_DECIMAL_DECIMAL_INTERNAL_H

#include <ghoti.io/math/macros.h>

#include <ghoti.io/math/decimal.h>

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Which way a decimal was rounded to a double. */
typedef enum {
  GMATH_DECIMAL_TIER_SPECIAL = 0,   ///< Zero, or a magnitude decided by its exponent alone.
  GMATH_DECIMAL_TIER_SHIFT = 1,     ///< A division by a power of two (1 for parse): shifting.
  GMATH_DECIMAL_TIER_DIV32 = 2,     ///< A divisor of one 32-bit limb: short division.
  GMATH_DECIMAL_TIER_RESTORING = 3, ///< The general tier: restoring long division.
  GMATH_DECIMAL_TIER_INTEGER = 4,   ///< Shortest only: an integer below 2^53, written directly.
  GMATH_DECIMAL_TIER_GENERAL = 5    ///< Shortest only: the search, by restoring division.
} gmath_decimal_tier;

/**
 * Round `(-1)^negative * (a b) * 10^exponent` to the nearest double, where
 * `a b` is the digits of @p a followed by those of @p b and @p exponent is the
 * power of ten of the last digit.  Every character must be a digit (checked).
 * @p force_general uses restoring division for every division.
 */
GMATH_INTERNAL_API GMATH_Result gmath_decimal_round_spans(
    bool negative, const char * a, size_t a_length, const char * b, size_t b_length,
    int64_t exponent, bool force_general, double * out, unsigned * flags,
    gmath_decimal_tier * tier);

/** ::gmath_decimal_shortest, optionally without the integer tier. */
GMATH_INTERNAL_API GMATH_Result gmath_decimal_shortest_tiered(
    double x, bool force_general, GMATH_Decimal * out, gmath_decimal_tier * tier);

#ifdef __cplusplus
}
#endif

#endif /* GHOTI_IO_GMATH_SRC_DECIMAL_DECIMAL_INTERNAL_H */
