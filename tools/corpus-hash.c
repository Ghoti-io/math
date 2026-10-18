/*
 * The cross-target probe for the elementary-function corpora (CAP-1, AD-17).
 *
 *   corpus-hash DIR
 *
 * Reads DIR/<fn>.corpus for sin, cos, tan, atan2, exp, log, pow and hypot (see
 * tools/oracle/gen_corpus.py and gen_corpus_elem.py), runs gmath_<fn> over the
 * inputs and prints one FNV-1a 64 hash over the little-endian bytes of every
 * result, in file order, the eight functions in that order, and the number of
 * results (math.trig.hash and math.trig.count: the name is the first library's,
 * kept so that the scripts that read it need not change), then the same pair
 * for each function alone (math.<fn>.hash, math.<fn>.count), so that a
 * mismatch says which function it is in.  The same program is built for x86-64,
 * i686 (SSE), arm64, big-endian and Windows by suite/tools/xarch/shape.sh and
 * suite/tools/xwin/shape.sh; every target must print the value committed in
 * tests/corpus/trig.hash.  `make check-corpus-hash` does that for the host.
 *
 * A corpus line is the argument bits (one for sin, cos, tan, exp, log; two for
 * atan2 (y, x), pow (x, y) and hypot (x, y)), then the result bits and the error
 * of the result: only the arguments are used.
 *
 * -DGMATH_PLANT_BIT flips one bit of one result before it is hashed, which
 * the gates use to show that a differing result changes the hash.
 */
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

typedef double (*fn1_t)(double);
typedef double (*fn2_t)(double, double);

static const struct {
  const char * name;
  int arity;
  fn1_t f1;
  fn2_t f2;
} fns[] = {
  {"sin", 1, gmath_sin, NULL},
  {"cos", 1, gmath_cos, NULL},
  {"tan", 1, gmath_tan, NULL},
  {"atan2", 2, NULL, gmath_atan2},
  {"exp", 1, gmath_exp, NULL},
  {"log", 1, gmath_log, NULL},
  {"pow", 2, NULL, gmath_pow},
  {"hypot", 2, NULL, gmath_hypot},
};

int main(int argc, char ** argv) {
  const int nfns = (int)(sizeof fns / sizeof fns[0]);
  if (argc != 2) {
    fprintf(stderr, "usage: corpus-hash DIR\n");
    return 2;
  }
  uint64_t hash = GMATH_FNV_BASIS;
  unsigned long count = 0;
  uint64_t fhash[8];
  unsigned long fcount[8];
  for (int f = 0; f < nfns; f++) {
    char path[4096];
    char line[512];
    fhash[f] = GMATH_FNV_BASIS;
    fcount[f] = 0;
    if (snprintf(path, sizeof path, "%s/%s.corpus", argv[1], fns[f].name) >= (int)sizeof path) {
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
      uint64_t a, b = 0;
      int got = fns[f].arity == 1 ? sscanf(line, "%" SCNx64, &a) : sscanf(line, "%" SCNx64 " %" SCNx64, &a, &b);
      if (got != fns[f].arity) {
        fprintf(stderr, "corpus-hash: bad line in %s: %s", path, line);
        fclose(fp);
        return 2;
      }
      double y = fns[f].arity == 1 ? fns[f].f1(double_of(a)) : fns[f].f2(double_of(a), double_of(b));
#ifdef GMATH_PLANT_BIT
      if (count == 1234) {
        uint64_t u;
        memcpy(&u, &y, sizeof u);
        u ^= 1u;
        y = double_of(u);
      }
#endif
      hash = gmath_fnv_double(hash, y);
      fhash[f] = gmath_fnv_double(fhash[f], y);
      fcount[f]++;
      count++;
    }
    fclose(fp);
  }
  printf("math.trig.hash  %016" PRIx64 "\n", hash);
  printf("math.trig.count  %lu\n", count);
  for (int f = 0; f < nfns; f++) {
    printf("math.%s.hash  %016" PRIx64 "\n", fns[f].name, fhash[f]);
    printf("math.%s.count  %lu\n", fns[f].name, fcount[f]);
  }
  return 0;
}
