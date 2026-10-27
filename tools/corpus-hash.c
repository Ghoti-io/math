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
#include <ghoti.io/math/decimal.h>
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
  K_D_N,    /* double -> int (ilogb) */
  K_F_DN,   /* exactly widened Float -> Float fraction, int */
  K_F_N     /* exactly widened Float -> int */
};

typedef double (*fn1_t)(double);
typedef double (*fn2_t)(double, double);
typedef double (*fnn_t)(double, int);

static double frexp_fraction(double x, int * e) {
  return gmath_frexp(x, e);
}

/* Float corpus values are stored as exactly widened doubles. */
static double scalbnf_widened(double x, int n) {
  return (double)gmath_scalbnf((float)x, n);
}
static double ldexpf_widened(double x, int n) {
  return (double)gmath_ldexpf((float)x, n);
}

/* These corpora contain only exact common signed32-range results. Full
 * native-width integer outputs are validated by the integer-rounding probe. */
static double lround_widened(double x) {return (double)gmath_lround(x);}
static double llround_widened(double x) {return (double)gmath_llround(x);}
static double lroundf_widened(double x) {return (double)gmath_lroundf((float)x);}
static double llroundf_widened(double x) {return (double)gmath_llroundf((float)x);}

static double atanf_widened(double x) {
  return (double)gmath_atanf((float)x);
}

static double atan2f_widened(double y, double x) {
  return (double)gmath_atan2f((float)y, (float)x);
}

static double hypotf_widened(double x, double y) {
  return (double)gmath_hypotf((float)x, (float)y);
}

static double fmodf_widened(double x, double y) {
  return (double)gmath_fmodf((float)x, (float)y);
}

static double fminf_widened(double x, double y) {
  return (double)gmath_fminf((float)x, (float)y);
}

static double fmaxf_widened(double x, double y) {
  return (double)gmath_fmaxf((float)x, (float)y);
}

static double expf_widened(double x) {
  return (double)gmath_expf((float)x);
}

static double exp2f_widened(double x) {
  return (double)gmath_exp2f((float)x);
}

static double log10f_widened(double x) {
  return (double)gmath_log10f((float)x);
}

static double logf_widened(double x) {
  return (double)gmath_logf((float)x);
}

static double log2f_widened(double x) {
  return (double)gmath_log2f((float)x);
}

static double floorf_widened(double x) {
  return (double)gmath_floorf((float)x);
}

static double ceilf_widened(double x) {
  return (double)gmath_ceilf((float)x);
}

static double truncf_widened(double x) {
  return (double)gmath_truncf((float)x);
}

static double roundf_widened(double x) {
  return (double)gmath_roundf((float)x);
}

static double rintf_widened(double x) {
  return (double)gmath_rintf((float)x);
}

static double fabsf_widened(double x) {
  return (double)gmath_fabsf((float)x);
}

static double sqrtf_widened(double x) {
  return (double)gmath_sqrtf((float)x);
}

static double copysignf_widened(double x, double y) {
  return (double)gmath_copysignf((float)x, (float)y);
}

static double sinf_widened(double x) {
  return (double)gmath_sinf((float)x);
}

static double cosf_widened(double x) {
  return (double)gmath_cosf((float)x);
}

