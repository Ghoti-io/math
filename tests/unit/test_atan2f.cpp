/**
 * @file Binary32 two-argument arctangent pinned references and strict corpus format.
 * Copyright 2026 by Corey Pennycuff
 */
#include "test_helpers.h"
#include <ghoti.io/math/elementary.h>
#include <algorithm>
#include <array>
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
  return line == "# Pinned oracle: tools/oracle/gen_corpus_atan2f.py; "
      "MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1";
}

struct Entry {
  uint32_t y, x, result, error;
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


bool Signaling(uint32_t word) { return (word&~kSign)>kInf && (word&kQuiet)==0; }
bool ZeroAngle(uint32_t y,uint32_t x) {
  return ((y&~kSign)==0 && !(x&kSign)) || ((y&~kSign)<kInf && x==kInf);
}
bool SpecialResult(uint32_t y,uint32_t x,uint32_t * result) {
  uint32_t a=y&~kSign,b=x&~kSign,sign=y&kSign;
  if (a>kInf || b>kInf) *result=kNaN;
  else if (ZeroAngle(y,x)) *result=sign;
  else if (!a) *result=sign|0x40490fdbu;
  else if (!b || (a==kInf && b<kInf)) *result=sign|0x3fc90fdbu;
  else if (a==kInf && b==kInf) *result=sign|((x&kSign)?0x4016cbe4u:0x3f490fdbu);
  else if (b==kInf) *result=sign|0x40490fdbu;
  else if (a==b) *result=sign|((x&kSign)?0x4016cbe4u:0x3f490fdbu);
  else return false;
  return true;
}
bool Tiny(uint32_t y,uint32_t x) {
  uint32_t a=y&~kSign;
  return x>0 && x<kInf && a>0 && a<kInf && double(Float(a))<double(Float(x))*0x1p-30;
}
uint32_t AngleError(uint32_t result) {
  uint32_t a=result&~kSign;
  if (!a || a>=kInf) return 0;
  return (a==0x4016cbe4u?0xbcccde2eu:0xbebbbd2eu)^(result&kSign);
}
int RequiredFlags(uint32_t y,uint32_t x,uint32_t result) {
  if (Signaling(y)||Signaling(x)) return FE_INVALID;
  if ((y&~kSign)>kInf || (x&~kSign)>kInf || ZeroAngle(y,x)) return 0;
  return FE_INEXACT|((result&~kSign)<0x00800000u?FE_UNDERFLOW:0);
}
// In the tiny region atan(r)<r, while every non-midpoint Float ratio is
// separated from an output midpoint by more than2^-25 FloatULP. Products
// below have at most49 significant bits and are exact normal Doubles.
bool TinyCertificate(const Entry & e) {
  uint32_t r=e.result&~kSign;
  if (r>=0x31000000u || (e.result&kSign)!=(e.y&kSign)) return false;
  double y=Float(e.y&~kSign),x=Float(e.x);
  double high=(double(Float(r))+double(Float(r+1)))/2;
  if (y>x*high) return false;
  if (r) {
    double low=(double(Float(r-1))+double(Float(r)))/2;
    if (y<=x*low) return false;
  }
  // A nonzero rational displacement from the rounded Float is much larger
  // than atan(r)-r. Equality means a strictly negative magnitude error.
  bool negative_magnitude_error=y<=x*double(Float(r));
  bool negative_error=negative_magnitude_error!=bool(e.y&kSign);
  return bool(e.error&kSign)==negative_error;
}
bool ValidResult(const Entry & e) {
  uint32_t special;
  if (SpecialResult(e.y,e.x,&special)) return e.result==special && e.error==AngleError(special);
  uint32_t r=e.result&~kSign;
  if ((e.result&kSign)!=(e.y&kSign) || r>0x40490fdbu || (e.error&~kSign)>0x3f000000u) return false;
  if (Tiny(e.y,e.x)) return TinyCertificate(e);
  if (r<0x00800000u) return false;
  // Concrete actual-transcendental pairs protect sign and finite payload
  // semantics independently of the separate rational metric fixtures.
  if ((e.y&~kSign)==kOne && e.x==0x40000000u)
    return e.result==(0x3eed6338u|(e.y&kSign)) && e.error==(0x3e2c376au^(e.y&kSign));
  return true;
}
bool ParseRow(const std::string & line,Entry * entry) {
  std::istringstream parser(line);
  std::string x,y,r,e,extra; uint64_t xb=0,yb=0,rb=0,eb=0;
  if (!(parser>>x>>y>>r>>e)||(parser>>extra)||!HexWord(x,16,&xb)||!HexWord(y,16,&yb)||
      !HexWord(r,16,&rb)||!HexWord(e,8,&eb)||!NarrowExact(xb,&entry->y)||
      !NarrowExact(yb,&entry->x)||!NarrowExact(rb,&entry->result)) return false;
  entry->error=static_cast<uint32_t>(eb);
  return ValidResult(*entry);
}
// The stream parser returns a diagnostic instead of emitting gtest failures,
// so malformed in-memory fixtures exercise exactly the production loader.
bool ParseCorpus(std::istream & input, size_t minimum,
    std::vector<Entry> * entries, std::string * reason) {
  entries->clear();
  std::set<std::pair<uint32_t,uint32_t>> inputs;
  bool provenance = false, function = false, metadata = false, format = false;
  size_t declared = 0;
  const std::string expected_format = "# binary32 y/x/results widened exactly to binary64; signed binary32 error in true binary32 ULP";
  auto fail = [&](const std::string & message) {
    *reason = message;
    return false;
  };
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty()) continue;
    if (line[0] == '#') {
      if (line.find("# Pinned oracle:") == 0) {
        if (provenance) return fail("duplicate atan2f provenance");
        if (!PinnedProvenance(line)) return fail("invalid atan2f pinned provenance");
        provenance = true;
      }
      else if (line.find("# function") == 0) {
        if (function) return fail("duplicate atan2f function header");
        if (line != "# function atan2f") return fail("invalid atan2f function header");
        function = true;
      }
      else if (line.find("# seed") == 0) {
        if (metadata) return fail("duplicate atan2f sample metadata");
        if (!SampleMetadata(line, &declared)) return fail("invalid atan2f sample metadata");
        metadata = true;
      }
      else if (line.find("# binary32") == 0) {
        if (format) return fail("duplicate atan2f format header");
        if (line != expected_format) return fail("invalid atan2f binary32 format header");
        format = true;
      }
      continue;
    }
    if (!provenance || !function || !metadata || !format) {
      return fail("missing required atan2f corpus metadata before data");
    }
    Entry entry{};
    if (!ParseRow(line, &entry)) return fail("bad atan2f corpus row or binary32 representation: " + line);
    if (!inputs.emplace(entry.x,entry.y).second) return fail("duplicate atan2f input word");
    entries->push_back(entry);
  }
  if (input.bad()) return fail("cannot read atan2f corpus");
  if (!provenance || !function || !metadata || !format) return fail("missing required atan2f corpus metadata");
  if (entries->size() != declared) return fail("atan2f corpus count disagrees with header");
  if (entries->size() < minimum) return fail("missing or truncated atan2f corpus");
  return true;
}


