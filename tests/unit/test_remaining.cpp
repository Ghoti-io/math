/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff */
#include "../remaining_probe.h"
#include "test_helpers.h"
#include <float.h>
TEST(RemainingFifteen, LoadedRowsAndCallerState) {
  const char * root = std::getenv("GMATH_REMAINING_CORPUS_DIR");
  EXPECT_EQ(remaining_probe(root && *root ? root : "tests/corpus", 0, 0), 0);
}
TEST(RemainingFifteen, NativeDirectionBeyondResultPrecision) {
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  for (int mode : modes) {
    ASSERT_EQ(fesetround(mode), 0);
    ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT), 0);
#if LDBL_MANT_DIG > 53
    long double up = 1.0L + 0x1p-60L, down = 1.0L - 0x1p-60L;
    EXPECT_EQ(rp_bits(gmath_nexttoward(1.0, up)), UINT64_C(0x3ff0000000000001));
    EXPECT_EQ(
        rp_bits(gmath_nexttoward(1.0, down)), UINT64_C(0x3fefffffffffffff));
#endif
    long double fup = 1.0L + 0x1p-30L, fdown = 1.0L - 0x1p-30L;
    EXPECT_EQ(rp_fbits(gmath_nexttowardf(1.0f, fup)), UINT64_C(0x3f800001));
    EXPECT_EQ(rp_fbits(gmath_nexttowardf(1.0f, fdown)), UINT64_C(0x3f7fffff));
    EXPECT_EQ(
        rp_bits(gmath_nexttoward(0.0, -0.0L)), UINT64_C(0x8000000000000000));
    EXPECT_EQ(rp_fbits(gmath_nexttowardf(-0.0f, 0.0L)), 0u);
    EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT), 0);
  }
  ASSERT_EQ(fesetenv(&saved), 0);
}
TEST(RemainingFifteen, ExactFusedCancellationAndTininess) {
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  for (int mode : modes) {
    ASSERT_EQ(fesetround(mode), 0);
    ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT), 0);
    EXPECT_EQ(rp_bits(gmath_fma(DBL_MAX, 2.0, -DBL_MAX)), rp_bits(DBL_MAX));
    EXPECT_EQ(rp_bits(gmath_fma(DBL_MIN, 0x1.ffffffffffffep-1, -DBL_MIN)),
        UINT64_C(0x8000000000000001));
    EXPECT_EQ(rp_bits(gmath_fma(1.0, 1.0, -1.0)),
        mode == FE_DOWNWARD ? UINT64_C(0x8000000000000000) : 0u);
    EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT), 0);
    ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT), 0);
    EXPECT_EQ(rp_bits(gmath_fma(DBL_MAX, DBL_MAX, -__builtin_inf())),
        UINT64_C(0xfff0000000000000));
    EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT), 0);
  }
  ASSERT_EQ(fesetenv(&saved), 0);
}
TEST(RemainingFifteen, CanonicalConstructorsAndControlPreservation) {
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  int original_errno = errno;
  const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  for (int mode : modes)
    for (int incoming : {0, FE_DIVBYZERO, FE_ALL_EXCEPT}) {
      ASSERT_EQ(fesetround(mode), 0);
      ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT), 0);
      ASSERT_EQ(feraiseexcept(incoming), 0);
      int seeded = fetestexcept(FE_ALL_EXCEPT);
      uint64_t controls = gmath_test_controls();
      errno = 47;
      EXPECT_EQ(rp_bits(gmath_nan((const char *)(uintptr_t)1)),
          UINT64_C(0x7ff8000000000000));
      EXPECT_EQ(rp_fbits(gmath_nanf(NULL)), UINT64_C(0x7fc00000));
      EXPECT_EQ(rp_bits(gmath_lgamma(2.0)), 0u);
      EXPECT_EQ(rp_bits(gmath_erf(-0.0)), UINT64_C(0x8000000000000000));
      EXPECT_EQ(rp_fbits(gmath_erfcf(0.0f)), UINT64_C(0x3f800000));
      EXPECT_EQ(rp_fbits(gmath_powf(-0.0f, 3.0f)), UINT64_C(0x80000000));
      EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT), seeded);
      EXPECT_EQ(errno, 47);
      EXPECT_EQ(fegetround(), mode);
      EXPECT_EQ(gmath_test_controls(), controls);
    }
  ASSERT_EQ(fesetenv(&saved), 0);
  errno = original_errno;
}
TEST(RemainingFifteen, UnsupportedNativeEncodingIsInvalid) {
#if LDBL_MANT_DIG == 64 && LDBL_MAX_EXP == 16384
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  unsigned char bytes[sizeof(long double)] = {0};
  uint16_t exp = 1;
  long double y;
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
  memcpy(bytes, &exp, 2);
#else
  memcpy(bytes + 8, &exp, 2);
#endif
  memcpy(&y, bytes, sizeof y);
  ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT), 0);
  EXPECT_EQ(rp_bits(gmath_nexttoward(1.0, y)), UINT64_C(0x7ff8000000000000));
  EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT), FE_INVALID);
  ASSERT_EQ(fesetenv(&saved), 0);