static double tanf_widened(double x) {
  return (double)gmath_tanf((float)x);
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
  {"scalbnf", "scalbnf", K_DN_D, 0, NULL, NULL, NULL, scalbnf_widened},
  {"ldexpf", "scalbnf", K_DN_D, 0, "scalbnf", NULL, NULL, ldexpf_widened},
  {"frexpf", "frexpf", K_F_DN, 0, NULL, NULL, NULL, NULL},
  {"ilogbf", "ilogbf", K_F_N, 0, NULL, NULL, NULL, NULL},
  {"lround", "lround", K_D_D, 0, NULL, lround_widened, NULL, NULL},
  {"llround", "lround", K_D_D, 0, NULL, llround_widened, NULL, NULL},
  {"lroundf", "lroundf", K_D_D, 0, NULL, lroundf_widened, NULL, NULL},
  {"llroundf", "lroundf", K_D_D, 0, NULL, llroundf_widened, NULL, NULL},
  {"atanf", "atanf", K_D_D, 0, NULL, atanf_widened, NULL, NULL},
  {"atan2f", "atan2f", K_DD_D, 0, NULL, NULL, atan2f_widened, NULL},
  {"exp", "exp", K_D_D, 1, NULL, gmath_exp, NULL, NULL},
  {"log", "log", K_D_D, 1, NULL, gmath_log, NULL, NULL},
  {"pow", "pow", K_DD_D, 1, NULL, NULL, gmath_pow, NULL},
  {"hypot", "hypot", K_DD_D, 1, NULL, NULL, gmath_hypot, NULL},
  {"hypotf", "hypotf", K_DD_D, 0, NULL, NULL, hypotf_widened, NULL},
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
  /* Supplemental functions preserve the legacy aggregate hash. */
  {"fmod", "fmod", K_DD_D, 0, NULL, NULL, gmath_fmod, NULL},
  {"fmodf", "fmodf", K_DD_D, 0, NULL, NULL, fmodf_widened, NULL},
  {"fmin", "fmin", K_DD_D, 0, NULL, NULL, gmath_fmin, NULL},
  {"fmax", "fmax", K_DD_D, 0, NULL, NULL, gmath_fmax, NULL},
  {"fminf", "fminf", K_DD_D, 0, NULL, NULL, fminf_widened, NULL},
  {"fmaxf", "fmaxf", K_DD_D, 0, NULL, NULL, fmaxf_widened, NULL},
  {"log2", "log2", K_D_D, 0, NULL, gmath_log2, NULL, NULL},
  {"log10", "log10", K_D_D, 0, NULL, gmath_log10, NULL, NULL},
  {"log2f", "log2f", K_D_D, 0, NULL, log2f_widened, NULL, NULL},
  {"exp2", "exp2", K_D_D, 0, NULL, gmath_exp2, NULL, NULL},
  {"exp2f", "exp2f", K_D_D, 0, NULL, exp2f_widened, NULL, NULL},
  {"expf", "expf", K_D_D, 0, NULL, expf_widened, NULL, NULL},
  {"logf", "logf", K_D_D, 0, NULL, logf_widened, NULL, NULL},
  {"log10f", "log10f", K_D_D, 0, NULL, log10f_widened, NULL, NULL},
  {"cbrt", "cbrt", K_D_D, 0, NULL, gmath_cbrt, NULL, NULL},
  {"floorf", "floorf", K_D_D, 0, NULL, floorf_widened, NULL, NULL},
  {"ceilf", "ceilf", K_D_D, 0, NULL, ceilf_widened, NULL, NULL},
  {"truncf", "truncf", K_D_D, 0, NULL, truncf_widened, NULL, NULL},
  {"roundf", "roundf", K_D_D, 0, NULL, roundf_widened, NULL, NULL},
  {"rintf", "rintf", K_D_D, 0, NULL, rintf_widened, NULL, NULL},
  {"fabsf", "fabsf", K_D_D, 0, NULL, fabsf_widened, NULL, NULL},
  {"sqrtf", "sqrtf", K_D_D, 0, NULL, sqrtf_widened, NULL, NULL},
  {"copysignf", "copysignf", K_DD_D, 0, NULL, NULL, copysignf_widened, NULL},
  {"sinf", "sinf", K_D_D, 0, NULL, sinf_widened, NULL, NULL},
  {"cosf", "cosf", K_D_D, 0, NULL, cosf_widened, NULL, NULL},
  {"tanf", "tanf", K_D_D, 0, NULL, tanf_widened, NULL, NULL},
};
#define NFNS ((int)(sizeof fns / sizeof fns[0]))

/*
 * The decimal conversions, each over its own corpus and outside the total:
 * gmath_decimal_parse hashed as the result's bits, the flags and the bytes
 * consumed; gmath_decimal_shortest as the sign, the digits and the exponent.
 * A line is at most a few thousand bytes (a text of more than 800 digits).
 */
