/**
 * @file Binary32 exp2 pinned references and strict corpus format.
 * Copyright 2026 by Corey Pennycuff
 */
#include "test_helpers.h"
#include <ghoti.io/math/elementary.h>
#include <algorithm>
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
#include <iterator>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

namespace {
constexpr uint32_t kSign = 0x80000000u;
constexpr uint32_t kInf = 0x7f800000u;
constexpr uint32_t kQuiet = 0x00400000u;
constexpr uint32_t kNaN = kInf | kQuiet;
constexpr uint32_t kOne = 0x3f800000u;
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
  return line == "# Pinned oracle: tools/oracle/gen_corpus_exp2f.py; "
      "MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1";
}

struct Entry {
  uint32_t x, result, error;
};

bool SampleMetadata(const std::string & line, size_t * entries) {
  std::istringstream parser(line);
  std::string marker, seed_key, seed, count_key, count, fresh_key, fresh;
  std::string entries_key, entry_text, extra;
  if (!(parser >> marker >> seed_key >> seed >> count_key >> count >>
          fresh_key >> fresh >> entries_key >> entry_text) || (parser >> extra)) {
    return false;
  }
  int64_t seed_number = 0;
  auto parsed_seed = std::from_chars(seed.data(), seed.data() + seed.size(), seed_number);
  size_t count_number = 0;
  return marker == "#" && seed_key == "seed" && count_key == "count" &&
      fresh_key == "fresh" && entries_key == "entries" &&
      parsed_seed.ec == std::errc{} && parsed_seed.ptr == seed.data() + seed.size() &&
      (count == "0" || PositiveInteger(count, &count_number)) &&
      (fresh == "False" || fresh == "True") && PositiveInteger(entry_text, entries);
}

bool IntegerInput(uint32_t word, int * output) {
  uint32_t a = word & ~kSign;
  if (a == 0) { *output = 0; return true; }
  int exponent = static_cast<int>(a >> 23) - 127;
  if (exponent < 0 || exponent > 7) return false;
  unsigned shift = static_cast<unsigned>(23 - exponent);
  uint32_t significand = (a & 0x007fffffu) | 0x00800000u;
  if ((significand & ((1u << shift) - 1u)) != 0) return false;
  int n = static_cast<int>(significand >> shift);
  *output = word & kSign ? -n : n;
  return true;
}

int RequiredFlags(uint32_t word) {
  uint32_t a = word & ~kSign;
  if (a > kInf) return (a & kQuiet) ? 0 : FE_INVALID;
  if (a == kInf || a == 0) return 0;
  if ((word & kSign) == 0 && a >= 0x43000000u) return FE_OVERFLOW | FE_INEXACT;
  if ((word & kSign) != 0 && a >= 0x43160000u) return FE_UNDERFLOW | FE_INEXACT;
  int n;
  if (IntegerInput(word, &n)) return 0;
  return FE_INEXACT | ((word & kSign) && a > 0x42fc0000u ? FE_UNDERFLOW : 0);
}

bool ValidResult(const Entry & entry) {
  uint32_t absolute = entry.x & ~kSign;
  if (absolute > kInf) return entry.result == kNaN && entry.error == 0;
  if (absolute == kInf) {
    return entry.result == ((entry.x & kSign) ? 0u : kInf) && entry.error == 0;
  }
  if (absolute == 0) return entry.result == kOne && entry.error == 0;
  if ((entry.result & kSign) != 0 || entry.result > kInf ||
      (entry.error & ~kSign) > 0x3f000000u) return false;
  // Positive finite x>=128 explicitly overflows. Negative finite x<=-150
  // explicitly returns +0, although its signed true-value error can be nonzero.
  bool overflow = (entry.x & kSign) == 0 && absolute >= 0x43000000u;
  bool zero_tail = (entry.x & kSign) != 0 && absolute >= 0x43160000u;
  if (overflow) return entry.result == kInf && entry.error == 0;
  if (zero_tail) {
    if (entry.result != 0 || (entry.error & kSign) != 0) return false;
    if (absolute == 0x43160000u) return entry.error == 0x3f000000u;
    if (absolute >= 0x43960000u) return entry.error == 0; // x<=-300
    return true;
  }
  int integer;
  if (IntegerInput(entry.x, &integer)) {
    uint32_t expected = integer >= -126 ? static_cast<uint32_t>(integer + 127) << 23 :
        1u << static_cast<unsigned>(integer + 149);
    return entry.result == expected && entry.error == 0;
  }
  return entry.result != 0 && entry.result < kInf;
}

