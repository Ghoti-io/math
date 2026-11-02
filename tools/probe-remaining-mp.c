/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff */
#include "../src/elementary/remaining_mp.h"
#include <inttypes.h>
#include <stdio.h>
static void emit(rmp r) {
  printf("%d %d", r.s, r.e);
  for (int i = 7; i >= 0; --i)
    printf(" %08" PRIx32, r.w[i]);
  putchar('\n');
}
static int raw(void) {
  unsigned op;
  while (scanf("%u", &op) == 1) {
    rmp a = rm_zero(), b = rm_zero();
    if (scanf("%d %d", &a.s, &a.e) != 2)
      return 2;
    for (int i = 7; i >= 0; --i)
      if (scanf("%" SCNx32, &a.w[i]) != 1)
        return 2;
    if (scanf("%d %d", &b.s, &b.e) != 2)
      return 2;
    for (int i = 7; i >= 0; --i)
      if (scanf("%" SCNx32, &b.w[i]) != 1)
        return 2;
    if (op == 5) {
      unsigned p = (unsigned)b.e;
      printf("%016" PRIx64 "\n", rm_pack(a, p, p == 52 ? 1023 : 127));
    }
    else {
      rmp r;
      if (op == 0)
        r = rm_add(a, b);
      else if (op == 1)
        r = rm_sub(a, b);
      else if (op == 2)
        r = rm_mul(a, b);
      else if (op == 3)
        r = rm_div(a, b);
      else
        return 2;
      emit(r);
    }
  }
  return ferror(stdin) ? 1 : 0;
}
int main(int argc, char ** argv) {
  if (argc == 2 && !strcmp(argv[1], "--raw"))
    return raw();
  if (argc != 1)
    return 2;
  unsigned op;
  uint64_t x, y;
  while (scanf("%u %" SCNx64 " %" SCNx64, &op, &x, &y) == 3) {
    rmp a = rm_raw(x, 52, 1023), b = rm_raw(y, 52, 1023), r;
    if (op == 0)
      r = rm_add(a, b);
    else if (op == 1)
      r = rm_sub(a, b);
    else if (op == 2)
      r = rm_mul(a, b);
    else if (op == 3) {
      if (!rm_nonzero(b))
        return 2;
      r = rm_div(a, b);
    }
    else {
      if (!y || y > UINT32_MAX)
        return 2;
      r = rm_over(a, (unsigned)y);
    }
    emit(r);
  }
  return ferror(stdin) ? 1 : 0;
}
