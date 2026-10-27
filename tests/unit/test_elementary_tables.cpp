/**
 * @file
 *
 * The tables and polynomials of src/elementary/explog.c, atan2.c and hypot.c
 * against independent double-double series.
 *
 * The oracle corpus (test_elementary.cpp) says the results are right at the
 * inputs it holds; this says the tables are: every row of the exp table, the
 * log rows, the arctangent rows and the reciprocal square root start, against
 * series evaluated here in double-double (about 2^-100) from nothing but
 * + - * /, and the polynomials against the same series over their whole range.
 * The constants this test spells out (ln2) are the mathematical values, not
 * copies of the generated headers.
 *
 * What it cannot see, and why, is in tools/check-planted-elem.py: a one-ulp
 * change of a table entry that is itself only a rounding correction (a "lo"
 * column) or of a high-order polynomial coefficient moves no result by more
 * than 2^-80 of itself.
 *
 * The three .c files are included here under other names for their public
 * functions (the library's own are linked in as well) so that their static
 * tables and helpers are reachable.
 *
 * Copyright 2026 by Corey Pennycuff
 */

#include "test_helpers.h"

#include <ghoti.io/math/elementary.h>

#undef gmath_exp
#undef gmath_expf
#undef gmath_exp2
#undef gmath_log
#undef gmath_logf
#undef gmath_log2
#undef gmath_log10
#undef gmath_log2f
#undef gmath_pow
#undef gmath_atan2
#undef gmath_hypot
#define gmath_exp test_copy_of_gmath_exp
#define gmath_expf test_copy_of_gmath_expf
#undef gmath_exp2f
#define gmath_exp2f test_copy_of_gmath_exp2f
#define gmath_exp2 test_copy_of_gmath_exp2
#define gmath_log test_copy_of_gmath_log
#define gmath_logf test_copy_of_gmath_logf
#define gmath_log2 test_copy_of_gmath_log2
#define gmath_log10 test_copy_of_gmath_log10
#define gmath_log2f test_copy_of_gmath_log2f
#define gmath_pow test_copy_of_gmath_pow
#define gmath_atan2 test_copy_of_gmath_atan2
#define gmath_hypot test_copy_of_gmath_hypot

#include "../../src/elementary/atan2.c"
#include "../../src/elementary/explog.c"
#include "../../src/elementary/hypot.c"

#include <cmath>
#include <cstdint>
#include <cstdio>

namespace {

// A double-double, value hi + lo, about 2^-100 relative.
struct DD {
  double hi;
  double lo;
};

DD Norm(double hi, double lo) {
  gmath_pair r = gmath_fast_two_sum(hi, lo);
  return {r.hi, r.lo};
}

DD Neg(DD a) { return {-a.hi, -a.lo}; }

DD Add(DD a, DD b) {
  gmath_pair s = gmath_two_sum(a.hi, b.hi);
  return Norm(s.hi, s.lo + (a.lo + b.lo));
}

DD Sub(DD a, DD b) { return Add(a, Neg(b)); }

DD Mul(DD a, DD b) {
  gmath_pair p = gmath_two_prod(a.hi, b.hi);
  return Norm(p.hi, p.lo + (a.hi * b.lo + a.lo * b.hi));
}

DD MulD(DD a, double d) { return Mul(a, DD{d, 0.0}); }

DD Div(DD a, DD b) {
  double q1 = a.hi / b.hi;
  DD r = Sub(a, MulD(b, q1));
  double q2 = r.hi / b.hi;
  r = Sub(r, MulD(b, q2));
  double q3 = r.hi / b.hi;
  return Add(Norm(q1, q2), DD{q3, 0.0});
}

DD DivInt(DD a, double d) { return Div(a, DD{d, 0.0}); }

// |a - b| / |b| as a double.
double RelDiff(DD a, DD b) {
  DD d = Sub(a, b);
  return std::fabs((d.hi + d.lo) / b.hi);
}

const DD kLn2 = {0x1.62e42fefa39efp-1, 0x1.abc9e3b39803fp-56};

// exp(r) for |r| <= 1, by the Taylor series.
DD ExpSeries(DD r) {
  DD term = {1.0, 0.0};
  DD sum = {1.0, 0.0};
  for (int k = 1; k < 40; k++) {
    term = DivInt(Mul(term, r), static_cast<double>(k));
    sum = Add(sum, term);
    if (std::fabs(term.hi) < 1e-40) {
      break;
    }
  }
  return sum;
}

// log(c) for c in [0.5, 2]: 2 atanh((c - 1)/(c + 1)).
DD LogSeries(DD c) {
  DD s = Div(Sub(c, DD{1.0, 0.0}), Add(c, DD{1.0, 0.0}));
  DD s2 = Mul(s, s);
  DD term = s;
  DD sum = s;
  for (int k = 1; k < 60; k++) {
    term = Mul(term, s2);
    sum = Add(sum, DivInt(term, 2.0 * k + 1.0));
    if (std::fabs(term.hi) < 1e-40) {
      break;
    }
  }
  return Add(sum, sum);
}

// atan(x) for x in [0, 1]: sum over n of (2^(2n) (n!)^2 / (2n + 1)!) x^(2n+1) / (1 + x^2)^(n+1),
// the Euler series, whose terms fall by at least a half each.
DD AtanSeries(DD x) {
  DD one = {1.0, 0.0};
  DD y = Div(Mul(x, x), Add(one, Mul(x, x)));  // x^2 / (1 + x^2)
  DD term = Div(x, Add(one, Mul(x, x)));
  DD sum = term;
  for (int n = 0; n < 200; n++) {
    term = Mul(term, y);
    term = DivInt(MulD(term, 2.0 * n + 2.0), 2.0 * n + 3.0);
    sum = Add(sum, term);
    if (std::fabs(term.hi) < 1e-40) {
      break;
    }
  }
  return sum;
}

const double kTol = 0x1p-100;

}  // namespace

