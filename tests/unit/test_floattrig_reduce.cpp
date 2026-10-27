/**
 * @file Result preservation and guards for binary32 wide trig reduction.
 * Copyright 2026 by Corey Pennycuff
 */
#include "test_helpers.h"
#include "../../src/elementary/floattrig_reduce.h"
#include <cfenv>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <cstdlib>

namespace {
uint32_t Bits(float x) {
  uint32_t u;
  std::memcpy(&u, &x, sizeof u);
  return u;
}
float Float(uint32_t u) {
  float x;
  std::memcpy(&x, &u, sizeof x);
  return x;
}
struct Environment {
  fenv_t saved;
  int error = errno;
  Environment() { std::fegetenv(&saved); }
  ~Environment() { std::fesetenv(&saved); errno = error; }
};
struct Function { float (*f)(float); double (*d)(double); };
const Function functions[] = {{gmath_sinf, gmath_sin},
    {gmath_cosf, gmath_cos}, {gmath_tanf, gmath_tan}};
bool Compare(uint32_t word) {
  float x = Float(word);
  for (const auto & fn : functions) {
    float expected = static_cast<float>(fn.d(static_cast<double>(x)));
    float result = fn.f(x);
    if (Bits(result) != Bits(expected)) {
      ADD_FAILURE() << std::hex << word << " result " << Bits(result)
                    << " previous " << Bits(expected);
      return false;
    }
  }
  return true;
}
}

// Compile the exact public source with counted double fallbacks. This makes
// admission observable without adding a production symbol or runtime switch.
namespace {
unsigned fallback_calls[3] = {};
double CountedSin(double x) { ++fallback_calls[0]; return gmath_sin(x); }
double CountedCos(double x) { ++fallback_calls[1]; return gmath_cos(x); }
double CountedTan(double x) { ++fallback_calls[2]; return gmath_tan(x); }
}
#undef gmath_sinf
#undef gmath_cosf
#undef gmath_tanf
#undef gmath_sin
#undef gmath_cos
#undef gmath_tan
#define gmath_sinf counted_sinf
#define gmath_cosf counted_cosf
#define gmath_tanf counted_tanf
#define gmath_sin CountedSin
#define gmath_cos CountedCos
#define gmath_tan CountedTan
#include "../../src/elementary/floattrig.c"
#undef gmath_sinf
#undef gmath_cosf
#undef gmath_tanf
#undef gmath_sin
#undef gmath_cos
#undef gmath_tan

TEST(FloattrigReduce, PublicAdmissionAndFallback) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  float (*const instrumented[])(float) = {counted_sinf, counted_cosf, counted_tanf};
  // At 2^30 every operation admits. Immediately below it dispatch remains on
  // the double moderate path. The other words are fixed uncertainty witnesses.
  const uint32_t uncertain[] = {0x621a4c41u, 0x5c63a2a9u, 0x5fae2a59u};
  for (unsigned op = 0; op < 3; ++op) {
    for (uint32_t sign : {0u, 0x80000000u}) {
      for (uint32_t a : {0x4e7fffffu, 0x4e800000u, 0x4e800001u,
                         0x54a70878u, 0x54a70879u, 0x54a7087au, uncertain[op]}) {
        fallback_calls[op] = 0;
        float x = Float(a | sign);
        float result = instrumented[op](x);
        unsigned expected_calls = a == 0x4e7fffffu || a == 0x54a70879u ||
            a == uncertain[op] ? 1u : 0u;
        EXPECT_EQ(fallback_calls[op], expected_calls) << std::hex << a << " op " << op;
        EXPECT_EQ(Bits(result), Bits(functions[op].f(x))) << std::hex << a;
      }
    }
  }
}

TEST(FloattrigReduce, PreservesWideResults) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  // Every row, significand boundaries and deterministic independent signs.
  for (unsigned e = 127; e < 255; ++e) {
    for (uint32_t mantissa : {0u, 1u, 2u, 0x3fffffu, 0x400000u,
                             0x7ffffdu, 0x7ffffeu, 0x7fffffu}) {
      uint32_t a = (e << 23) | mantissa;
      if (a <= 0x3f800000u) continue;
      ASSERT_TRUE(Compare(a));
      ASSERT_TRUE(Compare(a | 0x80000000u));
    }
  }
  const char * exhaustive = std::getenv("GMATH_FLOATTRIG_EXHAUSTIVE");
  if (exhaustive && std::strcmp(exhaustive, "1") == 0) {
    for (uint32_t a = 0x3f800001u; a < 0x7f800000u; ++a) {
      ASSERT_TRUE(Compare(a));
      ASSERT_TRUE(Compare(a | 0x80000000u));
    }
    return;
  }
  uint32_t state = 0x6d2b79f5u;
  for (unsigned i = 0; i < 1000000; ++i) {
    state ^= state << 13; state ^= state >> 17; state ^= state << 5;
    uint32_t a = 0x3f800001u + (state & 0x3fffffffu);
    if (a >= 0x7f800000u) a -= 0x00800000u;
    ASSERT_TRUE(Compare(a | (state & 0x80000000u)));
  }
}

