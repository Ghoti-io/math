/**
 * @file
 * Real cube roots against independent pinned MPFR600/mpmath640 references.
 * GMATH_CBRT_CORPUS_DIR selects an alternate required corpus directory.
 * Accuracy requires FE_TONEAREST; tests restore the incoming environment.
 * Copyright 2026 by Corey Pennycuff
 */
#include "test_helpers.h"

#include <ghoti.io/math/elementary.h>

#include <cerrno>
#include <cfenv>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <limits>
#include <sstream>
#include <string>
#include <unordered_set>
#include <vector>

namespace {

constexpr uint64_t kSign = 0x8000000000000000ull;
constexpr uint64_t kInf = 0x7ff0000000000000ull;
constexpr uint64_t kQuiet = 0x0008000000000000ull;
constexpr uint64_t kNaN = kInf | kQuiet;

double Value(uint64_t word) {
  double x;
  std::memcpy(&x, &word, sizeof x);
  return x;
}
uint64_t Bits(double x) {
  uint64_t word;
  std::memcpy(&word, &x, sizeof word);
  return word;
}
float ErrorValue(uint32_t word) {
  float x;
  std::memcpy(&x, &word, sizeof x);
  return x;
}
uint32_t ErrorBits(float x) {
  uint32_t word;
  std::memcpy(&word, &x, sizeof word);
  return word;
}

struct Environment {
  fenv_t saved;
  int saved_errno;
  Environment() : saved_errno(errno) {
    std::fegetenv(&saved);
  }
  ~Environment() {
    std::fesetenv(&saved);
    errno = saved_errno;
  }
};

struct Policy {
  int required, allowed;
};

Policy ExpectedPolicy(uint64_t word) {
  uint64_t magnitude = word & ~kSign;
  if (magnitude > kInf) {
    int flags = (magnitude & kQuiet) == 0 ? FE_INVALID : 0;
    return {flags, flags};
  }
  if (magnitude == 0 || magnitude == kInf) {
    return {0, 0};
  }
  // This exact host decomposition independently identifies all binary cubes,
  // including subnormal inputs, before the floating environment is cleared.
  int exponent;
  double fraction = std::frexp(Value(magnitude), &exponent);
  if (fraction == 0.5 && (exponent - 1) % 3 == 0) {
    return {0, 0};
  }
  return {0, FE_INEXACT};
}

double CheckCall(
    uint64_t word, int incoming_flags = 0, int expected_mode = FE_TONEAREST) {
  Policy policy = ExpectedPolicy(word);
  std::feclearexcept(FE_ALL_EXCEPT);
  if (incoming_flags != 0) {
    EXPECT_EQ(std::feraiseexcept(incoming_flags), 0);
  }
  int existing = std::fetestexcept(FE_ALL_EXCEPT);
  errno = E2BIG;
  double result = gmath_cbrt(Value(word));
  int result_errno = errno;
  int result_mode = std::fegetround();
  int result_flags = std::fetestexcept(FE_ALL_EXCEPT);
  EXPECT_EQ(result_errno, E2BIG) << std::hex << word;
  EXPECT_EQ(result_mode, expected_mode);
  EXPECT_EQ(
      result_flags & (policy.required | existing), policy.required | existing)
      << std::hex << word;
  EXPECT_EQ(result_flags & ~(policy.allowed | existing), 0) << std::hex << word;
  uint64_t a = word & ~kSign;
  if (a != 0 && a < kInf) {
    EXPECT_TRUE(std::isnormal(result)) << std::hex << word;
  }
  return result;
}

struct Entry {
  uint64_t x, result;
  uint32_t error;
};

bool PositiveInteger(const std::string & text, size_t * output) {
  size_t value = 0;
  auto parsed = std::from_chars(text.data(), text.data() + text.size(), value);
  if (parsed.ec != std::errc{} || parsed.ptr != text.data() + text.size() ||
      value == 0) {
    return false;
  }
  *output = value;
  return true;
}

std::vector<Entry> Load() {
  const char * env = std::getenv("GMATH_CBRT_CORPUS_DIR");
  std::string directory = env && *env ? env : "tests/corpus";
  std::ifstream input(directory + "/cbrt.corpus");
  EXPECT_TRUE(input.is_open()) << "missing cbrt corpus";
  std::vector<Entry> entries;
  std::unordered_set<uint64_t> inputs;
  bool have_count = false;
  size_t declared_entries = 0;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty()) {
      continue;
    }
    if (line[0] == '#') {
      std::istringstream header(line.substr(1));
      std::string token;
      while (header >> token) {
        if (token == "entries") {
          EXPECT_FALSE(have_count) << "duplicate cbrt entries header";
          have_count = true;
          std::string count;
          if (!(header >> count) ||
              !PositiveInteger(count, &declared_entries)) {
            ADD_FAILURE() << "invalid cbrt entries header: " << line;
          }
        }
      }
      continue;
    }
    Entry entry{};
    std::string extra;
    std::istringstream parser(line);
    if (!(parser >> std::hex >> entry.x >> entry.result >> entry.error) ||
        (parser >> extra)) {
      ADD_FAILURE() << "bad cbrt corpus row: " << line;
      continue;
    }
    if (!inputs.insert(entry.x).second) {
      ADD_FAILURE() << "duplicate cbrt input word: " << std::hex << entry.x;
    }
    entries.push_back(entry);
  }
  EXPECT_TRUE(have_count) << "missing required cbrt entries header";
  EXPECT_EQ(entries.size(), declared_entries)
      << "cbrt corpus count disagrees with header";
  const char * minimum = std::getenv("GMATH_CBRT_MIN_ENTRIES");
  size_t required = 1000;
  if (minimum != nullptr && !PositiveInteger(minimum, &required)) {
    ADD_FAILURE()
        << "GMATH_CBRT_MIN_ENTRIES must be a complete positive decimal integer";
  }
  EXPECT_GE(entries.size(), required) << "missing or truncated cbrt corpus";
  return entries;
}