bool ParseRow(const std::string & line, Entry * entry) {
  std::istringstream parser(line);
  std::string x, result, error, extra;
  uint64_t xword = 0, rword = 0, eword = 0;
  if (!(parser >> x >> result >> error) || (parser >> extra) ||
      !HexWord(x, 16, &xword) || !HexWord(result, 16, &rword) ||
      !HexWord(error, 8, &eword) || !NarrowExact(xword, &entry->x) ||
      !NarrowExact(rword, &entry->result)) return false;
  entry->error = static_cast<uint32_t>(eword);
  return ValidResult(*entry);
}

// The stream parser returns a diagnostic instead of emitting gtest failures,
// so malformed in-memory fixtures exercise exactly the production loader.
bool ParseCorpus(std::istream & input, size_t minimum,
    std::vector<Entry> * entries, std::string * reason) {
  entries->clear();
  std::set<uint32_t> inputs;
  bool provenance = false, function = false, metadata = false, format = false;
  size_t declared = 0;
  const std::string expected_format = "# binary32 inputs/results widened exactly to binary64; signed binary32 error in true binary32 ULP";
  auto fail = [&](const std::string & message) {
    *reason = message;
    return false;
  };
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty()) continue;
    if (line[0] == '#') {
      if (line.find("# Pinned oracle:") == 0) {
        if (provenance) return fail("duplicate exp2f provenance");
        if (!PinnedProvenance(line)) return fail("invalid exp2f pinned provenance");
        provenance = true;
      }
      else if (line.find("# function") == 0) {
        if (function) return fail("duplicate exp2f function header");
        if (line != "# function exp2f") return fail("invalid exp2f function header");
        function = true;
      }
      else if (line.find("# seed") == 0) {
        if (metadata) return fail("duplicate exp2f sample metadata");
        if (!SampleMetadata(line, &declared)) return fail("invalid exp2f sample metadata");
        metadata = true;
      }
      else if (line.find("# binary32") == 0) {
        if (format) return fail("duplicate exp2f format header");
        if (line != expected_format) return fail("invalid exp2f binary32 format header");
        format = true;
      }
      continue;
    }
    if (!provenance || !function || !metadata || !format) {
      return fail("missing required exp2f corpus metadata before data");
    }
    Entry entry{};
    if (!ParseRow(line, &entry)) return fail("bad exp2f corpus row or binary32 representation: " + line);
    if (!inputs.insert(entry.x).second) return fail("duplicate exp2f input word");
    entries->push_back(entry);
  }
  if (input.bad()) return fail("cannot read exp2f corpus");
  if (!provenance || !function || !metadata || !format) return fail("missing required exp2f corpus metadata");
  if (entries->size() != declared) return fail("exp2f corpus count disagrees with header");
  if (entries->size() < minimum) return fail("missing or truncated exp2f corpus");
  return true;
}

