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
static const unsigned LD_JOIN(gmath_long_double_nine_format_,LD_NATIVE)
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
#include "nearby_mode.h"
#include "long_double_scale_bits.h"
#include "long_double_nine_bits.h"

#ifndef GMATH_LONG_DOUBLE_NINE_RAW_ONLY
GMATH_STATIC_ASSERT((LONG_MAX==INT32_MAX || LONG_MAX==INT64_MAX) &&
  LONG_MIN == -LONG_MAX-1 && LLONG_MAX==INT64_MAX && LLONG_MIN == -LLONG_MAX-1,
  "long-double integer conversion requires signed32/64 long and signed64 long long");
static int64_t ldn_integer_bytes(int current,const unsigned char *x,unsigned bits)
  __asm__("gmath_long_double_nine_integer_bytes") __attribute__((noinline,used));
static int64_t ldn_integer_bytes(int current,const unsigned char *x,unsigned bits) {
  return ldn_integer(LD_NATIVE,ld_read(x),current,current?ldn_mode():0,bits);
}
static void ldn_bytes(int op,const unsigned char *x,const unsigned char *y,
  const unsigned char *z,unsigned char *out,int *q)
  __asm__("gmath_long_double_nine_bytes") __attribute__((noinline,used));
static void ldn_bytes(int op,const unsigned char *x,const unsigned char *y,
  const unsigned char *z,unsigned char *out,int *q) {
  ld_raw a=ld_read(x),b=ld_read(y),c={0,0};if(z)c=ld_read(z);
  ld_write(out,ldn_run(LD_NATIVE,op,a,b,c,op==LDN_FMA?ldn_mode():0,q));
}
#if LD_NATIVE == 80 && defined(__x86_64__) && defined(__ELF__) && (defined(__GNUC__) || defined(__clang__))
#define LDN_STRING_(x) #x
#define LDN_STRING(x) LDN_STRING_(x)
#if defined(__clang__)
#define LDN_UNREACHABLE
#else
#define LDN_UNREACHABLE __builtin_unreachable();
#endif
#define LDN_INT(name,type,current,bits) \
 __attribute__((naked)) type name(long double x __attribute__((unused))) { __asm__( \
 "subq $24, %rsp\n\t.cfi_adjust_cfa_offset 24\n\t" \
 "movl $" LDN_STRING(current) ", %edi\n\tleaq 32(%rsp), %rsi\n\t" \
 "movl $" LDN_STRING(bits) ", %edx\n\tcall gmath_long_double_nine_integer_bytes\n\t" \
 "addq $24, %rsp\n\t.cfi_adjust_cfa_offset -24\n\tret");LDN_UNREACHABLE }
LDN_INT(gmath_lroundl,long,0,__SIZEOF_LONG__*8)
LDN_INT(gmath_llroundl,long long,0,64)
LDN_INT(gmath_lrintl,long,1,__SIZEOF_LONG__*8)
LDN_INT(gmath_llrintl,long long,1,64)
#define LDN_REAL(signature,op,third,quotient) \
 __attribute__((naked)) signature { __asm__( \
 "subq $24, %rsp\n\t.cfi_adjust_cfa_offset 24\n\t" quotient \
 "movl $" LDN_STRING(op) ", %edi\n\tleaq 32(%rsp), %rsi\n\tleaq 48(%rsp), %rdx\n\t" third \
 "movq %rsp, %r8\n\tcall gmath_long_double_nine_bytes\n\tfldt (%rsp)\n\t" \
 "addq $24, %rsp\n\t.cfi_adjust_cfa_offset -24\n\tret");LDN_UNREACHABLE }
#define LDN_BINARY(name,op) LDN_REAL(long double name(long double x __attribute__((unused)),long double y __attribute__((unused))),op,"xorl %ecx, %ecx\n\t","xorl %r9d, %r9d\n\t")
LDN_BINARY(gmath_fmodl,0)
LDN_BINARY(gmath_remainderl,1)
LDN_BINARY(gmath_fdiml,3)
LDN_REAL(long double gmath_remquol(long double x __attribute__((unused)),long double y __attribute__((unused)),int *q __attribute__((unused))),2,"xorl %ecx, %ecx\n\t","movq %rdi, %r9\n\t")
LDN_REAL(long double gmath_fmal(long double x __attribute__((unused)),long double y __attribute__((unused)),long double z __attribute__((unused))),4,"leaq 64(%rsp), %rcx\n\t","xorl %r9d, %r9d\n\t")
#else
#define LDN_INT(name,type,current,bits) type name(long double x) {return (type)ldn_integer_bytes(current,(const unsigned char *)&x,bits);}
LDN_INT(gmath_lroundl,long,0,sizeof(long)*CHAR_BIT)
LDN_INT(gmath_llroundl,long long,0,64)
LDN_INT(gmath_lrintl,long,1,sizeof(long)*CHAR_BIT)
LDN_INT(gmath_llrintl,long long,1,64)
#define LDN_BINARY(name,op) long double name(long double x,long double y) {long double out;ldn_bytes(op,(const unsigned char *)&x,(const unsigned char *)&y,0,(unsigned char *)&out,0);return out;}
#if GMATH_HAVE_LONG_DOUBLE_REMAINDER
LDN_BINARY(gmath_fmodl,0)
LDN_BINARY(gmath_remainderl,1)
long double gmath_remquol(long double x,long double y,int *q) {long double out;ldn_bytes(2,(const unsigned char *)&x,(const unsigned char *)&y,0,(unsigned char *)&out,q);return out;}
#endif
LDN_BINARY(gmath_fdiml,3)
long double gmath_fmal(long double x,long double y,long double z) {long double out;ldn_bytes(4,(const unsigned char *)&x,(const unsigned char *)&y,(const unsigned char *)&z,(unsigned char *)&out,0);return out;}
#endif
#endif
