/** @file Exact floating exponent references and caller state.
 * Copyright 2026 by Corey Pennycuff
 */
#include "../exponent_value_domain.h"
#include "test_helpers.h"
#include <chrono>
#include <filesystem>
#include <fstream>
TEST(ExponentValue, DoublePinnedAndCallerState) {
  const char * directory = std::getenv("GMATH_EXPONENT_VALUE_CORPUS_DIR");
  EXPECT_EQ(
      expv_probe(directory && *directory ? directory : "tests/corpus", 64, 1),
      0);
}
TEST(ExponentValue, FloatPinnedAndCallerState) {
  const char * directory = std::getenv("GMATH_EXPONENT_VALUE_CORPUS_DIR");
  EXPECT_EQ(
      expv_probe(directory && *directory ? directory : "tests/corpus", 32, 1),
      0);
}
TEST(ExponentValue, ProbeBoundaryRestoration) {
  struct Restore {
    fenv_t environment;
    int error;
    Restore() : error(errno) {
      (void)fegetenv(&environment);
    }
    ~Restore() {
      (void)fesetenv(&environment);
      errno = error;
    }
  } restore;
  auto directory =
      std::filesystem::temp_directory_path() /
      ("gmath-exponent-" +
       std::to_string(
           std::chrono::steady_clock::now().time_since_epoch().count()));
  ASSERT_TRUE(std::filesystem::create_directory(directory));
  struct Cleanup {
    std::filesystem::path directory;
    ~Cleanup() {
      std::filesystem::remove_all(directory);
    }
  } cleanup{directory};
  const char * requested = std::getenv("GMATH_EXPONENT_VALUE_CORPUS_DIR");
  std::string valid = requested && *requested ? requested : "tests/corpus";
  for (const char * name : {"logb", "logbf"}) {
    std::ifstream source(std::filesystem::path(valid) /
                         (std::string(name) + "-special.corpus"));
    ASSERT_TRUE(source.good());
    std::ofstream file(directory / (std::string(name) + "-special.corpus"));
    std::string line;
    // Valid headers and first row execute calls that change mode/flags/errno
    // before the deliberately malformed second row forces cleanup.
    for (unsigned i = 0; i < 5; i++) {
      ASSERT_TRUE(static_cast<bool>(std::getline(source, line)));
      file << line << "\n";
    }
    file << "malformed late row\n";
  }
  for (unsigned width : {64u, 32u}) {
    for (bool malformed : {false, true}) {
      ASSERT_EQ(fesetround(FE_DOWNWARD), 0);
      ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT), 0);
      ASSERT_EQ(feraiseexcept(FE_INVALID | FE_DIVBYZERO), 0);
      int incoming = fetestexcept(FE_ALL_EXCEPT);
      errno = 739;
      int status = expv_probe(
          malformed ? directory.string().c_str() : valid.c_str(), width, 0);
      int error = errno, flags = fetestexcept(FE_ALL_EXCEPT),
          mode = fegetround();
      EXPECT_EQ(status, malformed ? 1 : 0);
      EXPECT_EQ(error, 739);
      EXPECT_EQ(flags, incoming);
      EXPECT_EQ(mode, FE_DOWNWARD);
    }
  }
}
TEST(ExponentValue, FiniteConversionDomain) {
  EXPECT_EQ(expv_integer_bits(0, 64), UINT64_C(0));
  EXPECT_EQ(expv_integer_bits(-1, 64), UINT64_C(0xbff0000000000000));
  EXPECT_EQ(expv_integer_bits(-1074, 64), UINT64_C(0xc090c80000000000));
  EXPECT_EQ(expv_integer_bits(-149, 32), UINT64_C(0xc3150000));
  EXPECT_EQ(expv_domain(64, 1), 0);
  EXPECT_EQ(expv_domain(32, 1), 0);
}
int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
