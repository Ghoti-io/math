/** @file Combined inverse hyperbolic family contracts.
 * Copyright 2026 by Corey Pennycuff
 */
#include "test_helpers.h"
#include "../inverse_hyperbolic_probe.h"
TEST(InverseHyperbolic, IndependentFamilyCorpusAndCallerState) {
  const char *root=std::getenv("GMATH_INVERSE_HYPERBOLIC_CORPUS_DIR");
  EXPECT_EQ(inverse_hyperbolic_probe(root&&*root?root:"tests/corpus",1,0),0);
}
TEST(InverseHyperbolic, AnalyticSpecialValuesAndFlagPriority) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);
  for(unsigned width:{64u,32u}) {
    unsigned p=width==64?52:23,bias=width==64?1023:127;
    uint64_t sign=UINT64_C(1)<<(width-1),one=(uint64_t)bias<<p,inf=(uint64_t)(2*bias+1)<<p;
    uint64_t nan=inf|(UINT64_C(1)<<(p-1));
    const uint64_t inputs[]={0,sign,inf,sign|inf,nan,sign|nan,inf|1,sign|inf|1,one,sign|one};
    const uint64_t targets[3][10]={
      {0,sign,inf,sign|inf,nan,nan,nan,nan,0,0},
      {nan,nan,inf,nan,nan,nan,nan,nan,0,nan},
      {0,sign,nan,nan,nan,nan,nan,nan,inf,sign|inf}};
    const unsigned flags[3][10]={{0,0,0,0,0,0,1,1,2,2},{1,1,0,1,0,0,1,1,0,1},{0,0,1,1,0,0,1,1,16,16}};
    for(unsigned kind=0;kind<3;++kind)for(unsigned i=0;i<10;++i) {
      if(kind==0&&i>=8)continue;
      EXPECT_EQ(fesetround(FE_TONEAREST),0);EXPECT_EQ(feclearexcept(FE_ALL_EXCEPT),0);
      EXPECT_EQ(ip_call(inputs[i],width,kind),targets[kind][i]);
      EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT),ip_flags(flags[kind][i]));
    }
  }
  EXPECT_EQ(fesetenv(&saved),0);
}
TEST(InverseHyperbolic, SymmetryMonotonicityAndBounds) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);ASSERT_EQ(fesetround(FE_TONEAREST),0);
  for(unsigned width:{64u,32u}) {
    uint64_t sign=UINT64_C(1)<<(width-1);double previous[3]={0.0,0.0,0.0};
    for(int i=0;i<=2560;++i) {
      double x=(double)i/128.0;uint64_t raw=width==64?ip_bits(x):ip_fbits((float)x);
      for(unsigned kind=0;kind<3;++kind) {
        if((kind==1&&x<1.0)||(kind==2&&x>1.0))continue;
        uint64_t positive=ip_call(raw,width,kind);
        if(kind!=1){EXPECT_EQ(ip_call(raw|sign,width,kind),positive|sign);}
        double value=ip_value(positive,width);EXPECT_GE(value,previous[kind]);previous[kind]=value;
        if(kind==0){EXPECT_LE(value,x); }
        if(kind==1){EXPECT_GE(value,0.0); }
        if(kind==2){EXPECT_GE(value,x);}
      }
    }
  }
  const char *root=std::getenv("GMATH_INVERSE_HYPERBOLIC_CORPUS_DIR");
  std::string path=std::string(root&&*root?root:"tests/corpus")+"/inverse-hyperbolic.corpus";
  FILE *file=fopen(path.c_str(),"rb");
  if(!file) {
    ADD_FAILURE()<<"cannot open monotonicity population "<<path;
  } else {
    char line[512];uint64_t previous[2][3]={{0,0,0},{0,0,0}};
    for(unsigned header=0;header<2;++header)if(!fgets(line,sizeof line,file)){ADD_FAILURE()<<"missing header";}
    while(fgets(line,sizeof line,file)) {
      gmath_hyperbolic_row row;
      if(gmath_parse_hyperbolic_row(line,&row)){ADD_FAILURE()<<"malformed monotonicity row";break;}
      unsigned width=row.width,index=width==64?0:1,p=width==64?52:23,bias=width==64?1023:127;
      uint64_t sign=UINT64_C(1)<<(width-1),one=(uint64_t)bias<<p,inf=(uint64_t)(2*bias+1)<<p;
      if(row.input&sign||row.input>=inf)continue;
      for(unsigned kind=0;kind<3;++kind) {
        if((kind==1&&row.input<one)||(kind==2&&row.input>one))continue;
        uint64_t positive=ip_call(row.input,width,kind);
        if(kind!=1){EXPECT_EQ(ip_call(row.input|sign,width,kind),positive|sign);}
        EXPECT_GE(positive,previous[index][kind]);previous[index][kind]=positive;
        if(kind==0){EXPECT_LE(positive,row.input);}
        if(kind==1){
          EXPECT_LE(positive,row.input);
          double x=ip_value(row.input,width);
          if(x>=2.0) {
            double lower=gmath_log(x),upper=lower+0x1.62e42fefa39efp-1;
            double y=ip_value(positive,width);
            // log(x) < acosh(x) < log(2x), allowing existing log's
            // one-ULP error and final arithmetic; no doubling huge x.
            EXPECT_GE(y,lower*(1.0-0x1p-48));
            EXPECT_LE(y,upper*(1.0+0x1p-22));
            if(x>=0x1p60) {
              uint64_t expected=width==64?ip_bits(upper):ip_fbits((float)upper);
              uint64_t distance=positive>expected?positive-expected:expected-positive;
              EXPECT_LE(distance,8u);
            }
          }
        }
        if(kind==2){EXPECT_GE(positive,row.input);}
      }
    }
    EXPECT_EQ(ferror(file),0);fclose(file);
  }
  EXPECT_EQ(fesetenv(&saved),0);
}
TEST(InverseHyperbolic, ClosedCellsAndNormalSubnormalBoundary) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);ASSERT_EQ(fesetround(FE_TONEAREST),0);
  for(unsigned width:{64u,32u}) {
    uint64_t sign=UINT64_C(1)<<(width-1),one=width==64?UINT64_C(0x3ff0000000000000):UINT64_C(0x3f800000);
    double maximum=0;
    EXPECT_EQ(ip_accuracy(one-1,one,width,-268435456,-268435456,&maximum),0);
    EXPECT_NE(ip_accuracy(one-2,one,width,-268435456,-268435456,&maximum),0);
    EXPECT_NE(ip_accuracy(one-2,one,width,-1,0,&maximum),0);
    EXPECT_NE(ip_accuracy(sign|(one-2),sign|one,width,0,1,&maximum),0);
    EXPECT_EQ(ip_accuracy(sign|(one-1),sign|one,width,268435456,268435456,&maximum),0);
    uint64_t minimum=width==64?UINT64_C(0x0010000000000000):UINT64_C(0x00800000);
    EXPECT_EQ(ip_accuracy(minimum-1,minimum,width,-268435456,-268435456,&maximum),0);
  }
  EXPECT_EQ(fesetenv(&saved),0);
}
TEST(InverseHyperbolic, PreserveFlushToZeroControlAndState) {
#if defined(__GNUC__) && defined(__SSE__) && (defined(__i386__) || defined(__x86_64__))
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);uint32_t before;
  __asm__ volatile("stmxcsr %0" : "=m"(before) : : "memory");
  alignas(16) unsigned char area[512]={};
  __asm__ volatile("fxsave %0" : "=m"(area) : : "memory");
  uint32_t mask;memcpy(&mask,area+28,sizeof mask);
  if(!mask)mask=UINT32_C(0x0000ffbf);
  unsigned daz_settings=(mask&UINT32_C(0x40))?2u:1u;
  const char *root=std::getenv("GMATH_INVERSE_HYPERBOLIC_CORPUS_DIR");
  for(unsigned ftz=0;ftz<2;++ftz)for(unsigned daz=0;daz<daz_settings;++daz) {
    uint32_t alternate=(before&~UINT32_C(0x8040))|(ftz?UINT32_C(0x8000):0)|(daz?UINT32_C(0x40):0);
    __asm__ volatile("ldmxcsr %0" : : "m"(alternate) : "memory");
    uint32_t observed;__asm__ volatile("stmxcsr %0" : "=m"(observed) : : "memory");
    EXPECT_EQ(observed&UINT32_C(0x8040),alternate&UINT32_C(0x8040));
    uint64_t controls=gmath_test_controls();
    for(unsigned width:{64u,32u}) {
      uint64_t minimum=width==64?UINT64_C(0x0010000000000000):UINT64_C(0x00800000);
      double maximum=0;
      EXPECT_EQ(ip_accuracy(minimum-1,minimum,width,-268435456,-268435456,&maximum),0);
      EXPECT_NE(ip_accuracy(minimum-2,minimum,width,-268435456,-268435456,&maximum),0);
      EXPECT_EQ(ip_accuracy(1,1,width,-1,0,&maximum),0);
      EXPECT_NE(ip_accuracy(3,1,width,-1,0,&maximum),0);
    }
    EXPECT_EQ(inverse_hyperbolic_probe(root&&*root?root:"tests/corpus",1,0),0);
    EXPECT_EQ(gmath_test_controls(),controls);
  }
  __asm__ volatile("ldmxcsr %0" : : "m"(before) : "memory");
  EXPECT_EQ(fesetenv(&saved),0);
#else
  GTEST_SKIP()<<"alternate SSE control setting is not available on this target";
#endif
}
int main(int argc,char **argv){::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
