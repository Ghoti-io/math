/*
 * The cross-target probe for the trig corpus (CAP-1, AD-17).
 *
 *   corpus-hash DIR
 *
 * Reads DIR/sin.corpus, DIR/cos.corpus and DIR/tan.corpus (see
 * tools/oracle/gen_corpus.py), runs gmath_sin, gmath_cos and gmath_tan over
 * the inputs and prints one FNV-1a 64 hash over the little-endian bytes of
 * every result, in file order, sin then cos then tan, and the number of
 * results.  The same program is built for x86-64, i686 (SSE), arm64,
 * big-endian and Windows by suite/tools/xarch/shape.sh and
 * suite/tools/xwin/shape.sh; every target must print the value committed in
 * tests/corpus/trig.hash.  `make check-corpus-hash` does that for the host.
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

int main(int argc, char ** argv) {
  static const char * const names[3] = {"sin", "cos", "tan"};
  double (*const fns[3])(double) = {gmath_sin, gmath_cos, gmath_tan};
  if (argc != 2) {
    fprintf(stderr, "usage: corpus-hash DIR\n");
    return 2;
  }
  uint64_t hash = GMATH_FNV_BASIS;
  unsigned long count = 0;
  for (int f = 0; f < 3; f++) {
    char path[4096];
    char line[256];
    if (snprintf(path, sizeof path, "%s/%s.corpus", argv[1], names[f]) >= (int)sizeof path) {
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
      uint64_t xbits;
      if (sscanf(line, "%" SCNx64, &xbits) != 1) {
        fprintf(stderr, "corpus-hash: bad line in %s: %s", path, line);
        fclose(fp);
        return 2;
      }
      double y = fns[f](double_of(xbits));
#ifdef GMATH_PLANT_BIT
      if (count == 1234) {
        uint64_t u;
        memcpy(&u, &y, sizeof u);
        u ^= 1u;
        y = double_of(u);
      }
#endif
      hash = gmath_fnv_double(hash, y);
      count++;
    }
    fclose(fp);
  }
  printf("math.trig.hash  %016" PRIx64 "\n", hash);
  printf("math.trig.count  %lu\n", count);
  return 0;
}
