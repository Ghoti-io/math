/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Binary32 atan2 special/state contracts. Constants and ordinary finite NN
 * fixtures come from the independent pinned atan2f oracle. Tiny-only added
 * fixtures use exact Fraction quotient midpoints and atan(q)<q; reflections
 * remain within the certified nearest pi/half-pi constant cells.
 * No implementation helper computes expected values. General finite bits
 * are checked in nearest mode; other modes check shape, sign and quadrant.
 * Tiny/special bits are checked in every mode. Caller-local memcpy transports
 * raw NaNs; state is captured before any reference/diagnostic arithmetic.
 * Hash: nearest/no incoming flags, result words plus normalized flags only.
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
    "raw atan2f probe requires IEEE binary32 in eight-bit bytes");

#define PI 0x40490fdbu
#define PIO2 0x3fc90fdbu
#define PIO4 0x3f490fdbu
#define THREEPIO4 0x4016cbe4u
struct vector { uint32_t y, x, result; int flags; unsigned all_modes; };
static const struct vector finite[] = {
    {0x00000001u, 0x40000000u, 0x00000000u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x40000000u, 0x00000001u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x00000001u, 0xc0000000u, 0x40490fdbu, FE_INEXACT, 0u},
    {0xc0000000u, 0x00000001u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x80000001u, 0x40000000u, 0x80000000u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x40000000u, 0x80000001u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x80000001u, 0xc0000000u, 0xc0490fdbu, FE_INEXACT, 0u},
    {0xc0000000u, 0x80000001u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x00000003u, 0x40000000u, 0x00000001u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x40000000u, 0x00000003u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x00000003u, 0xc0000000u, 0x40490fdbu, FE_INEXACT, 0u},
    {0xc0000000u, 0x00000003u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x80000003u, 0x40000000u, 0x80000001u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x40000000u, 0x80000003u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x80000003u, 0xc0000000u, 0xc0490fdbu, FE_INEXACT, 0u},
    {0xc0000000u, 0x80000003u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x00000005u, 0x40000000u, 0x00000002u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x40000000u, 0x00000005u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x00000005u, 0xc0000000u, 0x40490fdbu, FE_INEXACT, 0u},
    {0xc0000000u, 0x00000005u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x80000005u, 0x40000000u, 0x80000002u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x40000000u, 0x80000005u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x80000005u, 0xc0000000u, 0xc0490fdbu, FE_INEXACT, 0u},
    {0xc0000000u, 0x80000005u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x00000007u, 0x40000000u, 0x00000003u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x40000000u, 0x00000007u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x00000007u, 0xc0000000u, 0x40490fdbu, FE_INEXACT, 0u},
    {0xc0000000u, 0x00000007u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x80000007u, 0x40000000u, 0x80000003u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x40000000u, 0x80000007u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x80000007u, 0xc0000000u, 0xc0490fdbu, FE_INEXACT, 0u},
    {0xc0000000u, 0x80000007u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x00ffffffu, 0x40000000u, 0x007fffffu, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x40000000u, 0x00ffffffu, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x00ffffffu, 0xc0000000u, 0x40490fdbu, FE_INEXACT, 0u},
    {0xc0000000u, 0x00ffffffu, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x80ffffffu, 0x40000000u, 0x807fffffu, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x40000000u, 0x80ffffffu, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x80ffffffu, 0xc0000000u, 0xc0490fdbu, FE_INEXACT, 0u},
    {0xc0000000u, 0x80ffffffu, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x01000000u, 0x40000000u, 0x00800000u, FE_INEXACT, 1u},
    {0x40000000u, 0x01000000u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x01000000u, 0xc0000000u, 0x40490fdbu, FE_INEXACT, 0u},
    {0xc0000000u, 0x01000000u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x81000000u, 0x40000000u, 0x80800000u, FE_INEXACT, 1u},
    {0x40000000u, 0x81000000u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x81000000u, 0xc0000000u, 0xc0490fdbu, FE_INEXACT, 0u},
    {0xc0000000u, 0x81000000u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x00000001u, 0x7f7fffffu, 0x00000000u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x7f7fffffu, 0x00000001u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x00000001u, 0xff7fffffu, 0x40490fdbu, FE_INEXACT, 0u},
    {0xff7fffffu, 0x00000001u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x80000001u, 0x7f7fffffu, 0x80000000u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x7f7fffffu, 0x80000001u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x80000001u, 0xff7fffffu, 0xc0490fdbu, FE_INEXACT, 0u},
    {0xff7fffffu, 0x80000001u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x00000001u, 0x3f800000u, 0x00000001u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x3f800000u, 0x00000001u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x00000001u, 0xbf800000u, 0x40490fdbu, FE_INEXACT, 0u},
    {0xbf800000u, 0x00000001u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x80000001u, 0x3f800000u, 0x80000001u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x3f800000u, 0x80000001u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x80000001u, 0xbf800000u, 0xc0490fdbu, FE_INEXACT, 0u},
    {0xbf800000u, 0x80000001u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x00000002u, 0x40400000u, 0x00000001u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x40400000u, 0x00000002u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x00000002u, 0xc0400000u, 0x40490fdbu, FE_INEXACT, 0u},
    {0xc0400000u, 0x00000002u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x80000002u, 0x40400000u, 0x80000001u, FE_UNDERFLOW | FE_INEXACT, 1u},
    {0x40400000u, 0x80000002u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x80000002u, 0xc0400000u, 0xc0490fdbu, FE_INEXACT, 0u},
    {0xc0400000u, 0x80000002u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x307fffffu, 0x3f800000u, 0x307fffffu, FE_INEXACT, 1u},
    {0x3f800000u, 0x307fffffu, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x307fffffu, 0xbf800000u, 0x40490fdbu, FE_INEXACT, 0u},
    {0xbf800000u, 0x307fffffu, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0xb07fffffu, 0x3f800000u, 0xb07fffffu, FE_INEXACT, 1u},
    {0x3f800000u, 0xb07fffffu, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0xb07fffffu, 0xbf800000u, 0xc0490fdbu, FE_INEXACT, 0u},
    {0xbf800000u, 0xb07fffffu, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x30800000u, 0x3f800000u, 0x30800000u, FE_INEXACT, 0u},
    {0x3f800000u, 0x30800000u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x30800000u, 0xbf800000u, 0x40490fdbu, FE_INEXACT, 0u},
    {0xbf800000u, 0x30800000u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0xb0800000u, 0x3f800000u, 0xb0800000u, FE_INEXACT, 0u},
    {0x3f800000u, 0xb0800000u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0xb0800000u, 0xbf800000u, 0xc0490fdbu, FE_INEXACT, 0u},
    {0xbf800000u, 0xb0800000u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x30800001u, 0x3f800000u, 0x30800001u, FE_INEXACT, 0u},
    {0x3f800000u, 0x30800001u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0x30800001u, 0xbf800000u, 0x40490fdbu, FE_INEXACT, 0u},
    {0xbf800000u, 0x30800001u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0xb0800001u, 0x3f800000u, 0xb0800001u, FE_INEXACT, 0u},
    {0x3f800000u, 0xb0800001u, 0x3fc90fdbu, FE_INEXACT, 0u},
    {0xb0800001u, 0xbf800000u, 0xc0490fdbu, FE_INEXACT, 0u},
    {0xbf800000u, 0xb0800001u, 0xbfc90fdbu, FE_INEXACT, 0u},
    {0x3f800000u, 0x40000000u, 0x3eed6338u, FE_INEXACT, 0u},
    {0x40000000u, 0x3f800000u, 0x3f8db70du, FE_INEXACT, 0u},
    {0x3f800000u, 0xc0000000u, 0x402b6374u, FE_INEXACT, 0u},
    {0xc0000000u, 0x3f800000u, 0xbf8db70du, FE_INEXACT, 0u},
    {0xbf800000u, 0x40000000u, 0xbeed6338u, FE_INEXACT, 0u},
    {0x40000000u, 0xbf800000u, 0x40023454u, FE_INEXACT, 0u},
    {0xbf800000u, 0xc0000000u, 0xc02b6374u, FE_INEXACT, 0u},
    {0xc0000000u, 0xbf800000u, 0xc0023454u, FE_INEXACT, 0u},
};
static const uint32_t special_words[] = {0, 1, 0x007fffffu, MIN_NORMAL,
    ONE, 0x40000000u, 0x7f7fffffu, INF, QNAN, QNAN | 7, 0x7fffffffu,
    INF | 1, INF | (QUIET - 1), INF | 0x12345u};