using Pair=std::pair<uint32_t,uint32_t>;
std::set<Pair> EssentialPairs() {
  std::set<Pair> required;
  auto add=[&](uint32_t y,uint32_t x) {
    for (uint32_t sy:{0u,kSign}) for (uint32_t sx:{0u,kSign}) {
      required.emplace(y|sy,x|sx);required.emplace(x|sx,y|sy);
    }
  };
  for (Pair p:{Pair{0,0},Pair{0,kOne},Pair{1,0x40000000},Pair{3,0x40000000},
      Pair{0x00ffffff,0x40000000},Pair{1,kInf-1},Pair{kOne,kOne},
      Pair{0x007fffff,kOne},Pair{0x00800000,kOne}}) add(p.first,p.second);
  required.emplace(kInf,kNaN);required.emplace(kNaN,kInf);
  for (unsigned e=1;e<255;++e) {add(e<<23,1);add(e<<23,kOne);}
  for (unsigned bit=0;bit<23;++bit) add(1u<<bit,1);
  for (uint32_t raw:{0x30800000u,0x3e000000u}) for (int d:{-1,0,1}) add(raw+uint32_t(d),kOne);
  for (unsigned j=8;j<=64;++j) {
    // j/64 and (2j+1)/128 are exactly representable Floats.
    uint32_t center=Bits(float(j)*0x1p-6f),half=Bits(float(2*j+1)*0x1p-7f);
    for (int d:{-1,0,1}) {add(center+uint32_t(d),kOne);add(half+uint32_t(d),kOne);}
  }
  return required;
}
bool EssentialCoverage(const std::vector<Entry> & entries) {
  std::set<Pair> present;for (const auto & e:entries) present.emplace(e.y,e.x);
  for (Pair p:EssentialPairs()) if (!present.count(p)) return false;
  return true;
}
std::vector<Entry> Load() {
  const char * env=std::getenv("GMATH_ATAN2F_CORPUS_DIR");
  std::string directory=env&&*env?env:"tests/corpus";
  std::ifstream input(directory+"/atan2f.corpus");std::vector<Entry> entries;
  if (!input.is_open()) {ADD_FAILURE()<<"missing atan2f corpus: "<<directory;return entries;}
  size_t minimum=1000;const char * min=std::getenv("GMATH_ATAN2F_MIN_ENTRIES");
  if (min&&!PositiveInteger(min,&minimum)) {ADD_FAILURE()<<"GMATH_ATAN2F_MIN_ENTRIES must be a complete positive decimal integer";return entries;}
  std::string payload((std::istreambuf_iterator<char>(input)),std::istreambuf_iterator<char>()),reason;
  std::istringstream stream(payload);
  if (input.bad()||!ParseCorpus(stream,minimum,&entries,&reason)) {ADD_FAILURE()<<reason;entries.clear();}
  if (!entries.empty()&&(!env||!*env)&&payload.find("\n# seed 20261027 count 3000 fresh False entries 35309\n")==std::string::npos) {
    ADD_FAILURE()<<"incorrect committed atan2f sample metadata";entries.clear();
  }
  if (!entries.empty()&&!EssentialCoverage(entries)) {ADD_FAILURE()<<"missing essential atan2f coverage";entries.clear();}
  return entries;
}
double TrueUlp(const Entry & e) {
  uint32_t a=e.result&~kSign;int exponent=int(a>>23)-127;
  int ue=std::max(exponent,-126)-23;
  if (exponent>-126 && !(a&0x007fffffu) && ((e.error^e.result)&kSign)) --ue;
  return std::ldexp(1.0,ue);
}
struct Interval {double low,high;};
Interval ErrorCell(uint32_t word) {
  if (!(word&~kSign)) {double half=std::ldexp(1.0,-150);return word&kSign?Interval{-half,0}:Interval{0,half};}
  double center=Float(word);
  return {(double(Float(word&kSign?word+1:word-1))+center)/2,
          (center+double(Float(word&kSign?word-1:word+1)))/2};
}
bool ExactMetric(const Entry & e) {return (e.result&~kSign)>=kInf || ZeroAngle(e.y,e.x);}
double UlpError(float y,const Entry & e) {
  if (ExactMetric(e)) return Bits(y)==e.result?0:std::numeric_limits<double>::infinity();
  if ((Bits(y)&~kSign)>=kInf) return std::numeric_limits<double>::infinity();
  double d=(double(y)-double(Float(e.result)))/TrueUlp(e);Interval cell=ErrorCell(e.error);
  return std::max(std::fabs(d-cell.low),std::fabs(d-cell.high));
}
bool WithinOneUlp(float y,const Entry & e) {
  if (ExactMetric(e)) return Bits(y)==e.result;
  if ((Bits(y)&~kSign)>=kInf) return false;
  double d=(double(y)-double(Float(e.result)))/TrueUlp(e);if (std::fabs(d)>2) return false;
  Interval cell=ErrorCell(e.error);return cell.low>=d-1 && cell.high<=d+1;
}
uint32_t Check(uint32_t y,uint32_t x,uint32_t expected,int mode,int seed=0,bool exact=true) {
  float a,b;std::memcpy(&a,&y,sizeof a);std::memcpy(&b,&x,sizeof b);
  EXPECT_EQ(std::fesetround(mode),0);EXPECT_EQ(std::feclearexcept(FE_ALL_EXCEPT),0);
  EXPECT_EQ(std::feraiseexcept(seed),0);int incoming=std::fetestexcept(FE_ALL_EXCEPT);
  errno=713;float (*volatile fn)(float,float)=gmath_atan2f;volatile float r=fn(a,b);
  int error=errno,flags=std::fetestexcept(FE_ALL_EXCEPT),rounding=std::fegetround();
  uint32_t bits=Bits(r),special;
  if (exact || SpecialResult(y,x,&special) || Tiny(y,x)) EXPECT_EQ(bits,expected)<<std::hex<<y<<","<<x;
  else {
    EXPECT_EQ(bits&kSign,y&kSign);EXPECT_GE(bits&~kSign,0x00800000u);EXPECT_LE(bits&~kSign,0x40490fdbu);
    if (!(x&kSign)) EXPECT_LE(bits&~kSign,0x3fc90fdbu);
    else EXPECT_GE(bits&~kSign,0x3fc90fdau);
  }
  EXPECT_EQ(flags,RequiredFlags(y,x,bits)|incoming)<<std::hex<<y<<","<<x;
  EXPECT_EQ(error,713);EXPECT_EQ(rounding,mode);return bits;
}
std::string Fixture(const std::string & rows,const std::string & count="1") {
  return "# Pinned oracle: tools/oracle/gen_corpus_atan2f.py; MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1\n# function atan2f\n# seed 20261027 count 0 fresh False entries "+count+
      "\n# binary32 y/x/results widened exactly to binary64; signed binary32 error in true binary32 ULP\n"+rows;
}
} // namespace