std::vector<Entry> Load() {
  const char * env = std::getenv("GMATH_EXP2F_CORPUS_DIR");
  std::string directory = env && *env ? env : "tests/corpus";
  std::ifstream input(directory + "/exp2f.corpus");
  std::vector<Entry> entries;
  if (!input.is_open()) {
    ADD_FAILURE() << "missing exp2f corpus: " << directory;
    return entries;
  }
  size_t minimum = 1000;
  const char * required = std::getenv("GMATH_EXP2F_MIN_ENTRIES");
  if (required != nullptr && !PositiveInteger(required, &minimum)) {
    ADD_FAILURE() << "GMATH_EXP2F_MIN_ENTRIES must be a complete positive decimal integer";
    return entries;
  }
  std::string reason;
  std::string payload((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
  if (input.bad()) { ADD_FAILURE() << "cannot read exp2f corpus"; return entries; }
  std::istringstream stream(payload);
  if (!ParseCorpus(stream, minimum, &entries, &reason)) {
    ADD_FAILURE() << reason;
    entries.clear();
  }
  if (!entries.empty() && (!env || !*env) &&
      payload.find("\n# seed 20261027 count 3000 fresh False entries 26220\n") == std::string::npos) {
    ADD_FAILURE() << "incorrect committed exp2f sample metadata";
    entries.clear();
  }
  std::set<uint32_t> present;
  for (const auto & entry : entries) present.insert(entry.x);
  bool complete = true;
  auto require = [&](uint32_t word) { complete = complete && present.count(word) != 0; };
  for (uint32_t word : {0u, kSign, kInf, kInf|kSign, kNaN, kNaN|kSign|7u,
      0xc3160000u, 0x43000000u, 0xc2fc0000u,
      0x32800000u, 0xb2800000u, 0xb338aa3bu, 0x33b8aa3bu}) {
    require(word);
  }
  for (int n = -149; n <= 127; ++n) require(Bits(static_cast<float>(n)));
  for (uint32_t center : {0xc3160000u, 0xc3150000u, 0xc2fc0000u, 0x43000000u,
                          0x32800000u, 0xb2800000u}) {
    for (int delta = -2; delta <= 2; ++delta) require(center + static_cast<uint32_t>(delta));
  }
  if (!entries.empty() && !complete) {
    ADD_FAILURE() << "missing essential exp2f coverage";
    entries.clear();
  }
  return entries;
}

// Signed error distinguishes an exact value below a rounded binade boundary,
// including a negative error which itself rounded to negative zero.
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
  if (ra >= kInf || (entry.x & ~kSign) >= kInf || (entry.x & ~kSign) == 0) {
    return Bits(y) == entry.result ? 0 : std::numeric_limits<double>::infinity();
  }
  if (ya >= kInf || (Bits(y) & kSign) != 0) {
    return std::numeric_limits<double>::infinity();
  }
  double reference = static_cast<double>(Float(entry.result));
  double distance = (static_cast<double>(y) - reference) / TrueUlp(entry);
  Interval cell = ErrorCell(entry.error);
  return std::max(std::fabs(distance - cell.low), std::fabs(distance - cell.high));
}

bool WithinOneUlp(float y, const Entry & entry) {
  uint32_t ya = Bits(y) & ~kSign, ra = entry.result & ~kSign;
  if (ra >= kInf || (entry.x & ~kSign) >= kInf || (entry.x & ~kSign) == 0) {
    return Bits(y) == entry.result;
  }
  if (ya >= kInf || (Bits(y) & kSign) != 0 || (ra == 0 && Bits(y) != 0)) {
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

std::string Fixture(const std::string & rows, const std::string & count = "1") {
  return "# Pinned oracle: tools/oracle/gen_corpus_exp2f.py; MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1\n"
      "# function exp2f\n# seed 20261027 count 0 fresh False entries " + count +
      "\n# binary32 inputs/results widened exactly to binary64; signed binary32 error in true binary32 ULP\n" + rows;
}
} // namespace

TEST(Exp2f, CorpusIsWithinOneUlp) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  auto entries = Load();
  ASSERT_FALSE(entries.empty());
  double worst = 0;
  uint32_t worst_input = 0;
  size_t failures = 0;
  for (const Entry & entry : entries) {
    float argument;
    std::memcpy(&argument, &entry.x, sizeof argument);
    ASSERT_EQ(std::feclearexcept(FE_ALL_EXCEPT), 0);
    errno = 713;
    float (*volatile fn)(float) = gmath_exp2f;
    volatile float result = fn(argument);
    int flags = std::fetestexcept(FE_ALL_EXCEPT);
    int error_number = errno;
    int mode = std::fegetround();
    EXPECT_EQ(flags, RequiredFlags(entry.x)) << std::hex << entry.x;
    EXPECT_EQ(error_number, 713);
    EXPECT_EQ(mode, FE_TONEAREST);
    double error = UlpError(result, entry);
    if (error > worst) {
      worst = error;
      worst_input = entry.x;
    }
    if (!WithinOneUlp(result, entry) && ++failures <= 5) {
      ADD_FAILURE() << "exp2f input " << std::hex << entry.x << " is " << std::dec
                    << error << " ulp from exact (error cell does not certify one ulp)";
    }
  }
  std::printf("  exp2f: %zu corpus entries, max error %.8f ulp (input bits %08x)\n",
      entries.size(), worst, worst_input);
  EXPECT_EQ(failures, 0u);
  EXPECT_LE(worst, 0.51) << "exp2f accuracy regression";
}

TEST(Exp2f, ErrorCellsPreserveTinyAndBinadeUncertainty) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  EXPECT_FALSE(WithinOneUlp(Float(0x3f800002), {1, 0x3f800001, kSign}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f800000), {1, 0x3f800001, kSign}));
  EXPECT_FALSE(WithinOneUlp(Float(0x3f800000), {1, 0x3f800001, 0}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f800002), {1, 0x3f800001, 0}));
  EXPECT_FALSE(WithinOneUlp(Float(0x3f7fffff), {1, 0x3f800000, 0x3f000000}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f7fffff), {1, 0x3f800000, 0x3effffff}));
  EXPECT_DOUBLE_EQ(UlpError(0.0f, {0xc3160000, 0, 0x3f000000}), 0.5 + 0x1p-25);
  EXPECT_TRUE(WithinOneUlp(0.0f, {0xc3160000, 0, 0x3f000000}));
  EXPECT_FALSE(WithinOneUlp(Float(1), {0xc3160000, 0, 0x3f000000}));
  EXPECT_FALSE(WithinOneUlp(Float(kSign), {0xc3160000, 0, 0x3f000000}));
  EXPECT_DOUBLE_EQ(UlpError(Float(0x00800000), {1, 0x007fffff, 0x3e800000}), 0.75 + 0x1p-27);
  EXPECT_DOUBLE_EQ(UlpError(Float(0x3f7fffff), {1, kOne, kSign}), 1.0);
  EXPECT_FALSE(WithinOneUlp(Float(kNaN | 1), {kInf | 1, kNaN, 0}));
  EXPECT_FALSE(WithinOneUlp(Float(kInf | kSign), {kInf, kInf, 0}));
  EXPECT_DOUBLE_EQ(ErrorCell(0).low, 0);
  EXPECT_DOUBLE_EQ(ErrorCell(kSign).high, 0);
  EXPECT_DOUBLE_EQ(ErrorCell(0).high, std::ldexp(1.0, -150));
  EXPECT_DOUBLE_EQ(ErrorCell(kSign).low, -std::ldexp(1.0, -150));
  EXPECT_LT(ErrorCell(0x3f000000).low, 0.5);
  EXPECT_GT(ErrorCell(0x3f000000).high, 0.5);
  EXPECT_LT(ErrorCell(0xbf000000).low, -0.5);
  EXPECT_GT(ErrorCell(0xbf000000).high, -0.5);
}

