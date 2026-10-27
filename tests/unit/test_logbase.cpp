/**
 * @file
 * Base-two/base-ten logarithms against pinned MPFR/mpmath reference values.
 * GMATH_LOGBASE_CORPUS_DIR selects another corpus directory.
 * These kernels require round-to-nearest; tests restore the original
 * environment. Copyright 2026 by Corey Pennycuff
 */
#include "test_helpers.h"

#include <ghoti.io/math/elementary.h>

#include <cerrno>
#include <cfenv>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <limits>
#include <sstream>
#include <string>
#include <type_traits>
#include <vector>

namespace {

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

template <class U>
using Number = std::conditional_t<sizeof(U) == 8, double, float>;

template <class U> Number<U> Value(U bits) {
  Number<U> value;
  std::memcpy(&value, &bits, sizeof value);
  return value;
}

template <class U> U Bits(Number<U> value) {
  U bits;
  std::memcpy(&bits, &value, sizeof bits);
  return bits;
}

template <class U> constexpr U Sign() {
  return U(1) << (sizeof(U) * 8 - 1);
}

template <class U> constexpr U Infinity() {
  if constexpr (sizeof(U) == 8) {
    return U(0x7ff0000000000000ull);
  }
  else {
    return U(0x7f800000u);
  }
}

template <class U> constexpr U Quiet() {
  if constexpr (sizeof(U) == 8) {
    return U(0x0008000000000000ull);
  }
  else {
    return U(0x00400000u);
  }
}

template <class U> int SpecialFlags(U x) {
  U a = x & ~Sign<U>();
  if (a > Infinity<U>()) {
    return (a & Quiet<U>()) == 0 ? FE_INVALID : 0;
  }
  if (a == 0) {
    return FE_DIVBYZERO;
  }
  return (x & Sign<U>()) != 0 ? FE_INVALID : 0;
}

template <class U> void CheckSpecials(Number<U> (*fn)(Number<U>)) {
  const U sign = Sign<U>(), inf = Infinity<U>(), quiet = Quiet<U>();
  const U one = Bits<U>(Number<U>(1));
  const U values[] = {0, sign, one, one | sign, inf, inf | sign, inf | quiet,
      inf | quiet | sign | 7, inf | quiet | (quiet - 1), inf | 1,
      inf | sign | 1, inf | (quiet - 1), inf | sign | (quiet - 1)};
  const int seeds[] = {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
      FE_INEXACT, FE_ALL_EXCEPT};
  for (int seed : seeds) {
    for (U word : values) {
      U a = word & ~sign;
      U expected = inf | quiet;
      if (a == 0) {
        expected = inf | sign;
      }
      else if (word == inf) {
        expected = inf;
      }
      else if (word == one) {
        expected = 0;
      }
      std::feclearexcept(FE_ALL_EXCEPT);
      if (seed != 0) {
        ASSERT_EQ(std::feraiseexcept(seed), 0);
      }
      int expected_flags =
          std::fetestexcept(FE_ALL_EXCEPT) | SpecialFlags(word);
      errno = E2BIG;
      Number<U> result = fn(Value(word));
      int result_errno = errno;
      int result_mode = std::fegetround();
      int result_flags = std::fetestexcept(FE_ALL_EXCEPT);
      EXPECT_EQ(result_errno, E2BIG);
      EXPECT_EQ(result_mode, FE_TONEAREST);
      EXPECT_EQ(Bits<U>(result), expected) << std::hex << word;
      EXPECT_EQ(result_flags, expected_flags) << std::hex << word;
    }
  }
}

struct Entry {
  uint64_t x, result;
  uint32_t error;
};

std::vector<Entry> Load(const char * name) {
  const char * env = std::getenv("GMATH_LOGBASE_CORPUS_DIR");
  std::string directory = env && *env ? env : "tests/corpus";
  std::ifstream input(directory + "/" + name + ".corpus");
  EXPECT_TRUE(input.is_open()) << "missing " << name << " corpus";
  std::vector<Entry> entries;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    Entry entry{};
    std::string extra;
    std::istringstream parser(line);
    if (!(parser >> std::hex >> entry.x >> entry.result >> entry.error) ||
        (parser >> extra)) {
      ADD_FAILURE() << "bad " << name << " corpus row: " << line;
      continue;
    }
    entries.push_back(entry);
  }
  const char * minimum = std::getenv("GMATH_LOGBASE_MIN_ENTRIES");
  size_t min_entries =
      minimum && *minimum ? std::strtoul(minimum, nullptr, 10) : 1000;
  EXPECT_GE(entries.size(), min_entries)
      << "missing or truncated " << name << " corpus";
  return entries;
}

