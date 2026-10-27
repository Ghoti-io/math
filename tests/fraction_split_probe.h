/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Shared C17 raw reference/state probe; the unit test and emulated targets use
 * identical checks. Whole-file SHA is checked separately by the default gate.
 */
#ifndef GHOTI_IO_GMATH_TEST_FRACTION_SPLIT_PROBE_H
#define GHOTI_IO_GMATH_TEST_FRACTION_SPLIT_PROBE_H
#include "corpus_hash.h"
#include <errno.h>
#include <fenv.h>
#include <ghoti.io/math/basic.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint64_t split_bits(double x) {
  uint64_t u;
  memcpy(&u, &x, 8);
  return u;
}
static uint32_t split_fbits(float x) {
  uint32_t u;
  memcpy(&u, &x, 4);
  return u;
}
/* Byte-counted lines reject embedded NUL and overlong/truncated records. */
static int split_line(FILE * file, char * line, size_t size) {
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
static int split_hex(const char * text, unsigned width, uint64_t * result) {
  if (strlen(text) != width / 4) {
    return 0;
  }
  uint64_t v = 0;
  for (const char * p = text; *p; p++) {
    unsigned d = (unsigned char)*p;
    if (d >= '0' && d <= '9') {
      d -= '0';
    } else if (d >= 'a' && d <= 'f') {
      d = d - 'a' + 10;
    } else {
      return 0;
    }
    v = (v << 4) | d;
  }
  *result = v;
  return 1;
}
static int split_call(uint64_t raw, uint64_t fraction, uint64_t whole,
                      int invalid, unsigned width, int mode, int seed,
                      int error, int omitted, uint64_t * hash) {
  double dx = 0;
  float fx = 0;
  if (width == 64) {
    memcpy(&dx, &raw, sizeof dx);
  } else {
    uint32_t word = (uint32_t)raw;
    memcpy(&fx, &word, sizeof fx);
  }
  if (fesetround(mode) || feclearexcept(FE_ALL_EXCEPT) || feraiseexcept(seed)) {
    return 1;
  }
  int incoming = fetestexcept(FE_ALL_EXCEPT);
  errno = error;
  uint64_t got, integer = UINT64_C(0xdeadbeef);
  if (width == 64) {
    double output;
    uint64_t sentinel = UINT64_C(0x7ff80000deadbeef);
    memcpy(&output, &sentinel, sizeof output);
    double (*volatile fn)(double, double *) = gmath_modf;
    got = split_bits(fn(dx, omitted ? NULL : &output));
    if (!omitted) {
      integer = split_bits(output);
    }
  } else {
    float output;
    uint32_t sentinel = UINT32_C(0x7fc0dead);
    memcpy(&output, &sentinel, sizeof output);
    float (*volatile fn)(float, float *) = gmath_modff;
    got = split_fbits(fn(fx, omitted ? NULL : &output));
    if (!omitted) {
      integer = split_fbits(output);
    }
  }
  int flags = fetestexcept(FE_ALL_EXCEPT), saved_errno = errno,
      saved_mode = fegetround();
  if (got != fraction || (!omitted && integer != whole) ||
      flags != (incoming | (invalid ? FE_INVALID : 0)) ||
      saved_errno != error || saved_mode != mode) {
    fprintf(stderr,
            "split mismatch width%u input %016" PRIx64
            " omitted%d mode%d flags%x/%x errno%d/%d\n",
            width, raw, omitted, mode, flags,
            incoming | (invalid ? FE_INVALID : 0), saved_errno, error);
    return 1;
  }
  *hash = gmath_fnv_u64(*hash, got);
  if (!omitted) {
    *hash = gmath_fnv_u64(*hash, integer);
  }
  return 0;
}

/* Returns failure after restoring the caller's environment, including errno. */
static int split_probe(const char * directory, unsigned width, int verbose) {
  fenv_t saved;
  int saved_errno = errno;
  if (fegetenv(&saved)) {
    return 1;
  }
  char path[4096], line[256];
  FILE * file = NULL;
  int status = 1;
  const char * name = width == 64 ? "modf" : "modff";
  uint64_t hash = GMATH_FNV_BASIS, state = GMATH_FNV_BASIS;
  uint64_t count = 0, calls = 0, previous = 0, entries = 0;
  if (snprintf(path, sizeof path, "%s/%s-special.corpus", directory, name) >=
      (int)sizeof path) {
    goto done;
  }
  file = fopen(path, "rb");
  if (!file) {
    fprintf(stderr, "missing split corpus: %s\n", path);
    goto done;
  }
  if (split_line(file, line, sizeof line) != 1 ||
      strcmp(line, "# Pinned oracle: fraction_split MPFR 4.2.2 gmpy2 2.3.2")) {
    goto done;
  }
  if (split_line(file, line, sizeof line) != 1) {
    goto done;
  }
  {
    char expected[64];
    snprintf(expected, sizeof expected, "# function %s", name);
    if (strcmp(line, expected)) {
      goto done;
    }
  }
  if (split_line(file, line, sizeof line) != 1) {
    goto done;
  }
  {
    char seed_text[32], count_text[32], rows_text[32], fresh[6], extra;
    if (sscanf(line, "# seed %31s count %31s fresh %5s entries %31s %c",
               seed_text, count_text, fresh, rows_text, &extra) != 4 ||
        (strcmp(fresh, "False") && strcmp(fresh, "True"))) {
      goto done;
    }
    const char * numbers[] = {seed_text, count_text, rows_text};
    uint64_t numbers_out[3];
    for (unsigned i = 0; i < 3; i++) {
      uint64_t n = 0;
      for (const char * p = numbers[i]; *p; p++) {
        if (*p < '0' || *p > '9' ||
            n > (UINT64_MAX - (unsigned)(*p - '0')) / 10) {
          goto done;
        }
        n = n * 10 + (unsigned)(*p - '0');
      }
      numbers_out[i] = n;
    }
    if (numbers_out[1] > 200000 || numbers_out[2] < 1000 ||
        numbers_out[2] > 300000) {
      goto done;
    }
    entries = numbers_out[2];
  }
  if (split_line(file, line, sizeof line) != 1 ||
      strcmp(line, "# input fraction integral invalid")) {
    goto done;
  }
  for (;;) {
    int read = split_line(file, line, sizeof line);
    if (!read) {
      break;
    }
    if (read < 0) {
      goto done;
    }
    char x[18], f[18], i[18], flag[3], extra;
    uint64_t raw, fraction, whole;
    if (sscanf(line, "%17s %17s %17s %2s %c", x, f, i, flag, &extra) != 4 ||
        !split_hex(x, width, &raw) || !split_hex(f, width, &fraction) ||
        !split_hex(i, width, &whole) ||
        (strcmp(flag, "0") && strcmp(flag, "1")) ||
        (count && raw <= previous) || count >= entries) {
      goto done;
    }
    int invalid = flag[0] == '1';
    previous = raw;
    uint64_t sign = UINT64_C(1) << (width - 1),
             inf = width == 64 ? UINT64_C(0x7ff0000000000000)
                               : UINT64_C(0x7f800000);
    uint64_t quiet =
        width == 64 ? UINT64_C(0x0008000000000000) : UINT64_C(0x00400000);
    uint64_t a = raw & (sign - 1);
    if (invalid != (a > inf && !(raw & quiet))) {
      goto done;
    }
    if (a > inf && (fraction != (inf | quiet) || whole != (inf | quiet))) {
      goto done;
    }
    if (a <= inf &&
        ((fraction & sign) != (raw & sign) || (whole & sign) != (raw & sign))) {
      goto done;
    }
    if (split_call(raw, fraction, whole, invalid, width, FE_TONEAREST, 0, 0, 0,
                   &hash)) {
      goto done;
    }
    count++;
    /* All reference rows in all four modes; extra incoming states for a
     * reproducible subset and every nonfinite. Requested flag combinations
     * may merge on hardware; compare actual incoming flags, not assumptions. */
    {
      int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
      int flags[] = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
                     FE_INEXACT};
      for (unsigned mode = 0; mode < 4; mode++) {
        unsigned sets = (count % 61 == 0 || a >= inf) ? 32u : 1u;
        for (unsigned subset = 0; subset < sets; subset++) {
          int seed = 0;
          for (unsigned b = 0; b < 5; b++) {
            if (subset & (1u << b)) {
              seed |= flags[b];
            }
          }
          for (unsigned err = 0; err < 2; err++) {
            for (int omitted = 0; omitted < 2; omitted++) {
              if (split_call(raw, fraction, whole, invalid, width, modes[mode],
                             seed, err ? 731 : 0, omitted, &state)) {
                goto done;
              }
              calls++;
            }
          }
        }
      }
    }
  }
  if (ferror(file) || count != entries) {
    goto done;
  }
  if (verbose) {
    printf("split.%s %016" PRIx64 " %" PRIu64 " state %016" PRIx64 " %" PRIu64
           " from %s\n",
           name, hash, count, state, calls, directory);
  }
  status = 0;
done:
  if (status) {
    fprintf(stderr, "split probe failed: %s\n", path);
  }
  if (file) {
    fclose(file);
  }
  if (fesetenv(&saved)) {
    status = 1;
  }
  errno = saved_errno;
  return status;
}
#endif
