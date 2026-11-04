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
 * @file namespace.h
 *
 * Maps every public name of this library into its version namespace.
 *
 * Kept in one file rather than beside each declaration: a type rename has to
 * be in effect before any struct tag that uses the name, and an internal
 * header may define such a tag without including the public header that
 * declares the typedef.
 *
 * `make check-symbols` fails if an exported symbol is missing from this list.
 */

#ifndef GHOTI_IO_GMATH_NAMESPACE_H
#define GHOTI_IO_GMATH_NAMESPACE_H

#include <ghoti.io/math/libver.h>
#include <float.h>

/// @cond HIDDEN_SYMBOLS

/* Public types, with their tags. */
#define GMATH_Decimal GHOTIIO_MATH(GMATH_Decimal)
#define GMATH_Result GHOTIIO_MATH(GMATH_Result)

/* Internal functions (src/decimal/decimal_internal.h), for the tests. */
#define gmath_decimal_round_spans GHOTIIO_MATH(gmath_decimal_round_spans)
#define gmath_decimal_shortest_tiered GHOTIIO_MATH(gmath_decimal_shortest_tiered)
#define gmath_decimal_tier GHOTIIO_MATH(gmath_decimal_tier)

/* Public functions. */
#define gmath_fabsl GHOTIIO_MATH(gmath_fabsl)
#define gmath_copysignl GHOTIIO_MATH(gmath_copysignl)
#define gmath_nanl GHOTIIO_MATH(gmath_nanl)
#define gmath_fminl GHOTIIO_MATH(gmath_fminl)
#define gmath_fmaxl GHOTIIO_MATH(gmath_fmaxl)
#define gmath_floorl GHOTIIO_MATH(gmath_floorl)
#define gmath_ceill GHOTIIO_MATH(gmath_ceill)
#define gmath_truncl GHOTIIO_MATH(gmath_truncl)
#define gmath_roundl GHOTIIO_MATH(gmath_roundl)
#define gmath_rintl GHOTIIO_MATH(gmath_rintl)
#define gmath_nearbyintl GHOTIIO_MATH(gmath_nearbyintl)
#define gmath_modfl GHOTIIO_MATH(gmath_modfl)
#if LDBL_MANT_DIG != 106 || LDBL_MAX_EXP != 1024
#define gmath_frexpl GHOTIIO_MATH(gmath_frexpl)
#endif
#define gmath_ilogbl GHOTIIO_MATH(gmath_ilogbl)
#define gmath_logbl GHOTIIO_MATH(gmath_logbl)

#define gmath_powf GHOTIIO_MATH(gmath_powf)
#define gmath_erf GHOTIIO_MATH(gmath_erf)
#define gmath_erff GHOTIIO_MATH(gmath_erff)
#define gmath_erfc GHOTIIO_MATH(gmath_erfc)
#define gmath_erfcf GHOTIIO_MATH(gmath_erfcf)
#define gmath_tgamma GHOTIIO_MATH(gmath_tgamma)
#define gmath_tgammaf GHOTIIO_MATH(gmath_tgammaf)
#define gmath_lgamma GHOTIIO_MATH(gmath_lgamma)
#define gmath_lgammaf GHOTIIO_MATH(gmath_lgammaf)
#define gmath_nan GHOTIIO_MATH(gmath_nan)
#define gmath_nanf GHOTIIO_MATH(gmath_nanf)
#define gmath_nexttoward GHOTIIO_MATH(gmath_nexttoward)
#define gmath_nexttowardf GHOTIIO_MATH(gmath_nexttowardf)
#define gmath_fma GHOTIIO_MATH(gmath_fma)
#define gmath_fmaf GHOTIIO_MATH(gmath_fmaf)

#define gmath_asinh GHOTIIO_MATH(gmath_asinh)
#define gmath_acosh GHOTIIO_MATH(gmath_acosh)
#define gmath_atanh GHOTIIO_MATH(gmath_atanh)
#define gmath_asinhf GHOTIIO_MATH(gmath_asinhf)
#define gmath_acoshf GHOTIIO_MATH(gmath_acoshf)
#define gmath_atanhf GHOTIIO_MATH(gmath_atanhf)

