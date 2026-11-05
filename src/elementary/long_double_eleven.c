/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Native long-double foundation. All numerical decisions use integers;
 * native arithmetic registers carry only the final ABI return value. */
#include <float.h>
#include <limits.h>
#include <ghoti.io/math/basic.h>
#include <ghoti.io/math/elementary.h>
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
static const unsigned LD_JOIN(gmath_long_double_eleven_format_,LD_NATIVE)
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
#include "long_double_eleven_bits.h"


#include "long_double_eleven_interval.h"
#include "long_double_eleven_exact.h"

static ld_raw lde_trans(unsigned fmt,int op,ld_value a,ld_value b) {
  int az=a.kind==LD_FINITE && ld_top(&a)<0,bz=b.kind==LD_FINITE && ld_top(&b)<0,sign=0;
  ld_value one={{0},0,LD_FINITE,0};ld_set(&one,LD_ZERO_BIT);
  if(op==LDE_POW) {
    if(b.kind==LD_FINITE && bz)return lde_unit(fmt,0);
    if(lde_one(&a))return lde_unit(fmt,0);
    if(a.kind==LD_NAN || b.kind==LD_NAN) {a.kind=LD_NAN;return ld_pack(fmt,&a);}
    ld_value absolute=a;absolute.sign=0;
    int magnitude=a.kind==LD_INF?1:ld_cmpmag(&absolute,&one);
    if(b.kind==LD_INF) {
      if(!magnitude)return lde_unit(fmt,0);
      a.kind=((magnitude>0)^b.sign)?LD_INF:LD_FINITE;
      a.sign=0;memset(a.w,0,sizeof a.w);return ld_pack(fmt,&a);
    }
    sign=a.sign && lde_odd(&b);
    if(a.kind==LD_INF || az) {
      if(az && b.sign)return lde_pole(fmt,sign);
      a.kind=(a.kind==LD_INF)^b.sign?LD_INF:LD_FINITE;
      a.sign=sign;memset(a.w,0,sizeof a.w);return ld_pack(fmt,&a);
    }
    if(a.sign && !lde_integer(&b))return lde_domain(fmt);
    if(!magnitude)return lde_unit(fmt,sign);
    a.sign=0;
    ld_raw exact;if(lde_exact_pow(fmt,&a,&b,sign,&exact))return exact;
  } else if(op<=LDE_EXPM1) {
    if(a.kind==LD_NAN)return ld_pack(fmt,&a);
    if(a.kind==LD_INF) {
      if(!a.sign)return ld_pack(fmt,&a);
      if(op==LDE_EXPM1)return lde_unit(fmt,1);
      memset(a.w,0,sizeof a.w);a.kind=LD_FINITE;a.sign=0;return ld_pack(fmt,&a);
    }
    if(az)return op==LDE_EXPM1?ld_pack(fmt,&a):lde_unit(fmt,0);
    if(op==LDE_EXP2 && lde_integer(&a)) {
      int n=0;
      if(ld_top(&a)>LD_ZERO_BIT+15)return lde_range(fmt,0,!a.sign);
      for(int j=15;j>=0;--j)n=(n<<1)|ld_bit(&a,LD_ZERO_BIT+j);
      if(a.sign)n=-n;
      int minimum=fmt==64 || fmt==106?-1074:fmt==80?-16445:-16494;
      int maximum=fmt==64 || fmt==106?1023:16383;
      if(n<minimum)return lde_range(fmt,0,0);
      if(n>maximum)return lde_range(fmt,0,1);
      ld_value exact={{0},0,LD_FINITE,0};ld_insert(&exact,1,n);return ld_pack(fmt,&exact);
    }
    /* For the single formats, |x|<2^-128 makes the first omitted
     * quadratic term less than1/8 of either adjacent gap. For DD,
     * |x|<2^-550 makes it smaller than its absolute minimum gap2^-1074. */
    int tiny=fmt==106?-550:-128;
    if(op==LDE_EXPM1 && ld_top(&a)+LD_BASE<tiny) {
      ld_raw out=ld_pack(fmt,&a);lds_flags(fmt,out,0,1,0);return out;
    }
    if(op!=LDE_EXPM1 && ld_top(&a)+LD_BASE< -1100) {
      ld_raw out=lde_unit(fmt,0);lds_flags(fmt,out,0,1,0);return out;
    }
  } else {
    if(a.kind==LD_NAN)return ld_pack(fmt,&a);
    if(op==LDE_LOG1P) {
      if(a.kind==LD_INF)return a.sign?lde_domain(fmt):ld_pack(fmt,&a);
      if(az)return ld_pack(fmt,&a);
      int tiny=fmt==106?-550:-128;
      if(ld_top(&a)+LD_BASE<tiny) {ld_raw out=ld_pack(fmt,&a);lds_flags(fmt,out,0,1,0);return out;}
      ld_add(&a,&one);
    }
    if(a.kind==LD_INF)return a.sign?lde_domain(fmt):ld_pack(fmt,&a);
    if(ld_top(&a)<0)return lde_pole(fmt,1);
    if(a.sign)return lde_domain(fmt);
    if(lde_one(&a)) {ld_value zero={{0},0,LD_FINITE,0};return ld_pack(fmt,&zero);}
    if(op==LDE_LOG2 && lde_low(&a)==ld_top(&a)) {
      int n=ld_top(&a)+LD_BASE;ld_value exact={{0},n<0,LD_FINITE,0};ld_insert(&exact,(unsigned)(n<0?-n:n),0);return ld_pack(fmt,&exact);
    }
    int n;
    if(op==LDE_LOG10 && lde_ten_power(fmt,&a,&n)) {
      ld_value exact={{0},0,LD_FINITE,0};ld_insert(&exact,(unsigned)n,0);return ld_pack(fmt,&exact);
    }
  }
  lde_interval ln2=lde_ln2(),argument;
  if(op==LDE_POW || op>=LDE_LOG) {
    argument=lde_log(&a,ln2);
    if(op==LDE_LOG2)argument=lde_idiv(argument,ln2);
    if(op==LDE_LOG10) {
      ld_value ten={{0},0,LD_FINITE,0};ld_insert(&ten,10,0);
      argument=lde_idiv(argument,lde_log(&ten,ln2));
    }
    if(op!=LDE_POW) {
      ldn_wide lo=lde_fwide(&argument.lo,0,0),hi=lde_fwide(&argument.hi,0,1);
      return lde_enclosed(fmt,&lo,&hi,1);
    }
    int bt=ld_top(&b)+LD_BASE;
    lde_interval normalized=lde_iconvert(&b,-bt);
    argument=lde_imul(argument,normalized);
    int top=lde_ftop(&argument.lo)-LDE_PREC+bt;
    if(top>15)return lde_range(fmt,sign,!argument.lo.sign);
    if(top< -1100) {ld_raw out=lde_unit(fmt,sign);lds_flags(fmt,out,0,1,0);return out;}
    argument.lo=lde_fshift(argument.lo,bt,0);argument.hi=lde_fshift(argument.hi,bt,1);
  } else {
    if(ld_top(&a)+LD_BASE>14) {
      if(op==LDE_EXPM1 && a.sign) {ld_raw out=lde_unit(fmt,1);lds_flags(fmt,out,0,1,0);return out;}
      return lde_range(fmt,0,!a.sign);
    }
    argument=lde_iconvert(&a,0);
    if(op==LDE_EXP2)argument=lde_imul(argument,ln2);
  }
  lde_fixed limit=lde_fint(12000),negative_limit=lde_fint(-12000);
  if(lde_fcmp(&argument.lo,&limit)>0)return lde_range(fmt,sign,1);
  if(lde_fcmp(&argument.hi,&negative_limit)<0) {
    if(op==LDE_EXPM1) {ld_raw out=lde_unit(fmt,1);lds_flags(fmt,out,0,1,0);return out;}
    return lde_range(fmt,sign,0);
  }
  ldn_wide lo=lde_exp_endpoint(argument.lo,ln2,0),hi=lde_exp_endpoint(argument.hi,ln2,1);
  if(op==LDE_EXPM1) {
    ldn_wide minus=ldn_widen(&one);minus.sign=1;ldn_wadd(&lo,&minus);ldn_wadd(&hi,&minus);
  }
  if(sign) {ldn_wide tmp=lo;lo=hi;hi=tmp;lo.sign^=1;hi.sign^=1;}
  return lde_enclosed(fmt,&lo,&hi,1);
}