double UlpError(double got, const Entry & entry) {
  double reference = Value(entry.result);
  if (std::isnan(reference)) {
    return Bits(got) == kNaN ? 0.0 : std::numeric_limits<double>::infinity();
  }
  if (reference == 0 || std::isinf(reference)) {
    return Bits(got) == entry.result ? 0.0
                                     : std::numeric_limits<double>::infinity();
  }
  if (!std::isfinite(got)) {
    return std::numeric_limits<double>::infinity();
  }
  double signed_error = ErrorValue(entry.error);
  int exponent;
  double mantissa = std::frexp(reference, &exponent);
  int unit_exponent = exponent - 53;
  if (std::fabs(mantissa) == 0.5 && signed_error != 0 &&
      (signed_error < 0) == (reference > 0)) {
    --unit_exponent;
  }
  double unit = std::ldexp(1.0, unit_exponent < -1074 ? -1074 : unit_exponent);
  return std::fabs((got - reference) / unit - signed_error);
}

} // namespace

TEST(Cbrt, CorpusIsWithinOneUlp) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  double worst = 0;
  uint64_t worst_input = 0;
  size_t count = 0;
  for (const Entry & entry : Load()) {
    double result = CheckCall(entry.x);
    double error = UlpError(result, entry);
    EXPECT_LE(error, 1.0) << "cbrt input " << std::hex << entry.x;
    // Regression margin above 0.49999902 ulp observed in the independent
    // 116072-input seed1793071801/count100000 reference sample.
    EXPECT_LE(error, 0.51) << "cbrt regression input " << std::hex << entry.x;
    if (error > worst) {
      worst = error;
      worst_input = entry.x;
    }
    ++count;
  }
  std::printf("  cbrt: %zu entries, measured max error %.8f ulp at %a\n", count,
      worst, Value(worst_input));
}

