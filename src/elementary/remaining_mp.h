/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Private normalized sign/magnitude binary arithmetic. The eight little-endian
 * words encode m*2^(e-255). All operations truncate toward zero at 256 bits;
 * no operation accesses floating controls or raises a floating exception.
 */
#ifndef GHOTI_IO_GMATH_REMAINING_MP_H
#define GHOTI_IO_GMATH_REMAINING_MP_H
#include <ghoti.io/math/macros.h>
#include <stdint.h>
#include <string.h>
typedef struct {
  uint32_t w[8];
  int e, s;
} rmp;
static inline rmp rm_zero(void) {
  rmp a = {{0}, 0, 0};
  return a;
}
static inline int rm_nonzero(rmp a) {
  return a.w[7] != 0;
}
static inline unsigned rm_top(uint32_t x) {
  unsigned n = 0;
  while (x >> 1) {
    x >>= 1;
    ++n;
  }
  return n;
}
static inline rmp rm_norm(rmp a) {
  int i = 7;
  while (i >= 0 && !a.w[i])
    --i;
  if (i < 0)
    return rm_zero();
  unsigned shift = 31 - rm_top(a.w[i]);
  int whole = 7 - i;
  for (int j = 7; j >= 0; --j) {
    uint32_t v = 0;
    if (j >= whole) {
      v = a.w[j - whole] << shift;
      if (shift && j > whole)
        v |= a.w[j - whole - 1] >> (32 - shift);
    }
    a.w[j] = v;
  }
  a.e -= whole * 32 + (int)shift;
  return a;
}
static inline rmp rm_uint(uint64_t n) {
  rmp a = rm_zero();
  a.w[0] = (uint32_t)n;
  a.w[1] = (uint32_t)(n >> 32);
  a.e = 255;
  return rm_norm(a);
}
static inline rmp rm_neg(rmp a) {
  if (rm_nonzero(a))
    a.s ^= 1;
  return a;
}
static inline rmp rm_scale(rmp a, int n) {
  a.e += n;
  return a;
}
static inline int rm_cmp(rmp a, rmp b) {
  if (!rm_nonzero(a))
    return rm_nonzero(b) ? -1 : 0;
  if (!rm_nonzero(b))
    return 1;
  if (a.e != b.e)
    return a.e > b.e ? 1 : -1;
  for (int i = 7; i >= 0; --i)
    if (a.w[i] != b.w[i])
      return a.w[i] > b.w[i] ? 1 : -1;
  return 0;
}
/* Exact truncation with a 32-bit guard word. For subtraction a discarded
 * nonzero tail is represented by rounding the aligned small magnitude up:
 * floor(A-B) = A-ceil(B) at this guard scale. Cancellation that could expose
 * the guard has gap<=32, where alignment discards nothing. */
