/**
 * @file
 * exp2 against pinned MPFR600/mpmath640 reference values and exact IEEE cases.
 * GMATH_EXP2_CORPUS_DIR selects another required corpus directory.
 * The API requires FE_TONEAREST; these tests restore the incoming environment.
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
  const uint64_t a = word & ~kSign;
  if (a > kInf) {
    int flags = (a & kQuiet) == 0 ? FE_INVALID : 0;
    return {flags, flags};
  }
  if (a == kInf || a == 0) {
    return {0, 0};
  }
  double x = Value(word);
  if (x >= 1024) {
    return {FE_OVERFLOW | FE_INEXACT, FE_OVERFLOW | FE_INEXACT};
  }
  if (x <= -1075) {
    return {FE_UNDERFLOW | FE_INEXACT, FE_UNDERFLOW | FE_INEXACT};
  }
  if (x == std::trunc(x)) {
    return {0, 0};
  }
  if (x < -1022) {
    return {FE_UNDERFLOW | FE_INEXACT, FE_UNDERFLOW | FE_INEXACT};
  }
  return {0, FE_INEXACT};
}

double CheckCall(uint64_t word, int incoming_flags = 0) {
  Policy policy = ExpectedPolicy(word);
  std::feclearexcept(FE_ALL_EXCEPT);
  if (incoming_flags != 0) {
    EXPECT_EQ(std::feraiseexcept(incoming_flags), 0);
  }
  // An overflow/underflow seed may also raise inexact on the target.
  int existing = std::fetestexcept(FE_ALL_EXCEPT);
  errno = E2BIG;
  double result = gmath_exp2(Value(word));
  int returned_errno = errno;
  int returned_mode = std::fegetround();
  int returned_flags = std::fetestexcept(FE_ALL_EXCEPT);
  EXPECT_EQ(returned_errno, E2BIG) << std::hex << word;
  EXPECT_EQ(returned_mode, FE_TONEAREST);
  EXPECT_EQ(
      returned_flags & (policy.required | existing), policy.required | existing)
      << std::hex << word;
  EXPECT_EQ(returned_flags & ~(policy.allowed | existing), 0)
      << std::hex << word;
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
  const char * env = std::getenv("GMATH_EXP2_CORPUS_DIR");
  std::string directory = env && *env ? env : "tests/corpus";
  std::ifstream input(directory + "/exp2.corpus");
  EXPECT_TRUE(input.is_open()) << "missing exp2 corpus";
  std::vector<Entry> entries;
  std::unordered_set<uint64_t> inputs;
  size_t declared_entries = 0;
  bool have_count = false;
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
          EXPECT_FALSE(have_count) << "duplicate exp2 entries header";
          have_count = true;
          std::string count;
          if (!(header >> count) ||
              !PositiveInteger(count, &declared_entries)) {
            ADD_FAILURE() << "invalid exp2 entries header: " << line;
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
      ADD_FAILURE() << "bad exp2 corpus row: " << line;
      continue;
    }
    if (!inputs.insert(entry.x).second) {
      ADD_FAILURE() << "duplicate exp2 input word: " << std::hex << entry.x;
    }
    entries.push_back(entry);
  }
  EXPECT_TRUE(have_count) << "missing required exp2 entries header";
  EXPECT_EQ(entries.size(), declared_entries)
      << "exp2 corpus count disagrees with header";
  const char * minimum = std::getenv("GMATH_EXP2_MIN_ENTRIES");
  size_t required = 1000;
  if (minimum != nullptr && !PositiveInteger(minimum, &required)) {
    ADD_FAILURE()
        << "GMATH_EXP2_MIN_ENTRIES must be a complete positive decimal integer";
  }
  EXPECT_GE(entries.size(), required) << "missing or truncated exp2 corpus";
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
  if (mantissa == 0.5 && signed_error < 0) {
    --unit_exponent;
  }
  double unit = std::ldexp(1.0, unit_exponent < -1074 ? -1074 : unit_exponent);
  return std::fabs((got - reference) / unit - signed_error);
}

} // namespace

TEST(Exp2, CorpusIsWithinOneUlpAndRegressionBounds) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  double max_normal = 0, max_subnormal = 0;
  uint64_t normal_input = 0, subnormal_input = 0;
  size_t count = 0;
  for (const Entry & entry : Load()) {
    double got = CheckCall(entry.x);
    double error = UlpError(got, entry);
    double reference = Value(entry.result);
    bool subnormal =
        reference > 0 && reference < std::numeric_limits<double>::min();
    double limit = subnormal ? 0.76 : 0.52;
    EXPECT_LE(error, limit) << "exp2 input " << std::hex << entry.x;
    if (subnormal && error > max_subnormal) {
      max_subnormal = error;
      subnormal_input = entry.x;
    }
    if (!subnormal && error > max_normal) {
      max_normal = error;
      normal_input = entry.x;
    }
    ++count;
  }
  std::printf("  exp2: %zu entries; measured normal max %.6f ulp at %a; "
              "subnormal max %.6f ulp at %a\n",
      count, max_normal, Value(normal_input), max_subnormal,
      Value(subnormal_input));
}

TEST(Exp2, UlpHelperUsesTrueBinadeAndSubnormalSpacing) {
  Entry one{0, Bits(1.0), ErrorBits(-0.25f)};
  EXPECT_DOUBLE_EQ(UlpError(1.0, one), 0.25);
  EXPECT_DOUBLE_EQ(UlpError(std::nextafter(1.0, 0.0), one), 0.75);
  one.error = 0;
  EXPECT_DOUBLE_EQ(UlpError(std::nextafter(1.0, 0.0), one), 0.5);
  Entry sub{0, 2, ErrorBits(0.25f)};
  EXPECT_DOUBLE_EQ(UlpError(Value(2), sub), 0.25);
  EXPECT_DOUBLE_EQ(UlpError(Value(3), sub), 0.75);
  Entry boundary{0, 0x0010000000000000ull, ErrorBits(-0.25f)};
  EXPECT_DOUBLE_EQ(UlpError(Value(boundary.result - 1), boundary), 0.75);
  EXPECT_TRUE(std::isinf(UlpError(-0.0, {0, 0, 0})));
  EXPECT_TRUE(
      std::isinf(UlpError(std::numeric_limits<double>::max(), {0, kInf, 0})));
  EXPECT_TRUE(std::isinf(UlpError(Value(kNaN | 7), {0, kNaN, 0})));
}

TEST(Exp2, PositiveCountParserRejectsPartialZeroAndOverflow) {
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

TEST(Exp2, NondefaultRoundingModesArePreservedForSafeInputs) {
  Environment saved;
  for (int mode : {FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (double input : {-1.0, -0.0, 0.0, 0.5, 1.0, 2.0}) {
      volatile double result = gmath_exp2(input);
      (void)result;
      EXPECT_EQ(std::fegetround(), mode);
    }
  }
}

TEST(Exp2, EveryRepresentableIntegerPowerIsExactWithoutExceptions) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  for (int exponent = -1074; exponent <= 1023; ++exponent) {
    double expected = std::ldexp(1.0, exponent);
    double result = CheckCall(Bits(static_cast<double>(exponent)));
    EXPECT_EQ(Bits(result), Bits(expected)) << exponent;
    EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), 0) << exponent;
  }
}

TEST(Exp2, SpecialValuesHaveCanonicalBitsAndRequiredExceptions) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  const uint64_t values[] = {0, kSign, kInf, kInf | kSign, kNaN,
      kNaN | kSign | 7, kNaN | (kQuiet - 1), kInf | 1, kInf | kSign | 1,
      kInf | (kQuiet - 1)};
  for (uint64_t word : values) {
    uint64_t a = word & ~kSign;
    uint64_t expected = a == 0 ? Bits(1.0)
        : a > kInf             ? kNaN
        : (word & kSign) != 0  ? 0
                               : kInf;
    EXPECT_EQ(Bits(CheckCall(word)), expected);
  }
}

TEST(Exp2, ThresholdNeighborsRaiseOnlyTheRequiredExceptions) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  EXPECT_EQ(Bits(CheckCall(Bits(-1075.0))), 0u);
  EXPECT_EQ(Bits(CheckCall(Bits(std::nextafter(-1075.0, -INFINITY)))), 0u);
  EXPECT_EQ(Bits(CheckCall(Bits(std::nextafter(-1075.0, INFINITY)))), 1u);
  EXPECT_EQ(Bits(CheckCall(Bits(-1074.0))), 1u);
  EXPECT_EQ(Bits(CheckCall(Bits(-1022.0))), 0x0010000000000000ull);
  double subnormal = CheckCall(Bits(std::nextafter(-1022.0, -INFINITY)));
  EXPECT_GT(subnormal, 0);
  EXPECT_LT(subnormal, std::numeric_limits<double>::min());
  EXPECT_TRUE(
      std::isfinite(CheckCall(Bits(std::nextafter(1024.0, -INFINITY)))));
  EXPECT_EQ(Bits(CheckCall(Bits(1024.0))), kInf);
  EXPECT_EQ(Bits(CheckCall(Bits(std::nextafter(1024.0, INFINITY)))), kInf);
  for (double tiny : {0x1p-54, -0x1p-54, 0x1p-55, -0x1p-55}) {
    EXPECT_EQ(Bits(CheckCall(Bits(tiny))), Bits(1.0));
  }
}

TEST(Exp2, IncomingExceptionFlagsErrnoAndModeArePreserved) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  const int seeds[] = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
      FE_INEXACT, FE_ALL_EXCEPT};
  const uint64_t words[] = {Bits(0.0), Bits(-0.0), Bits(0.5), Bits(1.0),
      Bits(-1074.0), Bits(-1074.5), Bits(-1075.0),
      Bits(std::nextafter(-1022.0, -INFINITY)),
      Bits(std::nextafter(1024.0, -INFINITY)), Bits(1024.0), Bits(0x1p-55),
      Bits(-0x1p-55), kInf, kInf | kSign, kNaN, kNaN | kSign | 7, kInf | 1,
      kInf | kSign | 1};
  for (int seed : seeds) {
    for (uint64_t word : words) {
      (void)CheckCall(word, seed);
    }
  }
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
