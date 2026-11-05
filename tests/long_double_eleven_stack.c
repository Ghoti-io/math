/* SPDX-License-Identifier: LGPL-3.0-only */
#define _GNU_SOURCE
#define GMATH_LONG_DOUBLE_ELEVEN_RAW_ONLY
#include "../src/elementary/long_double_eleven.c"
#include "long_double_eleven_abi.h"
#include <pthread.h>
#include <sys/mman.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
static void *run(void *unused) {
 (void)unused;
 ld_raw one={0x3ff0000000000000,1},huge={0x7fe0000000000000,0},tiny={1,0};
 ld_raw result=lde_run(106,LDE_POW,one,huge);
 if(result.hi!=0x3ff0000000000002 || result.lo!=0x3980000000000001)abort();
 result=lde_run(106,LDE_LOG,one,tiny);if(result.hi!=1 || result.lo)abort();
 result=lde_run(106,LDE_EXP,tiny,tiny);if(result.hi!=0x3ff0000000000000 || result.lo!=1)abort();
 result=lde_run(128,LDE_HYPOT,(ld_raw){0,1},(ld_raw){0,1});if(result.hi || result.lo!=1)abort();
 for(int op=0;op<11;++op) {
  long double x=2.0L,y=3.0L,out;
#if defined(LDE_BYTE_CALLER)
  lde_native80_bytes(op,&x,&y,&out);
#else
  switch(op) {
  case 0:out=gmath_sqrtl(x);break;case 1:out=gmath_cbrtl(x);break;
  case 2:out=gmath_hypotl(x,y);break;case 3:out=gmath_expl(x);break;
  case 4:out=gmath_exp2l(x);break;case 5:out=gmath_expm1l(x);break;
  case 6:out=gmath_logl(x);break;case 7:out=gmath_log2l(x);break;
  case 8:out=gmath_log10l(x);break;case 9:out=gmath_log1pl(x);break;
  default:out=gmath_powl(x,y);break;
  }
#endif
  if(ld_read((unsigned char *)&out).hi==0)abort();
 }
 return 0;
}
int main(void) {
 const size_t usable=2*1024*1024;size_t page=(size_t)sysconf(_SC_PAGESIZE);
 unsigned char *mapping=mmap(0,usable+2*page,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
 if(mapping==MAP_FAILED || mprotect(mapping+page,usable,PROT_READ|PROT_WRITE))return 2;
 pthread_attr_t attr;if(pthread_attr_init(&attr) || pthread_attr_setstack(&attr,mapping+page,usable))return 3;
 pthread_t worker;if(pthread_create(&worker,&attr,run,0) || pthread_join(worker,0))return 4;
 pthread_attr_destroy(&attr);munmap(mapping,usable+2*page);puts("2MiB usable stack with two inaccessible guard pages: eleven native ABI and DD/128 hard witnesses pass");return 0;
}
