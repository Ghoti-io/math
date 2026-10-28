/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Shared C17 raw nearby-integer value/state checks; actual flags asserted
 * inline.
 */
#ifndef GMATH_TEST_NEARBY_PROBE_H
#define GMATH_TEST_NEARBY_PROBE_H
#include "corpus_hash.h"
#include <errno.h>
#include <fenv.h>
#include <ghoti.io/math/basic.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int nb_line(FILE * file, char * line, size_t size) {
  size_t n = 0;
  int c;
  while ((c = fgetc(file)) != EOF && c != '\n') {
    if (!c || n + 1 >= size) {
      return -1;
    }
    line[n++] = (char)c;
  }
  line[n] = 0;
  if (c == EOF) {
    return n ? -1 : 0;
  }
  return 1;
}
static int nb_hex(const char * text, unsigned width, uint64_t * result) {
  if (strlen(text) != width / 4) {
    return 0;
  }
  uint64_t v = 0;
  for (const char * p = text; *p; p++) {
    unsigned d = (unsigned char)*p;
    if (d >= '0' && d <= '9') {
      d -= '0';
    }
    else if (d >= 'a' && d <= 'f') {
      d = d - 'a' + 10;
    }
    else {
      return 0;
    }
    v = (v << 4) | d;
  }
  *result = v;
  return 1;
}
static int nb_metadata(const char * line, uint64_t * entries) {
  char seed[32], count[32], rows[32], fresh[6], extra;
  if (sscanf(line, "# seed %31s count %31s fresh %5s entries %31s %c", seed,
          count, fresh, rows, &extra) != 4 ||
      (strcmp(fresh, "false") && strcmp(fresh, "true"))) {
    return 0;
  }
  const char * numbers[] = {seed, count, rows};
  uint64_t values[3];
  for (unsigned i = 0; i < 3; i++) {
    uint64_t n = 0;
    for (const char * p = numbers[i]; *p; p++) {
      if (*p < '0' || *p > '9' ||
          n > (UINT64_MAX - (unsigned)(*p - '0')) / 10) {
        return 0;
      }
      n = n * 10 + (unsigned)(*p - '0');
    }
    values[i] = n;
  }
  if (values[1] > 50000 || values[2] < 1000 || values[2] > 150000) {
    return 0;
  }
  *entries = values[2];
  return 1;
}
/* Control-only snapshots. Architectural status/diagnostic fields are excluded;
 * the standard C exception flags are asserted separately. PPC covers binary
 * controls only (old mffs upper words need not describe decimal controls).
 * Unknown ports retain the C mode/flag assertions.
 */
