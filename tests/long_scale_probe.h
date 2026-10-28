/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Width-aware exact native-long scaling and caller-state validation.
 */
#ifndef GHOTI_IO_GMATH_TEST_LONG_SCALE_PROBE_H
#define GHOTI_IO_GMATH_TEST_LONG_SCALE_PROBE_H
#include "corpus_hash.h"
#include <errno.h>
#include <fenv.h>
#include <ghoti.io/math/basic.h>
#include <inttypes.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef __cplusplus
#define LS_STATIC_ASSERT static_assert
#else
#define LS_STATIC_ASSERT _Static_assert
#endif
LS_STATIC_ASSERT((LONG_MAX == INT32_MAX && LONG_MIN == INT32_MIN) ||
                     (LONG_MAX == INT64_MAX && LONG_MIN == INT64_MIN),
                 "Long scaling probe requires signed long32/64");
#undef LS_STATIC_ASSERT
static int ls_line(FILE * file, char * line, size_t size) {
  size_t n = 0;
  int c;
  while ((c = fgetc(file)) != EOF && c != '\n') {
    if (!c || n + 1 >= size) {
      return -1;
    }
    line[n++] = (char)c;
  }
  line[n] = 0;
  return c == EOF ? (n ? -1 : 0) : 1;
}
static int ls_hex(const char * text, unsigned width, uint64_t * result) {
  if (strlen(text) != width / 4) {
    return 0;
  }
  uint64_t v = 0;
  for (const char * p = text; *p; p++) {
    unsigned d = (unsigned char)*p;
    if (d >= '0' && d <= '9') {
      d -= '0';
    } else if (d >= 'a' && d <= 'f') {
      d = d - 'a' + 10u;
    } else {
      return 0;
    }
    v = (v << 4) | d;
  }
  *result = v;
  return 1;
}
static int ls_decimal(const char * text, uint64_t maximum, uint64_t * value) {
  if (!*text || (text[0] == '0' && text[1])) {
    return 0;
  }
  uint64_t n = 0;
  for (const char * p = text; *p; p++) {
    unsigned c = (unsigned char)*p;
    if (c < '0' || c > '9' || n > (maximum - (c - '0')) / 10) {
      return 0;
    }
    n = n * 10 + (c - '0');
  }
  *value = n;
  return 1;
}
static int64_t ls_signed(uint64_t word) {
  return word <= INT64_MAX ? (int64_t)word : -1 - (int64_t)(~word);
}
static int ls_eligible(int64_t n) {
  return n >= (int64_t)LONG_MIN && n <= (int64_t)LONG_MAX;
}
static int ls_metadata(const char * line, uint64_t * entries) {
  char seed[22], count[8], fresh[7], number[9], extra;
  uint64_t unused;
  if (sscanf(line, "# seed %21s count %7s fresh %6s entries %8s %c", seed,
             count, fresh, number, &extra) != 4) {
    return 0;
  }
  if (!ls_decimal(seed, UINT64_MAX, &unused) ||
      !ls_decimal(count, 50000, &unused) ||
      (strcmp(fresh, "True") && strcmp(fresh, "False")) ||
      !ls_decimal(number, 2000000, entries) || !*entries) {
    return 0;
  }
  return 1;
}
static int ls_selected(uint64_t raw, int64_t n, unsigned width,
                       uint64_t index) {
  unsigned p = width == 64 ? 52u : 23u, bias = width == 64 ? 1023u : 127u;
  uint64_t sign = UINT64_C(1) << (width - 1), a = raw & (sign - 1);
  uint64_t inf = (width == 64 ? UINT64_C(2047) : UINT64_C(255)) << p;
  if (index % 127 == 0 || a >= inf) {
    return 1;
  }
  int boundary = a == 0 || a == 1 || a == 3 || a == 5 ||
                 a == ((UINT64_C(1) << p) - 1) || a == (UINT64_C(1) << p) ||
                 a == ((UINT64_C(1) << (p + 1)) - 1) ||
                 a == ((uint64_t)bias << p) || a == inf - 1;
  if (!boundary) {
    return 0;
  }
  return n == INT64_MIN || n == -INT64_C(4294967296) || n == INT32_MIN ||
         n == -5000 || n == -512 || n == -1 || n == 0 || n == 1 || n == 512 ||
         n == 5000 || n == INT32_MAX || n == INT64_C(4294967296) ||
         n == INT64_MAX;
}
static int ls_call(uint64_t raw, int64_t n, uint64_t result, unsigned flags,
                   unsigned width, int mode, int seed, int error,
                   uint64_t * hash) {
  if (!ls_eligible(n) || fesetround(mode) || feclearexcept(FE_ALL_EXCEPT) ||
      feraiseexcept(seed)) {
    return 1;
  }
  int incoming = fetestexcept(FE_ALL_EXCEPT);
  errno = error;
  uint64_t got;
  if (width == 64) {
    double x, y;
    memcpy(&x, &raw, 8);
    double (*volatile fn)(double, long) = gmath_scalbln;
    y = fn(x, (long)n);
    memcpy(&got, &y, 8);
  } else {
    uint32_t word = (uint32_t)raw, out;
    float x, y;
    memcpy(&x, &word, 4);
    float (*volatile fn)(float, long) = gmath_scalblnf;
    y = fn(x, (long)n);
    memcpy(&out, &y, 4);
    got = out;
  }
  int native =
      ((flags & 1u) ? FE_INVALID : 0) | ((flags & 4u) ? FE_OVERFLOW : 0) |
      ((flags & 8u) ? FE_UNDERFLOW : 0) | ((flags & 16u) ? FE_INEXACT : 0);
  int got_errno = errno, got_flags = fetestexcept(FE_ALL_EXCEPT),
      got_mode = fegetround();
  if (got != result || got_errno != error || got_flags != (incoming | native) ||
      got_mode != mode) {
    fprintf(stderr,
            "long scale mismatch width%u n%" PRId64 " input%016" PRIx64
            " result%016" PRIx64 "/%016" PRIx64
            " flags%x/%x errno%d/%d mode%d/%d\n",
            width, n, raw, got, result, got_flags, incoming | native, got_errno,
            error, got_mode, mode);
    return 1;
  }
  *hash = gmath_fnv_u64(*hash, got);
  return 0;
}
static int ls_classes(uint64_t raw, int64_t n, uint64_t result, unsigned flags,
                      unsigned width) {
  unsigned p = width == 64 ? 52u : 23u;
  uint64_t sign = UINT64_C(1) << (width - 1);
  uint64_t a = raw & (sign - 1), r = result & (sign - 1),
           inf = (width == 64 ? UINT64_C(2047) : UINT64_C(255)) << p;
  uint64_t hidden = UINT64_C(1) << p, quiet = UINT64_C(1) << (p - 1);
  if (a > inf) {
    return result == (inf | quiet) && flags == ((a & quiet) ? 0u : 1u);
  }
  if (!a || a == inf) {
    return result == raw && flags == 0;
  }
  if ((result & sign) != (raw & sign) || r > inf) {
    return 0;
  }
  if (n == 0) {
    return result == raw && flags == 0;
  }
  if (r == inf) {
    return flags == 20;
  }
  if (!r) {
    return flags == 24;
  }
  if (flags == 0) {
    return 1;
  }
  if (flags == 16) {
    return width == 32 && r == hidden;
  }
  if (flags == 24) {
    return width == 64 ? r <= hidden : r < hidden;
  }
  return 0;
}
static int ls_probe(const char * directory, unsigned width, int verbose) {
  fenv_t saved;
  int saved_errno = errno;
  if (fegetenv(&saved)) {
    return 1;
  }
  FILE * file = NULL;
  int status = 1;
  char path[4096], line[256];
  const char * name = width == 64 ? "scalbln" : "scalblnf";
  uint64_t entries = 0, rows = 0, count = 0, skipped = 0, calls = 0,
           previous = 0;
  int64_t previous_n = 0;
  uint64_t hash = GMATH_FNV_BASIS, state = GMATH_FNV_BASIS;
  if (snprintf(path, sizeof path, "%s/%s-special.corpus", directory, name) >=
      (int)sizeof path) {
    goto done;
  }
  file = fopen(path, "rb");
  if (!file) {
    goto done;
  }
  if (ls_line(file, line, sizeof line) != 1 ||
      strcmp(line, "# Pinned oracle: long_scale MPFR 4.2.2 gmpy2 2.3.2")) {
    goto done;
  }
  {
    char expected[64];
    snprintf(expected, sizeof expected, "# function %s", name);
    if (ls_line(file, line, sizeof line) != 1 || strcmp(line, expected)) {
      goto done;
    }
  }
  if (ls_line(file, line, sizeof line) != 1 || !ls_metadata(line, &entries)) {
    goto done;
  }
  if (ls_line(file, line, sizeof line) != 1 ||
      strcmp(line, "# raw x signed64 n result normalized-flags")) {
    goto done;
  }
  for (;;) {
    int read = ls_line(file, line, sizeof line);
    if (!read) {
      break;
    }
    if (read < 0) {
      goto done;
    }
    char x[18], nw[18], y[18], flag[4], extra;
    uint64_t raw, nword, result, parsed_flags;
    if (sscanf(line, "%17s %17s %17s %3s %c", x, nw, y, flag, &extra) != 4 ||
        !ls_hex(x, width, &raw) || !ls_hex(nw, 64, &nword) ||
        !ls_hex(y, width, &result) || !ls_decimal(flag, 24, &parsed_flags) ||
        rows >= entries) {
      goto done;
    }
    int64_t n = ls_signed(nword);
    unsigned flags = (unsigned)parsed_flags;
    if ((rows && (raw < previous || (raw == previous && n <= previous_n))) ||
        !ls_classes(raw, n, result, flags, width)) {
      goto done;
    }
    previous = raw;
    previous_n = n;
    ++rows;
    if (!ls_eligible(n)) {
      ++skipped;
      continue;
    }
    if (ls_call(raw, n, result, flags, width, FE_TONEAREST, 0, 0, &hash)) {
      goto done;
    }
    ++count;
    int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
    int native[] = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
                    FE_INEXACT};
    unsigned sets = ls_selected(raw, n, width, rows) ? 32u : 1u;
    for (unsigned m = 0; m < 4; m++) {
      for (unsigned subset = 0; subset < sets; subset++) {
        int seed = 0;
        for (unsigned b = 0; b < 5; b++) {
          if (subset & (1u << b)) {
            seed |= native[b];
          }
        }
        for (unsigned e = 0; e < 2; e++) {
          if (ls_call(raw, n, result, flags, width, modes[m], seed, e ? 733 : 0,
                      &state)) {
            goto done;
          }
          ++calls;
        }
      }
    }
  }
  if (ferror(file) || rows != entries || count + skipped != entries || !count) {
    goto done;
  }
  if (verbose) {
    printf("longscale.%u.long%u %016" PRIx64 " %" PRIu64 " skipped %" PRIu64
           " state %016" PRIx64 " %" PRIu64 " from %s\n",
           width, (unsigned)(sizeof(long) * CHAR_BIT), hash, count, skipped,
           state, calls, directory);
  }
  status = 0;
done:
  if (file && fclose(file)) {
    status = 1;
  }
  if (status) {
    fprintf(stderr, "long scale probe failed width%u: %s\n", width, path);
  }
  if (fesetenv(&saved)) {
    status = 1;
  }
  errno = saved_errno;
  return status;
}
#endif
