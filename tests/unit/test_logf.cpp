/**
 * @file Binary32 natural-log pinned references and strict corpus format.
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
  return line == "# Pinned oracle: tools/oracle/gen_corpus_logf.py; "
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

int RequiredFlags(uint32_t word) {
  uint32_t a = word & ~kSign;
  if (a > kInf) return (a & kQuiet) ? 0 : FE_INVALID;
  if (a == 0) return FE_DIVBYZERO;
  if (word & kSign) return FE_INVALID;
  if (word == kOne || word == kInf) return 0;
  return FE_INEXACT;
}

bool ValidResult(const Entry & entry) {
  uint32_t a = entry.x & ~kSign;
  if (a > kInf) return entry.result == kNaN && entry.error == 0;
  if (a == 0) return entry.result == (kInf | kSign) && entry.error == 0;
  if (entry.x & kSign) return entry.result == kNaN && entry.error == 0;
  if (entry.x == kInf) return entry.result == kInf && entry.error == 0;
  if (entry.x == kOne) return entry.result == 0 && entry.error == 0;
  uint32_t magnitude = entry.result & ~kSign;
  return magnitude >= 0x00800000u && magnitude < kInf &&
      ((entry.result & kSign) != 0) == (entry.x < kOne) &&
      (entry.error & ~kSign) <= 0x3f000000u;
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
        if (provenance) return fail("duplicate logf provenance");
        if (!PinnedProvenance(line)) return fail("invalid logf pinned provenance");
        provenance = true;
      }
      else if (line.find("# function") == 0) {
        if (function) return fail("duplicate logf function header");
        if (line != "# function logf") return fail("invalid logf function header");
        function = true;
      }
      else if (line.find("# seed") == 0) {
        if (metadata) return fail("duplicate logf sample metadata");
        if (!SampleMetadata(line, &declared)) return fail("invalid logf sample metadata");
        metadata = true;
      }
      else if (line.find("# binary32") == 0) {
        if (format) return fail("duplicate logf format header");
        if (line != expected_format) return fail("invalid logf binary32 format header");
        format = true;
      }
      continue;
    }
    if (!provenance || !function || !metadata || !format) {
      return fail("missing required logf corpus metadata before data");
    }
    Entry entry{};
    if (!ParseRow(line, &entry)) return fail("bad logf corpus row or binary32 representation: " + line);
    if (!inputs.insert(entry.x).second) return fail("duplicate logf input word");
    entries->push_back(entry);
  }
  if (input.bad()) return fail("cannot read logf corpus");
  if (!provenance || !function || !metadata || !format) return fail("missing required logf corpus metadata");
  if (entries->size() != declared) return fail("logf corpus count disagrees with header");
  if (entries->size() < minimum) return fail("missing or truncated logf corpus");
  return true;
}

std::set<uint32_t> EssentialWords() {
  std::set<uint32_t> required = {0u, kSign, kInf, kInf | kSign, kNaN,
      kNaN | kSign | 7u, kInf - 1, (kInf - 1) | kSign,
      0x3f000000u, 0x40000000u, 0x3ebc5ab2u, 0x402df854u,
      0x3f800006u, 0x3f81ffffu, 0x3fe7ffffu, 0x00738001u};
  for (uint32_t center : {kOne, 0x00800000u, 0x3f7f0000u, 0x3f810000u,
                          0x40000000u, 0xc0000000u}) {
    for (int delta = -2; delta <= 2; ++delta) required.insert(center + static_cast<uint32_t>(delta));
  }
  for (unsigned exponent = 1; exponent < 255; ++exponent) {
    required.insert(exponent << 23);
    required.insert(kSign | (exponent << 23));
  }
  for (unsigned bit = 0; bit < 23; ++bit) {
    required.insert(1u << bit);
    required.insert(kSign | (1u << bit));
  }
  // Independent row geometry: normalized [181/256,181/128),128 rows.
  // Require every seam and half seam rather than trusting the row count.
  for (unsigned row = 0; row <= 128; ++row) {
    uint64_t seam = 0x3fe6a00000000000ull + (uint64_t(row) << 45);
    uint32_t narrow;
    if (NarrowExact(seam, &narrow)) required.insert(narrow);
    if (row < 128 && NarrowExact(seam + (uint64_t(1) << 44), &narrow)) required.insert(narrow);
  }
  return required;
}
bool EssentialCoverage(const std::vector<Entry> & entries) {
  std::set<uint32_t> present;
  for (const auto & entry : entries) present.insert(entry.x);
  for (uint32_t required : EssentialWords()) {
    if (!present.count(required)) return false;
  }
  return true;
}
std::vector<Entry> Load() {
  const char * env = std::getenv("GMATH_LOGF_CORPUS_DIR");
  std::string directory = env && *env ? env : "tests/corpus";
  std::ifstream input(directory + "/logf.corpus");
  std::vector<Entry> entries;
  if (!input.is_open()) {
    ADD_FAILURE() << "missing logf corpus: " << directory;
    return entries;
  }
  size_t minimum = 1000;
  const char * required = std::getenv("GMATH_LOGF_MIN_ENTRIES");
  if (required != nullptr && !PositiveInteger(required, &minimum)) {
    ADD_FAILURE() << "GMATH_LOGF_MIN_ENTRIES must be a complete positive decimal integer";
    return entries;
  }
  std::string reason;
  std::string payload((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
  if (input.bad()) { ADD_FAILURE() << "cannot read logf corpus"; return entries; }
  std::istringstream stream(payload);
  if (!ParseCorpus(stream, minimum, &entries, &reason)) {
    ADD_FAILURE() << reason;
    entries.clear();
  }
  if (!entries.empty() && (!env || !*env) &&
      payload.find("\n# seed 20261027 count 3000 fresh False entries 19120\n") == std::string::npos) {
    ADD_FAILURE() << "incorrect committed logf sample metadata";
    entries.clear();
  }
  if (!entries.empty() && !EssentialCoverage(entries)) {
    ADD_FAILURE() << "missing essential logf coverage";
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

bool StrictSpecial(uint32_t input) {
  uint32_t a = input & ~kSign;
  return a >= kInf || a == 0 || (input & kSign) != 0 || input == kOne;
}
double UlpError(float y, const Entry & entry) {
  uint32_t bits = Bits(y), a = bits & ~kSign;
  if (StrictSpecial(entry.x)) {
    return bits == entry.result ? 0 : std::numeric_limits<double>::infinity();
  }
  if (a < 0x00800000u || a >= kInf || ((bits ^ entry.result) & kSign) != 0) {
    return std::numeric_limits<double>::infinity();
  }
  double distance = (static_cast<double>(y) - static_cast<double>(Float(entry.result))) / TrueUlp(entry);
  Interval cell = ErrorCell(entry.error);
  return std::max(std::fabs(distance - cell.low), std::fabs(distance - cell.high));
}
bool WithinOneUlp(float y, const Entry & entry) {
  uint32_t bits = Bits(y), a = bits & ~kSign;
  if (StrictSpecial(entry.x)) return bits == entry.result;
  if (a < 0x00800000u || a >= kInf || ((bits ^ entry.result) & kSign) != 0) return false;
  double distance = (static_cast<double>(y) - static_cast<double>(Float(entry.result))) / TrueUlp(entry);
  if (std::fabs(distance) > 2) return false;
  Interval cell = ErrorCell(entry.error);
  return cell.low >= distance - 1 && cell.high <= distance + 1;
}

std::string Fixture(const std::string & rows, const std::string & count = "1") {
  return "# Pinned oracle: tools/oracle/gen_corpus_logf.py; MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1\n"
      "# function logf\n# seed 20261027 count 0 fresh False entries " + count +
      "\n# binary32 inputs/results widened exactly to binary64; signed binary32 error in true binary32 ULP\n" + rows;
}
} // namespace

TEST(Logf, CorpusIsWithinOneUlp) {
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
    float (*volatile fn)(float) = gmath_logf;
    volatile float result = fn(argument);
    int error_number = errno;
    int flags = std::fetestexcept(FE_ALL_EXCEPT);
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
      ADD_FAILURE() << "logf input " << std::hex << entry.x << " is " << std::dec
                    << error << " ulp from exact (error cell does not certify one ulp)";
    }
  }
  std::printf("  logf: %zu corpus entries, max error %.8f ulp (input bits %08x)\n",
      entries.size(), worst, worst_input);
  EXPECT_EQ(failures, 0u);
  EXPECT_LE(worst, 0.51) << "logf accuracy regression";
}

TEST(Logf, ErrorCellsPreserveBothOutputSignsAndBinades) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  EXPECT_FALSE(WithinOneUlp(Float(0x3f800002), {0x40000000, 0x3f800001, kSign}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f800000), {0x40000000, 0x3f800001, kSign}));
  EXPECT_FALSE(WithinOneUlp(Float(0x3f800000), {0x40000000, 0x3f800001, 0}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f800002), {0x40000000, 0x3f800001, 0}));
  EXPECT_FALSE(WithinOneUlp(Float(0xbf800002), {0x3f000000, 0xbf800001, 0}));
  EXPECT_TRUE(WithinOneUlp(Float(0xbf800000), {0x3f000000, 0xbf800001, 0}));
  EXPECT_FALSE(WithinOneUlp(Float(0xbf7fffff), {0x3f000000, 0xbf800000, 0xbf000000}));
  EXPECT_TRUE(WithinOneUlp(Float(0xbf7fffff), {0x3f000000, 0xbf800000, 0xbeffffff}));
  EXPECT_DOUBLE_EQ(UlpError(Float(0xbf7fffff), {0x3f000000, 0xbf800000, 0x3e800000}), 0.75 + 0x1p-27);
  EXPECT_DOUBLE_EQ(UlpError(Float(0xbf800001), {0x3f000000, 0xbf800000, 0xbe800000}), 0.75 + 0x1p-27);
  EXPECT_FALSE(WithinOneUlp(Float(kSign), {kOne, 0, 0}));
  EXPECT_FALSE(WithinOneUlp(Float(kNaN | 1), {kSign, kInf | kSign, 0}));
  EXPECT_FALSE(WithinOneUlp(Float(kOne), {0x3f000000, 0xbf800000, 0}));
  EXPECT_DOUBLE_EQ(ErrorCell(0).high, std::ldexp(1.0, -150));
  EXPECT_DOUBLE_EQ(ErrorCell(kSign).low, -std::ldexp(1.0, -150));
  EXPECT_LT(ErrorCell(0xbf000000).low, -0.5);
  EXPECT_GT(ErrorCell(0xbf000000).high, -0.5);
}

TEST(Logf, LoadFixturesRequirePinnedMetadataAndUniqueExactWords) {
  const std::string row = "3ff0000000000000 0000000000000000 00000000\n";
  std::vector<Entry> entries;
  std::string reason;
  auto parse = [&](const std::string & text, size_t minimum = 1) {
    std::istringstream input(text);
    return ParseCorpus(input, minimum, &entries, &reason);
  };
  ASSERT_TRUE(parse(Fixture(row))) << reason;
  EXPECT_FALSE(parse(Fixture(row), 2));
  EXPECT_FALSE(parse(Fixture(row, "2")));
  EXPECT_FALSE(parse(Fixture(row + row, "2")));
  EXPECT_FALSE(parse(Fixture(row, "1junk")));
  EXPECT_FALSE(parse(Fixture("3ff0000000000001 0000000000000000 00000000\n")));
  EXPECT_FALSE(parse(Fixture("3ff0000000000000 0000000000000001 00000000\n")));
  EXPECT_FALSE(parse(Fixture("3ff0000000000000 0000000000000000 000000000\n")));
  EXPECT_FALSE(parse(Fixture(row.substr(0, row.size() - 1) + " extra\n")));
  EXPECT_FALSE(parse(Fixture(row) + "# function logf\n"));
  EXPECT_FALSE(parse(Fixture(row) + "# seed 1 count 0 fresh False entries 1\n"));
  EXPECT_FALSE(parse(Fixture(row) + "# binary32 inputs/results widened exactly to binary64; signed binary32 error in true binary32 ULP\n"));
  const std::string valid = Fixture(row);
  for (const auto & replacement : std::vector<std::pair<std::string, std::string>>{
           {"MPFR 4.2.2", "MPFR 4.2.1"}, {"gmpy2 2.3.2", "gmpy2 2.3.1"},
           {"mpmath 1.4.1", ""}, {"mpmath 1.4.1", "mpmath 1.4.1 mpmath 1.4.1"},
           {"# function logf", "# function log2f"}, {"fresh False", "fresh maybe"},
           {"count 0", "count 0junk"}, {"seed 20261027", "seed 20261027junk"}}) {
    std::string bad = valid;
    bad.replace(bad.find(replacement.first), replacement.first.size(), replacement.second);
    EXPECT_FALSE(parse(bad)) << replacement.first;
  }
  for (const std::string & header : {std::string("# Pinned oracle:"), std::string("# function"),
           std::string("# seed"), std::string("# binary32")}) {
    std::string bad = valid;
    size_t begin = bad.find(header), end = bad.find('\n', begin);
    bad.erase(begin, end - begin + 1);
    EXPECT_FALSE(parse(bad)) << header;
  }
  EXPECT_FALSE(parse(valid + valid.substr(0, valid.find('\n') + 1)));
  EXPECT_TRUE(parse(Fixture("0000000000000000 fff0000000000000 00000000\n"))) << reason;
  EXPECT_TRUE(parse(Fixture("8000000000000000 fff0000000000000 00000000\n"))) << reason;
  EXPECT_TRUE(parse(Fixture("fff0000000000000 7ff8000000000000 00000000\n"))) << reason;
  EXPECT_TRUE(parse(Fixture("3fe0000000000000 bfe62e4300000000 3d02e308\n"))) << reason;
  EXPECT_FALSE(parse(Fixture("3fe0000000000000 3fe62e4300000000 3d02e308\n")));
  EXPECT_FALSE(parse(Fixture("3fe0000000000000 0000000000000000 00000000\n")));
}

TEST(Logf, WordAndCountParsersRejectPartialAndOutOfRangeText) {
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

TEST(Logf, EssentialCoverageAndDomainPoliciesRejectDroppedFamilies) {
  std::vector<Entry> entries;
  for (uint32_t word : EssentialWords()) entries.push_back({word, 0, 0});
  EXPECT_TRUE(EssentialCoverage(entries));
  for (uint32_t missing : {0u, kSign, kOne, kInf, 0x00800000u, kSign | 1u,
           0x3f7f0000u, 0x3f810000u, 0x3f800006u, 0x3ebc5ab2u,
           0x40000001u, 0x3f350000u}) {
    auto truncated = entries;
    truncated.erase(std::remove_if(truncated.begin(), truncated.end(),
        [&](const Entry & entry) { return entry.x == missing; }), truncated.end());
    EXPECT_FALSE(EssentialCoverage(truncated)) << std::hex << missing;
  }
  EXPECT_EQ(RequiredFlags(0), FE_DIVBYZERO);
  EXPECT_EQ(RequiredFlags(kSign), FE_DIVBYZERO);
  EXPECT_EQ(RequiredFlags(kOne), 0);
  EXPECT_EQ(RequiredFlags(0x40000000), FE_INEXACT);
  EXPECT_EQ(RequiredFlags(0x3f000000), FE_INEXACT);
  EXPECT_EQ(RequiredFlags(1), FE_INEXACT);
  EXPECT_EQ(RequiredFlags(kSign | 1), FE_INVALID);
  EXPECT_EQ(RequiredFlags(kInf | kSign), FE_INVALID);
  EXPECT_EQ(RequiredFlags(kNaN | kSign), 0);
  Entry row{};
  EXPECT_TRUE(ParseRow("0000000000000000 fff0000000000000 00000000", &row));
  EXPECT_FALSE(ParseRow("0000000000000000 7ff0000000000000 00000000", &row));
  EXPECT_FALSE(ParseRow("3ff0000000000000 8000000000000000 00000000", &row));
  EXPECT_TRUE(ParseRow("3fe0000000000000 bfe62e4300000000 3d02e308", &row));
  EXPECT_FALSE(ParseRow("3fe0000000000000 bfe62e4300000000 3f800000", &row));
}

namespace {
void CheckLogf(uint32_t input, uint32_t expected, bool exact,
               int mode, int incoming) {
  float x;
  std::memcpy(&x, &input, sizeof x);
  ASSERT_EQ(std::fesetround(mode), 0);
  ASSERT_EQ(std::feclearexcept(FE_ALL_EXCEPT), 0);
  ASSERT_EQ(std::feraiseexcept(incoming), 0);
  int existing = std::fetestexcept(FE_ALL_EXCEPT);
  errno = 713;
  float (*volatile fn)(float) = gmath_logf;
  volatile float result = fn(x);
  int error = errno;
  int flags = std::fetestexcept(FE_ALL_EXCEPT);
  int rounding = std::fegetround();
  uint32_t bits = Bits(result), absolute = bits & ~kSign;
  if (exact) {
    EXPECT_EQ(bits, expected) << std::hex << input;
  }
  else {
    EXPECT_GE(absolute, 0x00800000u) << std::hex << input;
    EXPECT_LT(absolute, kInf);
    EXPECT_EQ(bits & kSign, input < kOne ? kSign : 0u);
  }
  EXPECT_EQ(flags, RequiredFlags(input) | existing) << std::hex << input;
  EXPECT_EQ(error, 713);
  EXPECT_EQ(rounding, mode);
}
uint32_t SpecialExpected(uint32_t input) {
  uint32_t a = input & ~kSign;
  if (a > kInf) return kNaN;
  if (a == 0) return kInf | kSign;
  if (input & kSign) return kNaN;
  if (a == kInf) return kInf;
  return 0; // x==1.
}
}

TEST(Logf, ExactSpecialsAndState) {
  Environment saved;
  const uint32_t cases[] = {0, kSign, kInf, kInf|kSign, kOne,
      kNaN, kNaN|7, kNaN|kSign, kNaN|kSign|7,
      kInf|1, kInf|kSign|1, 0x7fbfffffu, 0xffbfffffu,
      kSign|1, 0x807fffffu, 0x80800000u, 0xbf800000u, 0xff7fffffu};
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    for (int incoming : {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW,
                         FE_UNDERFLOW, FE_INEXACT, FE_ALL_EXCEPT}) {
      for (uint32_t input : cases) CheckLogf(input, SpecialExpected(input), true, mode, incoming);
      for (uint32_t input : {1u, 0x007fffffu, 0x00800000u, 0x7f7fffffu,
                            0x3f7ffffeu, 0x3f7fffffu, 0x3f800001u, 0x3f800002u}) {
        CheckLogf(input, 0, false, mode, incoming);
      }
    }
  }
}

TEST(Logf, BinaryPowersAndDomainState) {
  Environment saved;
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    for (int incoming : {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW,
                         FE_UNDERFLOW, FE_INEXACT, FE_ALL_EXCEPT}) {
      for (int exponent = -149; exponent <= 127; ++exponent) {
        uint32_t input = exponent >= -126 ?
            static_cast<uint32_t>(exponent + 127) << 23 :
            1u << static_cast<unsigned>(exponent + 149);
        CheckLogf(input, 0, exponent == 0, mode, incoming);
        CheckLogf(input | kSign, kNaN, true, mode, incoming);
      }
    }
  }
}

TEST(Logf, FiniteRandomEnvironment) {
  Environment saved;
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    uint32_t state = 0x62b3ae91u;
    for (unsigned i = 0; i < 10000; ++i) {
      state ^= state << 13; state ^= state >> 17; state ^= state << 5;
      bool exact = StrictSpecial(state);
      CheckLogf(state, exact ? SpecialExpected(state) : 0u, exact, mode, FE_DIVBYZERO);
    }
  }
}

TEST(Logf, SeamsAndMonotonicity) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  for (unsigned exponent = 1; exponent < 255; ++exponent) {
    for (unsigned j = 0; j < 128; ++j) {
      for (uint32_t half : {0u, 0x8000u}) {
        uint32_t center = (exponent << 23) | (j << 16) | half;
        for (int delta : {-1, 0}) {
          uint32_t a = center + static_cast<uint32_t>(delta);
          float left = gmath_logf(Float(a)), right = gmath_logf(Float(a + 1));
          ASSERT_GE(right, left) << std::hex << a;
        }
      }
    }
  }
  for (unsigned bit = 0; bit < 23; ++bit) {
    uint32_t base = 1u << bit;
    for (uint32_t a : {base, base + 1, base + (base >> 1), (base << 1) - 1}) {
      if (a >= 0x00800000u) continue;
      ASSERT_GE(gmath_logf(Float(a + 1)), gmath_logf(Float(a))) << std::hex << a;
    }
  }
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    // Systematic nonzero residuals and both sides of normalized table seams.
    for (unsigned exponent : {1u, 63u, 126u, 127u, 128u, 190u, 254u}) {
      for (unsigned j = 0; j < 128; ++j) {
        for (uint32_t half : {0u, 0x8000u}) {
          uint32_t center = (exponent << 23) | (j << 16) | half;
          for (int delta : {-1, 0, 1}) {
            uint32_t input = center + static_cast<uint32_t>(delta);
            CheckLogf(input, 0, input == kOne, mode, 0);
          }
        }
      }
    }
  }
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