double UlpError(double got, const Entry & entry, int precision) {
  double reference = Value(entry.result);
  if (std::isnan(reference)) {
    return Bits<uint64_t>(got) == 0x7ff8000000000000ull
        ? 0.0
        : std::numeric_limits<double>::infinity();
  }
  if (reference == 0 || std::isinf(reference)) {
    return Bits<uint64_t>(got) == entry.result
        ? 0.0
        : std::numeric_limits<double>::infinity();
  }
  if (!std::isfinite(got)) {
    return std::numeric_limits<double>::infinity();
  }
  double signed_error = Value(entry.error);
  int exponent;
  double mantissa = std::frexp(reference, &exponent);
  int unit_exponent = exponent - precision;
  // The rounded result can cross a binade boundary. err is signed relative
  // to true-value spacing, so recover the binade of the true value.
  if (std::fabs(mantissa) == 0.5 && signed_error != 0 &&
      (signed_error < 0) == (reference > 0)) {
    --unit_exponent;
  }
  const int minimum_unit = precision == 24 ? -149 : -1074;
  double unit = std::ldexp(
      1.0, unit_exponent < minimum_unit ? minimum_unit : unit_exponent);
  return std::fabs((got - reference) / unit - signed_error);
}

double FloatLog(double x) {
  return static_cast<double>(gmath_log2f(static_cast<float>(x)));
}

struct Function {
  const char * name;
  double (*fn)(double);
  int precision;
};
const Function kFunctions[] = {{"log2", gmath_log2, 53},
    {"log10", gmath_log10, 53}, {"log2f", FloatLog, 24}};

} // namespace

TEST(Logbase, CorpusIsWithinOneUlp) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  for (const Function & function : kFunctions) {
    double worst = 0;
    uint64_t worst_input = 0;
    size_t count = 0;
    for (const Entry & entry : Load(function.name)) {
      std::feclearexcept(FE_ALL_EXCEPT);
      errno = E2BIG;
      double result = function.fn(Value(entry.x));
      int result_errno = errno;
      int result_mode = std::fegetround();
      int result_flags = std::fetestexcept(FE_ALL_EXCEPT);
      EXPECT_EQ(result_errno, E2BIG);
      EXPECT_EQ(result_mode, FE_TONEAREST);
      uint64_t a = entry.x & ~Sign<uint64_t>();
      int required = SpecialFlags(entry.x);
      EXPECT_EQ(result_flags & ~FE_INEXACT, required)
          << function.name << " flags at input " << std::hex << entry.x;
      if (a > Infinity<uint64_t>() || a == 0 ||
          (entry.x & Sign<uint64_t>()) != 0 || entry.x == Bits<uint64_t>(1.0) ||
          a == Infinity<uint64_t>()) {
        EXPECT_EQ(result_flags, required);
      }
      double error = UlpError(result, entry, function.precision);
      if (error > worst) {
        worst = error;
        worst_input = entry.x;
      }
      EXPECT_LE(error, 1.0)
          << function.name << " input " << std::hex << entry.x;
      // Regression margin tighter than the public one-ulp contract: both
      // kernels retain precision until the last target-format rounding.
      EXPECT_LE(error, 0.51) << function.name << " precision regression at "
                             << std::hex << entry.x;
      ++count;
    }
    std::printf("  %s: %zu entries, measured max error %.6f ulp at %a\n",
        function.name, count, worst, Value(worst_input));
  }
}

