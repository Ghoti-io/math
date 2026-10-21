/**
 * @file
 *
 * gmath_decimal_parse, gmath_decimal_to_double and gmath_decimal_shortest
 * against the committed corpus (tests/corpus, written by
 * tools/oracle/gen_corpus_decimal.py, where an exact rational reference, MPFR
 * and CPython agree): each has one correct answer, so the bits, the flags and
 * the digits must equal the oracle's.  Then the requirements decimal.h states:
 * the grammar and what is consumed, the arguments refused, the inverse property
 * (the shortest digits read back to the same double) over many random doubles,
 * inputs longer than any limit of the method, and independence from the
 * rounding mode.  Every fast tier is checked against the general tier on every
 * corpus input and shown taken (AD-13).
 *
 * The corpus is required: a missing or short file fails, it is never skipped.
 * GMATH_TRIG_CORPUS_DIR points the test at another directory (a sample drawn on
 * the day, by `make check-oracle-fresh`).  GMATH_DECIMAL_SOAK=N runs N random
 * doubles in the inverse test instead of the default.
 *
 * Copyright 2026 by Corey Pennycuff
 */

#include "test_helpers.h"

#include "../../src/decimal/decimal_internal.h"

#include <cfenv>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <random>
#include <sstream>
#include <string>
#include <vector>

#include <ghoti.io/math/decimal.h>

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

std::string CorpusDir() {
  const char * env = std::getenv("GMATH_TRIG_CORPUS_DIR");
  return env && *env ? env : "tests/corpus";
}

size_t MinEntries() {
  const char * env = std::getenv("GMATH_TRIG_MIN_ENTRIES");
  return env && *env ? std::strtoul(env, nullptr, 10) : 1000;
}

std::vector<std::vector<std::string>> Load(const char * fn, size_t words) {
  std::vector<std::vector<std::string>> out;
  std::ifstream in(CorpusDir() + "/" + fn + ".corpus");
  std::string line;
  while (std::getline(in, line)) {
    if (line.empty() || line[0] == '#') {
      continue;
    }
    std::istringstream ls(line);
    std::vector<std::string> w;
    std::string t;
    while (ls >> t) {
      w.push_back(t);
    }
    if (w.size() != words) {
      ADD_FAILURE() << "bad corpus line in " << fn << ": " << line.substr(0, 80);
      continue;
    }
    out.push_back(w);
  }
  return out;
}

uint64_t Hex(const std::string & s) {
  return std::strtoull(s.c_str(), nullptr, 16);
}

struct Parsed {
  GMATH_Result result;
  uint64_t bits;
  size_t consumed;
  unsigned flags;
};

Parsed Parse(const std::string & s) {
  Parsed p{GMATH_ERR_INTERNAL, 0, 0, 0};
  double d = 0;
  p.result = gmath_decimal_parse(s.data(), s.size(), &d, &p.consumed, &p.flags);
  p.bits = BitsOf(d);
  return p;
}

std::string Spelled(const GMATH_Decimal & d) {
  return std::string(d.negative ? "-" : "") + d.digits + "e" + std::to_string(d.exponent);
}

}  // namespace

TEST(DecimalCorpus, ParseEqualsTheOracleInBitsAndFlags) {
  auto rows = Load("decimal_parse", 3);
  ASSERT_GE(rows.size(), MinEntries()) << "the corpus " << CorpusDir() << "/decimal_parse.corpus is missing or short";
  size_t bad = 0;
  for (const auto & r : rows) {
    Parsed p = Parse(r[0]);
    if (p.result != GMATH_OK || p.bits != Hex(r[1]) || p.flags != std::strtoul(r[2].c_str(), nullptr, 10) ||
        p.consumed != r[0].size()) {
      if (++bad <= 10) {
        ADD_FAILURE() << r[0].substr(0, 80) << ": got " << std::hex << p.bits << " flags " << std::dec << p.flags
                      << " consumed " << p.consumed << " result " << p.result << ", want " << r[1] << " flags " << r[2];
      }
    }
  }
  EXPECT_EQ(bad, 0u);
}