TEST(Atan2f, CorpusIsWithinOneUlp) {
  Environment saved;auto entries=Load();ASSERT_FALSE(entries.empty());double worst=0;uint32_t wy=0,wx=0;
  for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}) for (const auto & e:entries) {
    uint32_t result=Check(e.y,e.x,e.result,mode,0,false);
    if (mode==FE_TONEAREST) {
      double error=UlpError(Float(result),e);if (error>worst) {worst=error;wy=e.y;wx=e.x;}
      EXPECT_TRUE(WithinOneUlp(Float(result),e))<<std::hex<<e.y<<","<<e.x;
    }
  }
  ASSERT_EQ(std::fesetround(FE_TONEAREST),0);
  std::printf("  atan2f: %zu corpus entries, max error %.8f ULP (input bits %08x,%08x)\n",entries.size(),worst,wy,wx);
  EXPECT_LE(worst,0.51);
}
TEST(Atan2f, ExactSpecialsAndState) {
  Environment saved;const uint32_t words[]={0,kSign,1,kSign|1,0x007fffff,0x00800000,kOne,kOne|kSign,
      kInf-1,kInf,kInf|kSign,kNaN,kNaN|7,kNaN|kSign|7,kInf|1,kInf|kSign|1};
  for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO})
    for (int seed:{0,FE_INVALID,FE_DIVBYZERO,FE_OVERFLOW,FE_UNDERFLOW,FE_INEXACT,FE_ALL_EXCEPT})
      for (uint32_t y:words) for (uint32_t x:words) {
        uint32_t expected;if (SpecialResult(y,x,&expected)) Check(y,x,expected,mode,seed);
      }
}
TEST(Atan2f, TinyMidpointsAndEqualMagnitudeConstants) {
  Environment saved;
  const Entry cases[]={{1,0x40000000,0,0x3f000000},{3,0x40000000,1,0x3f000000},
      {0x00ffffff,0x40000000,0x007fffff,0x3f000000},{1,kInf-1,0,0},
      {kOne,kOne,0x3f490fdb,0xbebbbd2e}};
  for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO})
    for (int seed:{0,FE_INVALID,FE_DIVBYZERO,FE_OVERFLOW,FE_UNDERFLOW,FE_INEXACT,FE_ALL_EXCEPT})
      for (const auto & e:cases) for (uint32_t sy:{0u,kSign}) Check(e.y|sy,e.x,e.result|sy,mode,seed);
}
TEST(Atan2f, PairParserMetadataAndSemanticCertificates) {
  const std::string row="0000000000000000 3ff0000000000000 0000000000000000 00000000\n";
  std::vector<Entry> entries;std::string reason;
  auto parse=[&](const std::string & text,size_t minimum=1) {std::istringstream in(text);return ParseCorpus(in,minimum,&entries,&reason);};
  EXPECT_TRUE(parse(Fixture(row)))<<reason;
  EXPECT_FALSE(parse(Fixture(row),2));EXPECT_FALSE(parse(Fixture(row,"2")));EXPECT_FALSE(parse(Fixture(row+row,"2")));
  for (const char * bad:{
      "0000000000000000 3ff0000000000000 00000000\n",
      "0000000000000000 3ff000000000000 0000000000000000 00000000\n",
      "0000000000000001 3ff0000000000000 0000000000000000 00000000\n",
      "0000000000000000 3ff0000000000001 0000000000000000 00000000\n",
      "0000000000000000 3ff0000000000000 0000000000000001 00000000\n",
      "0000000000000000 3ff0000000000000 8000000000000000 00000000\n",
      "0000000000000000 3ff0000000000000 0000000000000000 80000000\n",
      "0000000000000000 3ff0000000000000 0000000000000000 7fc00000\n"}) EXPECT_FALSE(parse(Fixture(bad)))<<bad;
  EXPECT_FALSE(parse(Fixture(row.substr(0,row.size()-1)+" extra\n")));
  const std::string valid=Fixture(row);
  for (const auto & change:std::vector<std::pair<std::string,std::string>>{
      {"MPFR 4.2.2","MPFR 4.2.1"},{"gmpy2 2.3.2","gmpy2 2.3.1"},
      {"mpmath 1.4.1","mpmath 1.4.1 mpmath 1.4.1"},{"# function atan2f","# function atan2"},
      {"fresh False","fresh maybe"},{"entries 1","entries 1junk"},{"seed 20261027","seed 1junk"}}) {
    std::string bad=valid;bad.replace(bad.find(change.first),change.first.size(),change.second);EXPECT_FALSE(parse(bad))<<change.first;
  }
  for (const std::string & header:{std::string("# Pinned oracle:"),std::string("# function"),std::string("# seed"),std::string("# binary32")}) {
    std::string bad=valid;size_t begin=bad.find(header),end=bad.find('\n',begin);bad.erase(begin,end-begin+1);EXPECT_FALSE(parse(bad));
  }
  EXPECT_FALSE(parse(valid+valid.substr(0,valid.find('\n')+1)));
  EXPECT_TRUE(ValidResult({kOne,kOne,0x3f490fdb,0xbebbbd2e}));
  EXPECT_FALSE(ValidResult({kOne,kOne,0x3f490fdb,0x3ebbbd2e}));
  EXPECT_FALSE(ValidResult({kOne,kOne,0x3f490fdc,0xbebbbd2e}));
  EXPECT_TRUE(ValidResult({kOne,0x40000000,0x3eed6338,0x3e2c376a}));
  EXPECT_FALSE(ValidResult({kOne,0x40000000,0x3eed6338,0xbe2c376a}));
  EXPECT_TRUE(ValidResult({0x00ffffff,0x40000000,0x007fffff,0x3f000000}));
  EXPECT_FALSE(ValidResult({0x00ffffff,0x40000000,0x00800000,0xbf000000}));
  EXPECT_TRUE(ValidResult({1,kOne,1,kSign}));
  EXPECT_FALSE(ValidResult({1,kOne,1,0}));
  EXPECT_TRUE(ValidResult({1|kSign,kOne,1|kSign,0}));
  EXPECT_FALSE(ValidResult({1|kSign,kOne,1|kSign,kSign}));
}
TEST(Atan2f, CompleteSignedErrorCellsAndCountParsers) {
  Environment saved;ASSERT_EQ(std::fesetround(FE_TONEAREST),0);
  EXPECT_FALSE(WithinOneUlp(Float(0x3f800002),{kOne,0x40000000,0x3f800001,kSign}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f800000),{kOne,0x40000000,0x3f800001,kSign}));
  EXPECT_FALSE(WithinOneUlp(Float(0xbf800002),{kOne|kSign,0x40000000,0xbf800001,0}));
  EXPECT_TRUE(WithinOneUlp(Float(0xbf800000),{kOne|kSign,0x40000000,0xbf800001,0}));
  EXPECT_FALSE(WithinOneUlp(Float(0x3f7fffff),{kOne,0x40000000,kOne,0x3f000000}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f7fffff),{kOne,0x40000000,kOne,0x3effffff}));
  EXPECT_FALSE(WithinOneUlp(Float(0xbf7fffff),{kOne|kSign,0x40000000,kOne|kSign,0xbf000000}));
  EXPECT_TRUE(WithinOneUlp(Float(0xbf7fffff),{kOne|kSign,0x40000000,kOne|kSign,0xbeffffff}));
  EXPECT_DOUBLE_EQ(ErrorCell(0).high,std::ldexp(1.0,-150));EXPECT_DOUBLE_EQ(ErrorCell(kSign).low,-std::ldexp(1.0,-150));
  EXPECT_DOUBLE_EQ(TrueUlp({1,0x40000000,0,0x3f000000}),std::ldexp(1.0,-149));
  EXPECT_EQ(RequiredFlags(1,0x40000000,0),FE_INEXACT|FE_UNDERFLOW);
  EXPECT_EQ(RequiredFlags(0,kOne,kSign),0);
  size_t count=0;EXPECT_TRUE(PositiveInteger("1",&count));
  for (const char * bad:{"","0","-1","+1","1junk"," 1","1 "}) EXPECT_FALSE(PositiveInteger(bad,&count));
  EXPECT_FALSE(PositiveInteger(std::to_string(std::numeric_limits<size_t>::max())+"0",&count));
}
TEST(Atan2f, EssentialPairsRejectMissingFamilies) {
  std::vector<Entry> entries;for (Pair p:EssentialPairs()) entries.push_back({p.first,p.second,0,0});EXPECT_TRUE(EssentialCoverage(entries));
  for (Pair missing:{Pair{1,0x40000000},Pair{3,0x40000000},Pair{0x00ffffff,0x40000000},Pair{0x30800000,kOne},Pair{0x3e000000,kOne}}) {
    auto subset=entries;subset.erase(std::remove_if(subset.begin(),subset.end(),[&](const Entry & e){return Pair{e.y,e.x}==missing;}),subset.end());EXPECT_FALSE(EssentialCoverage(subset));
  }
}
TEST(Atan2f, AllModeFiniteClassFlagsAndNearestOddSymmetry) {
  Environment saved;uint32_t state=0x49c0192du;
  for (unsigned i=0;i<5000;++i) {
    state^=state<<13;state^=state>>17;state^=state<<5;uint32_t x=state&~kSign;
    state^=state<<13;state^=state>>17;state^=state<<5;uint32_t y=state&~kSign;
    if (!x||!y||x>=kInf||y>=kInf) continue;
    ASSERT_EQ(std::fesetround(FE_TONEAREST),0);uint32_t baseline=Bits(gmath_atan2f(Float(y),Float(x)));
    EXPECT_EQ(Bits(gmath_atan2f(Float(y|kSign),Float(x))),baseline|kSign);
    for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}) {
      Check(y,x,baseline,mode,FE_DIVBYZERO,false);Check(y|kSign,x,baseline|kSign,mode,FE_DIVBYZERO,false);
      uint32_t special;if (SpecialResult(y,x|kSign,&special)) Check(y,x|kSign,special,mode,FE_DIVBYZERO);
      else Check(y,x|kSign,0,mode,FE_DIVBYZERO,false);
    }
  }
}
int main(int argc,char ** argv) {::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
