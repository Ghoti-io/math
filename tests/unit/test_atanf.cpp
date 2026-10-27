/**
 * @file Binary32 unary arctangent references, raw specials and state contracts.
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
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr uint32_t Sign=0x80000000u, Inf=0x7f800000u, NaN=0x7fc00000u;
float Value(uint32_t raw) {float value;std::memcpy(&value,&raw,4);return value;}
uint32_t Bits(float value) {uint32_t raw;std::memcpy(&raw,&value,4);return raw;}
struct Environment {
  fenv_t saved;int error;
  Environment():error(errno) {std::fegetenv(&saved);}
  ~Environment() {std::fesetenv(&saved);errno=error;}
};
struct Entry {uint32_t input,result,error;};
uint64_t Hex(const std::string & text,size_t width) {
  uint64_t result=0;auto p=std::from_chars(text.data(),text.data()+text.size(),result,16);
  if (text.size()!=width||p.ec!=std::errc{}||p.ptr!=text.data()+text.size())
    throw std::runtime_error("bad fixed-width hex word");
  return result;
}
uint32_t Narrow(uint64_t raw) {
  // Reject malformed or signaling NaNs before floating conversion.
  uint64_t magnitude=raw&0x7fffffffffffffffull;
  if (magnitude>0x7ff0000000000000ull) {
    if (!(raw&0x0008000000000000ull)||(raw&0x1fffffffull))
      throw std::runtime_error("bad widened quiet NaN");
    return static_cast<uint32_t>(raw>>32)&Sign ? Sign|Inf|static_cast<uint32_t>((raw>>29)&0x7fffffu) : Inf|static_cast<uint32_t>((raw>>29)&0x7fffffu);
  }
  double value;std::memcpy(&value,&raw,8);float f=static_cast<float>(value);
  double back=f;uint64_t check;std::memcpy(&check,&back,8);
  if (check!=raw) throw std::runtime_error("not exactly widened binary32");
  return Bits(f);
}
uint64_t Decimal(const std::string & text) {
  uint64_t value=0;auto parsed=std::from_chars(text.data(),text.data()+text.size(),value);
  if (text.empty()||parsed.ec!=std::errc{}||parsed.ptr!=text.data()+text.size())
    throw std::runtime_error("bad decimal metadata");
  return value;
}
std::vector<Entry> Parse(std::istream & stream) {
  std::string line;
  if (!std::getline(stream,line)||line!="# Pinned oracle: tools/oracle/gen_corpus_atanf.py; MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1")
    throw std::runtime_error("incorrect oracle provenance");
  if (!std::getline(stream,line)||line!="# function atanf") throw std::runtime_error("wrong function");
  if (!std::getline(stream,line)) throw std::runtime_error("missing sample metadata");
  std::istringstream meta(line);std::string hash,seedlabel,countlabel,freshlabel,entrieslabel,fresh,extra;
  std::string seed,count,entrytext;
  if (!(meta>>hash>>seedlabel>>seed>>countlabel>>count>>freshlabel>>fresh>>entrieslabel>>entrytext)||meta>>extra||
      hash!="#"||seedlabel!="seed"||countlabel!="count"||freshlabel!="fresh"||entrieslabel!="entries"||
      (fresh!="True"&&fresh!="False"))
    throw std::runtime_error("bad sample metadata");
  (void)Decimal(seed);if (Decimal(count)>10000000) throw std::runtime_error("sample count too large");
  uint64_t entries=Decimal(entrytext);
  if (!entries||entries>10000000) throw std::runtime_error("bad entries count");
  if (!std::getline(stream,line)||line!="# binary32 input/result widened exactly to binary64; signed binary32 error in true binary32 ULP")
    throw std::runtime_error("wrong format");
  std::vector<Entry> result;std::set<uint32_t> seen;
  while (std::getline(stream,line)) {
    std::istringstream row(line);std::string a,b,c;
    if (!(row>>a>>b>>c)||row>>extra) throw std::runtime_error("bad row");
    Entry e{Narrow(Hex(a,16)),Narrow(Hex(b,16)),static_cast<uint32_t>(Hex(c,8))};
    uint32_t magnitude=e.input&~Sign, target=e.result&~Sign;
    if (!seen.insert(e.input).second) throw std::runtime_error("duplicate input");
    if ((e.error&~Sign)>0x3f000000u) throw std::runtime_error("invalid error certificate");
    if (magnitude>Inf) {
      if (e.result!=NaN||e.error!=0) throw std::runtime_error("bad NaN reference");
    } else if (!magnitude) {
      if (e.result!=e.input||e.error!=0) throw std::runtime_error("bad zero reference");
    } else if (!target||target>0x3fc90fdbu||((e.input^e.result)&Sign)) {
      throw std::runtime_error("bad finite angle reference");
    }
    result.push_back(e);
  }
  if (stream.bad()||result.size()!=entries) throw std::runtime_error("entry count mismatch");
  return result;
}
std::vector<Entry> Load() {
  const char * directory=std::getenv("GMATH_ATANF_CORPUS_DIR");
  std::string path=directory&&*directory?directory:"tests/corpus";
  std::ifstream stream(path+"/atanf.corpus");
  if (!stream) throw std::runtime_error("missing atanf corpus: "+path);
  auto rows=Parse(stream);
  if (rows.size()<2000) throw std::runtime_error("insufficient sample");
  std::printf("  atanf: %zu reference entries from %s\n",rows.size(),path.c_str());
  return rows;
}
uint32_t Check(uint32_t input,int mode,int incoming) {
  EXPECT_EQ(std::fesetround(mode),0);EXPECT_EQ(std::feclearexcept(FE_ALL_EXCEPT),0);
  EXPECT_EQ(std::feraiseexcept(incoming),0);int seeded=std::fetestexcept(FE_ALL_EXCEPT);errno=719;
  float x=Value(input);float (*volatile function)(float)=gmath_atanf;volatile float result=function(x);
  int error=errno,flags=std::fetestexcept(FE_ALL_EXCEPT),rounding=std::fegetround();
  uint32_t output=Bits(result),a=input&~Sign;int added=0;
  if (a>Inf) {
    EXPECT_EQ(output,NaN);if (!(a&0x00400000u)) added=FE_INVALID;
  } else if (!a) {EXPECT_EQ(output,input);}
  else {
    added=FE_INEXACT;if (a<0x00800000u) added|=FE_UNDERFLOW;
    EXPECT_EQ(output&Sign,input&Sign);EXPECT_LE(output&~Sign,0x3fc90fdbu);
    if (a<0x30800000u) {EXPECT_EQ(output,input);}
    if (a==Inf) {EXPECT_EQ(output,0x3fc90fdbu|(input&Sign));}
  }
  EXPECT_EQ(flags,seeded|added)<<std::hex<<input;EXPECT_EQ(error,719);EXPECT_EQ(rounding,mode);
  return output;
}
double Error(uint32_t output,const Entry & e) {
  if ((e.input&~Sign)>Inf||!(e.input&~Sign)) return output==e.result?0:INFINITY;
  if ((output&~Sign)>=Inf) return INFINITY;
  uint32_t a=e.result&~Sign;int exponent=static_cast<int>(a>>23)-127;
  int unit=std::max(exponent,-126)-23;
  if (exponent>-126&&!(a&0x7fffffu)&&((e.error^e.result)&Sign)) --unit;
  double d=(double(Value(output))-double(Value(e.result)))/std::ldexp(1.0,unit);
  double center=Value(e.error),low,high;
  if (!(e.error&~Sign)) {low=e.error&Sign?-std::ldexp(1.0,-150):0;high=e.error&Sign?0:std::ldexp(1.0,-150);}
  else {low=(double(Value(e.error&Sign?e.error+1:e.error-1))+center)/2;
    high=(center+double(Value(e.error&Sign?e.error-1:e.error+1)))/2;}
  return std::max(std::fabs(d-low),std::fabs(d-high));
}
} // namespace

TEST(Atanf, PinnedAccuracyAndAllModeState) {
  Environment saved;std::vector<Entry> rows;ASSERT_NO_THROW(rows=Load());double worst=0;
  for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}) for (const auto & e:rows) {
    uint32_t output=Check(e.input,mode,0);
    if (mode==FE_TONEAREST) {double error=Error(output,e);worst=std::max(worst,error);EXPECT_LE(error,1.0)<<std::hex<<e.input;}
  }
  std::printf("  atanf: maximum closed-cell error %.8f ULP\n",worst);EXPECT_LE(worst,0.51);
}
TEST(Atanf, RawSpecialsAndIncomingState) {
  Environment saved;
  for (uint32_t a:{0u,1u,3u,0x007fffffu,0x00800000u,0x307fffffu,0x30800000u,0x3e000000u,
                  0x3f800000u,0x7f7fffffu,Inf,0x7fc00000u,0x7fc12345u,0x7f800001u,0x7fbfffffu})
    for (uint32_t sign:{0u,Sign}) for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO})
      for (int seed:{0,FE_INVALID,FE_DIVBYZERO,FE_OVERFLOW,FE_UNDERFLOW,FE_INEXACT,FE_ALL_EXCEPT})
        (void)Check(a|sign,mode,seed);
}
TEST(Atanf, TinyInputBitsIncludingMinimumNormal) {
  Environment saved;
  for (uint32_t a=1;a<0x30800000u;a+=7919u) for (uint32_t sign:{0u,Sign})
    for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}) (void)Check(a|sign,mode,0);
}
TEST(Atanf, ParserRejectsBrokenPayloads) {
  const std::string header="# Pinned oracle: tools/oracle/gen_corpus_atanf.py; MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1\n# function atanf\n# seed 20261027 count 0 fresh False entries 1\n# binary32 input/result widened exactly to binary64; signed binary32 error in true binary32 ULP\n";
  for (const std::string row:{"0000000000000000 0000000000000000 00000000\n", "3ff0000000000000 3fe921fb60000000 bebbbd2e\n"}) {
    std::istringstream good(header+row);EXPECT_NO_THROW(Parse(good));
    for (const std::string & broken:{header+row+row,header+row+"extra\n",header+row.substr(1),header}) {
      std::istringstream bad(broken);EXPECT_THROW(Parse(bad),std::runtime_error);
    }
  }
  for (const std::string row:{"0000000000000000 8000000000000000 00000000\n",
      "3ff0000000000001 3fe921fb60000000 00000000\n", "7ff0000000000001 7ff8000000000000 00000000\n",
      "3ff0000000000000 7ff0000000000000 00000000\n", "3ff0000000000000 3fe921fb60000000 7f800000\n"}) {
    std::istringstream bad(header+row);EXPECT_THROW(Parse(bad),std::runtime_error);
  }
}
TEST(Atanf, OldPathBitAndStateCompatibility) {
  Environment saved;
  struct Result {uint32_t bits;int flags,error,mode;};
  auto call=[](uint32_t word,int mode,int seed,bool previous) {
    float input=Value(word);EXPECT_EQ(std::fesetround(mode),0);EXPECT_EQ(std::feclearexcept(FE_ALL_EXCEPT),0);
    EXPECT_EQ(std::feraiseexcept(seed),0);errno=733;float output;
    if (previous) {float (*volatile fn)(float,float)=gmath_atan2f;output=fn(input,1.0f);}
    else {float (*volatile fn)(float)=gmath_atanf;output=fn(input);}
    int error=errno,flags=std::fetestexcept(FE_ALL_EXCEPT),rounding=std::fegetround();
    return Result{Bits(output),flags,error,rounding};
  };
  std::vector<Entry> entries;ASSERT_NO_THROW(entries=Load());std::vector<uint32_t> words;
  for (const auto & e:entries) words.push_back(e.input);
  uint32_t random=0x6174616eu;
  for (unsigned i=0;i<32768;++i) {random^=random<<13;random^=random>>17;random^=random<<5;words.push_back(random);}
  for (uint32_t word:words) for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO})
    for (int seed:{0,FE_INVALID,FE_DIVBYZERO,FE_OVERFLOW,FE_UNDERFLOW,FE_INEXACT,FE_ALL_EXCEPT}) {
      auto a=call(word,mode,seed,false),b=call(word,mode,seed,true);
      EXPECT_EQ(a.bits,b.bits)<<std::hex<<word;EXPECT_EQ(a.flags,b.flags)<<std::hex<<word;
      EXPECT_EQ(a.error,b.error);EXPECT_EQ(a.mode,b.mode);
    }
}
int main(int argc,char ** argv) {::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
