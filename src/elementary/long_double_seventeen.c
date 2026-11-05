/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Final native real long-double functions. Numerical decisions use integers;
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
static const unsigned LD_JOIN(gmath_long_double_seventeen_format_,LD_NATIVE)
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


#include "long_double_seventeen_constants.h"
#include "long_double_seventeen_interval.h"
enum {LDS17_SIN,LDS17_COS,LDS17_TAN,LDS17_ASIN,LDS17_ACOS,LDS17_ATAN,LDS17_ATAN2,
 LDS17_SINH,LDS17_COSH,LDS17_TANH,LDS17_ASINH,LDS17_ACOSH,LDS17_ATANH,LDS17_ERF,LDS17_ERFC,LDS17_TGAMMA,LDS17_LGAMMA};
static ld_raw lds17_zero(unsigned fmt,int sign) {
  ld_value zero={{0},sign,LD_FINITE,0};return ld_pack(fmt,&zero);
}
static ld_raw lds17_identity(unsigned fmt,int n,int sign,int inexact) {
  ld_value value={{0},sign,LD_FINITE,0};ld_insert(&value,(unsigned)n,0);
  ld_raw out=ld_pack(fmt,&value);if(inexact)lds_flags(fmt,out,0,1,0);return out;
}
static lds17_interval lds17_erf_small(lds17_interval x,lds17_interval ln2) {
  /* Positive expansion exp(-x*x)*sum(2^n*x^(2n+1)/(2n+1)!!).
   * Once n>=512 the following ratios are below1/2 for |x|<16.
   * Twice the next term encloses the complete positive remainder. */
  lds17_interval square=lds17_mul(x,x),twosquare=lds17_shift(square,1),term=x,sum=x;
  unsigned n=0;
  do {
    ++n;term=lds17_small(lds17_mul(term,twosquare),2*n+1);sum=lds17_add(sum,term);
  } while(n<512 || term.e>=sum.e-4400);
  term=lds17_shift(lds17_small(lds17_mul(term,twosquare),2*n+3),1);
  term.m.lo=lde_fint(0);sum=lds17_add(sum,term);
  return lds17_div(lds17_shift(lds17_mul(lds17_exp(lds17_neg(square),ln2),sum),1),lds17_sqrt(lds17_pi()));
}
static lds17_interval lds17_erfc_tail(lds17_interval x,lds17_interval ln2) {
  /* Positive forward continuants: h_n=2U_n/T_n. Even/odd depths
   * enclose the Stieltjes fraction; only these final two ratios divide. */
  lds17_interval tprev=lds17_int(1),t=lds17_shift(x,1);
  lds17_interval uprev=lds17_int(0),u=lds17_int(1),twox=lds17_shift(x,1);
  lds17_interval upper=lds17_int(0),lower=upper;
  for(unsigned n=1;n<=2049;++n) {
    lds17_interval tn=lds17_add(lds17_mul(twox,t),lds17_times_unsigned(tprev,2*n));
    lds17_interval un=lds17_add(lds17_mul(twox,u),lds17_times_unsigned(uprev,2*n));
    tprev=t;t=tn;uprev=u;u=un;
    if(n==2048)upper=lds17_div(lds17_shift(u,1),t);
    if(n==2049)lower=lds17_div(lds17_shift(u,1),t);
  }
  int e=upper.e>lower.e?upper.e:lower.e;
  lde_interval m={lde_fshift(lower.m.lo,lower.e-e,0),lde_fshift(upper.m.hi,upper.e-e,1)};
  lds17_interval ratio=lds17_normal(m,e);
  return lds17_div(lds17_mul(ratio,lds17_exp(lds17_neg(lds17_mul(x,x)),ln2)),lds17_sqrt(lds17_pi()));
}
static lds17_interval lds17_lgamma_positive(lds17_interval x,lds17_interval ln2) {
  lds17_interval one=lds17_int(1),product=one,y=x;
  /* Inspect the actual lower endpoint, not merely the shared exponent:
   * an interval straddling1024 must take one further recurrence step. */
  while(y.m.lo.sign || lde_ftop(&y.m.lo)<0 || lde_ftop(&y.m.lo)+y.e<LDE_PREC+10) {
    product=lds17_mul(product,y);y=lds17_add(y,one);
  }
  lds17_interval inv=lds17_div(one,y),square=lds17_mul(inv,inv),power=inv,sum=lds17_int(0);
  for(unsigned k=0;k<512;++k) {
    lde_fixed c={{0},0};memcpy(c.w,lds17_bernoulli_floor+k*LDE_FW,sizeof c.w);
    lde_interval cm={c,c};lde_funit(&cm.hi);
    lds17_interval coefficient=lds17_normal(cm,lds17_bernoulli_exponent[k]);
    if(lds17_bernoulli_sign[k])coefficient=lds17_neg(coefficient);
    sum=lds17_add(sum,lds17_mul(coefficient,power));power=lds17_mul(power,square);
  }
  /* Stieltjes remainder has the sign of the first omitted term and
   * magnitude bounded by that term. Last retained term is negative;
   * its magnitude bounds the next one at y>=1024 because the ratio
   * <=(1024*1025)/(4*pi*pi*1024^2)<1/32. */
  lds17_interval tail;
  /* Bound the omitted term by |last term|/16. */
  lde_fixed c={{0},0};memcpy(c.w,lds17_bernoulli_floor+511*LDE_FW,sizeof c.w);lde_interval cm={c,c};lde_funit(&cm.hi);
  tail=lds17_small(lds17_mul(lds17_normal(cm,lds17_bernoulli_exponent[511]),lds17_div(power,square)),16);
  tail.m.lo=lde_fint(0);sum=lds17_add(sum,tail);
  lds17_interval main=lds17_sub(lds17_mul(lds17_sub(y,lds17_shift(one,-1)),lds17_log(y,ln2)),y);
  lds17_interval constant=lds17_shift(lds17_log(lds17_shift(lds17_pi(),1),ln2),-1);
  return lds17_sub(lds17_add(main,lds17_add(constant,sum)),lds17_log(product,ln2));
}
static lds17_interval lds17_sinpi(const ld_value *a,int *negative) {
  ld_value fractional=*a;fractional.sign=0;
  for(int i=LD_ZERO_BIT;i<LD_WORDS*32;++i)fractional.w[i/32]&=~(UINT32_C(1)<<(i%32));
  *negative=!ld_bit(a,LD_ZERO_BIT); /* sign of Gamma(-|a|). */
  lds17_interval f=lds17_from(&fractional),one=lds17_int(1);
  if(f.e>=-1)f=lds17_sub(one,f);
  lds17_interval s,c;lds17_sincos(lds17_mul(f,lds17_pi()),&s,&c);return s;
}
static ld_raw lds17_run(unsigned fmt,int op,ld_raw raw,ld_raw second) {
  ld_value a=ld_decode(fmt,raw),b={{0},0,LD_FINITE,0};
  if(op==LDS17_ATAN2)b=ld_decode(fmt,second);
  if(a.invalid || b.invalid)return lde_domain(fmt);
  if(a.kind==LD_NAN || b.kind==LD_NAN) {a.kind=LD_NAN;return ld_pack(fmt,&a);}
  int zero=a.kind==LD_FINITE && ld_top(&a)<0,sign=a.sign;
  ld_value abs=a;abs.sign=0;
  ld_value unity={{0},0,LD_FINITE,0};ld_set(&unity,LD_ZERO_BIT);
  int cmp=a.kind==LD_INF?1:ld_cmpmag(&abs,&unity);
  lds17_interval x=lds17_from(&abs),one=lds17_int(1),result;
  if(op<=LDS17_TAN) {
    if(a.kind==LD_INF)return lde_domain(fmt);
    if(zero)return op==LDS17_COS?lde_unit(fmt,0):ld_pack(fmt,&a);
    if(x.e<(fmt==106?-550:-128)) {
      if(op==LDS17_COS)return lds17_identity(fmt,1,0,1);
      ld_raw out=ld_pack(fmt,&a);lds_flags(fmt,out,0,1,0);return out;
    }
    unsigned quadrant;lds17_interval s,c;lds17_sincos(lds17_reduce(&a,&quadrant),&s,&c);
    switch(quadrant) {case 1:result=s;s=c;c=lds17_neg(result);break;case 2:s=lds17_neg(s);c=lds17_neg(c);break;case 3:result=s;s=lds17_neg(c);c=result;break;default:break;}
    return lds17_round(fmt,op==LDS17_SIN?s:op==LDS17_COS?c:lds17_div(s,c));
  }
  if(op==LDS17_ATAN2) {
    int bz=b.kind==LD_FINITE && ld_top(&b)<0;
    if(zero && !b.sign)return lds17_zero(fmt,sign);
    if(b.kind==LD_INF && !b.sign && a.kind!=LD_INF)return lds17_zero(fmt,sign);
    if(zero)result=lds17_pi();
    else if(bz || (a.kind==LD_INF && b.kind!=LD_INF))result=lds17_shift(lds17_pi(),-1);
    else if(a.kind==LD_INF && b.kind==LD_INF)result=lds17_small(lds17_mul(lds17_int(b.sign?3:1),lds17_pi()),4);
    else if(b.kind==LD_INF)result=lds17_pi();
    else {ld_value bx=b;bx.sign=0;result=lds17_atan(lds17_div(x,lds17_from(&bx)));if(b.sign)result=lds17_sub(lds17_pi(),result);}
    return lds17_round(fmt,sign?lds17_neg(result):result);
  }
  if(op<=LDS17_ATAN) {
    if(op!=LDS17_ATAN && cmp>0)return lde_domain(fmt);
    if(zero && op!=LDS17_ACOS)return ld_pack(fmt,&a);
    if(op==LDS17_ACOS && cmp==0 && !sign)return lds17_zero(fmt,0);
    if(op==LDS17_ATAN && a.kind==LD_INF)result=lds17_shift(lds17_pi(),-1);
    else if(op==LDS17_ATAN)result=lds17_atan(x);
    else if(op==LDS17_ASIN) {
      if(cmp==0)result=lds17_shift(lds17_pi(),-1);
      else result=lds17_atan(lds17_div(x,lds17_sqrt(lds17_mul(lds17_sub(one,x),lds17_add(one,x)))));
    } else {
      if(cmp==0)return lds17_round(fmt,lds17_pi());
      lds17_interval signedx=sign?lds17_neg(x):x;
      return lds17_round(fmt,lds17_shift(lds17_atan(lds17_sqrt(lds17_div(lds17_sub(one,signedx),lds17_add(one,signedx)))),1));
    }
    return lds17_round(fmt,sign?lds17_neg(result):result);
  }
  if(op<=LDS17_ATANH) {
    if(op==LDS17_ACOSH && (sign || cmp<0))return lde_domain(fmt);
    if(op==LDS17_ATANH && cmp>=0) {if(cmp==0)return lde_pole(fmt,sign);return lde_domain(fmt);}
    if(op==LDS17_ACOSH && cmp==0)return lds17_zero(fmt,0);
    if(zero)return op==LDS17_COSH?lde_unit(fmt,0):ld_pack(fmt,&a);
    if(a.kind==LD_INF) {
      if(op==LDS17_TANH)return lde_unit(fmt,sign);
      if(op==LDS17_COSH)a.sign=0;
      return ld_pack(fmt,&a);
    }
    if(op!=LDS17_ACOSH && x.e<(fmt==106?-550:-128)) {
      if(op==LDS17_COSH)return lds17_identity(fmt,1,0,1);
      ld_raw out=ld_pack(fmt,&a);lds_flags(fmt,out,0,1,0);return out;
    }
    lds17_interval ln2=lds17_ln2();
    if(op<=LDS17_TANH) {
      if(x.e>=14)return op==LDS17_TANH?lds17_identity(fmt,1,sign,1):lde_range(fmt,op==LDS17_SINH?sign:0,1);
      if(op==LDS17_TANH && x.e>=9)return lds17_identity(fmt,1,sign,1);
      lds17_interval positive=lds17_exp(x,ln2),negative=lds17_div(one,positive);
      if(op==LDS17_SINH)result=lds17_shift(lds17_sub(positive,negative),-1);
      else if(op==LDS17_COSH)result=lds17_shift(lds17_add(positive,negative),-1);
      else result=lds17_div(lds17_sub(positive,negative),lds17_add(positive,negative));
    } else if(op==LDS17_ASINH)result=lds17_log(lds17_add(x,lds17_sqrt(lds17_add(lds17_mul(x,x),one))),ln2);
    else if(op==LDS17_ACOSH)result=lds17_log(lds17_add(x,lds17_sqrt(lds17_mul(lds17_sub(x,one),lds17_add(x,one)))),ln2);
    else result=lds17_shift(lds17_log(lds17_div(lds17_add(one,x),lds17_sub(one,x)),ln2),-1);
    return lds17_round(fmt,sign && op!=LDS17_COSH?lds17_neg(result):result);
  }
  if(op<=LDS17_ERFC) {
    if(zero)return op==LDS17_ERF?ld_pack(fmt,&a):lde_unit(fmt,0);
    if(a.kind==LD_INF)return op==LDS17_ERF?lde_unit(fmt,sign):lds17_identity(fmt,sign?2:0,0,0);
    if(x.e>=7)return op==LDS17_ERF?lds17_identity(fmt,1,sign,1):sign?lds17_identity(fmt,2,0,1):lde_range(fmt,0,0);
    lds17_interval ln2=lds17_ln2();
    if(x.e<4) {result=lds17_erf_small(x,ln2);if(op==LDS17_ERFC)result=lds17_sub(one,sign?lds17_neg(result):result);else if(sign)result=lds17_neg(result);}
    else {result=lds17_erfc_tail(x,ln2);if(op==LDS17_ERF) {result=lds17_sub(one,result);if(sign)result=lds17_neg(result);}else if(sign)result=lds17_sub(lds17_int(2),result);}
    return lds17_round(fmt,result);
  }
  if(a.kind==LD_INF) {if(op==LDS17_TGAMMA && sign)return lde_domain(fmt);a.sign=0;return ld_pack(fmt,&a);}
  if(zero)return lde_pole(fmt,op==LDS17_TGAMMA?sign:0);
  if(sign && lde_integer(&a))return op==LDS17_LGAMMA?lde_pole(fmt,0):lde_domain(fmt);
  ld_value two={{0},0,LD_FINITE,0};ld_insert(&two,2,0);
  if(!sign && (!cmp || !ld_cmpmag(&abs,&two)))return op==LDS17_LGAMMA?lds17_zero(fmt,0):lde_unit(fmt,0);
  lds17_interval ln2=lds17_ln2();int gamma_negative=0;
  if(sign) {
    lds17_interval sine=lds17_sinpi(&abs,&gamma_negative);
    result=lds17_sub(lds17_sub(lds17_log(lds17_pi(),ln2),lds17_log(sine,ln2)),lds17_lgamma_positive(lds17_add(one,x),ln2));
  } else result=lds17_lgamma_positive(x,ln2);
  if(op==LDS17_LGAMMA)return lds17_round(fmt,result);
  if(result.e>=14)return lde_range(fmt,gamma_negative,!result.m.lo.sign);
  result=lds17_exp(result,ln2);if(gamma_negative)result=lds17_neg(result);
  return lds17_round(fmt,result);
}
#ifndef GMATH_LONG_DOUBLE_SEVENTEEN_RAW_ONLY
static void lds17_bytes(int op,const unsigned char *x,const unsigned char *y,unsigned char *out)
  __asm__("gmath_long_double_seventeen_bytes") __attribute__((noinline,used));