static uint64_t nb_controls(void) {
#if (defined(__GNUC__) || defined(__clang__)) && defined(__SSE__) &&           \
    (defined(__i386__) || defined(__x86_64__))
  uint32_t raw;
  __asm__ volatile("stmxcsr %0" : "=m"(raw) : : "memory");
  return raw & UINT32_C(0xffffffc0);
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
static int nb_call(uint64_t input, uint64_t expected, unsigned invalid,
    unsigned width, int mode, int subset, int error, uint64_t * hash) {
  const int flags[] = {
      FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW, FE_INEXACT};
  int seed = 0;
  for (unsigned b = 0; b < 5; b++)
    if (subset & (1 << b))
      seed |= flags[b];
  if (fesetround(mode) || feclearexcept(FE_ALL_EXCEPT) || feraiseexcept(seed))
    return 1;
  int incoming = fetestexcept(FE_ALL_EXCEPT);
  uint64_t controls_before = nb_controls();
  errno = error;
  uint64_t got;
  if (width == 64) {
    double x;
    memcpy(&x, &input, 8);
    double (*volatile fn)(double) = gmath_nearbyint;
    double y = fn(x);
    memcpy(&got, &y, 8);
  }
  else {
    uint32_t word = (uint32_t)input, result;
    float x;
    memcpy(&x, &word, 4);
    float (*volatile fn)(float) = gmath_nearbyintf;
    float y = fn(x);
    memcpy(&result, &y, 4);
    got = result;
  }
  int got_errno = errno, got_flags = fetestexcept(FE_ALL_EXCEPT),
      got_mode = fegetround();
  int want = incoming | (invalid ? FE_INVALID : 0);
  uint64_t controls_after = nb_controls();
  if (controls_before != controls_after) {
    fprintf(stderr,
        "nearby control-state mismatch width%u input%016" PRIx64
        " control%016" PRIx64 "/%016" PRIx64 "\n",
        width, input, controls_after, controls_before);
    return 1;
  }
  if (got != expected || got_flags != want || got_errno != error ||
      got_mode != mode) {
    fprintf(stderr,
        "nearby mismatch width%u input%016" PRIx64 " got%016" PRIx64
        "/%016" PRIx64 " flags%x/%x errno%d/%d mode%d/%d\n",
        width, input, got, expected, got_flags, want, got_errno, error,
        got_mode, mode);
    return 1;
  }
  *hash = gmath_fnv_u64(*hash, got);
  return 0;
}
static int nb_probe(const char * directory, unsigned width, int print) {
  fenv_t saved;
  int error = errno, status = 1;
  FILE * file = NULL;
  char path[4096], line[256];
  if (fegetenv(&saved))
    return 1;
  uint64_t entries = 0, count = 0, previous = 0, hash = GMATH_FNV_BASIS,
           state = GMATH_FNV_BASIS, calls = 0;
  unsigned p = width == 64 ? 52u : 23u, bias = width == 64 ? 1023u : 127u;
  uint64_t sign = UINT64_C(1) << (width - 1),
           inf = (width == 64 ? UINT64_C(2047) : UINT64_C(255)) << p,
           quiet = UINT64_C(1) << (p - 1);
  const char * name = width == 64 ? "nearbyint" : "nearbyintf";
  if (snprintf(path, sizeof path, "%s/%s-special.corpus", directory, name) >=
      (int)sizeof path)
    goto done;
  file = fopen(path, "rb");
  if (!file)
    goto done;
  if (nb_line(file, line, sizeof line) != 1 ||
      strcmp(line, "# Pinned oracle: nearby MPFR 4.2.2 gmpy2 2.3.2"))
    goto done;
  {
    char header[80];
    snprintf(header, sizeof header, "# function %s", name);
    if (nb_line(file, line, sizeof line) != 1 || strcmp(line, header))
      goto done;
  }
  if (nb_line(file, line, sizeof line) != 1 || !nb_metadata(line, &entries))
    goto done;
  if (nb_line(file, line, sizeof line) != 1 ||
      strcmp(
          line, "# input nearest downward upward towardzero normalized-flags"))
    goto done;
  for (;;) {
    int read = nb_line(file, line, sizeof line);
    if (!read)
      break;
    if (read < 0)
      goto done;
    char text[5][18], flag[3], extra;
    uint64_t word[5];
    if (sscanf(line, "%17s %17s %17s %17s %17s %2s %c", text[0], text[1],
            text[2], text[3], text[4], flag, &extra) != 6)
      goto done;
    for (unsigned i = 0; i < 5; i++)
      if (!nb_hex(text[i], width, &word[i]))
        goto done;
    if (strcmp(flag, "0") && strcmp(flag, "1"))
      goto done;
    if (count >= entries || (count && word[0] <= previous))
      goto done;
    previous = word[0];
    count++;
    uint64_t a = word[0] & (sign - 1);
    unsigned invalid = (unsigned)(flag[0] - '0');
    if (invalid != (unsigned)(a > inf && !(a & quiet)))
      goto done;
    for (unsigned i = 1; i < 5; i++) {
      if (a > inf && word[i] != (inf | quiet))
        goto done;
      if ((a == 0 || a == inf) && word[i] != word[0])
        goto done;
      if (a < inf && (word[i] & (sign - 1)) >= inf)
        goto done;
    }
    uint64_t half = (uint64_t)(bias - 1) << p, one = (uint64_t)bias << p;
    unsigned sets = count % 61 == 0 || a >= inf || a == 0 || a == 1 ||
            a == (UINT64_C(1) << p) - 1 || a == (UINT64_C(1) << p) ||
            a == half - 1 || a == half || a == half + 1 || a == one - 1 ||
            a == one || a == one + 1
        ? 32u
        : 1u;
    const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
    for (unsigned mode = 0; mode < 4; mode++)
      for (unsigned subset = 0; subset < sets; subset++)
        for (unsigned err = 0; err < 2; err++) {
          if (nb_call(word[0], word[mode + 1], invalid, width, modes[mode],
                  (int)subset, err ? 733 : 0, &state))
            goto done;
          if (!mode && !subset && !err)
            hash = gmath_fnv_u64(hash, word[1]);
          calls++;
        }
  }
  if (ferror(file) || count != entries)
    goto done;
  if (print)
    printf("nearby.%s %016" PRIx64 " %" PRIu64 " state %016" PRIx64 " %" PRIu64
           " from %s\n",
        name, hash, count, state, calls, directory);
  status = 0;
done:
  if (file)
    fclose(file);
  if (fesetenv(&saved))
    status = 1;
  errno = error;
  if (status)
    fprintf(stderr,
        "nearby probe failed width%u from %s after%" PRIu64 " rows\n", width,
        directory, count);
  return status;
}
#endif
