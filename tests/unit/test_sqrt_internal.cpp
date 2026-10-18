/**
 * @file
 *
 * The parts of the portable square root (src/elementary/sqrt_impl.h) that a
 * result cannot show on its own: the estimate and the exact correction after
 * it.  The correction has to repair an estimate that is one unit in the last
 * place too low or too high, and the estimate in practice only falls short, so
 * the branch that lowers it and the equality cases are not
 * reached by any argument of gmath_sqrt.  They are reached here by handing
 * gmath_sqrt_correct an estimate that is wrong in each direction, for random
 * m in [1, 4), for exact squares and for the arguments at which the residual
 * equals y u exactly.
 *
 * sqrt_impl.h is included directly (it has only static functions).
 *
 * Copyright 2026 by Corey Pennycuff
 */

#include "test_helpers.h"

#include "../../src/elementary/sqrt_impl.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace {

double DoubleOf(uint64_t u) {
  double d;
  std::memcpy(&d, &u, sizeof d);
  return d;
}

uint64_t BitsOf(double d) {
  uint64_t u;
  std::memcpy(&u, &d, sizeof u);
  return u;
}

__extension__ typedef unsigned __int128 u128;

// The correctly rounded square root of m in [1, 4), by the integer square root of its significand with a remainder.
double RefSqrt(double m) {
  uint64_t b = BitsOf(m);
  uint64_t sig = (b & 0xfffffffffffffull) | (1ull << 52);
  int e = static_cast<int>((b >> 52) - 1023);  // 0 or 1
  u128 N = static_cast<u128>(sig) << (58 + e);  // value m = sig 2^(e-52); sqrt(sig 2^e 2^58) = sqrt(m) 2^55
  u128 rem = N, res = 0, bit = static_cast<u128>(1) << 126;
  while (bit > N) {
    bit >>= 2;
  }
  while (bit) {
    if (rem >= res + bit) {
      rem -= res + bit;
      res = (res >> 1) + bit;
    } else {
      res >>= 1;
    }
    bit >>= 2;
  }
  int len = 0;
  for (u128 t = res; t; t >>= 1) {
    len++;
  }
  int drop = len - 53;
  uint64_t q = static_cast<uint64_t>(res >> drop);
  u128 low = res & ((static_cast<u128>(1) << drop) - 1);
  u128 half = static_cast<u128>(1) << (drop - 1);
  if (low > half || (low == half && (rem != 0 || (q & 1)))) {
    q++;
  }
  // q * 2^drop / 2^55 is the root; a 53-bit q has the value q 2^-52 when len is 56
  return std::ldexp(static_cast<double>(q), drop - 55);
}

struct Xorshift {
  uint64_t s;
  uint64_t Next() {
    s ^= s << 13;
    s ^= s >> 7;
    s ^= s << 17;
    return s;
  }
};

double RandomM(Xorshift & r) {
  return DoubleOf(((r.Next() & 1) ? 0x4000000000000000ull : 0x3ff0000000000000ull) | (r.Next() & 0xfffffffffffffull));
}

}  // namespace

TEST(SqrtInternal, ReferenceRootIsRight) {
  EXPECT_EQ(RefSqrt(1.0), 1.0);
  EXPECT_EQ(RefSqrt(4.0 - 0x1p-51), 0x1.fffffffffffffp0);
  EXPECT_EQ(RefSqrt(2.0), 0x1.6a09e667f3bcdp+0);
  EXPECT_EQ(RefSqrt(1.0 + 0x1p-52), 1.0);
  EXPECT_EQ(RefSqrt(3.0), 0x1.bb67ae8584caap+0);
}

TEST(SqrtInternal, TheEstimateIsWithinOneUlpOfTheRoot) {
  Xorshift r{0x243f6a8885a308d3ull};
  double worst = 0.0;
  for (int i = 0; i < 4000000; i++) {
    double m = RandomM(r);
    double ref = RefSqrt(m);
    double err = std::fabs(gmath_sqrt_estimate(m) - ref) / 0x1p-52;
    if (err > worst) {
      worst = err;
    }
  }
  std::printf("  estimate: worst distance from the correctly rounded root %.3f ulp\n", worst);
  EXPECT_LE(worst, 1.0);
}

TEST(SqrtInternal, TheCorrectionRepairsAnEstimateOneUlpLowHighOrRight) {
  Xorshift r{0x13198a2e03707344ull};
  uint64_t bad = 0;
  for (int i = 0; i < 3000000; i++) {
    double m = RandomM(r);
    double ref = RefSqrt(m);
    for (double y : {ref, std::nextafter(ref, 4.0), std::nextafter(ref, 0.0)}) {
      if (y < 1.0) {
        continue;
      }
      if (BitsOf(gmath_sqrt_correct(m, y)) != BitsOf(ref)) {
        if (bad++ < 5) {
          ADD_FAILURE() << std::hexfloat << "m = " << m << " from " << y << " gave " << gmath_sqrt_correct(m, y) << ", not " << ref;
        }
      }
    }
  }
  EXPECT_EQ(bad, 0u);
}

TEST(SqrtInternal, TheCorrectionFindsExactSquaresFromEitherSide) {
  for (uint64_t k = 0; k < 20000; k++) {
    // y = a number of 26 bits in [1, 2): y^2 is a double
    double y = 1.0 + static_cast<double>((k * 2654435761ull) & 0x3ffffffull) * 0x1p-26;
    double m = y * y;
    ASSERT_EQ(RefSqrt(m), y);
    EXPECT_EQ(gmath_sqrt_correct(m, y), y);
    EXPECT_EQ(gmath_sqrt_correct(m, std::nextafter(y, 4.0)), y);
    EXPECT_EQ(gmath_sqrt_correct(m, std::nextafter(y, 0.0)), y);
  }
}

TEST(SqrtInternal, TheEqualityCasesOfTheResidualRoundTheRightWay) {
  const double u = 0x1p-52;
  // m = 1 + u: sqrt = 1 + u/2 - u^2/8, just below the halfway point 1 + u/2, so 1.  The residual of y = 1 is
  // +y u exactly (no rounding up: "rho > y u"), and that of y = 1 + u is -y u exactly (rounding down: "rho <= -y u").
  EXPECT_EQ(RefSqrt(1.0 + u), 1.0);
  EXPECT_EQ(gmath_sqrt_correct(1.0 + u, 1.0), 1.0);
  EXPECT_EQ(gmath_sqrt_correct(1.0 + u, 1.0 + u), 1.0);
}

TEST(SqrtInternal, AnEstimateOfTwoForTheLargestArgument) {
  // m just under 4: the root is below 2 and rounds to 2 - 2^-52; an estimate of 2 is lowered by the residual -2^-51 = -y u.
  double m = 4.0 - 0x1p-51;
  EXPECT_EQ(RefSqrt(m), 0x1.fffffffffffffp0);
  EXPECT_EQ(gmath_sqrt_correct(m, 2.0), 0x1.fffffffffffffp0);
  EXPECT_EQ(gmath_sqrt_correct(m, 0x1.fffffffffffffp0), 0x1.fffffffffffffp0);
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