// AD-13: every tier against the general one, on every corpus input, and each
// tier seen taken.
TEST(DecimalCorpus, EveryParseTierEqualsTheGeneralTierAndIsTaken) {
  auto rows = Load("decimal_parse", 3);
  ASSERT_GE(rows.size(), MinEntries());
  size_t taken[6] = {0, 0, 0, 0, 0, 0};
  size_t bad = 0;
  for (const auto & r : rows) {
    // Split the text the way gmath_decimal_parse does, independently: the
    // digits before and after the point, and the exponent of the last digit.
    const std::string & s = r[0];
    size_t i = 0;
    bool neg = false;
    if (s[i] == '+' || s[i] == '-') {
      neg = s[i] == '-';
      i++;
    }
    std::string ip, fp;
    while (i < s.size() && s[i] >= '0' && s[i] <= '9') {
      ip += s[i++];
    }
    if (i < s.size() && s[i] == '.') {
      i++;
      while (i < s.size() && s[i] >= '0' && s[i] <= '9') {
        fp += s[i++];
      }
    }
    long long e = 0;
    if (i < s.size()) {
      std::string ex = s.substr(i + 1);
      // A huge exponent saturates; any magnitude past +-2^61 decides alike.
      e = std::strtoll(ex.c_str(), nullptr, 10);
      if (e > (1ll << 61)) {
        e = 1ll << 61;
      } else if (e < -(1ll << 61)) {
        e = -(1ll << 61);
      }
    }
    int64_t last = e - static_cast<int64_t>(fp.size());
    double fast = 0, general = 0;
    unsigned ff = 99, gf = 99;
    gmath_decimal_tier tf = GMATH_DECIMAL_TIER_GENERAL, tg = GMATH_DECIMAL_TIER_GENERAL;
    GMATH_Result a = gmath_decimal_round_spans(neg, ip.data(), ip.size(), fp.data(), fp.size(), last, false, &fast, &ff, &tf);
    GMATH_Result b = gmath_decimal_round_spans(neg, ip.data(), ip.size(), fp.data(), fp.size(), last, true, &general, &gf, &tg);
    taken[tf]++;
    if (a != GMATH_OK || b != GMATH_OK || BitsOf(fast) != BitsOf(general) || ff != gf ||
        BitsOf(fast) != Hex(r[1])) {
      if (++bad <= 10) {
        ADD_FAILURE() << s.substr(0, 80) << ": tier " << tf << " gives " << std::hex << BitsOf(fast)
                      << ", the general tier " << BitsOf(general);
      }
    }
    EXPECT_NE(tg, GMATH_DECIMAL_TIER_DIV32) << "the general tier must not divide by one limb";
  }
  EXPECT_EQ(bad, 0u);
  EXPECT_GT(taken[GMATH_DECIMAL_TIER_SPECIAL], 10u);
  EXPECT_GT(taken[GMATH_DECIMAL_TIER_SHIFT], 100u);
  EXPECT_GT(taken[GMATH_DECIMAL_TIER_DIV32], 100u);
  EXPECT_GT(taken[GMATH_DECIMAL_TIER_RESTORING], 100u);
}

TEST(DecimalCorpus, ShortestEqualsTheOracleAndEveryTierAgrees) {
  auto rows = Load("decimal_shortest", 3);
  ASSERT_GE(rows.size(), MinEntries()) << "the corpus " << CorpusDir() << "/decimal_shortest.corpus is missing or short";
  size_t taken[6] = {0, 0, 0, 0, 0, 0};
  size_t bad = 0;
  for (const auto & r : rows) {
    uint64_t u = Hex(r[0]);
    GMATH_Decimal d, g;
    gmath_decimal_tier t = GMATH_DECIMAL_TIER_SPECIAL, tg = GMATH_DECIMAL_TIER_SPECIAL;
    GMATH_Result a = gmath_decimal_shortest_tiered(DoubleOf(u), false, &d, &t);
    GMATH_Result b = gmath_decimal_shortest_tiered(DoubleOf(u), true, &g, &tg);
    taken[t]++;
    EXPECT_TRUE(tg == GMATH_DECIMAL_TIER_GENERAL || tg == GMATH_DECIMAL_TIER_SPECIAL) << std::hex << u;
    std::string want = r[1] + "e" + r[2];
    bool ok = a == GMATH_OK && b == GMATH_OK && std::string(d.digits) + "e" + std::to_string(d.exponent) == want &&
              Spelled(d) == Spelled(g) && d.negative == ((u >> 63) != 0) && d.length == std::strlen(d.digits);
    if (!ok && ++bad <= 10) {
      ADD_FAILURE() << std::hex << u << ": got " << Spelled(d) << " (general " << Spelled(g) << "), want " << want;
    }
    // The public entry point is the tiered one with every tier allowed.
    GMATH_Decimal p;
    ASSERT_EQ(gmath_decimal_shortest(DoubleOf(u), &p), GMATH_OK);
    EXPECT_EQ(Spelled(p), Spelled(d));
  }
  EXPECT_EQ(bad, 0u);
  EXPECT_GT(taken[GMATH_DECIMAL_TIER_INTEGER], 1000u);
  EXPECT_GT(taken[GMATH_DECIMAL_TIER_SHIFT], 1000u);
  EXPECT_GT(taken[GMATH_DECIMAL_TIER_GENERAL], 1000u);
}

