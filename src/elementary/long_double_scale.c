/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Native long-double foundation. All numerical decisions use integers;
 * native arithmetic registers carry only the final ABI return value. */
#include <float.h>
#include <limits.h>
#include <ghoti.io/math/basic.h>
#include "elem_common.h"
#include "long_double_bits.h"
#if LDBL_MANT_DIG == 53 && LDBL_MAX_EXP == 1024
#define LD_NATIVE 64
#elif LDBL_MANT_DIG == 64 && LDBL_MAX_EXP == 16384
#define LD_NATIVE 80
#elif LDBL_MANT_DIG == 113 && LDBL_MAX_EXP == 16384
#define LD_NATIVE 128
#elif LDBL_MANT_DIG == 106 && LDBL_MAX_EXP == 1024
#define LD_NATIVE 106
#else
#error Unsupported native long double representation
#endif
#define LD_JOIN_(a,b) a##b
#define LD_JOIN(a,b) LD_JOIN_(a,b)
static const unsigned LD_JOIN(gmath_long_double_scale_format_,LD_NATIVE)
    __attribute__((used)) = LD_NATIVE;
static ld_raw ld_read(const unsigned char *p) {
  ld_raw r = {0,0};
#if LD_NATIVE == 64
  memcpy(&r.hi,p,8);
#elif LD_NATIVE == 80
  uint16_t se;
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
  memcpy(&se,p,2); memcpy(&r.lo,p+sizeof(long double)-8,8);
#else
  memcpy(&r.lo,p,8); memcpy(&se,p+8,2);
#endif
  r.hi=se;
#elif LD_NATIVE == 128
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
  memcpy(&r.hi,p,8); memcpy(&r.lo,p+8,8);
#else
  memcpy(&r.lo,p,8); memcpy(&r.hi,p+8,8);
#endif
#else
  memcpy(&r.hi,p,8); memcpy(&r.lo,p+8,8);
#endif
  return r;
}
static void ld_write(unsigned char *p, ld_raw r) {
  memset(p,0,sizeof(long double));
#if LD_NATIVE == 64
  memcpy(p,&r.hi,8);
#elif LD_NATIVE == 80
  uint16_t se = (uint16_t)r.hi;
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
  memcpy(p,&se,2); memcpy(p+sizeof(long double)-8,&r.lo,8);
#else
  memcpy(p,&r.lo,8); memcpy(p+8,&se,2);
#endif
#elif LD_NATIVE == 128
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
  memcpy(p,&r.hi,8); memcpy(p+8,&r.lo,8);
#else
  memcpy(p,&r.lo,8); memcpy(p+8,&r.hi,8);
#endif
#else
  memcpy(p,&r.hi,8); memcpy(p+8,&r.lo,8);
#endif
}
#include "long_double_scale_bits.h"
/* Private synthetic probes reuse adapters without defining public wrappers. */
#ifndef GMATH_LONG_DOUBLE_SCALE_RAW_ONLY
static void lds_bytes(int op,const unsigned char *x,const unsigned char *y,
                      unsigned char *out,long exponent)
  __asm__("gmath_long_double_scale_bytes") __attribute__((noinline,used));
static void lds_bytes(int op,const unsigned char *x,const unsigned char *y,
                      unsigned char *out,long exponent) {
  ld_raw a=ld_read(x),b={0,0};if(y)b=ld_read(y);
  ld_write(out,lds_run(LD_NATIVE,op,a,b,exponent));
}
#if LD_NATIVE == 80 && defined(__x86_64__) && defined(__ELF__) && (defined(__GNUC__) || defined(__clang__))
#define LDS_STRING_(x) #x
#define LDS_STRING(x) LDS_STRING_(x)
#if defined(__clang__)
#define LDS_UNREACHABLE
#else
#define LDS_UNREACHABLE __builtin_unreachable();
#endif
#define LDS_WRAPPER(signature,op,exponent,second) \
 __attribute__((naked)) signature { __asm__( \
 "subq $24, %rsp\n\t.cfi_adjust_cfa_offset 24\n\t" exponent \
 "movl $" LDS_STRING(op) ", %edi\n\tleaq 32(%rsp), %rsi\n\t" second \
 "movq %rsp, %rcx\n\tcall gmath_long_double_scale_bytes\n\tfldt (%rsp)\n\t" \
 "addq $24, %rsp\n\t.cfi_adjust_cfa_offset -24\n\tret");LDS_UNREACHABLE }
#define LDS_SCALE(name,op,type,conversion) LDS_WRAPPER(long double name(long double x __attribute__((unused)),type n __attribute__((unused))),op,conversion,"xorl %edx, %edx\n\t")
LDS_SCALE(gmath_ldexpl,0,int,"movslq %edi, %r8\n\t")
LDS_SCALE(gmath_scalbnl,1,int,"movslq %edi, %r8\n\t")
LDS_SCALE(gmath_scalblnl,2,long,"movq %rdi, %r8\n\t")
#define LDS_ADJ(name,op) LDS_WRAPPER(long double name(long double x __attribute__((unused)),long double y __attribute__((unused))),op,"xorl %r8d, %r8d\n\t","leaq 48(%rsp), %rdx\n\t")
LDS_ADJ(gmath_nextafterl,3)
LDS_ADJ(gmath_nexttowardl,4)
#else
#define LDS_SCALE(name,op,type) long double name(long double x,type n) {long double out;lds_bytes(op,(const unsigned char *)&x,0,(unsigned char *)&out,n);return out;}
LDS_SCALE(gmath_ldexpl,0,int)
LDS_SCALE(gmath_scalbnl,1,int)
LDS_SCALE(gmath_scalblnl,2,long)
#define LDS_ADJ(name,op) long double name(long double x,long double y) {long double out;lds_bytes(op,(const unsigned char *)&x,(const unsigned char *)&y,(unsigned char *)&out,0);return out;}
LDS_ADJ(gmath_nextafterl,3)
LDS_ADJ(gmath_nexttowardl,4)
#endif

#endif /* !GMATH_LONG_DOUBLE_SCALE_RAW_ONLY */
