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

// Compare the fast reduction with the exact one at x (pi/4 < x < 2^30): the
// four-part one below 2^20 and the wide one from there.
void Compare(double x, Tally * t) {
  double fh, fl, eh, el;
  t->tried++;
  int nf = x < 0x1p20 ? reduce_fast(x, &fh, &fl) : reduce_fast_wide(x, &fh, &fl);
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

TEST(TrigReduce, TheLimitsAreExclusiveAndBothSidesAgree) {
  // Just below 2^20 the four-part path may run, from 2^20 the wide one; at
  // and above 2^30 only the exact one runs, and the dispatcher gives the same
  // quadrant whichever it is.
  for (double limit : {0x1p20, 0x1p30}) {
    double below = limit;
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
  }
  // 2^20 and above, until 2^30: the wide path, close to the exact one.
  double mid = 0x1p20;
  for (int i = 0; i < 64; i++) {
    double rh, rl, eh, el;
    int n = reduce_any(mid, &rh, &rl);
    int ne = reduce(mid, &eh, &el);
    EXPECT_EQ(n, ne);
    EXPECT_EQ(rh, eh);
    EXPECT_LE(std::fabs(rl - el), 0x1p-79 * std::fabs(eh));
    mid = std::nextafter(mid, 1e30);
  }
  double above = 0x1p30;
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

TEST(TrigReduce, WideUniformAgreesAndIsTaken) {
  Rng r;
  Tally t;
  for (int i = 0; i < 400000; i++) {
    double x = 0x1p20 + r.unit() * (0x1p30 - 0x1p20);
    if (x >= 0x1p20 && x < 0x1p30) Compare(x, &t);
  }
  Expect(t, "uniform in [2^20, 2^30)", 1e-4);
}

TEST(TrigReduce, WideEveryBinadeAgreesAndIsTaken) {
  Rng r;
  Tally t;
  for (int i = 0; i < 400000; i++) {
    int e = 20 + static_cast<int>(r.next() % 10);  // 2^20 .. 2^29
    double x = std::ldexp(1.0 + r.unit(), e);
    if (x >= 0x1p20 && x < 0x1p30) Compare(x, &t);
  }
  Expect(t, "wide, every binade", 1e-4);
}

TEST(TrigReduce, WideNearMultiplesOfPiOver2Agree) {
  // The doubles around k*pi/2 for k up to the top of the range (n < 2^29.35),
  // k*pi/2 formed from the double-double pi/2 so that it is within an ulp of
  // the true multiple: remainders of the size of ulp(x), 2^-23 down, and the
  // cancellation that goes with them.  (The worst cases, down to 2^-59, are in
  // the next test.)
  Rng r;
  Tally t;
  for (int i = 0; i < 300000; i++) {
    double k = static_cast<double>(667544 + r.next() % (683565275 - 667544));
    gmath_dd p = two_prod(k, GMATH_PIO2_HI);
    double x = p.hi + (p.lo + k * GMATH_PIO2_LO);
    double u = std::ldexp(1.0, std::ilogb(x) - 52);
    int sh = static_cast<int>(r.next() % 8);
    double off = static_cast<double>(static_cast<int64_t>(r.next() % 2001) - 1000) * u * std::ldexp(1.0, sh);
    x += off;
    if (x >= 0x1p20 && x < 0x1p30) Compare(x, &t);
  }
  Expect(t, "wide, near k*pi/2", 0.01);
}

TEST(TrigReduce, WideWorstCasesAboveTheFloorAgree) {
  // The doubles of [2^20, 2^30) closest to a multiple of pi/2 whose remainder
  // is still above the 2^-55 floor (2^-54.1 and up): the smallest remainders
  // the wide path takes, so the largest relative error it has.
  Tally t;
  for (double x : {0x1.9eb7148f354d6p+20, 0x1.9eb7148f354d6p+21, 0x1.9eb7148f354d6p+22,
                   0x1.b951f1572eba5p+28, 0x1.b951f1572eba5p+29}) {
    Compare(x, &t);
    Compare(std::nextafter(x, 0.0), &t);
    Compare(std::nextafter(x, 1e30), &t);
  }
  Expect(t, "wide, worst cases above the floor", 0.0);
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

TEST(TrigReduce, WideDeclinesUnderTheFloorAndTheExactReductionTakesOver) {
  // 0x1.b951f1572eba5p+23 and its doublings are the doubles in [2^20, 2^30)
  // closest to a multiple of pi/2 (remainders 2^-59.03, 2^-58.03, ...); the
  // wide path owes the first five to the exact reduction (under 2^-55) and
  // takes the last two.
  const struct {
    double x;
    bool declined;
  } cases[] = {
      {0x1.b951f1572eba5p+23, true}, {0x1.b951f1572eba5p+24, true},
      {0x1.b951f1572eba5p+25, true}, {0x1.b951f1572eba5p+26, true},
      {0x1.b951f1572eba5p+27, true}, {0x1.b951f1572eba5p+28, false},
      {0x1.b951f1572eba5p+29, false},
  };
  for (const auto & c : cases) {
    double fh, fl, eh, el, ah, al;
    int nf = reduce_fast_wide(c.x, &fh, &fl);
    EXPECT_EQ(nf < 0, c.declined) << std::hexfloat << c.x;
    int ne = reduce(c.x, &eh, &el);
    int na = reduce_any(c.x, &ah, &al);
    EXPECT_EQ(na, ne);
    EXPECT_EQ(ah, eh);
    if (c.declined) {
      EXPECT_EQ(al, el);
    } else {
      EXPECT_LE(std::fabs(al - el), 0x1p-79 * std::fabs(eh));
    }
  }
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
