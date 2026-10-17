/**
 * @file
 *
 * The table-driven kernel of src/elementary/trig.c against an independent
 * double-double Taylor series.
 *
 * The oracle corpus (test_trig.cpp) says the results are right at the inputs it
 * holds; this says the table is: every row, in every column that can move a
 * result, against a series evaluated here in double-double (about 2^-100)
 * from nothing but + - * /; that the row index is in range for every argument
 * the kernel can see; that each row is taken (the kernel is accurate at the
 * start, the middle and the end of every slice, and on both sides of the
 * 2^-4 where the table ends and the direct polynomial starts); and that the
 * direct path is accurate at every binade.
 *
 * What it cannot see, and why, is in tools/check-planted.py: a one-ulp change
 * of a table entry that is itself only a rounding correction (a "lo" column,
 * d0, e0) or of a high-order tail coefficient moves no result by more than
 * 2^-90 of itself.
 *
 * trig.c is included here under other names for its three public functions
 * (the library's own are linked in as well) so that its static kernel and
 * table are reachable.
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

// A double-double, value hi + lo.  The operations are only as good as this
// test needs (about 2^-100 relative), built from the error-free
// transformations of trig.c.
struct DD {
  double hi;
  double lo;
};

DD Norm(double hi, double lo) {
  gmath_dd r = fast_two_sum(hi, lo);
  return {r.hi, r.lo};
}

DD Neg(DD a) { return {-a.hi, -a.lo}; }

DD Add(DD a, DD b) {
  gmath_dd s = two_sum(a.hi, b.hi);
  return Norm(s.hi, s.lo + (a.lo + b.lo));
}

DD Sub(DD a, DD b) { return Add(a, Neg(b)); }

DD Mul(DD a, DD b) {
  gmath_dd p = two_prod(a.hi, b.hi);
  return Norm(p.hi, p.lo + (a.hi * b.lo + a.lo * b.hi));
}

DD DivInt(DD a, double d) {
  double q1 = a.hi / d;
  gmath_dd p = two_prod(q1, d);
  double rem = ((a.hi - p.hi) - p.lo) + a.lo;
  return Norm(q1, rem / d);
}

DD Div(DD a, DD b) {
  double q1 = a.hi / b.hi;
  DD r = Sub(a, Mul(DD{q1, 0.0}, b));
  double q2 = r.hi / b.hi;
  r = Sub(r, Mul(DD{q2, 0.0}, b));
  double q3 = r.hi / b.hi;
  return Add(Norm(q1, q2), DD{q3, 0.0});
}

// sin x and cos x for |x| < 1, by their Taylor series: the last term kept is
// below 1e-37.
void SinCos(DD x, DD * s, DD * c) {
  DD x2 = Mul(x, x);
  DD ts = x, tc = {1.0, 0.0};
  DD ss = x, cs = tc;
  for (int k = 1; k <= 16; k++) {
    ts = Neg(DivInt(Mul(ts, x2), (2.0 * k) * (2.0 * k + 1.0)));
    tc = Neg(DivInt(Mul(tc, x2), (2.0 * k - 1.0) * (2.0 * k)));
    ss = Add(ss, ts);
    cs = Add(cs, tc);
  }
  *s = ss;
  *c = cs;
}

// |y - ref| in units of ulp(ref).
double UlpErr(double y, DD ref) {
  int e;
  std::frexp(ref.hi, &e);
  double u = std::ldexp(1.0, (e - 1 < -1022 ? -1022 : e - 1) - 52);
  return std::fabs(((y - ref.hi) - ref.lo) / u);
}

// The bounds are test_trig.cpp's kTightFresh: the worst measured over 4.6e8
// random arguments plus about 0.01.
constexpr double kBoundSinCos = 0.5350;
constexpr double kBoundTan = 0.5750;

struct Rng {
  uint64_t s = 0x2545f4914f6cdd1dull;
  uint64_t next() {
    s ^= s << 13;
    s ^= s >> 7;
    s ^= s << 17;
    return s;
  }
  double unit() { return static_cast<double>(next() >> 11) * 0x1p-53; }
};

// The a of row k (0 <= k < 256), exactly.
double RowA(int k) { return std::ldexp(1.0 + (k % 64) / 64.0, -4 + k / 64); }

// Row k of the table as a pointer into it.
int RowIndex(const double * row) {
  return static_cast<int>((row - &gmath_trig_rows[0][0]) / 8);
}

// The kernel's four results at h + l against the series, with the bound of the
// function; fails with the argument.
void CheckKernels(double h, double l, const char * what, double * worst_sc, double * worst_tan) {
  DD s, c;
  SinCos(DD{h, l}, &s, &c);
  DD t = Div(s, c);
  DD k = Div(c, s);
  struct {
    const char * name;
    double y;
    DD ref;
    double bound;
  } cases[] = {
      {"kernel_sin", kernel_sin(h, l), s, kBoundSinCos},
      {"kernel_cos", kernel_cos(h, l), c, kBoundSinCos},
      {"kernel_tan", kernel_tan(h, l, 0), t, kBoundTan},
      {"kernel_cot", kernel_tan(h, l, 1), k, kBoundTan},
  };
  for (const auto & cs : cases) {
    double err = UlpErr(cs.y, cs.ref);
    double * worst = cs.bound == kBoundTan ? worst_tan : worst_sc;
    if (err > *worst) {
      *worst = err;
    }
    EXPECT_LE(err, cs.bound) << what << ": " << cs.name << "(" << std::hexfloat << h << " + " << l << ")";
  }
}

}  // namespace

TEST(TrigKernel, TableRowsMatchAnIndependentSeries) {
  for (int k = 0; k < GMATH_TRIG_ROWS; k++) {
    double a = RowA(k);
    DD s, c;
    SinCos(DD{a, 0.0}, &s, &c);
    DD t = Div(s, c);
    DD kt = Div(c, s);
    const double * r = gmath_trig_rows[k];
    SCOPED_TRACE(testing::Message() << "row " << k << ", a = " << std::hexfloat << a);
    // The high columns are the correctly rounded values.
    EXPECT_EQ(r[GMATH_TRIG_SIN_HI], s.hi);
    EXPECT_EQ(r[GMATH_TRIG_COS_HI], c.hi);
    EXPECT_EQ(r[GMATH_TRIG_TAN_HI], t.hi);
    EXPECT_EQ(r[GMATH_TRIG_COT_HI], kt.hi);
    // The low columns are the rest of a double-double, to 2^-100 of the value.
    EXPECT_LE(std::fabs(r[GMATH_TRIG_SIN_LO] - s.lo), 0x1p-100 * std::fabs(s.hi));
    EXPECT_LE(std::fabs(r[GMATH_TRIG_COS_LO] - c.lo), 0x1p-100 * std::fabs(c.hi));
    // d0 = sin_hi - tan_hi * cos_hi and e0 = cos_hi - cot_hi * sin_hi, exactly
    // (the three factors are doubles), rounded once.
    gmath_dd p = two_prod(r[GMATH_TRIG_TAN_HI], r[GMATH_TRIG_COS_HI]);
    gmath_dd d0 = two_sum(r[GMATH_TRIG_SIN_HI] - p.hi, -p.lo);
    EXPECT_EQ(r[GMATH_TRIG_TAN_D0], d0.hi);
    gmath_dd q = two_prod(r[GMATH_TRIG_COT_HI], r[GMATH_TRIG_SIN_HI]);
    gmath_dd e0 = two_sum(r[GMATH_TRIG_COS_HI] - q.hi, -q.lo);
    EXPECT_EQ(r[GMATH_TRIG_COT_E0], e0.hi);
  }
  // The row for a = 0.
  const double * z = gmath_trig_rows[GMATH_TRIG_ZERO_ROW];
  EXPECT_EQ(z[GMATH_TRIG_SIN_HI], 0.0);
  EXPECT_EQ(z[GMATH_TRIG_SIN_LO], 0.0);
  EXPECT_EQ(z[GMATH_TRIG_COS_HI], 1.0);
  EXPECT_EQ(z[GMATH_TRIG_COS_LO], 0.0);
  EXPECT_EQ(z[GMATH_TRIG_TAN_HI], 0.0);
  EXPECT_EQ(z[GMATH_TRIG_TAN_D0], 0.0);
  EXPECT_EQ(z[GMATH_TRIG_COT_HI], 0.0);
  EXPECT_EQ(z[GMATH_TRIG_COT_E0], 0.0);
}

TEST(TrigKernel, EachRowIsOneCacheLine) {
  // The layout a vector kernel loads from: 64-byte rows, 64-byte aligned.
  EXPECT_EQ(sizeof gmath_trig_rows[0], 64u);
  EXPECT_EQ(reinterpret_cast<uintptr_t>(&gmath_trig_rows[0][0]) % 64, 0u);
}

TEST(TrigKernel, TheRowIndexIsInRangeForEveryReducedArgument) {
  // kernel_front's index for each a, for the double just below the next a, for
  // 2^-4 and below it, and for the largest h the kernel sees, the double
  // nearest pi/4; and for the largest double below 1, an upper bound on that.
  for (int k = 0; k < GMATH_TRIG_ROWS; k++) {
    double a = RowA(k);
    double b;
    const double * row = kernel_front(a, &b);
    EXPECT_EQ(RowIndex(row), k) << std::hexfloat << a;
    EXPECT_EQ(b, 0.0);
    double below = std::nextafter(k + 1 < 256 ? RowA(k + 1) : 1.0, 0.0);
    row = kernel_front(below, &b);
    EXPECT_EQ(RowIndex(row), k) << std::hexfloat << below;
    EXPECT_GT(b, 0.0);
    EXPECT_LT(b, std::ldexp(1.0, -4 + k / 64) / 64.0);  // the slice's width
  }
  double b;
  EXPECT_EQ(RowIndex(kernel_front(GMATH_PIO4, &b)), 228);
  EXPECT_EQ(RowIndex(kernel_front(std::nextafter(1.0, 0.0), &b)), 255);
  EXPECT_EQ(RowIndex(kernel_front(0x1p-4, &b)), 0);
  EXPECT_EQ(RowIndex(kernel_front(std::nextafter(0x1p-4, 0.0), &b)), GMATH_TRIG_ZERO_ROW);
  EXPECT_EQ(RowIndex(kernel_front(0x1p-28, &b)), GMATH_TRIG_ZERO_ROW);
  EXPECT_EQ(b, 0x1p-28);
  // The mask: an h that no reduction returns still reads a row of the table.
  for (double h : {1.0, 1.5, 2.0, 100.0, 0x1p20, 1e300, 0x1.fffffffffffffp1023}) {
    int idx = RowIndex(kernel_front(h, &b));
    EXPECT_GE(idx, 0) << h;
    EXPECT_LT(idx, GMATH_TRIG_ROWS) << h;
  }
  // No argument the reductions return is above the double pi/4 (reduce_any's
  // contract, tested in test_trig_reduce.cpp; the exact reduction rounds a value
  // below pi/4 to at most it), and that double is in row 228, below row 229.
  EXPECT_LT(GMATH_PIO4, RowA(229));
  EXPECT_GE(GMATH_PIO4, RowA(228));
}

TEST(TrigKernel, EveryRowIsTakenAndAccurate) {
  // The start, the end and two interior points of every slice, as an exact
  // reduced argument and with a nonzero tail l (the reduction's rl), on all four
  // kernels.  Rows 229 and above are not reachable by any argument (a > pi/4)
  // but are the same formulas and are checked as well.
  Rng r;
  double worst_sc = 0, worst_tan = 0;
  for (int k = 0; k < GMATH_TRIG_ROWS; k++) {
    double a = RowA(k);
    double next = k + 1 < 256 ? RowA(k + 1) : 1.0;
    double pts[4] = {a, std::nextafter(next, 0.0), a + (next - a) * r.unit(), a + (next - a) * r.unit()};
    for (double h : pts) {
      CheckKernels(h, 0.0, "exact", &worst_sc, &worst_tan);
      double l = (r.unit() - 0.5) * 0x1p-52 * h;
      CheckKernels(h, l, "with a tail", &worst_sc, &worst_tan);
    }
  }
  std::printf("  all rows: worst sin/cos %.4f ulp, tan/cot %.4f ulp\n", worst_sc, worst_tan);
}

TEST(TrigKernel, TheDirectPathIsAccurateAtEveryBinade) {
  Rng r;
  double worst_sc = 0, worst_tan = 0;
  for (int e = -28; e < -4; e++) {
    for (int i = 0; i < 400; i++) {
      double h = std::ldexp(1.0 + r.unit(), e);
      double l = (r.unit() - 0.5) * 0x1p-52 * h;
      CheckKernels(h, i % 2 ? l : 0.0, "direct", &worst_sc, &worst_tan);
    }
  }
  // Either side of the boundary with the table.
  double lo = 0x1p-4, hi = 0x1p-4;
  for (int i = 0; i < 64; i++) {
    lo = std::nextafter(lo, 0.0);
    hi = std::nextafter(hi, 1.0);
    CheckKernels(lo, 0.0, "just below 2^-4", &worst_sc, &worst_tan);
    CheckKernels(hi, 0.0, "just above 2^-4", &worst_sc, &worst_tan);
  }
  CheckKernels(0x1p-4, 0.0, "2^-4", &worst_sc, &worst_tan);
  std::printf("  direct path and boundary: worst sin/cos %.4f ulp, tan/cot %.4f ulp\n", worst_sc, worst_tan);
}

TEST(TrigKernel, PublicFunctionsTakeTheTableAtEveryReachableRow) {
  // Through gmath_sin/cos/tan themselves: an unreduced argument on each of the
  // 229 rows a reduced argument can reach.
  Rng r;
  for (int k = 0; k < 229; k++) {
    double a = RowA(k);
    double next = RowA(k + 1);
    for (double x : {a, a + (next - a) * r.unit(), std::nextafter(next < GMATH_PIO4 ? next : GMATH_PIO4, 0.0)}) {
      DD s, c;
      SinCos(DD{x, 0.0}, &s, &c);
      EXPECT_LE(UlpErr(test_copy_of_gmath_sin(x), s), kBoundSinCos) << std::hexfloat << x;
      EXPECT_LE(UlpErr(test_copy_of_gmath_cos(x), c), kBoundSinCos) << std::hexfloat << x;
      EXPECT_LE(UlpErr(test_copy_of_gmath_tan(x), Div(s, c)), kBoundTan) << std::hexfloat << x;
    }
  }
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
