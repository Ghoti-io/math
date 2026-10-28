/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Read arithmetic rounding controls, preserving controls and C exception flags.
 * SPARC STFSR/STXFSR can clear architectural FTT trap-type status, which is not
 * a C exception flag; coherent nontrapping standard environments are assumed.
 * Internal codes: 0 nearest/even, 1 down, 2 up, 3 toward zero, -1 unsupported.
 * Standard fenv fallback is retained for ports without a native reader; that
 * explicit/unsupported-port configuration requires the platform fenv runtime.
 */
#ifndef GHOTI_IO_GMATH_NEARBY_MODE_H
#define GHOTI_IO_GMATH_NEARBY_MODE_H
#include <ghoti.io/math/macros.h>
#include <stdint.h>
#include <string.h>
#if (defined(__powerpc__) || defined(__powerpc64__)) &&                        \
    !defined(_SOFT_FLOAT) && !defined(__NO_FPRS__) &&                          \
    !defined(_SOFT_DOUBLE) && !defined(__SOFTFP__) && !defined(__SPE__)
#define GMATH_NEARBY_PPC_NATIVE 1
#endif
#if defined(__sparc__) && !defined(__SOFTFP__) && !defined(_SOFT_FLOAT)
#define GMATH_NEARBY_SPARC_NATIVE 1
#endif
#if defined(GMATH_NEARBY_FENV_QUERY) ||                                        \
    !((defined(__GNUC__) || defined(__clang__)) &&                             \
        ((defined(__SSE__) && (defined(__i386__) || defined(__x86_64__))) ||   \
            defined(__aarch64__) || defined(__s390x__) ||                      \
            defined(GMATH_NEARBY_PPC_NATIVE) ||                                \
            defined(GMATH_NEARBY_SPARC_NATIVE)))
#define GMATH_NEARBY_QUERY_NATIVE 0
#include <errno.h>
#include <fenv.h>
static inline int nearby_mode(void) {
  int saved = errno, mode = fegetround();
  errno = saved;
  if (mode == FE_TONEAREST)
    return 0;
  if (mode == FE_DOWNWARD)
    return 1;
  if (mode == FE_UPWARD)
    return 2;
  if (mode == FE_TOWARDZERO)
    return 3;
  return -1;
}
#else
#define GMATH_NEARBY_QUERY_NATIVE 1
static inline int nearby_mode(void) {
#if defined(__SSE__) && (defined(__i386__) || defined(__x86_64__))
  uint32_t control;
  __asm__ volatile("stmxcsr %0" : "=m"(control) : : "memory");
  return (int)((control >> 13) & 3u);
#elif defined(__aarch64__)
  uint64_t control;
  __asm__ volatile("mrs %0, fpcr" : "=r"(control) : : "memory");
  unsigned code = (unsigned)((control >> 22) & 3u);
  return (int)(((code & 1u) << 1) | ((code & 2u) >> 1));
#elif defined(__s390x__)
  uint32_t control;
  __asm__ volatile("efpc %0" : "=d"(control) : : "memory");
  unsigned code = control & 7u;
  return code > 3u ? -1 : (code == 1u ? 3 : code == 3u ? 1 : (int)code);
#elif defined(GMATH_NEARBY_PPC_NATIVE)
  double control;
  uint64_t word;
  __asm__ volatile("mffs %0" : "=f"(control) : : "memory");
  memcpy(&word, &control, sizeof word);
  unsigned code = (unsigned)(word & 3u);
  return code == 1u ? 3 : code == 3u ? 1 : (int)code;
#elif defined(GMATH_NEARBY_SPARC_NATIVE)
#if defined(__arch64__)
  uint64_t control;
  __asm__ volatile("stx %%fsr, %0" : "=m"(control) : : "memory");
#else
  uint32_t control;
  __asm__ volatile("st %%fsr, %0" : "=m"(control) : : "memory");
#endif
  unsigned code = (unsigned)((control >> 30) & 3u);
  return code == 1u ? 3 : code == 3u ? 1 : (int)code;

#endif
}
#endif
#endif
