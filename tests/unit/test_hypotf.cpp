/**
 * @file Binary32 hypotenuse pinned references and strict corpus format.
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
  return line == "# Pinned oracle: tools/oracle/gen_corpus_hypotf.py; "
      "MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1";
}

struct Entry {
  uint32_t x, y, result, error;
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


// Independent test integers use half-minimum-subnormal units (2^-150).
// An exact input square/sum needs at most557 bits;18 limbs leave19 spare.
struct Big { std::array<uint32_t,18> limb{}; };
Big Add(Big a, const Big & b) {
  uint64_t carry=0;
  for (unsigned i=0;i<a.limb.size();++i) {
    uint64_t sum=uint64_t(a.limb[i])+b.limb[i]+carry;
    a.limb[i]=static_cast<uint32_t>(sum); carry=sum>>32;
  }
  return a;
}
int Compare(const Big & a,const Big & b) {
  for (int i=17;i>=0;--i) {
    if (a.limb[i]!=b.limb[i]) return a.limb[i]<b.limb[i]?-1:1;
  }
  return 0;
}
Big SquareCoefficient(uint32_t coefficient,unsigned shift) {
  Big out;
  uint64_t square=uint64_t(coefficient)*coefficient;
  unsigned bit=2*shift;
  while (square) {
    if (square&1) out.limb[bit/32]|=uint32_t(1)<<(bit%32);
    square>>=1; ++bit;
  }
  return out;
}
Big SquareFloat(uint32_t word) {
  uint32_t a=word&~kSign,field=a>>23,significand=a&0x007fffffu;
  return field?SquareCoefficient(significand|0x00800000u,field):SquareCoefficient(significand,1);
}
Big SumSquares(uint32_t x,uint32_t y) { return Add(SquareFloat(x),SquareFloat(y)); }
Big MidpointSquare(uint32_t result,bool upper) {
  unsigned field=result>>23;
  uint32_t q=result&0x007fffffu;
  if (!field) return SquareCoefficient(2*q+(upper?1u:~0u),0);
  q|=0x00800000u;
  if (!upper && q==0x00800000u && field>1) return SquareCoefficient(0x01ffffffu,field-2);
  return SquareCoefficient(2*q+(upper?1u:~0u),field-1);
}
bool Signaling(uint32_t word) { return (word&~kSign)>kInf && (word&kQuiet)==0; }
bool SpecialResult(uint32_t x,uint32_t y,uint32_t * result) {
  uint32_t a=x&~kSign,b=y&~kSign;
  if (Signaling(x)||Signaling(y)) *result=kNaN;
  else if (a==kInf||b==kInf) *result=kInf;
  else if (a>kInf||b>kInf) *result=kNaN;
  else if (!a) *result=b;
  else if (!b) *result=a;
  else return false;
  return true;
}
int RequiredFlags(uint32_t x,uint32_t y,uint32_t result) {
  if (Signaling(x)||Signaling(y)) return FE_INVALID;
  uint32_t special;
  if (SpecialResult(x,y,&special)) return 0;
  if (result==kInf) return FE_OVERFLOW|FE_INEXACT;
  if (Compare(SumSquares(x,y),SquareFloat(result))==0) return 0;
  return FE_INEXACT|(result<0x00800000u?FE_UNDERFLOW:0);
}
bool ValidResult(const Entry & entry) {
  uint32_t special;
  if (SpecialResult(entry.x,entry.y,&special)) return entry.result==special && entry.error==0;
  if ((entry.result&kSign)!=0 || entry.result>kInf ||
      (entry.error&~kSign)>0x3f000000u) return false;
  Big sum=SumSquares(entry.x,entry.y);
  Big overflow=SquareCoefficient(0x01ffffffu,253);
  if (Compare(sum,overflow)>=0) return entry.result==kInf && entry.error==0;
  if (entry.result==0 || entry.result>=kInf || entry.result<std::max(entry.x&~kSign,entry.y&~kSign)) return false;
  int lower=Compare(sum,MidpointSquare(entry.result,false));
  int upper=Compare(sum,MidpointSquare(entry.result,true));
  if (lower<0 || upper>0 || ((lower==0||upper==0)&&(entry.result&1u))) return false;
  int exact=Compare(sum,SquareFloat(entry.result));
  if (!exact) return entry.error==0;
  return ((entry.error&kSign)!=0)==(exact<0);
}
bool ParseRow(const std::string & line,Entry * entry) {
  std::istringstream parser(line);
  std::string x,y,r,e,extra; uint64_t xb=0,yb=0,rb=0,eb=0;
  if (!(parser>>x>>y>>r>>e)||(parser>>extra)||!HexWord(x,16,&xb)||!HexWord(y,16,&yb)||
      !HexWord(r,16,&rb)||!HexWord(e,8,&eb)||!NarrowExact(xb,&entry->x)||
      !NarrowExact(yb,&entry->y)||!NarrowExact(rb,&entry->result)) return false;
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
  const std::string expected_format = "# binary32 x/y/results widened exactly to binary64; signed binary32 error in true binary32 ULP";
  auto fail = [&](const std::string & message) {
    *reason = message;
    return false;
  };
  std::string line;
  while (std::getline(input, line)) {
    if (line.empty()) continue;
    if (line[0] == '#') {
      if (line.find("# Pinned oracle:") == 0) {
        if (provenance) return fail("duplicate hypotf provenance");
        if (!PinnedProvenance(line)) return fail("invalid hypotf pinned provenance");
        provenance = true;
      }
      else if (line.find("# function") == 0) {
        if (function) return fail("duplicate hypotf function header");
        if (line != "# function hypotf") return fail("invalid hypotf function header");
        function = true;
      }
      else if (line.find("# seed") == 0) {
        if (metadata) return fail("duplicate hypotf sample metadata");
        if (!SampleMetadata(line, &declared)) return fail("invalid hypotf sample metadata");
        metadata = true;
      }
      else if (line.find("# binary32") == 0) {
        if (format) return fail("duplicate hypotf format header");
        if (line != expected_format) return fail("invalid hypotf binary32 format header");
        format = true;
      }
      continue;
    }
    if (!provenance || !function || !metadata || !format) {
      return fail("missing required hypotf corpus metadata before data");
    }
    Entry entry{};
    if (!ParseRow(line, &entry)) return fail("bad hypotf corpus row or binary32 representation: " + line);
    if (!inputs.emplace(entry.x,entry.y).second) return fail("duplicate hypotf input word");
    entries->push_back(entry);
  }
  if (input.bad()) return fail("cannot read hypotf corpus");
  if (!provenance || !function || !metadata || !format) return fail("missing required hypotf corpus metadata");
  if (entries->size() != declared) return fail("hypotf corpus count disagrees with header");
  if (entries->size() < minimum) return fail("missing or truncated hypotf corpus");
  return true;
}


using Pair=std::pair<uint32_t,uint32_t>;
std::set<Pair> EssentialPairs() {
  std::set<Pair> required;
  auto add=[&](uint32_t a,uint32_t b) {
    for (uint32_t sx:{0u,kSign}) for (uint32_t sy:{0u,kSign}) {
      required.emplace(a|sx,b|sy); required.emplace(b|sy,a|sx);
    }
  };
  for (Pair pair: {Pair{0,0},Pair{0,kOne},Pair{1,1},Pair{3,4},
      Pair{0x40400000,0x40800000},Pair{0x007fffff,0x00000fff},
      Pair{0x7f6eccf8,0x7eb8807f},Pair{0x00ffffff,0x1000},
      Pair{kOne,kOne},Pair{kInf-1,1},Pair{kInf-1,kInf-1},
      Pair{0x3fffffff,0x3b800000},Pair{0x4b7fffff,0x46000000},
      Pair{0x4a9ff14a,0x4b896bb0},Pair{0x4c3eb25c,0x461c3c00}}) add(pair.first,pair.second);
  required.emplace(kInf,kNaN);required.emplace(kNaN,kInf);
  for (unsigned e=1;e<255;++e) add(e<<23,1);
  for (unsigned bit=0;bit<23;++bit) add(1u<<bit,1);
  for (uint32_t b:{0x39800000u,0x39000000u}) {
    for (int delta:{-1,0,1}) add(kOne,b+static_cast<uint32_t>(delta));
  }
  return required;
}
bool EssentialCoverage(const std::vector<Entry> & entries) {
  std::set<Pair> present;
  for (const auto & e:entries) present.emplace(e.x,e.y);
  for (Pair pair:EssentialPairs()) if (!present.count(pair)) return false;
  return true;
}
std::vector<Entry> Load() {
  const char * env=std::getenv("GMATH_HYPOTF_CORPUS_DIR");
  std::string directory=env&&*env?env:"tests/corpus";
  std::ifstream input(directory+"/hypotf.corpus");std::vector<Entry> entries;
  if (!input.is_open()) {ADD_FAILURE()<<"missing hypotf corpus: "<<directory;return entries;}
  size_t minimum=1000;const char * min=std::getenv("GMATH_HYPOTF_MIN_ENTRIES");
  if (min&&!PositiveInteger(min,&minimum)) {ADD_FAILURE()<<"GMATH_HYPOTF_MIN_ENTRIES must be a complete positive decimal integer";return entries;}
  std::string payload((std::istreambuf_iterator<char>(input)),std::istreambuf_iterator<char>()),reason;
  std::istringstream stream(payload);
  if (input.bad()||!ParseCorpus(stream,minimum,&entries,&reason)) {ADD_FAILURE()<<reason;entries.clear();}
  if (!entries.empty()&&(!env||!*env)&&payload.find("\n# seed 20261027 count 3000 fresh False entries 35910\n")==std::string::npos) {
    ADD_FAILURE()<<"incorrect committed hypotf sample metadata";entries.clear();
  }
  if (!entries.empty()&&!EssentialCoverage(entries)) {ADD_FAILURE()<<"missing essential hypotf coverage";entries.clear();}
  return entries;
}
double TrueUlp(const Entry & entry) {
  uint32_t a=entry.result;
  int exponent=static_cast<int>(a>>23)-127;
  int ue=std::max(exponent,-126)-23;
  if (exponent>-126&&(a&0x007fffffu)==0&&(entry.error&kSign)) --ue;
  return std::ldexp(1.0,ue);
}
struct Interval {double low,high;};
Interval ErrorCell(uint32_t word) {
  if ((word&~kSign)==0) {double half=std::ldexp(1.0,-150);return word&kSign?Interval{-half,0}:Interval{0,half};}
  double center=Float(word);
  return {(double(Float(word&kSign?word+1:word-1))+center)/2,
          (center+double(Float(word&kSign?word-1:word+1)))/2};
}
double UlpError(float y,const Entry & e) {
  if (e.result>=kInf||e.result==0) return Bits(y)==e.result?0:std::numeric_limits<double>::infinity();
  if ((Bits(y)&kSign)||(Bits(y)&~kSign)>=kInf) return std::numeric_limits<double>::infinity();
  double d=(double(y)-double(Float(e.result)))/TrueUlp(e);Interval cell=ErrorCell(e.error);
  return std::max(std::fabs(d-cell.low),std::fabs(d-cell.high));
}
bool WithinOneUlp(float y,const Entry & e) {
  if (e.result>=kInf||e.result==0) return Bits(y)==e.result;
  if ((Bits(y)&kSign)||(Bits(y)&~kSign)>=kInf) return false;
  double d=(double(y)-double(Float(e.result)))/TrueUlp(e);if (std::fabs(d)>2) return false;
  Interval cell=ErrorCell(e.error);return cell.low>=d-1&&cell.high<=d+1;
}
uint32_t Check(uint32_t x,uint32_t y,uint32_t expected,int mode,int seed=0) {
  float a,b;std::memcpy(&a,&x,sizeof a);std::memcpy(&b,&y,sizeof b);
  EXPECT_EQ(std::fesetround(mode),0);EXPECT_EQ(std::feclearexcept(FE_ALL_EXCEPT),0);
  EXPECT_EQ(std::feraiseexcept(seed),0);int incoming=std::fetestexcept(FE_ALL_EXCEPT);
  errno=713;float (*volatile fn)(float,float)=gmath_hypotf;volatile float r=fn(a,b);
  int error=errno,flags=std::fetestexcept(FE_ALL_EXCEPT),rounding=std::fegetround();
  uint32_t bits=Bits(r);
  EXPECT_EQ(bits,expected)<<std::hex<<x<<","<<y;
  EXPECT_EQ(flags,RequiredFlags(x,y,expected)|incoming)<<std::hex<<x<<","<<y;
  EXPECT_EQ(error,713);EXPECT_EQ(rounding,mode);
  return bits;
}
std::string Fixture(const std::string & rows,const std::string & count="1") {
  return "# Pinned oracle: tools/oracle/gen_corpus_hypotf.py; MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1\n# function hypotf\n# seed 20261027 count 0 fresh False entries "+count+
      "\n# binary32 x/y/results widened exactly to binary64; signed binary32 error in true binary32 ULP\n"+rows;
}
} // namespace

TEST(Hypotf, CorpusIsCorrectlyRoundedInEveryMode) {
  Environment saved;auto entries=Load();ASSERT_FALSE(entries.empty());
  double worst=0;uint32_t wx=0,wy=0;
  for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}) {
    for (const auto & e:entries) {
      uint32_t result=Check(e.x,e.y,e.result,mode);
      if (mode==FE_TONEAREST) {
        double error=UlpError(Float(result),e);
        if (error>worst) {worst=error;wx=e.x;wy=e.y;}
        EXPECT_TRUE(WithinOneUlp(Float(result),e));
      }
    }
  }
  ASSERT_EQ(std::fesetround(FE_TONEAREST),0);
  std::printf("  hypotf: %zu corpus entries, max error %.8f ULP (input bits %08x,%08x)\n",entries.size(),worst,wx,wy);
  EXPECT_LE(worst,0.51);
}
TEST(Hypotf, ExactSpecialsAndState) {
  Environment saved;
  const uint32_t words[]={0,kSign,1,kSign|1,0x007fffff,0x00800000,kOne,kOne|kSign,
      kInf-1,kInf,kInf|kSign,kNaN,kNaN|7,kNaN|kSign|7,kInf|1,kInf|kSign|1};
  for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO})
    for (int seed:{0,FE_INVALID,FE_DIVBYZERO,FE_OVERFLOW,FE_UNDERFLOW,FE_INEXACT,FE_ALL_EXCEPT})
      for (uint32_t x:words) for (uint32_t y:words) {
        uint32_t expected;if (SpecialResult(x,y,&expected)) Check(x,y,expected,mode,seed);
      }
}
TEST(Hypotf, ExactTriplesTinyCarryAndOverflowTie) {
  Environment saved;
  const Entry cases[]={{3,4,5,0},{0x40400000,0x40800000,0x40a00000,0},
      {1,1,1,0x3ed413cd},{0x007fffff,0x00000fff,0x00800000,0xb9fff000},
      {0x7f6eccf8,0x7eb8807f,kInf,0},{0x00ffffff,0x1000,0x01000000,0xbeffffff},
      {0x4c3eb25c,0x461c3c00,0x4c3eb25c,0x3e800000},
      {0x7e0420f5,0x7f7ddc25,0x7f7fffff,0x3e800000}};
  for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO})
    for (int seed:{0,FE_INVALID,FE_DIVBYZERO,FE_OVERFLOW,FE_UNDERFLOW,FE_INEXACT,FE_ALL_EXCEPT})
      for (const auto & e:cases) for (uint32_t sx:{0u,kSign}) for (uint32_t sy:{0u,kSign}) {
        Check(e.x|sx,e.y|sy,e.result,mode,seed);Check(e.y|sy,e.x|sx,e.result,mode,seed);
      }
}
TEST(Hypotf, PairParserMetadataAndExactMidpointCertificates) {
  std::string row="4008000000000000 4010000000000000 4014000000000000 00000000\n";
  std::vector<Entry> entries;std::string reason;
  auto parse=[&](const std::string & text,size_t minimum=1) {std::istringstream in(text);return ParseCorpus(in,minimum,&entries,&reason);};
  EXPECT_TRUE(parse(Fixture(row)))<<reason;
  EXPECT_FALSE(parse(Fixture(row),2));EXPECT_FALSE(parse(Fixture(row,"2")));
  EXPECT_FALSE(parse(Fixture(row+row,"2")));
  EXPECT_TRUE(parse(Fixture(row+"4010000000000000 4008000000000000 4014000000000000 00000000\n","2")))<<reason;
  EXPECT_FALSE(parse(Fixture("4008000000000000 4010000000000000 00000000\n")));
  EXPECT_FALSE(parse(Fixture("4008000000000000 401000000000000 4014000000000000 00000000\n")));
  EXPECT_FALSE(parse(Fixture("4008000000000000 4010000000000000 c014000000000000 00000000\n")));
  EXPECT_FALSE(parse(Fixture("4008000000000000 4010000000000000 4014000000000000 7fc00000\n")));
  EXPECT_FALSE(parse(Fixture("4008000000000001 4010000000000000 4014000000000000 00000000\n")));
  EXPECT_FALSE(parse(Fixture("4008000000000000 4010000000000001 4014000000000000 00000000\n")));
  EXPECT_FALSE(parse(Fixture("4008000000000000 4010000000000000 4014000020000000 00000000\n")));
  EXPECT_FALSE(parse(Fixture("4008000000000000 4010000000000000 4014000000000000 3e800000\n")));
  EXPECT_FALSE(parse(Fixture(row.substr(0,row.size()-1)+" extra\n")));
  const std::string valid=Fixture(row);
  for (const auto & change:std::vector<std::pair<std::string,std::string>>{
      {"MPFR 4.2.2","MPFR 4.2.1"},{"mpmath 1.4.1","mpmath 1.4.1 mpmath 1.4.1"},
      {"# function hypotf","# function hypot"},{"fresh False","fresh maybe"},
      {"entries 1","entries 1junk"},{"seed 20261027","seed 1junk"}}) {
    std::string bad=valid;bad.replace(bad.find(change.first),change.first.size(),change.second);
    EXPECT_FALSE(parse(bad))<<change.first;
  }
  for (const std::string & header:{std::string("# Pinned oracle:"),std::string("# function"),std::string("# seed"),std::string("# binary32")}) {
    std::string bad=valid;size_t begin=bad.find(header),end=bad.find('\n',begin);bad.erase(begin,end-begin+1);EXPECT_FALSE(parse(bad));
  }
  EXPECT_FALSE(parse(valid+valid.substr(0,valid.find('\n')+1)));
  EXPECT_TRUE(parse(Fixture("3ff0000000000000 3ff0000000000000 3ff6a09e60000000 3e4fe77a\n")))<<reason;
  EXPECT_FALSE(parse(Fixture("3ff0000000000000 3ff0000000000000 3ff6a09e60000000 be4fe77a\n")));
}
TEST(Hypotf, CompleteErrorCellsAndCountParsers) {
  Environment saved;ASSERT_EQ(std::fesetround(FE_TONEAREST),0);
  EXPECT_FALSE(WithinOneUlp(Float(0x3f800002),{kOne,kOne,0x3f800001,kSign}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f800000),{kOne,kOne,0x3f800001,kSign}));
  EXPECT_FALSE(WithinOneUlp(Float(0x3f7fffff),{kOne,kOne,kOne,0x3f000000}));
  EXPECT_TRUE(WithinOneUlp(Float(0x3f7fffff),{kOne,kOne,kOne,0x3effffff}));
  EXPECT_DOUBLE_EQ(ErrorCell(0).high,std::ldexp(1.0,-150));
  EXPECT_DOUBLE_EQ(ErrorCell(kSign).low,-std::ldexp(1.0,-150));
  EXPECT_EQ(RequiredFlags(3,4,5),0);EXPECT_EQ(RequiredFlags(1,1,1),FE_UNDERFLOW|FE_INEXACT);
  EXPECT_EQ(RequiredFlags(0x007fffff,0xfff,0x00800000),FE_INEXACT);
  size_t count=0;EXPECT_TRUE(PositiveInteger("1",&count));
  for (const char * bad:{"","0","-1","+1","1junk"," 1","1 "}) EXPECT_FALSE(PositiveInteger(bad,&count));
  EXPECT_FALSE(PositiveInteger(std::to_string(std::numeric_limits<size_t>::max())+"0",&count));
}
TEST(Hypotf, EssentialPairsRejectMissingFamilies) {
  std::vector<Entry> entries;for (Pair p:EssentialPairs()) entries.push_back({p.first,p.second,0,0});
  EXPECT_TRUE(EssentialCoverage(entries));
  for (Pair missing:{Pair{3,4},Pair{0x007fffff,0xfff},Pair{0x7f6eccf8,0x7eb8807f},Pair{kOne,0x39000000},Pair{1,1}}) {
    auto subset=entries;subset.erase(std::remove_if(subset.begin(),subset.end(),[&](const Entry & e){return Pair{e.x,e.y}==missing;}),subset.end());
    EXPECT_FALSE(EssentialCoverage(subset));
  }
}
TEST(Hypotf, AllModeSymmetryAndFiniteClassProperties) {
  Environment saved;uint32_t state=0x49c0192du;
  for (unsigned i=0;i<10000;++i) {
    state^=state<<13;state^=state>>17;state^=state<<5;uint32_t x=state&~kSign;
    state^=state<<13;state^=state>>17;state^=state<<5;uint32_t y=state&~kSign;
    if (x>=kInf||y>=kInf) continue;
    ASSERT_EQ(std::fesetround(FE_TONEAREST),0);float a=Float(x),b=Float(y);uint32_t baseline=Bits(gmath_hypotf(a,b));
    EXPECT_GE(baseline,std::max(x,y));EXPECT_LE(baseline,kInf);
    for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}) {
      Check(x,y,baseline,mode,FE_DIVBYZERO);Check(y|kSign,x|kSign,baseline,mode,FE_DIVBYZERO);
    }
  }
}
int main(int argc,char ** argv) {::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