TEST(ElementaryTables, ConstantsAreTheirDefinitions) {
  // ln2 = LN2_HI + LN2_LO, LN2_HI of 41 bits (e * LN2_HI exact for |e| < 2^12).
  EXPECT_EQ(gmath_bits(GMATH_LN2_HI) & ((1ull << (52 - 40)) - 1), 0u);
  EXPECT_LT(RelDiff(Add(DD{GMATH_LN2_HI, 0.0}, DD{GMATH_LN2_LO, 0.0}), kLn2), 0x1p-100);
  // ln2/128 = L1 + L2, L1 of 30 bits (n L1 exact for |n| < 2^23).
  EXPECT_EQ(gmath_bits(GMATH_EXP_L1) & ((1ull << (52 - 29)) - 1), 0u);
  DD l = Add(DD{GMATH_EXP_L1, 0.0}, DD{GMATH_EXP_L2, 0.0});
  DD want = MulD(kLn2, 0x1p-7);
  EXPECT_LT(RelDiff(l, want), 0x1p-80);  // L2 is one double: 2^-83
  // 128/ln2 to a unit in the last place.
  DD inv = Div(DD{128.0, 0.0}, kLn2);
  EXPECT_LT(RelDiff(DD{GMATH_EXP_INV_LN2_N, 0.0}, inv), 0x1p-53);
  // The magic number, and the thresholds the code states.
  EXPECT_EQ(GMATH_EXP_MAGIC, 0x1.8p52);
  EXPECT_GT(GMATH_EXP_CERTAIN_OVER, 709.782712893384);
  EXPECT_LT(GMATH_EXP_CERTAIN_UNDER, -745.1332191019412);
}

TEST(ElementaryTables, ExpTableMatchesTwoToTheJOver128) {
  for (int j = 0; j < 128; j++) {
    DD r = MulD(kLn2, j * 0x1p-7);
    DD v = ExpSeries(r);  // 2^(j/128)
    double hi = gmath_exp_tab[2 * j];
    double lo = gmath_exp_tab[2 * j + 1];
    EXPECT_EQ(hi, v.hi) << "row " << j << ": the high part is not the correctly rounded value";
    DD d = Sub(v, DD{hi, 0.0});
    EXPECT_LT(std::fabs((d.hi + d.lo) - lo), kTol) << "row " << j << ": the low part";
  }
}

TEST(ElementaryTables, ExpPolynomialOverTheReducedRange) {
  // exp r - 1 = r + r^2 P(r) as exp_core evaluates it, over |r| <= ln2/256 and a little beyond.
  const double rmax = 0x1.62e42fefa39efp-9 * 1.003;
  const double* c = gmath_exp_poly;
  double worst = 0.0;
  for (int i = -2000; i <= 2000; i++) {
    double r = rmax * i / 2000.0;
    double r2 = r * r;
    double p = r + r2 * ((c[0] + c[1] * r) + (c[2] + c[3] * r) * r2);
    DD e = Sub(ExpSeries(DD{r, 0.0}), DD{1.0, 0.0});
    double err = std::fabs(p - (e.hi + e.lo));
    if (err > worst) {
      worst = err;
    }
  }
  std::printf("  exp polynomial: worst absolute error %.3g (2^%.1f)\n", worst, std::log2(worst));
  EXPECT_LT(worst, 0x1p-60);
}