#else
  GTEST_SKIP() << "native format has no unsupported80 encodings";
#endif
}
int main(int argc, char ** argv) {
  ::testing::InitGoogleTest(&argc, argv);
  return RUN_ALL_TESTS();
}
TEST(RemainingFifteen, PreserveFlushToZeroAndDenormalControls) {
#if (defined(__GNUC__) || defined(__clang__)) && defined(__SSE__) &&           \
    (defined(__i386__) || defined(__x86_64__))
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  uint32_t before;
  __asm__ volatile("stmxcsr %0" : "=m"(before)::"memory");
  alignas(16) unsigned char area[512] = {};
  __asm__ volatile("fxsave %0" : "=m"(area)::"memory");
  uint32_t mask;
  memcpy(&mask, area + 28, 4);
  if (!mask)
    mask = UINT32_C(0xffbf);
  unsigned daz_settings = (mask & UINT32_C(0x40)) ? 2u : 1u;
  const char * root = std::getenv("GMATH_REMAINING_CORPUS_DIR");
  for (unsigned ftz = 0; ftz < 2; ++ftz)
    for (unsigned daz = 0; daz < daz_settings; ++daz) {
      uint32_t alternate = (before & ~UINT32_C(0x8040)) |
          (ftz ? UINT32_C(0x8000) : 0) | (daz ? UINT32_C(0x40) : 0);
      __asm__ volatile("ldmxcsr %0" ::"m"(alternate) : "memory");
      double maximum = 0;
      EXPECT_EQ(rp_accuracy(1, 1, 64, -1, 0, &maximum), 0);
      EXPECT_NE(rp_accuracy(2, 1, 64, -1, 0, &maximum), 0);
      uint64_t controls = gmath_test_controls();
      EXPECT_EQ(
          remaining_probe(root && *root ? root : "tests/corpus", 0, 0), 0);
      EXPECT_EQ(gmath_test_controls(), controls);
    }
  __asm__ volatile("ldmxcsr %0" ::"m"(before) : "memory");
  ASSERT_EQ(fesetenv(&saved), 0);
#else
  GTEST_SKIP() << "alternate SSE controls unavailable";
#endif
}
#if (defined(__GNUC__) || defined(__clang__)) && defined(__x86_64__) &&        \
    defined(__ELF__) && LDBL_MANT_DIG == 64 && LDBL_MAX_EXP == 16384