static ld_raw lde_run(unsigned fmt,int op,ld_raw x,ld_raw y) {
  ld_value a=ld_decode(fmt,x),b={{0},0,LD_FINITE,0};
  if(op==LDE_HYPOT || op==LDE_POW)b=ld_decode(fmt,y);
  if(a.invalid || b.invalid) {lds_raise_invalid();a.kind=LD_NAN;return ld_pack(fmt,&a);}
  if(op==LDE_HYPOT && (a.kind==LD_INF || b.kind==LD_INF)) {a.kind=LD_INF;a.sign=0;return ld_pack(fmt,&a);}
  if(op>=LDE_EXP)return lde_trans(fmt,op,a,b);
  if(a.kind==LD_NAN || b.kind==LD_NAN) {a.kind=LD_NAN;return ld_pack(fmt,&a);}
  if(op==LDE_SQRT && a.sign && (a.kind==LD_INF || ld_top(&a)>=0)) {lds_raise_invalid();a.kind=LD_NAN;return ld_pack(fmt,&a);}
  if(op==LDE_HYPOT) {
    a.sign=b.sign=0;
    if(ld_top(&a)<0 && ld_top(&b)<0)return ld_pack(fmt,&a);
    ldn_wide sum=ldn_product(&a,&a),other=ldn_product(&b,&b);ldn_wadd(&sum,&other);
    return lde_root(fmt,&sum,2,0);
  }
  if(a.kind==LD_INF || ld_top(&a)<0)return ld_pack(fmt,&a);
  ldn_wide radicand=ldn_widen(&a);radicand.sign=0;
  return lde_root(fmt,&radicand,op==LDE_CBRT?3:2,a.sign);
}
#ifndef GMATH_LONG_DOUBLE_ELEVEN_RAW_ONLY
static void lde_bytes(int op,const unsigned char *x,const unsigned char *y,unsigned char *out)
  __asm__("gmath_long_double_eleven_bytes") __attribute__((noinline,used));
