/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Oracle-free binary32 hypot contracts. Finite fixtures were independently
 * certified with rational squared-distance/midpoint comparisons, including
 * both tie directions, the overflow midpoint and tininess after rounding.
 * No implementation helper or floating reference decides expected results.
 * Raw caller-local memcpy transports NaNs. Snapshot state before diagnostics.
 * Hash: nearest/no incoming flags, result words plus normalized flags only;
 * errno and rounding mode are asserted on every call, outside the payload.
 */
#include <ghoti.io/math/elementary.h>
#include <errno.h>
#include <fenv.h>
#include <float.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define SIGN 0x80000000u
#define ABS 0x7fffffffu
#define INF 0x7f800000u
#define QUIET 0x00400000u
#define QNAN 0x7fc00000u
#define ONE 0x3f800000u
#define MIN_NORMAL 0x00800000u

_Static_assert(CHAR_BIT == 8 && sizeof(float) == 4 &&
    sizeof(float) == sizeof(uint32_t) && FLT_RADIX == 2 && FLT_MANT_DIG == 24 &&
    FLT_MIN_EXP == -125 && FLT_MAX_EXP == 128,
    "raw hypotf probe requires IEEE binary32 in eight-bit bytes");

struct vector { uint32_t x, y, result; int flags; };
static const struct vector finite[] = {
    /* Exact Double root is FLT_MAX+quarter Float ULP: needs boundary-only IX. */
    {0x7e0420f5u, 0x7f7ddc25u, 0x7f7fffffu, FE_INEXACT},
    /* Exact Double root49990001 needs Float-only inexact at49990000. */
    {0x4c3eb25cu, 0x461c3c00u, 0x4c3eb25cu, FE_INEXACT},
    {0x00000000u, 0x00000000u, 0x00000000u, 0},
    {0x00000003u, 0x00000004u, 0x00000005u, 0},
    {0x00000001u, 0x00000001u, 0x00000001u, FE_UNDERFLOW | FE_INEXACT},
    {0x007fffffu, 0x00000fffu, 0x00800000u, FE_INEXACT},
    {0x007fffffu, 0x00000001u, 0x007fffffu, FE_UNDERFLOW | FE_INEXACT},
    {0x00800000u, 0x00000001u, 0x00800000u, FE_INEXACT},
    {0x00800000u, 0x00800000u, 0x00b504f3u, FE_INEXACT},
    {0x3f800000u, 0x3f800000u, 0x3fb504f3u, FE_INEXACT},
    {0x40400000u, 0x40800000u, 0x40a00000u, 0},
    {0x40a00000u, 0x41400000u, 0x41500000u, 0},
    {0x7f7fffffu, 0x7f7fffffu, 0x7f800000u, FE_OVERFLOW | FE_INEXACT},
    {0x7f6eccf8u, 0x7eb8807fu, 0x7f800000u, FE_OVERFLOW | FE_INEXACT},
    {0x3f800000u, 0x00000001u, 0x3f800000u, FE_INEXACT},
    {0x3f800000u, 0x39000000u, 0x3f800000u, FE_INEXACT},
    {0x4b7fffffu, 0x46000000u, 0x4b800000u, FE_INEXACT},
    {0x4a9ff14au, 0x4b896bb0u, 0x4b8f1eaeu, FE_INEXACT},
    {0x00000003u, 0x00000004u, 0x00000005u, 0},
    {0x00000006u, 0x00000008u, 0x0000000au, 0},
    {0x00000600u, 0x00000800u, 0x00000a00u, 0},
    {0x01400000u, 0x01800000u, 0x01a00000u, 0},
    {0x01c00000u, 0x02000000u, 0x02200000u, 0},
    {0x36400000u, 0x36800000u, 0x36a00000u, 0},
    {0x4a400000u, 0x4a800000u, 0x4aa00000u, 0},
    {0x72400000u, 0x72800000u, 0x72a00000u, 0},
    {0x7e400000u, 0x7e800000u, 0x7ea00000u, 0},
    {0x7f6eccf7u, 0x7eb8807fu, 0x7f7fffffu, FE_INEXACT},
    {0x7f6eccf9u, 0x7eb8807fu, 0x7f800000u, FE_OVERFLOW | FE_INEXACT},
    {0x7f6eccf8u, 0x7eb8807eu, 0x7f7fffffu, FE_INEXACT},
    {0x7f6eccf8u, 0x7eb88080u, 0x7f800000u, FE_OVERFLOW | FE_INEXACT},
};
static const uint32_t special_words[] = {0, 1, 0x007fffffu, MIN_NORMAL,
    ONE, 0x7f7fffffu, INF, QNAN, QNAN | 7, 0x7fffffffu,
    INF | 1, INF | (QUIET - 1), INF | 0x12345u};