#define RP_STRING_INNER(x) #x
#define RP_STRING(x) RP_STRING_INNER(x)
/* Integer-only caller: native80 never enters a caller floating register. */
__attribute__((naked)) static uint64_t rp_raw_native_abi(uint64_t x
    __attribute__((unused)),
    const unsigned char * bytes __attribute__((unused)),
    unsigned width __attribute__((unused))) {
  __asm__(
      "subq $24,%rsp\n\tmovq 0(%rsi),%rax\n\tmovq %rax,0(%rsp)\n\tmovq "
      "8(%rsi),%rax\n\tmovq %rax,8(%rsp)\n\tmovq %rdi,%xmm0\n\tcmpl "
      "$32,%edx\n\tje 1f\n\tcall " RP_STRING(
          gmath_nexttoward) "\n\tmovq %xmm0,%rax\n\tjmp "
                            "2f\n1:\n\tcall " RP_STRING(gmath_nexttowardf) "\n"
                                                                           "\tm"
                                                                           "ovd"
                                                                           " %"
                                                                           "xmm"
                                                                           "0,%"
                                                                           "eax"
                                                                           "\n2"
                                                                           ":\n"
                                                                           "\ta"
                                                                           "ddq"
                                                                           " $"
                                                                           "24,"
                                                                           "%rs"
                                                                           "p\n"
                                                                           "\tr"
                                                                           "e"
                                                                           "t");
}
#endif
TEST(RemainingFifteen, RawNativeAbiSignalingAndUnsupported) {
#if (defined(__GNUC__) || defined(__clang__)) && defined(__x86_64__) &&        \
    defined(__ELF__) && LDBL_MANT_DIG == 64 && LDBL_MAX_EXP == 16384
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  int original_errno = errno;
  const uint64_t mantissas[] = {UINT64_C(0x8000000000000001),
      UINT64_C(0xc000000000000001), 0, 0, UINT64_C(0x8000000000000008), 0,
      UINT64_C(0x8000000000000000)};
  const uint16_t exponents[] = {
      32767, 32767, 1, 32767, 16383, UINT16_C(0x8000), 16383};
  for (unsigned width : {64u, 32u})
    for (unsigned i = 0; i < 7; ++i) {
      unsigned char bytes[16] = {0};
      memcpy(bytes, &mantissas[i], 8);
      memcpy(bytes + 8, &exponents[i], 2);
      unsigned p = width == 64 ? 52 : 23, bias = width == 64 ? 1023 : 127;
      uint64_t one = (uint64_t)bias << p, inf = (uint64_t)(2 * bias + 1) << p,
               sign = UINT64_C(1) << (width - 1);
      uint64_t x = i == 5 ? 0 : one;
      uint64_t expected = i < 4 ? inf | (UINT64_C(1) << (p - 1))
          : i == 4              ? one + 1
          : i == 5              ? sign
                                : one;
      int flags = i == 0 || i == 2 || i == 3 ? FE_INVALID : 0;
      ASSERT_EQ(fesetround(FE_TONEAREST), 0);
      ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT), 0);
      errno = 61;
      uint64_t controls = gmath_test_controls();
      EXPECT_EQ(rp_raw_native_abi(x, bytes, width), expected);
      EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT), flags);
      EXPECT_EQ(errno, 61);
      EXPECT_EQ(gmath_test_controls(), controls);
    }
  ASSERT_EQ(fesetenv(&saved), 0);
  errno = original_errno;
#else
  GTEST_SKIP() << "integer-only native80 SysV caller unavailable";
#endif
}
TEST(RemainingFifteen, RawPseudoDenormalEquivalence) {
#if (defined(__GNUC__) || defined(__clang__)) && defined(__x86_64__) &&        \
    defined(__ELF__) && LDBL_MANT_DIG == 64 && LDBL_MAX_EXP == 16384
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO})
    for (unsigned width : {64u, 32u})
      for (unsigned negative = 0; negative < 2; ++negative) {
        uint64_t sign = UINT64_C(1) << (width - 1),
                 mant = UINT64_C(0x8000000000012345);
        uint16_t pseudo = (uint16_t)(negative ? 0x8000 : 0),
                 canonical = (uint16_t)(pseudo | 1);
        unsigned char a[16] = {}, b[16] = {};
        memcpy(a, &mant, 8);
        memcpy(b, &mant, 8);
        memcpy(a + 8, &pseudo, 2);
        memcpy(b + 8, &canonical, 2);
        for (uint64_t x : {UINT64_C(0), sign, UINT64_C(1), sign | 1}) {
          uint64_t expected =
              (x & (sign - 1)) ? x & sign : (negative ? sign : 0) | 1;
          for (const unsigned char * bytes : {a, b}) {
            ASSERT_EQ(fesetround(mode), 0);
            ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT), 0);
            EXPECT_EQ(rp_raw_native_abi(x, bytes, width), expected);
            EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT), FE_UNDERFLOW | FE_INEXACT);
          }
        }
        uint64_t zero_m = 0;
        memcpy(a, &zero_m, 8);
        for (uint64_t x : {UINT64_C(0), sign}) {
          ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT), 0);
          EXPECT_EQ(rp_raw_native_abi(x, a, width), negative ? sign : 0);
          EXPECT_EQ(fetestexcept(FE_ALL_EXCEPT), 0);
        }
      }
  ASSERT_EQ(fesetenv(&saved), 0);
