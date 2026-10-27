/**
 * @file Exact integer-return rounding, width-aware references and state.
 * Copyright 2026 by Corey Pennycuff
 */
#include "test_helpers.h"
#include <ghoti.io/math/basic.h>
#include <array>
#include <cerrno>
#include <cfenv>
#include <charconv>
#include <climits>
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
struct Environment {
  fenv_t saved;int error;
  Environment():error(errno) {std::fegetenv(&saved);}
  ~Environment() {std::fesetenv(&saved);errno=error;}
};
struct Entry {uint64_t input;int64_t result32,result64;int invalid32,invalid64;};
uint64_t Hex(const std::string & text,size_t length) {
  uint64_t value=0;auto r=std::from_chars(text.data(),text.data()+text.size(),value,16);
  if (text.size()!=length||r.ec!=std::errc{}||r.ptr!=text.data()+text.size()) throw std::runtime_error("invalid hex word");
  return value;
}
uint64_t Decimal(const std::string & text) {
  uint64_t value=0;auto r=std::from_chars(text.data(),text.data()+text.size(),value);
  if (text.empty()||r.ec!=std::errc{}||r.ptr!=text.data()+text.size()) throw std::runtime_error("invalid decimal metadata");
  return value;
}
int64_t Signed(uint64_t word) {int64_t value;std::memcpy(&value,&word,8);return value;}
std::vector<Entry> Parse(std::istream & input,unsigned width) {
  std::string line,extra;
  if (!std::getline(input,line)||line!="# Pinned oracle: tools/oracle/gen_corpus_intround.py; MPFR 4.2.2 gmpy2 2.3.2") throw std::runtime_error("wrong provenance");
  if (!std::getline(input,line)||line!="# function intround"+std::to_string(width)) throw std::runtime_error("wrong function");
  if (!std::getline(input,line)) throw std::runtime_error("missing metadata");
  std::istringstream metadata(line);std::array<std::string,9> fields;
  for (auto & field:fields) if (!(metadata>>field)) throw std::runtime_error("missing metadata field");
  if (metadata>>extra||fields[0]!="#"||fields[1]!="seed"||fields[3]!="count"||fields[5]!="fresh"||fields[7]!="entries"||
      (fields[6]!="True"&&fields[6]!="False")) throw std::runtime_error("bad metadata labels");
  (void)Decimal(fields[2]);if (Decimal(fields[4])>10000000) throw std::runtime_error("excessive requested count");
  uint64_t count=Decimal(fields[8]);if (!count||count>20000000) throw std::runtime_error("bad row count");
  if (!std::getline(input,line)||line!="# raw input; signed32 result invalid; signed64 result invalid") throw std::runtime_error("wrong format");
  std::vector<Entry> rows;std::set<uint64_t> seen;
  while (std::getline(input,line)) {
    std::istringstream stream(line);std::string raw,r32,b32,r64,b64;
    if (!(stream>>raw>>r32>>b32>>r64>>b64)||stream>>extra||(b32!="0"&&b32!="1")||(b64!="0"&&b64!="1")) throw std::runtime_error("bad row");
    Entry e{Hex(raw,width/4),Signed(Hex(r32,16)),Signed(Hex(r64,16)),b32=="1",b64=="1"};
    if (!seen.insert(e.input).second||e.result32<INT32_MIN||e.result32>INT32_MAX) throw std::runtime_error("duplicate/out-of-range row");
    if ((e.invalid32&&e.result32!=INT32_MIN)||(e.invalid64&&e.result64!=INT64_MIN)||(!e.invalid32&&(e.invalid64||e.result64!=e.result32))) throw std::runtime_error("inconsistent width results");
    unsigned mantissa=width==64?52:23,exponent=width==64?11:8;
    uint64_t magnitude=e.input&((UINT64_C(1)<<(width-1))-1);
    if ((magnitude>>mantissa)==((UINT64_C(1)<<exponent)-1)&&(!e.invalid32||!e.invalid64)) throw std::runtime_error("nonfinite must be invalid");
    rows.push_back(e);
  }
  if (input.bad()||rows.size()!=count) throw std::runtime_error("count mismatch");
  return rows;
}
std::vector<Entry> Load(unsigned width) {
  const char * override_directory=std::getenv("GMATH_INTROUND_CORPUS_DIR");
  std::string directory=override_directory&&*override_directory?override_directory:"tests/corpus";
  std::ifstream input(directory+"/intround"+std::to_string(width)+".corpus");
  if (!input) throw std::runtime_error("missing integer-rounding corpus: "+directory);
  auto rows=Parse(input,width);if (rows.size()<4000) throw std::runtime_error("insufficient reference sample");
  std::printf("  intround%u: %zu reference entries from %s\n",width,rows.size(),directory.c_str());return rows;
}
void Check(const Entry & e,unsigned width,int mode,int seed,bool wide) {
  double d=0;float f=0;
  if (width==64) std::memcpy(&d,&e.input,8);
  else {uint32_t raw=static_cast<uint32_t>(e.input);std::memcpy(&f,&raw,4);}
  EXPECT_EQ(std::fesetround(mode),0);EXPECT_EQ(std::feclearexcept(FE_ALL_EXCEPT),0);EXPECT_EQ(std::feraiseexcept(seed),0);
  int incoming=std::fetestexcept(FE_ALL_EXCEPT);errno=727;
  int64_t result;
  if (wide) {
    if (width==64) {long long (*volatile fn)(double)=gmath_llround;result=fn(d);}
    else {long long (*volatile fn)(float)=gmath_llroundf;result=fn(f);}
  } else {
    if (width==64) {long (*volatile fn)(double)=gmath_lround;result=fn(d);}
    else {long (*volatile fn)(float)=gmath_lroundf;result=fn(f);}
  }
  int error=errno,flags=std::fetestexcept(FE_ALL_EXCEPT),rounding=std::fegetround();
  bool use64=wide||LONG_MAX==INT64_MAX;int invalid=use64?e.invalid64:e.invalid32;
  EXPECT_EQ(result,use64?e.result64:e.result32)<<std::hex<<e.input;
  EXPECT_EQ(flags,incoming|(invalid?FE_INVALID:0))<<std::hex<<e.input;
  EXPECT_EQ(error,727);EXPECT_EQ(rounding,mode);
}
std::string Fixture(const std::string & row,const std::string & count="1") {
  return "# Pinned oracle: tools/oracle/gen_corpus_intround.py; MPFR 4.2.2 gmpy2 2.3.2\n# function intround64\n# seed 1 count 0 fresh False entries "+count+"\n# raw input; signed32 result invalid; signed64 result invalid\n"+row;
}
} // namespace