static void lde_bytes(int op,const unsigned char *x,const unsigned char *y,unsigned char *out) {
  ld_raw b={0,0};if(y)b=ld_read(y);ld_write(out,lde_run(LD_NATIVE,op,ld_read(x),b));
}
#if LD_NATIVE == 80 && defined(__x86_64__) && defined(__ELF__) && (defined(__GNUC__) || defined(__clang__))
#define LDE_STRING_(x) #x
#define LDE_STRING(x) LDE_STRING_(x)
#if defined(__clang__)
#define LDE_UNREACHABLE
#else
#define LDE_UNREACHABLE __builtin_unreachable();
#endif
#define LDE_REAL(signature,op,second) \
 __attribute__((naked)) signature { __asm__( \
 "subq $24, %rsp\n\t.cfi_adjust_cfa_offset 24\n\t" \
 "movl $" LDE_STRING(op) ", %edi\n\tleaq 32(%rsp), %rsi\n\t" second \
 "movq %rsp, %rcx\n\tcall gmath_long_double_eleven_bytes\n\tfldt (%rsp)\n\t" \
 "addq $24, %rsp\n\t.cfi_adjust_cfa_offset -24\n\tret");LDE_UNREACHABLE }
#define LDE_UNARY(name,op) LDE_REAL(long double name(long double x __attribute__((unused))),op,"xorl %edx, %edx\n\t")
#define LDE_BINARY(name,op) LDE_REAL(long double name(long double x __attribute__((unused)),long double y __attribute__((unused))),op,"leaq 48(%rsp), %rdx\n\t")
#elif LD_NATIVE == 80 && defined(__i386__) && defined(__ELF__) && (defined(__GNUC__) || defined(__clang__))
#define LDE_STRING_(x) #x
#define LDE_STRING(x) LDE_STRING_(x)
#if defined(__clang__)
#define LDE_UNREACHABLE
#else
#define LDE_UNREACHABLE __builtin_unreachable();
#endif
#define LDE_REAL(signature,op,second) \
 __attribute__((naked)) signature { __asm__( \
 "subl $44,%esp\n\t.cfi_adjust_cfa_offset 44\n\t" \
 "movl $" LDE_STRING(op) ",(%esp)\n\tleal 48(%esp),%eax\n\tmovl %eax,4(%esp)\n\t" second \
 "leal 16(%esp),%eax\n\tmovl %eax,12(%esp)\n\tcall gmath_long_double_eleven_bytes\n\tfldt 16(%esp)\n\t" \
 "addl $44,%esp\n\t.cfi_adjust_cfa_offset -44\n\tret");LDE_UNREACHABLE }
#define LDE_UNARY(name,op) LDE_REAL(long double name(long double x __attribute__((unused))),op,"movl $0,8(%esp)\n\t")
#define LDE_BINARY(name,op) LDE_REAL(long double name(long double x __attribute__((unused)),long double y __attribute__((unused))),op,"leal 60(%esp),%eax\n\tmovl %eax,8(%esp)\n\t")
#else
#define LDE_UNARY(name,op) long double name(long double x) {long double out;lde_bytes(op,(const unsigned char *)&x,0,(unsigned char *)&out);return out;}
#define LDE_BINARY(name,op) long double name(long double x,long double y) {long double out;lde_bytes(op,(const unsigned char *)&x,(const unsigned char *)&y,(unsigned char *)&out);return out;}
#endif
LDE_UNARY(gmath_sqrtl,0)
LDE_UNARY(gmath_cbrtl,1)
LDE_BINARY(gmath_hypotl,2)
LDE_UNARY(gmath_expl,3)
LDE_UNARY(gmath_exp2l,4)
LDE_UNARY(gmath_expm1l,5)
LDE_UNARY(gmath_logl,6)
LDE_UNARY(gmath_log2l,7)
LDE_UNARY(gmath_log10l,8)
LDE_UNARY(gmath_log1pl,9)
LDE_BINARY(gmath_powl,10)
#endif
