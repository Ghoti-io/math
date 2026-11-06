/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Exact 4224-bit product-plus-sum, rounded once; native long-double direction
 * decoded as bytes, without executing long-double arithmetic instructions.
 */
#include "elem_common.h"
#include "nearby_mode.h"
#include "remaining_mp.h"
#include <float.h>
#include <ghoti.io/math/basic.h>
#define RX_N 132
static void rx_inexact(void) {
  volatile double a = 1.0, b = 0x1p-54;
  volatile double t = a + b;
  (void)t;
}
static void rx_unpack(uint64_t a, unsigned p, int bias, uint64_t * m, int * e) {
  unsigned f = (unsigned)(a >> p);
  *m = a & ((UINT64_C(1) << p) - 1);
  *e = 1 - bias - (int)p;
  if (f) {
    *m |= UINT64_C(1) << p;
    *e = (int)f - bias - (int)p;
  }
}
static void rx_put(
    uint32_t * a, const uint32_t * m, unsigned n, unsigned shift) {
  unsigned k = shift / 32, t = shift % 32;
  for (unsigned i = 0; i < n; ++i) {
    a[k + i] |= m[i] << t;
    if (t)
      a[k + i + 1] |= m[i] >> (32 - t);
  }
}
static unsigned rx_bit(const uint32_t * a, int bit) {
  return bit >= 0 && bit < 32 * RX_N ? (a[bit / 32] >> (bit % 32)) & 1u : 0;
}
static uint64_t rx_fma(
    uint64_t x, uint64_t y, uint64_t z, unsigned p, int bias) {
  uint64_t sign = UINT64_C(1) << (p + (p == 52 ? 11 : 8)),
           inf = (uint64_t)(2 * bias + 1) << p, quiet = UINT64_C(1) << (p - 1);
  uint64_t ax = x & (sign - 1), ay = y & (sign - 1), az = z & (sign - 1);
  int ps = ((x ^ y) & sign) != 0, zs = (z & sign) != 0, mode = nearby_mode();
  int invalid = (ax == inf && !ay) || (ay == inf && !ax);
  if ((ax > inf && !(x & quiet)) || (ay > inf && !(y & quiet)) ||
      (az > inf && !(z & quiet)))
    invalid = 1;
  if (invalid) {
    (void)gmath_invalid();
    return inf | quiet;
  }
  if (ax > inf || ay > inf || az > inf)
    return inf | quiet;
  if (ax == inf || ay == inf) {
    if (az == inf && ps != zs) {
      (void)gmath_invalid();
      return inf | quiet;
    }
    return inf | (ps ? sign : 0);
  }
  if (az == inf)
    return z;
  uint64_t mx, my, mz;
  int ex, ey, ez;
  rx_unpack(ax, p, bias, &mx, &ex);
  rx_unpack(ay, p, bias, &my, &ey);
  rx_unpack(az, p, bias, &mz, &ez);
  uint32_t product[4] = {0}, xm[2] = {(uint32_t)mx, (uint32_t)(mx >> 32)},
           ym[2] = {(uint32_t)my, (uint32_t)(my >> 32)};
  for (unsigned i = 0; i < 2; ++i) {
    uint64_t carry = 0;
    for (unsigned j = 0; j < 2; ++j) {
      uint64_t v = (uint64_t)xm[i] * ym[j] + product[i + j] + carry;
      product[i + j] = (uint32_t)v;
      carry = v >> 32;
    }
    product[i + 2] = (uint32_t)carry;
  }
  uint32_t a[RX_N] = {0}, b[RX_N] = {0},
           zm[2] = {(uint32_t)mz, (uint32_t)(mz >> 32)};
  const int base = -2148;
  rx_put(a, product, 4, (unsigned)(ex + ey - base));
  rx_put(b, zm, 2, (unsigned)(ez - base));
  int cmp = 0;
  for (int i = RX_N - 1; i >= 0; --i)
    if (a[i] != b[i]) {
      cmp = a[i] > b[i] ? 1 : -1;
      break;
    }
  int result_sign = ps;
  if (ps != zs && cmp < 0) {
    for (unsigned i = 0; i < RX_N; ++i) {
      uint32_t t = a[i];
      a[i] = b[i];
      b[i] = t;
    }
    result_sign = zs;
  }
  uint64_t carry = 0;
  for (unsigned i = 0; i < RX_N; ++i) {
    if (ps == zs) {
      uint64_t v = (uint64_t)a[i] + b[i] + carry;
      a[i] = (uint32_t)v;
      carry = v >> 32;
    }
    else {
      uint64_t sub = (uint64_t)b[i] + carry;
      uint32_t old = a[i];
      a[i] = (uint32_t)((uint64_t)old - sub);
      carry = (uint64_t)old < sub;
    }
  }
  int top = 32 * RX_N - 1;
  while (top >= 0 && !rx_bit(a, top))
    --top;
  if (top < 0) {
    if (ps == zs)
      return ps ? sign : 0;
    return mode == 1 ? sign : 0;
  }
  int cut = top - (int)p, mincut = 1 - bias - (int)p - base;
  if (cut < mincut)
    cut = mincut;
  uint64_t q = 0;
  for (int i = top; i >= cut; --i)
    q = (q << 1) | rx_bit(a, i);
  unsigned lost = 0, sticky = 0;
  for (int i = 0; i < cut; ++i)
    lost |= rx_bit(a, i);
  for (int i = 0; i < cut - 1; ++i)
    sticky |= rx_bit(a, i);
  if (mode == 0 || mode < 0)
    q += rx_bit(a, cut - 1) && (sticky || (q & 1));
  else if (lost && ((mode == 1 && result_sign) || (mode == 2 && !result_sign)))
    ++q;
  int e = cut + base + (int)p;
  if (q == (UINT64_C(1) << (p + 1))) {
    q >>= 1;
    ++e;
  }
  uint64_t sb = result_sign ? sign : 0;
  if (e > bias) {
    (void)gmath_overflow(0);
    return sb |
        ((mode == 3 || (mode == 1 && !result_sign) ||
             (mode == 2 && result_sign))
                ? inf - 1
                : inf);
  }
  uint64_t result = q;
  if (q >= (UINT64_C(1) << p))
    result = ((uint64_t)(e + bias) << p) | (q & ((UINT64_C(1) << p) - 1));
  if (lost) {
    if (result < (UINT64_C(1) << p))
      (void)gmath_underflow(0);
    else
      rx_inexact();
  }
  return result | sb;
}
double gmath_fma(double x, double y, double z) {
  return gmath_double(
      rx_fma(gmath_bits(x), gmath_bits(y), gmath_bits(z), 52, 1023));
}
float gmath_fmaf(float x, float y, float z) {
  uint32_t a, b, c;
  memcpy(&a, &x, 4);
  memcpy(&b, &y, 4);
  memcpy(&c, &z, 4);
  a = (uint32_t)rx_fma(a, b, c, 23, 127);
  memcpy(&x, &a, 4);
  return x;
}
double gmath_nan(const char * tag) {
  (void)tag;
  return gmath_double(GMATH_QNAN_BITS);
}
float gmath_nanf(const char * tag) {
  (void)tag;
  uint32_t b = UINT32_C(0x7fc00000);
  float x;
  memcpy(&x, &b, 4);
  return x;
}