static void lds17_bytes(int op,const unsigned char *x,const unsigned char *y,unsigned char *out) {
  ld_raw b={0,0};if(y)b=ld_read(y);ld_write(out,lds17_run(LD_NATIVE,op,ld_read(x),b));
}
#if LD_NATIVE == 80 && defined(__x86_64__) && defined(__ELF__) && (defined(__GNUC__) || defined(__clang__))
#define LDS17_STRING_(x) #x
#define LDS17_STRING(x) LDS17_STRING_(x)
#if defined(__clang__)
#define LDS17_UNREACHABLE
#else
#define LDS17_UNREACHABLE __builtin_unreachable();
#endif
#define LDS17_REAL(signature,op,second) \
 __attribute__((naked)) signature { __asm__( \
 "subq $24, %rsp\n\t.cfi_adjust_cfa_offset 24\n\t" \
 "movl $" LDS17_STRING(op) ", %edi\n\tleaq 32(%rsp), %rsi\n\t" second \
 "movq %rsp, %rcx\n\tcall gmath_long_double_seventeen_bytes\n\tfldt (%rsp)\n\t" \
 "addq $24, %rsp\n\t.cfi_adjust_cfa_offset -24\n\tret");LDS17_UNREACHABLE }
#define LDS17_UNARY(name,op) LDS17_REAL(long double name(long double x __attribute__((unused))),op,"xorl %edx, %edx\n\t")
#define LDS17_BINARY(name,op) LDS17_REAL(long double name(long double x __attribute__((unused)),long double y __attribute__((unused))),op,"leaq 48(%rsp), %rdx\n\t")
#elif LD_NATIVE == 80 && defined(__i386__) && defined(__ELF__) && (defined(__GNUC__) || defined(__clang__))
#define LDS17_STRING_(x) #x
#define LDS17_STRING(x) LDS17_STRING_(x)
#if defined(__clang__)
#define LDS17_UNREACHABLE
#else
#define LDS17_UNREACHABLE __builtin_unreachable();
#endif
#define LDS17_REAL(signature,op,second) \
 __attribute__((naked)) signature { __asm__( \
 "subl $44,%esp\n\t.cfi_adjust_cfa_offset 44\n\t" \
 "movl $" LDS17_STRING(op) ",(%esp)\n\tleal 48(%esp),%eax\n\tmovl %eax,4(%esp)\n\t" second \
 "leal 16(%esp),%eax\n\tmovl %eax,12(%esp)\n\tcall gmath_long_double_seventeen_bytes\n\tfldt 16(%esp)\n\t" \
 "addl $44,%esp\n\t.cfi_adjust_cfa_offset -44\n\tret");LDS17_UNREACHABLE }
