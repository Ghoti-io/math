/**
 * @file
 * Exact extrema against rational/IEEE corpora, raw special values and flags.
 * GMATH_EXTREMA_CORPUS_DIR selects another extrema corpus directory.
 * Copyright 2026 by Corey Pennycuff
 */
#include "test_helpers.h"

#include <ghoti.io/math/basic.h>

#include <cerrno>
#include <cfenv>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <random>
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

template <class U> bool Signaling(U x) {
  return (x & ~Sign<U>()) > Infinity<U>() && (x & Quiet<U>()) == 0;
}

// Numeric comparison is independent of the implementation's integer ordering.
// Classify raw bits first so the reference never evaluates a signaling NaN.
template <class U> U Expected(U x, U y, bool minimum) {
  const U ax = x & ~Sign<U>(), ay = y & ~Sign<U>();
  const U canonical = Infinity<U>() | Quiet<U>();
  if (Signaling(x) || Signaling(y)) {
    return canonical;
  }
  if (ax > Infinity<U>()) {
    return ay > Infinity<U>() ? canonical : y;
  }
  if (ay > Infinity<U>()) {
    return x;
  }
  if (ax == 0 && ay == 0) {
    return minimum ? (x | y) : (x & y);
  }
  Number<U> a = Value(x), b = Value(y);
  return minimum ? (a < b ? x : y) : (a > b ? x : y);
}

template <class U>
void CheckSpecials(
    Number<U> (*fn)(Number<U>, Number<U>), bool minimum, int incoming_flags) {
  const U sign = Sign<U>(), inf = Infinity<U>(), quiet = Quiet<U>();
  const U one = Bits<U>(Number<U>(1));
  std::vector<U> values = {0, sign, one, sign | one, 1, sign | 1, inf - 1,
      sign | (inf - 1), inf, sign | inf, inf | quiet | 7,
      sign | inf | quiet | 3, inf | 1, sign | inf | 1};
  const U payloads[] = {1, quiet - 1, quiet, quiet + 1, (quiet << 1) - 1,
      U(0x12345), quiet | U(0x12345), U(0x2aaaa), quiet | U(0x2aaaa)};
  for (U payload : payloads) {
    values.push_back(inf | payload);
    values.push_back(sign | inf | payload);
  }
  const int incoming_mode = std::fegetround();
  for (U x : values) {
    for (U y : values) {
      U expected = Expected(x, y, minimum);
      int flags = Signaling(x) || Signaling(y) ? FE_INVALID : 0;
      std::feclearexcept(FE_ALL_EXCEPT);
      if (incoming_flags != 0) {
        ASSERT_EQ(std::feraiseexcept(incoming_flags), 0);
      }
      // Raising overflow/underflow can also set inexact on some targets.
      flags |= std::fetestexcept(FE_ALL_EXCEPT);
      errno = E2BIG;
      Number<U> result = fn(Value(x), Value(y));
      int returned_errno = errno;
      int returned_mode = std::fegetround();
      int returned_flags = std::fetestexcept(FE_ALL_EXCEPT);
      EXPECT_EQ(returned_errno, E2BIG);
      EXPECT_EQ(returned_mode, incoming_mode);
      EXPECT_EQ(Bits<U>(result), expected)
          << std::hex << x << " " << y << " minimum " << minimum;
      EXPECT_EQ(returned_flags, flags);
    }
  }
}

struct Row {
  uint64_t x, y, result;
};

std::vector<Row> Load(const char * name) {
  const char * env = std::getenv("GMATH_EXTREMA_CORPUS_DIR");
  std::string directory = env && *env ? env : "tests/corpus";
  std::ifstream input(directory + "/" + name + ".corpus");
  EXPECT_TRUE(input.is_open()) << "missing " << name << " corpus";
  std::vector<Row> rows;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    Row row{};
    std::string extra;
    std::istringstream parser(line);
    if (!(parser >> std::hex >> row.x >> row.y >> row.result) ||
        (parser >> extra)) {
      ADD_FAILURE() << "bad " << name << " corpus row: " << line;
      continue;
    }
    rows.push_back(row);
  }
  EXPECT_GE(rows.size(), 1000u) << "missing or truncated " << name << " corpus";
  return rows;
}

struct DoubleFn {
  const char * name;
  double (*fn)(double, double);
};
const DoubleFn kDoubles[] = {{"fmin", gmath_fmin}, {"fmax", gmath_fmax}};
struct FloatFn {
  const char * name;
  float (*fn)(float, float);
};
const FloatFn kFloats[] = {{"fminf", gmath_fminf}, {"fmaxf", gmath_fmaxf}};