static void append(struct vector * cases, unsigned * count, struct vector v) {
  for (unsigned i = 0; i < *count; ++i) {
    if (cases[i].y == v.y && cases[i].x == v.x) return;
  }
  cases[(*count)++] = v;
}
static int special(uint32_t y, uint32_t x, struct vector * v) {
  uint32_t a = y & ABS, b = x & ABS, sign = y & SIGN;
  *v = (struct vector){y, x, 0, 0, 1};
  if ((a > INF && !(a & QUIET)) || (b > INF && !(b & QUIET))) {
    v->result = QNAN; v->flags = FE_INVALID; return 1;
  }
  if (a > INF || b > INF) { v->result = QNAN; return 1; }
  if ((a == 0 && !(x & SIGN)) || (a < INF && b == INF && !(x & SIGN))) {
    v->result = sign; return 1;
  }
  uint32_t magnitude;
  if (a == 0) magnitude = PI;
  else if (b == 0) magnitude = PIO2;
  else if (a == INF && b == INF) magnitude = (x & SIGN) ? THREEPIO4 : PIO4;
  else if (a == INF) magnitude = PIO2;
  else if (b == INF) magnitude = PI;
  else if (a == b) magnitude = (x & SIGN) ? THREEPIO4 : PIO4;
  else return 0;
  v->result = magnitude | sign; v->flags = FE_INEXACT; return 1;
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
        uint32_t y = special_words[i] | ((signs & 1) ? SIGN : 0);
        uint32_t x = special_words[j] | ((signs & 2) ? SIGN : 0);
        if (special(y, x, &v)) append(cases, &case_count, v);
      }
    }
  }
  for (unsigned i = 0; i < sizeof finite / sizeof finite[0]; ++i) {
    append(cases, &case_count, finite[i]);
  }
  fenv_t saved;
  if (feholdexcept(&saved) != 0) {
    fputs("atan2f-special: cannot save floating environment\n", stderr);
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
        float y, x;
        memcpy(&y, &v.y, sizeof y); memcpy(&x, &v.x, sizeof x);
        if (feclearexcept(FE_ALL_EXCEPT) != 0 || feraiseexcept(seeds[s]) != 0) {
          ++failures; goto done;
        }
        int existing = fetestexcept(FE_ALL_EXCEPT);
        errno = E2BIG;
        float result = gmath_atan2f(y, x);
        int result_errno = errno;
        int flags = fetestexcept(FE_ALL_EXCEPT), mode = fegetround();
        uint32_t word; memcpy(&word, &result, sizeof word);
        uint32_t magnitude = word & ABS;
        int bad = (m == 0 || v.all_modes) ? word != v.result :
            magnitude < MIN_NORMAL || magnitude >= INF ||
            (word & SIGN) != (v.y & SIGN) ||
            ((v.x & SIGN) ? (magnitude < PIO2 - 1u || magnitude > PI + 1u) :
                             magnitude > PIO2 + 1u);
        if (bad || flags != (v.flags | existing) ||
            result_errno != E2BIG || mode != modes[m]) {
          if (failures < 20) {
            fprintf(stderr, "atan2f-special: y=%08" PRIx32 " x=%08" PRIx32
                " result=%08" PRIx32 " expected=%08" PRIx32
                " flags=%x required=%x errno=%d mode=%x expected-mode=%x\n",
                v.y, v.x, word, v.result, (unsigned)flags,
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
    printf("math.atan2f_special.hash %016" PRIx64 "\n", hash);
    printf("math.atan2f_special.count %" PRIu64 "\n", count);
  }
  else fprintf(stderr, "atan2f-special: %u contract checks failed\n", failures);
  errno = saved_errno;
  return failures != 0;
}
