/**
 * @file
 *
 * gmath_sqrt (with its hardware and portable variants), gmath_floor, gmath_ceil,
 * gmath_trunc, gmath_round, gmath_rint, gmath_fabs, gmath_copysign, gmath_scalbn,
 * gmath_ldexp, gmath_frexp and gmath_ilogb against the committed corpus
 * (tests/corpus, written by tools/oracle/gen_corpus_exact.py): each has one
 * correct answer, so every result must equal the oracle's bit for bit.  Then
 * the special values of C99 Annex F one by one, the exceptions, independence of
 * the rounding mode, and, for the square root, the two variants against each
 * other and against an exact integer reference over many millions of
 * arguments.
 *
 * The corpus is required: a missing or short file fails, it is never skipped.
 * GMATH_TRIG_CORPUS_DIR points the test at another directory (a sample drawn
 * on the day, by `make check-oracle-fresh`); the committed hash is checked only
 * against the committed corpus.  GMATH_SQRT_SOAK=N runs N random arguments in
 * the variant test instead of the default (the 1e8 run of story 4a).
 *
 * Copyright 2026 by Corey Pennycuff
 */

#include "test_helpers.h"
#include "corpus_hash.h"

#include <cfenv>
#include <climits>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <limits>
#include <sstream>
#include <string>
#include <vector>

#include <ghoti.io/math/basic.h>

