/** @file Exact IEEE remainder/quotient contracts. Copyright 2026 Corey Pennycuff */
#include "test_helpers.h"
#include "../ieee_remainder_probe.h"
#include <cstdlib>
#include <gtest/gtest-spi.h>
#include <filesystem>
#include <fstream>
#include <string>
struct IrEnvironment {
 fenv_t saved;int error;bool good;
 IrEnvironment():error(errno),good(fegetenv(&saved)==0){}
 ~IrEnvironment(){if(good)(void)fesetenv(&saved);errno=error;}
};
static void ir_fatal_under_guard(){IrEnvironment guard;ASSERT_TRUE(guard.good);ASSERT_EQ(fesetround(FE_DOWNWARD),0);ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT),0);ASSERT_EQ(feraiseexcept(FE_INVALID),0);errno=19;FAIL()<<"deliberate guarded assertion";}
static const char *ir_directory(){const char *s=std::getenv("GMATH_IEEE_REMAINDER_CORPUS_DIR");return s&&*s?s:"tests/corpus";}
static void pinned(unsigned width){IrEnvironment guard;ASSERT_TRUE(guard.good);ir_result r={0,0,0,0,0};ASSERT_EQ(ir_run(ir_directory(),width,1,&r),0);const char *env=std::getenv("GMATH_IEEE_REMAINDER_CORPUS_DIR");if(!env||!*env){EXPECT_TRUE(ir_pinned(r,width));}}
TEST(IeeeRemainder,PinnedDoubleCorpusAndCallerState){pinned(64);}
TEST(IeeeRemainder,PinnedFloatCorpusAndCallerState){pinned(32);}
TEST(IeeeRemainder,NearestEvenAndSevenQuotientBits){
 IrEnvironment guard;ASSERT_TRUE(guard.good);
 for(int n:{0,1,2,3,126,127,128,129,254,255,256})for(int sx:{-1,1})for(int sy:{-1,1}){
  double x=sx*(n+0.5),y=sy;uint64_t xb,yb,rb;int nearest=n+(n&1);double r=sx*((n&1)?-0.5:0.5);
  memcpy(&xb,&x,8);memcpy(&yb,&y,8);memcpy(&rb,&r,8);ir_row row={xb,yb,rb,sx*sy*(nearest&127),0};
  for(int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}){uint64_t out=0;int q=0;EXPECT_TRUE(ir_call(row,64,mode,3,733,1,&out,&q));}
 }
 EXPECT_EQ(fesetenv(&guard.saved),0);
}
TEST(IeeeRemainder,EarlyZeroAppendsQuotientBits){
 IrEnvironment guard;ASSERT_TRUE(guard.good);
 for(int gap=0;gap<=1023;gap++){
  uint64_t x=static_cast<uint64_t>(gap+1023)<<52;ir_row row={x,UINT64_C(0x3ff0000000000000),0,gap>=7?0:1<<gap,0};
  uint64_t r=0;int q=0;EXPECT_TRUE(ir_call(row,64,FE_DOWNWARD,0,0,1,&r,&q));
 }
 EXPECT_EQ(fesetenv(&guard.saved),0);
}
TEST(IeeeRemainder,MinimumSubnormalHalves){
 IrEnvironment guard;ASSERT_TRUE(guard.good);
 for(unsigned width:{32u,64u})for(uint64_t sign:{UINT64_C(0),UINT64_C(1)<<(width-1)}){
  ir_row rows[4]={{sign|1,2,sign|1,0,0},{sign|3,2,(sign^(UINT64_C(1)<<(width-1)))|1,sign?-2:2,0},{sign|5,2,sign|1,sign?-2:2,0},{sign|7,2,(sign^(UINT64_C(1)<<(width-1)))|1,sign?-4:4,0}};
  for(auto row:rows)for(int mode:{FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO})for(int kind:{0,1,2}){uint64_t r=0;int q=0;EXPECT_TRUE(ir_call(row,width,mode,24,733,kind,&r,&q));}
 }
 EXPECT_EQ(fesetenv(&guard.saved),0);
}
TEST(IeeeRemainder,NaNPrecedenceAndZeroQuotient){
 IrEnvironment guard;ASSERT_TRUE(guard.good);
 const uint64_t inf=UINT64_C(0x7ff0000000000000),nan=UINT64_C(0x7ff8000000000000);
 ir_row rows[]={{nan|3,0,nan,0,0},{inf,nan|9,nan,0,0},{nan|3,inf|1,nan,0,1},{inf|1,nan|3,nan,0,1},{inf,0,nan,0,1},{UINT64_C(0x8000000000000000),inf,UINT64_C(0x8000000000000000),0,0}};
 for(auto row:rows)for(int kind:{0,1,2}){uint64_t r=0;int q=0;EXPECT_TRUE(ir_call(row,64,FE_UPWARD,3,0,kind,&r,&q));}
 EXPECT_EQ(fesetenv(&guard.saved),0);
}
TEST(IeeeRemainder,MalformedTailRestoresCallerState){
 namespace fs=std::filesystem;int marker=0;auto dir=fs::temp_directory_path()/("gmath-ieeeremainder-"+std::to_string(reinterpret_cast<uintptr_t>(&marker)));fs::create_directory(dir);
 for(unsigned width:{32u,64u}){
  std::string name=width==64?"remainder":"remainderf";std::ofstream f(dir/(name+"-special.corpus"),std::ios::binary);
  f<<IR_PROVENANCE<<"\n# function "<<name<<"\n# seed 0 count 0 fresh True entries 1\n# x y result quotient invalid\n"<<(width==64?"0000000000000000 0000000000000001 0000000000000000 0 0\n":"00000000 00000001 00000000 0 0\n")<<"bad\n";f.close();
  IrEnvironment guard;ASSERT_TRUE(guard.good);ASSERT_EQ(fesetround(FE_UPWARD),0);ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT),0);ASSERT_EQ(feraiseexcept(FE_DIVBYZERO),0);int flags=fetestexcept(FE_ALL_EXCEPT);errno=733;
  EXPECT_EQ(ir_run(dir.c_str(),width,0,NULL),1);EXPECT_EQ(errno,733);EXPECT_EQ(fegetround(),FE_UPWARD);EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT),flags);EXPECT_EQ(fesetenv(&guard.saved),0);
 }
 fs::remove_all(dir);
}
TEST(IeeeRemainder,EnvironmentRestoresAfterFatalAssertion){
 IrEnvironment guard;ASSERT_TRUE(guard.good);ASSERT_EQ(fesetround(FE_UPWARD),0);ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT),0);ASSERT_EQ(feraiseexcept(FE_DIVBYZERO),0);int flags=fetestexcept(FE_ALL_EXCEPT);errno=733;
 EXPECT_FATAL_FAILURE(ir_fatal_under_guard(),"deliberate guarded assertion");
 EXPECT_EQ(fegetround(),FE_UPWARD);EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT),flags);EXPECT_EQ(errno,733);
}
int main(int argc,char **argv){testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
