/**
 * @file
 * Exact binary remainders against an independent rational corpus, raw IEEE
 * special values, rounding modes, and an additional host-libm differential.
 * GMATH_REMAINDER_CORPUS_DIR selects an alternate remainder corpus directory;
 * existing elementary fresh-sample directories do not contain these corpora.
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
#include <vector>

namespace {

constexpr uint64_t kNaN = 0x7ff8000000000000ull;
constexpr uint32_t kNaNf = 0x7fc00000u;

uint64_t Bits(double x) {
  uint64_t bits;
  std::memcpy(&bits, &x, sizeof bits);
  return bits;
}
uint32_t Bits(float x) {
  uint32_t bits;
  std::memcpy(&bits, &x, sizeof bits);
  return bits;
}
double Double(uint64_t bits) {
  double x;
  std::memcpy(&x, &bits, sizeof x);
  return x;
}
float Float(uint32_t bits) {
  float x;
  std::memcpy(&x, &bits, sizeof x);
  return x;
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

struct Row {
  uint64_t x, y, result;
};

std::vector<Row> Load(const char * name) {
  const char * env = std::getenv("GMATH_REMAINDER_CORPUS_DIR");
  std::string directory = env && *env ? env : "tests/corpus";
  std::ifstream input(directory + "/" + name + ".corpus");
  EXPECT_TRUE(input.is_open()) << "missing " << name << " corpus";
  std::vector<Row> rows;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    std::istringstream parser(line);
    Row row{};
    std::string extra;
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

bool Valid(double x, double y) {
  return std::isfinite(x) && !std::isnan(y) && y != 0;
}

} // namespace

TEST(Remainder, CorpusIsExact) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  for (const Row & row : Load("fmod")) {
    double x = Double(row.x), y = Double(row.y);
    std::feclearexcept(FE_ALL_EXCEPT);
    double result = gmath_fmod(x, y);
    EXPECT_EQ(Bits(result), row.result) << std::hex << row.x << " " << row.y;
    if (Valid(x, y)) {
      EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), 0);
    }
  }
  for (const Row & row : Load("fmodf")) {
    float x = static_cast<float>(Double(row.x));
    float y = static_cast<float>(Double(row.y));
    std::feclearexcept(FE_ALL_EXCEPT);
    float result = gmath_fmodf(x, y);
    EXPECT_EQ(Bits(static_cast<double>(result)), row.result)
        << std::hex << row.x << " " << row.y;
    if (Valid(x, y)) {
      EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), 0);
    }
  }
}

TEST(Remainder, SpecialValuesAndExceptions) {
  Environment saved;
  const uint64_t q = kNaN | 7, s = 0x7ff0000000000001ull;
  const uint64_t inf = 0x7ff0000000000000ull;
  struct Case {
    uint64_t x, y, result;
    bool invalid;
  };
  const Case cases[] = {
      {Bits(5.0), Bits(2.0), Bits(1.0), false},
      {Bits(-5.0), Bits(2.0), Bits(-1.0), false},
      {Bits(5.0), Bits(-2.0), Bits(1.0), false},
      {Bits(-5.0), Bits(-2.0), Bits(-1.0), false},
      {Bits(-4.0), Bits(2.0), Bits(-0.0), false},
      {Bits(-0.0), Bits(2.0), Bits(-0.0), false},
      {Bits(3.0), inf, Bits(3.0), false},
      {Bits(-3.0), inf | (1ull << 63), Bits(-3.0), false},
      {inf, Bits(2.0), kNaN, true},
      {inf, inf, kNaN, true},
      {Bits(0.0), Bits(-0.0), kNaN, true},
      {Bits(1.0), Bits(0.0), kNaN, true},
      {q, Bits(2.0), kNaN, false},
      {Bits(2.0), q, kNaN, false},
      {q, q, kNaN, false},
      {q, Bits(0.0), kNaN, false},
      {inf, q, kNaN, false},
      {s, Bits(2.0), kNaN, true},
      {Bits(2.0), s, kNaN, true},
      {q, s, kNaN, true},
      {s, q, kNaN, true},
      {s, s, kNaN, true},
  };
  for (const Case & c : cases) {
    std::feclearexcept(FE_ALL_EXCEPT);
    double result = gmath_fmod(Double(c.x), Double(c.y));
    EXPECT_EQ(Bits(result), c.result);
    EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), c.invalid ? FE_INVALID : 0);
  }
  const uint32_t qf = kNaNf | 7, sf = 0x7f800001u, inff = 0x7f800000u;
  struct CaseF {
    uint32_t x, y, result;
    bool invalid;
  };
  const CaseF float_cases[] = {
      {Bits(-5.0f), Bits(-2.0f), Bits(-1.0f), false},
      {Bits(-4.0f), Bits(2.0f), Bits(-0.0f), false},
      {Bits(-0.0f), Bits(2.0f), Bits(-0.0f), false},
      {Bits(-3.0f), inff, Bits(-3.0f), false},
      {inff, Bits(2.0f), kNaNf, true},
      {inff, inff, kNaNf, true},
      {Bits(0.0f), Bits(-0.0f), kNaNf, true},
      {Bits(1.0f), Bits(0.0f), kNaNf, true},
      {qf, Bits(2.0f), kNaNf, false},
      {Bits(2.0f), qf, kNaNf, false},
      {qf, qf, kNaNf, false},
      {qf, Bits(0.0f), kNaNf, false},
      {inff, qf, kNaNf, false},
      {sf, Bits(2.0f), kNaNf, true},
      {Bits(2.0f), sf, kNaNf, true},
      {qf, sf, kNaNf, true},
      {sf, qf, kNaNf, true},
      {sf, sf, kNaNf, true},
  };
  for (const CaseF & c : float_cases) {
    std::feclearexcept(FE_ALL_EXCEPT);
    float result = gmath_fmodf(Float(c.x), Float(c.y));
    EXPECT_EQ(Bits(result), c.result);
    EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), c.invalid ? FE_INVALID : 0);
  }
}

TEST(Remainder, ExistingFlagsAndErrnoArePreserved) {
  Environment saved;
  struct Case {
    uint64_t x, y, result;
    bool invalid;
  };
  const uint64_t q = kNaN | 7, sn = 0x7ff0000000000001ull;
  const uint64_t inf = 0x7ff0000000000000ull;
  const Case doubles[] = {
      {Bits(5.0), Bits(2.0), Bits(1.0), false},
      {Bits(-4.0), Bits(2.0), Bits(-0.0), false},
      {Bits(-0.0), Bits(2.0), Bits(-0.0), false},
      {Bits(-1.0), Bits(2.0), Bits(-1.0), false},
      {Bits(1.0), inf, Bits(1.0), false},
      {inf, Bits(2.0), kNaN, true},
      {Bits(1.0), Bits(0.0), kNaN, true},
      {q, Bits(2.0), kNaN, false},
      {Bits(2.0), q, kNaN, false},
      {sn, Bits(2.0), kNaN, true},
      {Bits(2.0), sn, kNaN, true},
      {q, sn, kNaN, true},
  };
  for (const Case & c : doubles) {
    std::feclearexcept(FE_ALL_EXCEPT);
    ASSERT_EQ(std::feraiseexcept(FE_DIVBYZERO), 0);
    errno = E2BIG;
    double result = gmath_fmod(Double(c.x), Double(c.y));
    EXPECT_EQ(errno, E2BIG);
    EXPECT_EQ(Bits(result), c.result);
    EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT),
        FE_DIVBYZERO | (c.invalid ? FE_INVALID : 0));
  }
  struct CaseF {
    uint32_t x, y, result;
    bool invalid;
  };
  const uint32_t qf = kNaNf | 7, sf = 0x7f800001u, inff = 0x7f800000u;
  const CaseF floats[] = {
      {Bits(5.0f), Bits(2.0f), Bits(1.0f), false},
      {Bits(-4.0f), Bits(2.0f), Bits(-0.0f), false},
      {Bits(-0.0f), Bits(2.0f), Bits(-0.0f), false},
      {Bits(-1.0f), Bits(2.0f), Bits(-1.0f), false},
      {Bits(1.0f), inff, Bits(1.0f), false},
      {inff, Bits(2.0f), kNaNf, true},
      {Bits(1.0f), Bits(0.0f), kNaNf, true},
      {qf, Bits(2.0f), kNaNf, false},
      {Bits(2.0f), qf, kNaNf, false},
      {sf, Bits(2.0f), kNaNf, true},
      {Bits(2.0f), sf, kNaNf, true},
      {qf, sf, kNaNf, true},
  };
  for (const CaseF & c : floats) {
    std::feclearexcept(FE_ALL_EXCEPT);
    ASSERT_EQ(std::feraiseexcept(FE_DIVBYZERO), 0);
    errno = E2BIG;
    float result = gmath_fmodf(Float(c.x), Float(c.y));
    EXPECT_EQ(errno, E2BIG);
    EXPECT_EQ(Bits(result), c.result);
    EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT),
        FE_DIVBYZERO | (c.invalid ? FE_INVALID : 0));
  }
}

TEST(Remainder, EveryRoundingModePreservesExactResultsAndFlags) {
  Environment saved;
  const int modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
  const auto doubles = Load("fmod");
  const auto floats = Load("fmodf");
  for (int mode : modes) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (const Row & row : doubles) {
      double x = Double(row.x), y = Double(row.y);
      if (!Valid(x, y)) {
        continue;
      }
      std::feclearexcept(FE_ALL_EXCEPT);
      double result = gmath_fmod(x, y);
      EXPECT_EQ(Bits(result), row.result) << "mode " << mode;
      EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), 0);
    }
    for (const Row & row : floats) {
      float x = static_cast<float>(Double(row.x));
      float y = static_cast<float>(Double(row.y));
      if (!Valid(x, y)) {
        continue;
      }
      std::feclearexcept(FE_ALL_EXCEPT);
      float result = gmath_fmodf(x, y);
      EXPECT_EQ(Bits(static_cast<double>(result)), row.result)
          << "mode " << mode;
      EXPECT_EQ(std::fetestexcept(FE_ALL_EXCEPT), 0);
    }
  }
}

TEST(Remainder, RandomFiniteInputsAgreeWithHostLibm) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  std::mt19937_64 rng(0x72656d61696e6465ull);
  for (int i = 0; i < 25000; ++i) {
    double x = Double(rng()), y = Double(rng());
    if (Valid(x, y)) {
      EXPECT_EQ(Bits(gmath_fmod(x, y)), Bits(std::fmod(x, y)));
    }
    float xf = Float(static_cast<uint32_t>(rng()));
    float yf = Float(static_cast<uint32_t>(rng()));
    if (Valid(xf, yf)) {
      EXPECT_EQ(Bits(gmath_fmodf(xf, yf)), Bits(std::fmod(xf, yf)));
    }
  }
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
