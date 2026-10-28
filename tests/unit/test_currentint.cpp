/** @file Exact current-mode integer conversion.
 * Copyright 2026 by Corey Pennycuff
 */
#include "../current_ir_probe.h"
#include "test_helpers.h"
TEST(CurrentInteger, PinnedDouble) {
  const char * p=std::getenv("GMATH_CURRENTINT_CORPUS_DIR");
  EXPECT_EQ(cr_probe(p&&*p?p:"tests/corpus",64,1),0);
}
TEST(CurrentInteger, PinnedFloat) {
  const char * p=std::getenv("GMATH_CURRENTINT_CORPUS_DIR");
  EXPECT_EQ(cr_probe(p&&*p?p:"tests/corpus",32,1),0);
}
TEST(CurrentInteger, TinyFractionsRequireOnlyInexactInEveryMode) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);int error=errno;
  const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  const uint64_t positive[]={0,0,1,0},negative[]={0,UINT64_MAX,0,0};
  uint64_t hash=GMATH_FNV_BASIS;
  for(unsigned mode=0;mode<4;mode++) {
    for(int subset=0;subset<32;subset++) {
      EXPECT_EQ(cr_call(1,positive[mode],2,64,0,modes[mode],subset,733,&hash),0);
      EXPECT_EQ(cr_call(UINT64_C(0x80000001),negative[mode],2,32,1,modes[mode],subset,0,&hash),0);
    }
  }
  EXPECT_EQ(fesetenv(&saved),0);errno=error;
}
TEST(CurrentInteger, ExactMinimumAndInvalidSentinelDifferOnlyByInvalid) {
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);int error=errno;uint64_t hash=GMATH_FNV_BASIS;
  EXPECT_EQ(cr_call(UINT64_C(0xc3e0000000000000),UINT64_C(0x8000000000000000),0,64,1,FE_TONEAREST,0,733,&hash),0);
  EXPECT_EQ(cr_call(UINT64_C(0x43e0000000000000),UINT64_C(0x8000000000000000),1,64,1,FE_TONEAREST,0,733,&hash),0);
  EXPECT_EQ(fesetenv(&saved),0);errno=error;
}
TEST(CurrentInteger, NativeLong32ChecksTheRoundedBoundaryBeforeInexact) {
#if LONG_MAX == INT32_MAX
  fenv_t saved;ASSERT_EQ(fegetenv(&saved),0);int error=errno;uint64_t hash=GMATH_FNV_BASIS;
  const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  const uint64_t positive[]={UINT64_C(0xffffffff80000000),UINT64_C(0x7fffffff),UINT64_C(0xffffffff80000000),UINT64_C(0x7fffffff)};
  const unsigned flags[]={1,2,1,2};
  for(unsigned i=0;i<4;i++) {
    EXPECT_EQ(cr_call(UINT64_C(0x41dfffffffe00000),positive[i],flags[i],64,0,modes[i],0,733,&hash),0);
    EXPECT_EQ(cr_call(UINT64_C(0xc1e0000000100000),UINT64_C(0xffffffff80000000),i==1?1u:2u,64,0,modes[i],0,733,&hash),0);
  }
  EXPECT_EQ(fesetenv(&saved),0);errno=error;
#else
  GTEST_SKIP()<<"native long is64 bits; signed32 boundary runs in raw cross probes";
#endif
}
int main(int argc,char ** argv) {::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