typedef struct {
  rmp a, b;
  int nan, invalid, inf, sign;
} rx_direction;
static rx_direction rx_decode64(uint64_t u) {
  rx_direction d;
  memset(&d, 0, sizeof d);
  uint64_t a = u & GMATH_ABS_MASK;
  d.sign = (int)(u >> 63);
  d.nan = a > GMATH_INF_BITS;
  d.invalid = d.nan && !(u & UINT64_C(0x0008000000000000));
  d.inf = a == GMATH_INF_BITS;
  if (a < GMATH_INF_BITS)
    d.a = rm_raw(u, 52, 1023);
  return d;
}
static rx_direction rx_decode80(uint64_t m, uint16_t se) {
  rx_direction d;
  memset(&d, 0, sizeof d);
  unsigned exp = se & 32767;
  d.sign = se >> 15;
  /* Pseudo-denormals (exp0,integer1) have the same value as exponent1.
   * Unnormals and pseudo infinities/NaNs are unsupported and invalid. */
  if (exp && !(m >> 63)) {
    d.nan = 1;
    d.invalid = 1;
    return d;
  }
  if (exp == 32767) {
    d.inf = m == UINT64_C(0x8000000000000000);
    d.nan = !d.inf;
    d.invalid = d.nan && !(m & UINT64_C(0x4000000000000000));
  }
  else {
    d.a = rm_uint(m);
    d.a.e += (exp ? (int)exp : 1) - 16383 - 63;
    d.a.s = d.sign;
  }
  return d;
}
static rx_direction rx_decode128(uint64_t hi, uint64_t lo) {
  rx_direction d;
  memset(&d, 0, sizeof d);
  unsigned exp = (unsigned)((hi >> 48) & 32767);
  d.sign = (int)(hi >> 63);
  uint64_t m = hi & UINT64_C(0x0000ffffffffffff);
  if (exp == 32767) {
    d.nan = m || lo;
    d.inf = !d.nan;
    d.invalid = d.nan && !(m & UINT64_C(0x0000800000000000));
  }
  else {
    if (exp)
      m |= UINT64_C(0x0001000000000000);
    d.a = rm_zero();
    d.a.w[0] = (uint32_t)lo;
    d.a.w[1] = (uint32_t)(lo >> 32);
    d.a.w[2] = (uint32_t)m;
    d.a.w[3] = (uint32_t)(m >> 32);
    d.a.e = 255 + (exp ? (int)exp : 1) - 16383 - 112;
    d.a.s = d.sign;
    d.a = rm_norm(d.a);
  }
  return d;
}
static rx_direction rx_decode_dd(uint64_t hi, uint64_t lo) {
  rx_direction d;
  memset(&d, 0, sizeof d);
  uint64_t ah = hi & GMATH_ABS_MASK, al = lo & GMATH_ABS_MASK;
  d.sign = (int)(hi >> 63);
  d.nan = ah > GMATH_INF_BITS || al > GMATH_INF_BITS;
  d.invalid = (ah > GMATH_INF_BITS && !(hi & UINT64_C(0x0008000000000000))) ||
      (al > GMATH_INF_BITS && !(lo & UINT64_C(0x0008000000000000)));
  if (al >= GMATH_INF_BITS || (ah == GMATH_INF_BITS && al)) {
    d.nan = 1;
    d.invalid = 1;
  }
  if (!d.nan) {
    d.inf = ah == GMATH_INF_BITS;
    if (!d.inf) {
      d.a = rm_raw(hi, 52, 1023);
      d.b = rm_raw(lo, 52, 1023);
    }
  }
  return d;
}
static rx_direction rx_decode(const unsigned char * bytes) {
  /* All decoders are also shared with the synthetic representation probe. */
  (void)rx_decode64; (void)rx_decode80; (void)rx_decode128; (void)rx_decode_dd;
#if LDBL_MANT_DIG == 53 && LDBL_MAX_EXP == 1024
  uint64_t u;
  memcpy(&u, bytes, 8);
  return rx_decode64(u);
#elif LDBL_MANT_DIG == 64 && LDBL_MAX_EXP == 16384
  uint64_t m;
  uint16_t se;
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
  memcpy(&se, bytes, 2);
  memcpy(&m, bytes + sizeof(long double) - 8, 8);
#else
  memcpy(&m, bytes, 8);
  memcpy(&se, bytes + 8, 2);
#endif
  return rx_decode80(m, se);
#elif LDBL_MANT_DIG == 113 && LDBL_MAX_EXP == 16384
  uint64_t lo, hi;
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
  memcpy(&hi, bytes, 8);
  memcpy(&lo, bytes + 8, 8);
#else
  memcpy(&lo, bytes, 8);
  memcpy(&hi, bytes + 8, 8);
#endif
  return rx_decode128(hi, lo);
#elif LDBL_MANT_DIG == 106 && LDBL_MAX_EXP == 1024
  uint64_t hi, lo;
  memcpy(&hi, bytes, 8);
  memcpy(&lo, bytes + 8, 8);
  return rx_decode_dd(hi, lo);
#else
#error Unsupported native long double representation
#endif
}
static int rx_signed_cmp(rmp a, rmp b) {
  int az = rm_nonzero(a), bz = rm_nonzero(b);
  if (!az && !bz)
    return 0;
  if (az && a.s && (!bz || !b.s))
    return -1;
  if (bz && b.s && (!az || !a.s))
    return 1;
  int c = rm_cmp(a, b);
  return a.s ? -c : c;
}
static uint64_t rx_toward_direction(
    uint64_t x, rx_direction d, unsigned p, int bias) {
  uint64_t sign = UINT64_C(1) << (p + (p == 52 ? 11 : 8)),
           inf = (uint64_t)(2 * bias + 1) << p, quiet = UINT64_C(1) << (p - 1),
           ax = x & (sign - 1);
  if (ax > inf || d.nan) {
    if ((ax > inf && !(x & quiet)) || d.invalid)
      (void)gmath_invalid();
    return inf | quiet;
  }
  int cmp;
  if (ax == inf)
    cmp = d.inf && ((x & sign) != 0) == d.sign ? 0 : ((x & sign) ? -1 : 1);
  else if (d.inf)
    cmp = d.sign ? 1 : -1;
  else {
    rmp delta = rm_sub(rm_raw(x, p, bias), d.a);
    /* Compare the residual with the low DD component separately. This
     * preserves a low component arbitrarily far below the leading value. */
    cmp = rx_signed_cmp(delta, d.b);
  }
  if (!cmp)
    return ax ? x : ((uint64_t)d.sign << (p + (p == 52 ? 11 : 8)));
  if (!ax) {
    (void)gmath_underflow(0);
    return (cmp > 0 ? sign : 0) | 1;
  }
  int outward = ((x & sign) ? cmp > 0 : cmp < 0);
  uint64_t result = outward ? x + 1 : x - 1, mag = result & (sign - 1);
  if (mag == inf && ax < inf)
    (void)gmath_overflow(0);
  else if (mag < (UINT64_C(1) << p))
    (void)gmath_underflow(0);
  return result;
}
static uint64_t rx_toward(
    uint64_t x, const unsigned char * bytes, unsigned p, int bias) {
  return rx_toward_direction(x, rx_decode(bytes), p, bias);
}
/* SysV x86-64 passes native80 y in memory at entry rsp+8 and x in
 * xmm0. Clang and sanitizer instrumentation can materialize y in x87 even for a
 * C byte-address operation. These two integer-only tail thunks expose its
 * incoming object bytes to ordinary C helpers while preserving both argument
 * and return ABIs. The compiler never creates a long-double IR load in a naked
 * thunk. */
