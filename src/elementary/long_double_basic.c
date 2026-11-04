/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Native long-double foundation. All numerical decisions use integers;
 * native arithmetic registers carry only the final ABI return value. */
#include <float.h>
#include <limits.h>
#include <ghoti.io/math/basic.h>
#include "elem_common.h"
#include "nearby_mode.h"
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
static const unsigned LD_JOIN(gmath_long_double_format_,LD_NATIVE)
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
/* Raw engine: synthetic format tests call this same numerical path. Auxiliary
 * results are object bytes, so modf stores never execute an FP instruction. */
static ld_raw ld_run(unsigned fmt, int op, ld_raw x, ld_raw y,
                     int mode, ld_raw *whole, int *exponent) {
  ld_value a = {{0},0,LD_FINITE,0}, b;
  if (exponent) *exponent = 0;
  if (op == LD_NAN_OP) { a.kind=LD_NAN; return ld_pack(fmt,&a); }
  a=ld_decode(fmt,x);
  if (op == LD_MIN || op == LD_MAX) {
    b=ld_decode(fmt,y);
    if (a.invalid || b.invalid) { (void)gmath_invalid(); a.kind=LD_NAN; }
    else if (a.kind == LD_NAN && b.kind != LD_NAN) a=b;
    else if (a.kind != LD_NAN && b.kind != LD_NAN) {
      int cmp=ld_cmp(&a,&b); if (op == LD_MAX ? cmp < 0 : cmp > 0) a=b;
    }
    return ld_pack(fmt,&a);
  }
  if (a.invalid) (void)gmath_invalid();
  int top=ld_top(&a);
  if (op == LD_ILOGB) {
    int e;
    if (a.kind == LD_NAN) e=GMATH_ILOGBNAN;
    else if (a.kind == LD_INF) e=INT_MAX;
    else if (top < 0) e=GMATH_ILOGB0;
    else e=top+LD_BASE;
    if (a.kind != LD_FINITE || top < 0) (void)gmath_invalid();
    if (exponent) *exponent=e;
    return ld_pack(fmt,&a);
  }
  if (a.kind == LD_NAN) { ld_raw r=ld_pack(fmt,&a); if (whole) *whole=r; return r; }
  if (op == LD_FABS) a.sign=0;
  else if (op == LD_COPY) a.sign=fmt == 80 ? (int)((y.hi>>15)&1) : (int)(y.hi>>63);
  else if (op == LD_LOGB) {
    if (a.kind == LD_INF) a.sign=0;
    else if (top < 0) { (void)gmath_div_by_zero(0); a.kind=LD_INF; a.sign=1; }
    else { int e=top+LD_BASE; memset(&a,0,sizeof a); a.sign=e<0; ld_insert(&a,(uint64_t)(e<0 ? -e : e),0); }
  } else if (op == LD_FREXP) {
    /* DD has no public frexpl; raw callers reject that unavailable opcode. */
    if (fmt != 106 && a.kind == LD_FINITE && top >= 0) {
      int e=top+LD_BASE+1; if (exponent) *exponent=e; ld_shift(&a,-e);
    }
  } else if (op == LD_MODF) {
    b=a;
    if (a.kind == LD_INF) memset(a.w,0,sizeof a.w), a.kind=LD_FINITE;
    else { ld_clear_below(&b,LD_ZERO_BIT); for (int i=LD_ZERO_BIT/32+1;i<LD_WORDS;++i) a.w[i]=0;
      a.w[LD_ZERO_BIT/32] &= (UINT32_C(1) << (LD_ZERO_BIT%32))-1; }
    if (whole) *whole=ld_pack(fmt,&b);
  } else if (op >= LD_FLOOR && op <= LD_NEARBY && a.kind == LD_FINITE) {
    int fraction=ld_any_below(&a,LD_ZERO_BIT), half=ld_bit(&a,LD_ZERO_BIT-1);
    int sticky=ld_any_below(&a,LD_ZERO_BIT-1), odd=ld_bit(&a,LD_ZERO_BIT);
    int increment=op == LD_FLOOR ? a.sign && fraction : op == LD_CEIL ? !a.sign && fraction :
      op == LD_ROUND ? half : op == LD_RINT ? half && (sticky || odd) :
      op == LD_NEARBY ? (mode==1 ? a.sign && fraction : mode==2 ? !a.sign && fraction : mode==3 ? 0 : half && (sticky || odd)) : 0;
    ld_clear_below(&a,LD_ZERO_BIT); if (increment) ld_increment(&a,LD_ZERO_BIT);
  }
  return ld_pack(fmt,&a);
}
/* Native extended80 uses x87 RC even when binary32/64 use MXCSR. */
#if (defined(__GNUC__) || defined(__clang__)) && (defined(__i386__) || defined(__x86_64__))
static inline int nearby_mode_extended80(void) {
  uint16_t control;
  __asm__ volatile("fnstcw %0" : "=m"(control) : : "memory");
  return (int)((control >> 10) & 3u);
}
#endif

static int ld_native_mode(void) {
#if LD_NATIVE == 80 && (defined(__i386__) || defined(__x86_64__))
  return nearby_mode_extended80();
#else
  return nearby_mode();
#endif
}
static int ld_bytes(int op, const unsigned char *x, const unsigned char *y,
                    unsigned char *out, void *aux) __asm__("gmath_long_double_bytes")
                    __attribute__((noinline,used));
