/**
 * @file
 * Exact binary32 basic functions against pinned Fraction/MPFR references.
 * GMATH_FLOATBASIC_CORPUS_DIR selects an alternate required corpus directory.
 * Copyright 2026 by Corey Pennycuff
 */
#include "test_helpers.h"

#include <ghoti.io/math/basic.h>

#include <cerrno>
#include <cfenv>
#include <charconv>
#include <cmath>
#include <cstdint>
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

float Float(uint32_t word) {
  float x;
  std::memcpy(&x, &word, sizeof x);
  return x;
}
uint32_t Bits(float x) {
  uint32_t word;
  std::memcpy(&word, &x, sizeof word);
  return word;
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
  bool square_root;
};
const Function kFunctions[] = {{"floorf", gmath_floorf, false},
    {"ceilf", gmath_ceilf, false}, {"truncf", gmath_truncf, false},
    {"roundf", gmath_roundf, false}, {"rintf", gmath_rintf, false},
    {"fabsf", gmath_fabsf, false}, {"sqrtf", gmath_sqrtf, true}};

struct Policy {
  int required, allowed;
};

Policy UnaryPolicy(const Function & function, uint32_t x) {
  uint32_t a = x & ~kSign;
  if (a > kInf) {
    int flags = (a & kQuiet) == 0 ? FE_INVALID : 0;
    return {flags, flags};
  }
  if (function.square_root) {
    if ((x & kSign) != 0 && a != 0) {
      return {FE_INVALID, FE_INVALID};
    }
    if (a != 0 && a < kInf) {
      return {0, FE_INEXACT};
    }
  }
  return {0, 0};
}

int SeedFlags(int requested) {
  std::feclearexcept(FE_ALL_EXCEPT);
  if (requested != 0) {
    EXPECT_EQ(std::feraiseexcept(requested), 0);
  }
  return std::fetestexcept(FE_ALL_EXCEPT);
}

float CheckUnary(
    const Function & function, uint32_t input, int mode, int seed = 0) {
  Policy policy = UnaryPolicy(function, input);
  int existing = SeedFlags(seed);
  errno = E2BIG;
  float result = function.fn(Float(input));
  int result_errno = errno;
  int result_mode = std::fegetround();
  int result_flags = std::fetestexcept(FE_ALL_EXCEPT);
  EXPECT_EQ(result_errno, E2BIG) << function.name;
  EXPECT_EQ(result_mode, mode) << function.name;
  EXPECT_EQ(
      result_flags & (policy.required | existing), policy.required | existing)
      << function.name << " input " << std::hex << input;
  EXPECT_EQ(result_flags & ~(policy.allowed | existing), 0)
      << function.name << " input " << std::hex << input;
  uint32_t a = input & ~kSign;
  if (function.square_root && (input & kSign) == 0 && a > 0 && a < kInf) {
    EXPECT_TRUE(std::isnormal(result)) << std::hex << input;
  }
  return result;
}

float CheckCopy(uint32_t x, uint32_t y, int mode, int seed = 0) {
  uint32_t a = x & ~kSign;
  int required = a > kInf && (a & kQuiet) == 0 ? FE_INVALID : 0;
  int existing = SeedFlags(seed);
  errno = E2BIG;
  float result = gmath_copysignf(Float(x), Float(y));
  int result_errno = errno;
  int result_mode = std::fegetround();
  int result_flags = std::fetestexcept(FE_ALL_EXCEPT);
  EXPECT_EQ(result_errno, E2BIG);
  EXPECT_EQ(result_mode, mode);
  EXPECT_EQ(result_flags, required | existing) << std::hex << x << " " << y;
  return result;
}

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

struct Entry {
  uint64_t x, y, result;
  uint32_t x32, y32, result32;
};

