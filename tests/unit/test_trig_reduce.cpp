/**
 * @file
 *
 * The fast argument reduction of src/elementary/trig.c against the exact one.
 *
 * The oracle corpus (test_trig.cpp) says the results are right; this says the
 * two reductions agree, which is what keeps the results the same bits as they
 * were before the fast one existed, and that the fast one is in fact taken: a
 * reduction that always declines gives right answers, slowly, and nothing in
 * the corpus would show it.
 *
 * trig.c is included here under other names for its three public functions
 * (the library's own are linked in as well) so that its static reduce_fast,
 * reduce and the constants are reachable.
 *
 * Copyright 2026 by Corey Pennycuff
 */

#include "test_helpers.h"

#include <ghoti.io/math/elementary.h>

#undef gmath_sin
#undef gmath_cos
#undef gmath_tan
#define gmath_sin test_copy_of_gmath_sin
#define gmath_cos test_copy_of_gmath_cos
#define gmath_tan test_copy_of_gmath_tan

#include "../../src/elementary/trig.c"

#include <cmath>
#include <cstdint>
#include <cstdio>

namespace {

struct Rng {
  uint64_t s = 0x9e3779b97f4a7c15ull;
  uint64_t next() {
    s ^= s << 13;
    s ^= s >> 7;
    s ^= s << 17;
    return s;
  }
  // [0, 1) with 53 random bits.
  double unit() { return static_cast<double>(next() >> 11) * 0x1p-53; }
};

struct Tally {
  long tried = 0;
  long declined = 0;
  long wrong_n = 0;
  long wrong_rh = 0;
  long wrong_rl = 0;
};

// Compare the fast reduction with the exact one at x (pi/4 < x < 2^20).
void Compare(double x, Tally * t) {
  double fh, fl, eh, el;
  t->tried++;
  int nf = reduce_fast(x, &fh, &fl);
  if (nf < 0) {
    t->declined++;
    return;
  }
  int ne = reduce(x, &eh, &el);
  if (nf != ne) {
    if (++t->wrong_n <= 3) ADD_FAILURE() << std::hexfloat << x << ": n " << nf << " vs " << ne;
    return;
  }
  if (fh != eh) {
    if (++t->wrong_rh <= 3) ADD_FAILURE() << std::hexfloat << x << ": rh " << fh << " vs " << eh;
    return;
  }
  // Within 2^-79 of the remainder, the bound reduce_fast documents.
  if (std::fabs(fl - el) > 0x1p-79 * std::fabs(eh)) {
    if (++t->wrong_rl <= 3) ADD_FAILURE() << std::hexfloat << x << ": rl " << fl << " vs " << el;
  }
}

void Expect(const Tally & t, const char * what, double max_declined_fraction) {
  std::printf("  %s: %ld arguments, %ld declined\n", what, t.tried, t.declined);
  EXPECT_EQ(t.wrong_n, 0) << what;
  EXPECT_EQ(t.wrong_rh, 0) << what;
  EXPECT_EQ(t.wrong_rl, 0) << what;
  EXPECT_GT(t.tried, 0) << what;
  EXPECT_LE(static_cast<double>(t.declined), max_declined_fraction * static_cast<double>(t.tried))
      << what << ": the fast reduction declines too often to be the fast path";
}

}  // namespace

TEST(TrigReduce, UniformAgreesAndIsTaken) {
  Rng r;
  Tally t;
  for (int i = 0; i < 400000; i++) {
    double x = GMATH_PIO4 + r.unit() * (0x1p20 - GMATH_PIO4);
    if (x > GMATH_PIO4 && x < 0x1p20) Compare(x, &t);
  }
  Expect(t, "uniform in (pi/4, 2^20)", 1e-4);
}

TEST(TrigReduce, EveryBinadeAgreesAndIsTaken) {
  Rng r;
  Tally t;
  for (int i = 0; i < 400000; i++) {
    int e = static_cast<int>(r.next() % 21) - 1;  // 2^-1 .. 2^19
    double x = std::ldexp(1.0 + r.unit(), e);
    if (x > GMATH_PIO4 && x < 0x1p20) Compare(x, &t);
  }
  Expect(t, "every binade", 1e-4);
}