// The inverse property decimal.h states, over random doubles of every exponent.
TEST(DecimalInverse, ShortestDigitsReadBackToTheSameDouble) {
  size_t n = 200000;
  if (const char * env = std::getenv("GMATH_DECIMAL_SOAK")) {
    n = std::strtoull(env, nullptr, 10);
  }
  std::mt19937_64 rng(20261021);
  size_t bad = 0;
  for (size_t i = 0; i < n; ++i) {
    uint64_t u = rng();
    if (((u >> 52) & 0x7ff) == 0x7ff) {
      continue;
    }
    GMATH_Decimal d;
    ASSERT_EQ(gmath_decimal_shortest(DoubleOf(u), &d), GMATH_OK);
    double back = 0;
    unsigned flags = 99;
    ASSERT_EQ(gmath_decimal_to_double(d.negative, d.digits, d.length, d.exponent, &back, &flags), GMATH_OK);
    if (BitsOf(back) != u && ++bad <= 10) {
      ADD_FAILURE() << std::hex << u << " -> " << Spelled(d) << " -> " << BitsOf(back);
    }
    EXPECT_LE(d.length, static_cast<size_t>(GMATH_DECIMAL_MAX_DIGITS));
    EXPECT_NE(d.digits[0], '0');
    EXPECT_NE(d.digits[d.length - 1], '0');
  }
  EXPECT_EQ(bad, 0u);
}

TEST(DecimalShortest, ZeroIsOneDigitWithTheSignOfX) {
  GMATH_Decimal d;
  ASSERT_EQ(gmath_decimal_shortest(0.0, &d), GMATH_OK);
  EXPECT_STREQ(d.digits, "0");
  EXPECT_EQ(d.length, 1u);
  EXPECT_EQ(d.exponent, 0);
  EXPECT_FALSE(d.negative);
  ASSERT_EQ(gmath_decimal_shortest(-0.0, &d), GMATH_OK);
  EXPECT_STREQ(d.digits, "0");
  EXPECT_TRUE(d.negative);
}

TEST(DecimalShortest, RefusesInfinityNanAndNullOutWithoutWriting) {
  GMATH_Decimal d;
  std::memset(&d, 0x5a, sizeof d);
  EXPECT_EQ(gmath_decimal_shortest(DoubleOf(0x7ff0000000000000ull), &d), GMATH_ERR_INVALID);
  EXPECT_EQ(gmath_decimal_shortest(DoubleOf(0xfff0000000000000ull), &d), GMATH_ERR_INVALID);
  EXPECT_EQ(gmath_decimal_shortest(DoubleOf(0x7ff8000000000000ull), &d), GMATH_ERR_INVALID);
  EXPECT_EQ(gmath_decimal_shortest(DoubleOf(0x7ff0000000000001ull), &d), GMATH_ERR_INVALID);
  EXPECT_EQ(static_cast<unsigned char>(d.digits[0]), 0x5au);
  EXPECT_EQ(gmath_decimal_shortest(1.0, nullptr), GMATH_ERR_INVALID);
}

// The ends of the interval: a midpoint goes to the even neighbour, so it is in
// the interval of an even significand and outside that of an odd one.
TEST(DecimalShortest, IncludesTheEndsOnlyForAnEvenSignificand) {
  // 2^53 + 2 (even significand after 2^53) and 2^53 + 4: the decimals 9007199254740993
  // and 9007199254740995 are the midpoints below and above 2^53 + 2.
  GMATH_Decimal d;
  ASSERT_EQ(gmath_decimal_shortest(9007199254740994.0, &d), GMATH_OK);
  EXPECT_EQ(Spelled(d), "9007199254740994e0");
  // 5e-324 is the shortest for the smallest subnormal (significand 1, odd):
  // 2.5e-324 would be the end and is excluded; 5e-324 is inside.
  ASSERT_EQ(gmath_decimal_shortest(DoubleOf(1), &d), GMATH_OK);
  EXPECT_EQ(Spelled(d), "5e-324");
  // 1e23 is the shortest spelling of the double nearest it, below 10^23.
  ASSERT_EQ(gmath_decimal_shortest(1e23, &d), GMATH_OK);
  EXPECT_EQ(Spelled(d), "1e23");
}

