/**
 * @file Binary32 trig references and floating-environment contract.
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
#include <set>
#include <sstream>
#include <string>
#include <vector>

namespace {
constexpr uint32_t kSign = 0x80000000u;
constexpr uint32_t kInf = 0x7f800000u;
constexpr uint32_t kQuiet = 0x00400000u;
constexpr uint32_t kNaN = kInf | kQuiet;
uint32_t Bits(float x) {
  uint32_t word;
  std::memcpy(&word, &x, sizeof word);
  return word;
}
float Float(uint32_t word) {
  float x;
  std::memcpy(&x, &word, sizeof x);
  return x;
}
// Exactly widened binary32 representations are recognized from integer fields,
// including quiet-NaN payloads. No floating conversion can quiet a NaN or round
// a malformed corpus word before the loader rejects it.
bool NarrowExact(uint64_t word, uint32_t * output) {
  uint32_t sign = static_cast<uint32_t>(word >> 32) & kSign;
  unsigned field = static_cast<unsigned>((word >> 52) & 0x7ffu);
  uint64_t fraction = word & 0x000fffffffffffffull;
  constexpr uint64_t low_mask = (uint64_t(1) << 29) - 1;
  if (field == 0x7ffu) {
    if (fraction == 0) {
      *output = sign | kInf;
      return true;
    }
    if ((fraction & low_mask) != 0 || (fraction & 0x0008000000000000ull) == 0) {
      return false;
    }
    *output = sign | kInf | static_cast<uint32_t>(fraction >> 29);
    return true;
  }
  if (field == 0) {
    if (fraction != 0) {
      return false;
    }
    *output = sign;
    return true;
  }
  int exponent = static_cast<int>(field) - 1023;
  if (exponent > 127 || exponent < -149) {
    return false;
  }
  if (exponent >= -126) {
    if ((fraction & low_mask) != 0) {
      return false;
    }
    *output = sign | (static_cast<uint32_t>(exponent + 127) << 23) |
        static_cast<uint32_t>(fraction >> 29);
    return true;
  }
  uint64_t significand = (uint64_t(1) << 52) | fraction;
  unsigned shift = static_cast<unsigned>(-exponent - 97);
  if ((significand & ((uint64_t(1) << shift) - 1)) != 0) {
    return false;
  }
  *output = sign | static_cast<uint32_t>(significand >> shift);
  return true;
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

struct Function {
  const char * name;
  float (*fn)(float);
  bool cosine;
};
const Function kFunctions[] = {{"sinf", gmath_sinf, false},
    {"cosf", gmath_cosf, true}, {"tanf", gmath_tanf, false}};

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

bool HexWord(const std::string & text, size_t width, uint64_t * output) {
  if (text.size() != width) {
    return false;
  }
  for (char c : text) {
    if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) {
      return false;
    }
  }
  auto parsed = std::from_chars(text.data(), text.data() + text.size(), *output, 16);
  return parsed.ec == std::errc{} && parsed.ptr == text.data() + text.size();
}

bool PinnedProvenance(const std::string & line) {
  // The complete pinned header fixes field order, versions, and multiplicity.
  return line == "# Pinned oracle: tools/oracle/gen_corpus_floattrig.py; "
      "MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1";
}

struct Entry {
  uint32_t x, result, error;
};
std::vector<Entry> Load(const char * name) {
  const char * env = std::getenv("GMATH_FLOATTRIG_CORPUS_DIR");
  std::string directory = env && *env ? env : "tests/corpus";
  std::ifstream input(directory + "/" + name + ".corpus");
  EXPECT_TRUE(input.is_open()) << "missing " << name << " corpus";
  std::vector<Entry> entries;
  std::set<uint32_t> inputs;
  bool have_count = false, have_provenance = false, have_format = false;
  bool have_metadata = false;
  size_t declared_entries = 0;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty()) {
      continue;
    }
    if (line[0] == '#') {
      if (line.find("# Pinned oracle:") == 0) {
        EXPECT_FALSE(have_provenance) << "duplicate " << name << " provenance";
        EXPECT_TRUE(PinnedProvenance(line))
            << "invalid " << name << " pinned provenance: " << line;
        have_provenance = true;
      }
      if (line == "# binary32 inputs/results widened exactly to binary64; signed binary32 error in true binary32 ULP") {
        EXPECT_FALSE(have_format) << "duplicate " << name << " format";
        have_format = true;
      }
      if (line.find("# seed ") == 0) {
        EXPECT_FALSE(have_metadata) << "duplicate " << name << " sample metadata";
        std::istringstream metadata(line.substr(2));
        std::string seed_key, seed, count_key, count, fresh_key, fresh;
        std::string entries_key, entries_text, extra;
        bool valid = static_cast<bool>(metadata >> seed_key >> seed >> count_key >> count >>
            fresh_key >> fresh >> entries_key >> entries_text) && !(metadata >> extra);
        int64_t seed_number = 0;
        auto parsed_seed = std::from_chars(seed.data(), seed.data() + seed.size(), seed_number);
        size_t count_number = 0, entries_number = 0;
        valid = valid && seed_key == "seed" && count_key == "count" &&
            fresh_key == "fresh" && entries_key == "entries" &&
            parsed_seed.ec == std::errc{} && parsed_seed.ptr == seed.data() + seed.size() &&
            (count == "0" || PositiveInteger(count, &count_number)) &&
            (fresh == "False" || fresh == "True") &&
            PositiveInteger(entries_text, &entries_number);
        EXPECT_TRUE(valid) << "invalid " << name << " sample metadata: " << line;
        have_metadata = valid;
      }
      std::istringstream header(line.substr(1));
      std::string token;
      while (header >> token) {
        if (token == "entries") {
          EXPECT_FALSE(have_count) << "duplicate " << name << " entries header";
          have_count = true;
          std::string count;
          if (!(header >> count) || !PositiveInteger(count, &declared_entries)) {
            ADD_FAILURE() << "invalid " << name << " entries header: " << line;
          }
        }
      }
      continue;
    }
    std::string x, r, e, extra;
    std::istringstream parser(line);
    uint64_t xword = 0, rword = 0, eword = 0;
    if (!(parser >> x >> r >> e) || (parser >> extra) ||
        !HexWord(x, 16, &xword) || !HexWord(r, 16, &rword) ||
        !HexWord(e, 8, &eword)) {
      ADD_FAILURE() << "bad " << name << " corpus row: " << line;
      continue;
    }
    Entry entry{};
    entry.error = static_cast<uint32_t>(eword);
    if (!NarrowExact(xword, &entry.x) || !NarrowExact(rword, &entry.result)) {
      ADD_FAILURE() << "invalid " << name << " binary32 representation: " << line;
      continue;
    }
    uint32_t absolute = entry.x & ~kSign;
    uint32_t ra = entry.result & ~kSign;
    // Widened sNaNs cannot survive the file format. Results of nonfinite
    // arguments must be the canonical quiet NaN and carry zero error.
    if ((absolute >= kInf && (entry.result != kNaN || entry.error != 0)) ||
        (absolute < kInf && (ra > kInf ||
            (ra == kInf && (std::string(name) != "tanf" || entry.error != 0)))) ||
        (entry.error & ~kSign) > 0x3f800000u) {
      ADD_FAILURE() << "invalid " << name << " result/error word: " << line;
      continue;
    }
    if (!inputs.insert(entry.x).second) {
      ADD_FAILURE() << "duplicate " << name << " input word: " << x;
    }
    entries.push_back(entry);
  }
  EXPECT_TRUE(have_provenance) << "missing " << name << " pinned provenance";
  EXPECT_TRUE(have_format) << "missing " << name << " binary32 format header";
  EXPECT_TRUE(have_count) << "missing required " << name << " entries header";
  EXPECT_TRUE(have_metadata) << "missing " << name << " sample metadata";
  EXPECT_EQ(entries.size(), declared_entries) << name << " corpus count disagrees with header";
  size_t required = 1000;
  const char * minimum = std::getenv("GMATH_FLOATTRIG_MIN_ENTRIES");
  if (minimum != nullptr && !PositiveInteger(minimum, &required)) {
    ADD_FAILURE() << "GMATH_FLOATTRIG_MIN_ENTRIES must be a complete positive decimal integer";
  }
  EXPECT_GE(entries.size(), required) << "missing or truncated " << name << " corpus";
  return entries;
}

// The error's sign also matters when it rounded to signed zero: sin(2^-149)
// lies just below its rounded value, although its stored error is -0.
double TrueUlp(const Entry & entry) {
  uint32_t ra = entry.result & ~kSign;
  int exponent = static_cast<int>(ra >> 23) - 127;
  int ue = (exponent < -126 ? -126 : exponent) - 23;
  if (exponent > -126 && (ra & 0x007fffffu) == 0 &&
      ((entry.error ^ entry.result) & kSign) != 0) {
    --ue;
  }
  return std::ldexp(1.0, ue);
}

struct Interval {
  double low, high;
};
Interval ErrorCell(uint32_t word) {
  // A stored error is itself rounded to binary32. Preserve the entire closed
  // rounding cell; its midpoint and both neighbors are exact in binary64.
  if ((word & ~kSign) == 0) {
    double half_minimum = std::ldexp(1.0, -150);
    return word & kSign ? Interval{-half_minimum, 0} : Interval{0, half_minimum};
  }
  double center = static_cast<double>(Float(word));
  uint32_t below = word & kSign ? word + 1 : word - 1;
  uint32_t above = word & kSign ? word - 1 : word + 1;
  return {(static_cast<double>(Float(below)) + center) / 2,
      (static_cast<double>(Float(above)) + center) / 2};
}

double UlpError(float y, const Entry & entry) {
  uint32_t ya = Bits(y) & ~kSign, ra = entry.result & ~kSign;
  if (ra >= kInf || (entry.x & ~kSign) == 0) {
    return Bits(y) == entry.result ? 0 : std::numeric_limits<double>::infinity();
  }
  if (ya >= kInf) {
    return std::numeric_limits<double>::infinity();
  }
  double reference = static_cast<double>(Float(entry.result));
  return std::fabs((static_cast<double>(y) - reference) / TrueUlp(entry) -
      static_cast<double>(Float(entry.error)));
}

bool WithinOneUlp(float y, const Entry & entry) {
  uint32_t ya = Bits(y) & ~kSign, ra = entry.result & ~kSign;
  if (ra >= kInf || (entry.x & ~kSign) == 0) {
    return Bits(y) == entry.result;
  }
  if (ya >= kInf) {
    return false;
  }
  double reference = static_cast<double>(Float(entry.result));
  // Nearby binary32 values have an exact difference and exact power-of-two
  // scaling in binary64. Remote results cannot meet the contract.
  double distance = (static_cast<double>(y) - reference) / TrueUlp(entry);
  if (std::fabs(distance) > 2) {
    return false;
  }
  Interval error = ErrorCell(entry.error);
  // Compare endpoints to distance +/- 1 rather than subtracting a tiny error
  // from distance: at distance == +/-1 subtraction could erase an excess.
  return error.low >= distance - 1 && error.high <= distance + 1;
}

int SeedFlags(int seed) {
  std::feclearexcept(FE_ALL_EXCEPT);
  if (seed) {
    EXPECT_EQ(std::feraiseexcept(seed), 0);
  }
  return std::fetestexcept(FE_ALL_EXCEPT);
}
float CheckCall(const Function & function, uint32_t input, int mode, int seed = 0) {
  // Keep the raw input local. A float-returning bit constructor can quiet an
  // sNaN in an i686 x87 return register before the function receives it.
  float argument;
  std::memcpy(&argument, &input, sizeof argument);
  int existing = SeedFlags(seed);
  errno = E2BIG;
  float result = function.fn(argument);
  int got_errno = errno, got_mode = std::fegetround();
  int flags = std::fetestexcept(FE_ALL_EXCEPT);
  uint32_t a = input & ~kSign, r = Bits(result) & ~kSign;
  int required = 0, allowed = 0;
  if (a >= kInf) {
    required = a == kInf || (a & kQuiet) == 0 ? FE_INVALID : 0;
    allowed = required;
  }
  else if (a != 0) {
    allowed = FE_INEXACT;
    if ((!function.cosine && a < 0x00800000u) || r < 0x00800000u) {
      required = FE_UNDERFLOW | FE_INEXACT;
      allowed |= required;
    }
    if (std::string(function.name) == "tanf" && r == kInf) {
      required = FE_OVERFLOW | FE_INEXACT;
      allowed |= required;
    }
  }
  if (a < kInf) {
    if (std::string(function.name) == "tanf") {
      EXPECT_LE(r, kInf) << function.name << " finite input produced NaN " << std::hex << input;
      if (r == kInf) {
        EXPECT_NE(flags & FE_OVERFLOW, 0)
            << function.name << " infinite output without overflow " << std::hex << input;
      }
    }
    else {
      EXPECT_LT(r, kInf) << function.name << " finite input produced nonfinite result " << std::hex << input;
    }
    // For 0 < |x| <= 1, sin and tan cannot vanish, and cos is at least
    // cos(1) > 1/2. This checks result classification in every mode without
    // imposing a directed-rounding accuracy promise.
    if (a != 0 && a <= 0x3f800000u) {
      EXPECT_NE(r, 0u) << function.name << " safe nonzero input produced zero " << std::hex << input;
    }
  }
  EXPECT_EQ(got_errno, E2BIG) << function.name;
  EXPECT_EQ(got_mode, mode) << function.name;
  EXPECT_EQ(flags & (required | existing), required | existing)
      << function.name << " missing required flags input " << std::hex << input;
  EXPECT_EQ(flags & ~(allowed | existing), 0)
      << function.name << " unexpected flags input " << std::hex << input;
  return result;
}

std::vector<uint32_t> SpecialValues() {
  std::vector<uint32_t> values = {0, kSign, kInf, kInf | kSign};
  for (uint32_t payload : {1u, kQuiet - 1, kQuiet, kQuiet + 1,
           (kQuiet << 1) - 1, 0x12345u, kQuiet | 0x12345u}) {
    values.push_back(kInf | payload);
    values.push_back(kSign | kInf | payload);
  }
  return values;
}
std::vector<uint32_t> StateValues() {
  auto values = SpecialValues();
  const uint32_t positive[] = {1, 2, 3, 0x003fffff, 0x00400000, 0x007ffffe,
      0x007fffff, 0x00800000, 0x00800001, 0x39800000, 0x3f000000,
      0x3f7fffff, 0x3f800000, 0x3f800001, 0x3fc90fda, 0x3fc90fdb,
      0x3fc90fdc, 0x40490fdb, 0x49800000, 0x4e800000, kInf - 1};
  for (uint32_t word : positive) {
    values.push_back(word);
    values.push_back(word | kSign);
  }
  return values;
}
} // namespace

TEST(Floattrig, CorpusIsWithinOneUlp) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  for (const auto & function : kFunctions) {
    double worst = 0;
    uint32_t worst_input = 0;
    size_t failures = 0;
    auto entries = Load(function.name);
    for (const auto & entry : entries) {
      float result = CheckCall(function, entry.x, FE_TONEAREST);
      double error = UlpError(result, entry);
      if (error > worst) {
        worst = error;
        worst_input = entry.x;
      }
      if (!WithinOneUlp(result, entry) && ++failures <= 5) {
        ADD_FAILURE() << function.name << " input " << std::hex << entry.x
                      << " is " << std::dec << error << " ulp from exact (error cell does not certify one ulp)";
      }
    }
    std::printf("  %s: %zu corpus entries, max error %.8f ulp (input bits %08x)\n",
        function.name, entries.size(), worst, worst_input);
    EXPECT_EQ(failures, 0u) << function.name;
    // The kernel's analytical allowance is below .505 ULP; the large pinned
    // soak measured at most .50212651. Leave a margin while catching drift.
    EXPECT_LE(worst, 0.51) << function.name << " accuracy regression";
  }
}

TEST(Floattrig, RawSpecialsInEveryMode) {
  Environment saved;
  for (int mode : {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (const auto & function : kFunctions) {
      for (uint32_t input : SpecialValues()) {
        uint32_t expected = (input & ~kSign) >= kInf ? kNaN :
            (function.cosine ? 0x3f800000u : input);
        EXPECT_EQ(Bits(CheckCall(function, input, mode)), expected)
            << function.name << " special input " << std::hex << input;
      }
    }
  }
}

TEST(Floattrig, TinyResultsRequireUnderflow) {
  Environment saved;
  std::set<uint32_t> words;
  for (uint32_t i = 1; i <= 1024; ++i) {
    words.insert(i);
    words.insert(0x00800000u - i);
  }
  for (unsigned length = 1; length <= 23; ++length) {
    uint32_t pivot = 1u << (length - 1);
    for (uint32_t word : {pivot, pivot + 1, (1u << length) - 1}) {
      words.insert(word);
    }
  }
  for (int mode : {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (const auto & function : kFunctions) {
      for (uint32_t word : words) {
        for (uint32_t sign : {0u, kSign}) {
          uint32_t input = word | sign;
          uint32_t expected = function.cosine ? 0x3f800000u : input;
          EXPECT_EQ(Bits(CheckCall(function, input, mode)), expected)
              << function.name << " tiny input " << std::hex << input;
        }
      }
    }
  }
}

TEST(Floattrig, ErrnoModeAndEveryIncomingFlagArePreserved) {
  Environment saved;
  for (int mode : {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (int seed : {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
             FE_INEXACT, FE_ALL_EXCEPT}) {
      for (const auto & function : kFunctions) {
        for (uint32_t input : StateValues()) {
          (void)CheckCall(function, input, mode, seed);
        }
      }
    }
  }
}

TEST(Floattrig, SymmetryIsExact) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  uint32_t state = 0x9e3779b9u;
  for (int i = 0; i < 20000; ++i) {
    state = state * 1664525u + 1013904223u;
    uint32_t positive = state & ~kSign;
    if (positive >= kInf) {
      continue;
    }
    for (const auto & function : kFunctions) {
      uint32_t p = Bits(CheckCall(function, positive, FE_TONEAREST));
      uint32_t n = Bits(CheckCall(function, positive | kSign, FE_TONEAREST));
      EXPECT_EQ(n, function.cosine ? p : p ^ kSign)
          << function.name << " symmetry input " << std::hex << positive;
    }
  }
}

TEST(Floattrig, OneSeamHasMonotoneDerivativeBoundedGaps) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  for (uint32_t sign : {0u, kSign}) {
    // Three adjacent pairs straddle both fast-path seams. Order by numerical
    // value, which reverses the magnitude words for the negative seam.
    const uint32_t magnitude[] = {0x3f7ffffe, 0x3f7fffff, 0x3f800000, 0x3f800001};
    for (const auto & function : kFunctions) {
      for (unsigned i = 0; i < 3; ++i) {
        unsigned left_index = sign ? 3 - i : i;
        unsigned right_index = sign ? 2 - i : i + 1;
        uint32_t left = magnitude[left_index] | sign;
        uint32_t right = magnitude[right_index] | sign;
        double xgap = static_cast<double>(Float(right)) - static_cast<double>(Float(left));
        float lower = CheckCall(function, left, FE_TONEAREST);
        float upper = CheckCall(function, right, FE_TONEAREST);
        double gap = static_cast<double>(upper) - static_cast<double>(lower);
        bool increasing = !function.cosine || sign != 0;
        EXPECT_GE(increasing ? gap : -gap, 0.0)
            << function.name << " nonmonotone at seam " << std::hex << left;
        // |sin'|, |cos'| <= 1; tan' < 4 in this neighborhood.
        // Each endpoint receives one binary32 ULP of contract allowance.
        auto ulp = [](float result) {
          uint32_t absolute = Bits(result) & ~kSign;
          int exponent = static_cast<int>(absolute >> 23) - 127;
          return std::ldexp(1.0, (exponent < -126 ? -126 : exponent) - 23);
        };
        double derivative = std::string(function.name) == "tanf" ? 4 : 1;
        EXPECT_LE(std::fabs(gap), derivative * xgap + ulp(lower) + ulp(upper))
            << function.name << " excessive seam gap " << std::hex << left;
      }
    }
  }
}

TEST(Floattrig, OneUlpDecisionContainsTheEntireErrorCell) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  // Infinitesimal excesses must not disappear when the error was rounded to
  // signed zero. All these distances are exactly +/-1 in true ULP units.
  EXPECT_FALSE(WithinOneUlp(Float(0x3f800002), {1, 0x3f800001, kSign}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f800000), {1, 0x3f800001, kSign}));
  EXPECT_FALSE(WithinOneUlp(Float(0x3f800000), {1, 0x3f800001, 0}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f800002), {1, 0x3f800001, 0}));
  // At +/-0.5 an error cell straddles the one-ULP boundary. The adjacent
  // error word toward zero certifies the same candidate, while the tie cell
  // itself cannot. Both sides of a binade boundary are covered.
  EXPECT_FALSE(WithinOneUlp(Float(0x3f7fffff), {1, 0x3f800000, 0x3f000000}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f7fffff), {1, 0x3f800000, 0x3effffff}));
  EXPECT_FALSE(WithinOneUlp(Float(0xbf7fffff), {1, 0xbf800000, 0xbf000000}));
  EXPECT_TRUE(WithinOneUlp(Float(0xbf7fffff), {1, 0xbf800000, 0xbeffffff}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f800000), {0, 0x3f800000, 0}));
  EXPECT_FALSE(WithinOneUlp(Float(0x3f800001), {0, 0x3f800000, 0}));
  EXPECT_FALSE(WithinOneUlp(Float(kSign), {0, 0, 0}));
  EXPECT_FALSE(WithinOneUlp(Float(kNaN | 1), {kInf, kNaN, 0}));
  Interval positive = ErrorCell(0x3f000000), negative = ErrorCell(0xbf000000);
  EXPECT_LT(positive.low, 0.5);
  EXPECT_GT(positive.high, 0.5);
  EXPECT_LT(negative.low, -0.5);
  EXPECT_GT(negative.high, -0.5);
  EXPECT_DOUBLE_EQ(ErrorCell(0).low, 0);
  EXPECT_DOUBLE_EQ(ErrorCell(kSign).high, 0);
  EXPECT_DOUBLE_EQ(ErrorCell(0).high, std::ldexp(1.0, -150));
  EXPECT_DOUBLE_EQ(ErrorCell(kSign).low, -std::ldexp(1.0, -150));
}

TEST(Floattrig, ErrorUsesTrueBinadeAndSubnormalSpacing) {
  EXPECT_DOUBLE_EQ(UlpError(Float(0x3f800000), {0x3f800000, 0x3f800000, 0xbe800000}), 0.25);
  EXPECT_DOUBLE_EQ(UlpError(Float(0x3f7fffff), {0x3f800000, 0x3f800000, 0xbe800000}), 0.75);
  EXPECT_DOUBLE_EQ(UlpError(Float(0xbf7fffff), {0xbf800000, 0xbf800000, 0x3e800000}), 0.75);
  EXPECT_DOUBLE_EQ(UlpError(Float(0x3f800001), {0x3f800000, 0x3f800000, 0x3e800000}), 0.75);
  EXPECT_DOUBLE_EQ(UlpError(Float(2), {1, 1, kSign}), 1.0);
  EXPECT_DOUBLE_EQ(UlpError(Float(0x00800000), {1, 0x007fffff, 0x3e800000}), 0.75);
  EXPECT_DOUBLE_EQ(UlpError(Float(0x3f7fffff), {1, 0x3f800000, kSign}), 1.0);
}

TEST(Floattrig, CorpusWordAndCountParsersAreStrict) {
  const std::string prefix = "# Pinned oracle: tools/oracle/gen_corpus_floattrig.py; ";
  EXPECT_TRUE(PinnedProvenance(prefix + "MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1"));
  for (const char * bad : {"MPFR ", "MPFR 4.2.1 gmpy2 2.3.2 mpmath 1.4.1",
           "MPFR 4.2.2 gmpy2 2.3.1 mpmath 1.4.1",
           "MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.0",
           "MPFR 4.2.2 gmpy2 2.3.2", "MPFR 4.2.2 mpmath 1.4.1",
           "MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1 mpmath 1.4.1"}) {
    EXPECT_FALSE(PinnedProvenance(prefix + bad));
  }
  uint32_t narrow = 0;
  for (uint64_t invalid : {1ull, 0x3ff0000000000001ull, 0x3690000000000000ull,
           0x47f0000000000000ull, 0x7ff8000000000001ull,
           0x7ff0000020000000ull}) {
    EXPECT_FALSE(NarrowExact(invalid, &narrow));
  }
  EXPECT_TRUE(NarrowExact(0x36a0000000000000ull, &narrow));
  EXPECT_EQ(narrow, 1u);
  uint64_t word = 0;
  EXPECT_TRUE(HexWord("0000000000000001", 16, &word));
  EXPECT_EQ(word, 1u);
  for (const char * bad : {"1", "000000000000000g", "000000000000000A",
           "+000000000000001", " 000000000000001"}) {
    EXPECT_FALSE(HexWord(bad, 16, &word));
  }
  size_t count = 0;
  EXPECT_TRUE(PositiveInteger("1", &count));
  EXPECT_TRUE(PositiveInteger(std::to_string(std::numeric_limits<size_t>::max()), &count));
  for (const char * bad : {"", "0", "-1", "+1", " 1", "1 ", "1junk", "junk"}) {
    EXPECT_FALSE(PositiveInteger(bad, &count));
  }
  EXPECT_FALSE(PositiveInteger(std::to_string(std::numeric_limits<size_t>::max()) + "0", &count));
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