void CheckCorpus() {
  const int incoming_mode = std::fegetround();
  for (const DoubleFn & function : kDoubles) {
    for (const Row & row : Load(function.name)) {
      std::feclearexcept(FE_ALL_EXCEPT);
      errno = E2BIG;
      double result = function.fn(Value(row.x), Value(row.y));
      EXPECT_EQ(errno, E2BIG);
      EXPECT_EQ(std::fegetround(), incoming_mode);
      EXPECT_EQ(Bits<uint64_t>(result), row.result)
          << function.name << " " << std::hex << row.x << " " << row.y;
      int flags = Signaling(row.x) || Signaling(row.y) ? FE_INVALID : 0;
      EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), flags);
    }
  }
  for (const FloatFn & function : kFloats) {
    for (const Row & row : Load(function.name)) {
      float x = static_cast<float>(Value(row.x));
      float y = static_cast<float>(Value(row.y));
      std::feclearexcept(FE_ALL_EXCEPT);
      errno = E2BIG;
      float result = function.fn(x, y);
      EXPECT_EQ(errno, E2BIG);
      EXPECT_EQ(std::fegetround(), incoming_mode);
      EXPECT_EQ(Bits<uint64_t>(static_cast<double>(result)), row.result)
          << function.name << " " << std::hex << row.x << " " << row.y;
      EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), 0);
    }
  }
}

} // namespace

TEST(Extrema, CorpusIsExact) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  CheckCorpus();
}

TEST(Extrema, RawSpecialValuesAndExceptions) {
  Environment saved;
  for (int mode : {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    CheckSpecials<uint64_t>(gmath_fmin, true, 0);
    CheckSpecials<uint64_t>(gmath_fmax, false, 0);
    CheckSpecials<uint32_t>(gmath_fminf, true, 0);
    CheckSpecials<uint32_t>(gmath_fmaxf, false, 0);
  }
}

TEST(Extrema, ExistingFlagsAndErrnoArePreserved) {
  Environment saved;
  const int flags[] = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
      FE_INEXACT, FE_ALL_EXCEPT};
  for (int mode : {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (int incoming : flags) {
      CheckSpecials<uint64_t>(gmath_fmin, true, incoming);
      CheckSpecials<uint64_t>(gmath_fmax, false, incoming);
      CheckSpecials<uint32_t>(gmath_fminf, true, incoming);
      CheckSpecials<uint32_t>(gmath_fmaxf, false, incoming);
    }
  }
}

TEST(Extrema, EveryRoundingModePreservesResultsAndFlags) {
  Environment saved;
  for (int mode : {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    CheckCorpus();
  }
}

TEST(Extrema, RandomFiniteInputsAgreeWithHostLibm) {
  Environment saved;
  std::mt19937_64 rng(0x65787472656d6121ull);
  for (int i = 0; i < 25000; ++i) {
    uint64_t x = rng(), y = rng();
    if ((x & ~Sign<uint64_t>()) < Infinity<uint64_t>() &&
        (y & ~Sign<uint64_t>()) < Infinity<uint64_t>() &&
        ((x | y) & ~Sign<uint64_t>()) != 0) {
      double a = Value(x), b = Value(y);
      EXPECT_EQ(
          Bits<uint64_t>(gmath_fmin(a, b)), Bits<uint64_t>(std::fmin(a, b)));
      EXPECT_EQ(
          Bits<uint64_t>(gmath_fmax(a, b)), Bits<uint64_t>(std::fmax(a, b)));
    }
    uint32_t xf = static_cast<uint32_t>(rng()),
             yf = static_cast<uint32_t>(rng());
    if ((xf & ~Sign<uint32_t>()) < Infinity<uint32_t>() &&
        (yf & ~Sign<uint32_t>()) < Infinity<uint32_t>() &&
        ((xf | yf) & ~Sign<uint32_t>()) != 0) {
      float a = Value(xf), b = Value(yf);
      EXPECT_EQ(
          Bits<uint32_t>(gmath_fminf(a, b)), Bits<uint32_t>(std::fmin(a, b)));
      EXPECT_EQ(
          Bits<uint32_t>(gmath_fmaxf(a, b)), Bits<uint32_t>(std::fmax(a, b)));
    }
  }
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
