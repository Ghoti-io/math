/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff */
#include <ghoti.io/math/basic.h>
#include <ghoti.io/math/elementary.h>
#include "test_helpers.h"
#include <cfenv>
#include <cerrno>
TEST(LongDoubleEleven, ExactRootsAndPowers) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);feclearexcept(FE_ALL_EXCEPT);
  EXPECT_EQ(gmath_sqrtl(4.0L),2.0L);EXPECT_EQ(gmath_cbrtl(-8.0L),-2.0L);
  EXPECT_EQ(gmath_hypotl(3.0L,4.0L),5.0L);EXPECT_EQ(gmath_powl(9.0L,0.5L),3.0L);
  EXPECT_EQ(gmath_exp2l(-10.0L),0x1p-10L);EXPECT_EQ(gmath_log2l(0x1p-10L),-10.0L);
  EXPECT_EQ(gmath_log10l(100.0L),2.0L);
  EXPECT_EQ(gmath_powl(__builtin_infl(),-2.0L),0.0L);
  EXPECT_EQ(gmath_copysignl(1.0L,gmath_powl(-__builtin_infl(),-3.0L)),-1.0L);
  EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT),0);
  EXPECT_EQ(fesetenv(&saved),0);
}
TEST(LongDoubleEleven, DomainAndState) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);feclearexcept(FE_ALL_EXCEPT);
  ASSERT_EQ(fesetround(FE_DOWNWARD),0);errno=173;
  long double result=gmath_powl(-1.0L,0.5L);
  EXPECT_TRUE(result!=result);EXPECT_EQ(fetestexcept(FE_INVALID),FE_INVALID);
  EXPECT_EQ(errno,173);EXPECT_EQ(fegetround(),FE_DOWNWARD);
  EXPECT_EQ(fesetenv(&saved),0);
}
int main(int argc,char **argv) {::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