#if (defined(__GNUC__) || defined(__clang__)) && defined(__x86_64__) &&        \
    defined(__ELF__) && LDBL_MANT_DIG == 64 && LDBL_MAX_EXP == 16384
static double rx_native_double(double x, const unsigned char * bytes) __asm__(
    "gmath_remaining_native_double_bytes") __attribute__((noinline, used));
static double rx_native_double(double x, const unsigned char * bytes) {
  return gmath_double(rx_toward(gmath_bits(x), bytes, 52, 1023));
}
static float rx_native_float(float x, const unsigned char * bytes) __asm__(
    "gmath_remaining_native_float_bytes") __attribute__((noinline, used));
static float rx_native_float(float x, const unsigned char * bytes) {
  uint32_t a;
  memcpy(&a, &x, 4);
  a = (uint32_t)rx_toward(a, bytes, 23, 127);
  memcpy(&x, &a, 4);
  return x;
}
__attribute__((naked)) double gmath_nexttoward(
    double x __attribute__((unused)), long double y __attribute__((unused))) {
  __asm__("leaq 8(%rsp), %rdi\n\tjmp gmath_remaining_native_double_bytes");
}
__attribute__((naked)) float gmath_nexttowardf(
    float x __attribute__((unused)), long double y __attribute__((unused))) {
  __asm__("leaq 8(%rsp), %rdi\n\tjmp gmath_remaining_native_float_bytes");
}
#else
double gmath_nexttoward(double x, long double y) {
  unsigned char bytes[sizeof y];
  const volatile unsigned char * source = (const volatile unsigned char *)&y;
  for (unsigned i = 0; i < sizeof y; ++i)
    bytes[i] = source[i];
  return gmath_double(rx_toward(gmath_bits(x), bytes, 52, 1023));
}
float gmath_nexttowardf(float x, long double y) {
  unsigned char bytes[sizeof y];
  uint32_t a;
  const volatile unsigned char * source = (const volatile unsigned char *)&y;
  for (unsigned i = 0; i < sizeof y; ++i)
    bytes[i] = source[i];
  memcpy(&a, &x, 4);
  a = (uint32_t)rx_toward(a, bytes, 23, 127);
  memcpy(&x, &a, 4);
  return x;
}

#endif