TEST(ElementaryTables, LogRowsAreMinusLogOfTheirMultiplier) {
  int ones = 0;
  for (int j = 0; j < 128; j++) {
    const double* row = gmath_log_rows[j];
    double c = row[0];
    // c has 26 significant bits: m_hi (27 bits) times c is an exact product.
    EXPECT_EQ(gmath_bits(c) & GMATH_LOG_LOW_MASK, 0u) << "row " << j << ": c has more than 26 bits";
    // the row's interval of m: c m - 1 is small on it
    double lo = gmath_double(GMATH_LOG_OFF + (static_cast<uint64_t>(j) << 45));
    double hi = gmath_double(GMATH_LOG_OFF + (static_cast<uint64_t>(j + 1) << 45));
    double zlo = lo * c - 1.0, zhi = hi * c - 1.0;
    if (c == 1.0) {
      ones++;
      EXPECT_EQ(row[1], 0.0) << "row " << j;
      EXPECT_EQ(row[2], 0.0) << "row " << j;
      EXPECT_TRUE(lo == 1.0 || hi == 1.0) << "row " << j << " has c = 1 and does not touch 1.0";
    } else {
      EXPECT_LT(std::fabs(zlo), 0x1p-7) << "row " << j;
      EXPECT_LT(std::fabs(zhi), 0x1p-7) << "row " << j;
      // log m = -log c + log1p z: the table holds -log c
      DD t = Neg(LogSeries(DD{c, 0.0}));
      // t_hi is a multiple of 2^-41 (e ln2_hi + t_hi is exact)
      EXPECT_EQ(row[1], std::ldexp(std::nearbyint(std::ldexp(row[1], 41)), -41)) << "row " << j;
      DD d = Sub(t, DD{row[1], 0.0});
      EXPECT_LT(std::fabs((d.hi + d.lo) - row[2]), kTol) << "row " << j << ": t_lo";
      EXPECT_LT(std::fabs(row[1] - t.hi), 0x1p-41) << "row " << j << ": t_hi is not the nearest multiple";
    }
    EXPECT_EQ(row[3], 0.0) << "row " << j;
  }
  EXPECT_EQ(ones, 2);
  EXPECT_EQ(gmath_log_rows[GMATH_LOG_ONE_ROW_LO][0], 1.0);
  EXPECT_EQ(gmath_log_rows[GMATH_LOG_ONE_ROW_HI][0], 1.0);
  EXPECT_EQ(gmath_double(GMATH_LOG_OFF + (static_cast<uint64_t>(GMATH_LOG_ONE_ROW_HI) << 45)), 1.0);
}

TEST(ElementaryTables, LogPolynomialsOverTheirRange) {
  // log1p z = z + z^2 P(z) (log), and z - z^2/2 + z^3 R(z) (pow), -2^-8 <= z <= 2^-7.
  const double* p = gmath_log_poly;
  const double* r = gmath_log_dd_poly;
  double worst = 0.0, worst_dd = 0.0;
  for (int i = -1000; i <= 1000; i++) {
    double z = (i < 0 ? 0x1p-8 : 0x1p-7) * 1.01 * i / 1000.0;
    if (z == 0.0) {
      continue;
    }
    DD one_z = Add(DD{1.0, 0.0}, DD{z, 0.0});
    DD lg = LogSeries(one_z);
    double z2 = z * z, z4 = z2 * z2;
    double q = z2 * (((p[0] + p[1] * z) + (p[2] + p[3] * z) * z2) + (p[4] + p[5] * z) * z4);
    // relative to z: the polynomial of log is accurate relative to z
    DD qwant = Sub(lg, DD{z, 0.0});
    double e1 = std::fabs(q - (qwant.hi + qwant.lo)) / std::fabs(z);
    worst = std::fmax(worst, e1);
    double poly = ((r[0] + r[1] * z) + (r[2] + r[3] * z) * z2) + ((r[4] + r[5] * z) + r[6] * z2) * z4;
    double t = (z * z2) * poly;
    // log1p z - z + z^2/2 against z^3 R(z), relative to z (the part that is double)
    DD zz = Mul(DD{z, 0.0}, DD{z, 0.0});
    DD rest = Add(Sub(lg, DD{z, 0.0}), DD{0.5 * zz.hi, 0.5 * zz.lo});
    double e2 = std::fabs(t - (rest.hi + rest.lo)) / std::fabs(z);
    worst_dd = std::fmax(worst_dd, e2);
  }
  std::printf("  log polynomial: worst error relative to z 2^%.1f; pow's cubic term: 2^%.1f\n", std::log2(worst),
      std::log2(worst_dd));
  EXPECT_LT(worst, 0x1p-58);
  EXPECT_LT(worst_dd, 0x1p-66);
}