TEST(IntegerRound, ExactReferencesAndAllModeState) {
  Environment saved;
  for (unsigned width:{32u,64u}) {
    std::vector<Entry> rows;ASSERT_NO_THROW(rows=Load(width));
    for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}) for (const auto & e:rows)
      for (bool wide:{false,true}) Check(e,width,mode,0,wide);
  }
}
TEST(IntegerRound, IncomingFlagsAndRawSpecials) {
  Environment saved;
  const Entry cases[]={
    {0,0,0,0,0},{0x8000000000000000ull,0,0,0,0},
    {0x3fdfffffffffffffull,0,0,0,0},{0x3fe0000000000000ull,1,1,0,0},
    {0xbfe0000000000000ull,-1,-1,0,0},{0x3fe0000000000001ull,1,1,0,0},
    {0x41dfffffffe00000ull,INT32_MIN,2147483648ll,1,0},
    {0xc1e00000000fffffull,INT32_MIN,INT32_MIN,0,0},
    {0xc1e0000000100000ull,INT32_MIN,-2147483649ll,1,0},
    {0x43dfffffffffffffull,INT32_MIN,9223372036854774784ll,1,0},
    {0x43e0000000000000ull,INT32_MIN,INT64_MIN,1,1},
    {0xc3e0000000000000ull,INT32_MIN,INT64_MIN,1,0},
    {0xc3e0000000000001ull,INT32_MIN,INT64_MIN,1,1},
    {0x7ff0000000000000ull,INT32_MIN,INT64_MIN,1,1},
    {0x7ff0000000000001ull,INT32_MIN,INT64_MIN,1,1},
    {0x7ff8000000000000ull,INT32_MIN,INT64_MIN,1,1},
    {0xfff8000000000007ull,INT32_MIN,INT64_MIN,1,1}};
  for (const auto & e:cases) for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO})
    for (int seed:{0,FE_INVALID,FE_DIVBYZERO,FE_OVERFLOW,FE_UNDERFLOW,FE_INEXACT,FE_ALL_EXCEPT})
      for (bool wide:{false,true}) Check(e,64,mode,seed,wide);
  const Entry floats[]={{1,0,0,0,0},{0x80000001,0,0,0,0},{0x3f000000,1,1,0,0},
    {0xbf000000,-1,-1,0,0},{0x4f000000,INT32_MIN,2147483648ll,1,0},
    {0xcf000000,INT32_MIN,INT32_MIN,0,0},{0x5f000000,INT32_MIN,INT64_MIN,1,1},
    {0xdf000000,INT32_MIN,INT64_MIN,1,0},{0x7f800001,INT32_MIN,INT64_MIN,1,1},
    {0xffc00007,INT32_MIN,INT64_MIN,1,1}};
  for (const auto & e:floats) for (int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO})
    for (int seed:{0,FE_INVALID,FE_DIVBYZERO,FE_OVERFLOW,FE_UNDERFLOW,FE_INEXACT,FE_ALL_EXCEPT})
      for (bool wide:{false,true}) Check(e,32,mode,seed,wide);
}
TEST(IntegerRound, ParserRejectsBrokenReferences) {
  const std::string row="3fe0000000000000 0000000000000001 0 0000000000000001 0\n";
  std::istringstream good(Fixture(row));EXPECT_NO_THROW(Parse(good,64));
  for (const auto & payload:{Fixture(row+row),Fixture(row,"2"),Fixture(row.substr(1)),Fixture(row+"extra\n"),Fixture(""),Fixture(row,"-1")}) {
    std::istringstream bad(payload);EXPECT_THROW(Parse(bad,64),std::runtime_error);
  }
  for (const std::string broken:{"7ff0000000000000 0000000000000000 0 0000000000000000 0\n",
    "3fe0000000000000 0000000080000000 0 0000000000000001 0\n",
    "3fe0000000000000 ffffffff80000000 1 0000000000000001 1\n",
    "3fe0000000000000 0000000000000001 2 0000000000000001 0\n"}) {
    std::istringstream bad(Fixture(broken));EXPECT_THROW(Parse(bad,64),std::runtime_error);
  }
}
TEST(IntegerRound, Binary32ParserRejectsBrokenReferences) {
  const std::string row="3f000000 0000000000000001 0 0000000000000001 0\n";
  auto fixture=[](const std::string & text) {
    std::string result=Fixture(text);result.replace(result.find("intround64"),10,"intround32");return result;
  };
  std::istringstream good(fixture(row));EXPECT_NO_THROW(Parse(good,32));
  for (const std::string broken:{"000000003f000000 0000000000000001 0 0000000000000001 0\n",
    "7f800000 0000000000000000 0 0000000000000000 0\n",
    "7f800001 ffffffff80000000 1 0000000000000000 0\n",
    "3f00000 0000000000000001 0 0000000000000001 0\n"}) {
    std::istringstream bad(fixture(broken));EXPECT_THROW(Parse(bad,32),std::runtime_error);
  }
  std::string wrong=fixture(row);wrong.replace(wrong.find("MPFR 4.2.2"),10,"MPFR 0.0.0");
  std::istringstream bad_provenance(wrong);EXPECT_THROW(Parse(bad_provenance,32),std::runtime_error);
  std::istringstream bad_function(Fixture(row));EXPECT_THROW(Parse(bad_function,32),std::runtime_error);
}
int main(int argc,char ** argv) {::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