TEST(Exp2f, LoadFixturesRequirePinnedMetadataAndUniqueExactWords) {
  const std::string row = "0000000000000000 3ff0000000000000 00000000\n";
  std::vector<Entry> entries;
  std::string reason;
  auto parse = [&](const std::string & text, size_t minimum = 1) {
    std::istringstream input(text);
    return ParseCorpus(input, minimum, &entries, &reason);
  };
  ASSERT_TRUE(parse(Fixture(row))) << reason;
  EXPECT_EQ(entries.size(), 1u);
  EXPECT_FALSE(parse(Fixture(row), 2));
  EXPECT_FALSE(parse(Fixture(row, "2")));
  EXPECT_FALSE(parse(Fixture(row + row, "2")));
  EXPECT_FALSE(parse(Fixture(row, "1junk")));
  EXPECT_FALSE(parse(Fixture(row, "0")));
  EXPECT_FALSE(parse(Fixture("0000000000000001 3ff0000000000000 00000000\n")));
  EXPECT_FALSE(parse(Fixture("0000000000000000 3ff0000000000001 00000000\n")));
  EXPECT_FALSE(parse(Fixture("0000000000000000 3ff0000000000000 000000000\n")));
  EXPECT_FALSE(parse(Fixture("0000000000000000 3ff0000000000000 00000000 extra\n")));
  EXPECT_FALSE(parse(Fixture("0000000000000000 bff0000000000000 00000000\n")));
  EXPECT_FALSE(parse(Fixture(row) + "# function exp2f\n"));
  EXPECT_FALSE(parse(Fixture(row) + "# seed 1 count 0 fresh False entries 1\n"));
  EXPECT_FALSE(parse(Fixture(row) + "# binary32 inputs/results widened exactly to binary64; signed binary32 error in true binary32 ULP\n"));
  const std::string valid = Fixture(row);
  for (const auto & replacement : std::vector<std::pair<std::string, std::string>>{
           {"MPFR 4.2.2", "MPFR 4.2.1"}, {"gmpy2 2.3.2", "gmpy2 2.3.1"},
           {"mpmath 1.4.1", ""}, {"mpmath 1.4.1", "mpmath 1.4.1 mpmath 1.4.1"},
           {"# function exp2f", "# function exp2"}, {"fresh False", "fresh maybe"},
           {"count 0", "count 0junk"}, {"seed 20261027", "seed 20261027junk"}}) {
    std::string bad = valid;
    bad.replace(bad.find(replacement.first), replacement.first.size(), replacement.second);
    EXPECT_FALSE(parse(bad)) << replacement.first;
  }
  for (const std::string & header : {std::string("# Pinned oracle:"),
           std::string("# function"), std::string("# seed"), std::string("# binary32")}) {
    std::string bad = valid;
    size_t begin = bad.find(header), end = bad.find('\n', begin);
    bad.erase(begin, end - begin + 1);
    EXPECT_FALSE(parse(bad)) << header;
  }
  EXPECT_FALSE(parse(Fixture(row) + valid.substr(0, valid.find('\n') + 1)));
  EXPECT_TRUE(parse(Fixture("c062c00000000000 0000000000000000 3f000000\n"))) << reason;
  EXPECT_TRUE(parse(Fixture("7ff0000000000000 7ff0000000000000 00000000\n"))) << reason;
  EXPECT_TRUE(parse(Fixture("fff0000000000000 0000000000000000 00000000\n"))) << reason;
  EXPECT_TRUE(parse(Fixture("7ff8000000000000 7ff8000000000000 00000000\n"))) << reason;
}

