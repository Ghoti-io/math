/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Exact signed dyadics on the binary128 minimum-subnormal grid. This bounded
 * integer representation also retains arbitrarily separated DD components. */
#ifndef GHOTI_IO_GMATH_LONG_DOUBLE_BITS_H
#define GHOTI_IO_GMATH_LONG_DOUBLE_BITS_H
#include <ghoti.io/math/macros.h>
#include <stdint.h>
#include <string.h>
#define LD_BASE (-16494)
#define LD_WORDS 1032
#define LD_ZERO_BIT (-LD_BASE)
typedef struct { uint64_t hi, lo; } ld_raw;
typedef struct { uint32_t w[LD_WORDS]; int sign, kind, invalid; } ld_value;
enum { LD_FINITE, LD_INF, LD_NAN };
enum { LD_FABS, LD_COPY, LD_NAN_OP, LD_MIN, LD_MAX, LD_FLOOR, LD_CEIL,
       LD_TRUNC, LD_ROUND, LD_RINT, LD_NEARBY, LD_MODF, LD_FREXP, LD_ILOGB, LD_LOGB };
static int ld_bit(const ld_value *v, int b) {
  return b >= 0 && b < LD_WORDS * 32 ? (int)((v->w[b / 32] >> (b % 32)) & 1) : 0;
}
static void ld_set(ld_value *v, int b) {
  if (b >= 0 && b < LD_WORDS * 32) v->w[b / 32] |= UINT32_C(1) << (b % 32);
}
static int ld_top(const ld_value *v) {
  for (int i = LD_WORDS - 1; i >= 0; --i)
    if (v->w[i]) { unsigned t = 31; while (!(v->w[i] >> t)) --t; return i * 32 + (int)t; }
  return -1;
}
static int ld_cmpmag(const ld_value *a, const ld_value *b) {
  for (int i = LD_WORDS - 1; i >= 0; --i)
    if (a->w[i] != b->w[i]) return a->w[i] > b->w[i] ? 1 : -1;
  return 0;
}
static void ld_add(ld_value *a, const ld_value *b) {
  int cmp = ld_cmpmag(a,b), subtract = a->sign != b->sign;
  uint64_t carry = 0;
  for (int i = 0; i < LD_WORDS; ++i) {
    uint64_t x = subtract && cmp < 0 ? b->w[i] : a->w[i];
    uint64_t y = subtract && cmp < 0 ? a->w[i] : b->w[i];
    if (subtract) { uint64_t sub = y + carry; a->w[i] = (uint32_t)(x-sub); carry = x < sub; }
    else { uint64_t sum = x + y + carry; a->w[i] = (uint32_t)sum; carry = sum >> 32; }
  }
  if (subtract && cmp < 0) a->sign = b->sign;
  if (subtract && !cmp) a->sign = 0;
}
static void ld_insert(ld_value *v, uint64_t m, int exponent) {
  for (int i = 0; i < 64; ++i) if ((m >> i) & 1) ld_set(v, exponent + i - LD_BASE);
}
static ld_value ld_decode64(uint64_t u) {
  ld_value v = {{0},(int)(u >> 63),LD_FINITE,0};
  unsigned e = (unsigned)((u >> 52) & 2047);
  uint64_t m = u & UINT64_C(0xfffffffffffff);
  if (e == 2047) { v.kind = m ? LD_NAN : LD_INF; v.invalid = m && !(m & UINT64_C(0x8000000000000)); }
  else ld_insert(&v, m | (e ? UINT64_C(0x10000000000000) : 0), (e ? (int)e : 1)-1023-52);
  return v;
}
static ld_value ld_decode(unsigned fmt, ld_raw r) {
  if (fmt == 64) return ld_decode64(r.hi);
  if (fmt == 106) {
    ld_value a = ld_decode64(r.hi), b = ld_decode64(r.lo);
    a.invalid |= b.invalid;
    if (b.kind != LD_FINITE || (a.kind == LD_INF && (r.lo << 1))) { a.kind = LD_NAN; a.invalid = 1; }
    if (b.kind == LD_NAN) a.kind = LD_NAN;
    if (a.kind == LD_FINITE) {
      int zero_sign = a.sign;
      ld_add(&a,&b);
      if (ld_top(&a) < 0 && !(r.hi << 1) && !(r.lo << 1)) a.sign = zero_sign;
      /* Canonical native DD finite range: DBL_MAX plus the largest binary64
       * below half its ulp. Arbitrary overlapping pairs can exceed it. */
      ld_value limit = ld_decode64(UINT64_C(0x7fefffffffffffff));
      ld_value tail = ld_decode64(UINT64_C(0x7c8fffffffffffff));
      ld_add(&limit,&tail);
      if (ld_cmpmag(&a,&limit) > 0) { a.kind = LD_NAN; a.invalid = 1; }
    }
    return a;
  }
  ld_value v = {{0},0,LD_FINITE,0};
  unsigned e;
  if (fmt == 80) {
    e = (unsigned)(r.hi & 32767); v.sign = (int)((r.hi >> 15) & 1);
    if (e && !(r.lo >> 63)) { v.kind = LD_NAN; v.invalid = 1; }
    else if (e == 32767) { v.kind = r.lo == UINT64_C(0x8000000000000000) ? LD_INF : LD_NAN; v.invalid = v.kind == LD_NAN && !(r.lo & UINT64_C(0x4000000000000000)); }
    else ld_insert(&v,r.lo,(e ? (int)e : 1)-16383-63);
  } else {
    e = (unsigned)((r.hi >> 48) & 32767); v.sign = (int)(r.hi >> 63);
    uint64_t m = r.hi & UINT64_C(0xffffffffffff);
    if (e == 32767) { v.kind = (m || r.lo) ? LD_NAN : LD_INF; v.invalid = v.kind == LD_NAN && !(m & UINT64_C(0x800000000000)); }
    else { int shift = (e ? (int)e : 1)-16383-112; ld_insert(&v,r.lo,shift); ld_insert(&v,m | (e ? UINT64_C(0x1000000000000) : 0),shift+64); }
  }
  return v;
}
static int ld_any_below(const ld_value *v, int cut) {
  if (cut > LD_WORDS*32) cut = LD_WORDS*32;
  for (int i = 0; i < cut / 32; ++i) if (v->w[i]) return 1;
  return cut > 0 && cut % 32 && (v->w[cut/32] & ((UINT32_C(1) << (cut%32))-1));
}
static void ld_clear_below(ld_value *v, int cut) {
  for (int i = 0; i < cut / 32; ++i) v->w[i] = 0;
  if (cut % 32) v->w[cut/32] &= ~((UINT32_C(1) << (cut%32))-1);
}
static void ld_increment(ld_value *v, int bit) {
  while (ld_bit(v,bit)) { v->w[bit/32] &= ~(UINT32_C(1) << (bit%32)); ++bit; }
  ld_set(v,bit);
}
static ld_raw ld_pack_single(unsigned fmt, const ld_value *v) {
  unsigned p = fmt == 64 ? 53 : fmt == 80 ? 64 : 113;
  int bias = fmt == 64 ? 1023 : 16383;
  ld_raw r = {0,0}; int top = ld_top(v), exp = 0;
  if (v->kind != LD_FINITE) {
    exp = 2*bias+1;
    if (fmt == 80) r.lo = UINT64_C(0x8000000000000000) | (v->kind == LD_NAN ? UINT64_C(0x4000000000000000) : 0);
    else if (v->kind == LD_NAN) r.hi = UINT64_C(1) << (fmt == 64 ? 51 : 47);
  } else if (top >= 0) {
    int exponent = top+LD_BASE, cut = top-(int)p+1;
    int mincut = 1-bias-(int)p+1-LD_BASE;
    if (cut < mincut) cut = mincut;
    uint64_t low = 0, high = 0;
    for (int i = top; i >= cut; --i) { high = (high<<1) | (low>>63); low = (low<<1) | (unsigned)ld_bit(v,i); }
    if (ld_bit(v,cut-1) && (ld_any_below(v,cut-1) || (low & 1))) { ++low; if (!low) ++high; }
    int carry = p == 64 ? high != 0 : p == 53 ? (low >> 53) != 0 : (high >> 49) != 0;
    if (carry) { low = (low>>1) | (high<<63); high >>= 1; ++exponent; }
    if (exponent > bias) { exp=2*bias+1; if (fmt == 80) r.lo = UINT64_C(0x8000000000000000); }
    else {
      int normal = fmt == 64 ? (low >> 52) != 0 : fmt == 80 ? (low >> 63) != 0 : (high >> 48) != 0;
      exp = normal ? (exponent < 1-bias ? 1 : exponent+bias) : 0;
      if (fmt == 64) r.hi = low & UINT64_C(0xfffffffffffff);
      else { r.lo = low; r.hi = high & UINT64_C(0xffffffffffff); }
    }
  }
  int sign = v->kind == LD_NAN ? 0 : v->sign;
  if (fmt == 80) r.hi = (uint64_t)exp | ((uint64_t)sign<<15);
  else r.hi |= ((uint64_t)exp << (fmt == 64 ? 52 : 48)) | ((uint64_t)sign<<63);
  return r;
}
static ld_raw ld_pack(unsigned fmt, const ld_value *v) {
  if (fmt != 106) return ld_pack_single(fmt,v);
  ld_raw hi = ld_pack_single(64,v), r = {hi.hi,0};
  if (v->kind != LD_FINITE || ld_top(v) < 0) return r;
  /* A finite DD can sit above binary64's overflow midpoint. Clamp its leader
   * to maximum finite before finding the exact residual. */
  if ((r.hi & UINT64_C(0x7fffffffffffffff)) == UINT64_C(0x7ff0000000000000))
    r.hi = ((uint64_t)v->sign<<63) | UINT64_C(0x7fefffffffffffff);
  ld_value residual = *v, leader = ld_decode64(r.hi);
  leader.sign ^= 1; ld_add(&residual,&leader);
  r.lo = ld_pack_single(64,&residual).hi;
  if (!(r.lo << 1)) r.lo = 0;
  return r;
}
static void ld_shift(ld_value *v, int shift) {
  ld_value out = {{0},v->sign,v->kind,v->invalid};
  for (int i = 0; i < LD_WORDS*32; ++i) if (ld_bit(v,i)) ld_set(&out,i+shift);
  *v = out;
}
static int ld_cmp(const ld_value *a, const ld_value *b) {
  if (a->sign != b->sign) return a->sign ? -1 : 1;
  int c = a->kind == LD_INF ? (b->kind == LD_INF ? 0 : 1) : b->kind == LD_INF ? -1 : ld_cmpmag(a,b);
  return a->sign ? -c : c;
}
#endif
