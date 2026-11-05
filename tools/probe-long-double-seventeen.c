/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Raw-layout probe. No oracle participates in the implementation. */
#define GMATH_LONG_DOUBLE_SEVENTEEN_RAW_ONLY
#include "../src/elementary/long_double_seventeen.c"
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include "long_double_seventeen_probe_input.h"
static unsigned flags(void) {
  int f=fetestexcept(FE_ALL_EXCEPT);
  return ((f&FE_INVALID)?1u:0u)|((f&FE_DIVBYZERO)?2u:0u)|((f&FE_INEXACT)?4u:0u)|((f&FE_UNDERFLOW)?8u:0u)|((f&FE_OVERFLOW)?16u:0u);
}
int main(void) {
  char line[512];unsigned rows=0;int record;
  while((record=lds17_probe_record(line,sizeof line))>0) {
    uint64_t fields[6];if(!lds17_probe_fields(line,fields,6,1))return 2;
    if((fields[0]!=64 && fields[0]!=80 && fields[0]!=106 && fields[0]!=128) || fields[1]>16)return 2;
    unsigned fmt=(unsigned)fields[0],op=(unsigned)fields[1];
    if(feclearexcept(FE_ALL_EXCEPT) || flags())return 2;
    errno=123;
    ld_raw out=lds17_run(fmt,(int)op,(ld_raw){fields[2],fields[3]},(ld_raw){fields[4],fields[5]});
    printf("%016"PRIx64" %016"PRIx64" %u %d\n",out.hi,out.lo,flags(),errno);fflush(stdout);++rows;
  }
  if(record<0 || ferror(stdin) || !rows)return 2;
  return 0;
}
