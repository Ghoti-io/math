/** @file Exact positive difference and caller-state contracts.
 * Copyright 2026 by Corey Pennycuff
 */
#include "../positive_difference_probe.h"
#include "test_helpers.h"
TEST(PositiveDifference, PinnedDouble) {
  const char * root=std::getenv("GMATH_FDIM_CORPUS_DIR");
  EXPECT_EQ(ppd_probe(root&&*root?root:"tests/corpus",64,1),0);
}
TEST(PositiveDifference, PinnedFloat) {
  const char * root=std::getenv("GMATH_FDIM_CORPUS_DIR");
  EXPECT_EQ(ppd_probe(root&&*root?root:"tests/corpus",32,1),0);
}
namespace {
struct Case {unsigned width;uint64_t x,y,result;unsigned flags;};
void Check(const Case * cases,size_t count) {
  const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  uint64_t hash=GMATH_FNV_BASIS;
  for(size_t i=0;i<count;++i)for(int mode:modes)for(int subset=0;subset<32;++subset)for(int error:{0,733}) {
    SCOPED_TRACE(i);
    EXPECT_EQ(ppd_call(cases[i].x,cases[i].y,cases[i].result,cases[i].flags,
        cases[i].width,mode,subset,error,&hash,1),0);
  }
}
}
TEST(PositiveDifference, OrderedZerosAndInfiniteDifferencesAreExact) {
  const Case cases[]={
    {64,0,0x8000000000000000ull,0,0},
    {64,0x8000000000000000ull,0,0,0},
    {64,0x7ff0000000000000ull,0x7ff0000000000000ull,0,0},
    {64,0xfff0000000000000ull,0xfff0000000000000ull,0,0},
    {64,0x7ff0000000000000ull,0,0x7ff0000000000000ull,0},
    {64,0,0xfff0000000000000ull,0x7ff0000000000000ull,0},
    {32,0x7f800000,0x7f800000,0,0},
    {32,0xff800000,0xff800000,0,0},
    {32,0x3f800000,0x40000000,0,0},
    {32,0xbf800000,0xc0000000,0x3f800000,0}};
  Check(cases,sizeof cases/sizeof *cases);
}
TEST(PositiveDifference, TinyPositiveDifferencesAreExactWithoutUnderflow) {
  const Case cases[]={
    {64,0x0010000000000000ull,0x000fffffffffffffull,1,0},
    {64,0x8000000000000001ull,0x8010000000000000ull,0x000fffffffffffffull,0},
    {64,1,0x8000000000000001ull,2,0},
    {64,0,0x8000000000000001ull,1,0},
    {32,0x00800000,0x007fffff,1,0},
    {32,0x80000001,0x80800000,0x007fffff,0},
    {32,1,0x80000001,2,0}};
  Check(cases,sizeof cases/sizeof *cases);
}
TEST(PositiveDifference, NearestTiesRespectThePowerOfTwoPredecessorSeam) {
  const Case cases[]={
    {64,0x3ff0000000000000ull,0x3c9fffffffffffffull,0x3fefffffffffffffull,2},
    {64,0x3ff0000000000000ull,0x3c90000000000000ull,0x3ff0000000000000ull,2},
    {64,0x3ff0000000000000ull,0x3c90000000000001ull,0x3fefffffffffffffull,2},
    {64,0x3ff0000000000000ull,0xbca0000000000000ull,0x3ff0000000000000ull,2},
    {64,0x3ff0000000000001ull,0xbca0000000000000ull,0x3ff0000000000002ull,2},
    {32,0x3f800000,0x337fffff,0x3f7fffff,2},
    {32,0x3f800000,0x33000000,0x3f800000,2},
    {32,0x3f800000,0x33000001,0x3f7fffff,2},
    {32,0x3f800001,0xb3800000,0x3f800002,2}};
  Check(cases,sizeof cases/sizeof *cases);
}
TEST(PositiveDifference, RoundedOverflowDistinguishesTheFiniteMaximumCell) {
  const Case cases[]={
    {64,0x7fefffffffffffffull,0xfc8fffffffffffffull,0x7fefffffffffffffull,2},
    {64,0x7fefffffffffffffull,0xfc90000000000000ull,0x7ff0000000000000ull,6},
    {64,0x7fe0000000000000ull,0xffe0000000000000ull,0x7ff0000000000000ull,6},
    {32,0x7f7fffff,0xf2ffffff,0x7f7fffff,2},
    {32,0x7f7fffff,0xf3000000,0x7f800000,6},
    {32,0x7f000000,0xff000000,0x7f800000,6}};
  Check(cases,sizeof cases/sizeof *cases);
}
TEST(PositiveDifference, EitherSignalingNaNOverridesQuietNaNWithoutOtherFlags) {
  const Case cases[]={
    {64,0x7ff8000000000001ull,0x7ff0000000000001ull,0x7ff8000000000000ull,1},
    {64,0xfff0000000000001ull,0x7ff8000000000001ull,0x7ff8000000000000ull,1},
    {64,0x7ff8000000000001ull,0x7ff0000000000000ull,0x7ff8000000000000ull,0},
    {32,0x7fc00001,0x7f800001,0x7fc00000,1},
    {32,0xff800001,0x7fc00001,0x7fc00000,1},
    {32,0x7fc00001,0x7f800000,0x7fc00000,0}};
  Check(cases,sizeof cases/sizeof *cases);
}
int main(int argc,char **argv){::testing::InitGoogleTest(&argc,argv);return RUN_ALL_TESTS();}