TEST(DecimalParse, ReadsTheLongestNumberAndStopsBeforeAnIncompleteExponent) {
  struct Case {
    const char * text;
    size_t consumed;
    uint64_t bits;
  };
  const Case cases[] = {
      {"1e", 1, BitsOf(1.0)},       {"1e+", 1, BitsOf(1.0)},       {"1e-x", 1, BitsOf(1.0)},
      {"1ex", 1, BitsOf(1.0)},      {"1E5", 3, BitsOf(1e5)},        {"1.5.3", 3, BitsOf(1.5)},
      {"-.5", 3, BitsOf(-0.5)},     {"+.5e1", 5, BitsOf(5.0)},      {"5.", 2, BitsOf(5.0)},
      {"5.e2", 4, BitsOf(500.0)},   {"0x10", 1, BitsOf(0.0)},       {"1_000", 1, BitsOf(1.0)},
      {"12px", 2, BitsOf(12.0)},    {"-0", 2, BitsOf(-0.0)},        {"007", 3, BitsOf(7.0)},
      {"1e0001", 6, BitsOf(10.0)},  {"3.14159 ", 7, BitsOf(3.14159)}, {".5.", 2, BitsOf(0.5)},
  };
  for (const auto & c : cases) {
    Parsed p = Parse(c.text);
    EXPECT_EQ(p.result, GMATH_OK) << c.text;
    EXPECT_EQ(p.consumed, c.consumed) << c.text;
    EXPECT_EQ(p.bits, c.bits) << c.text;
  }
}

TEST(DecimalParse, RefusesTextThatDoesNotStartWithANumberAndWritesNothing) {
  const char * texts[] = {"", ".", "+", "-", "+.", "e5", " 1", "inf", "nan", "infinity", "-e1", ".e1", "\t1"};
  for (const char * t : texts) {
    double d = 12345.0;
    size_t consumed = 77;
    unsigned flags = 88;
    EXPECT_EQ(gmath_decimal_parse(t, std::strlen(t), &d, &consumed, &flags), GMATH_ERR_FORMAT) << "'" << t << "'";
    EXPECT_EQ(d, 12345.0);
    EXPECT_EQ(consumed, 77u);
    EXPECT_EQ(flags, 88u);
  }
  double d = 0;
  EXPECT_EQ(gmath_decimal_parse(nullptr, 0, &d, nullptr, nullptr), GMATH_ERR_FORMAT);
}

TEST(DecimalParse, RespectsTheLengthNotATerminator) {
  const char text[] = "123456";
  double d = 0;
  size_t consumed = 0;
  ASSERT_EQ(gmath_decimal_parse(text, 3, &d, &consumed, nullptr), GMATH_OK);
  EXPECT_EQ(d, 123.0);
  EXPECT_EQ(consumed, 3u);
  // No NUL anywhere: the reader must stop at the length.
  char buf[2] = {'9', '9'};
  ASSERT_EQ(gmath_decimal_parse(buf, 2, &d, &consumed, nullptr), GMATH_OK);
  EXPECT_EQ(d, 99.0);
}

TEST(DecimalArguments, AreRefusedWithErrInvalidAndNothingWritten) {
  double d = 42.0;
  unsigned flags = 7;
  EXPECT_EQ(gmath_decimal_parse("1", 1, nullptr, nullptr, nullptr), GMATH_ERR_INVALID);
  EXPECT_EQ(gmath_decimal_parse(nullptr, 1, &d, nullptr, nullptr), GMATH_ERR_INVALID);
  EXPECT_EQ(gmath_decimal_to_double(false, "1", 1, 0, nullptr, nullptr), GMATH_ERR_INVALID);
  EXPECT_EQ(gmath_decimal_to_double(false, nullptr, 1, 0, &d, &flags), GMATH_ERR_INVALID);
  EXPECT_EQ(gmath_decimal_to_double(false, "1", 0, 0, &d, &flags), GMATH_ERR_INVALID);
  EXPECT_EQ(gmath_decimal_to_double(false, "1.5", 3, 0, &d, &flags), GMATH_ERR_INVALID);
  EXPECT_EQ(gmath_decimal_to_double(false, "12a", 3, 0, &d, &flags), GMATH_ERR_INVALID);
  EXPECT_EQ(gmath_decimal_to_double(false, "-1", 2, 0, &d, &flags), GMATH_ERR_INVALID);
  EXPECT_EQ(d, 42.0);
  EXPECT_EQ(flags, 7u);
}