TEST(Cbrt, UlpHelperUsesSignedTrueValueSpacing) {
  Entry positive{0, Bits(1.0), ErrorBits(-0.25f)};
  EXPECT_DOUBLE_EQ(UlpError(1.0, positive), 0.25);
  EXPECT_DOUBLE_EQ(UlpError(std::nextafter(1.0, 0.0), positive), 0.75);
  Entry negative{0, Bits(-1.0), ErrorBits(0.25f)};
  EXPECT_DOUBLE_EQ(UlpError(-1.0, negative), 0.25);
  EXPECT_DOUBLE_EQ(UlpError(std::nextafter(-1.0, 0.0), negative), 0.75);
  negative.error = ErrorBits(-0.25f);
  EXPECT_DOUBLE_EQ(UlpError(std::nextafter(-1.0, -INFINITY), negative), 0.75);
  negative.error = 0;
  EXPECT_DOUBLE_EQ(UlpError(std::nextafter(-1.0, 0.0), negative), 0.5);
  EXPECT_TRUE(std::isinf(UlpError(-0.0, {0, 0, 0})));
  EXPECT_TRUE(std::isinf(UlpError(Value(kNaN | 7), {0, kNaN, 0})));
}

TEST(Cbrt, EveryBinaryCubePowerIsExactWithoutExceptions) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  for (int q = -358; q <= 341; ++q) {
    double input = std::ldexp(1.0, 3 * q);
    double expected = std::ldexp(1.0, q);
    EXPECT_EQ(Bits(CheckCall(Bits(input))), Bits(expected)) << q;
    EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), 0);
    EXPECT_EQ(Bits(CheckCall(Bits(-input))), Bits(-expected)) << q;
    EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), 0);
  }
}

TEST(Cbrt, IsOddAcrossTheCommittedFiniteInputPopulation) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  for (const Entry & entry : Load()) {
    if ((entry.x & kSign) == 0 && entry.x != 0 && entry.x < kInf) {
      double positive = CheckCall(entry.x);
      double negative = CheckCall(entry.x | kSign);
      EXPECT_EQ(Bits(negative), Bits(positive) | kSign) << std::hex << entry.x;
    }
  }
}

TEST(Cbrt, SpecialValuesAndIncomingFlagsHaveExactBehavior) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  const uint64_t values[] = {0, kSign, kInf, kInf | kSign, kNaN,
      kNaN | kSign | 7, kNaN | (kQuiet - 1), kInf | 1, kInf | kSign | 1,
      kInf | (kQuiet - 1), kInf | kSign | (kQuiet - 1)};
  const int seeds[] = {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
      FE_INEXACT, FE_ALL_EXCEPT};
  for (int seed : seeds) {
    for (uint64_t word : values) {
      uint64_t expected = (word & ~kSign) > kInf ? kNaN : word;
      EXPECT_EQ(Bits(CheckCall(word, seed)), expected);
    }
  }
}

TEST(Cbrt, FiniteCallsPreserveErrnoModeAndExistingFlags) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  const uint64_t words[] = {Bits(1.0), Bits(-1.0), Bits(8.0), Bits(-8.0),
      Bits(27.0), Bits(-27.0), Bits(2.0), Bits(-2.0), 1, kSign | 1,
      0x0010000000000000ull, 0x8010000000000000ull, 0x7fefffffffffffffull,
      0xffefffffffffffffull};
  const int seeds[] = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
      FE_INEXACT, FE_ALL_EXCEPT};
  for (int seed : seeds) {
    for (uint64_t word : words) {
      (void)CheckCall(word, seed);
    }
  }
}

