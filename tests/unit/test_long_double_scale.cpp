/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff */
#include "../long_double_scale_native.h"
#include "test_helpers.h"
#include <cstdlib>
TEST(LongDoubleScale, LiteralNativeCorpus) {
  const char *root=std::getenv("GMATH_LONG_DOUBLE_SCALE_CORPUS_DIR");
  EXPECT_EQ(ldsc_corpus(root&&*root?root:"tests/corpus",0),0);
}
TEST(LongDoubleScale, ActualExponentExtremes) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);
  for(int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}) {
    ASSERT_EQ(fesetround(mode),0);
    for(int sign:{0,1}) for(long n:{LONG_MIN,LONG_MAX}) {
      ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT),0);errno=173;
      long double r=gmath_scalblnl(sign?-1.0L:1.0L,n);
      long double expected=n<0?(sign?-0.0L:0.0L):(sign?-__builtin_infl():__builtin_infl());
      ldn_raw got=ldn_load(&r),want=ldn_load(&expected);
      EXPECT_EQ(got.hi,want.hi);EXPECT_EQ(got.lo,want.lo);
      EXPECT_EQ(fetestexcept(FE_OVERFLOW|FE_UNDERFLOW|FE_INEXACT),(n<0?FE_UNDERFLOW:FE_OVERFLOW)|FE_INEXACT);
      EXPECT_EQ(errno,173);
    }
    EXPECT_EQ(gmath_ldexpl(1.25L,3),10.0L);
    EXPECT_EQ(gmath_scalbnl(1.25L,3),10.0L);
    EXPECT_EQ(gmath_nextafterl(1.0L,2.0L),gmath_nexttowardl(1.0L,2.0L));
  }
  EXPECT_EQ(fesetenv(&saved),0);
}
int main(int argc,char **argv) {::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