static void append(struct vector * cases, unsigned * count, struct vector v) {
  for (unsigned i = 0; i < *count; ++i) {
    if (cases[i].x == v.x && cases[i].y == v.y) return;
  }
  cases[(*count)++] = v;
}
static int special(uint32_t x, uint32_t y, struct vector * v) {
  uint32_t a = x & ABS, b = y & ABS;
  *v = (struct vector){x, y, 0, 0};
  if ((a > INF && !(a & QUIET)) || (b > INF && !(b & QUIET))) {
    v->result = QNAN; v->flags = FE_INVALID;
  }
  else if (a == INF || b == INF) v->result = INF;
  else if (a > INF || b > INF) v->result = QNAN;
  else if (a == 0 || b == 0) v->result = a | b;
  else return 0;
  return 1;
}
static uint32_t normalized_flags(int flags) {
  return ((flags & FE_INVALID) ? 1u : 0u) |
      ((flags & FE_DIVBYZERO) ? 2u : 0u) |
      ((flags & FE_OVERFLOW) ? 4u : 0u) |
      ((flags & FE_UNDERFLOW) ? 8u : 0u) |
      ((flags & FE_INEXACT) ? 16u : 0u);
}
static uint64_t hash_word(uint64_t hash, uint32_t word) {
  for (unsigned i = 0; i < 4; ++i) {
    hash ^= (word >> (8 * i)) & 0xffu;
    hash *= 0x100000001b3ull;
  }
  return hash;
}
int main(void) {
  int saved_errno = errno;
  struct vector cases[2048];
  unsigned case_count = 0;
  for (unsigned i = 0; i < sizeof special_words / sizeof special_words[0]; ++i) {
    for (unsigned j = 0; j < sizeof special_words / sizeof special_words[0]; ++j) {
      for (unsigned signs = 0; signs < 4; ++signs) {
        struct vector v;
        uint32_t x = special_words[i] | ((signs & 1) ? SIGN : 0);
        uint32_t y = special_words[j] | ((signs & 2) ? SIGN : 0);
        if (special(x, y, &v)) append(cases, &case_count, v);
      }
    }
  }
  for (unsigned i = 0; i < sizeof finite / sizeof finite[0]; ++i) {
    for (unsigned signs = 0; signs < 4; ++signs) {
      struct vector v = finite[i];
      v.x |= (signs & 1) ? SIGN : 0;
      v.y |= (signs & 2) ? SIGN : 0;
      append(cases, &case_count, v);
      uint32_t x = v.x; v.x = v.y; v.y = x;
      append(cases, &case_count, v);
    }
  }
  fenv_t saved;
  if (feholdexcept(&saved) != 0) {
    fputs("hypotf-special: cannot save floating environment\n", stderr);
    errno = saved_errno; return 1;
  }
  unsigned failures = 0;
  uint64_t hash = 0xcbf29ce484222325ull, count = 0;
  if (fesetenv(FE_DFL_ENV) != 0) { ++failures; goto done; }
  const int modes[] = {FE_TONEAREST, FE_UPWARD, FE_DOWNWARD, FE_TOWARDZERO};
  const int seeds[] = {0, FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW,
      FE_UNDERFLOW, FE_INEXACT, FE_ALL_EXCEPT};
  for (unsigned m = 0; m < sizeof modes / sizeof modes[0]; ++m) {
    if (fesetround(modes[m]) != 0) { ++failures; goto done; }
    for (unsigned s = 0; s < sizeof seeds / sizeof seeds[0]; ++s) {
      for (unsigned i = 0; i < case_count; ++i) {
        struct vector v = cases[i];
        float x, y;
        memcpy(&x, &v.x, sizeof x); memcpy(&y, &v.y, sizeof y);
        if (feclearexcept(FE_ALL_EXCEPT) != 0 || feraiseexcept(seeds[s]) != 0) {
          ++failures; goto done;
        }
        int existing = fetestexcept(FE_ALL_EXCEPT);
        errno = E2BIG;
        float result = gmath_hypotf(x, y);
        int result_errno = errno;
        int flags = fetestexcept(FE_ALL_EXCEPT), mode = fegetround();
        uint32_t word; memcpy(&word, &result, sizeof word);
        if (word != v.result || flags != (v.flags | existing) ||
            result_errno != E2BIG || mode != modes[m]) {
          if (failures < 20) {
            fprintf(stderr, "hypotf-special: x=%08" PRIx32 " y=%08" PRIx32
                " result=%08" PRIx32 " expected=%08" PRIx32
                " flags=%x required=%x errno=%d mode=%x expected-mode=%x\n",
                v.x, v.y, word, v.result, (unsigned)flags,
                (unsigned)(v.flags | existing), result_errno,
                (unsigned)mode, (unsigned)modes[m]);
          }
          ++failures;
        }
        if (m == 0 && s == 0) {
          hash = hash_word(hash, word);
          hash = hash_word(hash, normalized_flags(flags)); ++count;
        }
      }
    }
  }
 done:
  if (fesetenv(&saved) != 0) { ++failures; }
  errno = saved_errno;
  if (failures == 0) {
    printf("math.hypotf_special.hash %016" PRIx64 "\n", hash);
    printf("math.hypotf_special.count %" PRIu64 "\n", count);
  }
  else fprintf(stderr, "hypotf-special: %u contract checks failed\n", failures);
  errno = saved_errno;
  return failures != 0;
}
