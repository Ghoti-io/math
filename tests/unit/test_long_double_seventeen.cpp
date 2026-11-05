/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff */
#include <ghoti.io/math/basic.h>
#include <ghoti.io/math/elementary.h>
#include "test_helpers.h"
#include <cfenv>
#include <cerrno>
TEST(LongDoubleSeventeen, ExactIdentities) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);feclearexcept(FE_ALL_EXCEPT);errno=173;
  EXPECT_EQ(gmath_sinl(-0.0L),0.0L);EXPECT_EQ(gmath_copysignl(1.0L,gmath_sinl(-0.0L)),-1.0L);
  EXPECT_EQ(gmath_cosl(0.0L),1.0L);EXPECT_EQ(gmath_tanl(-0.0L),0.0L);
  EXPECT_EQ(gmath_asinl(-0.0L),0.0L);EXPECT_EQ(gmath_acosl(1.0L),0.0L);
  EXPECT_EQ(gmath_atanl(-0.0L),0.0L);EXPECT_EQ(gmath_atan2l(-0.0L,1.0L),0.0L);
  EXPECT_EQ(gmath_sinhl(-0.0L),0.0L);EXPECT_EQ(gmath_coshl(0.0L),1.0L);
  EXPECT_EQ(gmath_tanhl(-0.0L),0.0L);EXPECT_EQ(gmath_asinhl(-0.0L),0.0L);
  EXPECT_EQ(gmath_acoshl(1.0L),0.0L);EXPECT_EQ(gmath_atanhl(-0.0L),0.0L);
  EXPECT_EQ(gmath_erfl(-0.0L),0.0L);EXPECT_EQ(gmath_erfcl(0.0L),1.0L);
  EXPECT_EQ(gmath_tgammal(1.0L),1.0L);EXPECT_EQ(gmath_tgammal(2.0L),1.0L);
  EXPECT_EQ(gmath_lgammal(1.0L),0.0L);EXPECT_EQ(gmath_lgammal(2.0L),0.0L);
  EXPECT_EQ(gmath_erfl(__builtin_infl()),1.0L);EXPECT_EQ(gmath_erfcl(__builtin_infl()),0.0L);
  EXPECT_EQ(gmath_erfcl(-__builtin_infl()),2.0L);EXPECT_EQ(gmath_tanhl(-__builtin_infl()),-1.0L);
  EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT),0);EXPECT_EQ(errno,173);EXPECT_EQ(fesetenv(&saved),0);
}
TEST(LongDoubleSeventeen, DomainPolesAndState) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);ASSERT_EQ(fesetround(FE_DOWNWARD),0);
  feclearexcept(FE_ALL_EXCEPT);errno=173;
  long double invalid[]={gmath_sinl(__builtin_infl()),gmath_cosl(__builtin_infl()),gmath_tanl(__builtin_infl()),
    gmath_asinl(2.0L),gmath_acosl(-2.0L),gmath_acoshl(0.0L),gmath_atanhl(2.0L),gmath_tgammal(-2.0L)};
  for(long double x:invalid)EXPECT_TRUE(x!=x);
  EXPECT_EQ(fetestexcept(FE_INVALID),FE_INVALID);
  EXPECT_EQ(gmath_atanhl(-1.0L),-__builtin_infl());EXPECT_EQ(gmath_tgammal(-0.0L),-__builtin_infl());
  EXPECT_EQ(gmath_lgammal(-2.0L),__builtin_infl());EXPECT_EQ(fetestexcept(FE_DIVBYZERO),FE_DIVBYZERO);
  EXPECT_EQ(errno,173);EXPECT_EQ(fegetround(),FE_DOWNWARD);EXPECT_EQ(fesetenv(&saved),0);
}
int main(int argc,char **argv) {::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