static int ld_bytes(int op, const unsigned char *x, const unsigned char *y,
                    unsigned char *out, void *aux) {
  ld_raw a={0,0}, b={0,0}, whole={0,0}; int exponent=0;
  if (x && op != LD_NAN_OP) a=ld_read(x);
  if (y) b=ld_read(y);
  ld_raw result=ld_run(LD_NATIVE,op,a,b,op==LD_NEARBY ? ld_native_mode() : 0,&whole,&exponent);
  ld_write(out,result);
  if (aux) {
    if (op==LD_MODF) ld_write((unsigned char *)aux,whole);
    else memcpy(aux,&exponent,sizeof exponent);
  }
  return exponent;
}
/* SysV AMD64 native80 arguments reside at entry rsp+8 and rsp+24. Reserve
 * 24 bytes (16 output, 8 alignment), call the integer byte engine, and load
 * exactly one canonical result into st(0). No input is loaded into x87. */
#if LD_NATIVE == 80 && defined(__x86_64__) && defined(__ELF__) && (defined(__GNUC__) || defined(__clang__))
#define LD_STRING_(x) #x
#define LD_STRING(x) LD_STRING_(x)
#if defined(__clang__)
#define LD_UNREACHABLE
#else
#define LD_UNREACHABLE __builtin_unreachable();
#endif
/* Public names expand through the namespace before being stringified. */
#define LD_WRAPPER(name,signature,operation,second,auxiliary,finish) \
  __attribute__((naked)) signature { __asm__( \
    "subq $24, %rsp\n\t.cfi_adjust_cfa_offset 24\n\t" auxiliary \
    "movl $" LD_STRING(operation) ", %edi\n\t" \
    "leaq 32(%rsp), %rsi\n\t" second \
    "movq %rsp, %rcx\n\tcall gmath_long_double_bytes\n\t" finish \
    "addq $24, %rsp\n\t.cfi_adjust_cfa_offset -24\n\tret"); LD_UNREACHABLE }
#define LD_UNARY(name,op) LD_WRAPPER(name,long double name(long double x __attribute__((unused))),op,"xorl %edx, %edx\n\t","xorl %r8d, %r8d\n\t","fldt (%rsp)\n\t")
LD_UNARY(gmath_fabsl,0)
LD_UNARY(gmath_floorl,5)
LD_UNARY(gmath_ceill,6)
LD_UNARY(gmath_truncl,7)
LD_UNARY(gmath_roundl,8)
LD_UNARY(gmath_rintl,9)
LD_UNARY(gmath_nearbyintl,10)
LD_UNARY(gmath_logbl,14)
#define LD_BINARY(name,op) LD_WRAPPER(name,long double name(long double x __attribute__((unused)),long double y __attribute__((unused))),op,"leaq 48(%rsp), %rdx\n\t","xorl %r8d, %r8d\n\t","fldt (%rsp)\n\t")
LD_BINARY(gmath_copysignl,1)
LD_BINARY(gmath_fminl,3)
LD_BINARY(gmath_fmaxl,4)
LD_WRAPPER(gmath_nanl,long double gmath_nanl(const char *tag __attribute__((unused))),2,"xorl %edx, %edx\n\t","xorl %r8d, %r8d\n\t","fldt (%rsp)\n\t")
LD_WRAPPER(gmath_modfl,long double gmath_modfl(long double x __attribute__((unused)),long double *integral __attribute__((unused))),11,"xorl %edx, %edx\n\t","movq %rdi, %r8\n\t","fldt (%rsp)\n\t")
LD_WRAPPER(gmath_frexpl,long double gmath_frexpl(long double x __attribute__((unused)),int *e __attribute__((unused))),12,"xorl %edx, %edx\n\t","movq %rdi, %r8\n\t","fldt (%rsp)\n\t")
LD_WRAPPER(gmath_ilogbl,int gmath_ilogbl(long double x __attribute__((unused))),13,"xorl %edx, %edx\n\t","xorl %r8d, %r8d\n\t","")
#else
#define LD_UNARY(name,op) long double name(long double x) { long double out; ld_bytes(op,(const unsigned char *)&x,0,(unsigned char *)&out,0); return out; }
LD_UNARY(gmath_fabsl,LD_FABS)
LD_UNARY(gmath_floorl,LD_FLOOR)
LD_UNARY(gmath_ceill,LD_CEIL)
LD_UNARY(gmath_truncl,LD_TRUNC)
LD_UNARY(gmath_roundl,LD_ROUND)
LD_UNARY(gmath_rintl,LD_RINT)
LD_UNARY(gmath_nearbyintl,LD_NEARBY)
LD_UNARY(gmath_logbl,LD_LOGB)
#define LD_BINARY(name,op) long double name(long double x,long double y) { long double out; ld_bytes(op,(const unsigned char *)&x,(const unsigned char *)&y,(unsigned char *)&out,0); return out; }
LD_BINARY(gmath_copysignl,LD_COPY)
LD_BINARY(gmath_fminl,LD_MIN)
LD_BINARY(gmath_fmaxl,LD_MAX)
long double gmath_nanl(const char *tag) { (void)tag; long double out; ld_bytes(LD_NAN_OP,0,0,(unsigned char *)&out,0); return out; }
long double gmath_modfl(long double x,long double *integral) { long double out; ld_bytes(LD_MODF,(const unsigned char *)&x,0,(unsigned char *)&out,integral); return out; }
#if GMATH_HAVE_FREXPL
long double gmath_frexpl(long double x,int *e) { long double out; ld_bytes(LD_FREXP,(const unsigned char *)&x,0,(unsigned char *)&out,e); return out; }
#endif
int gmath_ilogbl(long double x) { long double out; return ld_bytes(LD_ILOGB,(const unsigned char *)&x,0,(unsigned char *)&out,0); }
#endif