TEST(Logbase, UlpInstrumentRecoversBothSidesOfSignedBinadeBoundaries) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  for (int precision : {24, 53}) {
    double up = std::ldexp(1.0, 1 - precision);
    double down = std::ldexp(1.0, -precision);
    Entry positive_above{0, Bits<uint64_t>(1.0), Bits<uint32_t>(0.25f)};
    Entry positive_below{0, Bits<uint64_t>(1.0), Bits<uint32_t>(-0.25f)};
    Entry negative_above{0, Bits<uint64_t>(-1.0), Bits<uint32_t>(0.25f)};
    Entry negative_below{0, Bits<uint64_t>(-1.0), Bits<uint32_t>(-0.25f)};
    EXPECT_DOUBLE_EQ(UlpError(1.0, positive_above, precision), 0.25);
    EXPECT_DOUBLE_EQ(UlpError(1.0 + up, positive_above, precision), 0.75);
    EXPECT_DOUBLE_EQ(UlpError(1.0 - down, positive_below, precision), 0.75);
    EXPECT_DOUBLE_EQ(UlpError(1.0 + up, positive_below, precision), 2.25);
    EXPECT_DOUBLE_EQ(UlpError(-1.0 + down, negative_above, precision), 0.75);
    EXPECT_DOUBLE_EQ(UlpError(-1.0 - up, negative_above, precision), 2.25);
    EXPECT_DOUBLE_EQ(UlpError(-1.0 - up, negative_below, precision), 0.75);
  }
}

TEST(Logbase, SpecialValuesExceptionsAndExistingState) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  CheckSpecials<uint64_t>(gmath_log2);
  CheckSpecials<uint64_t>(gmath_log10);
  CheckSpecials<uint32_t>(gmath_log2f);
}

TEST(Logbase, FiniteCallsPreserveExistingFlagsAndErrno) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  const int seeds[] = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
      FE_INEXACT, FE_ALL_EXCEPT};
  for (const Function & function : kFunctions) {
    double tiny = function.precision == 24
        ? static_cast<double>(std::numeric_limits<float>::denorm_min())
        : std::numeric_limits<double>::denorm_min();
    for (double input : {1.5, 10.0, tiny}) {
      for (int seed : seeds) {
        std::feclearexcept(FE_ALL_EXCEPT);
        ASSERT_EQ(std::feraiseexcept(seed), 0);
        int incoming_flags = std::fetestexcept(FE_ALL_EXCEPT);
        errno = E2BIG;
        double result = function.fn(input);
        int result_errno = errno;
        int result_mode = std::fegetround();
        int result_flags = std::fetestexcept(FE_ALL_EXCEPT);
        EXPECT_EQ(result_errno, E2BIG);
        EXPECT_EQ(result_mode, FE_TONEAREST);
        EXPECT_TRUE(std::isfinite(result));
        EXPECT_EQ(result_flags & incoming_flags, incoming_flags);
        EXPECT_EQ(result_flags & ~(incoming_flags | FE_INEXACT), 0);
      }
    }
  }
}

TEST(Logbase, EveryBinaryPowerIsExactWithoutExceptions) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  for (int exponent = -1074; exponent <= 1023; ++exponent) {
    double x = std::ldexp(1.0, exponent);
    std::feclearexcept(FE_ALL_EXCEPT);
    errno = E2BIG;
    double result = gmath_log2(x);
    EXPECT_EQ(errno, E2BIG);
    EXPECT_EQ(
        Bits<uint64_t>(result), Bits<uint64_t>(static_cast<double>(exponent)));
    EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), 0) << exponent;
    EXPECT_EQ(std::fegetround(), FE_TONEAREST);
  }
  for (int exponent = -149; exponent <= 127; ++exponent) {
    float x = std::ldexp(1.0f, exponent);
    std::feclearexcept(FE_ALL_EXCEPT);
    errno = E2BIG;
    float result = gmath_log2f(x);
    EXPECT_EQ(errno, E2BIG);
    EXPECT_EQ(
        Bits<uint32_t>(result), Bits<uint32_t>(static_cast<float>(exponent)));
    EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), 0) << exponent;
    EXPECT_EQ(std::fegetround(), FE_TONEAREST);
  }
}

TEST(Logbase, RepresentableDecimalPowersGiveExactIntegerResults) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  double x = 1.0;
  for (int exponent = 0; exponent <= 22; ++exponent) {
    std::feclearexcept(FE_ALL_EXCEPT);
    errno = E2BIG;
    double result = gmath_log10(x);
    EXPECT_EQ(errno, E2BIG);
    EXPECT_EQ(
        Bits<uint64_t>(result), Bits<uint64_t>(static_cast<double>(exponent)));
    EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT) & ~FE_INEXACT, 0);
    if (exponent == 0) {
      EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), 0);
    }
    EXPECT_EQ(std::fegetround(), FE_TONEAREST);
    x *= 10.0;
  }
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
