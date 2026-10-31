/** @file Binary64 unary arctangent literal contracts.
 * Copyright 2026 by Corey Pennycuff
 */
#include "../atan_corpus.h"
#include "test_helpers.h"
namespace {
struct AtanCase {uint64_t x, expected;unsigned flags;bool strict;};
void CheckAtan(const AtanCase * cases, size_t count) {
  const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  for (size_t i=0;i<count;++i) for (int mode:modes) {
    for (unsigned subset=0;subset<32;++subset) for (int error:{0,733}) {
      SCOPED_TRACE(i);
      EXPECT_EQ(a64_call(cases[i].x,cases[i].expected,cases[i].flags,
          cases[i].strict||mode==FE_TONEAREST,mode,subset,error),0);
    }
  }
}
}
TEST(Atan, PinnedCorpusAndCallerState) {
  const char * root=std::getenv("GMATH_ATAN_CORPUS_DIR");
  EXPECT_EQ(a64_probe(root&&*root?root:"tests/corpus",1),0);
}
TEST(Atan, SignedZerosAndNaNs) {
  const AtanCase c[] = {
    {0,0,0,true},{UINT64_C(0x8000000000000000),UINT64_C(0x8000000000000000),0,true},
    {UINT64_C(0x7ff8000000000001),UINT64_C(0x7ff8000000000000),0,true},
    {UINT64_C(0xfff8000000000007),UINT64_C(0x7ff8000000000000),0,true},
    {UINT64_C(0x7ff0000000000001),UINT64_C(0x7ff8000000000000),1,true},
    {UINT64_C(0xfff4000000000000),UINT64_C(0x7ff8000000000000),1,true}};
  CheckAtan(c,sizeof c/sizeof *c);
}
TEST(Atan, TinyBitsAndAfterRoundTininess) {
  const AtanCase c[] = {
    {1,1,6,true},{UINT64_C(0x8000000000000001),UINT64_C(0x8000000000000001),6,true},
    {UINT64_C(0x000fffffffffffff),UINT64_C(0x000fffffffffffff),6,true},
    {UINT64_C(0x0010000000000000),UINT64_C(0x0010000000000000),2,true},
    {UINT64_C(0x3e0fffffffffffff),UINT64_C(0x3e0fffffffffffff),2,true},
    {UINT64_C(0xbe0fffffffffffff),UINT64_C(0xbe0fffffffffffff),2,true}};
  CheckAtan(c,sizeof c/sizeof *c);
}
TEST(Atan, HugeAndInfiniteAnglesAvoidSpuriousUnderflow) {
  const AtanCase c[] = {
    {UINT64_C(0x4350000000000000),UINT64_C(0x3ff921fb54442d18),2,true},
    {UINT64_C(0xc350000000000000),UINT64_C(0xbff921fb54442d18),2,true},
    {UINT64_C(0x7fefffffffffffff),UINT64_C(0x3ff921fb54442d18),2,true},
    {UINT64_C(0xffefffffffffffff),UINT64_C(0xbff921fb54442d18),2,true},
    {UINT64_C(0x7ff0000000000000),UINT64_C(0x3ff921fb54442d18),2,true},
    {UINT64_C(0xfff0000000000000),UINT64_C(0xbff921fb54442d18),2,true}};
  CheckAtan(c,sizeof c/sizeof *c);
}
TEST(Atan, GeneralSubsetHasNormalResultsAndInexactOnly) {
  const AtanCase c[] = {
    {UINT64_C(0x3e10000000000000),UINT64_C(0x3e10000000000000),2,false},
    {UINT64_C(0x3ff0000000000000),UINT64_C(0x3fe921fb54442d18),2,false},
    {UINT64_C(0xbff0000000000000),UINT64_C(0xbfe921fb54442d18),2,false},
    {UINT64_C(0x434fffffffffffff),UINT64_C(0x3ff921fb54442d18),2,false}};
  CheckAtan(c,sizeof c/sizeof *c);
}
int main(int argc,char **argv) {
  ::testing::InitGoogleTest(&argc,argv);
  return RUN_ALL_TESTS();
}
