/** @file Exact mode-aware nearby-integer rounding.
 * Copyright 2026 by Corey Pennycuff
 */
#include "../nearby_probe.h"
#include "test_helpers.h"
TEST(Nearby, PinnedDouble) {
  const char * p = std::getenv("GMATH_NEARBY_CORPUS_DIR");
  EXPECT_EQ(nb_probe(p && *p ? p : "tests/corpus", 64, 1), 0);
}
TEST(Nearby, PinnedFloat) {
  const char * p = std::getenv("GMATH_NEARBY_CORPUS_DIR");
  EXPECT_EQ(nb_probe(p && *p ? p : "tests/corpus", 32, 1), 0);
}
TEST(Nearby, LiteralTiesDirectionsAndIncomingFlags) {
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  int error = errno;
  const uint64_t out[] = {UINT64_C(0xc000000000000000),
      UINT64_C(0xc000000000000000), UINT64_C(0xbff0000000000000),
      UINT64_C(0xbff0000000000000)};
  const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  uint64_t hash = GMATH_FNV_BASIS;
  for (unsigned i = 0; i < 4; i++)
    for (int subset = 0; subset < 32; subset++)
      EXPECT_EQ(nb_call(UINT64_C(0xbff8000000000000), out[i], 0, 64, modes[i],
                    subset, 733, &hash),
          0);
  EXPECT_EQ(fesetenv(&saved), 0);
  errno = error;
}
int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
TEST(Nearby, NativeSseQueryUnderManualDesynchronization) {
#if (defined(__GNUC__) || defined(__clang__)) && defined(__SSE__) &&           \
    (defined(__i386__) || defined(__x86_64__)) &&                              \
    !defined(GMATH_NEARBY_FENV_QUERY)
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  int error = errno;
  EXPECT_EQ(fesetround(FE_DOWNWARD), 0);
  uint32_t original;
  __asm__ volatile("stmxcsr %0" : "=m"(original)::"memory");
  uint32_t upward = (original & ~UINT32_C(0x6000)) | UINT32_C(0x4000);
  __asm__ volatile("ldmxcsr %0" ::"m"(upward) : "memory");
  double (*volatile d)(double) = gmath_nearbyint;
  float (*volatile f)(float) = gmath_nearbyintf;
  EXPECT_EQ(d(0.25), 1.0);
  EXPECT_EQ(f(0.25f), 1.0f);
  uint32_t after;
  __asm__ volatile("stmxcsr %0" : "=m"(after)::"memory");
  EXPECT_EQ(after, upward);
  EXPECT_EQ(fegetround(), FE_DOWNWARD);
  EXPECT_EQ(fesetenv(&saved), 0);
  errno = error;
#else
  GTEST_SKIP() << "native SSE-control policy is not this configuration";
#endif
}
