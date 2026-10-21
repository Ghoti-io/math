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
 * The version this build reports, and the strings of the result codes.
 */

#include <ghoti.io/math/macros.h>

#include <ghoti.io/math/core.h>
#include <ghoti.io/math/libver.h>

const char * gmath_version_string(void) {
  return GMATH_VERSION_STRING;
}

unsigned gmath_version_number(void) {
  return GMATH_VERSION_NUMBER;
}

const char * gmath_result_string(GMATH_Result result) {
  switch (result) {
  case GMATH_OK:
    return "ok";
  case GMATH_ERR_IO:
    return "input/output error";
  case GMATH_ERR_FORMAT:
    return "not a format handled here";
  case GMATH_ERR_UNSUPPORTED:
    return "feature not supported";
  case GMATH_ERR_LIMIT:
    return "a limit was exceeded";
  case GMATH_ERR_CORRUPT:
    return "corrupt data";
  case GMATH_ERR_OOM:
    return "out of memory";
  case GMATH_ERR_INVALID:
    return "invalid argument";
  case GMATH_ERR_INTERNAL:
    return "internal error";
  case GMATH_RESULT_COUNT:
    break;
  }
  return "unknown result";
}
