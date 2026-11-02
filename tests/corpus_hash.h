/*
 * The corpus hash: FNV-1a 64 over the little-endian bytes of each result.
 *
 * A local helper for the sin/cos/tan corpus; the spelling that the shape
 * family uses everywhere lands in shape-geometry (CAP-13), and this is to be
 * replaced by it then.  The bytes are produced by shifting, never by reading
 * the double's memory, so the hash does not depend on the host's byte order.
 * Plain C so that the cross-target probe (tools/corpus-hash.c) and the C++
 * test hash the same way.
 */

#ifndef GHOTI_IO_GMATH_CORPUS_HASH_H
#define GHOTI_IO_GMATH_CORPUS_HASH_H

#include <stdint.h>
#include <string.h>

#define GMATH_FNV_BASIS 0xcbf29ce484222325ull
#define GMATH_FNV_PRIME 0x100000001b3ull

static inline uint64_t gmath_fnv_u64(uint64_t h, uint64_t v) {
  for (int i = 0; i < 8; i++) {
    h ^= (v >> (8 * i)) & 0xffu;
    h *= GMATH_FNV_PRIME;
  }
  return h;
}

static inline uint64_t gmath_fnv_double(uint64_t h, double d) {
  uint64_t u;
  memcpy(&u, &d, sizeof u);
  return gmath_fnv_u64(h, u);
}

/* Shared strict integer-only inverse-family row parser. Kept in this existing
 * cross-probe header so a standalone copied client needs no new include or
 * platform runtime. Numeric conversions are checked before accumulation.
 */
typedef struct {
  unsigned width;
  uint64_t input, target[2];
  unsigned flags[2];
  int64_t low[2], high[2];
} gmath_inverse_row;

static inline int gmath_parse_inverse_row(const char *line, gmath_inverse_row *row) {
  const char *cursor=line;
  for (unsigned field=0;field<10;++field) {
    while (*cursor==' ') ++cursor;
    int negative=*cursor=='-';
    if (negative) ++cursor;
    const char *start=cursor;
    unsigned base=(field==1||field==2||field==6)?16u:10u;
    uint64_t value=0;
    while (*cursor && *cursor!=' ' && *cursor!='\n') {
      unsigned digit=*cursor>='0'&&*cursor<='9'?(unsigned)(*cursor-'0'):
          *cursor>='a'&&*cursor<='f'?(unsigned)(*cursor-'a'+10):16u;
      if (digit>=base || value>(UINT64_MAX-digit)/base) return 1;
      value=value*base+digit;++cursor;
    }
    if (cursor==start) return 1;
    if (field==0) {
      if (negative || !(value==32||value==64)) return 1;
      row->width=(unsigned)value;
    } else if (base==16) {
      if (negative || cursor-start!=(int)(row->width/4) ||
          (row->width==32 && value>UINT32_MAX)) return 1;
      if (field==1) row->input=value;
      else row->target[field==2?0:1]=value;
    } else if (field==3||field==7) {
      if (negative || value>31) return 1;
      row->flags[field==3?0:1]=(unsigned)value;
    } else {
      if (value>UINT64_C(536870913)) return 1;
      int64_t residual=negative?-(int64_t)value:(int64_t)value;
      unsigned index=field<6?0u:1u;
      if (field==4||field==8) row->low[index]=residual;
      else row->high[index]=residual;
    }
  }
  while (*cursor==' ') ++cursor;
  return !(*cursor=='\n' && cursor[1]=='\0');
}

/* Bounded integer-only triple rows for the hyperbolic family. */
typedef struct {
  unsigned width;
  uint64_t input, target[3];
  unsigned flags[3];
  int64_t low[3], high[3];
} gmath_hyperbolic_row;

static inline int gmath_parse_hyperbolic_row(const char *line, gmath_hyperbolic_row *row) {
  const char *cursor=line;
  for (unsigned field=0;field<14;++field) {
    while (*cursor==' ') ++cursor;
    int negative=*cursor=='-';
    if (negative) ++cursor;
    const char *start=cursor;
    unsigned base=(field==1||field==2||field==6||field==10)?16u:10u;
    uint64_t value=0;
    while (*cursor && *cursor!=' ' && *cursor!='\n') {
      unsigned digit=*cursor>='0'&&*cursor<='9'?(unsigned)(*cursor-'0'):
          *cursor>='a'&&*cursor<='f'?(unsigned)(*cursor-'a'+10):16u;
      if (digit>=base || value>(UINT64_MAX-digit)/base) return 1;
      value=value*base+digit;++cursor;
    }
    if (cursor==start) return 1;
    if (field==0) {
      if (negative || !(value==32||value==64)) return 1;
      row->width=(unsigned)value;
    } else if (base==16) {
      if (negative || cursor-start!=(int)(row->width/4) ||
          (row->width==32 && value>UINT32_MAX)) return 1;
      if (field==1) row->input=value;
      else row->target[(field-2)/4]=value;
    } else if (field==3||field==7||field==11) {
      if (negative || value>31) return 1;
      row->flags[(field-3)/4]=(unsigned)value;
    } else {
      if (value>UINT64_C(536870913)) return 1;
      int64_t residual=negative?-(int64_t)value:(int64_t)value;
      unsigned index=(field-2)/4;
      if (field==4||field==8||field==12) row->low[index]=residual;
      else row->high[index]=residual;
    }
  }
  while (*cursor==' ') ++cursor;
  return !(*cursor=='\n' && cursor[1]=='\0');
}

#endif /* GHOTI_IO_GMATH_CORPUS_HASH_H */
