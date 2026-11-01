/** @file Combined cancellation-safe logarithm/exponential family contracts.
 * Copyright 2026 by Corey Pennycuff
 */
#include "test_helpers.h"
#include "../log1p_expm1_probe.h"
TEST(Log1pExpm1, IndependentFamilyCorpusAndCallerState) {
  const char *root=std::getenv("GMATH_LOG1P_EXPM1_CORPUS_DIR");
  EXPECT_EQ(log1p_expm1_probe(root&&*root?root:"tests/corpus",1,0),0);
}
TEST(Log1pExpm1, AnalyticSpecialValuesAndFlagPriority) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);
  for(unsigned width:{64u,32u}) {
    unsigned p=width==64?52:23,bias=width==64?1023:127;
    uint64_t sign=UINT64_C(1)<<(width-1),one=(uint64_t)bias<<p,inf=(uint64_t)(2*bias+1)<<p;
    uint64_t nan=inf|(UINT64_C(1)<<(p-1));
    for(unsigned exponential=0;exponential<2;++exponential) {
      const uint64_t inputs[]={0,sign,inf,sign|inf,nan,sign|nan,inf|1,sign|inf|1,sign|one};
      const uint64_t log_targets[]={0,sign,inf,nan,nan,nan,nan,nan,sign|inf};
      const unsigned log_flags[]={0,0,0,1,0,0,1,1,16};
      const uint64_t exp_targets[]={0,sign,inf,sign|one,nan,nan,nan,nan,0};
      const unsigned exp_flags[]={0,0,0,0,0,0,1,1,2};
      for(unsigned i=0;i<(exponential?8u:9u);++i) {
        EXPECT_EQ(fesetround(FE_TONEAREST),0);EXPECT_EQ(feclearexcept(FE_ALL_EXCEPT),0);
        EXPECT_EQ(pe_call(inputs[i],width,exponential),exponential?exp_targets[i]:log_targets[i]);
        EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT),pe_flags(exponential?exp_flags[i]:log_flags[i]));
      }
    }
  }
  EXPECT_EQ(fesetenv(&saved),0);
}
TEST(Log1pExpm1, MonotonicitySignsAndConvexityBounds) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);ASSERT_EQ(fesetround(FE_TONEAREST),0);
  for(unsigned width:{64u,32u}) {
    double previous[2]={-100.0,-2.0};
    for(int i=-127;i<=1024;++i) {
      double x=(double)i/128.0;uint64_t raw=width==64?pe_bits(x):pe_fbits((float)x);
      double logarithm=pe_value(pe_call(raw,width,0),width),exponential=pe_value(pe_call(raw,width,1),width);
      EXPECT_GE(logarithm,previous[0]);EXPECT_GE(exponential,previous[1]);
      EXPECT_LE(logarithm,x);EXPECT_GE(exponential,x);EXPECT_GE(exponential,-1.0);
      previous[0]=logarithm;previous[1]=exponential;
    }
  }
  EXPECT_EQ(fesetenv(&saved),0);
}
TEST(Log1pExpm1, ClosedCellsAndNormalSubnormalBoundary) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);ASSERT_EQ(fesetround(FE_TONEAREST),0);
  for(unsigned width:{64u,32u}) {
    uint64_t sign=UINT64_C(1)<<(width-1),one=width==64?UINT64_C(0x3ff0000000000000):UINT64_C(0x3f800000);
    double maximum=0;
    EXPECT_EQ(pe_accuracy(one-1,one,width,-268435456,-268435456,&maximum),0);
    EXPECT_NE(pe_accuracy(one-2,one,width,-268435456,-268435456,&maximum),0);
    EXPECT_NE(pe_accuracy(one-2,one,width,-1,0,&maximum),0);
    EXPECT_NE(pe_accuracy(sign|(one-2),sign|one,width,0,1,&maximum),0);
    EXPECT_EQ(pe_accuracy(sign|(one-1),sign|one,width,268435456,268435456,&maximum),0);
    uint64_t minimum=width==64?UINT64_C(0x0010000000000000):UINT64_C(0x00800000);
    EXPECT_EQ(pe_accuracy(minimum-1,minimum,width,-268435456,-268435456,&maximum),0);
  }
  EXPECT_EQ(fesetenv(&saved),0);
}
TEST(Log1pExpm1, PreserveFlushToZeroControlAndState) {
#if defined(__GNUC__) && defined(__SSE__) && (defined(__i386__) || defined(__x86_64__))
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);uint32_t before;
  __asm__ volatile("stmxcsr %0" : "=m"(before) : : "memory");
  uint32_t alternate=before|UINT32_C(0x8000);
  __asm__ volatile("ldmxcsr %0" : : "m"(alternate) : "memory");
  uint64_t controls=gmath_test_controls();
  const char *root=std::getenv("GMATH_LOG1P_EXPM1_CORPUS_DIR");
  EXPECT_EQ(log1p_expm1_probe(root&&*root?root:"tests/corpus",1,0),0);
  EXPECT_EQ(gmath_test_controls(),controls);
  __asm__ volatile("ldmxcsr %0" : : "m"(before) : "memory");
  EXPECT_EQ(fesetenv(&saved),0);
#else
  GTEST_SKIP()<<"alternate SSE control setting is not available on this target";
#endif
}
int main(int argc,char **argv){::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
