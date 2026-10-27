/** @file Exact modf pairs and caller-state contracts.
 * Copyright 2026 by Corey Pennycuff
 */
#include "../fraction_split_probe.h"
#include "test_helpers.h"

TEST(FractionSplit, DoublePinnedAndCallerState) {
  const char * directory = std::getenv("GMATH_SPLIT_CORPUS_DIR");
  EXPECT_EQ(
      split_probe(directory && *directory ? directory : "tests/corpus", 64, 1),
      0);
}
TEST(FractionSplit, FloatPinnedAndCallerState) {
  const char * directory = std::getenv("GMATH_SPLIT_CORPUS_DIR");
  EXPECT_EQ(
      split_probe(directory && *directory ? directory : "tests/corpus", 32, 1),
      0);
}
TEST(FractionSplit, AliasedOutputObject) {
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(fesetround(mode), 0);
    double d = -1.75;
    float f = -1.75f;
    EXPECT_EQ(gmath_modf(d, &d), -0.75);
    EXPECT_EQ(d, -1.0);
    EXPECT_EQ(gmath_modff(f, &f), -0.75f);
    EXPECT_EQ(f, -1.0f);
  }
  EXPECT_EQ(fesetenv(&saved), 0);
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
