/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff */
#include "../long_double_native.h"
#include "test_helpers.h"
#include <cstdlib>
TEST(LongDouble, NativeFormatCorpus) {
  const char *root=std::getenv("GMATH_LONG_DOUBLE_CORPUS_DIR");
  EXPECT_EQ(ldn_corpus(root && *root ? root : "tests/corpus",0),0);
}
TEST(LongDouble, ExactBeyondDoubleAndPointerRules) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);
  for(int mode : {FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}) {
    ASSERT_EQ(fesetround(mode),0);
    long double x=-1.75L;
    EXPECT_EQ(gmath_modfl(x,&x),-0.75L);EXPECT_EQ(x,-1.0L);
    EXPECT_EQ(gmath_modfl(-1.75L,nullptr),-0.75L);
#if GMATH_HAVE_FREXPL
    EXPECT_EQ(gmath_frexpl(1.75L,nullptr),0.875L);
#endif
#if LDBL_MANT_DIG > 53
    long double a=0x1.000000000000001p0L;
    EXPECT_EQ(gmath_fabsl(-a),a);
    EXPECT_EQ(gmath_fmaxl(a,1.0L),a);
    EXPECT_EQ(gmath_floorl(a),1.0L);EXPECT_EQ(gmath_ceill(a),2.0L);
#if GMATH_HAVE_FREXPL
    int e=0;EXPECT_EQ(gmath_frexpl(a,&e),0x1.000000000000001p-1L);EXPECT_EQ(e,1);
#endif
#endif
  }
  EXPECT_EQ(fesetenv(&saved),0);
}
TEST(LongDouble, FixedRoundingPolicies) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);
  for(int mode : {FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}) {
    ASSERT_EQ(fesetround(mode),0);ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT),0);
    EXPECT_EQ(gmath_floorl(1.75L),1.0L);EXPECT_EQ(gmath_floorl(-1.75L),-2.0L);
    EXPECT_EQ(gmath_ceill(1.75L),2.0L);EXPECT_EQ(gmath_ceill(-1.75L),-1.0L);
    EXPECT_EQ(gmath_truncl(1.75L),1.0L);EXPECT_EQ(gmath_truncl(-1.75L),-1.0L);
    EXPECT_EQ(gmath_roundl(2.5L),3.0L);EXPECT_EQ(gmath_roundl(-2.5L),-3.0L);
    EXPECT_EQ(gmath_rintl(2.5L),2.0L);EXPECT_EQ(gmath_rintl(3.5L),4.0L);
    EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT),0);
  }
  EXPECT_EQ(fesetenv(&saved),0);
}
int main(int argc,char **argv) { ::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS(); }