#define LDS17_UNARY(name,op) LDS17_REAL(long double name(long double x __attribute__((unused))),op,"movl $0,8(%esp)\n\t")
#define LDS17_BINARY(name,op) LDS17_REAL(long double name(long double x __attribute__((unused)),long double y __attribute__((unused))),op,"leal 60(%esp),%eax\n\tmovl %eax,8(%esp)\n\t")
#else
#define LDS17_UNARY(name,op) long double name(long double x) {long double out;lds17_bytes(op,(const unsigned char *)&x,0,(unsigned char *)&out);return out;}
#define LDS17_BINARY(name,op) long double name(long double x,long double y) {long double out;lds17_bytes(op,(const unsigned char *)&x,(const unsigned char *)&y,(unsigned char *)&out);return out;}
#endif
LDS17_UNARY(gmath_sinl,0)
LDS17_UNARY(gmath_cosl,1)
LDS17_UNARY(gmath_tanl,2)
LDS17_UNARY(gmath_asinl,3)
LDS17_UNARY(gmath_acosl,4)
LDS17_UNARY(gmath_atanl,5)
LDS17_BINARY(gmath_atan2l,6)
LDS17_UNARY(gmath_sinhl,7)
LDS17_UNARY(gmath_coshl,8)
LDS17_UNARY(gmath_tanhl,9)
LDS17_UNARY(gmath_asinhl,10)
LDS17_UNARY(gmath_acoshl,11)
LDS17_UNARY(gmath_atanhl,12)
LDS17_UNARY(gmath_erfl,13)
LDS17_UNARY(gmath_erfcl,14)
LDS17_UNARY(gmath_tgammal,15)
LDS17_UNARY(gmath_lgammal,16)
#endif