std::vector<Entry> Load(const char * name, bool binary = false) {
  const char * env = std::getenv("GMATH_FLOATBASIC_CORPUS_DIR");
  std::string directory = env && *env ? env : "tests/corpus";
  std::ifstream input(directory + "/" + name + ".corpus");
  EXPECT_TRUE(input.is_open()) << "missing " << name << " corpus";
  std::vector<Entry> entries;
  std::set<std::pair<uint32_t, uint32_t>> inputs;
  bool have_count = false;
  size_t declared_entries = 0;
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty()) {
      continue;
    }
    if (line[0] == '#') {
      std::istringstream header(line.substr(1));
      std::string token;
      while (header >> token) {
        if (token == "entries") {
          EXPECT_FALSE(have_count) << "duplicate " << name << " entries header";
          have_count = true;
          std::string count;
          if (!(header >> count) ||
              !PositiveInteger(count, &declared_entries)) {
            ADD_FAILURE() << "invalid " << name << " entries header: " << line;
          }
        }
      }
      continue;
    }
    Entry entry{};
    std::string extra;
    std::istringstream parser(line);
    bool valid = static_cast<bool>(parser >> std::hex >> entry.x);
    if (valid && binary) {
      valid = static_cast<bool>(parser >> entry.y);
    }
    valid = valid && static_cast<bool>(parser >> entry.result);
    if (!valid || (parser >> extra)) {
      ADD_FAILURE() << "bad " << name << " corpus row: " << line;
      continue;
    }
    if (!NarrowExact(entry.x, &entry.x32) ||
        (binary && !NarrowExact(entry.y, &entry.y32)) ||
        !NarrowExact(entry.result, &entry.result32)) {
      ADD_FAILURE() << "invalid " << name
                    << " binary32 representation: " << line;
      continue;
    }
    if (!inputs.emplace(entry.x32, entry.y32).second) {
      ADD_FAILURE() << "duplicate " << name << " input words: " << std::hex
                    << entry.x << " " << entry.y;
    }
    entries.push_back(entry);
  }
  EXPECT_TRUE(have_count) << "missing required " << name << " entries header";
  EXPECT_EQ(entries.size(), declared_entries)
      << name << " corpus count disagrees with header";
  const char * minimum = std::getenv("GMATH_FLOATBASIC_MIN_ENTRIES");
  size_t required = 1000;
  if (minimum != nullptr && !PositiveInteger(minimum, &required)) {
    ADD_FAILURE() << "GMATH_FLOATBASIC_MIN_ENTRIES must be a complete positive "
                     "decimal integer";
  }
  EXPECT_GE(entries.size(), required)
      << "missing or truncated " << name << " corpus";
  return entries;
}

void CheckCorpus(int mode, bool include_sqrt) {
  for (const Function & function : kFunctions) {
    if (function.square_root && !include_sqrt) {
      continue;
    }
    for (const Entry & entry : Load(function.name)) {
      float result = CheckUnary(function, entry.x32, mode);
      EXPECT_EQ(Bits(result), entry.result32)
          << function.name << " input " << std::hex << entry.x;
    }
  }
  for (const Entry & entry : Load("copysignf", true)) {
    float result = CheckCopy(entry.x32, entry.y32, mode);
    EXPECT_EQ(Bits(result), entry.result32)
        << std::hex << entry.x << " " << entry.y;
  }
}

uint32_t SpecialExpected(const Function & function, uint32_t input) {
  uint32_t a = input & ~kSign;
  if (a > kInf) {
    return kNaN;
  }
  if (function.square_root && (input & kSign) != 0 && a != 0) {
    return kNaN;
  }
  if (std::string(function.name) == "fabsf") {
    return a;
  }
  return input;
}

std::vector<uint32_t> RawValues() {
  std::vector<uint32_t> values = {
      0, kSign, Bits(1.0f), Bits(-1.0f), kInf, kInf | kSign};
  for (uint32_t payload : {1u, kQuiet - 1, kQuiet, kQuiet + 1,
           (kQuiet << 1) - 1, 0x12345u, kQuiet | 0x12345u}) {
    values.push_back(kInf | payload);
    values.push_back(kSign | kInf | payload);
  }
  return values;
}

std::vector<uint32_t> FiniteStateValues() {
  std::vector<uint32_t> values;
  const uint32_t positive[] = {1, 2, 0x007fffff, 0x00800000, 0x00800001,
      kInf - 1, Bits(0.25f), Bits(0.5f) - 1, Bits(0.5f), Bits(0.5f) + 1,
      Bits(1.25f), Bits(1.5f) - 1, Bits(1.5f), Bits(1.5f) + 1, Bits(2.0f),
      Bits(2.75f), Bits(0x1p23f) - 1, Bits(0x1p23f), Bits(0x1p23f) + 1};
  for (uint32_t word : positive) {
    values.push_back(word);
    values.push_back(word | kSign);
  }
  return values;
}

} // namespace

TEST(Floatbasic, CorpusIsExact) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  CheckCorpus(FE_TONEAREST, true);
}

