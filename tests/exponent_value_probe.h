/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Shared C17 exact exponent reference/state checks.
 */
#ifndef GHOTI_IO_GMATH_TEST_EXPONENT_VALUE_PROBE_H
#define GHOTI_IO_GMATH_TEST_EXPONENT_VALUE_PROBE_H
#include "corpus_hash.h"
#include <errno.h>
#include <fenv.h>
#include <ghoti.io/math/basic.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Byte-counted lines reject embedded NUL and overlong/truncated records. */
static int expv_line(FILE * file, char * line, size_t size) {
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
static int expv_hex(const char * text, unsigned width, uint64_t * result) {
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
#if defined(GMATH_LOGB_REFERENCE) != defined(GMATH_LOGBF_REFERENCE)
#error "Configure both exponent reference functions together"
#endif
#ifdef GMATH_LOGB_REFERENCE
#ifndef GMATH_EXPONENT_BASELINE_IDENTITY
#error "Exponent reference identity is required"
#endif
#ifdef __cplusplus
extern "C" {
#endif
extern double GMATH_LOGB_REFERENCE(double);
extern float GMATH_LOGBF_REFERENCE(float);
#ifdef __cplusplus
}
#endif
#endif
static inline int expv_reference_alias(void) {
#ifdef GMATH_LOGB_REFERENCE
  double (*volatile current_d)(double) = gmath_logb;
  float (*volatile current_f)(float) = gmath_logbf;
  double (*volatile prior_d)(double) = GMATH_LOGB_REFERENCE;
  float (*volatile prior_f)(float) = GMATH_LOGBF_REFERENCE;
  return current_d == prior_d || current_f == prior_f;
#else
  return 0;
#endif
}
static int expv_invoke(uint64_t raw, uint64_t result, unsigned flags,
                       unsigned width, int mode, int seed, int error,
                       uint64_t * hash, int reference) {
#ifndef GMATH_LOGB_REFERENCE
  (void)reference;
#endif
  if (fesetround(mode) || feclearexcept(FE_ALL_EXCEPT) || feraiseexcept(seed)) {
    return 1;
  }
  int incoming = fetestexcept(FE_ALL_EXCEPT);
  errno = error;
  uint64_t got;
  if (width == 64) {
    double x;
    memcpy(&x, &raw, 8);
    double (*volatile fn)(double) = gmath_logb;
#ifdef GMATH_LOGB_REFERENCE
    if (reference) {
      fn = GMATH_LOGB_REFERENCE;
    }
#endif
    double y = fn(x);
    memcpy(&got, &y, 8);
  } else {
    uint32_t word = (uint32_t)raw, output;
    float x;
    memcpy(&x, &word, 4);
    float (*volatile fn)(float) = gmath_logbf;
#ifdef GMATH_LOGBF_REFERENCE
    if (reference) {
      fn = GMATH_LOGBF_REFERENCE;
    }
#endif
    float y = fn(x);
    memcpy(&output, &y, 4);
    got = output;
  }
  int native = (flags == 1 ? FE_INVALID : flags == 2 ? FE_DIVBYZERO : 0);
  int got_errno = errno, got_flags = fetestexcept(FE_ALL_EXCEPT),
      got_mode = fegetround();
  if (got != result || got_flags != (incoming | native) || got_errno != error ||
      got_mode != mode) {
    fprintf(stderr,
            "exponent mismatch width%u input %016" PRIx64 " result %016" PRIx64
            "/%016" PRIx64
            " implementation %s flags%x/%x errno%d/%d mode%d/%d\n",
            width, raw, got, result, reference ? "prior" : "current", got_flags,
            incoming | native, got_errno, error, got_mode, mode);
    return 1;
  }
  /* Portable result/order digest: actual flags/errno/mode were asserted above.
   * Incoming flag merges differ across machines; do not encode assumed states.
   */
  *hash = gmath_fnv_u64(*hash, got);
  return 0;
}
static int expv_call(uint64_t raw, uint64_t result, unsigned flags,
                     unsigned width, int mode, int seed, int error,
                     uint64_t * hash) {
  if (expv_invoke(raw, result, flags, width, mode, seed, error, hash, 0)) {
    return 1;
  }
#ifdef GMATH_LOGB_REFERENCE
  uint64_t ignored = GMATH_FNV_BASIS;
  if (expv_invoke(raw, result, flags, width, mode, seed, error, &ignored, 1)) {
    return 1;
  }
#endif
  return 0;
}
static int expv_metadata(const char * line, uint64_t * entries) {
  char seed[32], count[32], rows[32], fresh[6], extra;
  if (sscanf(line, "# seed %31s count %31s fresh %5s entries %31s %c", seed,
             count, fresh, rows, &extra) != 4 ||
      (strcmp(fresh, "False") && strcmp(fresh, "True"))) {
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
  if (values[1] > 200000 || values[2] < 1000 || values[2] > 300000) {
    return 0;
  }
  *entries = values[2];
  return 1;
}
static int expv_selected(uint64_t a, unsigned width, uint64_t index) {
  unsigned p = width == 64 ? 52u : 23u, bias = width == 64 ? 1023u : 127u;
  uint64_t hidden = UINT64_C(1) << p, one = (uint64_t)bias << p,
           two = (uint64_t)(bias + 1) << p;
  uint64_t inf = (uint64_t)(width == 64 ? 2047u : 255u) << p;
  return index % 61 == 0 || a >= inf || a == 0 || a == 1 || a == 2 || a == 3 ||
         a == hidden - 1 || a == hidden || a == hidden + 1 || a == one - 1 ||
         a == one || a == one + 1 || a == two - 1 || a == two || a == two + 1 ||
         a == inf - 1;
}
static int expv_probe(const char * directory, unsigned width, int verbose) {
  fenv_t saved;
  int saved_errno = errno;
  if (fegetenv(&saved)) {
    return 1;
  }
  FILE * file = NULL;
  int status = 1;
  char path[4096], line[256];
  uint64_t hash = GMATH_FNV_BASIS, state = GMATH_FNV_BASIS, entries = 0,
           count = 0, calls = 0, previous = 0;
  const char * name = width == 64 ? "logb" : "logbf";
  if (snprintf(path, sizeof path, "%s/%s-special.corpus", directory, name) >=
      (int)sizeof path) {
    goto done;
  }
  if (expv_reference_alias()) {
    fputs("exponent reference aliases current function\n", stderr);
    goto done;
  }
  file = fopen(path, "rb");
  if (!file) {
    fprintf(stderr, "missing exponent corpus: %s\n", path);
    goto done;
  }
  if (expv_line(file, line, sizeof line) != 1 ||
      strcmp(line, "# Pinned oracle: exponent_value MPFR 4.2.2 gmpy2 2.3.2")) {
    goto done;
  }
  {
    char expected[64];
    snprintf(expected, sizeof expected, "# function %s", name);
    if (expv_line(file, line, sizeof line) != 1 || strcmp(line, expected)) {
      goto done;
    }
  }
  if (expv_line(file, line, sizeof line) != 1 ||
      !expv_metadata(line, &entries)) {
    goto done;
  }
  if (expv_line(file, line, sizeof line) != 1 ||
      strcmp(line, "# input result normalized-flags")) {
    goto done;
  }
  for (;;) {
    int read = expv_line(file, line, sizeof line);
    if (!read) {
      break;
    }
    if (read < 0) {
      goto done;
    }
    char x[18], y[18], flag[3], extra;
    uint64_t raw, result;
    if (sscanf(line, "%17s %17s %2s %c", x, y, flag, &extra) != 3 ||
        !expv_hex(x, width, &raw) || !expv_hex(y, width, &result) ||
        (strcmp(flag, "0") && strcmp(flag, "1") && strcmp(flag, "2")) ||
        (count && raw <= previous) || count >= entries) {
      goto done;
    }
    previous = raw;
    unsigned flags = (unsigned)(flag[0] - '0');
    uint64_t sign = UINT64_C(1) << (width - 1), a = raw & (sign - 1);
    uint64_t inf =
        width == 64 ? UINT64_C(0x7ff0000000000000) : UINT64_C(0x7f800000);
    uint64_t quiet =
        width == 64 ? UINT64_C(0x0008000000000000) : UINT64_C(0x00400000);
    unsigned expected_flags =
        a == 0 ? 2u : (a > inf && !(raw & quiet) ? 1u : 0u);
    if (flags != expected_flags) {
      goto done;
    }
    if (a > inf && result != (inf | quiet)) {
      goto done;
    }
    if (a == inf && result != inf) {
      goto done;
    }
    if (a == 0 && result != (sign | inf)) {
      goto done;
    }
    if (a && a < inf && (result & (sign - 1)) >= inf) {
      goto done;
    }
    if (expv_call(raw, result, flags, width, FE_TONEAREST, 0, 0, &hash)) {
      goto done;
    }
    count++;
    {
      int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
      int incoming_flags[] = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW,
                              FE_UNDERFLOW, FE_INEXACT};
      unsigned sets = expv_selected(a, width, count) ? 32u : 1u;
      for (unsigned mode = 0; mode < 4; mode++) {
        for (unsigned subset = 0; subset < sets; subset++) {
          int seed = 0;
          for (unsigned b = 0; b < 5; b++) {
            if (subset & (1u << b)) {
              seed |= incoming_flags[b];
            }
          }
          for (unsigned error = 0; error < 2; error++) {
            if (expv_call(raw, result, flags, width, modes[mode], seed,
                          error ? 733 : 0, &state)) {
              goto done;
            }
            calls++;
          }
        }
      }
    }
  }
  if (ferror(file) || count != entries) {
    goto done;
  }
  if (verbose) {
    printf("exponent.%s %016" PRIx64 " %" PRIu64 " state %016" PRIx64
           " %" PRIu64 " from %s\n",
           name, hash, count, state, calls, directory);
  }
  status = 0;
done:
  if (status) {
    fprintf(stderr, "exponent probe failed: %s\n", path);
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
