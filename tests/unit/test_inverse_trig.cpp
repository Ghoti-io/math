/** @file Combined inverse sine/cosine numerical and raw-state tests.
 * Copyright 2026 by Corey Pennycuff
 */
#include "test_helpers.h"
#include "../inverse_trig_probe.h"

TEST(InverseTrig, IndependentFamilyCorpusAndCallerState) {
  const char *root=std::getenv("GMATH_INVERSE_TRIG_CORPUS_DIR");
  EXPECT_EQ(inverse_trig_probe(root&&*root?root:"tests/corpus",1,0),0);
}
TEST(InverseTrig, AnalyticZerosEndpointsAndDomain) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);
  const unsigned widths[]={64,32};
  for(unsigned width:widths) {
    unsigned p=width==64?52:23,bias=width==64?1023:127;
    uint64_t sign=UINT64_C(1)<<(width-1),one=(uint64_t)bias<<p;
    for(unsigned cosine=0;cosine<2;++cosine) {
      const uint64_t inputs[]={0,sign,one,sign|one,one+1,sign|(one+1)};
      const uint64_t expected64[2][6]={{0,UINT64_C(0x8000000000000000),UINT64_C(0x3ff921fb54442d18),UINT64_C(0xbff921fb54442d18),UINT64_C(0x7ff8000000000000),UINT64_C(0x7ff8000000000000)},
        {UINT64_C(0x3ff921fb54442d18),UINT64_C(0x3ff921fb54442d18),0,UINT64_C(0x400921fb54442d18),UINT64_C(0x7ff8000000000000),UINT64_C(0x7ff8000000000000)}};
      const uint64_t expected32[2][6]={{0,UINT64_C(0x80000000),UINT64_C(0x3fc90fdb),UINT64_C(0xbfc90fdb),UINT64_C(0x7fc00000),UINT64_C(0x7fc00000)},
        {UINT64_C(0x3fc90fdb),UINT64_C(0x3fc90fdb),0,UINT64_C(0x40490fdb),UINT64_C(0x7fc00000),UINT64_C(0x7fc00000)}};
      for(unsigned i=0;i<6;++i) {
        EXPECT_EQ(fesetround(FE_TONEAREST),0);EXPECT_EQ(feclearexcept(FE_ALL_EXCEPT),0);
        EXPECT_EQ(it_call(inputs[i],width,cosine),width==64?expected64[cosine][i]:expected32[cosine][i]);
        EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT),it_flags(it_expected_flags(inputs[i],width,cosine)));
      }
    }
  }
  EXPECT_EQ(fesetenv(&saved),0);
}
TEST(InverseTrig, PrincipalRangesMonotonicitySymmetryAndSeams) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);ASSERT_EQ(fesetround(FE_TONEAREST),0);
  for(unsigned width:{64u,32u}) {
    double previous_asin=-2.0,previous_acos=4.0;
    for(int i=-1024;i<=1024;++i) {
      double x=(double)i/1024.0;uint64_t raw=width==64?it_bits(x):it_fbits((float)x);
      uint64_t sine=it_call(raw,width,0),cosine=it_call(raw,width,1);
      double a=it_value(sine,width),c=it_value(cosine,width);
      EXPECT_GE(a,previous_asin);EXPECT_LE(c,previous_acos);
      EXPECT_GE(a,-1.571);EXPECT_LE(a,1.571);EXPECT_GE(c,0.0);EXPECT_LE(c,3.142);
      uint64_t sign=UINT64_C(1)<<(width-1);
      EXPECT_EQ(it_call(raw^sign,width,0),sine^sign);
      previous_asin=a;previous_acos=c;
    }
    uint64_t half=width==64?UINT64_C(0x3fe0000000000000):UINT64_C(0x3f000000);
    for(uint64_t sign:{UINT64_C(0),UINT64_C(1)<<(width-1)}) {
      for(unsigned cosine=0;cosine<2;++cosine) {
        double left=it_value(it_call(sign|(half-1),width,cosine),width);
        double right=it_value(it_call(sign|(half+1),width,cosine),width);
        double difference=left-right;if(difference<0)difference=-difference;
        EXPECT_LT(difference,width==64?0x1p-48:0x1p-19);
      }
    }
  }
  EXPECT_EQ(fesetenv(&saved),0);
}
TEST(InverseTrig, ClosedErrorCellsUseRealBinadeSpacing) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);ASSERT_EQ(fesetround(FE_TONEAREST),0);
  for(unsigned width:{64u,32u}) {
    uint64_t sign=UINT64_C(1)<<(width-1),one=width==64?UINT64_C(0x3ff0000000000000):UINT64_C(0x3f800000);
    double maximum=0;
    EXPECT_EQ(it_accuracy(one-1,one,width,-268435456,-268435456,&maximum),0);
    EXPECT_NE(it_accuracy(one-2,one,width,-268435456,-268435456,&maximum),0);
    EXPECT_EQ(it_accuracy(sign|(one-1),sign|one,width,268435456,268435456,&maximum),0);
    EXPECT_NE(it_accuracy(sign|(one-2),sign|one,width,268435456,268435456,&maximum),0);
    EXPECT_NE(it_accuracy(one-2,one,width,-1,0,&maximum),0);
    EXPECT_NE(it_accuracy(sign|(one-2),sign|one,width,0,1,&maximum),0);
    EXPECT_NE(it_accuracy(one+2,one+1,width,-268435456,-268435456,&maximum),0);
    EXPECT_EQ(it_accuracy(one+2,one+1,width,268435456,268435456,&maximum),0);
    uint64_t minimum=width==64?UINT64_C(0x0010000000000000):UINT64_C(0x00800000);
    EXPECT_EQ(it_accuracy(minimum-1,minimum,width,-268435456,-268435456,&maximum),0);
  }
  EXPECT_EQ(fesetenv(&saved),0);
}
int main(int argc,char **argv) {
  ::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();
}
