/**
 * @file Exact Float decomposition/scaling references and caller-state
 * contracts. Copyright 2026 by Corey Pennycuff
 */
#include "test_helpers.h"
#include <array>
#include <cerrno>
#include <cfenv>
#include <charconv>
#include <climits>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <ghoti.io/math/basic.h>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {
constexpr uint32_t Sign = 0x80000000u, Inf = 0x7f800000u, NaN = 0x7fc00000u,
                   Hidden = 0x00800000u;
float Value(uint32_t word) {
  float x;
  std::memcpy(&x, &word, 4);
  return x;
}
uint32_t Bits(float x) {
  uint32_t word;
  std::memcpy(&word, &x, 4);
  return word;
}
int Signed(uint32_t word) {
  int32_t n;
  std::memcpy(&n, &word, 4);
  return n;
}
struct Entry {
  std::array<uint32_t, 9> w;
};
struct Environment {
  fenv_t saved;
  int error;
  Environment() : error(errno) {
    std::fegetenv(&saved);
  }
  ~Environment() {
    std::fesetenv(&saved);
    errno = error;
  }
};
uint64_t Number(const std::string & text, int base, size_t width = 0) {
  uint64_t result = 0;
  auto p =
      std::from_chars(text.data(), text.data() + text.size(), result, base);
  if (text.empty() || (width && text.size() != width) || p.ec != std::errc{} ||
      p.ptr != text.data() + text.size()) {
    throw std::runtime_error("invalid complete integer");
  }
  return result;
}
// Integer-to-Double conversion is exact (at most24bits). ldexp's Double result
// stays normal, including when reference scaling is clamped to+-700. All
// midpoint sums fit25bits, so these certificate comparisons are mode-safe.
double Magnitude(uint32_t raw) {
  uint32_t a = raw & ~Sign, field = a >> 23, sig = a & 0x7fffffu;
  if (field) {
    sig |= Hidden;
  }
  return std::ldexp(static_cast<double>(sig),
                    field ? static_cast<int>(field) - 150 : -149);
}
void Validate(const Entry & e) {
  const auto & w = e.w;
  uint32_t a = w[0] & ~Sign, r = w[2] & ~Sign, f = w[4] & ~Sign;
  bool snan = a > Inf && !(a & 0x00400000u);
  int exponent = Signed(w[5]), ilog = Signed(w[7]);
  if (w[6] != (snan ? 1u : 0u) || w[8] != (a == 0 || a >= Inf ? 1u : 0u)) {
    throw std::runtime_error("wrong special flags");
  }
  if (a >= Inf || !a) {
    uint32_t expected = a > Inf ? NaN : w[0];
    if (w[2] != expected || w[4] != expected || exponent != 0 ||
        w[3] != (snan ? 1u : 0u) || ilog != (a == 0 ? INT32_MIN : INT32_MAX)) {
      throw std::runtime_error("wrong special reference");
    }
    return;
  }
  if ((w[4] & Sign) != (w[0] & Sign) || f < 0x3f000000u || f >= 0x3f800000u ||
      exponent < -148 || exponent > 128 || ilog != exponent - 1 ||
      std::ldexp(Magnitude(w[4]), exponent) != Magnitude(w[0])) {
    throw std::runtime_error("wrong exact decomposition");
  }
  if ((w[2] & Sign) != (w[0] & Sign) || r > Inf) {
    throw std::runtime_error("wrong scaled sign/class");
  }
  int n = Signed(w[1]);
  int clamp = n > 700 ? 700 : (n < -700 ? -700 : n);
  double exact = std::ldexp(Magnitude(w[0]), clamp);
  if (r == Inf) {
    if (w[3] != 20 || exact < 0x1p128) {
      throw std::runtime_error("wrong overflow reference");
    }
    return;
  }
  double result = Magnitude(w[2]);
  bool inexact = result != exact;
  uint32_t flags = inexact ? (16u | (r < Hidden ? 8u : 0u)) : 0u;
  if (w[3] != flags) {
    throw std::runtime_error("wrong after-round scaling flags");
  }
  if (!inexact) {
    return;
  }
  if (r > Hidden) {
    throw std::runtime_error(
        "inexact normal scaling must be the minimum normal");
  }
  double low = r ? (Magnitude(r - 1) + result) * 0.5 : 0;
  double high = (result + Magnitude(r + 1)) * 0.5;
  if (exact < low || exact > high ||
      ((r & 1u) && (exact == low || exact == high))) {
    throw std::runtime_error("wrong ties-even target cell");
  }
}
std::vector<Entry> Parse(std::istream & input) {
  std::string line, extra;
  if (!std::getline(input, line) ||
      line != "# Pinned oracle: tools/oracle/gen_corpus_float_scale.py; MPFR "
              "4.2.2 gmpy2 2.3.2") {
    throw std::runtime_error("wrong provenance");
  }
  if (!std::getline(input, line) || line != "# function float_scale") {
    throw std::runtime_error("wrong function");
  }
  if (!std::getline(input, line)) {
    throw std::runtime_error("missing metadata");
  }
  std::istringstream meta(line);
  std::array<std::string, 9> fields;
  for (auto & field : fields) {
    if (!(meta >> field)) {
      throw std::runtime_error("missing metadata field");
    }
  }
  if (meta >> extra || fields[0] != "#" || fields[1] != "seed" ||
      fields[3] != "count" || fields[5] != "fresh" || fields[7] != "entries" ||
      (fields[6] != "False" && fields[6] != "True")) {
    throw std::runtime_error("wrong metadata labels");
  }
  (void)Number(fields[2], 10);
  if (Number(fields[4], 10) > 50000) {
    throw std::runtime_error("excessive requested count");
  }
  uint64_t count = Number(fields[8], 10);
  if (!count || count > 5000000) {
    throw std::runtime_error("invalid population");
  }
  if (!std::getline(input, line) ||
      line != "# raw x n scale flags fraction exponent flags ilogb flags") {
    throw std::runtime_error("wrong columns");
  }
  std::vector<Entry> rows;
  std::set<std::pair<uint32_t, uint32_t>> seen;
  while (std::getline(input, line)) {
    if (rows.size() >= count) {
      throw std::runtime_error("rows exceed declared population");
    }
    std::istringstream row(line);
    Entry e{};
    for (auto & word : e.w) {
      std::string text;
      if (!(row >> text)) {
        throw std::runtime_error("missing row field");
      }
      word = static_cast<uint32_t>(Number(text, 16, 8));
    }
    if (row >> extra || !seen.emplace(e.w[0], e.w[1]).second) {
      throw std::runtime_error("extra/duplicate row");
    }
    Validate(e);
    rows.push_back(e);
  }
  if (input.bad() || rows.size() != count) {
    throw std::runtime_error("population mismatch");
  }
  return rows;
}
std::vector<Entry> Load() {
  const char * override_directory = std::getenv("GMATH_FLOATSCALE_CORPUS_DIR");
  std::string directory = override_directory && *override_directory
                              ? override_directory
                              : "tests/corpus";
  std::ifstream input(directory + "/float_scale.corpus");
  if (!input) {
    throw std::runtime_error("missing Float scale corpus: " + directory);
  }
  auto rows = Parse(input);
  if (rows.size() < 10000) {
    throw std::runtime_error("insufficient Float scale sample");
  }
  std::set<std::pair<uint32_t, uint32_t>> needed = {{1, 0xffffffffu},
                                                    {3, 0xffffffffu},
                                                    {0xffffff, 0xffffffffu},
                                                    {0x800000, 0xffffffffu},
                                                    {0x3f800000, 0x80000000u},
                                                    {0x3f800000, 0x7fffffffu},
                                                    {0x7f800001, 0},
                                                    {NaN, 0},
                                                    {0, 0}};
  for (const auto & e : rows) {
    needed.erase({e.w[0], e.w[1]});
  }
  if (!needed.empty()) {
    throw std::runtime_error("missing essential Float scale cases");
  }
  std::printf("  float_scale: %zu reference entries from %s\n", rows.size(),
              directory.c_str());
  return rows;
}
int Flags(uint32_t flags) {
  return ((flags & 1u) ? FE_INVALID : 0) | ((flags & 4u) ? FE_OVERFLOW : 0) |
         ((flags & 8u) ? FE_UNDERFLOW : 0) | ((flags & 16u) ? FE_INEXACT : 0);
}
bool Check(const Entry & e, unsigned kind, int mode, int seed) {
  float x = Value(e.w[0]);
  int n = Signed(e.w[1]);
  EXPECT_EQ(std::fesetround(mode), 0);
  EXPECT_EQ(std::feclearexcept(FE_ALL_EXCEPT), 0);
  EXPECT_EQ(std::feraiseexcept(seed), 0);
  int incoming = std::fetestexcept(FE_ALL_EXCEPT);
  errno = 739;
  float output = 0;
  int exponent = 12345, integer = 0;
  if (kind == 0) {
    float (*volatile fn)(float, int) = gmath_scalbnf;
    output = fn(x, n);
  } else if (kind == 1) {
    float (*volatile fn)(float, int) = gmath_ldexpf;
    output = fn(x, n);
  } else if (kind == 2 || kind == 3) {
    float (*volatile fn)(float, int *) = gmath_frexpf;
    output = fn(x, kind == 2 ? &exponent : nullptr);
  } else {
    int (*volatile fn)(float) = gmath_ilogbf;
    integer = fn(x);
  }
  int error = errno, flags = std::fetestexcept(FE_ALL_EXCEPT),
      rounding = std::fegetround();
  uint32_t result = kind == 4 ? static_cast<uint32_t>(integer) : Bits(output);
  uint32_t expected = kind < 2 ? e.w[2] : (kind < 4 ? e.w[4] : e.w[7]);
  int added = Flags(kind < 2 ? e.w[3] : (kind < 4 ? e.w[6] : e.w[8]));
  EXPECT_EQ(result, expected)
      << std::hex << e.w[0] << "," << e.w[1] << " kind" << kind;
  EXPECT_EQ(flags, incoming | added)
      << std::hex << e.w[0] << "," << e.w[1] << " kind" << kind;
  if (kind == 2) {
    EXPECT_EQ(exponent, Signed(e.w[5]));
  }
  EXPECT_EQ(error, 739);
  EXPECT_EQ(rounding, mode);
  return result == expected && flags == (incoming | added) && error == 739 &&
         rounding == mode && (kind != 2 || exponent == Signed(e.w[5]));
}
std::string Fixture(const std::string & row, const std::string & count = "1") {
  return "# Pinned oracle: tools/oracle/gen_corpus_float_scale.py; MPFR 4.2.2 "
         "gmpy2 2.3.2\n# function float_scale\n# seed 1 count 0 fresh False "
         "entries " +
         count +
         "\n# raw x n scale flags fraction exponent flags ilogb flags\n" + row;
}
} // namespace
TEST(FloatScale, ExactReferencesAllModes) {
  Environment saved;
  std::vector<Entry> rows;
  ASSERT_NO_THROW(rows = Load());
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    for (const auto & e : rows) {
      for (unsigned kind = 0; kind < 5; ++kind) {
        if (!Check(e, kind, mode, 0)) {
          return;
        }
      }
    }
  }
}
TEST(FloatScale, RawBoundaryIncomingState) {
  Environment saved;
  std::vector<Entry> rows;
  ASSERT_NO_THROW(rows = Load());
  for (const auto & e : rows) {
    uint32_t a = e.w[0] & ~Sign;
    if (!(a == 0 || a == 1 || a == 3 || a == 5 || a == 0x7fffff ||
          a == Hidden || a == 0xffffff || a == 0x3f800000 || a >= Inf)) {
      continue;
    }
    int n = Signed(e.w[1]);
    if (!(n == -1 || n == 0 || n == 1 || n == INT32_MIN || n == INT32_MAX)) {
      continue;
    }
    for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
      for (int seed : {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
                       FE_INEXACT, FE_ALL_EXCEPT}) {
        for (unsigned kind = 0; kind < 5; ++kind) {
          if (!Check(e, kind, mode, seed)) {
            return;
          }
        }
      }
    }
  }
}
TEST(FloatScale, ParserRejectsMalformedAndIncorrectTargets) {
  Environment saved;
  const std::string row = "3f800000 00000000 3f800000 00000000 3f000000 "
                          "00000001 00000000 00000000 00000000\n";
  std::istringstream good(Fixture(row));
  EXPECT_NO_THROW(Parse(good));
  for (const auto & text :
       {Fixture(row + row), Fixture(row, "2"), Fixture(row.substr(1)),
        Fixture(row + "extra\n"), Fixture(""), Fixture(row, "-1")}) {
    std::istringstream bad(text);
    EXPECT_THROW(Parse(bad), std::runtime_error);
  }
  for (const auto & change : std::vector<std::pair<std::string, std::string>>{
           {"MPFR 4.2.2", "MPFR other"},
           {"function float_scale", "function wrong"},
           {"seed 1", "seed -1"},
           {"seed 1", "seed 18446744073709551616"},
           {"count 0", "count 50001"},
           {"fresh False", "fresh false"},
           {"entries 1", "entries 0"},
           {"entries 1", "entries 5000001"},
           {"entries 1", "entries 1 extra"},
           {"fraction exponent", "wrong exponent"},
           {"3f800000 00000000", "3f80000x 00000000"}}) {
    std::string text = Fixture(row);
    text.replace(text.find(change.first), change.first.size(), change.second);
    std::istringstream bad(text);
    EXPECT_THROW(Parse(bad), std::runtime_error);
  }
  for (const std::string text : {"00ffffff ffffffff 00800000 00000018 3f7fffff "
                                 "ffffff83 00000000 ffffff82 00000000\n",
                                 "00000001 ffffffff 00000001 00000018 3f000000 "
                                 "ffffff6c 00000000 ffffff6b 00000000\n",
                                 "7f800001 00000000 7fc00000 00000000 7fc00000 "
                                 "00000000 00000001 7fffffff 00000001\n",
                                 "3f800000 00000000 3f800000 00000000 3f000000 "
                                 "00000002 00000000 00000001 00000000\n"}) {
    std::istringstream bad(Fixture(text));
    EXPECT_THROW(Parse(bad), std::runtime_error);
  }
}
int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
