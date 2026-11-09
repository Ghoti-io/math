/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Internal C++ caller-state fixture for elementary and exp2 unit tests.
 */
#ifndef GMATH_TEST_FP_STATE_FIXTURE_H
#define GMATH_TEST_FP_STATE_FIXTURE_H
#include "fp_controls.h"
#include <cerrno>
#include <cfenv>
#include <cstdint>
#include <cstring>

namespace gmath_test {
constexpr int kStateFlags = FE_INVALID | FE_DIVBYZERO | FE_OVERFLOW | FE_UNDERFLOW | FE_INEXACT;
struct FenvGuard {
  fenv_t saved;
  int saved_errno = errno;
  FenvGuard() { std::fegetenv(&saved); }
  ~FenvGuard() { std::fesetenv(&saved); errno = saved_errno; }
};

// Set coherent nontrapping controls. Alternate SSE profiles are used only
// when their bits are reported writable by the architectural save area.
inline bool StateProfile(unsigned profile) {
#if (defined(__GNUC__) || defined(__clang__)) && defined(__SSE__) && \
    (defined(__i386__) || defined(__x86_64__))
  alignas(16) unsigned char area[512] = {};
  __asm__ volatile("fxsave %0" : "=m"(area) : : "memory");
  uint32_t mask;
  std::memcpy(&mask, area + 28, sizeof mask);
  if (!mask) mask = UINT32_C(0xffbf);
  const uint32_t flush[] = {0, UINT32_C(0x8000), UINT32_C(0x8040)};
  if ((flush[profile] & mask) != flush[profile]) return false;
  uint32_t mxcsr;
  uint16_t cw;
  __asm__ volatile("stmxcsr %0" : "=m"(mxcsr) : : "memory");
  __asm__ volatile("fnstcw %0" : "=m"(cw) : : "memory");
  mxcsr = (mxcsr & ~UINT32_C(0x8040)) | UINT32_C(0x1f80) | flush[profile];
  const uint16_t pcs[] = {3, 0, 2};
  cw = static_cast<uint16_t>((cw & ~UINT16_C(0x0300)) | (pcs[profile] << 8) | 0x3f);
  __asm__ volatile("ldmxcsr %0" : : "m"(mxcsr) : "memory");
  __asm__ volatile("fldcw %0" : : "m"(cw) : "memory");
  return true;
#else
  return profile == 0;
#endif
}
} // namespace gmath_test

#endif
