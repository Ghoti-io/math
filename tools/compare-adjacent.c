/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Actual-prior result compatibility, not reference accuracy or per-call flags.
 */
#include <errno.h>
#include <fenv.h>
#include <ghoti.io/math/basic.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifndef GMATH_ADJACENT_BASELINE_IDENTITY
#error "Declared baseline identity is required"
#endif
#ifndef GMATH_NEXTAFTERF_REFERENCE
#error "An actual separately compiled prior Float function is required"
#endif
extern float GMATH_NEXTAFTERF_REFERENCE(float, float);
static int number(const char * text, uint64_t * value) {
  char * end;
  errno = 0;
  if (!*text || *text == '-' || *text == '+') {
    return 0;
  }
  unsigned long long result = strtoull(text, &end, 0);
  if (errno || *end) {
    return 0;
  }
  *value = (uint64_t)result;
  return 1;
}
int main(int argc, char ** argv) {
  uint64_t start, end, step, targets, mode;
  if (argc != 6 || !number(argv[1], &start) || !number(argv[2], &end) ||
      !number(argv[3], &step) || !number(argv[4], &targets) ||
      !number(argv[5], &mode) || start >= end || end > UINT64_C(0x100000000) ||
      !step || step > UINT32_MAX || targets < 1 || targets > 127 || mode > 3) {
    fputs("usage: compare-adjacent START END STEP TARGET_MASK(1..127) "
          "MODE(0..3)\n",
          stderr);
    return 2;
  }
  const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  fenv_t saved;
  if (fegetenv(&saved) || fesetenv(FE_DFL_ENV) || fesetround(modes[mode])) {
    return 2;
  }
  float (*volatile candidate)(float, float) = gmath_nextafterf;
  float (*volatile previous)(float, float) = GMATH_NEXTAFTERF_REFERENCE;
  if (candidate == previous) {
    (void)fesetenv(&saved);
    fputs("adjacent reference aliases candidate\n", stderr);
    return 2;
  }
  uint64_t count = 0;
  int failure = 0;
  for (uint64_t word = start; word < end; word += step) {
    uint32_t raw = (uint32_t)word;
    const uint32_t target_words[] = {0x7f800000u, 0xff800000u, 0,
                                     0x80000000u, raw,         0x3f800000u,
                                     0xbf800000u};
    for (unsigned target = 0; target < 7; ++target) {
      if (!(targets & (UINT64_C(1) << target))) {
        continue;
      }
      float x, y;
      memcpy(&x, &raw, 4);
      memcpy(&y, &target_words[target], 4);
      float current = candidate(x, y), old = previous(x, y);
      uint32_t a, b;
      memcpy(&a, &current, 4);
      memcpy(&b, &old, 4);
      if (a != b) {
        fprintf(stderr,
                "adjacent mismatch input%08" PRIx32 " target%08" PRIx32
                " candidate%08" PRIx32 " previous%08" PRIx32 "\n",
                raw, target_words[target], a, b);
        failure = 1;
        break;
      }
      ++count;
    }
    if (failure) {
      break;
    }
  }
  int ending_mode = fegetround();
  if (fesetenv(&saved) || ending_mode != modes[mode]) {
    failure = 1;
  }
  if (!failure) {
    fputs(GMATH_ADJACENT_BASELINE_IDENTITY, stdout);
    printf("adjacent.compare %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64
           " %" PRIu64 " %" PRIu64 "\n",
           start, end, step, targets, mode, count);
  }
  return failure;
}