#define gmath_sinh GHOTIIO_MATH(gmath_sinh)
#define gmath_cosh GHOTIIO_MATH(gmath_cosh)
#define gmath_tanh GHOTIIO_MATH(gmath_tanh)
#define gmath_sinhf GHOTIIO_MATH(gmath_sinhf)
#define gmath_coshf GHOTIIO_MATH(gmath_coshf)
#define gmath_tanhf GHOTIIO_MATH(gmath_tanhf)

#define gmath_log1p GHOTIIO_MATH(gmath_log1p)
#define gmath_log1pf GHOTIIO_MATH(gmath_log1pf)
#define gmath_expm1 GHOTIIO_MATH(gmath_expm1)
#define gmath_expm1f GHOTIIO_MATH(gmath_expm1f)

#define gmath_asin GHOTIIO_MATH(gmath_asin)
#define gmath_acos GHOTIIO_MATH(gmath_acos)
#define gmath_asinf GHOTIIO_MATH(gmath_asinf)
#define gmath_acosf GHOTIIO_MATH(gmath_acosf)

#define gmath_atan GHOTIIO_MATH(gmath_atan)
#define gmath_atan2 GHOTIIO_MATH(gmath_atan2)
#define gmath_atanf GHOTIIO_MATH(gmath_atanf)
#define gmath_atan2f GHOTIIO_MATH(gmath_atan2f)
#define gmath_ceil GHOTIIO_MATH(gmath_ceil)
#define gmath_copysign GHOTIIO_MATH(gmath_copysign)
#define gmath_cos GHOTIIO_MATH(gmath_cos)
#define gmath_decimal_parse GHOTIIO_MATH(gmath_decimal_parse)
#define gmath_decimal_shortest GHOTIIO_MATH(gmath_decimal_shortest)
#define gmath_decimal_to_double GHOTIIO_MATH(gmath_decimal_to_double)
#define gmath_exp GHOTIIO_MATH(gmath_exp)
#define gmath_expf GHOTIIO_MATH(gmath_expf)
#define gmath_sinf GHOTIIO_MATH(gmath_sinf)
#define gmath_cosf GHOTIIO_MATH(gmath_cosf)
#define gmath_tanf GHOTIIO_MATH(gmath_tanf)
#define gmath_floorf GHOTIIO_MATH(gmath_floorf)
#define gmath_ceilf GHOTIIO_MATH(gmath_ceilf)
#define gmath_truncf GHOTIIO_MATH(gmath_truncf)
#define gmath_roundf GHOTIIO_MATH(gmath_roundf)
#define gmath_rintf GHOTIIO_MATH(gmath_rintf)
#define gmath_fabsf GHOTIIO_MATH(gmath_fabsf)
#define gmath_copysignf GHOTIIO_MATH(gmath_copysignf)
#define gmath_sqrtf GHOTIIO_MATH(gmath_sqrtf)
#define gmath_cbrt GHOTIIO_MATH(gmath_cbrt)
#define gmath_cbrtf GHOTIIO_MATH(gmath_cbrtf)
#define gmath_exp2 GHOTIIO_MATH(gmath_exp2)
#define gmath_exp2f GHOTIIO_MATH(gmath_exp2f)
#define gmath_fabs GHOTIIO_MATH(gmath_fabs)
#define gmath_floor GHOTIIO_MATH(gmath_floor)
#define gmath_fdim GHOTIIO_MATH(gmath_fdim)
#define gmath_fdimf GHOTIIO_MATH(gmath_fdimf)
#define gmath_fmax GHOTIIO_MATH(gmath_fmax)
#define gmath_fmaxf GHOTIIO_MATH(gmath_fmaxf)
#define gmath_fmin GHOTIIO_MATH(gmath_fmin)
#define gmath_fminf GHOTIIO_MATH(gmath_fminf)
#define gmath_modf GHOTIIO_MATH(gmath_modf)
#define gmath_modff GHOTIIO_MATH(gmath_modff)
#define gmath_remainder GHOTIIO_MATH(gmath_remainder)
#define gmath_remainderf GHOTIIO_MATH(gmath_remainderf)
#define gmath_remquo GHOTIIO_MATH(gmath_remquo)
#define gmath_remquof GHOTIIO_MATH(gmath_remquof)
#define gmath_fmod GHOTIIO_MATH(gmath_fmod)
#define gmath_fmodf GHOTIIO_MATH(gmath_fmodf)
#define gmath_frexp GHOTIIO_MATH(gmath_frexp)
#define gmath_hypot GHOTIIO_MATH(gmath_hypot)
#define gmath_hypotf GHOTIIO_MATH(gmath_hypotf)
#define gmath_logb GHOTIIO_MATH(gmath_logb)
#define gmath_logbf GHOTIIO_MATH(gmath_logbf)
#define gmath_ilogb GHOTIIO_MATH(gmath_ilogb)
#define gmath_ldexp GHOTIIO_MATH(gmath_ldexp)
#define gmath_log GHOTIIO_MATH(gmath_log)
#define gmath_logf GHOTIIO_MATH(gmath_logf)
#define gmath_log10 GHOTIIO_MATH(gmath_log10)
#define gmath_log10f GHOTIIO_MATH(gmath_log10f)
#define gmath_log2 GHOTIIO_MATH(gmath_log2)
#define gmath_log2f GHOTIIO_MATH(gmath_log2f)
#define gmath_pow GHOTIIO_MATH(gmath_pow)
#define gmath_result_string GHOTIIO_MATH(gmath_result_string)
#define gmath_rint GHOTIIO_MATH(gmath_rint)
#define gmath_lrint GHOTIIO_MATH(gmath_lrint)
#define gmath_lrintf GHOTIIO_MATH(gmath_lrintf)
#define gmath_llrint GHOTIIO_MATH(gmath_llrint)
#define gmath_llrintf GHOTIIO_MATH(gmath_llrintf)
#define gmath_nearbyint GHOTIIO_MATH(gmath_nearbyint)
#define gmath_nearbyintf GHOTIIO_MATH(gmath_nearbyintf)
#define gmath_lround GHOTIIO_MATH(gmath_lround)
#define gmath_lroundf GHOTIIO_MATH(gmath_lroundf)
#define gmath_llround GHOTIIO_MATH(gmath_llround)
#define gmath_llroundf GHOTIIO_MATH(gmath_llroundf)
#define gmath_round GHOTIIO_MATH(gmath_round)
#define gmath_nextafter GHOTIIO_MATH(gmath_nextafter)
#define gmath_nextafterf GHOTIIO_MATH(gmath_nextafterf)
#define gmath_scalbnf GHOTIIO_MATH(gmath_scalbnf)
#define gmath_ldexpf GHOTIIO_MATH(gmath_ldexpf)
#define gmath_frexpf GHOTIIO_MATH(gmath_frexpf)
#define gmath_ilogbf GHOTIIO_MATH(gmath_ilogbf)
#define gmath_scalbln GHOTIIO_MATH(gmath_scalbln)
#define gmath_scalblnf GHOTIIO_MATH(gmath_scalblnf)
#define gmath_scalbn GHOTIIO_MATH(gmath_scalbn)
#define gmath_sin GHOTIIO_MATH(gmath_sin)
#define gmath_sqrt GHOTIIO_MATH(gmath_sqrt)
#define gmath_sqrt_hardware GHOTIIO_MATH(gmath_sqrt_hardware)
#define gmath_sqrt_has_hardware GHOTIIO_MATH(gmath_sqrt_has_hardware)
#define gmath_sqrt_portable GHOTIIO_MATH(gmath_sqrt_portable)
#define gmath_tan GHOTIIO_MATH(gmath_tan)
#define gmath_trunc GHOTIIO_MATH(gmath_trunc)
#define gmath_version_number GHOTIIO_MATH(gmath_version_number)
#define gmath_version_string GHOTIIO_MATH(gmath_version_string)

/// @endcond

#endif // GHOTI_IO_GMATH_NAMESPACE_H