TEST(ElementaryTables, Log2FloatKernelHasSubUlpReserve) {
  double worst = 0.0;
  for (unsigned j = 0; j < 128; ++j) {
    double lo = gmath_double(GMATH_LOG_OFF + (static_cast<uint64_t>(j) << 45));
    double hi = gmath_double(GMATH_LOG_OFF + (static_cast<uint64_t>(j + 1) << 45));
    const double * row = gmath_log_rows[j];
    EXPECT_LT(std::fabs(lo * row[0] - 1.0), 0.008);
    EXPECT_LT(std::fabs(hi * row[0] - 1.0), 0.008);
    EXPECT_LT(std::fabs(row[1]) + std::fabs(row[2]), 0.36);
    bool one = row[0] == 1.0;
    if (!one) {
      EXPECT_TRUE(hi <= 1.0 - 0x1p-8 || lo >= 1.0 + 0x1p-7);
    }
    for (int i = 0; i <= 32; ++i) {
      float m = static_cast<float>(lo + (hi - lo) * (i / 32.0));
      if (static_cast<double>(m) >= hi) {
        m = std::nextafter(static_cast<float>(hi), 0.0f);
      }
      DD lm = Div(LogSeries(DD{static_cast<double>(m), 0.0}), kLn2);
      for (int scale : {-125, -10, 0, 10, 127}) {
        double x = std::ldexp(static_cast<double>(m), scale);
        ASSERT_EQ(x, static_cast<double>(static_cast<float>(x)));
        DD reference = Add(DD{static_cast<double>(scale), 0.0}, lm);
        double got = log2f_positive(x);
        if (reference.hi == 0.0) {
          EXPECT_EQ(got, 0.0);
          continue;
        }
        int exponent;
        std::frexp(reference.hi, &exponent);
        double unit = std::ldexp(1.0, exponent - 24);
        DD difference = Sub(DD{got, 0.0}, reference);
        double error = std::fabs(difference.hi + difference.lo) / unit;
        worst = std::fmax(worst, error);
        EXPECT_LT(error, 0.01) << "row " << j << " scale " << scale;
      }
    }
  }
  std::printf("  float log2: pre-round error below %.6g binary32 ulp over every row\n", worst);
}

TEST(ElementaryTables, Atan2RowsAreTheTaylorSeriesOfArctangent) {
  EXPECT_EQ(GMATH_ATAN2_ROWS, 128);
  for (int j = 0; j < GMATH_ATAN2_ROWS; j++) {
    const double* g = gmath_atan2_rows[j];
    if (j > 64) {
      for (int k = 0; k < 2 + GMATH_ATAN2_TAYLOR; k++) {
        EXPECT_EQ(g[k], gmath_atan2_rows[64][k]) << "row " << j << " does not repeat row 64";
      }
      continue;
    }
    DD f = {j / 64.0, 0.0};
    DD at = AtanSeries(f);
    EXPECT_EQ(g[0], at.hi) << "row " << j << ": atan F hi";
    DD d = Sub(at, DD{g[0], 0.0});
    EXPECT_LT(std::fabs((d.hi + d.lo) - g[1]), kTol) << "row " << j << ": atan F lo";
    if (j < 8) {
      continue;  // never read: the direct path takes q < 1/8
    }
    // The series at F against the arctangent at F + beta, beta up to 2^-7 each way.
    double worst = 0.0;
    for (int i = -8; i <= 8; i++) {
      double beta = i * 0x1p-7 / 8.0 * 1.01;
      DD x = Add(f, DD{beta, 0.0});
      DD want = AtanSeries(x);
      double e1 = (g[2] + g[3] * beta) + (g[4] + g[5] * beta) * (beta * beta);
      double e2 = (g[6] + g[7] * beta) + (g[8] + g[9] * beta) * (beta * beta);
      double b2 = beta * beta;
      double c = g[1] + beta * (e1 + e2 * (b2 * b2));
      DD diff = Sub(Add(DD{g[0], 0.0}, DD{c, 0.0}), want);
      worst = std::fmax(worst, std::fabs((diff.hi + diff.lo) / want.hi));
    }
    EXPECT_LT(worst, 0x1p-56) << "row " << j << ": the Taylor series at F against atan(F + beta)";
  }
}

