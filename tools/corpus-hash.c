/*
 * The cross-target probe for the function corpora (CAP-1, AD-17, AD-22).
 *
 *   corpus-hash DIR
 *
 * Reads DIR/<fn>.corpus for sin, cos, tan, atan2, exp, log, pow, hypot, sqrt,
 * floor, ceil, trunc, round, rint, fabs, copysign, scalbn, frexp and ilogb (see
 * tools/oracle/gen_corpus.py, gen_corpus_elem.py and gen_corpus_exact.py), runs
 * gmath_<fn> over the inputs and prints one FNV-1a 64 hash over the little-endian
 * bytes of every result, in file order, the nineteen functions in that order, and
 * the number of results (math.trig.hash and math.trig.count: the name is the
 * first library's, kept so that the scripts that read it need not change), then
 * the same pair for each function alone (math.<fn>.hash, math.<fn>.count), so
 * that a mismatch says which function it is in.  frexp feeds its fraction and
 * then its exponent (as 64 bits, sign extended); ilogb and the integer argument of
 * scalbn are 64 bits, sign extended.  The same program is built for x86-64, i686
 * (SSE), arm64, big-endian and Windows by suite/tools/xarch/shape.sh and
 * suite/tools/xwin/shape.sh; every target must print the value committed in
 * tests/corpus/trig.hash.  `make check-corpus-hash` does that for the host.
 *
 * The variants.  The square root has two implementations, the target's
 * instruction and the portable method, and ldexp is scalbn under another
 * name.  They are run over the corpus as well (math.sqrt_portable.*,
 * math.sqrt_hardware.* and math.ldexp.*, outside the total) and must give the
 * hash of sqrt and of scalbn exactly: a difference is printed, and the exit status
 * is 1.  math.sqrt_hardware.available says whether the target has an instruction
 * (0: the "hardware" run was the portable function again).  AD-17: every variant
 * is bit-identical, and the gate runs all of them on every host.
 *
 * A corpus line is the argument bits (one for most, two for atan2 (y, x), pow (x,
 * y), hypot (x, y), copysign and scalbn), then the result: only the arguments are
 * used.
 *
 * -DGMATH_PLANT_BIT flips one bit of one result before it is hashed, which
 * the gates use to show that a differing result changes the hash.
 * -DGMATH_PLANT_VARIANT flips one bit of one result of the hardware square root
 * only, which the gates use to show that the variant check can fail.
 */
#include <ghoti.io/math/basic.h>
#include <ghoti.io/math/elementary.h>

#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "../tests/corpus_hash.h"

static double double_of(uint64_t u) {
  double d;
  memcpy(&d, &u, sizeof d);
  return d;
}

/* How a corpus line is read and a result is hashed. */
enum kind {
  K_D_D,    /* double -> double */
  K_DD_D,   /* double, double -> double */
  K_DN_D,   /* double, int -> double */
  K_D_DN,   /* double -> double, int (frexp) */
  K_D_N     /* double -> int (ilogb) */
};

typedef double (*fn1_t)(double);
typedef double (*fn2_t)(double, double);
typedef double (*fnn_t)(double, int);

static double frexp_fraction(double x, int * e) {
  return gmath_frexp(x, e);
}

static const struct {
  const char * name; /* the reported name */
  const char * file; /* the corpus read */
  enum kind kind;
  int in_total;      /* a variant is checked against another function and left out of the total */
  const char * same_as;
  fn1_t f1;
  fn2_t f2;
  fnn_t fn;
} fns[] = {
  {"sin", "sin", K_D_D, 1, NULL, gmath_sin, NULL, NULL},
  {"cos", "cos", K_D_D, 1, NULL, gmath_cos, NULL, NULL},
  {"tan", "tan", K_D_D, 1, NULL, gmath_tan, NULL, NULL},
  {"atan2", "atan2", K_DD_D, 1, NULL, NULL, gmath_atan2, NULL},
  {"exp", "exp", K_D_D, 1, NULL, gmath_exp, NULL, NULL},
  {"log", "log", K_D_D, 1, NULL, gmath_log, NULL, NULL},
  {"pow", "pow", K_DD_D, 1, NULL, NULL, gmath_pow, NULL},
  {"hypot", "hypot", K_DD_D, 1, NULL, NULL, gmath_hypot, NULL},
  {"sqrt", "sqrt", K_D_D, 1, NULL, gmath_sqrt, NULL, NULL},
  {"floor", "floor", K_D_D, 1, NULL, gmath_floor, NULL, NULL},
  {"ceil", "ceil", K_D_D, 1, NULL, gmath_ceil, NULL, NULL},
  {"trunc", "trunc", K_D_D, 1, NULL, gmath_trunc, NULL, NULL},
  {"round", "round", K_D_D, 1, NULL, gmath_round, NULL, NULL},
  {"rint", "rint", K_D_D, 1, NULL, gmath_rint, NULL, NULL},
  {"fabs", "fabs", K_D_D, 1, NULL, gmath_fabs, NULL, NULL},
  {"copysign", "copysign", K_DD_D, 1, NULL, NULL, gmath_copysign, NULL},
  {"scalbn", "scalbn", K_DN_D, 1, NULL, NULL, NULL, gmath_scalbn},
  {"frexp", "frexp", K_D_DN, 1, NULL, NULL, NULL, NULL},
  {"ilogb", "ilogb", K_D_N, 1, NULL, NULL, NULL, NULL},
  /* the variants, over the corpus of the function they must equal */
  {"sqrt_portable", "sqrt", K_D_D, 0, "sqrt", gmath_sqrt_portable, NULL, NULL},
  {"sqrt_hardware", "sqrt", K_D_D, 0, "sqrt", gmath_sqrt_hardware, NULL, NULL},
  {"ldexp", "scalbn", K_DN_D, 0, "scalbn", NULL, NULL, gmath_ldexp},
};
#define NFNS ((int)(sizeof fns / sizeof fns[0]))

