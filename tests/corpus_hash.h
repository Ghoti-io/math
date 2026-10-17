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

#endif /* GHOTI_IO_GMATH_CORPUS_HASH_H */
