/**
 * @file
 *
 * gmath_atan2, gmath_exp, gmath_log, gmath_pow and gmath_hypot against the
 * multiple-precision oracle's committed corpus (tests/corpus, written by
 * tools/oracle/gen_corpus_elem.py), the special values of C99 Annex F one by
 * one, the exceptions, the exact results, and the symmetries.
 *
 * The corpus is required: a missing or short file fails, it is never skipped.
 * GMATH_TRIG_CORPUS_DIR points the test at another directory, which
 * `make check-oracle-fresh` uses for a sample drawn on the day; the committed
 * hash is checked only against the committed corpus.  (The variable has the
 * name testTrig gave it, and both tests read it.)
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

// The contract is 1 ulp (kContract).  The other bounds are what the functions
// measure plus a margin, so that a table entry or coefficient that is wrong by
// more than rounding, which is worse than that without being worse than 1, still
// shows.  (One that is wrong by a unit in the last place of a tail coefficient
// moves no result of the corpus by more than a rounding and is caught by the
// committed hash and the table tests instead; see tools/check-planted-elem.py.)
//
// The functions are table-driven with a correction in double, so they are not always the correctly
// rounded result.  Measured, in ulp of the exact value (story 4, 2026-10-18; the largest error of
// results of normal size, and on the next line that of results in the subnormal range, which are
// rounded twice (once to 53 bits and once by the scaling):
//
//                                   atan2    exp      log      pow      hypot
//   committed corpus                0.5345   0.5039   0.5048   0.5084   0.5000
//     subnormal results             0.46     0.68     -        0.70     0.50
//   twelve `oracle.py fresh` samples (8,400 .. 10,500 entries each)
//                                   0.5545   0.5028   0.5048   0.5084   0.5000
//     subnormal results             0.47     0.74     -        0.75     0.50
//   150,000 random arguments in each of 4 to 6 distributions per function (seeds 1, 2, 77)
//                                   0.5532   0.5053   0.5051   0.5077   0.5000
//     subnormal results             -        0.75     -        0.74     0.75
//
// kTight is held on the committed corpus, 0.01 above its measured worst case; a sample drawn today may
// hold a new worst case a little above the old ones, so it is held to tight_fresh, 0.01 above the worst
// of all the samples.  The subnormal results are held to 0.76, the 0.75 that two roundings allow; atan2
// and log round once there.  All of these are far below the contract.
constexpr double kContract = 1.0;

// tight, tight_fresh, sub: see the table above.
#define BOUNDS_ATAN2 {0.545, 0.565, 0.51}
#define BOUNDS_EXP {0.514, 0.516, 0.76}
#define BOUNDS_LOG {0.515, 0.516, 0.51}
#define BOUNDS_POW {0.518, 0.518, 0.76}
#define BOUNDS_HYPOT {0.505, 0.505, 0.76}

struct Bounds {
  double tight;        // the committed corpus, results of normal size
  double tight_fresh;  // a sample drawn on the day, and every other sample
  double sub;          // results that are subnormal (the scaling rounds a second time)
};

struct Entry {
  uint64_t a;
  uint64_t b;  // the second argument; 0 for the functions of one
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

const uint64_t kQNaN = 0x7ff8000000000000ull;
const double kInf = std::numeric_limits<double>::infinity();
const double kNaN = std::numeric_limits<double>::quiet_NaN();

std::string CorpusDir(bool * committed) {
  const char * env = std::getenv("GMATH_TRIG_CORPUS_DIR");
  *committed = !(env && *env);
  return *committed ? "tests/corpus" : env;
}

std::vector<Entry> Load(const std::string & dir, const char * fn, int arity) {
  std::vector<Entry> out;
  std::ifstream in(dir + "/" + fn + ".corpus");
  std::string line;
  while (std::getline(in, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    unsigned long long a, b = 0, r;
    unsigned e;
    int got = arity == 1 ? std::sscanf(line.c_str(), "%llx %llx %x", &a, &r, &e)
                         : std::sscanf(line.c_str(), "%llx %llx %llx %x", &a, &b, &r, &e);
    if (got != arity + 2) {
      ADD_FAILURE() << "bad corpus line in " << fn << ": " << line;
      continue;
    }
    out.push_back({a, b, r, static_cast<double>(FloatOf(e))});
  }
  return out;
}

// |y - exact| in units of ulp(exact), given the corpus entry; infinity for a
// result that is not a number where one is expected, or the reverse.  An
// expected infinity or zero must be matched exactly (sign included).
double UlpError(double y, const Entry & e) {
  double r = DoubleOf(e.r);
  if (std::isnan(r)) {
    return (std::isnan(y) && BitsOf(y) == kQNaN) ? 0.0 : std::numeric_limits<double>::infinity();
  }
  if (std::isnan(y)) {
    return std::numeric_limits<double>::infinity();
  }
  if (r == 0.0 || std::isinf(r)) {
    return BitsOf(y) == e.r ? 0.0 : std::numeric_limits<double>::infinity();
  }
  if (std::isinf(y)) {
    return std::numeric_limits<double>::infinity();
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

struct Fn {
  const char * name;
  int arity;
  double (*f1)(double);
  double (*f2)(double, double);
  Bounds bounds;
};

double Call(const Fn & f, const Entry & e) {
  return f.arity == 1 ? f.f1(DoubleOf(e.a)) : f.f2(DoubleOf(e.a), DoubleOf(e.b));
}

struct Stats {
  size_t entries = 0;
  double max_err = 0;
  double max_sub = 0;
  uint64_t max_a = 0, max_b = 0;
  size_t over = 0;
};

Stats Check(const Fn & f, const std::vector<Entry> & corpus) {
  Stats s;
  for (const Entry & e : corpus) {
    double y = Call(f, e);
    double err = UlpError(y, e);
    s.entries++;
    double r = DoubleOf(e.r);
    bool sub = r != 0.0 && std::isfinite(r) && std::fabs(r) < std::numeric_limits<double>::min();
    if (sub) {
      if (err > s.max_sub) {
        s.max_sub = err;
      }
    } else if (err > s.max_err) {
      s.max_err = err;
      s.max_a = e.a;
      s.max_b = e.b;
    }
    if (err > kContract) {
      if (++s.over <= 5) {
        ADD_FAILURE() << f.name << "(" << std::hexfloat << DoubleOf(e.a) << (f.arity == 2 ? ", " : "")
                      << (f.arity == 2 ? DoubleOf(e.b) : 0.0) << ") = " << y << " is " << std::defaultfloat << err
                      << " ulp from the exact value; the correctly rounded result is " << std::hexfloat << r;
      }
    }
  }
  std::printf("  %s: %zu corpus entries, max error %.4f ulp (a = %a, b = %a), subnormal results %.4f\n", f.name,
      s.entries, s.max_err, DoubleOf(s.max_a), DoubleOf(s.max_b), s.max_sub);
  return s;
}

size_t MinEntries() {
  const char * env = std::getenv("GMATH_TRIG_MIN_ENTRIES");
  return env && *env ? std::strtoul(env, nullptr, 10) : 1000;
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

namespace {

const Fn kFns[] = {
  {"atan2", 2, nullptr, gmath_atan2, BOUNDS_ATAN2},
  {"exp", 1, gmath_exp, nullptr, BOUNDS_EXP},
  {"log", 1, gmath_log, nullptr, BOUNDS_LOG},
  {"pow", 2, nullptr, gmath_pow, BOUNDS_POW},
  {"hypot", 2, nullptr, gmath_hypot, BOUNDS_HYPOT},
};

}  // namespace

TEST(Elementary, CorpusIsWithinOneUlp) {
  bool committed;
  std::string dir = CorpusDir(&committed);
  for (const Fn & f : kFns) {
    std::vector<Entry> corpus = Load(dir, f.name, f.arity);
    ASSERT_GE(corpus.size(), MinEntries()) << dir << "/" << f.name << ".corpus is missing or short";
    Stats s = Check(f, corpus);
    EXPECT_EQ(s.over, 0u) << f.name;
    EXPECT_LE(s.max_err, committed ? f.bounds.tight : f.bounds.tight_fresh)
        << f.name << " is within the contract but no longer as accurate as it was";
    EXPECT_LE(s.max_sub, f.bounds.sub) << f.name << ": results in the subnormal range";
    if (committed) {
      uint64_t hash = GMATH_FNV_BASIS;
      for (const Entry & e : corpus) {
        hash = gmath_fnv_double(hash, Call(f, e));
      }
      unsigned long long want_hash = 0, want_count = 0;
      ASSERT_TRUE(CommittedHash(f.name, &want_hash, &want_count)) << "tests/corpus/trig.hash has no line for " << f.name;
      ASSERT_NE(want_count, 0u) << "tests/corpus/trig.hash is missing or empty";
      EXPECT_EQ(corpus.size(), want_count) << f.name;
      EXPECT_EQ(hash, want_hash) << "the results of " << f.name << " over the committed corpus changed";
    }
  }
}

namespace {

::testing::AssertionResult SameBits(double got, double want) {
  if (BitsOf(got) == BitsOf(want)) {
    return ::testing::AssertionSuccess();
  }
  return ::testing::AssertionFailure() << std::hexfloat << "got " << got << " (0x" << std::hex << BitsOf(got)
                                       << "), want " << std::hexfloat << want << " (0x" << std::hex << BitsOf(want) << ")";
}

#define EXPECT_BITS(got, want) EXPECT_TRUE(SameBits((got), (want)))

const double kPi = 0x1.921fb54442d18p+1;
const double kPi2 = 0x1.921fb54442d18p+0;
const double kPi4 = 0x1.921fb54442d18p-1;
const double k3Pi4 = 0x1.2d97c7f3321d2p+1;
const double kMin = std::numeric_limits<double>::min();
const double kMax = std::numeric_limits<double>::max();
const double kDenorm = std::numeric_limits<double>::denorm_min();

struct Flags {
  Flags() { std::feclearexcept(FE_ALL_EXCEPT); }
  bool Raised(int f) const { return std::fetestexcept(f) != 0; }
};

}  // namespace

TEST(Elementary, Atan2QuadrantsAndSignedZeros) {
  // C99 F.9.1.4, row by row.
  EXPECT_BITS(gmath_atan2(0.0, 0.0), 0.0);
  EXPECT_BITS(gmath_atan2(-0.0, 0.0), -0.0);
  EXPECT_BITS(gmath_atan2(0.0, -0.0), kPi);
  EXPECT_BITS(gmath_atan2(-0.0, -0.0), -kPi);
  EXPECT_BITS(gmath_atan2(0.0, 1.0), 0.0);
  EXPECT_BITS(gmath_atan2(-0.0, 1.0), -0.0);
  EXPECT_BITS(gmath_atan2(0.0, -1.0), kPi);
  EXPECT_BITS(gmath_atan2(-0.0, -1.0), -kPi);
  EXPECT_BITS(gmath_atan2(0.0, kDenorm), 0.0);
  EXPECT_BITS(gmath_atan2(-0.0, -kDenorm), -kPi);
  EXPECT_BITS(gmath_atan2(1.0, 0.0), kPi2);
  EXPECT_BITS(gmath_atan2(1.0, -0.0), kPi2);
  EXPECT_BITS(gmath_atan2(-1.0, 0.0), -kPi2);
  EXPECT_BITS(gmath_atan2(-1.0, -0.0), -kPi2);
  EXPECT_BITS(gmath_atan2(kDenorm, 0.0), kPi2);
  EXPECT_BITS(gmath_atan2(1.0, kInf), 0.0);
  EXPECT_BITS(gmath_atan2(-1.0, kInf), -0.0);
  EXPECT_BITS(gmath_atan2(1.0, -kInf), kPi);
  EXPECT_BITS(gmath_atan2(-1.0, -kInf), -kPi);
  EXPECT_BITS(gmath_atan2(kInf, 1.0), kPi2);
  EXPECT_BITS(gmath_atan2(-kInf, 1.0), -kPi2);
  EXPECT_BITS(gmath_atan2(kInf, -1.0), kPi2);
  EXPECT_BITS(gmath_atan2(kInf, 0.0), kPi2);
  EXPECT_BITS(gmath_atan2(kInf, kInf), kPi4);
  EXPECT_BITS(gmath_atan2(-kInf, kInf), -kPi4);
  EXPECT_BITS(gmath_atan2(kInf, -kInf), k3Pi4);
  EXPECT_BITS(gmath_atan2(-kInf, -kInf), -k3Pi4);
  // The four quadrants of the unit diagonal.
  EXPECT_BITS(gmath_atan2(1.0, 1.0), kPi4);
  EXPECT_BITS(gmath_atan2(1.0, -1.0), k3Pi4);
  EXPECT_BITS(gmath_atan2(-1.0, -1.0), -k3Pi4);
  EXPECT_BITS(gmath_atan2(-1.0, 1.0), -kPi4);
  // Extreme ratios: past the range of the doubles, the angle is the axis (or the
  // axis less a zero's worth).
  EXPECT_BITS(gmath_atan2(kDenorm, kMax), 0.0);
  EXPECT_BITS(gmath_atan2(-kDenorm, kMax), -0.0);
  EXPECT_BITS(gmath_atan2(kDenorm, -kMax), kPi);
  EXPECT_BITS(gmath_atan2(kMax, kDenorm), kPi2);
  EXPECT_BITS(gmath_atan2(-kMax, -kDenorm), -kPi2);
  EXPECT_BITS(gmath_atan2(kDenorm, kDenorm), kPi4);
  EXPECT_BITS(gmath_atan2(kDenorm, 1.0), kDenorm);
  EXPECT_BITS(gmath_atan2(-kDenorm, 1.0), -kDenorm);
  EXPECT_BITS(gmath_atan2(kMax, kMax), kPi4);
  EXPECT_BITS(gmath_atan2(kMin, kMin), kPi4);
  EXPECT_BITS(gmath_atan2(1e-300, 1e300), 0.0);
  EXPECT_BITS(gmath_atan2(1e300, 1e-300), kPi2);
  // NaN in either argument.
  EXPECT_BITS(gmath_atan2(kNaN, 1.0), DoubleOf(kQNaN));
  EXPECT_BITS(gmath_atan2(1.0, kNaN), DoubleOf(kQNaN));
  EXPECT_BITS(gmath_atan2(kNaN, kNaN), DoubleOf(kQNaN));
  EXPECT_BITS(gmath_atan2(kInf, kNaN), DoubleOf(kQNaN));
  EXPECT_BITS(gmath_atan2(DoubleOf(0xfff8000000000123ull), 0.0), DoubleOf(kQNaN));
  EXPECT_BITS(gmath_atan2(0.0, DoubleOf(0x7ff0000000000001ull)), DoubleOf(kQNaN));
}

TEST(Elementary, Atan2IsOddInYAndTheMirrorAcrossTheAxes) {
  uint64_t s = 0x2545f4914f6cdd1dull;
  for (int i = 0; i < 20000; i++) {
    s = s * 6364136223846793005ull + 1442695040888963407ull;
    uint64_t t = s * 0x9e3779b97f4a7c15ull;
    double y = DoubleOf(s & 0x7fffffffffffffffull);
    double x = DoubleOf(t & 0x7fffffffffffffffull);
    if (!std::isfinite(x) || !std::isfinite(y)) {
      continue;
    }
    double a = gmath_atan2(y, x);
    EXPECT_BITS(gmath_atan2(-y, x), -a);
    EXPECT_BITS(gmath_atan2(-y, -x), -gmath_atan2(y, -x));
    // atan2(y, x) + atan2(y, -x) is pi to rounding, so the reflection is the table's, not a drift.
    EXPECT_NEAR(a + gmath_atan2(y, -x), kPi, 6e-16) << std::hexfloat << y << " " << x;
    // Within the first quadrant atan2(y, x) + atan2(x, y) = pi/2.
    EXPECT_NEAR(a + gmath_atan2(x, y), kPi2, 3e-16) << std::hexfloat << y << " " << x;
  }
}

TEST(Elementary, ExpSpecialValuesOverflowUnderflowAndSubnormals) {
  EXPECT_BITS(gmath_exp(0.0), 1.0);
  EXPECT_BITS(gmath_exp(-0.0), 1.0);
  EXPECT_BITS(gmath_exp(kInf), kInf);
  EXPECT_BITS(gmath_exp(-kInf), 0.0);
  EXPECT_BITS(gmath_exp(kNaN), DoubleOf(kQNaN));
  EXPECT_BITS(gmath_exp(DoubleOf(0x7ff0000000000001ull)), DoubleOf(kQNaN));
  EXPECT_BITS(gmath_exp(DoubleOf(0xfff8000000000042ull)), DoubleOf(kQNaN));
  // exp 1 is e, correctly rounded here (the result is a quarter of an ulp from the double).
  EXPECT_NEAR(gmath_exp(1.0), 2.718281828459045, 1e-15);
  EXPECT_BITS(gmath_exp(kDenorm), 1.0);
  EXPECT_BITS(gmath_exp(-kDenorm), 1.0);
  EXPECT_BITS(gmath_exp(0x1p-54), 1.0);
  EXPECT_BITS(gmath_exp(-0x1p-54), 1.0);
  EXPECT_BITS(gmath_exp(0x1p-52), 1.0 + 0x1p-52);
  // The overflow threshold: the largest x with a finite result, and the next double.
  const double over = 0x1.62e42fefa39efp+9;
  EXPECT_TRUE(std::isfinite(gmath_exp(over)));
  EXPECT_GT(gmath_exp(over), 1.79769e308);
  EXPECT_BITS(gmath_exp(std::nextafter(over, kInf)), kInf);
  EXPECT_BITS(gmath_exp(710.0), kInf);
  EXPECT_BITS(gmath_exp(1e300), kInf);
  EXPECT_BITS(gmath_exp(kMax), kInf);
  // The underflow threshold: the least x with a result above zero, and the double below it.
  const double under = -0x1.74910d52d3051p+9;
  EXPECT_BITS(gmath_exp(under), kDenorm);
  EXPECT_BITS(gmath_exp(std::nextafter(under, -kInf)), 0.0);
  EXPECT_BITS(gmath_exp(-746.0), 0.0);
  EXPECT_BITS(gmath_exp(-1e300), 0.0);
  EXPECT_BITS(gmath_exp(-kMax), 0.0);
  // The boundary of the normals: ln(2^-1022) is -708.396418532264; below it the result is subnormal.
  EXPECT_GE(gmath_exp(-708.39), kMin);
  EXPECT_LT(gmath_exp(-708.4), kMin);
  EXPECT_GT(gmath_exp(-708.4), 0.0);
  EXPECT_LT(gmath_exp(-720.0), kMin);
  EXPECT_GT(gmath_exp(-744.0), 0.0);
  // Monotone through the subnormals.
  double prev = gmath_exp(-708.0);
  for (double x = -708.0; x > -745.2; x -= 0.01) {
    double y = gmath_exp(x);
    EXPECT_LE(y, prev) << x;
    prev = y;
  }
}

TEST(Elementary, ExpExceptions) {
  for (double x : {709.8, 710.0, 711.0, 1000.0, 1e300, kMax}) {
    Flags f;
    volatile double y = gmath_exp(x);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_OVERFLOW)) << x;
    EXPECT_TRUE(f.Raised(FE_INEXACT)) << x;
  }
  for (double x : {-745.2, -746.0, -747.0, -1000.0, -1e300, -kMax}) {
    Flags f;
    volatile double y = gmath_exp(x);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_UNDERFLOW)) << x;
    EXPECT_TRUE(f.Raised(FE_INEXACT)) << x;
  }
  {
    Flags f;
    volatile double y = gmath_exp(-740.0);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_UNDERFLOW));
  }
  {
    Flags f;
    volatile double y = gmath_exp(1.0);
    (void)y;
    EXPECT_FALSE(f.Raised(FE_OVERFLOW));
    EXPECT_FALSE(f.Raised(FE_UNDERFLOW));
    EXPECT_FALSE(f.Raised(FE_DIVBYZERO));
    EXPECT_FALSE(f.Raised(FE_INVALID));
  }
  {
    Flags f;
    volatile double y = gmath_exp(kInf);
    (void)y;
    EXPECT_FALSE(f.Raised(FE_OVERFLOW));
    EXPECT_FALSE(f.Raised(FE_INVALID));
  }
  {
    Flags f;
    volatile double y = gmath_exp(0.0);
    (void)y;
    EXPECT_FALSE(f.Raised(FE_INEXACT));
  }
  {
    Flags f;
    volatile double y = gmath_exp(DoubleOf(0x7ff0000000000001ull));
    (void)y;
    EXPECT_TRUE(f.Raised(FE_INVALID));
  }
}

TEST(Elementary, LogSpecialValuesAndExceptions) {
  EXPECT_BITS(gmath_log(1.0), 0.0);
  EXPECT_BITS(gmath_log(0.0), -kInf);
  EXPECT_BITS(gmath_log(-0.0), -kInf);
  EXPECT_BITS(gmath_log(kInf), kInf);
  EXPECT_BITS(gmath_log(-kInf), DoubleOf(kQNaN));
  EXPECT_BITS(gmath_log(-1.0), DoubleOf(kQNaN));
  EXPECT_BITS(gmath_log(-kDenorm), DoubleOf(kQNaN));
  EXPECT_BITS(gmath_log(-kMax), DoubleOf(kQNaN));
  EXPECT_BITS(gmath_log(kNaN), DoubleOf(kQNaN));
  EXPECT_BITS(gmath_log(DoubleOf(0xfff8000000000042ull)), DoubleOf(kQNaN));
  {
    Flags f;
    volatile double y = gmath_log(0.0);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_DIVBYZERO));
    EXPECT_FALSE(f.Raised(FE_INVALID));
  }
  {
    Flags f;
    volatile double y = gmath_log(-2.0);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_INVALID));
    EXPECT_FALSE(f.Raised(FE_DIVBYZERO));
  }
  {
    Flags f;
    volatile double y = gmath_log(2.0);
    (void)y;
    EXPECT_FALSE(f.Raised(FE_INVALID));
    EXPECT_FALSE(f.Raised(FE_DIVBYZERO));
    EXPECT_FALSE(f.Raised(FE_OVERFLOW));
    EXPECT_FALSE(f.Raised(FE_UNDERFLOW));
  }
  // Subnormals and the extremes have ordinary logarithms.
  EXPECT_NEAR(gmath_log(kDenorm), -744.4400719213812, 1e-12);
  EXPECT_NEAR(gmath_log(kMax), 709.782712893384, 1e-12);
  EXPECT_NEAR(gmath_log(kMin), -708.3964185322641, 1e-12);
  // Near 1 the result keeps its relative accuracy: log(1 + 2^-52) is 2^-52 less a hair.
  EXPECT_BITS(gmath_log(1.0 + 0x1p-52), 0x1.fffffffffffffp-53);
  EXPECT_BITS(gmath_log(1.0 - 0x1p-53), -0x1p-53);
  EXPECT_LT(gmath_log(std::nextafter(1.0, 0.0)), 0.0);
  EXPECT_GT(gmath_log(std::nextafter(1.0, 2.0)), 0.0);
  // log of a power of two is k ln2 to 1 ulp, and exactly odd-symmetric.
  for (int k = -1074; k <= 1023; k++) {
    double x = std::ldexp(1.0, k);
    double y = gmath_log(x);
    if (k != 0) {
      EXPECT_NEAR(y / (k * 0.6931471805599453), 1.0, 4e-16) << k;
    }
    if (k > 0 && k <= 1022) {
      EXPECT_BITS(gmath_log(std::ldexp(1.0, -k)), -gmath_log(std::ldexp(1.0, k)));
    }
  }
}

TEST(Elementary, ExpAndLogAreInversesToAFewUlp) {
  uint64_t s = 0x9e3779b97f4a7c15ull;
  for (int i = 0; i < 20000; i++) {
    s = s * 6364136223846793005ull + 1442695040888963407ull;
    double x = (static_cast<double>(s >> 11) * 0x1p-53 * 2 - 1) * 700.0;
    double back = gmath_log(gmath_exp(x));
    EXPECT_NEAR(back, x, 4e-16 * std::fabs(x) + 4e-16) << x;
  }
}

TEST(Elementary, PowSpecialValues) {
  // C99 F.9.4.4, row by row.
  const double nan_ = DoubleOf(kQNaN);
  // pow(x, +-0) = 1 and pow(+1, y) = 1 for any x and y, a NaN included.
  for (double x : {0.0, -0.0, 1.0, -1.0, 2.0, -2.5, kInf, -kInf, kNaN, kMax, kDenorm}) {
    EXPECT_BITS(gmath_pow(x, 0.0), 1.0);
    EXPECT_BITS(gmath_pow(x, -0.0), 1.0);
  }
  for (double y : {0.0, -0.0, 1.0, -1.0, 2.5, -2.5, kInf, -kInf, kNaN, kMax, kDenorm}) {
    EXPECT_BITS(gmath_pow(1.0, y), 1.0);
  }
  EXPECT_BITS(gmath_pow(-1.0, kInf), 1.0);
  EXPECT_BITS(gmath_pow(-1.0, -kInf), 1.0);
  EXPECT_BITS(gmath_pow(kNaN, 1.0), nan_);
  EXPECT_BITS(gmath_pow(2.0, kNaN), nan_);
  EXPECT_BITS(gmath_pow(kNaN, kNaN), nan_);
  EXPECT_BITS(gmath_pow(-1.0, kNaN), nan_);
  EXPECT_BITS(gmath_pow(kNaN, -1.0), nan_);
  // pow(+-0, y)
  EXPECT_BITS(gmath_pow(0.0, -1.0), kInf);
  EXPECT_BITS(gmath_pow(-0.0, -1.0), -kInf);
  EXPECT_BITS(gmath_pow(0.0, -3.0), kInf);
  EXPECT_BITS(gmath_pow(-0.0, -3.0), -kInf);
  EXPECT_BITS(gmath_pow(0.0, -2.0), kInf);
  EXPECT_BITS(gmath_pow(-0.0, -2.0), kInf);
  EXPECT_BITS(gmath_pow(0.0, -0.5), kInf);
  EXPECT_BITS(gmath_pow(-0.0, -0.5), kInf);
  EXPECT_BITS(gmath_pow(-0.0, -kInf), kInf);
  EXPECT_BITS(gmath_pow(0.0, -kInf), kInf);
  EXPECT_BITS(gmath_pow(0.0, 1.0), 0.0);
  EXPECT_BITS(gmath_pow(-0.0, 1.0), -0.0);
  EXPECT_BITS(gmath_pow(-0.0, 3.0), -0.0);
  EXPECT_BITS(gmath_pow(-0.0, 2.0), 0.0);
  EXPECT_BITS(gmath_pow(-0.0, 0.5), 0.0);
  EXPECT_BITS(gmath_pow(0.0, 2.0), 0.0);
  EXPECT_BITS(gmath_pow(-0.0, kInf), 0.0);
  EXPECT_BITS(gmath_pow(-0.0, 9007199254740991.0), -0.0);
  EXPECT_BITS(gmath_pow(-0.0, 9007199254740992.0), 0.0);
  EXPECT_BITS(gmath_pow(-0.0, -9007199254740991.0), -kInf);
  // pow(+-inf, y)
  EXPECT_BITS(gmath_pow(kInf, 1.0), kInf);
  EXPECT_BITS(gmath_pow(kInf, -1.0), 0.0);
  EXPECT_BITS(gmath_pow(kInf, kInf), kInf);
  EXPECT_BITS(gmath_pow(kInf, -kInf), 0.0);
  EXPECT_BITS(gmath_pow(-kInf, 3.0), -kInf);
  EXPECT_BITS(gmath_pow(-kInf, 2.0), kInf);
  EXPECT_BITS(gmath_pow(-kInf, 0.5), kInf);
  EXPECT_BITS(gmath_pow(-kInf, -3.0), -0.0);
  EXPECT_BITS(gmath_pow(-kInf, -2.0), 0.0);
  EXPECT_BITS(gmath_pow(-kInf, -0.5), 0.0);
  EXPECT_BITS(gmath_pow(-kInf, kInf), kInf);
  EXPECT_BITS(gmath_pow(-kInf, -kInf), 0.0);
  // pow(x, +-inf)
  EXPECT_BITS(gmath_pow(0.5, kInf), 0.0);
  EXPECT_BITS(gmath_pow(-0.5, kInf), 0.0);
  EXPECT_BITS(gmath_pow(2.0, kInf), kInf);
  EXPECT_BITS(gmath_pow(-2.0, kInf), kInf);
  EXPECT_BITS(gmath_pow(0.5, -kInf), kInf);
  EXPECT_BITS(gmath_pow(-0.5, -kInf), kInf);
  EXPECT_BITS(gmath_pow(2.0, -kInf), 0.0);
  EXPECT_BITS(gmath_pow(-2.0, -kInf), 0.0);
  EXPECT_BITS(gmath_pow(kDenorm, -kInf), kInf);
  EXPECT_BITS(gmath_pow(kMax, kInf), kInf);
  // a finite negative x and a finite non-integer y
  EXPECT_BITS(gmath_pow(-2.0, 0.5), nan_);
  EXPECT_BITS(gmath_pow(-2.0, -0.5), nan_);
  EXPECT_BITS(gmath_pow(-0.5, 1.5), nan_);
  EXPECT_BITS(gmath_pow(-kDenorm, 0.1), nan_);
  EXPECT_BITS(gmath_pow(-kMax, 1e-300), nan_);
  // a finite negative x and an integer y: the sign follows the parity, up to and past 2^53
  EXPECT_BITS(gmath_pow(-2.0, 3.0), -8.0);
  EXPECT_BITS(gmath_pow(-2.0, 2.0), 4.0);
  EXPECT_BITS(gmath_pow(-2.0, -3.0), -0.125);
  EXPECT_BITS(gmath_pow(-1.0, 9007199254740991.0), -1.0);
  EXPECT_BITS(gmath_pow(-1.0, 9007199254740992.0), 1.0);
  EXPECT_BITS(gmath_pow(-1.0, 1e300), 1.0);
  EXPECT_BITS(gmath_pow(-1.0, -9007199254740991.0), -1.0);
  EXPECT_BITS(gmath_pow(-1.0, 0.5), nan_);
  EXPECT_BITS(gmath_pow(-0.5, 9007199254740991.0), -0.0);
  EXPECT_BITS(gmath_pow(-0.5, 1e300), 0.0);
  EXPECT_BITS(gmath_pow(-2.0, 1e300), kInf);
  EXPECT_BITS(gmath_pow(-2.0, 1025.0), -kInf);
  EXPECT_BITS(gmath_pow(-2.0, 1024.0), kInf);
  EXPECT_BITS(gmath_pow(-2.0, -1075.0), -0.0);
  EXPECT_BITS(gmath_pow(-2.0, -1076.0), 0.0);
  // overflow, underflow and the subnormals
  EXPECT_BITS(gmath_pow(2.0, 1024.0), kInf);
  EXPECT_BITS(gmath_pow(2.0, 1023.0), 0x1p1023);
  EXPECT_BITS(gmath_pow(2.0, -1074.0), kDenorm);
  EXPECT_BITS(gmath_pow(2.0, -1075.0), 0.0);
  EXPECT_BITS(gmath_pow(2.0, -1022.0), kMin);
  EXPECT_NEAR(gmath_pow(10.0, 308.0) / 1e308, 1.0, 3e-16);
  EXPECT_BITS(gmath_pow(10.0, 309.0), kInf);
  EXPECT_BITS(gmath_pow(10.0, -323.0), 9.88131291682493e-324);
  EXPECT_BITS(gmath_pow(10.0, -400.0), 0.0);
  EXPECT_BITS(gmath_pow(kMax, 2.0), kInf);
  EXPECT_BITS(gmath_pow(kMax, 1.0), kMax);
  EXPECT_BITS(gmath_pow(kDenorm, 2.0), 0.0);
  EXPECT_BITS(gmath_pow(kDenorm, 0.5), 2.2227587494850775e-162);
  // huge exponents
  EXPECT_BITS(gmath_pow(1.0 + 0x1p-52, 1e300), kInf);
  EXPECT_BITS(gmath_pow(1.0 + 0x1p-52, -1e300), 0.0);
  EXPECT_BITS(gmath_pow(1.0 - 0x1p-53, 1e300), 0.0);
  EXPECT_BITS(gmath_pow(1.0 - 0x1p-53, -1e300), kInf);
  EXPECT_BITS(gmath_pow(0.5, kMax), 0.0);
  EXPECT_BITS(gmath_pow(2.0, kMax), kInf);
  EXPECT_BITS(gmath_pow(2.0, -kMax), 0.0);
  EXPECT_BITS(gmath_pow(1.5, 0x1p64), kInf);
  EXPECT_BITS(gmath_pow(0.75, 0x1p64), 0.0);
  // tiny exponents give 1
  EXPECT_BITS(gmath_pow(2.0, kDenorm), 1.0);
  EXPECT_BITS(gmath_pow(kMax, 0x1p-60), 1.0 + 3 * 0x1p-52);
}

TEST(Elementary, PowExceptions) {
  {
    Flags f;
    volatile double y = gmath_pow(0.0, -1.0);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_DIVBYZERO));
  }
  {
    Flags f;
    volatile double y = gmath_pow(-0.0, -3.0);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_DIVBYZERO));
  }
  {
    Flags f;
    volatile double y = gmath_pow(-2.0, 0.5);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_INVALID));
  }
  {
    Flags f;
    volatile double y = gmath_pow(2.0, 1024.0);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_OVERFLOW));
  }
  {
    Flags f;
    volatile double y = gmath_pow(2.0, -1076.0);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_UNDERFLOW));
  }
  {
    Flags f;
    volatile double y = gmath_pow(1.0 + 0x1p-52, 1e300);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_OVERFLOW));
  }
  // an exponent too large to multiply: the answer is the overflow or the underflow and nothing else
  for (double x : {0x1p-100, 0.5, 1e-100}) {
    Flags f;
    volatile double y = gmath_pow(x, kMax);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_UNDERFLOW)) << x;
    EXPECT_FALSE(f.Raised(FE_OVERFLOW)) << x;
    EXPECT_FALSE(f.Raised(FE_INVALID)) << x;
  }
  for (double x : {0x1p100, 2.0, 1e100}) {
    Flags f;
    volatile double y = gmath_pow(x, kMax);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_OVERFLOW)) << x;
    EXPECT_FALSE(f.Raised(FE_UNDERFLOW)) << x;
    EXPECT_FALSE(f.Raised(FE_INVALID)) << x;
  }
  {
    Flags f;
    volatile double y = gmath_pow(0.0, -kInf);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_DIVBYZERO));
  }
  {
    Flags f;
    volatile double y = gmath_pow(-0.0, -kInf);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_DIVBYZERO));
  }
  {
    Flags f;
    volatile double y = gmath_pow(1.0, kNaN);
    (void)y;
    EXPECT_FALSE(f.Raised(FE_INVALID));
  }
  {
    Flags f;
    volatile double y = gmath_pow(3.0, 2.0);
    (void)y;
    EXPECT_FALSE(f.Raised(FE_INVALID));
    EXPECT_FALSE(f.Raised(FE_DIVBYZERO));
    EXPECT_FALSE(f.Raised(FE_OVERFLOW));
    EXPECT_FALSE(f.Raised(FE_UNDERFLOW));
  }
  {
    Flags f;
    volatile double y = gmath_pow(0.0, 2.0);
    (void)y;
    EXPECT_FALSE(f.Raised(FE_DIVBYZERO));
  }
}

TEST(Elementary, PowExactResultsAreExact) {
  // An exactly representable result must come back exactly: the error is below 0.55 ulp, and the
  // neighbours of a representable value are a whole ulp (half an ulp below a power of two) away.
  for (int k = -1074; k <= 1023; k++) {
    EXPECT_BITS(gmath_pow(2.0, k), std::ldexp(1.0, k));
    EXPECT_BITS(gmath_pow(0.5, -k), std::ldexp(1.0, k));
  }
  double p3 = 1.0;
  double p5 = 1.0;
  double p10 = 1.0;
  double p7 = 1.0;
  for (int k = 0; k <= 33; k++) {  // 3^33 < 2^53.2: exact up to 3^33
    if (k <= 33) {
      EXPECT_BITS(gmath_pow(3.0, k), p3) << k;
      EXPECT_BITS(gmath_pow(-3.0, k), (k & 1) ? -p3 : p3) << k;
    }
    if (k <= 22) {
      EXPECT_BITS(gmath_pow(5.0, k), p5) << k;
      EXPECT_BITS(gmath_pow(10.0, k), p10) << k;
    }
    if (k <= 18) {
      EXPECT_BITS(gmath_pow(7.0, k), p7) << k;
    }
    p3 *= 3.0;
    p5 *= 5.0;
    p10 *= 10.0;
    p7 *= 7.0;
  }
  // squares and other small powers of representable numbers
  uint64_t s = 0x2545f4914f6cdd1dull;
  for (int i = 0; i < 2000; i++) {
    s = s * 6364136223846793005ull + 1442695040888963407ull;
    double x = static_cast<double>((s >> 38) | 1);  // an odd integer below 2^26
    EXPECT_BITS(gmath_pow(x, 2.0), x * x) << x;
    EXPECT_BITS(gmath_pow(x, 1.0), x) << x;
    EXPECT_BITS(gmath_pow(x * x, 0.5), x) << x;
  }
  EXPECT_BITS(gmath_pow(1.5, 2.0), 2.25);
  EXPECT_BITS(gmath_pow(0.25, 0.5), 0.5);
  EXPECT_BITS(gmath_pow(4.0, 0.5), 2.0);
  EXPECT_BITS(gmath_pow(4.0, 1.5), 8.0);
  EXPECT_BITS(gmath_pow(1e10, 2.0), 1e20);
  EXPECT_BITS(gmath_pow(2.0, 0.5), 1.4142135623730951);
}

TEST(Elementary, HypotSpecialValues) {
  const double nan_ = DoubleOf(kQNaN);
  EXPECT_BITS(gmath_hypot(0.0, 0.0), 0.0);
  EXPECT_BITS(gmath_hypot(-0.0, -0.0), 0.0);
  EXPECT_BITS(gmath_hypot(-0.0, 0.0), 0.0);
  EXPECT_BITS(gmath_hypot(3.0, -0.0), 3.0);
  EXPECT_BITS(gmath_hypot(-0.0, -4.5), 4.5);
  EXPECT_BITS(gmath_hypot(kDenorm, 0.0), kDenorm);
  EXPECT_BITS(gmath_hypot(-kMax, 0.0), kMax);
  // infinity beats NaN, in either argument and with either sign
  for (double inf : {kInf, -kInf}) {
    for (double y : {0.0, -0.0, 1.0, -7.5, kMax, kDenorm, kInf, -kInf, kNaN, DoubleOf(0x7ff0000000000001ull),
             DoubleOf(0xfff8000000000042ull)}) {
      EXPECT_BITS(gmath_hypot(inf, y), kInf);
      EXPECT_BITS(gmath_hypot(y, inf), kInf);
    }
  }
  EXPECT_BITS(gmath_hypot(kNaN, 1.0), nan_);
  EXPECT_BITS(gmath_hypot(1.0, kNaN), nan_);
  EXPECT_BITS(gmath_hypot(kNaN, kNaN), nan_);
  EXPECT_BITS(gmath_hypot(kNaN, 0.0), nan_);
  EXPECT_BITS(gmath_hypot(DoubleOf(0xfff8000000000042ull), 3.0), nan_);
  // Pythagorean triples, scaled by powers of two, are exact.
  const int triples[][3] = {{3, 4, 5}, {5, 12, 13}, {8, 15, 17}, {7, 24, 25}, {20, 21, 29}, {9, 40, 41},
      {12, 35, 37}, {11, 60, 61}, {13, 84, 85}, {16, 63, 65}, {33, 56, 65}, {48, 55, 73}, {65, 72, 97}};
  for (const auto & t : triples) {
    for (int k = -1000; k <= 1000; k += 7) {
      double a = std::ldexp(t[0], k), b = std::ldexp(t[1], k), c = std::ldexp(t[2], k);
      EXPECT_BITS(gmath_hypot(a, b), c) << t[0] << "," << t[1] << " * 2^" << k;
      EXPECT_BITS(gmath_hypot(-b, a), c);
    }
    EXPECT_BITS(gmath_hypot(t[0] * 1e10, t[1] * 1e10), t[2] * 1e10) << t[0];
  }
  // overflow only when the result does not fit, and none spurious
  EXPECT_BITS(gmath_hypot(kMax, kMax), kInf);
  EXPECT_BITS(gmath_hypot(kMax, 1.0), kMax);
  EXPECT_BITS(gmath_hypot(kMax, 1e290), kMax);
  EXPECT_TRUE(std::isfinite(gmath_hypot(1e308, 1e308)));
  EXPECT_NEAR(gmath_hypot(1e308, 1e308) / 1.4142135623730951e308, 1.0, 2e-16);
  EXPECT_NEAR(gmath_hypot(kMax / 1.5, kMax / 1.5) / (kMax / 1.5 * 1.4142135623730951), 1.0, 2e-16);
  EXPECT_BITS(gmath_hypot(kMax * 0.75, kMax * 0.75), kInf);
  // and none of the underflow that squaring would give
  EXPECT_NEAR(gmath_hypot(1e-200, 1e-200) / 1.4142135623730951e-200, 1.0, 2e-16);
  EXPECT_NEAR(gmath_hypot(kMin, kMin) / (kMin * 1.4142135623730951), 1.0, 2e-16);
  EXPECT_BITS(gmath_hypot(kDenorm, kDenorm), kDenorm);
  EXPECT_BITS(gmath_hypot(kDenorm * 3, kDenorm * 4), kDenorm * 5);
  EXPECT_BITS(gmath_hypot(1e-300, 1e-310), 1e-300);
  {
    Flags f;
    volatile double y = gmath_hypot(1e-200, 1e-200);
    (void)y;
    EXPECT_FALSE(f.Raised(FE_UNDERFLOW));
    EXPECT_FALSE(f.Raised(FE_OVERFLOW));
  }
  {
    Flags f;
    volatile double y = gmath_hypot(1e200, 1e200);
    (void)y;
    EXPECT_FALSE(f.Raised(FE_OVERFLOW));
    EXPECT_FALSE(f.Raised(FE_UNDERFLOW));
  }
  {
    Flags f;
    volatile double y = gmath_hypot(kMax, kMax);
    (void)y;
    EXPECT_TRUE(f.Raised(FE_OVERFLOW));
  }
  {
    Flags f;
    volatile double y = gmath_hypot(kInf, kNaN);
    (void)y;
    EXPECT_FALSE(f.Raised(FE_INVALID));
  }
}

TEST(Elementary, HypotIsSymmetricInSignAndOrder) {
  uint64_t s = 0x2545f4914f6cdd1dull;
  for (int i = 0; i < 20000; i++) {
    s = s * 6364136223846793005ull + 1442695040888963407ull;
    uint64_t t = s * 0x9e3779b97f4a7c15ull;
    double x = DoubleOf(s & 0x7fffffffffffffffull);
    double y = DoubleOf(t & 0x7fffffffffffffffull);
    if (!std::isfinite(x) || !std::isfinite(y)) {
      continue;
    }
    double h = gmath_hypot(x, y);
    EXPECT_BITS(gmath_hypot(y, x), h);
    EXPECT_BITS(gmath_hypot(-x, y), h);
    EXPECT_BITS(gmath_hypot(x, -y), h);
    EXPECT_BITS(gmath_hypot(-x, -y), h);
    EXPECT_GE(h, std::fmax(x, y));
  }
}

TEST(Elementary, NonFiniteArgumentsGiveTheSameQuietNan) {
  const double inputs[] = {kNaN, DoubleOf(0xfff8000000000000ull), DoubleOf(0x7ff8000000000123ull),
      DoubleOf(0x7ff0000000000001ull), DoubleOf(0xfff0000000000007ull)};
  for (double x : inputs) {
    EXPECT_BITS(gmath_exp(x), DoubleOf(kQNaN));
    EXPECT_BITS(gmath_log(x), DoubleOf(kQNaN));
    EXPECT_BITS(gmath_atan2(x, 2.0), DoubleOf(kQNaN));
    EXPECT_BITS(gmath_atan2(2.0, x), DoubleOf(kQNaN));
    EXPECT_BITS(gmath_pow(x, 2.0), DoubleOf(kQNaN));
    EXPECT_BITS(gmath_pow(2.0, x), DoubleOf(kQNaN));
    EXPECT_BITS(gmath_hypot(x, 2.0), DoubleOf(kQNaN));
    EXPECT_BITS(gmath_hypot(2.0, x), DoubleOf(kQNaN));
  }
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