int main(int argc, char ** argv) {
  if (argc != 2) {
    fprintf(stderr, "usage: corpus-hash DIR\n");
    return 2;
  }
  uint64_t hash = GMATH_FNV_BASIS;
  unsigned long count = 0;
  uint64_t fhash[NFNS];
  unsigned long fcount[NFNS];
  for (int f = 0; f < NFNS; f++) {
    char path[4096];
    char line[512];
    fhash[f] = GMATH_FNV_BASIS;
    fcount[f] = 0;
    if (snprintf(path, sizeof path, "%s/%s.corpus", argv[1], fns[f].file) >= (int)sizeof path) {
      fprintf(stderr, "corpus-hash: path too long\n");
      return 2;
    }
    FILE * fp = fopen(path, "r");
    if (!fp) {
      fprintf(stderr, "corpus-hash: cannot open %s\n", path);
      return 2;
    }
    while (fgets(line, sizeof line, fp)) {
      if (line[0] == '#' || line[0] == '\n' || line[0] == '\r') {
        continue;
      }
      uint64_t a = 0, b = 0;
      int want = (fns[f].kind == K_DD_D || fns[f].kind == K_DN_D) ? 2 : 1;
      int got = want == 1 ? sscanf(line, "%" SCNx64, &a) : sscanf(line, "%" SCNx64 " %" SCNx64, &a, &b);
      if (got != want) {
        fprintf(stderr, "corpus-hash: bad line in %s: %s", path, line);
        fclose(fp);
        return 2;
      }
      double x = double_of(a);
      double y = 0.0;
      int n = 0;
      uint64_t extra = 0; /* a second word to hash after the result: frexp's exponent, ilogb's value */
      int has_double = 1;
      switch (fns[f].kind) {
        case K_D_D:
          y = fns[f].f1(x);
          break;
        case K_DD_D:
          y = fns[f].f2(x, double_of(b));
          break;
        case K_DN_D:
          y = fns[f].fn(x, (int)(int64_t)b);
          break;
        case K_D_DN:
          y = frexp_fraction(x, &n);
          extra = (uint64_t)(int64_t)n;
          break;
        case K_D_N:
          has_double = 0;
          extra = (uint64_t)(int64_t)gmath_ilogb(x);
          break;
      }
#ifdef GMATH_PLANT_BIT
      if (count == 1234 && fns[f].in_total) {
        uint64_t u;
        memcpy(&u, &y, sizeof u);
        u ^= 1u;
        y = double_of(u);
      }
#endif
#ifdef GMATH_PLANT_VARIANT
      if (fcount[f] == 100 && strcmp(fns[f].name, "sqrt_hardware") == 0) {
        uint64_t u;
        memcpy(&u, &y, sizeof u);
        u ^= 1u;
        y = double_of(u);
      }
#endif
      if (has_double) {
        fhash[f] = gmath_fnv_double(fhash[f], y);
      }
      if (fns[f].kind == K_D_DN || fns[f].kind == K_D_N) {
        fhash[f] = gmath_fnv_u64(fhash[f], extra);
      }
      if (fns[f].in_total) {
        if (has_double) {
          hash = gmath_fnv_double(hash, y);
        }
        if (fns[f].kind == K_D_DN || fns[f].kind == K_D_N) {
          hash = gmath_fnv_u64(hash, extra);
        }
        count++;
      }
      fcount[f]++;
    }
    fclose(fp);
  }
  printf("math.trig.hash  %016" PRIx64 "\n", hash);
  printf("math.trig.count  %lu\n", count);
  for (int f = 0; f < NFNS; f++) {
    printf("math.%s.hash  %016" PRIx64 "\n", fns[f].name, fhash[f]);
    printf("math.%s.count  %lu\n", fns[f].name, fcount[f]);
  }
  printf("math.sqrt_hardware.available  %d\n", gmath_sqrt_has_hardware());
  int status = 0;
  for (int f = 0; f < NFNS; f++) {
    if (fns[f].same_as == NULL) {
      continue;
    }
    for (int g = 0; g < NFNS; g++) {
      if (strcmp(fns[g].name, fns[f].same_as) == 0 && (fhash[f] != fhash[g] || fcount[f] != fcount[g])) {
        fprintf(stderr, "corpus-hash: the variant %s gives %016" PRIx64 " where %s gives %016" PRIx64 "\n",
          fns[f].name, fhash[f], fns[g].name, fhash[g]);
        printf("math.variants.mismatch  %s\n", fns[f].name);
        status = 1;
      }
    }
  }
  return status;
}