TEST(Exp2f, WordAndCountParsersRejectPartialAndOutOfRangeText) {
  uint32_t word32 = 0;
  for (uint64_t invalid : {1ull, 0x3ff0000000000001ull, 0x3690000000000000ull,
           0x47f0000000000000ull, 0x7ff8000000000001ull, 0x7ff0000020000000ull}) {
    EXPECT_FALSE(NarrowExact(invalid, &word32));
  }
  EXPECT_TRUE(NarrowExact(0x36a0000000000000ull, &word32));
  EXPECT_EQ(word32, 1u);
  uint64_t word = 0;
  EXPECT_TRUE(HexWord("0000000000000001", 16, &word));
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

namespace {
void CheckExp2f(uint32_t input, uint32_t expected, int required,
                int mode, int incoming) {
  float x;
  std::memcpy(&x, &input, sizeof x);
  ASSERT_EQ(std::fesetround(mode), 0);
  ASSERT_EQ(std::feclearexcept(FE_ALL_EXCEPT), 0);
  ASSERT_EQ(std::feraiseexcept(incoming), 0);
  int actual_incoming = std::fetestexcept(FE_ALL_EXCEPT);
  errno = 713;
  float (*volatile fn)(float) = gmath_exp2f;
  volatile float result = fn(x);
  int error = errno;
  int flags = std::fetestexcept(FE_ALL_EXCEPT);
  int rounding = std::fegetround();
  EXPECT_EQ(Bits(result), expected) << std::hex << input;
  EXPECT_EQ(flags, required | actual_incoming) << std::hex << input;
  EXPECT_EQ(error, 713);
  EXPECT_EQ(rounding, mode);
}
int Exp2fPolicy(float x) {
  return RequiredFlags(Bits(x));
}
}

TEST(Exp2f, ExactIntegerReferenceRowsRejectCorruption) {
  for (int n = -149; n <= 127; ++n) {
    Entry entry{Bits(static_cast<float>(n)), n >= -126 ?
        static_cast<uint32_t>(n + 127) << 23 : 1u << static_cast<unsigned>(n + 149), 0};
    EXPECT_TRUE(ValidResult(entry));
    entry.error = 0x3e800000u;
    EXPECT_FALSE(ValidResult(entry));
    entry.error = 0;
    ++entry.result;
    EXPECT_FALSE(ValidResult(entry));
  }
}

TEST(Exp2f, DirectedHalfSeamsAndAdjacentWords) {
  Environment saved;
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (int base : {-149, -127, -126, -1, 0, 1, 126, 127}) {
      for (unsigned j = 0; j < 128; ++j) {
        float center = static_cast<float>(base) + static_cast<float>(2*j+1) * 0x1p-8f;
        uint32_t word = Bits(center);
        for (int delta : {-1, 0, 1}) {
          uint32_t input = word + static_cast<uint32_t>(delta);
          float x = Float(input);
          int expected_flags = RequiredFlags(input);
          ASSERT_EQ(std::feclearexcept(FE_ALL_EXCEPT), 0);
          errno = 713;
          float (*volatile fn)(float) = gmath_exp2f;
          volatile float result = fn(x);
          int flags = std::fetestexcept(FE_ALL_EXCEPT);
          int error = errno, actual_mode = std::fegetround();
          ASSERT_EQ(flags, expected_flags) << std::hex << input;
          ASSERT_EQ(error, 713);
          ASSERT_EQ(actual_mode, mode);
          ASSERT_LE(Bits(result), kInf);
        }
      }
    }
  }
}