#else
  GTEST_SKIP() << "integer-only native80 SysV caller unavailable";
#endif
}
#if defined(__GLIBC__) || defined(__APPLE__) || defined(__FreeBSD__)
#include <math.h>
#endif
TEST(RemainingFifteen, LgammaPreservesPlatformSigngam) {
#if defined(__GLIBC__) || defined(__APPLE__) || defined(__FreeBSD__)
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  int original = signgam;
  for (double x : {3.0, -0.5, -2.0, rp_double(UINT64_C(0x7ff8000000000000))}) {
    signgam = 1977;
    (void)gmath_lgamma(x);
    EXPECT_EQ(signgam, 1977);
    signgam = -1977;
    (void)gmath_lgammaf((float)x);
    EXPECT_EQ(signgam, -1977);
  }
  signgam = original;
  EXPECT_EQ(fesetenv(&saved), 0);
#else
  GTEST_SKIP() << "platform does not expose signgam";
#endif
}

TEST(RemainingFifteen, ExactDyadicPowersAllCallerStates) {
  fenv_t saved;
  ASSERT_EQ(fegetenv(&saved), 0);
  int original_errno = errno;
  const uint32_t cases[][3] = {
      {UINT32_C(0x1f800000), UINT32_C(0x40000000), UINT32_C(0x200000)},
      {UINT32_C(0x7f000000), UINT32_C(0xbf800000), UINT32_C(0x400000)},
      {UINT32_C(0x1c800000), UINT32_C(0x40000000), UINT32_C(0x200)},
      {UINT32_C(0x3f000000), UINT32_C(0x43150000), UINT32_C(0x1)},
      {UINT32_C(0xbf000000), UINT32_C(0x43150000), UINT32_C(0x80000001)},
      {UINT32_C(0xa7000000), UINT32_C(0x40400000), UINT32_C(0x80000004)},
      {UINT32_C(0x2), UINT32_C(0x3f000000), UINT32_C(0x1a800000)},
      {UINT32_C(0x1d400000), UINT32_C(0x40000000), UINT32_C(0x1200)},
      {UINT32_C(0x11100000), UINT32_C(0x3fc00000), UINT32_C(0x360)}};
  for (const auto & row : cases)
    for (int mode : {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO})
      for (unsigned subset = 0; subset < 32; ++subset) {
        int incoming = ((subset & 1) ? FE_INVALID : 0) |
            ((subset & 2) ? FE_INEXACT : 0) |
            ((subset & 4) ? FE_UNDERFLOW : 0) |
            ((subset & 8) ? FE_OVERFLOW : 0) |
            ((subset & 16) ? FE_DIVBYZERO : 0);
        ASSERT_EQ(fesetround(mode), 0);
        ASSERT_EQ(feclearexcept(FE_ALL_EXCEPT), 0);
        ASSERT_EQ(feraiseexcept(incoming), 0);
        int seeded = fetestexcept(FE_ALL_EXCEPT);
        uint64_t controls = gmath_test_controls();
        errno = 67;
        EXPECT_EQ(rp_call(8, row[0], row[1], 0), row[2]);
        int after = fetestexcept(FE_ALL_EXCEPT);
        EXPECT_EQ(after & seeded, seeded);
        EXPECT_EQ(after & ~(seeded | FE_INEXACT), 0);
        EXPECT_EQ(errno, 67);
        EXPECT_EQ(fegetround(), mode);
        EXPECT_EQ(gmath_test_controls(), controls);
      }
  ASSERT_EQ(fesetenv(&saved), 0);
  errno = original_errno;
}