TEST(Cbrt, NondefaultModesArePreservedForSafeInputs) {
  Environment saved;
  const uint64_t words[] = {Bits(-8.0), Bits(-1.0), Bits(-0.0), Bits(0.0),
      Bits(1.0), Bits(2.0), Bits(8.0), Bits(27.0), 1, kSign | 1,
      0x0010000000000000ull, 0x8010000000000000ull, 0x7fefffffffffffffull,
      0xffefffffffffffffull, kInf, kInf | kSign, kNaN, kInf | 1};
  const int seeds[] = {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
      FE_INEXACT, FE_ALL_EXCEPT};
  for (int mode : {FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (int seed : seeds) {
      for (uint64_t word : words) {
        // Only state, allowed flags and normal finite output are checked;
        // accuracy and correct rounding are not promised in these modes.
        (void)CheckCall(word, seed, mode);
      }
    }
  }
}

TEST(Cbrt, NeighborsAreMonotoneAtReductionAndExactCubeBoundaries) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  auto check_neighbors = [](double center) {
    double previous = CheckCall(Bits(std::nextafter(center, -INFINITY)));
    double current = CheckCall(Bits(center));
    double next = CheckCall(Bits(std::nextafter(center, INFINITY)));
    EXPECT_LE(previous, current) << std::hexfloat << center;
    EXPECT_LE(current, next) << std::hexfloat << center;
  };
  for (int exponent = -1074; exponent <= 1023; ++exponent) {
    double x = std::ldexp(1.0, exponent);
    check_neighbors(x);
    check_neighbors(-x);
  }
  for (int exponent : {-1022, -1021, -1020, 0, 1, 2, 1020, 1021, 1022}) {
    for (int row = 0; row <= 64; ++row) {
      double x = std::ldexp(1.0 + static_cast<double>(row) / 64.0, exponent);
      check_neighbors(x);
      check_neighbors(-x);
    }
  }
  for (int n = 1; n <= 64; ++n) {
    for (int q : {-350, -340, -1, 0, 1, 300, 330}) {
      double x = std::ldexp(static_cast<double>(n * n * n), 3 * q);
      check_neighbors(x);
      check_neighbors(-x);
    }
  }
}

TEST(Cbrt, ExactInputScalingPreservesRootBitsAcrossExponentClasses) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  const double significands[] = {
      1.25, 1.5, 1.75, 1.015625, 1.0078125, 0x1.0000000000001p+0};
  bool saw_subnormal[3] = {false, false, false};
  bool saw_normal[3] = {false, false, false};
  size_t exercised[3] = {0, 0, 0};
  for (int r = 0; r < 3; ++r) {
    for (double significand : significands) {
      double base = std::ldexp(significand, r);
      double base_root = CheckCall(Bits(base));
      for (int q = -358; q <= 341; ++q) {
        double input = std::ldexp(base, 3 * q);
        if (!std::isfinite(input) || input == 0) {
          continue;
        }
        // Reverse scaling is exact for the candidate finite binary64 input.
        // Equality proves the forward scaling lost no significand bits;
        // rounded subnormal candidates are deliberately not property inputs.
        if (std::ldexp(input, -3 * q) != base) {
          continue;
        }
        saw_subnormal[r] |= std::fpclassify(input) == FP_SUBNORMAL;
        saw_normal[r] |= std::isnormal(input);
        double expected = std::ldexp(base_root, q);
        EXPECT_EQ(Bits(CheckCall(Bits(input))), Bits(expected))
            << "r " << r << " q " << q << " base " << std::hexfloat << base;
        EXPECT_EQ(Bits(CheckCall(Bits(-input))), Bits(-expected))
            << "r " << r << " q " << q << " base " << std::hexfloat << base;
        ++exercised[r];
      }
    }
    EXPECT_TRUE(saw_subnormal[r]) << r;
    EXPECT_TRUE(saw_normal[r]) << r;
    EXPECT_GT(exercised[r], 600u) << r;
  }
}

TEST(Cbrt, PositiveCountParserRejectsPartialZeroAndOverflow) {
  size_t count = 0;
  EXPECT_TRUE(PositiveInteger("1", &count));
  EXPECT_EQ(count, 1u);
  EXPECT_TRUE(PositiveInteger(
      std::to_string(std::numeric_limits<size_t>::max()), &count));
  EXPECT_EQ(count, std::numeric_limits<size_t>::max());
  for (const char * text : {"", "0", "-1", "+1", " 1", "1 ", "1junk", "junk"}) {
    EXPECT_FALSE(PositiveInteger(text, &count)) << text;
  }
  EXPECT_FALSE(PositiveInteger(
      std::to_string(std::numeric_limits<size_t>::max()) + "0", &count));
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