static char decimal_line[1 << 16];

static int hash_decimal(const char * dir, const char * fn, int parse, uint64_t * h, unsigned long * c) {
  char path[4096];
  if (snprintf(path, sizeof path, "%s/%s.corpus", dir, fn) >= (int)sizeof path) {
    fprintf(stderr, "corpus-hash: path too long\n");
    return 2;
  }
  FILE * fp = fopen(path, "r");
  if (!fp) {
    fprintf(stderr, "corpus-hash: cannot open %s\n", path);
    return 2;
  }
  *h = GMATH_FNV_BASIS;
  *c = 0;
  while (fgets(decimal_line, sizeof decimal_line, fp)) {
    size_t len = strlen(decimal_line);
    if (len == sizeof decimal_line - 1 && decimal_line[len - 1] != '\n') {
      fprintf(stderr, "corpus-hash: a line of %s is too long\n", path);
      fclose(fp);
      return 2;
    }
    if (decimal_line[0] == '#' || decimal_line[0] == '\n' || decimal_line[0] == '\r') {
      continue;
    }
    char * space = strchr(decimal_line, ' ');
    if (!space) {
      fprintf(stderr, "corpus-hash: bad line in %s\n", path);
      fclose(fp);
      return 2;
    }
    if (parse) {
      double d = 0;
      size_t consumed = 0;
      unsigned flags = 0;
      if (gmath_decimal_parse(decimal_line, (size_t)(space - decimal_line), &d, &consumed, &flags) != GMATH_OK) {
        d = double_of(0x7ff8dead00000000ull); /* a refusal hashes as itself */
      }
      *h = gmath_fnv_double(*h, d);
      *h = gmath_fnv_u64(*h, flags);
      *h = gmath_fnv_u64(*h, (uint64_t)consumed);
    } else {
      uint64_t u = 0;
      if (sscanf(decimal_line, "%" SCNx64, &u) != 1) {
        fprintf(stderr, "corpus-hash: bad line in %s\n", path);
        fclose(fp);
        return 2;
      }
      GMATH_Decimal dec;
      if (gmath_decimal_shortest(double_of(u), &dec) != GMATH_OK) {
        *h = gmath_fnv_u64(*h, 0xdeadull);
      } else {
        *h = gmath_fnv_u64(*h, dec.negative ? 1u : 0u);
        for (size_t i = 0; i < dec.length; i++) {
          *h = gmath_fnv_u64(*h, (uint64_t)(unsigned char)dec.digits[i]);
        }
        *h = gmath_fnv_u64(*h, (uint64_t)(int64_t)dec.exponent);
      }
    }
    (*c)++;
  }
  fclose(fp);
  return 0;
}

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
        case K_F_DN:
          y = (double)gmath_frexpf((float)x, &n);
          extra = (uint64_t)(int64_t)n;
          break;
        case K_F_N:
          has_double = 0;
          extra = (uint64_t)(int64_t)gmath_ilogbf((float)x);
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
      if (fns[f].kind == K_D_DN || fns[f].kind == K_D_N ||
          fns[f].kind == K_F_DN || fns[f].kind == K_F_N) {
        fhash[f] = gmath_fnv_u64(fhash[f], extra);
      }
      if (fns[f].in_total) {
        if (has_double) {
          hash = gmath_fnv_double(hash, y);
        }
        if (fns[f].kind == K_D_DN || fns[f].kind == K_D_N ||
          fns[f].kind == K_F_DN || fns[f].kind == K_F_N) {
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
  {
    static const char * const decimal_fns[2] = {"decimal_parse", "decimal_shortest"};
    for (int k = 0; k < 2; k++) {
      uint64_t h = 0;
      unsigned long c = 0;
      int rc = hash_decimal(argv[1], decimal_fns[k], k == 0, &h, &c);
      if (rc != 0) {
        return rc;
      }
      printf("math.%s.hash  %016" PRIx64 "\n", decimal_fns[k], h);
      printf("math.%s.count  %lu\n", decimal_fns[k], c);
    }
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