TEST(FloattrigReduce, TinyPhaseFallbackAndRange) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  // Binary32 neighbors of pi/2 and pi exercise the general helper. The wide
  // words additionally reach the public tiny-phase fallback above 2^30.
  for (uint32_t a : {0x3fc90fdau, 0x3fc90fdbu, 0x40490fdau, 0x40490fdbu,
                     0x54a70879u}) {
    unsigned q = 9;
    double r = 99;
    EXPECT_FALSE(floattrig_reduce(a, &q, &r));
    ASSERT_TRUE(Compare(a));
    ASSERT_TRUE(Compare(a | 0x80000000u));
  }
  unsigned admitted = 0;
  for (unsigned e = 127; e < 255; ++e) {
    for (uint32_t m : {0u, 0x123456u, 0x400000u, 0x7fffffu}) {
      unsigned q;
      double r;
      if (floattrig_reduce((e << 23) | m, &q, &r)) {
        ++admitted;
        ASSERT_LT(q, 4u);
        ASSERT_GE(std::fabs(r), 0x1p-12);
        ASSERT_LT(std::fabs(r), 0.786);
      }
    }
  }
  EXPECT_GT(admitted, 500u);
}

TEST(FloattrigReduce, RoundingCellAdmission) {
  Environment saved;
  ASSERT_EQ(std::fesetround(FE_TONEAREST), 0);
  for (uint32_t word : {0x39800000u, 0x3effffffu, 0x3f000000u,
                        0x3f7fffffu, 0x3f800000u, 0x457fffffu}) {
    double centre = static_cast<double>(Float(word));
    double lower = (centre + static_cast<double>(Float(word - 1))) * 0.5;
    double upper = (centre + static_cast<double>(Float(word + 1))) * 0.5;
    for (double sign : {-1.0, 1.0}) {
      float out = 0;
      EXPECT_TRUE(floattrig_accept(sign * centre, &out));
      EXPECT_EQ(Bits(out), Bits(static_cast<float>(sign * centre)));
      EXPECT_FALSE(floattrig_accept(sign * lower, &out));
      EXPECT_FALSE(floattrig_accept(sign * upper, &out));
      EXPECT_FALSE(floattrig_accept(sign * (lower + centre * 0x1p-36), &out));
      EXPECT_FALSE(floattrig_accept(sign * (upper - centre * 0x1p-36), &out));
      EXPECT_TRUE(floattrig_accept(sign * ((centre + lower) * 0.5), &out));
      EXPECT_TRUE(floattrig_accept(sign * ((centre + upper) * 0.5), &out));
    }
  }
}

TEST(FloattrigReduce, WideStateAndModes) {
  Environment saved;
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO}) {
    ASSERT_EQ(std::fesetround(mode), 0);
    uint32_t state = 0x8f32a1bdu;
    for (unsigned i = 0; i < 2048; ++i) {
      state ^= state << 13; state ^= state >> 17; state ^= state << 5;
      uint32_t a = 0x3f800001u + (state & 0x3fffffffu);
      if (a >= 0x7f800000u) a -= 0x00800000u;
      float x = Float(a | (state & 0x80000000u));
      for (const auto & fn : functions) {
        std::feclearexcept(FE_ALL_EXCEPT);
        volatile double reference = fn.d(static_cast<double>(x));
        volatile float old = static_cast<float>(reference);
        (void)old;
        int expected_flags = std::fetestexcept(FE_ALL_EXCEPT);
        std::feclearexcept(FE_ALL_EXCEPT);
        ASSERT_EQ(std::feraiseexcept(FE_DIVBYZERO), 0);
        errno = 713;
        volatile float result = fn.f(x);
        (void)result;
        int flags = std::fetestexcept(FE_ALL_EXCEPT);
        ASSERT_EQ(flags, expected_flags | FE_DIVBYZERO) << std::hex << a;
        ASSERT_EQ(errno, 713);
        ASSERT_EQ(std::fegetround(), mode);
      }
    }
  }
}

int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