TEST(Floatbasic, RoundingAndSignCorpusIsExactInEveryMode) {
  Environment saved;
  for (int mode : {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    CheckCorpus(mode, false);
  }
}

TEST(Floatbasic, RawNaNsZerosAndSignOnlySecondOperand) {
  Environment saved;
  const auto values = RawValues();
  for (int mode : {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (const Function & function : kFunctions) {
      for (uint32_t input : values) {
        float result = CheckUnary(function, input, mode);
        uint32_t a = input & ~kSign;
        if (!function.square_root || mode == FE_TONEAREST || a == 0 ||
            a >= kInf || (input & kSign) != 0) {
          EXPECT_EQ(Bits(result), SpecialExpected(function, input))
              << function.name << " " << std::hex << input;
        }
      }
    }
    for (uint32_t x : values) {
      for (uint32_t y : values) {
        uint32_t expected =
            (x & ~kSign) > kInf ? kNaN : (x & ~kSign) | (y & kSign);
        EXPECT_EQ(Bits(CheckCopy(x, y, mode)), expected)
            << std::hex << x << " " << y;
      }
    }
  }
}

TEST(Floatbasic, ErrnoAndEveryIncomingFlagArePreserved) {
  Environment saved;
  auto values = RawValues();
  const auto finite = FiniteStateValues();
  values.insert(values.end(), finite.begin(), finite.end());
  const int seeds[] = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
      FE_INEXACT, FE_ALL_EXCEPT};
  for (int mode : {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (int seed : seeds) {
      for (const Function & function : kFunctions) {
        for (uint32_t input : values) {
          (void)CheckUnary(function, input, mode, seed);
        }
      }
      for (uint32_t x : values) {
        for (uint32_t y : values) {
          (void)CheckCopy(x, y, mode, seed);
        }
      }
    }
  }
}

TEST(Floatbasic, SqrtStateAndNormalOutputAtArgumentExtremes) {
  Environment saved;
  const Function function{"sqrtf", gmath_sqrtf, true};
  const uint32_t values[] = {1, 2, 0x007fffff, 0x00800000, 0x00800001,
      Bits(1.0f), Bits(2.0f), Bits(4.0f), kInf - 1};
  for (int mode : {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    for (int seed : {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
             FE_INEXACT, FE_ALL_EXCEPT}) {
      for (uint32_t input : values) {
        // Outside nearest, only the state/exception/range contract is tested.
        (void)CheckUnary(function, input, mode, seed);
      }
    }
  }
}

TEST(Floatbasic, CorpusWordsMustBeExactBinary32Representations) {
  struct Case {
    uint64_t wide;
    uint32_t narrow;
  };
  const Case valid[] = {{0, 0}, {0x8000000000000000ull, kSign},
      {0x3ff0000000000000ull, 0x3f800000u},
      {0x3ff0000020000000ull, 0x3f800001u}, {0x36a0000000000000ull, 1},
      {0x3810000000000000ull, 0x00800000u},
      {0x47efffffe0000000ull, 0x7f7fffffu}, {0x7ff0000000000000ull, kInf},
      {0xfff0000000000000ull, kInf | kSign},
      {0x7ff8000020000000ull, 0x7fc00001u},
      {0xfff8000020000000ull, 0xffc00001u}};
  for (const Case & example : valid) {
    uint32_t word = 0;
    EXPECT_TRUE(NarrowExact(example.wide, &word));
    EXPECT_EQ(word, example.narrow);
  }
  for (uint64_t invalid : {1ull, 0x3ff0000000000001ull, 0x3690000000000000ull,
           0x47f0000000000000ull, 0x7ff8000000000001ull,
           0x7ff0000020000000ull}) {
    uint32_t word = 0;
    EXPECT_FALSE(NarrowExact(invalid, &word)) << std::hex << invalid;
  }
}

TEST(Floatbasic, PositiveCountParserRejectsPartialZeroAndOverflow) {
  size_t count = 0;
  EXPECT_TRUE(PositiveInteger("1", &count));
  EXPECT_EQ(count, 1u);
  EXPECT_TRUE(PositiveInteger(
      std::to_string(std::numeric_limits<size_t>::max()), &count));
  EXPECT_EQ(count, std::numeric_limits<size_t>::max());
  for (const char * text : {"", "0", "-1", "+1", " 1", "1 ", "1junk", "junk"}) {
    EXPECT_FALSE(PositiveInteger(text, &count)) << text;
  }
  EXPECT_FALSE(PositiveInteger(
      std::to_string(std::numeric_limits<size_t>::max()) + "0", &count));
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