TEST(DecimalToDouble, TakesAnyExponentWithoutOverflowingItsArithmetic) {
  double d = 0;
  unsigned flags = 0;
  ASSERT_EQ(gmath_decimal_to_double(false, "1", 1, INT64_MAX, &d, &flags), GMATH_OK);
  EXPECT_EQ(BitsOf(d), 0x7ff0000000000000ull);
  EXPECT_EQ(flags, GMATH_DECIMAL_OVERFLOW | GMATH_DECIMAL_INEXACT);
  ASSERT_EQ(gmath_decimal_to_double(true, "1", 1, INT64_MIN, &d, &flags), GMATH_OK);
  EXPECT_EQ(BitsOf(d), 0x8000000000000000ull);
  EXPECT_EQ(flags, GMATH_DECIMAL_UNDERFLOW | GMATH_DECIMAL_INEXACT);
  ASSERT_EQ(gmath_decimal_to_double(true, "000", 3, INT64_MAX, &d, &flags), GMATH_OK);
  EXPECT_EQ(BitsOf(d), 0x8000000000000000ull);
  EXPECT_EQ(flags, 0u);
  // Many digits and an exponent that brings them back: 10^(n-1) * 10^-(n-1) is 1.
  std::string many = "1" + std::string(5000, '0');
  ASSERT_EQ(gmath_decimal_to_double(false, many.data(), many.size(), -5000, &d, &flags), GMATH_OK);
  EXPECT_EQ(d, 1.0);
  EXPECT_EQ(flags, 0u);
  ASSERT_EQ(gmath_decimal_to_double(false, many.data(), many.size(), INT64_MIN, &d, &flags), GMATH_OK);
  EXPECT_EQ(BitsOf(d), 0u);
}

// Past the 800 significant digits the method keeps: the rest decides only
// whether the value is above the truncation, and the result must still be
// correctly rounded.
TEST(DecimalToDouble, RoundsInputsLongerThanTheTruncationCorrectly) {
  // 2^53 + 1 is the midpoint between 2^53 and 2^53 + 2: a tie, to even (2^53).
  // A nonzero digit a hundred thousand places later breaks the tie upward.
  std::string tie = "9007199254740993";
  double d = 0;
  unsigned flags = 0;
  ASSERT_EQ(gmath_decimal_to_double(false, tie.data(), tie.size(), 0, &d, &flags), GMATH_OK);
  EXPECT_EQ(d, 9007199254740992.0);
  EXPECT_EQ(flags, GMATH_DECIMAL_INEXACT);
  std::string above = tie + std::string(100000, '0') + "1";
  ASSERT_EQ(gmath_decimal_to_double(false, above.data(), above.size(), -100001, &d, &flags), GMATH_OK);
  EXPECT_EQ(d, 9007199254740994.0);
  std::string zeros = tie + std::string(100000, '0');
  ASSERT_EQ(gmath_decimal_to_double(false, zeros.data(), zeros.size(), -100000, &d, &flags), GMATH_OK);
  EXPECT_EQ(d, 9007199254740992.0);
  // Just below the tie, by digits: 9007199254740992.999...9 (100000 nines).
  std::string below = "9007199254740992" + std::string(100000, '9');
  ASSERT_EQ(gmath_decimal_to_double(false, below.data(), below.size(), -100000, &d, &flags), GMATH_OK);
  EXPECT_EQ(d, 9007199254740992.0);
  // And through the parser, with the point and an exponent.
  std::string text = "9.007199254740993" + std::string(1000, '0') + "1e15";
  Parsed p = Parse(text);
  EXPECT_EQ(p.bits, BitsOf(9007199254740994.0));
  EXPECT_EQ(p.consumed, text.size());
}

