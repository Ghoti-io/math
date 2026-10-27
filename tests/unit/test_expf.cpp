/**
 * @file Binary32 natural-exp pinned references and strict corpus format.
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
  return line == "# Pinned oracle: tools/oracle/gen_corpus_expf.py; "
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
  if (a == kInf || a == 0) return 0;
  if ((word & kSign) == 0 && a >= 0x42b17218u) return FE_OVERFLOW | FE_INEXACT;
  return FE_INEXACT | ((word & kSign) && a >= 0x42aeac50u ? FE_UNDERFLOW : 0);
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
  bool overflow = (entry.x & kSign) == 0 && absolute >= 0x42b17218u;
  bool zero_tail = (entry.x & kSign) != 0 && absolute >= 0x42cff1b5u;
  if (overflow) return entry.result == kInf && entry.error == 0;
  if (zero_tail) {
    if (entry.result != 0 || (entry.error & kSign) != 0) return false;
    if (absolute >= 0x43800000u) return entry.error == 0; // x<=-256
    return true;
  }
  if (entry.result == 0 || entry.result >= kInf) return false;
  bool subnormal = (entry.x & kSign) != 0 && absolute >= 0x42aeac50u;
  return subnormal ? entry.result < 0x00800000u : entry.result >= 0x00800000u;
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
        if (provenance) return fail("duplicate expf provenance");
        if (!PinnedProvenance(line)) return fail("invalid expf pinned provenance");
        provenance = true;
      }
      else if (line.find("# function") == 0) {
        if (function) return fail("duplicate expf function header");
        if (line != "# function expf") return fail("invalid expf function header");
        function = true;
      }
      else if (line.find("# seed") == 0) {
        if (metadata) return fail("duplicate expf sample metadata");
        if (!SampleMetadata(line, &declared)) return fail("invalid expf sample metadata");
        metadata = true;
      }
      else if (line.find("# binary32") == 0) {
        if (format) return fail("duplicate expf format header");
        if (line != expected_format) return fail("invalid expf binary32 format header");
        format = true;
      }
      continue;
    }
    if (!provenance || !function || !metadata || !format) {
      return fail("missing required expf corpus metadata before data");
    }
    Entry entry{};
    if (!ParseRow(line, &entry)) return fail("bad expf corpus row or binary32 representation: " + line);
    if (!inputs.insert(entry.x).second) return fail("duplicate expf input word");
    entries->push_back(entry);
  }
  if (input.bad()) return fail("cannot read expf corpus");
  if (!provenance || !function || !metadata || !format) return fail("missing required expf corpus metadata");
  if (entries->size() != declared) return fail("expf corpus count disagrees with header");
  if (entries->size() < minimum) return fail("missing or truncated expf corpus");
  return true;
}

std::set<uint32_t> EssentialWords() {
  std::set<uint32_t> required = {0u, kSign, kInf, kInf | kSign, kNaN,
      kNaN | kSign | 7u, kInf - 1, (kInf - 1) | kSign, 0x3f800000u, 0xbf800000u, 0xb3000000u, 0x33800000u};
  // Independent pinned natural-log reduction families, present even in
  // fresh count-zero samples: table seams, half seams, integer neighbors.
  for (uint32_t word : {0xc2b00c6eu, 0x3e2be687u, 0x3eb17218u, 0x42b16f52u,
      0xc2b00b0bu, 0x3e2eac50u, 0x3eb2d4fcu, 0x42b170b5u,
      0xbfffffffu, 0xc0000001u, 0x3fffffffu, 0x40000001u}) required.insert(word);
  // b3000000 and 33800000 above are pinned output-midpoint inverse witnesses.
  for (uint32_t center : {0x42b17218u, 0xc2cff1b5u, 0xc2aeac50u,
                          0x32800000u, 0xb2800000u, 0xb3000000u, 0x33800000u}) {
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
  const char * env = std::getenv("GMATH_EXPF_CORPUS_DIR");
  std::string directory = env && *env ? env : "tests/corpus";
  std::ifstream input(directory + "/expf.corpus");
  std::vector<Entry> entries;
  if (!input.is_open()) {
    ADD_FAILURE() << "missing expf corpus: " << directory;
    return entries;
  }
  size_t minimum = 1000;
  const char * required = std::getenv("GMATH_EXPF_MIN_ENTRIES");
  if (required != nullptr && !PositiveInteger(required, &minimum)) {
    ADD_FAILURE() << "GMATH_EXPF_MIN_ENTRIES must be a complete positive decimal integer";
    return entries;
  }
  std::string reason;
  std::string payload((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
  if (input.bad()) { ADD_FAILURE() << "cannot read expf corpus"; return entries; }
  std::istringstream stream(payload);
  if (!ParseCorpus(stream, minimum, &entries, &reason)) {
    ADD_FAILURE() << reason;
    entries.clear();
  }
  if (!entries.empty() && (!env || !*env) &&
      payload.find("\n# seed 20261027 count 3000 fresh False entries 27228\n") == std::string::npos) {
    ADD_FAILURE() << "incorrect committed expf sample metadata";
    entries.clear();
  }
  if (!entries.empty() && !EssentialCoverage(entries)) {
    ADD_FAILURE() << "missing essential expf coverage";
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
  return "# Pinned oracle: tools/oracle/gen_corpus_expf.py; MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1\n"
      "# function expf\n# seed 20261027 count 0 fresh False entries " + count +
      "\n# binary32 inputs/results widened exactly to binary64; signed binary32 error in true binary32 ULP\n" + rows;
}
} // namespace

TEST(Expf, CorpusIsWithinOneUlp) {
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
    float (*volatile fn)(float) = gmath_expf;
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
      ADD_FAILURE() << "expf input " << std::hex << entry.x << " is " << std::dec
                    << error << " ulp from exact (error cell does not certify one ulp)";
    }
  }
  std::printf("  expf: %zu corpus entries, max error %.8f ulp (input bits %08x)\n",
      entries.size(), worst, worst_input);
  EXPECT_EQ(failures, 0u);
  EXPECT_LE(worst, 0.51) << "expf accuracy regression";
}

TEST(Expf, ErrorCellsPreserveTinyAndBinadeUncertainty) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  // D=-.5 and E near+.5: upper error endpoints can exceed one ULP.
  EXPECT_TRUE(WithinOneUlp(Float(0x3f7fffff), {1, kOne, 0x3effffff}));
  EXPECT_FALSE(WithinOneUlp(Float(0x3f7fffff), {1, kOne, 0x3f000000}));
  EXPECT_FALSE(WithinOneUlp(Float(0x3f7fffff), {1, kOne, 0x3f000001}));
  // D=-1.5 and E near-.5: the opposite signed cell endpoint matters too.
  EXPECT_FALSE(WithinOneUlp(Float(0x3f7fffff), {1, 0x3f800001, 0xbeffffff}));
  EXPECT_FALSE(WithinOneUlp(Float(0x3f7fffff), {1, 0x3f800001, 0xbf000000}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f7fffff), {1, 0x3f800001, 0xbf000001}));
  // The last helper fixture's error is outside a valid rounded-reference row;
  // the loader rejects it independently. It only tests the metric algebra.
  Entry invalid{1, 0x3f800001, 0xbf000001};
  EXPECT_FALSE(ValidResult(invalid));

  EXPECT_FALSE(WithinOneUlp(Float(0x3f800002), {1, 0x3f800001, kSign}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f800000), {1, 0x3f800001, kSign}));
  EXPECT_FALSE(WithinOneUlp(Float(0x3f800000), {1, 0x3f800001, 0}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f800002), {1, 0x3f800001, 0}));
  EXPECT_FALSE(WithinOneUlp(Float(0x3f7fffff), {1, 0x3f800000, 0x3f000000}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f7fffff), {1, 0x3f800000, 0x3effffff}));
  EXPECT_DOUBLE_EQ(UlpError(0.0f, {0xc2cff1b5, 0, 0x3f000000}), 0.5 + 0x1p-25);
  EXPECT_TRUE(WithinOneUlp(0.0f, {0xc2cff1b5, 0, 0x3f000000}));
  EXPECT_FALSE(WithinOneUlp(Float(1), {0xc2cff1b5, 0, 0x3f000000}));
  EXPECT_FALSE(WithinOneUlp(Float(kSign), {0xc2cff1b5, 0, 0x3f000000}));
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

TEST(Expf, LoadFixturesRequirePinnedMetadataAndUniqueExactWords) {
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
  EXPECT_FALSE(parse(Fixture(row) + "# function expf\n"));
  EXPECT_FALSE(parse(Fixture(row) + "# seed 1 count 0 fresh False entries 1\n"));
  EXPECT_FALSE(parse(Fixture(row) + "# binary32 inputs/results widened exactly to binary64; signed binary32 error in true binary32 ULP\n"));
  const std::string valid = Fixture(row);
  for (const auto & replacement : std::vector<std::pair<std::string, std::string>>{
           {"MPFR 4.2.2", "MPFR 4.2.1"}, {"gmpy2 2.3.2", "gmpy2 2.3.1"},
           {"mpmath 1.4.1", ""}, {"mpmath 1.4.1", "mpmath 1.4.1 mpmath 1.4.1"},
           {"# function expf", "# function exp2"}, {"fresh False", "fresh maybe"},
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
  EXPECT_TRUE(parse(Fixture("c059fe36a0000000 0000000000000000 3effff8b\n"))) << reason;
  EXPECT_TRUE(parse(Fixture("7ff0000000000000 7ff0000000000000 00000000\n"))) << reason;
  EXPECT_TRUE(parse(Fixture("fff0000000000000 0000000000000000 00000000\n"))) << reason;
  EXPECT_TRUE(parse(Fixture("7ff8000000000000 7ff8000000000000 00000000\n"))) << reason;
}

TEST(Expf, WordAndCountParsersRejectPartialAndOutOfRangeText) {
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

TEST(Expf, EssentialCoverageAndRangePoliciesRejectDroppedBoundaries) {
  std::vector<Entry> entries;
  for (uint32_t word : EssentialWords()) entries.push_back({word, 0, 0});
  EXPECT_TRUE(EssentialCoverage(entries));
  for (uint32_t missing : {0u, kSign, 0x42b17218u, 0xc2cff1b5u,
           0xc2aeac50u, 0x32800000u, 0xb2800000u, 0xb3000000u,
           0x33800000u, 0x00800000u, kSign | 1u}) {
    auto truncated = entries;
    truncated.erase(std::remove_if(truncated.begin(), truncated.end(),
        [&](const Entry & entry) { return entry.x == missing; }), truncated.end());
    EXPECT_FALSE(EssentialCoverage(truncated)) << std::hex << missing;
  }
  EXPECT_EQ(RequiredFlags(0), 0);
  EXPECT_EQ(RequiredFlags(kSign), 0);
  EXPECT_EQ(RequiredFlags(0x3f800000), FE_INEXACT); // exp(1) is inexact.
  EXPECT_EQ(RequiredFlags(0xbf800000), FE_INEXACT);
  EXPECT_EQ(RequiredFlags(0xc2aeac50), FE_UNDERFLOW | FE_INEXACT);
  EXPECT_EQ(RequiredFlags(0xc2aeac4f), FE_INEXACT);
  EXPECT_EQ(RequiredFlags(0x42b17218), FE_OVERFLOW | FE_INEXACT);
  EXPECT_EQ(RequiredFlags(0x42b17217), FE_INEXACT);
  Entry row{};
  EXPECT_TRUE(ParseRow("c059fe36a0000000 0000000000000000 3effff8b", &row));
  EXPECT_FALSE(ParseRow("c059fe36a0000000 36a0000000000000 3effff8b", &row));
  EXPECT_TRUE(ParseRow("40562e4300000000 7ff0000000000000 00000000", &row));
  EXPECT_FALSE(ParseRow("40562e42e0000000 7ff0000000000000 00000000", &row));
  EXPECT_FALSE(ParseRow("c055d58a00000000 3810000000000000 00000000", &row));
  EXPECT_FALSE(ParseRow("c055d589e0000000 380fffffe0000000 00000000", &row));
}

namespace {
void CheckExpf(uint32_t input, uint32_t expected, int required,
               int mode, int incoming, bool exact_bits = true) {
  float x;
  std::memcpy(&x, &input, sizeof x);
  ASSERT_EQ(std::fesetround(mode), 0);
  ASSERT_EQ(std::feclearexcept(FE_ALL_EXCEPT), 0);
  ASSERT_EQ(std::feraiseexcept(incoming), 0);
  int existing = std::fetestexcept(FE_ALL_EXCEPT);
  errno = 713;
  float (*volatile fn)(float) = gmath_expf;
  volatile float result = fn(x);
  int error = errno;
  int flags = std::fetestexcept(FE_ALL_EXCEPT);
  int rounding = std::fegetround();
  if (exact_bits) {
    EXPECT_EQ(Bits(result), expected) << std::hex << input;
  }
  else {
    EXPECT_GE(Bits(result), 0x00800000u);
    EXPECT_LT(Bits(result), kInf);
  }
  EXPECT_EQ(flags, required | existing) << std::hex << input;
  EXPECT_EQ(error, 713);
  EXPECT_EQ(rounding, mode);
}
}

TEST(Expf, ExactSpecialsAndTinyState) {
  Environment saved;
  struct Case { uint32_t input, output; int flags; };
  const Case cases[] = {
    {0, kOne, 0}, {kSign, kOne, 0}, {kInf, kInf, 0}, {kInf|kSign, 0, 0},
    {kNaN, kNaN, 0}, {kNaN|7, kNaN, 0}, {kNaN|kSign, kNaN, 0},
    {kInf|1, kNaN, FE_INVALID}, {kInf|kSign|1, kNaN, FE_INVALID},
    {0x7fbfffffu, kNaN, FE_INVALID}, {0xffbfffffu, kNaN, FE_INVALID},
    {1, kOne, FE_INEXACT}, {kSign|1, kOne, FE_INEXACT},
    {0x007fffffu, kOne, FE_INEXACT}, {0x807fffffu, kOne, FE_INEXACT},
    {0x00800000u, kOne, FE_INEXACT}, {0x80800000u, kOne, FE_INEXACT},
    {0x32800000u, kOne, FE_INEXACT}, {0xb2800000u, kOne, FE_INEXACT},
    {0x32800001u, kOne, FE_INEXACT}, {0xb2800001u, kOne, FE_INEXACT},
    {0x42b17218u, kInf, FE_OVERFLOW|FE_INEXACT},
    {0x7f7fffffu, kInf, FE_OVERFLOW|FE_INEXACT},
    {0xc2cff1b5u, 0, FE_UNDERFLOW|FE_INEXACT},
    {0xff7fffffu, 0, FE_UNDERFLOW|FE_INEXACT}
  };
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    for (int incoming : {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW,
                         FE_UNDERFLOW, FE_INEXACT, FE_ALL_EXCEPT}) {
      for (const auto & c : cases) {
        bool tiny = (c.input & ~kSign) != 0 && (c.input & ~kSign) <= 0x32800001u;
        CheckExpf(c.input, c.output, c.flags, mode, incoming,
                  mode == FE_TONEAREST || !tiny);
      }
    }
  }
}

TEST(Expf, BoundaryAndReductionLandmarks) {
  Environment saved;
  constexpr double ln2 = 0x1.62e42fefa39efp-1;
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (int n : {-19199, -18001, -16129, -16128, -129, -128, -127,
                  -1, 0, 1, 127, 128, 129, 16127, 16383}) {
      for (double half : {0.0, 0.5}) {
        // These are selection landmarks, not numerical reference values.
        // The corpus independently certifies the actual binary32 inputs.
        float center = static_cast<float>((static_cast<double>(n) + half) * (ln2 / 128));
        uint32_t word = Bits(center);
        for (int delta : {-1, 0, 1}) {
          if (word == 0 && delta < 0) continue;
          uint32_t input = word + static_cast<uint32_t>(delta);
          float x = Float(input);
          int required = RequiredFlags(input);
          ASSERT_EQ(std::feclearexcept(FE_ALL_EXCEPT), 0);
          errno = 713;
          float (*volatile fn)(float) = gmath_expf;
          volatile float result = fn(x);
          int flags = std::fetestexcept(FE_ALL_EXCEPT);
          int error = errno, rounding = std::fegetround();
          ASSERT_EQ(flags, required) << std::hex << input;
          ASSERT_EQ(error, 713);
          ASSERT_EQ(rounding, mode);
          ASSERT_LE(Bits(result), kInf);
        }
      }
    }
    for (uint32_t center : {0x42b17218u, 0xc2cff1b5u, 0xc2aeac50u,
                            0x32800000u, 0xb2800000u}) {
      for (int delta = -2; delta <= 2; ++delta) {
        uint32_t input = center + static_cast<uint32_t>(delta);
        float x = Float(input);
        int required = RequiredFlags(input);
        ASSERT_EQ(std::feclearexcept(FE_ALL_EXCEPT), 0);
        errno = 713;
        float (*volatile fn)(float) = gmath_expf;
        volatile float result = fn(x);
        int flags = std::fetestexcept(FE_ALL_EXCEPT);
        int error = errno, rounding = std::fegetround();
        ASSERT_EQ(flags, required) << std::hex << input;
        ASSERT_EQ(error, 713);
        ASSERT_EQ(rounding, mode);
        ASSERT_LE(Bits(result), kInf);
      }
    }
  }
}

TEST(Expf, FiniteRandomEnvironment) {
  Environment saved;
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    uint32_t state = 0xc35a7b91u; // Replay identical words in every mode.
    ASSERT_EQ(std::fesetround(mode), 0);
    for (unsigned i = 0; i < 10000; ++i) {
      state ^= state << 13; state ^= state >> 17; state ^= state << 5;
      if ((state & ~kSign) >= kInf) continue;
      float x = Float(state);
      int required = RequiredFlags(state);
      ASSERT_EQ(std::feclearexcept(FE_ALL_EXCEPT), 0);
      ASSERT_EQ(std::feraiseexcept(FE_DIVBYZERO), 0);
      errno = 713;
      float (*volatile fn)(float) = gmath_expf;
      volatile float result = fn(x);
      int flags = std::fetestexcept(FE_ALL_EXCEPT);
      int error = errno, rounding = std::fegetround();
      ASSERT_EQ(flags, required | FE_DIVBYZERO) << std::hex << state;
      ASSERT_EQ(error, 713);
      ASSERT_EQ(rounding, mode);
      ASSERT_LE(Bits(result), kInf);
    }
  }
}

TEST(Expf, BoundaryMonotonicity) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  for (uint32_t center : {0x42b17218u, 0xc2cff1b5u, 0xc2aeac50u,
                          0x32800000u, 0xb2800000u}) {
    for (int delta = -256; delta < 256; ++delta) {
      uint32_t a = center + static_cast<uint32_t>(delta);
      float left = gmath_expf(Float(a)), right = gmath_expf(Float(a + 1));
      if (center & kSign) {
        ASSERT_LE(right, left) << std::hex << a;
      }
      else {
        ASSERT_GE(right, left) << std::hex << a;
      }
    }
  }
  constexpr double ln2 = 0x1.62e42fefa39efp-1;
  for (int n = -19199; n < 16384; ++n) {
    for (double half : {0.0, 0.5}) {
      uint32_t center = Bits(static_cast<float>((static_cast<double>(n) + half) * (ln2 / 128)));
      for (int delta : {-1, 0}) {
        if (center == 0 && delta < 0) continue;
        uint32_t a = center + static_cast<uint32_t>(delta);
        float left = gmath_expf(Float(a)), right = gmath_expf(Float(a + 1));
        if (center & kSign) {
          ASSERT_LE(right, left) << std::hex << a;
        }
        else {
          ASSERT_GE(right, left) << std::hex << a;
        }
      }
    }
  }
  EXPECT_EQ(Bits(gmath_expf(Float(0xc2cff1b4u))), 1u);
  EXPECT_EQ(Bits(gmath_expf(Float(0xc2cff1b5u))), 0u);
  EXPECT_LT(Bits(gmath_expf(Float(0x42b17217u))), kInf);
  EXPECT_EQ(Bits(gmath_expf(Float(0x42b17218u))), kInf);
  EXPECT_LT(Bits(gmath_expf(Float(0xc2aeac50u))), 0x00800000u);
  EXPECT_GE(Bits(gmath_expf(Float(0xc2aeac4fu))), 0x00800000u);
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