static inline rmp rm_add(rmp a, rmp b) {
  if (!rm_nonzero(a))
    return b;
  if (!rm_nonzero(b))
    return a;
  if (rm_cmp(a, b) < 0) {
    rmp t = a;
    a = b;
    b = t;
  }
  unsigned gap = (unsigned)(a.e - b.e);
  uint32_t wide[10] = {0}, small[10] = {0};
  for (unsigned i = 0; i < 8; ++i)
    wide[i + 1] = a.w[i];
  unsigned sticky = 0;
  if (gap <= 32) {
    unsigned shift = 32 - gap, whole = shift / 32, part = shift % 32;
    for (unsigned i = 0; i < 8; ++i) {
      small[i + whole] |= b.w[i] << part;
      if (part)
        small[i + whole + 1] |= b.w[i] >> (32 - part);
    }
  }
  else {
    unsigned shift = gap - 32, whole = shift / 32, part = shift % 32;
    for (unsigned i = 0; i < 8; ++i) {
      if (i + whole < 8) {
        small[i] = b.w[i + whole] >> part;
        if (part && i + whole + 1 < 8)
          small[i] |= b.w[i + whole + 1] << (32 - part);
      }
    }
    for (unsigned i = 0; i < whole && i < 8; ++i)
      sticky |= b.w[i];
    if (part && whole < 8)
      sticky |= b.w[whole] & ((UINT32_C(1) << part) - 1);
  }
  if (a.s != b.s && sticky) {
    uint64_t carry = 1;
    for (unsigned i = 0; i < 10 && carry; ++i) {
      uint64_t v = (uint64_t)small[i] + carry;
      small[i] = (uint32_t)v;
      carry = v >> 32;
    }
  }
  uint64_t carry = 0;
  for (unsigned i = 0; i < 10; ++i) {
    if (a.s == b.s) {
      uint64_t v = (uint64_t)wide[i] + small[i] + carry;
      wide[i] = (uint32_t)v;
      carry = v >> 32;
    }
    else {
      uint64_t sub = (uint64_t)small[i] + carry;
      uint32_t old = wide[i];
      wide[i] = (uint32_t)((uint64_t)old - sub);
      carry = (uint64_t)old < sub;
    }
  }
  int word = 9;
  while (word >= 0 && !wide[word])
    --word;
  if (word < 0)
    return rm_zero();
  int top = word * 32 + (int)rm_top(wide[word]), cut = top - 255;
  rmp r = rm_zero();
  r.s = a.s;
  r.e = a.e + top - 287;
  if (cut >= 0) {
    unsigned whole = (unsigned)cut / 32, part = (unsigned)cut % 32;
    for (unsigned i = 0; i < 8; ++i) {
      if (i + whole < 10) {
        r.w[i] = wide[i + whole] >> part;
        if (part && i + whole + 1 < 10)
          r.w[i] |= wide[i + whole + 1] << (32 - part);
      }
    }
  }
  else {
    unsigned shift = (unsigned)(-cut), whole = shift / 32, part = shift % 32;
    for (unsigned i = 0; i < 8; ++i)
      if (i >= whole) {
        r.w[i] = wide[i - whole] << part;
        if (part && i > whole)
          r.w[i] |= wide[i - whole - 1] >> (32 - part);
      }
  }
  return r;
}
static inline rmp rm_sub(rmp a, rmp b) {
  return rm_add(a, rm_neg(b));
}
static inline rmp rm_mul(rmp a, rmp b) {
  if (!rm_nonzero(a) || !rm_nonzero(b))
    return rm_zero();
  uint32_t p[16] = {0};
  for (unsigned i = 0; i < 8; ++i) {
    uint64_t c = 0;
    for (unsigned j = 0; j < 8; ++j) {
      uint64_t v = (uint64_t)a.w[i] * b.w[j] + p[i + j] + c;
      p[i + j] = (uint32_t)v;
      c = v >> 32;
    }
    p[i + 8] = (uint32_t)c;
  }
  rmp r = rm_zero();
  r.s = a.s ^ b.s;
  r.e = a.e + b.e + 1;
  for (int i = 0; i < 8; ++i)
    r.w[i] = p[i + 8];
  if (!(p[15] & UINT32_C(0x80000000))) {
    for (int i = 0; i < 8; ++i)
      r.w[i] = (p[i + 8] << 1) | (p[i + 7] >> 31);
    --r.e;
  }
  return r;
}
static inline rmp rm_div(rmp a, rmp b) {
  if (!rm_nonzero(a))
    return a;
  /* Remainder is nine words, so its shift cannot lose the carry bit. */
  uint32_t rem[9] = {0};
  rmp q = rm_zero();
  q.s = a.s ^ b.s;
  q.e = a.e - b.e;
  for (int i = 0; i < 8; ++i)
    rem[i] = a.w[i];
  if (rm_cmp(rm_scale(a, -a.e), rm_scale(b, -b.e)) < 0) {
    uint32_t c = 0;
    for (int i = 0; i < 9; ++i) {
      uint32_t n = rem[i] >> 31;
      rem[i] = (rem[i] << 1) | c;
      c = n;
    }
    --q.e;
  }
  for (int bit = 255; bit >= 0; --bit) {
    int cmp = rem[8] ? 1 : 0;
    if (!cmp) {
      for (int i = 7; i >= 0; --i)
        if (rem[i] != b.w[i]) {
          cmp = rem[i] > b.w[i] ? 1 : -1;
          break;
        }
    }
    if (cmp >= 0) {
      uint64_t borrow = 0;
      for (int i = 0; i < 8; ++i) {
        uint64_t sub = (uint64_t)b.w[i] + borrow;
        uint32_t old = rem[i];
        rem[i] = (uint32_t)((uint64_t)old - sub);
        borrow = (uint64_t)old < sub;
      }
      rem[8] -= (uint32_t)borrow;
      q.w[bit / 32] |= UINT32_C(1) << (bit % 32);
    }
    uint32_t c = 0;
    for (int i = 0; i < 9; ++i) {
      uint32_t n = rem[i] >> 31;
      rem[i] = (rem[i] << 1) | c;
      c = n;
    }
  }
  return q;
}
static inline rmp rm_int(int n) {
  rmp a = rm_uint((uint64_t)(n < 0 ? -(int64_t)n : n));
  a.s = n < 0;
  return a;
}
static inline rmp rm_over(rmp a, unsigned n) {
  if (!rm_nonzero(a))
    return a;
  uint32_t q[9];
  uint64_t rem = 0;
  for (int i = 8; i >= 0; --i) {
    uint64_t v = (rem << 32) | (i ? a.w[i - 1] : 0);
    q[i] = (uint32_t)(v / n);
    rem = v % n;
  }
  int top = 8;
  while (!q[top])
    --top;
  int bit = top * 32 + (int)rm_top(q[top]), cut = bit - 255;
  unsigned whole = (unsigned)cut / 32, shift = (unsigned)cut % 32;
  for (unsigned i = 0; i < 8; ++i) {
    a.w[i] = q[i + whole] >> shift;
    if (shift && i + whole + 1 < 9)
      a.w[i] |= q[i + whole + 1] << (32 - shift);
  }
  a.e += bit - 287;
  return a;
}
static inline rmp rm_raw(uint64_t bits, unsigned p, int bias) {
  uint64_t sign = UINT64_C(1) << (p + (p == 52 ? 11 : 8)),
           a = bits & (sign - 1);
  unsigned f = (unsigned)(a >> p);
  uint64_t m = a & ((UINT64_C(1) << p) - 1);
  int e = 1 - bias - (int)p;
  if (f) {
    m |= UINT64_C(1) << p;
    e = (int)f - bias - (int)p;
  }
  rmp r = rm_uint(m);
  r.e += e;
  r.s = (bits & sign) != 0;
  return r;
}
static inline unsigned rm_bit(rmp a, int bit) {
  return bit >= 0 && bit < 256 ? (a.w[bit / 32] >> (bit % 32)) & 1u : 0;
}
/* Nearest/even final packing, independently of caller mode. */
static inline uint64_t rm_pack(rmp a, unsigned p, int bias) {
  uint64_t sign = (uint64_t)a.s << (p + (p == 52 ? 11 : 8));
  if (!rm_nonzero(a))
    return sign;
  int cut = 255 - (int)p;
  if (a.e < 1 - bias)
    cut += 1 - bias - a.e;
  uint64_t q = 0;
  for (int i = 255; i >= cut; --i)
    q = (q << 1) | rm_bit(a, i);
  unsigned sticky = 0;
  for (int i = 0; i < cut - 1 && i < 256; ++i)
    sticky |= rm_bit(a, i);
  q += rm_bit(a, cut - 1) && (sticky || (q & 1));
  if (a.e < 1 - bias)
    return sign | q;
  int e = a.e;
  if (q == (UINT64_C(1) << (p + 1))) {
    q >>= 1;
    ++e;
  }
  if (e > bias)
    return sign | ((uint64_t)(2 * bias + 1) << p);
  return sign | ((uint64_t)(e + bias) << p) | (q & ((UINT64_C(1) << p) - 1));
}
#endif