TEST(ElementaryTables, Atan2DirectPolynomialOverItsRange) {
  const double* p = gmath_atan2_poly;
  double worst = 0.0;
  for (int i = 1; i <= 2000; i++) {
    double q = 0.125 * i / 2000.0;
    double w = q * q;
    double w2 = w * w;
    double e1 = (p[0] + p[1] * w) + (p[2] + p[3] * w) * w2;
    double e2 = (p[4] + p[5] * w) + p[6] * w2;
    double poly = e1 + e2 * (w2 * w2);
    DD want = AtanSeries(DD{q, 0.0});
    DD got = Add(DD{q, 0.0}, DD{(q * w) * poly, 0.0});
    worst = std::fmax(worst, RelDiff(got, want));
  }
  std::printf("  atan polynomial: worst relative error 2^%.1f\n", std::log2(worst));
  EXPECT_LT(worst, 0x1p-59);
}

TEST(ElementaryTables, HypotReciprocalSquareRootStart) {
  for (int i = 0; i < (1 << GMATH_HYPOT_ROW_BITS); i++) {
    int p = i >> 8;  // the low bit of the biased exponent
    double j = i & 255;
    double q = p == 0 ? 2.0 : 1.0;
    double t = gmath_hypot_rsqrt[i];
    // the cell is s = q (1 + f) for f from j/256 to (j + 1)/256: t * t * s is 1 to twice 2^-9.9 across it
    for (double f : {j / 256.0, (j + 1) / 256.0, (j + 0.5) / 256.0}) {
      double s = q * (1.0 + f);
      EXPECT_LT(std::fabs(t * t * s - 1.0), std::pow(2.0, -8.9)) << "row " << i << " f " << f;
    }
  }
}

TEST(ElementaryTables, IndicesAreInRangeForEveryArgument) {
  // log: every positive normal bit pattern's row is inside the table, and m is in [0.707, 1.414)
  const uint64_t xs[] = {0x0010000000000000ull, 0x0010000000000001ull, 0x3fe6a00000000000ull, 0x3fe69fffffffffffull,
      0x3ff0000000000000ull, 0x3fefffffffffffffull, 0x3ff6a00000000000ull, 0x7fefffffffffffffull, 0x7fe0000000000000ull,
      0x3ff6a00000000001ull, 0x3ff6a0000000000full};
  for (uint64_t xb : xs) {
    int e;
    double zh, zl;
    const double* row = log_front(xb, &e, &zh, &zl);
    EXPECT_GE(row, &gmath_log_rows[0][0]) << std::hex << xb;
    EXPECT_LT(row, (&gmath_log_rows[0][0] + 128 * 4)) << std::hex << xb;
    EXPECT_LT(std::fabs(zh), 0x1p-6) << std::hex << xb;
  }
  uint64_t s = 0x9e3779b97f4a7c15ull;
  for (int i = 0; i < 200000; i++) {
    s = s * 6364136223846793005ull + 1442695040888963407ull;
    uint64_t xb = (s & 0x7fffffffffffffffull) | 0x0010000000000000ull;
    if ((xb >> 52) == 0x7ff) {
      continue;
    }
    int e;
    double zh, zl;
    const double* row = log_front(xb, &e, &zh, &zl);
    ASSERT_GE(row, &gmath_log_rows[0][0]);
    ASSERT_LT(row, (&gmath_log_rows[0][0] + 128 * 4));
    ASSERT_LT(std::fabs(zh), 0x1p-6) << std::hex << xb;
    // x = 2^e m with z the reduced argument: reconstruct and compare
    double x = gmath_double(xb);
    double m = x * std::ldexp(1.0, -e);
    EXPECT_GE(m, 0.707);
    EXPECT_LT(m, 1.4143);
    DD cm = Mul(DD{row[0], 0.0}, DD{m, 0.0});
    DD zexact = Sub(cm, DD{1.0, 0.0});
    DD zdiff = Sub(zexact, DD{zh, zl});
    EXPECT_LT(std::fabs(zdiff.hi + zdiff.lo), 0x1p-100) << std::hex << xb;
  }
  // exp: n and (j, k) agree, for every n an argument can give
  for (int n = -140000; n <= 131100; n++) {
    unsigned j = static_cast<unsigned>(n) & 127u;
    int k = n >> 7;
    ASSERT_EQ(k * 128 + static_cast<int>(j), n);
    ASSERT_LT(j, 128u);
  }
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