TEST(DecimalToDouble, ReportsUnderflowOnlyForAnInexactTinyResult) {
  double d = 0;
  unsigned flags = 0;
  // 2^-1074 exactly is the smallest subnormal and exact: no flags.
  Parsed p = Parse("4.940656458412465441765687928682213723650598026143247644255856825006755072702087518652998363616359923797965646954457177309266567103559397963987747960107818781263007131903114045278458171678489821036887186360569987307230500063874091535649843873124733972731696151400317153853980741262385655911710266585566867681870395603106249319452715914924553293054565444011274801297099995419319894090804165633245247571478690147267801593552386115501348035264934720193790268107107491703332226844753335720832431936092382893458368060106011506169809753078342277318329247904982524730776375927247874656084778203734469699533647017972677717585125660551199131504891101451037862738167250955837389733598993664809941164205702637090279242767544565229087538682506419718265533447265625e-324");
  EXPECT_EQ(p.bits, 1u);
  EXPECT_EQ(p.flags, 0u);
  // The smallest normal number is not tiny.
  p = Parse("2.225073858507201383090232717332404064219215980462331830553327416887204434813918195854283159012511020564067339731035811005152434161553460108856012385377718821130777993532002330479610147442583636071921565046942503734208375250806650616658158948720491179968591639648500635908770118304874799780887753749949451580451605050915399856582470818645113537935804992115981085766051992433352114352390148795699609591288891602992641511063466313393663477586513029371762047325631781485664350872122828637642044846811407613911477062801689853244110024161447421618567166150540154285084716752901903161322778896729707373123334086988983175067838846926092773977972858659654941091369095406136467568702398678315290680984617210924625396728515625e-308");
  EXPECT_EQ(p.bits, 0x0010000000000000ull);
  EXPECT_EQ(p.flags, 0u);
  ASSERT_EQ(gmath_decimal_to_double(false, "1", 1, -320, &d, &flags), GMATH_OK);
  EXPECT_EQ(flags, GMATH_DECIMAL_INEXACT | GMATH_DECIMAL_UNDERFLOW);
}

// No floating-point operation is used: the rounding mode is never read and no
// exception flag is raised.
TEST(DecimalEnvironment, ResultsDoNotDependOnTheRoundingModeAndRaiseNothing) {
  auto rows = Load("decimal_parse", 3);
  auto srows = Load("decimal_shortest", 3);
  ASSERT_GE(rows.size(), MinEntries());
  const int modes[] = {FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
  for (int mode : modes) {
    ASSERT_EQ(std::fesetround(mode), 0);
    std::feclearexcept(FE_ALL_EXCEPT);
    size_t bad = 0;
    for (size_t i = 0; i < rows.size(); i += 7) {
      double d = 0;
      size_t consumed = 0;
      unsigned flags = 0;
      if (gmath_decimal_parse(rows[i][0].data(), rows[i][0].size(), &d, &consumed, &flags) != GMATH_OK ||
          BitsOf(d) != Hex(rows[i][1])) {
        bad++;
      }
    }
    for (size_t i = 0; i < srows.size(); i += 7) {
      GMATH_Decimal d;
      if (gmath_decimal_shortest(DoubleOf(Hex(srows[i][0])), &d) != GMATH_OK ||
          std::string(d.digits) != srows[i][1] || std::to_string(d.exponent) != srows[i][2]) {
        bad++;
      }
    }
    int raised = std::fetestexcept(FE_ALL_EXCEPT);
    std::fesetround(FE_TONEAREST);
    EXPECT_EQ(bad, 0u) << "rounding mode " << mode;
    EXPECT_EQ(raised, 0) << "rounding mode " << mode;
  }
}

TEST(DecimalSpans, ADigitStringSplitAnywhereGivesTheSameResult) {
  const std::string digits = "31415926535897932384626433832795028841971693993751";
  double whole = 0;
  ASSERT_EQ(gmath_decimal_to_double(false, digits.data(), digits.size(), -49, &whole, nullptr), GMATH_OK);
  for (size_t cut = 0; cut <= digits.size(); ++cut) {
    double d = 0;
    unsigned flags = 0;
    ASSERT_EQ(gmath_decimal_round_spans(false, digits.data(), cut, digits.data() + cut, digits.size() - cut, -49,
                                        false, &d, &flags, nullptr),
              GMATH_OK);
    EXPECT_EQ(BitsOf(d), BitsOf(whole)) << cut;
  }
}

TEST(MathResult, EveryCodeHasItsOwnString) {
  std::vector<std::string> seen;
  for (int r = 0; r < GMATH_RESULT_COUNT; ++r) {
    const char * s = gmath_result_string(static_cast<GMATH_Result>(r));
    ASSERT_NE(s, nullptr);
    EXPECT_STRNE(s, "unknown result") << r;
    for (const auto & t : seen) {
      EXPECT_NE(t, s);
    }
    seen.push_back(s);
  }
  EXPECT_STREQ(gmath_result_string(GMATH_RESULT_COUNT), "unknown result");
  EXPECT_STREQ(gmath_result_string(static_cast<GMATH_Result>(-1)), "unknown result");
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