TEST(TrigReduce, NearMultiplesOfPiOver2Agree) {
  // The doubles around k*pi/2 and at offsets that put the remainder anywhere
  // from 2^-60 up; the declined ones are the ones under the 2^-55 floor and
  // the ones the quotient rounds the wrong way, and are few.
  Rng r;
  Tally t;
  for (int i = 0; i < 300000; i++) {
    double k = static_cast<double>(1 + r.next() % 667544);
    double x = k * 1.5707963267948966;  // within ulp(x) of k*pi/2
    double u = std::ldexp(1.0, std::ilogb(x) - 52);
    int sh = static_cast<int>(r.next() % 34);
    double off = static_cast<double>(static_cast<int64_t>(r.next() % 2001) - 1000) * u * std::ldexp(1.0, sh);
    x += off;
    if (x > GMATH_PIO4 && x < 0x1p20) Compare(x, &t);
  }
  Expect(t, "near k*pi/2", 0.2);
}

TEST(TrigReduce, TheLimitIsExclusiveAndBothSidesAgree) {
  // Just below 2^20 the fast path may run; at and above it never does, and the
  // dispatcher gives the same quadrant either way.
  double below = 0x1p20;
  for (int i = 0; i < 64; i++) {
    below = std::nextafter(below, 0.0);
    Tally t;
    Compare(below, &t);
    EXPECT_EQ(t.wrong_n + t.wrong_rh + t.wrong_rl, 0);
    double rh, rl, eh, el;
    int n = reduce_any(below, &rh, &rl);
    int ne = reduce(below, &eh, &el);
    EXPECT_EQ(n, ne);
    EXPECT_EQ(rh, eh);
    EXPECT_LE(std::fabs(rl - el), 0x1p-79 * std::fabs(eh));
  }
  double above = 0x1p20;
  for (int i = 0; i < 64; i++) {
    double rh, rl, eh, el;
    int n = reduce_any(above, &rh, &rl);
    int ne = reduce(above, &eh, &el);
    EXPECT_EQ(n, ne);
    EXPECT_EQ(rh, eh);
    EXPECT_EQ(rl, el);  // the exact reduction itself: identical, not close
    above = std::nextafter(above, 1e30);
  }
}

TEST(TrigReduce, EdgesAgree) {
  // The doubles either side of pi/4 (the quotient is 0 or 1 there) and the
  // doubles at k*pi/2 for small k (remainders near 1e-16, above the floor).
  Tally t;
  double x = GMATH_PIO4;
  for (int i = 0; i < 200; i++) {
    x = std::nextafter(x, 2.0);
    Compare(x, &t);
  }
  Expect(t, "just above pi/4", 1.0);
  Tally u;
  for (double y : {1.5707963267948966, 3.141592653589793, 4.71238898038469, 6.283185307179586}) {
    Compare(y, &u);
    Compare(std::nextafter(y, 0.0), &u);
    Compare(std::nextafter(y, 10.0), &u);
  }
  Expect(u, "k*pi/2 for k = 1..4", 0.0);
}

TEST(TrigReduce, DeclinesUnderTheFloorAndTheExactReductionTakesOver) {
  // 0x1.6c6cbc45dc8dep+5 and its doublings are the doubles below 2^20 closest
  // to a multiple of pi/2 (remainders 2^-60.5, 2^-59.5, ...); the fast path
  // owes them to the exact reduction up to 2^-55.5, and takes the next two.
  const struct {
    double x;
    bool declined;
  } cases[] = {
      {0x1.6c6cbc45dc8dep+5, true}, {0x1.6c6cbc45dc8dep+6, true},
      {0x1.6c6cbc45dc8dep+7, true}, {0x1.6c6cbc45dc8dep+8, true},
      {0x1.6c6cbc45dc8dep+9, true}, {0x1.6c6cbc45dc8dep+10, true},
      {0x1.6c6cbc45dc8dep+11, false}, {0x1.6c6cbc45dc8dep+12, false},
  };
  for (const auto & c : cases) {
    double fh, fl, eh, el, ah, al;
    int nf = reduce_fast(c.x, &fh, &fl);
    EXPECT_EQ(nf < 0, c.declined) << std::hexfloat << c.x;
    int ne = reduce(c.x, &eh, &el);
    int na = reduce_any(c.x, &ah, &al);
    EXPECT_EQ(na, ne);
    EXPECT_EQ(ah, eh);
    if (c.declined) {
      EXPECT_EQ(al, el);  // the exact reduction itself
    } else {
      EXPECT_LE(std::fabs(al - el), 0x1p-79 * std::fabs(eh));
    }
  }
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
