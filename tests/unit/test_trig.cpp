/**
 * @file
 *
 * gmath_sin, gmath_cos and gmath_tan against the multiple-precision oracle's
 * committed corpus (tests/corpus, written by tools/oracle/gen_corpus.py).
 *
 * The corpus is required: a missing or short file fails, it is never skipped.
 * GMATH_TRIG_CORPUS_DIR points the test at another directory, which
 * `make oracle-fresh` uses for a sample drawn on the day; the committed hash
 * is checked only against the committed corpus.
 *
 * Copyright 2026 by Corey Pennycuff
 */

#include "test_helpers.h"
#include "corpus_hash.h"

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
#include <vector>

namespace {

// The contract is 1 ulp (kContract).  The other bounds are what the kernel
// measures plus a margin, so that a table entry or coefficient that is wrong
// by more than rounding, which is worse than that without being worse than 1,
// still shows.  (One that is wrong by a unit in the last place of a tail
// coefficient moves no result of the corpus by more than a rounding and is
// caught by the committed hash and the table-row test instead; see
// tools/check-planted.py.)
//
// The kernel (a table of sin, cos, tan and cot of the leading six bits of the
// reduced argument and a short correction in double; trig.c) rounds its
// correction, so its results are no longer within 0.50x ulp.  tan, with about
// five roundings in the correction and a division, is the worst.  Measured, in
// ulp of the exact value (story 3a, 2026-10-17):
//
//                                       sin      cos      tan
//   committed corpus (17,580 each)      0.5053   0.5111   0.5254
//   four oracle samples of 120,000 each, uniform +-pi/4, log-uniform
//   2^-28 .. pi/4 and log-uniform 0.8 .. 2^20
//                                       0.5151   0.5154   0.5364
//   six `oracle.py fresh` samples (27,539 entries per function in all)
//                                       0.5051   0.5073   0.5155
//   4.6e8 random arguments, against the previous double-double kernel
//   (accurate to about 2^-64)           0.5234   0.5234   0.5640
//
// kTight is held on the committed corpus, 0.01 above its measured worst case.
// A sample drawn today may hold a new worst case a little above the old ones,
// so it is held to kTightFresh, 0.01 above the worst of everything above (the
// random arguments).  All of these are far below the contract.
constexpr double kContract = 1.0;
constexpr double kTight[3] = {0.5150, 0.5210, 0.5350};       // sin, cos, tan
constexpr double kTightFresh[3] = {0.5350, 0.5350, 0.5750};  // sin, cos, tan

struct Entry {
  uint64_t x;
  uint64_t r;
  double err;
};

double DoubleOf(uint64_t u) {
  double d;
  std::memcpy(&d, &u, sizeof d);
  return d;
}

uint64_t BitsOf(double d) {
  uint64_t u;
  std::memcpy(&u, &d, sizeof u);
  return u;
}

float FloatOf(uint32_t u) {
  float f;
  std::memcpy(&f, &u, sizeof f);
  return f;
}

std::string CorpusDir(bool * committed) {
  const char * env = std::getenv("GMATH_TRIG_CORPUS_DIR");
  *committed = !(env && *env);
  return *committed ? "tests/corpus" : env;
}

std::vector<Entry> Load(const std::string & dir, const char * fn) {
  std::vector<Entry> out;
  std::ifstream in(dir + "/" + fn + ".corpus");
  std::string line;
  while (std::getline(in, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    unsigned long long x, r;
    unsigned e;
    if (std::sscanf(line.c_str(), "%llx %llx %x", &x, &r, &e) != 3) {
      ADD_FAILURE() << "bad corpus line in " << fn << ": " << line;
      continue;
    }
    out.push_back({x, r, static_cast<double>(FloatOf(e))});
  }
  return out;
}

// |y - exact| in units of ulp(exact), given the corpus entry; infinity for a
// result that is not a number where one is expected, or the reverse.
double UlpError(double y, const Entry & e) {
  double r = DoubleOf(e.r);
  if (std::isnan(r)) {
    return std::isnan(y) ? 0.0 : std::numeric_limits<double>::infinity();
  }
  if (std::isnan(y) || std::isinf(y)) {
    return std::numeric_limits<double>::infinity();
  }
  if (r == 0.0) {
    // The exact value is zero only for a zero argument; the sign must agree.
    return BitsOf(y) == e.r ? 0.0 : std::numeric_limits<double>::infinity();
  }
  int exp;
  double m = std::frexp(r, &exp);
  int ue = (exp - 1 < -1022 ? -1022 : exp - 1) - 52;
  // A power of two with the exact value below it: the spacing there is half.
  if (std::fabs(m) == 0.5 && exp - 1 > -1022 && (e.err < 0) == (r > 0)) {
    ue -= 1;
  }
  double u = std::ldexp(1.0, ue);
  return std::fabs((y - r) / u - e.err);
}

using Fn = double (*)(double);

struct Stats {
  size_t entries = 0;
  double max_err = 0;
  uint64_t max_x = 0;
  size_t over = 0;
};

Stats Check(const char * name, Fn f, const std::vector<Entry> & corpus) {
  Stats s;
  for (const Entry & e : corpus) {
    double y = f(DoubleOf(e.x));
    double err = UlpError(y, e);
    s.entries++;
    if (err > s.max_err) {
      s.max_err = err;
      s.max_x = e.x;
    }
    if (err > kContract) {
      if (++s.over <= 5) {
        ADD_FAILURE() << name << "(" << std::hexfloat << DoubleOf(e.x) << ") = " << y
                      << " is " << std::defaultfloat << err
                      << " ulp from the exact value; the correctly rounded result is "
                      << std::hexfloat << DoubleOf(e.r);
      }
    }
  }
  std::printf("  %s: %zu corpus entries, max error %.4f ulp (x = %a)\n", name,
      s.entries, s.max_err, DoubleOf(s.max_x));
  return s;
}

size_t MinEntries() {
  const char * env = std::getenv("GMATH_TRIG_MIN_ENTRIES");
  return env && *env ? std::strtoul(env, nullptr, 10) : 10000;
}

// The `fn NAME HASH COUNT` line of tests/corpus/trig.hash.
bool CommittedHash(const char * name, unsigned long long * hash, unsigned long long * count) {
  std::ifstream in("tests/corpus/trig.hash");
  std::string line;
  while (std::getline(in, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    std::istringstream ls(line);
    std::string key, fname;
    ls >> key >> fname;
    if (key == "fn" && fname == name) {
      ls >> std::hex >> *hash >> std::dec >> *count;
      return true;
    }
  }
  return false;
}

}  // namespace

TEST(Trig, CorpusIsWithinOneUlp) {
  bool committed;
  std::string dir = CorpusDir(&committed);
  const struct {
    const char * name;
    Fn f;
  } fns[] = {{"sin", gmath_sin}, {"cos", gmath_cos}, {"tan", gmath_tan}};
  int fi = -1;
  for (const auto & fn : fns) {
    fi++;
    std::vector<Entry> corpus = Load(dir, fn.name);
    ASSERT_GE(corpus.size(), MinEntries()) << dir << "/" << fn.name << ".corpus is missing or short";
    Stats s = Check(fn.name, fn.f, corpus);
    EXPECT_EQ(s.over, 0u) << fn.name;
    EXPECT_LE(s.max_err, committed ? kTight[fi] : kTightFresh[fi]) << fn.name << " is within the contract but no longer as accurate as it was";
    if (committed) {
      uint64_t hash = GMATH_FNV_BASIS;
      for (const Entry & e : corpus) {
        hash = gmath_fnv_double(hash, fn.f(DoubleOf(e.x)));
      }
      unsigned long long want_hash = 0, want_count = 0;
      ASSERT_TRUE(CommittedHash(fn.name, &want_hash, &want_count)) << "tests/corpus/trig.hash has no line for " << fn.name;
      ASSERT_NE(want_count, 0u) << "tests/corpus/trig.hash is missing or empty";
      EXPECT_EQ(corpus.size(), want_count) << fn.name;
      EXPECT_EQ(hash, want_hash) << "the results of " << fn.name << " over the committed corpus changed";
    }
  }
}

TEST(Trig, ZerosAndSubnormals) {
  EXPECT_EQ(BitsOf(gmath_sin(0.0)), BitsOf(0.0));
  EXPECT_EQ(BitsOf(gmath_sin(-0.0)), BitsOf(-0.0));
  EXPECT_EQ(BitsOf(gmath_tan(0.0)), BitsOf(0.0));
  EXPECT_EQ(BitsOf(gmath_tan(-0.0)), BitsOf(-0.0));
  EXPECT_EQ(gmath_cos(0.0), 1.0);
  EXPECT_EQ(gmath_cos(-0.0), 1.0);
  // The first and last thousand subnormals and the first normals: sin x == x,
  // tan x == x, cos x == 1, with the sign of x.
  std::vector<uint64_t> bits;
  for (uint64_t b = 1; b <= 1000; b++) {
    bits.push_back(b);
  }
  for (uint64_t b = 0x000fffffffffffffull; b > 0x000fffffffffffffull - 1000; b--) {
    bits.push_back(b);
  }
  for (uint64_t b = 0x0010000000000000ull; b < 0x0010000000000000ull + 100; b++) {
    bits.push_back(b);
  }
  for (uint64_t b : bits) {
    for (uint64_t s : {0ull, 0x8000000000000000ull}) {
      double x = DoubleOf(b | s);
      EXPECT_EQ(BitsOf(gmath_sin(x)), BitsOf(x)) << std::hexfloat << x;
      EXPECT_EQ(BitsOf(gmath_tan(x)), BitsOf(x)) << std::hexfloat << x;
      EXPECT_EQ(gmath_cos(x), 1.0) << std::hexfloat << x;
    }
  }
  EXPECT_EQ(gmath_sin(5e-324), 5e-324);
  EXPECT_EQ(gmath_tan(-5e-324), -5e-324);
}

TEST(Trig, NonFiniteGivesTheSameQuietNan) {
  const uint64_t qnan = 0x7ff8000000000000ull;
  const double inf = std::numeric_limits<double>::infinity();
  const double inputs[] = {inf, -inf, DoubleOf(0x7ff8000000000000ull),
      DoubleOf(0xfff8000000000000ull), DoubleOf(0x7ff8000000000123ull),
      DoubleOf(0x7ff0000000000001ull)};
  for (Fn f : {gmath_sin, gmath_cos, gmath_tan}) {
    for (double x : inputs) {
      EXPECT_EQ(BitsOf(f(x)), qnan) << std::hexfloat << x;
    }
  }
}

TEST(Trig, InfinityRaisesInvalid) {
  const double inf = std::numeric_limits<double>::infinity();
  for (Fn f : {gmath_sin, gmath_cos, gmath_tan}) {
    std::feclearexcept(FE_ALL_EXCEPT);
    volatile double y = f(inf);
    (void)y;
    EXPECT_TRUE(std::fetestexcept(FE_INVALID));
  }
}

TEST(Trig, SymmetryIsExact) {
  // sin and tan are odd and cos is even, bit for bit, over a deterministic
  // sweep that reaches every exponent.
  uint64_t s = 0x9e3779b97f4a7c15ull;
  for (int i = 0; i < 20000; i++) {
    s = s * 6364136223846793005ull + 1442695040888963407ull;
    double x = DoubleOf(s & 0x7fffffffffffffffull);
    if (!std::isfinite(x)) {
      continue;
    }
    EXPECT_EQ(BitsOf(gmath_sin(-x)), BitsOf(gmath_sin(x)) ^ 0x8000000000000000ull) << std::hexfloat << x;
    EXPECT_EQ(BitsOf(gmath_tan(-x)), BitsOf(gmath_tan(x)) ^ 0x8000000000000000ull) << std::hexfloat << x;
    EXPECT_EQ(BitsOf(gmath_cos(-x)), BitsOf(gmath_cos(x))) << std::hexfloat << x;
  }
}

TEST(Trig, KnownHardCases) {
  // The double whose reduction is hardest (Muller, Elementary Functions): its
  // cosine is about -4.68716592425462761e-19, which only an exact reduction gets.
  double x = std::ldexp(6381956970095103.0, 797);
  EXPECT_NEAR(gmath_cos(x) / -4.68716592425462761e-19, 1.0, 1e-15);
  EXPECT_NEAR(gmath_sin(x), 1.0, 1e-15);
  // The two doubles either side of pi/4 reduce on different sides of the cut.
  EXPECT_NEAR(gmath_tan(0x1.921fb54442d18p-1), 1.0, 2e-16);
  EXPECT_GT(gmath_tan(std::nextafter(0x1.921fb54442d18p-1, 2.0)), 1.0);
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
