/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff */
#include "../long_double_nine_native.h"
#include "test_helpers.h"
#include <cstdlib>
TEST(LongDoubleNine, LiteralNativeCorpus) {
  const char *root=std::getenv("GMATH_LONG_DOUBLE_NINE_CORPUS_DIR");
  EXPECT_EQ(ld9_corpus(root&&*root?root:"tests/corpus",0),0);
}
TEST(LongDoubleNine, FusedIntermediateRange) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);
  EXPECT_EQ(fesetround(FE_TONEAREST),0);EXPECT_EQ(feclearexcept(FE_ALL_EXCEPT),0);
  volatile long double largest=LDBL_MAX;
  long double result=gmath_fmal(largest,2.0L,-largest);
  EXPECT_EQ(result,largest);EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT),0);
  EXPECT_EQ(fesetenv(&saved),0);
}
int main(int argc,char **argv) {::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
