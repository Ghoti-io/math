/** @file Native-long exponent scaling references and caller state.
 * Copyright 2026 by Corey Pennycuff
 */
#include "../long_scale_probe.h"
#include "test_helpers.h"
#include <chrono>
#include <filesystem>
#include <fstream>
TEST(LongScale, DoublePinnedAndCallerState) {
  const char * directory = std::getenv("GMATH_LONG_SCALE_CORPUS_DIR");
  EXPECT_EQ(
      ls_probe(directory && *directory ? directory : "tests/corpus", 64, 1), 0);
}
TEST(LongScale, FloatPinnedAndCallerState) {
  const char * directory = std::getenv("GMATH_LONG_SCALE_CORPUS_DIR");
  EXPECT_EQ(
      ls_probe(directory && *directory ? directory : "tests/corpus", 32, 1), 0);
}
TEST(LongScale, RoundingBoundaryAndNativeExtremes) {
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  int error = errno;
  struct Restore {
    fenv_t environment;
    int error;
    ~Restore() {
      (void)fesetenv(&environment);
      errno = error;
    }
  } restore{saved, error};
  int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  uint64_t hash = GMATH_FNV_BASIS;
  for (int mode : modes) {
    EXPECT_EQ(ls_call(UINT64_C(0x001fffffffffffff), -1,
                      UINT64_C(0x0010000000000000), 24, 64, mode, FE_INVALID,
                      733, &hash),
              0);
    EXPECT_EQ(ls_call(UINT64_C(0x00ffffff), -1, UINT64_C(0x00800000), 16, 32,
                      mode, FE_INVALID, 733, &hash),
              0);
    for (unsigned width : {64u, 32u}) {
      uint64_t one =
          width == 64 ? UINT64_C(0x3ff0000000000000) : UINT64_C(0x3f800000);
      uint64_t inf =
          width == 64 ? UINT64_C(0x7ff0000000000000) : UINT64_C(0x7f800000);
      EXPECT_EQ(ls_call(one, LONG_MAX, inf, 20, width, mode, 0, 0, &hash), 0);
      EXPECT_EQ(ls_call(one, LONG_MIN, 0, 24, width, mode, 0, 0, &hash), 0);
    }
  }
}
TEST(LongScale, SignedWordsAndNativeEligibility) {
  EXPECT_EQ(ls_signed(UINT64_C(0x8000000000000000)), INT64_MIN);
  EXPECT_EQ(ls_signed(UINT64_C(0x7fffffffffffffff)), INT64_MAX);
  EXPECT_EQ(ls_signed(UINT64_MAX), -1);
  EXPECT_TRUE(ls_eligible(LONG_MIN));
  EXPECT_TRUE(ls_eligible(LONG_MAX));
  EXPECT_EQ(ls_eligible(INT64_C(4294967296)), sizeof(long) == 8);
  EXPECT_EQ(ls_eligible(-INT64_C(4294967296)), sizeof(long) == 8);
}
TEST(LongScale, RestoresEnvironmentAfterLateMalformedRow) {
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  int error = errno;
  struct Restore {
    fenv_t environment;
    int error;
    ~Restore() {
      (void)fesetenv(&environment);
      errno = error;
    }
  } restore{saved, error};
  auto path =
      std::filesystem::temp_directory_path() /
      ("gmath-long-scale-" +
       std::to_string(
           std::chrono::steady_clock::now().time_since_epoch().count()));
  ASSERT_TRUE(std::filesystem::create_directory(path));
  struct Cleanup {
    std::filesystem::path path;
    ~Cleanup() {
      std::filesystem::remove_all(path);
    }
  } cleanup{path};
  const char * requested = std::getenv("GMATH_LONG_SCALE_CORPUS_DIR");
  std::string valid = requested && *requested ? requested : "tests/corpus";
  for (unsigned width : {64u, 32u}) {
    const char * name = width == 64 ? "scalbln" : "scalblnf";
    std::ofstream file(path / (std::string(name) + "-special.corpus"));
    file << "# Pinned oracle: long_scale MPFR 4.2.2 gmpy2 2.3.2\n# function "
         << name
         << "\n# seed 0 count 0 fresh True entries 2\n# raw x signed64 n "
            "result normalized-flags\n";
    file << (width == 64
                 ? "3ff0000000000000 0000000000000000 3ff0000000000000 0\n"
                 : "3f800000 0000000000000000 3f800000 0\n");
    file << "malformed late row\n";
    file.close();
    for (bool malformed : {false, true}) {
      ASSERT_EQ(fesetround(FE_DOWNWARD), 0);
      ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT), 0);
      ASSERT_EQ(feraiseexcept(FE_INVALID | FE_DIVBYZERO), 0);
      int incoming = fetestexcept(FE_ALL_EXCEPT);
      errno = 739;
      int status =
          ls_probe(malformed ? path.string().c_str() : valid.c_str(), width, 0);
      int got_errno = errno, flags = fetestexcept(FE_ALL_EXCEPT),
          mode = fegetround();
      EXPECT_EQ(status, malformed ? 1 : 0);
      EXPECT_EQ(got_errno, 739);
      EXPECT_EQ(flags, incoming);
      EXPECT_EQ(mode, FE_DOWNWARD);
    }
  }
}
int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