namespace {

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

const uint64_t kQNaN = 0x7ff8000000000000ull;
const double kInf = std::numeric_limits<double>::infinity();
const double kMin = std::numeric_limits<double>::min();
const double kMax = std::numeric_limits<double>::max();
const double kDenorm = std::numeric_limits<double>::denorm_min();

::testing::AssertionResult SameBits(double got, double want) {
  if (BitsOf(got) == BitsOf(want)) {
    return ::testing::AssertionSuccess();
  }
  return ::testing::AssertionFailure() << std::hexfloat << "got " << got << " (0x" << std::hex << BitsOf(got)
                                       << "), want " << std::hexfloat << want << " (0x" << std::hex << BitsOf(want) << ")";
}

#define EXPECT_BITS(got, want) EXPECT_TRUE(SameBits((got), (want)))

struct Flags {
  Flags() { std::feclearexcept(FE_ALL_EXCEPT); }
  bool Raised(int f) const { return std::fetestexcept(f) != 0; }
};

std::string CorpusDir(bool * committed) {
  const char * env = std::getenv("GMATH_TRIG_CORPUS_DIR");
  *committed = !(env && *env);
  return *committed ? "tests/corpus" : env;
}

size_t MinEntries() {
  const char * env = std::getenv("GMATH_TRIG_MIN_ENTRIES");
  return env && *env ? std::strtoul(env, nullptr, 10) : 1000;
}

// One corpus line: the hexadecimal words, in order.
std::vector<std::vector<uint64_t>> Load(const std::string & dir, const char * fn, size_t words) {
  std::vector<std::vector<uint64_t>> out;
  std::ifstream in(dir + "/" + fn + ".corpus");
  std::string line;
  while (std::getline(in, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    std::istringstream ls(line);
    std::vector<uint64_t> w;
    unsigned long long v;
    while (ls >> std::hex >> v) {
      w.push_back(v);
    }
    if (w.size() != words) {
      ADD_FAILURE() << "bad corpus line in " << fn << ": " << line;
      continue;
    }
    out.push_back(w);
  }
  return out;
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

// What a function does with one corpus line: the words of its result, to compare with the corpus' own.
using Eval = std::function<std::vector<uint64_t>(const std::vector<uint64_t> &)>;

struct Fn {
  const char * name;
  const char * file;
  size_t words;   // words per corpus line
  size_t nargs;   // the leading words that are arguments
  Eval eval;      // results, to compare with the trailing words
};

Eval D1(double (*f)(double)) {
  return [f](const std::vector<uint64_t> & w) { return std::vector<uint64_t>{BitsOf(f(DoubleOf(w[0])))}; };
}

const Fn kFns[] = {
  {"sqrt", "sqrt", 2, 1, D1(gmath_sqrt)},
  {"sqrt_portable", "sqrt", 2, 1, D1(gmath_sqrt_portable)},
  {"sqrt_hardware", "sqrt", 2, 1, D1(gmath_sqrt_hardware)},
  {"floor", "floor", 2, 1, D1(gmath_floor)},
  {"ceil", "ceil", 2, 1, D1(gmath_ceil)},
  {"trunc", "trunc", 2, 1, D1(gmath_trunc)},
  {"round", "round", 2, 1, D1(gmath_round)},
  {"rint", "rint", 2, 1, D1(gmath_rint)},
  {"fabs", "fabs", 2, 1, D1(gmath_fabs)},
  {"copysign", "copysign", 3, 2,
   [](const std::vector<uint64_t> & w) { return std::vector<uint64_t>{BitsOf(gmath_copysign(DoubleOf(w[0]), DoubleOf(w[1])))}; }},
  {"scalbn", "scalbn", 3, 2,
   [](const std::vector<uint64_t> & w) {
     return std::vector<uint64_t>{BitsOf(gmath_scalbn(DoubleOf(w[0]), static_cast<int>(static_cast<int64_t>(w[1]))))};
   }},
  {"ldexp", "scalbn", 3, 2,
   [](const std::vector<uint64_t> & w) {
     return std::vector<uint64_t>{BitsOf(gmath_ldexp(DoubleOf(w[0]), static_cast<int>(static_cast<int64_t>(w[1]))))};
   }},
  {"frexp", "frexp", 3, 1,
   [](const std::vector<uint64_t> & w) {
     int e = 12345;
     double f = gmath_frexp(DoubleOf(w[0]), &e);
     return std::vector<uint64_t>{BitsOf(f), static_cast<uint64_t>(static_cast<int64_t>(e))};
   }},
  {"ilogb", "ilogb", 2, 1,
   [](const std::vector<uint64_t> & w) {
     return std::vector<uint64_t>{static_cast<uint64_t>(static_cast<int64_t>(gmath_ilogb(DoubleOf(w[0]))))};
   }},
};

}  // namespace

TEST(Basic, CorpusIsExact) {
  bool committed;
  std::string dir = CorpusDir(&committed);
  for (const Fn & f : kFns) {
    auto corpus = Load(dir, f.file, f.words);
    ASSERT_GE(corpus.size(), MinEntries()) << dir << "/" << f.file << ".corpus is missing or short";
    size_t wrong = 0;
    uint64_t hash = GMATH_FNV_BASIS;
    for (const auto & w : corpus) {
      std::vector<uint64_t> got = f.eval(w);
      bool ok = got.size() == f.words - f.nargs;
      for (size_t i = 0; ok && i < got.size(); i++) {
        ok = got[i] == w[f.nargs + i];
      }
      if (!ok) {
        if (wrong++ < 5) {
          ADD_FAILURE() << f.name << "(0x" << std::hex << w[0] << ") gave 0x" << (got.empty() ? 0 : got[0]) << ", the oracle says 0x"
                        << w[f.nargs];
        }
      }
      // the hash of the function alone: results, as the probe does (a double, then an int word for frexp and ilogb)
      for (size_t i = 0; i < got.size(); i++) {
        hash = gmath_fnv_u64(hash, got[i]);
      }
    }
    EXPECT_EQ(wrong, 0u) << f.name << ": results that differ from the oracle's, of " << corpus.size();
    std::printf("  %s: %zu corpus entries, %zu wrong\n", f.name, corpus.size(), wrong);
    if (committed) {
      unsigned long long want_hash = 0, want_count = 0;
      ASSERT_TRUE(CommittedHash(f.name, &want_hash, &want_count)) << "tests/corpus/trig.hash has no line for " << f.name;
      ASSERT_NE(want_count, 0u) << "tests/corpus/trig.hash is missing or empty";
      EXPECT_EQ(corpus.size(), want_count) << f.name;
      EXPECT_EQ(hash, want_hash) << "the results of " << f.name << " over the committed corpus changed";
    }
  }
}

// ---------------------------------------------------------------------------
// The square root: two variants and an exact reference.
// ---------------------------------------------------------------------------

#ifdef __SIZEOF_INT128__
namespace {

__extension__ typedef unsigned __int128 u128;

// The correctly rounded square root of a positive finite double, by the integer square root of its significand
// with the remainder (digit by digit, 128-bit): independent of everything in the library.
uint64_t RefSqrtBits(uint64_t b) {
  uint64_t a = b & 0x7fffffffffffffffull;
  int64_t E = static_cast<int64_t>(a >> 52);
  uint64_t m = a & 0xfffffffffffffull;
  if (E == 0) {
    int sh = 0;
    while (!(m & (1ull << 52))) {
      m <<= 1;
      sh++;
    }
    E = 1 - sh;
  } else {
    m |= 1ull << 52;
  }
  int64_t ee = E - 1023;
  u128 N = m;
  if (ee & 1) {
    N <<= 1;
    ee -= 1;
  }
  N <<= 58;
  u128 rem = N, res = 0, bit = static_cast<u128>(1) << 126;
  while (bit > N) {
    bit >>= 2;
  }
  while (bit) {
    if (rem >= res + bit) {
      rem -= res + bit;
      res = (res >> 1) + bit;
    } else {
      res >>= 1;
    }
    bit >>= 2;
  }
  int len = 0;
  for (u128 t = res; t; t >>= 1) {
    len++;
  }
  int drop = len - 53;
  uint64_t q = static_cast<uint64_t>(res >> drop);
  u128 low = res & ((static_cast<u128>(1) << drop) - 1);
  u128 half = static_cast<u128>(1) << (drop - 1);
  bool up = low > half || (low == half && (rem != 0 || (q & 1)));
  if (up) {
    q++;
  }
  int64_t ex2 = (ee - 110) / 2 + drop;
  if (q == (1ull << 53)) {
    q >>= 1;
    ex2++;
  }
  int64_t be = ex2 + 52 + 1023;
  return (static_cast<uint64_t>(be) << 52) | (q & 0xfffffffffffffull);
}

struct Xorshift {
  uint64_t s;
  uint64_t Next() {
    s ^= s << 13;
    s ^= s >> 7;
    s ^= s << 17;
    return s;
  }
};

}  // namespace

TEST(Basic, SqrtVariantsAgreeWithEachOtherAndWithTheExactSquareRoot) {
  uint64_t n = 6000000;
  if (const char * env = std::getenv("GMATH_SQRT_SOAK")) {
    n = std::strtoull(env, nullptr, 10);
  }
  Xorshift r{0x9e3779b97f4a7c15ull};
  uint64_t bad = 0;
  for (uint64_t i = 0; i < n; i++) {
    uint64_t b;
    switch (i & 7) {
      case 0:
      case 1:
      case 2:
        b = r.Next() & 0x7fffffffffffffffull;
        break;
      case 3:  // subnormal
        b = r.Next() & 0x000fffffffffffffull;
        break;
      case 4: {  // a square, or next to one
        double s = DoubleOf(0x3ff0000000000000ull | (r.Next() & 0xfffffffffffffull));
        b = BitsOf(s * s);
        break;
      }
      case 5: {  // the square of a short number, and its neighbours
        double q = static_cast<double>((r.Next() & 0x3ffffffull) | 0x2000000ull) * DoubleOf((r.Next() % 2000 + 500) << 52);
        b = BitsOf(q * q) + (r.Next() % 5) - 2;
        break;
      }
      case 6: {  // the square of a halfway point (the hardest case for any method)
        uint64_t y = 0x3ff0000000000000ull | (r.Next() & 0xfffffffffffffull);
        // (y + 2^-53)^2 = y^2 + y 2^-52 + 2^-106: the double nearest to it, and the ones either side
        double yd = DoubleOf(y);
        b = BitsOf(yd * yd + yd * 0x1p-52) + (r.Next() % 3) - 1;
        break;
      }
      default:
        b = (r.Next() & 0x000fffffffffffffull) | ((r.Next() % 2046 + 1) << 52);
        break;
    }
    b &= 0x7fffffffffffffffull;
    if ((b >> 52) == 0x7ff || b == 0) {
      continue;
    }
    double x = DoubleOf(b);
    uint64_t want = RefSqrtBits(b);
    uint64_t p = BitsOf(gmath_sqrt_portable(x));
    uint64_t h = BitsOf(gmath_sqrt_hardware(x));
    uint64_t g = BitsOf(gmath_sqrt(x));
    if (p != want || h != want || g != want) {
      if (bad++ < 5) {
        ADD_FAILURE() << std::hex << "sqrt(0x" << b << "): exact 0x" << want << " portable 0x" << p << " hardware 0x" << h
                      << " gmath_sqrt 0x" << g;
      }
    }
  }
  EXPECT_EQ(bad, 0u);
  std::printf("  sqrt: %llu arguments, hardware instruction %s\n", static_cast<unsigned long long>(n),
      gmath_sqrt_has_hardware() ? "used" : "absent (the portable method twice)");
}

TEST(Basic, SqrtOfEveryExponentWithEdgeMantissas) {
  const uint64_t mants[] = {0, 1, 2, 0xfffffffffffffull, 0xffffffffffffeull, 0x8000000000000ull, 0x7ffffffffffffull,
      0x5555555555555ull, 0xaaaaaaaaaaaaaull};
  uint64_t bad = 0;
  for (uint64_t e = 0; e < 2047; e++) {
    for (uint64_t m : mants) {
      uint64_t b = (e << 52) | m;
      if (b == 0) {
        continue;
      }
      uint64_t want = RefSqrtBits(b);
      double x = DoubleOf(b);
      if (BitsOf(gmath_sqrt_portable(x)) != want || BitsOf(gmath_sqrt_hardware(x)) != want) {
        bad++;
      }
    }
  }
  EXPECT_EQ(bad, 0u);
}
#endif

TEST(Basic, SqrtSpecialValues) {
  const double kNaN = DoubleOf(kQNaN);
  for (auto f : {gmath_sqrt, gmath_sqrt_portable, gmath_sqrt_hardware}) {
    EXPECT_BITS(f(0.0), 0.0);
    EXPECT_BITS(f(-0.0), -0.0);
    EXPECT_BITS(f(kInf), kInf);
    EXPECT_BITS(f(-kInf), kNaN);
    EXPECT_BITS(f(-1.0), kNaN);
    EXPECT_BITS(f(-kDenorm), kNaN);
    EXPECT_BITS(f(-kMax), kNaN);
    EXPECT_BITS(f(kNaN), kNaN);
    EXPECT_BITS(f(DoubleOf(0xfff8000000000000ull)), kNaN);  // a negative NaN
    EXPECT_BITS(f(DoubleOf(0x7ff0000000000001ull)), kNaN);  // a signalling NaN
    EXPECT_BITS(f(DoubleOf(0xfff4000000000123ull)), kNaN);
    EXPECT_BITS(f(1.0), 1.0);
    EXPECT_BITS(f(4.0), 2.0);
    EXPECT_BITS(f(0.25), 0.5);
    EXPECT_BITS(f(2.0), 0x1.6a09e667f3bcdp+0);
    EXPECT_BITS(f(kMax), 0x1.fffffffffffffp+511);
    EXPECT_BITS(f(kMin), 0x1p-511);
    EXPECT_BITS(f(kDenorm), 0x1p-537);
    EXPECT_BITS(f(0x1.fffffffffffffp+1), 0x1.fffffffffffffp+0);
  }
}

TEST(Basic, SqrtRaisesInvalidForANegativeArgumentAndNothingElseButInexact) {
  for (auto f : {gmath_sqrt, gmath_sqrt_portable, gmath_sqrt_hardware}) {
    {
      Flags fl;
      volatile double x = -1.0;
      (void)f(x);
      EXPECT_TRUE(fl.Raised(FE_INVALID));
    }
    {
      Flags fl;
      volatile double x = -0.0;
      (void)f(x);
      EXPECT_FALSE(fl.Raised(FE_INVALID));
    }
    {
      // The instruction raises inexact only for an inexact result; the portable method does its work in
      // inexact arithmetic and raises it whatever the result (documented in basic.h).
      Flags fl;
      volatile double x = 4.0;
      (void)f(x);
      EXPECT_FALSE(fl.Raised(FE_INVALID | FE_OVERFLOW | FE_UNDERFLOW | FE_DIVBYZERO));
      if (f == gmath_sqrt_hardware && gmath_sqrt_has_hardware()) {
        EXPECT_FALSE(fl.Raised(FE_INEXACT));
      }
    }
    {
      Flags fl;
      volatile double x = 2.0;
      (void)f(x);
      EXPECT_FALSE(fl.Raised(FE_INVALID | FE_OVERFLOW | FE_UNDERFLOW | FE_DIVBYZERO));
    }
    {
      Flags fl;
      volatile double x = kInf;
      (void)f(x);
      EXPECT_FALSE(fl.Raised(FE_INVALID));
    }
    {
      Flags fl;
      volatile double x = DoubleOf(0x7ff0000000000001ull);
      (void)f(x);
      EXPECT_TRUE(fl.Raised(FE_INVALID));  // a signalling NaN
    }
  }
}

TEST(Basic, SqrtReportsWhetherItUsesTheInstruction) {
  int has = gmath_sqrt_has_hardware();
  EXPECT_TRUE(has == 0 || has == 1);
#if defined(GMATH_SQRT_PORTABLE)
  EXPECT_EQ(has, 0);
#endif
#if (defined(__x86_64__) || defined(__aarch64__)) && !defined(GMATH_SQRT_PORTABLE)
  EXPECT_EQ(has, 1) << "this target has a correctly rounding square-root instruction and the build did not turn it off";
#endif
  std::printf("  hardware square root: %s\n", has ? "yes" : "no");
}

// ---------------------------------------------------------------------------
// The rounding functions: Annex F and independence of the rounding mode.
// ---------------------------------------------------------------------------

TEST(Basic, RoundingFunctionsFollowAnnexFOnTheZerosAndTheLimits) {
  const double kNaN = DoubleOf(kQNaN);
  EXPECT_BITS(gmath_floor(-0.0), -0.0);
  EXPECT_BITS(gmath_floor(0.0), 0.0);
  EXPECT_BITS(gmath_floor(0.3), 0.0);
  EXPECT_BITS(gmath_floor(-0.3), -1.0);
  EXPECT_BITS(gmath_floor(-kDenorm), -1.0);
  EXPECT_BITS(gmath_floor(kDenorm), 0.0);
  EXPECT_BITS(gmath_floor(-1.0), -1.0);
  EXPECT_BITS(gmath_floor(-1.5), -2.0);
  EXPECT_BITS(gmath_floor(2.5), 2.0);
  EXPECT_BITS(gmath_floor(-0x1p52), -0x1p52);
  EXPECT_BITS(gmath_floor(-0x1.fffffffffffffp51), -0x1p52);
  EXPECT_BITS(gmath_floor(0x1.fffffffffffffp51), 0x1.ffffffffffffep51);
  EXPECT_BITS(gmath_floor(kMax), kMax);
  EXPECT_BITS(gmath_floor(-kInf), -kInf);
  EXPECT_BITS(gmath_floor(kInf), kInf);
  EXPECT_BITS(gmath_ceil(-0.0), -0.0);
  EXPECT_BITS(gmath_ceil(-0.3), -0.0);
  EXPECT_BITS(gmath_ceil(-kDenorm), -0.0);
  EXPECT_BITS(gmath_ceil(0.3), 1.0);
  EXPECT_BITS(gmath_ceil(kDenorm), 1.0);
  EXPECT_BITS(gmath_ceil(-1.5), -1.0);
  EXPECT_BITS(gmath_ceil(1.5), 2.0);
  EXPECT_BITS(gmath_ceil(1.0), 1.0);
  EXPECT_BITS(gmath_ceil(0x1.fffffffffffffp51), 0x1p52);
  EXPECT_BITS(gmath_trunc(-0.0), -0.0);
  EXPECT_BITS(gmath_trunc(-0.9), -0.0);
  EXPECT_BITS(gmath_trunc(0.9), 0.0);
  EXPECT_BITS(gmath_trunc(-1.9), -1.0);
  EXPECT_BITS(gmath_trunc(1.9), 1.0);
  EXPECT_BITS(gmath_trunc(0x1.fffffffffffffp51), 0x1.ffffffffffffep51);
  EXPECT_BITS(gmath_round(0.5), 1.0);
  EXPECT_BITS(gmath_round(-0.5), -1.0);
  EXPECT_BITS(gmath_round(2.5), 3.0);
  EXPECT_BITS(gmath_round(-2.5), -3.0);
  EXPECT_BITS(gmath_round(0.49999999999999994), 0.0);
  EXPECT_BITS(gmath_round(-0.49999999999999994), -0.0);
  EXPECT_BITS(gmath_round(-0.0), -0.0);
  EXPECT_BITS(gmath_round(1.4999999999999998), 1.0);
  EXPECT_BITS(gmath_round(0x1.fffffffffffffp51), 0x1p52);
  EXPECT_BITS(gmath_round(4503599627370495.5), 4503599627370496.0);
  EXPECT_BITS(gmath_rint(0.5), 0.0);
  EXPECT_BITS(gmath_rint(-0.5), -0.0);
  EXPECT_BITS(gmath_rint(1.5), 2.0);
  EXPECT_BITS(gmath_rint(2.5), 2.0);
  EXPECT_BITS(gmath_rint(3.5), 4.0);
  EXPECT_BITS(gmath_rint(-2.5), -2.0);
  EXPECT_BITS(gmath_rint(-3.5), -4.0);
  EXPECT_BITS(gmath_rint(0.5000000000000001), 1.0);
  EXPECT_BITS(gmath_rint(-0.4), -0.0);
  EXPECT_BITS(gmath_rint(4503599627370495.5), 4503599627370496.0);
  EXPECT_BITS(gmath_rint(4503599627370494.5), 4503599627370494.0);
  EXPECT_BITS(gmath_rint(kInf), kInf);
  for (auto f : {gmath_floor, gmath_ceil, gmath_trunc, gmath_round, gmath_rint, gmath_fabs}) {
    EXPECT_BITS(f(kNaN), kNaN);
    EXPECT_BITS(f(DoubleOf(0xfff8000000000000ull)), kNaN);
    EXPECT_BITS(f(DoubleOf(0x7ff0000000000001ull)), kNaN);
    EXPECT_BITS(f(DoubleOf(0xfff4000000000123ull)), kNaN);
  }
  EXPECT_BITS(gmath_fabs(-0.0), 0.0);
  EXPECT_BITS(gmath_fabs(-kInf), kInf);
  EXPECT_BITS(gmath_fabs(-kDenorm), kDenorm);
  EXPECT_BITS(gmath_fabs(-3.5), 3.5);
  EXPECT_BITS(gmath_copysign(3.0, -0.0), -3.0);
  EXPECT_BITS(gmath_copysign(-3.0, 0.0), 3.0);
  EXPECT_BITS(gmath_copysign(0.0, -1.0), -0.0);
  EXPECT_BITS(gmath_copysign(-kInf, 1.0), kInf);
  EXPECT_BITS(gmath_copysign(1.0, DoubleOf(0xfff8000000000000ull)), -1.0);  // the sign bit of a NaN y is a sign bit
  EXPECT_BITS(gmath_copysign(kNaN, -1.0), kNaN);
  EXPECT_BITS(gmath_copysign(DoubleOf(0xfff8000000000000ull), 1.0), kNaN);
}

TEST(Basic, RoundingFunctionsDoNotReadTheRoundingMode) {
  const int modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
  const double xs[] = {0.5, 1.5, 2.5, -0.5, -1.5, -2.5, 0.3, -0.3, 1e-300, -1e-300, 4503599627370495.5, 123.75, -123.75};
  struct Want {
    double (*f)(double);
    std::vector<double> r;
  };
  std::vector<Want> wants = {
      {gmath_floor, {}}, {gmath_ceil, {}}, {gmath_trunc, {}}, {gmath_round, {}}, {gmath_rint, {}}};
  for (auto & w : wants) {
    for (double x : xs) {
      w.r.push_back(w.f(x));
    }
  }
  int saved = std::fegetround();
  for (int mode : modes) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (auto & w : wants) {
      for (size_t i = 0; i < sizeof xs / sizeof xs[0]; i++) {
        EXPECT_BITS(w.f(xs[i]), w.r[i]) << "rounding mode " << mode;
      }
    }
  }
  std::fesetround(saved);
}

TEST(Basic, RoundingFunctionsRaiseNothingButInvalidForASignallingNaN) {
  for (auto f : {gmath_floor, gmath_ceil, gmath_trunc, gmath_round, gmath_rint, gmath_fabs}) {
    {
      Flags fl;
      volatile double x = 2.5;
      (void)f(x);
      EXPECT_FALSE(fl.Raised(FE_ALL_EXCEPT));
    }
    {
      Flags fl;
      volatile double x = -0.3;
      (void)f(x);
      EXPECT_FALSE(fl.Raised(FE_ALL_EXCEPT));
    }
    {
      Flags fl;
      volatile double x = DoubleOf(0x7ff0000000000001ull);
      (void)f(x);
      EXPECT_TRUE(fl.Raised(FE_INVALID));
    }
  }
}

TEST(Basic, RoundingFunctionsAgreeWithTheLibraryOnRandomArguments) {
  // A second reference that is not the corpus: the C library's own functions (exact by definition), in
  // the default rounding mode, over uniform bit patterns, values around the integers, and halfway cases.
  uint64_t s = 0x2545f4914f6cdd1dull;
  auto next = [&s]() {
    s ^= s << 13;
    s ^= s >> 7;
    s ^= s << 17;
    return s;
  };
  uint64_t bad = 0;
  for (int i = 0; i < 4000000; i++) {
    double x;
    switch (i & 3) {
      case 0:
        x = DoubleOf(next());
        break;
      case 1:
        x = static_cast<double>(static_cast<int64_t>(next() >> 20) - (1 << 20)) * 0x1p-8;
        break;
      case 2:
        x = std::ldexp(static_cast<double>(next() >> 11), -static_cast<int>(next() % 64));
        break;
      default:
        x = static_cast<double>(static_cast<int64_t>(next() >> 12)) + 0.5;
        break;
    }
    if (std::isnan(x)) {
      continue;
    }
    if (BitsOf(gmath_floor(x)) != BitsOf(std::floor(x)) || BitsOf(gmath_ceil(x)) != BitsOf(std::ceil(x)) ||
        BitsOf(gmath_trunc(x)) != BitsOf(std::trunc(x)) || BitsOf(gmath_round(x)) != BitsOf(std::round(x)) ||
        BitsOf(gmath_rint(x)) != BitsOf(std::nearbyint(x)) || BitsOf(gmath_fabs(x)) != BitsOf(std::fabs(x))) {
      if (bad++ < 5) {
        ADD_FAILURE() << std::hexfloat << "rounding of " << x;
      }
    }
  }
  EXPECT_EQ(bad, 0u);
}

// ---------------------------------------------------------------------------
// scalbn, ldexp, frexp, ilogb
// ---------------------------------------------------------------------------

TEST(Basic, ScalbnSpecialValuesAndExceptions) {
  const double kNaN = DoubleOf(kQNaN);
  EXPECT_BITS(gmath_scalbn(1.0, 10), 1024.0);
  EXPECT_BITS(gmath_scalbn(1.0, -1074), kDenorm);
  EXPECT_BITS(gmath_scalbn(1.0, -1075), 0.0);                      // a tie between 0 and denorm_min: even
  EXPECT_BITS(gmath_scalbn(1.5, -1075), kDenorm);                  // just over it
  EXPECT_BITS(gmath_scalbn(-1.0, -1075), -0.0);
  EXPECT_BITS(gmath_scalbn(0x1.8p0, -1074), 2 * kDenorm);          // 1.5 denorm_min: a tie, to even
  EXPECT_BITS(gmath_scalbn(0x1.4p0, -1074), kDenorm);              // 1.25: down
  EXPECT_BITS(gmath_scalbn(kDenorm, 1074), 1.0);
  EXPECT_BITS(gmath_scalbn(kDenorm, 2000), 0x1p926);
  EXPECT_BITS(gmath_scalbn(kMax, 1), kInf);
  EXPECT_BITS(gmath_scalbn(-kMax, 1), -kInf);
  EXPECT_BITS(gmath_scalbn(kMax, -1), 0x1.fffffffffffffp1022);
  EXPECT_BITS(gmath_scalbn(kMin, -1), 0x1p-1023);
  EXPECT_BITS(gmath_scalbn(0x1.fffffffffffffp-1022, -1), 0x1p-1022);  // rounds up to the smallest normal
  EXPECT_BITS(gmath_scalbn(1.0, INT_MAX), kInf);
  EXPECT_BITS(gmath_scalbn(1.0, INT_MIN), 0.0);
  EXPECT_BITS(gmath_scalbn(-1.0, INT_MIN), -0.0);
  EXPECT_BITS(gmath_scalbn(0.0, 100), 0.0);
  EXPECT_BITS(gmath_scalbn(-0.0, 100), -0.0);
  EXPECT_BITS(gmath_scalbn(kInf, -100), kInf);
  EXPECT_BITS(gmath_scalbn(-kInf, 100), -kInf);
  EXPECT_BITS(gmath_scalbn(kNaN, 3), kNaN);
  EXPECT_BITS(gmath_scalbn(DoubleOf(0xfff0000000000001ull), 3), kNaN);
  EXPECT_BITS(gmath_ldexp(3.0, 4), 48.0);
  {
    Flags fl;
    volatile double x = kMax;
    (void)gmath_scalbn(x, 1);
    EXPECT_TRUE(fl.Raised(FE_OVERFLOW));
    EXPECT_TRUE(fl.Raised(FE_INEXACT));
  }
  {
    Flags fl;
    volatile double x = 1.0;
    (void)gmath_scalbn(x, -1074);  // exact
    EXPECT_FALSE(fl.Raised(FE_UNDERFLOW | FE_INEXACT | FE_OVERFLOW));
  }
  {
    Flags fl;
    volatile double x = 3.0;
    (void)gmath_scalbn(x, -1075);  // tiny and inexact
    EXPECT_TRUE(fl.Raised(FE_UNDERFLOW));
  }
  {
    Flags fl;
    volatile double x = 3.0;
    (void)gmath_scalbn(x, 5);
    EXPECT_FALSE(fl.Raised(FE_ALL_EXCEPT));
  }
}

TEST(Basic, ScalbnFrexpAndIlogbAgreeWithTheLibraryOnRandomArguments) {
  uint64_t s = 0x6a09e667f3bcc909ull;
  auto next = [&s]() {
    s ^= s << 13;
    s ^= s >> 7;
    s ^= s << 17;
    return s;
  };
  uint64_t bad = 0;
  for (int i = 0; i < 3000000; i++) {
    double x = DoubleOf(next());
    if (std::isnan(x)) {
      continue;
    }
    int n;
    switch (i & 3) {
      case 0:
        n = static_cast<int>(next() % 4400) - 2200;
        break;
      case 1:
        n = static_cast<int>(next() % 130) - 65;
        break;
      case 2:
        n = -static_cast<int>((BitsOf(x) >> 52) & 0x7ff) + static_cast<int>(next() % 120) - 100;
        break;
      default:
        n = static_cast<int>(next());
        break;
    }
    int e1 = 0, e2 = 0;
    double f1 = gmath_frexp(x, &e1);
    double f2 = std::frexp(x, &e2);
    bool finite = std::isfinite(x);
    if (BitsOf(gmath_scalbn(x, n)) != BitsOf(std::scalbn(x, n)) || BitsOf(gmath_ldexp(x, n)) != BitsOf(std::ldexp(x, n)) ||
        BitsOf(f1) != BitsOf(f2) || (finite && e1 != e2) || (finite && x != 0 && gmath_ilogb(x) != std::ilogb(x))) {
      if (bad++ < 5) {
        ADD_FAILURE() << std::hexfloat << "scalbn/frexp/ilogb of " << x << " (n = " << n << ")";
      }
    }
  }
  EXPECT_EQ(bad, 0u);
}

TEST(Basic, FrexpAndIlogbSpecialValues) {
  int e = 77;
  EXPECT_BITS(gmath_frexp(0.0, &e), 0.0);
  EXPECT_EQ(e, 0);
  EXPECT_BITS(gmath_frexp(-0.0, &e), -0.0);
  EXPECT_EQ(e, 0);
  e = 77;
  EXPECT_BITS(gmath_frexp(kInf, &e), kInf);
  EXPECT_EQ(e, 0);
  EXPECT_BITS(gmath_frexp(DoubleOf(0xfff8000000000001ull), &e), DoubleOf(kQNaN));
  EXPECT_BITS(gmath_frexp(1.0, &e), 0.5);
  EXPECT_EQ(e, 1);
  EXPECT_BITS(gmath_frexp(-8.0, &e), -0.5);
  EXPECT_EQ(e, 4);
  EXPECT_BITS(gmath_frexp(kDenorm, &e), 0.5);
  EXPECT_EQ(e, -1073);
  EXPECT_BITS(gmath_frexp(kMax, &e), 0x1.fffffffffffffp-1);
  EXPECT_EQ(e, 1024);
  EXPECT_BITS(gmath_frexp(3.0, nullptr), 0.75);
  EXPECT_EQ(gmath_ilogb(1.0), 0);
  EXPECT_EQ(gmath_ilogb(0.75), -1);
  EXPECT_EQ(gmath_ilogb(-8.0), 3);
  EXPECT_EQ(gmath_ilogb(kDenorm), -1074);
  EXPECT_EQ(gmath_ilogb(0x0.fffffffffffffp-1022), -1023);
  EXPECT_EQ(gmath_ilogb(kMax), 1023);
  {
    Flags fl;
    volatile double z = 0.0;
    EXPECT_EQ(gmath_ilogb(z), GMATH_ILOGB0);
    EXPECT_TRUE(fl.Raised(FE_INVALID));
  }
  EXPECT_EQ(gmath_ilogb(kInf), INT_MAX);
  EXPECT_EQ(gmath_ilogb(-kInf), INT_MAX);
  EXPECT_EQ(gmath_ilogb(DoubleOf(kQNaN)), GMATH_ILOGBNAN);
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
