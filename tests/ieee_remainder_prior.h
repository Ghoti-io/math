/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Optional own-project prior declarations; not a numerical reference oracle.
 */
#ifndef GMATH_IEEE_REMAINDER_PRIOR_H
#define GMATH_IEEE_REMAINDER_PRIOR_H
#ifdef __cplusplus
extern "C" {
#endif
extern double gmath_ieee_prior_remainder(double,double);
extern float gmath_ieee_prior_remainderf(float,float);
extern double gmath_ieee_prior_remquo(double,double,int *);
extern float gmath_ieee_prior_remquof(float,float,int *);
#ifdef __cplusplus
}
#endif
#endif
