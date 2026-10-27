/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Full exact result probe plus selected all-mode/incoming-state checks.
 */
#include "../tests/corpus_hash.h"
#include <errno.h>
#include <fenv.h>
#include <ghoti.io/math/basic.h>
#include <inttypes.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
_Static_assert(sizeof(int) == 4 && INT_MAX == INT32_MAX && sizeof(float) == 4,
               "raw Float scale probe expects binary32 and signed32 int");
static int signed_word(uint32_t word) {
  int result;
  memcpy(&result, &word, 4);
  return result;
}
static int native_flags(uint32_t flags) {
  return ((flags & 1u) ? FE_INVALID : 0) | ((flags & 4u) ? FE_OVERFLOW : 0) |
         ((flags & 8u) ? FE_UNDERFLOW : 0) | ((flags & 16u) ? FE_INEXACT : 0);
}
static int selected(uint32_t raw, int n, uint64_t index) {
  if (index % 251u == 0) {
    return 1;
  }
  uint32_t a = raw & 0x7fffffffu;
  const uint32_t words[] = {0,          1,          2,          3,
                            5,          0x7fffff,   0x800000,   0xffffff,
                            0x1000000,  0x3f800000, 0x7f7fffff, 0x7f800000,
                            0x7f800001, 0x7fc00000, 0x7fffffff};
  const int exponents[] = {INT_MIN, -150, -24, -1, 0, 1, 127, 128, INT_MAX};
  int found = 0;
  for (unsigned i = 0; i < sizeof words / sizeof *words; ++i) {
    if (a == words[i]) {
      found = 1;
    }
  }
  if (!found) {
    return 0;
  }
  for (unsigned i = 0; i < sizeof exponents / sizeof *exponents; ++i) {
    if (n == exponents[i]) {
      return 1;
    }
  }
  return 0;
}
static int parse(const char * line, uint32_t words[9]) {
  const unsigned char * p = (const unsigned char *)line;
  for (unsigned field = 0; field < 9; ++field) {
    uint32_t word = 0;
    for (unsigned i = 0; i < 8; ++i) {
      unsigned char c = *p++;
      unsigned digit;
      if (c >= '0' && c <= '9') {
        digit = (unsigned)(c - '0');
      } else if (c >= 'a' && c <= 'f') {
        digit = (unsigned)(c - 'a') + 10u;
      } else if (c >= 'A' && c <= 'F') {
        digit = (unsigned)(c - 'A') + 10u;
      } else {
        return 0;
      }
      word = (word << 4) | digit;
    }
    words[field] = word;
    if (field < 8 && *p++ != ' ') {
      return 0;
    }
  }
  return *p == '\0' || (*p == '\n' && p[1] == '\0');
}
static int invoke(const uint32_t w[9], unsigned kind, int mode, int seed,
                  uint64_t * full, uint64_t * all, unsigned hash_kind) {
  float x;
  memcpy(&x, w, 4);
  int n = signed_word(w[1]), exponent = 12345, integer = 0;
  float result = 0;
  if (fesetround(mode) || feclearexcept(FE_ALL_EXCEPT) || feraiseexcept(seed)) {
    return 1;
  }
  int incoming = fetestexcept(FE_ALL_EXCEPT);
  errno = E2BIG;
  if (kind == 0) {
    float (*volatile fn)(float, int) = gmath_scalbnf;
    result = fn(x, n);
  } else if (kind == 1) {
    float (*volatile fn)(float, int) = gmath_ldexpf;
    result = fn(x, n);
  } else if (kind < 4) {
    float (*volatile fn)(float, int *) = gmath_frexpf;
    result = fn(x, kind == 2 ? &exponent : NULL);
  } else {
    int (*volatile fn)(float) = gmath_ilogbf;
    integer = fn(x);
  }
  int error = errno, flags = fetestexcept(FE_ALL_EXCEPT),
      rounding = fegetround();
  uint32_t output;
  if (kind == 4) {
    output = (uint32_t)integer;
  } else {
    memcpy(&output, &result, 4);
  }
  uint32_t expected = kind < 2 ? w[2] : (kind < 4 ? w[4] : w[7]);
  uint32_t extra = kind == 2 ? (uint32_t)exponent : 0,
           expected_extra = kind == 2 ? w[5] : 0;
  uint32_t required = kind < 2 ? w[3] : (kind < 4 ? w[6] : w[8]);
  if (output != expected || extra != expected_extra ||
      flags != (incoming | native_flags(required)) || error != E2BIG ||
      rounding != mode) {
    fprintf(stderr,
            "Float scale input%08" PRIx32 " n%08" PRIx32
            " kind%u result%08" PRIx32 " expected%08" PRIx32 " extra%08" PRIx32
            " expected%08" PRIx32 " flags%x required%x errno%d mode%x\n",
            w[0], w[1], kind, output, expected, extra, expected_extra,
            (unsigned)flags, (unsigned)(incoming | native_flags(required)),
            error, (unsigned)rounding);
    return 1;
  }
  uint64_t * hash = hash_kind == 1 ? full : all;
  if (hash_kind) {
    *hash = gmath_fnv_u64(gmath_fnv_u64(gmath_fnv_u64(*hash, output), extra),
                          required);
  }
  return 0;
}
int main(int argc, char ** argv) {
  if (argc > 2) {
    return 2;
  }
  const char * directory = argc == 2 ? argv[1] : "tests/corpus";
  char path[4096], line[512];
  int size = snprintf(path, sizeof path, "%s/float_scale.corpus", directory);
  if (size < 0 || (size_t)size >= sizeof path) {
    return 2;
  }
  FILE * input = fopen(path, "r");
  if (!input) {
    perror(path);
    return 2;
  }
  fenv_t saved;
  int saved_errno = errno;
  if (fegetenv(&saved)) {
    fclose(input);
    return 2;
  }
  const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  const int seeds[] = {
      0,          FE_INVALID,   FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
      FE_INEXACT, FE_ALL_EXCEPT};
  uint64_t full = GMATH_FNV_BASIS, all = GMATH_FNV_BASIS, count = 0, states = 0,
           index = 0;
  int failure = 0;
  while (fgets(line, sizeof line, input)) {
    if (line[0] == '#') {
      continue;
    }
    uint32_t words[9];
    if (!parse(line, words)) {
      failure = 1;
      break;
    }
    for (unsigned kind = 0; kind < 5 && !failure; ++kind) {
      failure = invoke(words, kind, FE_TONEAREST, 0, &full, &all, 1);
      ++count;
    }
    if (!failure && selected(words[0], signed_word(words[1]), index)) {
      for (unsigned m = 0; m < 4 && !failure; ++m) {
        for (unsigned s = 0; s < 7 && !failure; ++s) {
          for (unsigned kind = 0; kind < 5 && !failure; ++kind) {
            failure = invoke(words, kind, modes[m], seeds[s], &full, &all,
                             s == 0 ? 2u : 0u);
            ++states;
          }
        }
      }
    }
    ++index;
    if (failure) {
      break;
    }
  }
  if (ferror(input) || index < 10000) {
    failure = 1;
  }
  fclose(input);
  if (fesetenv(&saved)) {
    failure = 1;
  }
  errno = saved_errno;
  if (!failure) {
    printf("math.floatscale_full.hash %016" PRIx64
           "\nmath.floatscale_full.count %" PRIu64
           "\nmath.floatscale_all_modes.hash %016" PRIx64
           "\nmath.floatscale_state.count %" PRIu64 "\n",
           full, count, all, states);
  }
  return failure;
}
