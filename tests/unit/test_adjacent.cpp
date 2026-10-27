/**
 * @file Exact adjacent-value references, boundaries and caller-state contracts.
 * Copyright 2026 by Corey Pennycuff
 */
#include "test_helpers.h"
#include <array>
#include <bit>
#include <cerrno>
#include <cfenv>
#include <charconv>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <ghoti.io/math/basic.h>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {
struct Format {
  bool single;
  uint64_t sign, infinity, quiet, minimum;
  const char * name;
};
constexpr Format Double{false,
                        0x8000000000000000ull,
                        0x7ff0000000000000ull,
                        0x0008000000000000ull,
                        0x0010000000000000ull,
                        "nextafter"};
constexpr Format Float{true,          0x80000000ull, 0x7f800000ull,
                       0x00400000ull, 0x00800000ull, "nextafterf"};
struct Entry {
  uint64_t x, y, result, flags;
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
double Value(uint64_t bits, const Format & format) {
  if (format.single) {
    return static_cast<double>(
        std::bit_cast<float>(static_cast<uint32_t>(bits)));
  }
  return std::bit_cast<double>(bits);
}
// Direction uses exact host comparisons only after raw NaNs are removed.
// Adjacency is certified by unsigned magnitude distance and destination bounds,
// independently of the runtime's signed ordering keys. Fraction/MPFR generation
// independently constructs the exact target, including subnormal spacing.
void Validate(const Entry & e, const Format & f) {
  if (f.single &&
      (e.x > UINT32_MAX || e.y > UINT32_MAX || e.result > UINT32_MAX)) {
    throw std::runtime_error("Float word outside32bits");
  }
  uint64_t a = e.x & ~f.sign, b = e.y & ~f.sign, r = e.result & ~f.sign;
  if (a > f.infinity || b > f.infinity) {
    uint64_t invalid = (a > f.infinity && !(e.x & f.quiet)) ||
                       (b > f.infinity && !(e.y & f.quiet));
    if (e.result != (f.infinity | f.quiet) || e.flags != invalid) {
      throw std::runtime_error("wrong NaN policy");
    }
    return;
  }
  if (e.x == e.y || !(a | b)) {
    if (e.result != e.y || e.flags) {
      throw std::runtime_error("wrong equality policy");
    }
    return;
  }
  uint64_t flags = 0;
  if (!a) {
    if (e.result != ((e.y & f.sign) | 1)) {
      throw std::runtime_error("wrong zero step");
    }
  } else if (a == f.infinity) {
    if (e.result != ((e.x & f.sign) | (f.infinity - 1))) {
      throw std::runtime_error("wrong infinity step");
    }
  } else {
    uint64_t distance = a > r ? a - r : r - a;
    if (r > f.infinity || (e.result & f.sign) != (e.x & f.sign) ||
        distance != 1) {
      throw std::runtime_error("not adjacent magnitude");
    }
    double x = Value(e.x, f), y = Value(e.y, f), result = Value(e.result, f);
    bool up = x < y;
    if ((up ? !(result > x) : !(result < x)) ||
        (up ? result > y : result < y)) {
      throw std::runtime_error("wrong direction or destination bound");
    }
  }
  if (a < f.infinity && r == f.infinity) {
    flags = 20;
  } else if (r < f.minimum) {
    flags = 24;
  }
  if (e.flags != flags) {
    throw std::runtime_error("wrong range flags");
  }
}
std::vector<Entry> Parse(std::istream & input, const Format & f) {
  std::string line, extra;
  if (!std::getline(input, line) ||
      line != "# Pinned oracle: tools/oracle/gen_corpus_adjacent.py; MPFR "
              "4.2.2 gmpy2 2.3.2") {
    throw std::runtime_error("wrong provenance");
  }
  if (!std::getline(input, line) ||
      line != std::string("# function ") + f.name + "_raw") {
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
    throw std::runtime_error("excessive random count");
  }
  uint64_t count = Number(fields[8], 10);
  if (!count || count > 250000) {
    throw std::runtime_error("invalid population");
  }
  if (!std::getline(input, line) ||
      line != "# raw x y result normalized-flags") {
    throw std::runtime_error("wrong columns");
  }
  std::vector<Entry> rows;
  std::set<std::pair<uint64_t, uint64_t>> seen;
  while (std::getline(input, line)) {
    if (rows.size() >= count) {
      throw std::runtime_error("rows exceed declared population");
    }
    std::istringstream row(line);
    std::array<uint64_t, 4> words{};
    for (auto & word : words) {
      std::string text;
      if (!(row >> text)) {
        throw std::runtime_error("missing row field");
      }
      word = Number(text, 16, 16);
    }
    Entry e{words[0], words[1], words[2], words[3]};
    if (row >> extra || !seen.emplace(e.x, e.y).second) {
      throw std::runtime_error("extra or duplicate row");
    }
    Validate(e, f);
    rows.push_back(e);
  }
  if (input.bad() || rows.size() != count) {
    throw std::runtime_error("population mismatch");
  }
  return rows;
}
std::vector<Entry> Load(const Format & f) {
  const char * override_directory = std::getenv("GMATH_ADJACENT_CORPUS_DIR");
  std::string directory = override_directory && *override_directory
                              ? override_directory
                              : "tests/corpus";
  std::ifstream input(directory + "/" + f.name + "-special.corpus");
  if (!input) {
    throw std::runtime_error("missing adjacent corpus: " + directory);
  }
  auto rows = Parse(input, f);
  if (rows.size() < 1000) {
    throw std::runtime_error("insufficient adjacent sample");
  }
  std::set<std::pair<uint64_t, uint64_t>> needed = {
      {0, f.sign},
      {f.sign, 0},
      {0, f.infinity},
      {1, 0},
      {f.minimum, 0},
      {f.minimum - 1, f.infinity},
      {f.infinity - 1, f.infinity},
      {f.infinity, 0},
      {f.infinity | f.quiet, f.infinity | 1},
      {f.infinity | 1, f.infinity | f.quiet}};
  for (const auto & row : rows) {
    needed.erase({row.x, row.y});
  }
  if (!needed.empty()) {
    throw std::runtime_error("missing essential adjacent cases");
  }
  std::printf("  %s: %zu reference entries from %s\n", f.name, rows.size(),
              directory.c_str());
  return rows;
}
int Flags(uint64_t flags) {
  return ((flags & 1) ? FE_INVALID : 0) | ((flags & 4) ? FE_OVERFLOW : 0) |
         ((flags & 8) ? FE_UNDERFLOW : 0) | ((flags & 16) ? FE_INEXACT : 0);
}
bool Selected(const Entry & e, size_t index, const Format & f) {
  uint64_t one = f.single ? 0x3f800000ull : 0x3ff0000000000000ull;
  std::set<uint64_t> points = {0,
                               1,
                               2,
                               3,
                               f.minimum - 1,
                               f.minimum,
                               f.minimum + 1,
                               one,
                               f.infinity - 1,
                               f.infinity,
                               f.infinity | 1,
                               f.infinity | f.quiet,
                               f.infinity | f.quiet | 1};
  return index % 127 == 0 ||
         (points.contains(e.x & ~f.sign) && points.contains(e.y & ~f.sign));
}
bool Check(const Entry & e, const Format & f, int mode, int seed,
           int error_seed = 739) {
  EXPECT_EQ(std::fesetround(mode), 0);
  EXPECT_EQ(std::feclearexcept(FE_ALL_EXCEPT), 0);
  EXPECT_EQ(std::feraiseexcept(seed), 0);
  int incoming = std::fetestexcept(FE_ALL_EXCEPT);
  errno = error_seed;
  uint64_t result;
  if (f.single) {
    float x = std::bit_cast<float>(static_cast<uint32_t>(e.x)),
          y = std::bit_cast<float>(static_cast<uint32_t>(e.y));
    float (*volatile fn)(float, float) = gmath_nextafterf;
    result = std::bit_cast<uint32_t>(fn(x, y));
  } else {
    double (*volatile fn)(double, double) = gmath_nextafter;
    result = std::bit_cast<uint64_t>(
        fn(std::bit_cast<double>(e.x), std::bit_cast<double>(e.y)));
  }
  int error = errno, flags = std::fetestexcept(FE_ALL_EXCEPT),
      rounding = std::fegetround();
  EXPECT_EQ(result, e.result) << f.name << " " << std::hex << e.x << " " << e.y;
  EXPECT_EQ(flags, incoming | Flags(e.flags))
      << f.name << " " << std::hex << e.x << " " << e.y;
  EXPECT_EQ(error, error_seed);
  EXPECT_EQ(rounding, mode);
  return result == e.result && flags == (incoming | Flags(e.flags)) &&
         error == error_seed && rounding == mode;
}
std::string Fixture(const Format & f, const std::string & row,
                    const std::string & count = "1") {
  return std::string("# Pinned oracle: tools/oracle/gen_corpus_adjacent.py; "
                     "MPFR 4.2.2 gmpy2 2.3.2\n# function ") +
         f.name + "_raw\n# seed 1 count 0 fresh False entries " + count +
         "\n# raw x y result normalized-flags\n" + row;
}
} // namespace
TEST(Adjacent, ExactReferencesAllModes) {
  Environment saved;
  for (const auto & f : {Double, Float}) {
    std::vector<Entry> rows;
    ASSERT_NO_THROW(rows = Load(f));
    for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
      for (const auto & e : rows) {
        if (!Check(e, f, mode, 0)) {
          return;
        }
      }
    }
  }
}
TEST(Adjacent, SelectedIncomingState) {
  Environment saved;
  const std::array<int, 5> flags = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW,
                                    FE_UNDERFLOW, FE_INEXACT};
  for (const auto & f : {Double, Float}) {
    std::vector<Entry> rows;
    ASSERT_NO_THROW(rows = Load(f));
    for (size_t i = 0; i < rows.size(); ++i) {
      if (Selected(rows[i], i, f)) {
        for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
          for (unsigned mask = 0; mask < 32; ++mask) {
            int seed = 0;
            for (unsigned bit = 0; bit < flags.size(); ++bit) {
              if (mask & (1u << bit)) {
                seed |= flags[bit];
              }
            }
            for (int error : {0, 739}) {
              if (!Check(rows[i], f, mode, seed, error)) {
                return;
              }
            }
          }
        }
      }
    }
  }
}
TEST(Adjacent, RawNaNOperandPriority) {
  Environment saved;
  for (const auto & f : {Double, Float}) {
    uint64_t q = f.infinity | f.quiet, s = f.infinity | 1;
    for (const auto & pair :
         std::vector<std::pair<uint64_t, uint64_t>>{{q, s},
                                                    {s, q},
                                                    {q, f.sign | s},
                                                    {f.sign | s, q},
                                                    {s, s},
                                                    {q, q}}) {
      Entry e{pair.first, pair.second, q,
              pair.first == q && pair.second == q ? 0u : 1u};
      for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
        for (int seed : {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
                         FE_INEXACT, FE_ALL_EXCEPT}) {
          if (!Check(e, f, mode, seed)) {
            return;
          }
        }
      }
    }
  }
}
TEST(Adjacent, ParserRejectsMalformedAndIncorrectTargets) {
  Environment saved;
  for (const auto & f : {Double, Float}) {
    const std::string row =
        "0000000000000000 0000000000000000 0000000000000000 0000000000000000\n";
    std::istringstream good(Fixture(f, row));
    EXPECT_NO_THROW(Parse(good, f));
    for (const auto & text : {Fixture(f, row + row), Fixture(f, row, "2"),
                              Fixture(f, row.substr(1)), Fixture(f, ""),
                              Fixture(f, row, "0"), Fixture(f, row, "-1")}) {
      std::istringstream bad(text);
      EXPECT_THROW(Parse(bad, f), std::runtime_error);
    }
    for (const auto & change : std::vector<std::pair<std::string, std::string>>{
             {"MPFR 4.2.2", "MPFR other"},
             {"_raw", "_wrong"},
             {"seed 1", "seed -1"},
             {"seed 1", "seed 18446744073709551616"},
             {"count 0", "count 50001"},
             {"fresh False", "fresh false"},
             {"entries 1", "entries 250001"},
             {"entries 1", "entries 1 extra"},
             {"normalized-flags", "bad-columns"}}) {
      std::string text = Fixture(f, row);
      text.replace(text.find(change.first), change.first.size(), change.second);
      std::istringstream bad(text);
      EXPECT_THROW(Parse(bad, f), std::runtime_error);
    }
    for (const Entry & e : std::vector<Entry>{
             {0, f.sign, 0, 0},
             {0, 1, 1, 0},
             {1, 0, 0, 0},
             {f.minimum - 1, f.infinity, f.minimum, 24},
             {f.minimum, 0, f.minimum - 1, 0},
             {f.infinity - 1, f.infinity, f.infinity, 0},
             {f.infinity, 0, f.infinity - 1, 20},
             {f.infinity | f.quiet, f.infinity | 1, f.infinity | f.quiet, 0},
             {f.minimum, f.infinity, f.minimum + 2, 0},
             {f.minimum, f.infinity, f.minimum - 1, 24}}) {
      EXPECT_THROW(Validate(e, f), std::runtime_error);
    }
  }
}
int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
