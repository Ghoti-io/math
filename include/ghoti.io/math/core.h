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
 * @file core.h
 *
 * The version this build reports, and the result code of the functions that
 * can fail (decimal.h; the functions of basic.h and elementary.h cannot).
 */

#ifndef GHOTI_IO_GMATH_CORE_H
#define GHOTI_IO_GMATH_CORE_H

#include <ghoti.io/math/macros.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief The result of a function that can fail.
 *
 * The suite's shared vocabulary (CONVENTIONS section 5), so that a caller
 * translating results between libraries meets the same names everywhere.
 */
typedef enum {
  GMATH_OK = 0,          ///< The operation succeeded.
  GMATH_ERR_IO,          ///< Not returned by this library.
  GMATH_ERR_FORMAT,      ///< The text is not a number in the grammar asked for.
  GMATH_ERR_UNSUPPORTED, ///< Not returned by this library.
  GMATH_ERR_LIMIT,       ///< Not returned by this library.
  GMATH_ERR_CORRUPT,     ///< Not returned by this library.
  GMATH_ERR_OOM,         ///< Not returned by this library: nothing allocates.
  GMATH_ERR_INVALID,     ///< A caller-supplied argument is wrong.
  GMATH_ERR_INTERNAL,    ///< The library's own invariant failed.
  GMATH_RESULT_COUNT
} GMATH_Result;

/**
 * @brief Static description of a result code.
 *
 * The string is never NULL, never allocated, and never contains caller data.
 *
 * @param result The result code, including values outside the enum.
 * @return A static string.
 */
GMATH_API const char * gmath_result_string(GMATH_Result result);

/**
 * @brief This build's version, as the string the Makefile generated.
 *
 * @return A static string, never NULL.  "0.0.0", or "0.0.0-dev" when BRANCH
 *   was overridden.
 */
GMATH_API const char * gmath_version_string(void);

/**
 * @brief This build's version, packed as ::GMATH_MAKE_VERSION packs it.
 *
 * @return `(major << 16) | (minor << 8) | patch`.
 */
GMATH_API unsigned gmath_version_number(void);

#ifdef __cplusplus
}
#endif

#endif /* GHOTI_IO_GMATH_CORE_H */