TEST(Exp2f, ExactPowersAndRawSpecialState) {
  Environment saved;
  struct Case { uint32_t input, output; int flags; };
  const Case cases[] = {
    {0, kOne, 0}, {kSign, kOne, 0}, {kInf, kInf, 0}, {kInf|kSign, 0, 0},
    {kNaN, kNaN, 0}, {kNaN|7, kNaN, 0}, {kNaN|kSign, kNaN, 0},
    {kInf|1, kNaN, FE_INVALID}, {kInf|kSign|1, kNaN, FE_INVALID},
    {0x7fbfffffu, kNaN, FE_INVALID}, {0xffbfffffu, kNaN, FE_INVALID},
    {1, kOne, FE_INEXACT}, {kSign|1, kOne, FE_INEXACT},
    {0x32800000u, kOne, FE_INEXACT}, {0xb2800000u, kOne, FE_INEXACT},
    {0x43000000u, kInf, FE_OVERFLOW|FE_INEXACT},
    {0x7f7fffffu, kInf, FE_OVERFLOW|FE_INEXACT},
    {0xc3160000u, 0, FE_UNDERFLOW|FE_INEXACT},
    {0xff7fffffu, 0, FE_UNDERFLOW|FE_INEXACT}
  };
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    for (int incoming : {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW,
                         FE_UNDERFLOW, FE_INEXACT, FE_ALL_EXCEPT}) {
      for (const auto & c : cases) {
        // Non-nearest tiny values may choose a neighbor of one; only state
        // is promised there and is exercised separately below.
        if (mode != FE_TONEAREST && (c.input & ~kSign) != 0 &&
            (c.input & ~kSign) <= 0x32800000u) continue;
        CheckExp2f(c.input, c.output, c.flags, mode, incoming);
      }
      for (int exponent = -149; exponent <= 127; ++exponent) {
        uint32_t expected = exponent >= -126 ?
            static_cast<uint32_t>(exponent + 127) << 23 :
            1u << static_cast<unsigned>(exponent + 149);
        CheckExp2f(Bits(static_cast<float>(exponent)), expected, 0, mode, incoming);
      }
    }
  }
}

TEST(Exp2f, ReductionGridFlagsAndMonotonicity) {
  Environment saved;
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    float previous = 0;
    for (int n = -19199; n < 16384; ++n) {
      float x = static_cast<float>(n) * 0x1p-7f;
      int expected_flags = Exp2fPolicy(x);
      ASSERT_EQ(std::feclearexcept(FE_ALL_EXCEPT), 0);
      errno = 713;
      float (*volatile fn)(float) = gmath_exp2f;
      volatile float result = fn(x);
      int flags = std::fetestexcept(FE_ALL_EXCEPT);
      int error = errno;
      int rounding = std::fegetround();
      ASSERT_EQ(flags, expected_flags) << "grid n=" << n;
      ASSERT_EQ(error, 713);
      ASSERT_EQ(rounding, mode);
      ASSERT_LT(Bits(result), kInf);
      if (mode == FE_TONEAREST) {
        ASSERT_GE(result, previous) << "grid n=" << n;
        ASSERT_GT(result, 0);
      }
      previous = result;
    }
  }
}

TEST(Exp2f, FiniteRandomEnvironment) {
  Environment saved;
  uint32_t state = 0x72a59bd3u;
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (unsigned i = 0; i < 10000; ++i) {
      state ^= state << 13; state ^= state >> 17; state ^= state << 5;
      uint32_t a = state & ~kSign;
      if (a >= kInf) continue;
      float x = Float(state);
      int expected_flags = Exp2fPolicy(x);
      ASSERT_EQ(std::feclearexcept(FE_ALL_EXCEPT), 0);
      ASSERT_EQ(std::feraiseexcept(FE_DIVBYZERO), 0);
      errno = 713;
      float (*volatile fn)(float) = gmath_exp2f;
      volatile float result = fn(x);
      int flags = std::fetestexcept(FE_ALL_EXCEPT);
      int error = errno;
      int rounding = std::fegetround();
      ASSERT_EQ(flags, expected_flags | FE_DIVBYZERO) << std::hex << state;
      ASSERT_EQ(error, 713);
      ASSERT_EQ(rounding, mode);
      ASSERT_LE(Bits(result), kInf);
    }
  }
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
