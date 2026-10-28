/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Test-only snapshots; no production control writes or new public interface.
 */
#ifndef GMATH_TEST_FP_CONTROLS_H
#define GMATH_TEST_FP_CONTROLS_H
#include <stdint.h>
#include <string.h>
/* Control-only snapshots. Architectural status/diagnostic fields are excluded;
 * the standard C exception flags are asserted separately. PPC covers binary
 * controls only (old mffs upper words need not describe decimal controls).
 * Unknown ports retain the C mode/flag assertions.
 */
static uint64_t gmath_test_controls(void) {
#if (defined(__GNUC__) || defined(__clang__)) && defined(__SSE__) &&           \
    (defined(__i386__) || defined(__x86_64__))
  uint32_t raw;
  __asm__ volatile("stmxcsr %0" : "=m"(raw) : : "memory");
  uint16_t x87;
  __asm__ volatile("fnstcw %0" : "=m"(x87) : : "memory");
  return ((uint64_t)x87 << 32) | (raw & UINT32_C(0xffffffc0));
#elif (defined(__GNUC__) || defined(__clang__)) &&                           \
    (defined(__i386__) || defined(__x86_64__))
  uint16_t x87;
  __asm__ volatile("fnstcw %0" : "=m"(x87) : : "memory");
  return (uint64_t)x87 << 32;
#elif (defined(__GNUC__) || defined(__clang__)) && defined(__aarch64__)
  uint64_t raw;
  __asm__ volatile("mrs %0, fpcr" : "=r"(raw) : : "memory");
  return raw;
#elif (defined(__GNUC__) || defined(__clang__)) && defined(__s390x__)
  uint32_t raw;
  __asm__ volatile("efpc %0" : "=d"(raw) : : "memory");
  return raw & UINT32_C(0xfc000077);
#elif (defined(__GNUC__) || defined(__clang__)) &&                             \
    (defined(__powerpc__) || defined(__powerpc64__)) &&                        \
    !defined(_SOFT_FLOAT) && !defined(__NO_FPRS__) &&                          \
    !defined(_SOFT_DOUBLE) && !defined(__SOFTFP__) && !defined(__SPE__)
  double raw;
  uint64_t word;
  __asm__ volatile("mffs %0" : "=f"(raw) : : "memory");
  memcpy(&word, &raw, sizeof word);
  return word & UINT64_C(0xff);
#elif (defined(__GNUC__) || defined(__clang__)) && defined(__sparc__) &&       \
    !defined(__SOFTFP__) && !defined(_SOFT_FLOAT)
#if defined(__arch64__)
  uint64_t raw;
  __asm__ volatile("stx %%fsr, %0" : "=m"(raw) : : "memory");
#else
  uint32_t raw;
  __asm__ volatile("st %%fsr, %0" : "=m"(raw) : : "memory");
#endif
  return raw & UINT64_C(0xcfc00000);
#else
  return 0;
#endif
}

#endif
