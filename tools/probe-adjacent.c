/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Raw adjacent values plus selected all-mode/incoming-state checks.
 */
#include "../tests/corpus_hash.h"
#include <errno.h>
#include <fenv.h>
#include <ghoti.io/math/basic.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(GMATH_NEXTAFTER_REFERENCE) != defined(GMATH_NEXTAFTERF_REFERENCE)
#error "Both adjacent reference functions must be configured together"
#endif
#ifdef GMATH_NEXTAFTER_REFERENCE
#ifndef GMATH_ADJACENT_BASELINE_IDENTITY
#error "Declared baseline identity is required"
#endif
extern double GMATH_NEXTAFTER_REFERENCE(double, double);
extern float GMATH_NEXTAFTERF_REFERENCE(float, float);
#endif
/* Count input bytes explicitly: C string functions alone hide embedded NULs. */
static int read_line(FILE * input, char * line, size_t capacity) {
  size_t size = 0;
  int byte;
  while ((byte = fgetc(input)) != EOF) {
    if (byte == 0 || size + 1 >= capacity) {
      return -1;
    }
    line[size++] = (char)byte;
    if (byte == '\n') {
      line[size] = '\0';
      return 1;
    }
  }
  line[size] = '\0';
  if (ferror(input)) {
    return -1;
  }
  return size ? 1 : 0;
}
static int native_flags(uint64_t flags) {
  return ((flags & 1u) ? FE_INVALID : 0) | ((flags & 4u) ? FE_OVERFLOW : 0) |
         ((flags & 8u) ? FE_UNDERFLOW : 0) | ((flags & 16u) ? FE_INEXACT : 0);
}
static int selected(uint64_t x, uint64_t y, uint64_t index, int single) {
  if (index % 127u == 0) {
    return 1;
  }
  uint64_t sign = single ? UINT64_C(0x80000000) : UINT64_C(0x8000000000000000);
  uint64_t inf = single ? UINT64_C(0x7f800000) : UINT64_C(0x7ff0000000000000);
  uint64_t quiet = single ? UINT64_C(0x00400000) : UINT64_C(0x0008000000000000);
  uint64_t minimum =
      single ? UINT64_C(0x00800000) : UINT64_C(0x0010000000000000);
  uint64_t one = single ? UINT64_C(0x3f800000) : UINT64_C(0x3ff0000000000000);
  const uint64_t points[] = {
      0,   1,       2,   3,       minimum - 1, minimum,        minimum + 1,
      one, inf - 1, inf, inf | 1, inf | quiet, inf | quiet | 1};
  int a = 0, b = 0;
  for (unsigned i = 0; i < sizeof points / sizeof *points; ++i) {
    if ((x & ~sign) == points[i]) {
      a = 1;
    }
    if ((y & ~sign) == points[i]) {
      b = 1;
    }
  }
  return a && b;
}
static int parse(const char * line, uint64_t words[4]) {
  const unsigned char * p = (const unsigned char *)line;
  for (unsigned field = 0; field < 4; ++field) {
    uint64_t word = 0;
    for (unsigned i = 0; i < 16; ++i) {
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
    if (field < 3 && *p++ != ' ') {
      return 0;
    }
  }
  return *p == '\0' || (*p == '\n' && p[1] == '\0');
}
static int invoke_impl(const uint64_t w[4], int single, int mode, int seed,
                       int error_seed, uint64_t * hash, int reference) {
#ifndef GMATH_NEXTAFTER_REFERENCE
  (void)reference;
#endif
  if (fesetround(mode) || feclearexcept(FE_ALL_EXCEPT) || feraiseexcept(seed)) {
    return 1;
  }
  int incoming = fetestexcept(FE_ALL_EXCEPT);
  errno = error_seed;
  uint64_t output;
  if (single) {
    uint32_t bx = (uint32_t)w[0], by = (uint32_t)w[1], bits;
    float x, y;
    memcpy(&x, &bx, 4);
    memcpy(&y, &by, 4);
    float (*volatile fn)(float, float) = gmath_nextafterf;
#ifdef GMATH_NEXTAFTER_REFERENCE
    if (reference) {
      fn = GMATH_NEXTAFTERF_REFERENCE;
    }
#endif
    float result = fn(x, y);
    memcpy(&bits, &result, 4);
    output = bits;
  } else {
    double x, y;
    memcpy(&x, &w[0], 8);
    memcpy(&y, &w[1], 8);
    double (*volatile fn)(double, double) = gmath_nextafter;
#ifdef GMATH_NEXTAFTER_REFERENCE
    if (reference) {
      fn = GMATH_NEXTAFTER_REFERENCE;
    }
#endif
    double result = fn(x, y);
    memcpy(&output, &result, 8);
  }
  int error = errno, flags = fetestexcept(FE_ALL_EXCEPT),
      rounding = fegetround();
  if (output != w[2] || flags != (incoming | native_flags(w[3])) ||
      error != error_seed || rounding != mode) {
    fprintf(stderr,
            "adjacent%d %s x%016" PRIx64 " y%016" PRIx64 " result%016" PRIx64
            " expected%016" PRIx64 " flags%x required%x errno%d mode%x\n",
            single ? 32 : 64, reference ? "prior" : "current", w[0], w[1],
            output, w[2], (unsigned)flags,
            (unsigned)(incoming | native_flags(w[3])), error,
            (unsigned)rounding);
    return 1;
  }
  if (hash) {
    *hash = gmath_fnv_u64(gmath_fnv_u64(*hash, output), w[3]);
  }
  return 0;
}
static int invoke(const uint64_t w[4], int single, int mode, int seed,
                  int error_seed, uint64_t * hash) {
  int result = invoke_impl(w, single, mode, seed, error_seed, hash, 0);
#ifdef GMATH_NEXTAFTER_REFERENCE
  if (!result) {
    result = invoke_impl(w, single, mode, seed, error_seed, NULL, 1);
  }
#endif
  return result;
}
typedef struct {
  uint64_t x, y;
} Pair;
static int compare_pair(const void * left, const void * right) {
  const Pair * a = left;
  const Pair * b = right;
  if (a->x != b->x) {
    return a->x < b->x ? -1 : 1;
  }
  return (a->y > b->y) - (a->y < b->y);
}
static int decimal(const char * text, uint64_t * result) {
  if (!*text) {
    return 0;
  }
  uint64_t value = 0;
  for (; *text; ++text) {
    if (*text < '0' || *text > '9') {
      return 0;
    }
    unsigned digit = (unsigned)(*text - '0');
    if (value > (UINT64_MAX - digit) / 10u) {
      return 0;
    }
    value = value * 10u + digit;
  }
  *result = value;
  return 1;
}
static int header(FILE * input, const char * name, uint64_t * count) {
  char line[512], expected[256], seed[32], random_count[32], fresh[32],
      entries[32], extra;
  if (read_line(input, line, sizeof line) != 1 ||
      strcmp(line, "# Pinned oracle: tools/oracle/gen_corpus_adjacent.py; MPFR "
                   "4.2.2 gmpy2 2.3.2\n")) {
    return 0;
  }
  int size = snprintf(expected, sizeof expected, "# function %s_raw\n", name);
  if (size < 0 || (size_t)size >= sizeof expected ||
      read_line(input, line, sizeof line) != 1 || strcmp(line, expected)) {
    return 0;
  }
  if (read_line(input, line, sizeof line) != 1 ||
      sscanf(line, "# seed %31s count %31s fresh %31s entries %31s %c", seed,
             random_count, fresh, entries, &extra) != 4) {
    return 0;
  }
  uint64_t seed_value, random_value;
  if (!decimal(seed, &seed_value) || !decimal(random_count, &random_value) ||
      random_value > 50000u || !decimal(entries, count) || *count < 1000u ||
      *count > 250000u || (strcmp(fresh, "False") && strcmp(fresh, "True"))) {
    return 0;
  }
  (void)seed_value;
  return read_line(input, line, sizeof line) == 1 &&
         !strcmp(line, "# raw x y result normalized-flags\n");
}
int main(int argc, char ** argv) {
  if (argc > 2) {
    return 2;
  }
#ifdef GMATH_NEXTAFTER_REFERENCE
  double (*volatile current_d)(double, double) = gmath_nextafter;
  double (*volatile prior_d)(double, double) = GMATH_NEXTAFTER_REFERENCE;
  float (*volatile current_f)(float, float) = gmath_nextafterf;
  float (*volatile prior_f)(float, float) = GMATH_NEXTAFTERF_REFERENCE;
  if (current_d == prior_d || current_f == prior_f) {
    fputs("adjacent raw reference aliases current function\n", stderr);
    return 2;
  }
#endif
#ifdef GMATH_NEXTAFTER_REFERENCE
  fputs(GMATH_ADJACENT_BASELINE_IDENTITY, stderr);
#endif
  const char * directory = argc == 2 ? argv[1] : "tests/corpus";
  fenv_t saved;
  int saved_errno = errno;
  if (fegetenv(&saved)) {
    return 2;
  }
  const int modes[] = {FE_TONEAREST, FE_DOWNWARD, FE_UPWARD, FE_TOWARDZERO};
  const int flags[] = {FE_INVALID, FE_DIVBYZERO, FE_OVERFLOW, FE_UNDERFLOW,
                       FE_INEXACT};
  const int errors[] = {0, E2BIG};
  int failure = 0;
  for (int single = 0; single < 2 && !failure; ++single) {
    const char * name = single ? "nextafterf" : "nextafter";
    char path[4096], line[512];
    int size =
        snprintf(path, sizeof path, "%s/%s-special.corpus", directory, name);
    if (size < 0 || (size_t)size >= sizeof path) {
      failure = 1;
      break;
    }
    FILE * input = fopen(path, "r");
    if (!input) {
      perror(path);
      failure = 1;
      break;
    }
    uint64_t count;
    if (!header(input, name, &count)) {
      fclose(input);
      failure = 1;
      break;
    }
    Pair * pairs = calloc((size_t)count, sizeof *pairs);
    if (!pairs) {
      fclose(input);
      failure = 1;
      break;
    }
    uint64_t full = GMATH_FNV_BASIS, all = GMATH_FNV_BASIS, index = 0,
             states = 0;
    int line_status;
    while ((line_status = read_line(input, line, sizeof line)) == 1) {
      uint64_t words[4];
      if (index >= count || !parse(line, words) ||
          (words[3] != 0 && words[3] != 1 && words[3] != 20 &&
           words[3] != 24) ||
          (single && (words[0] > UINT32_MAX || words[1] > UINT32_MAX ||
                      words[2] > UINT32_MAX))) {
        failure = 1;
        break;
      }
      pairs[index] = (Pair){words[0], words[1]};
      failure = invoke(words, single, FE_TONEAREST, 0, E2BIG, &full);
      if (!failure && selected(words[0], words[1], index, single)) {
        for (unsigned m = 0; m < 4 && !failure; ++m) {
          for (unsigned mask = 0; mask < 32 && !failure; ++mask) {
            int seed = 0;
            for (unsigned bit = 0; bit < 5; ++bit) {
              if (mask & (1u << bit)) {
                seed |= flags[bit];
              }
            }
            for (unsigned error = 0; error < 2 && !failure; ++error) {
              failure = invoke(words, single, modes[m], seed, errors[error],
                               mask == 0 && error == 0 ? &all : NULL);
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
    if (line_status < 0 || ferror(input) || index != count) {
      failure = 1;
    }
    fclose(input);
    if (!failure) {
      qsort(pairs, (size_t)count, sizeof *pairs, compare_pair);
      for (uint64_t i = 1; i < count; ++i) {
        if (pairs[i - 1].x == pairs[i].x && pairs[i - 1].y == pairs[i].y) {
          failure = 1;
          break;
        }
      }
    }
    free(pairs);
    if (!failure) {
      printf("math.%s_raw.hash %016" PRIx64 "\nmath.%s_raw.count %" PRIu64
             "\nmath.%s_all_modes.hash %016" PRIx64
             "\nmath.%s_state.count %" PRIu64 "\n",
             name, full, name, index, name, all, name, states);
    }
  }
  if (fesetenv(&saved)) {
    failure = 1;
  }
  errno = saved_errno;
  return failure;
}
