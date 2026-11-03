/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Representative host-output comparison; differences are not accuracy proofs.
 * Build with -fno-builtin -frounding-math; production archive retains its flags.
 */
#define _GNU_SOURCE
#include <ghoti.io/math/basic.h>
#include <ghoti.io/math/elementary.h>
#include <math.h>
#include <fenv.h>
#include <errno.h>
#include <float.h>
#include <stdint.h>
#include <inttypes.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#if defined(__GLIBC__)
#include <gnu/libc-version.h>
#endif
static uint64_t dbits(double x){uint64_t u;memcpy(&u,&x,8);return u;}
static uint64_t fbits(float x){uint32_t u;memcpy(&u,&x,4);return u;}
static double rawd(uint64_t u){double x;memcpy(&x,&u,8);return x;}
static float rawf(uint32_t u){float x;memcpy(&x,&u,4);return x;}
typedef struct{uint64_t word,aux;int flags,error,mode_after,seed,sign_after;} result;
static result invoke(int id,int ours,double x,double y,double z,float xf,float yf,float zf,int k,long double direction,int mode,int seed){
 result r={0};if(fesetround(mode)){fputs("unsupported rounding mode\n",stderr);exit(2);}
 feclearexcept(FE_ALL_EXCEPT);if(seed)feraiseexcept(FE_DIVBYZERO);
 r.seed=fetestexcept(FE_ALL_EXCEPT);errno=123;signgam=12345;
 switch(id){
case 0:{double (* volatile f)(double)=ours?gmath_sqrt:sqrt;r.word=dbits(f(x));break;}
case 1:{float (* volatile f)(float)=ours?gmath_sqrtf:sqrtf;r.word=fbits(f(xf));break;}
case 2:{double (* volatile f)(double)=ours?gmath_floor:floor;r.word=dbits(f(x));break;}
case 3:{float (* volatile f)(float)=ours?gmath_floorf:floorf;r.word=fbits(f(xf));break;}
case 4:{double (* volatile f)(double)=ours?gmath_ceil:ceil;r.word=dbits(f(x));break;}
case 5:{float (* volatile f)(float)=ours?gmath_ceilf:ceilf;r.word=fbits(f(xf));break;}
case 6:{double (* volatile f)(double)=ours?gmath_trunc:trunc;r.word=dbits(f(x));break;}
case 7:{float (* volatile f)(float)=ours?gmath_truncf:truncf;r.word=fbits(f(xf));break;}
case 8:{double (* volatile f)(double)=ours?gmath_round:round;r.word=dbits(f(x));break;}
case 9:{float (* volatile f)(float)=ours?gmath_roundf:roundf;r.word=fbits(f(xf));break;}
case 10:{double (* volatile f)(double)=ours?gmath_rint:rint;r.word=dbits(f(x));break;}
case 11:{float (* volatile f)(float)=ours?gmath_rintf:rintf;r.word=fbits(f(xf));break;}
case 12:{double (* volatile f)(double)=ours?gmath_fabs:fabs;r.word=dbits(f(x));break;}
case 13:{float (* volatile f)(float)=ours?gmath_fabsf:fabsf;r.word=fbits(f(xf));break;}
case 14:{long (* volatile f)(double)=ours?gmath_lround:lround;r.word=(uint64_t)(int64_t)f(x);break;}
case 15:{long (* volatile f)(float)=ours?gmath_lroundf:lroundf;r.word=(uint64_t)(int64_t)f(xf);break;}
case 16:{long long (* volatile f)(double)=ours?gmath_llround:llround;r.word=(uint64_t)(int64_t)f(x);break;}
case 17:{long long (* volatile f)(float)=ours?gmath_llroundf:llroundf;r.word=(uint64_t)(int64_t)f(xf);break;}
case 18:{double (* volatile f)(double)=ours?gmath_nearbyint:nearbyint;r.word=dbits(f(x));break;}
case 19:{float (* volatile f)(float)=ours?gmath_nearbyintf:nearbyintf;r.word=fbits(f(xf));break;}
case 20:{long (* volatile f)(double)=ours?gmath_lrint:lrint;r.word=(uint64_t)(int64_t)f(x);break;}
case 21:{long (* volatile f)(float)=ours?gmath_lrintf:lrintf;r.word=(uint64_t)(int64_t)f(xf);break;}
case 22:{long long (* volatile f)(double)=ours?gmath_llrint:llrint;r.word=(uint64_t)(int64_t)f(x);break;}
case 23:{long long (* volatile f)(float)=ours?gmath_llrintf:llrintf;r.word=(uint64_t)(int64_t)f(xf);break;}
case 24:{double (* volatile f)(double,double)=ours?gmath_copysign:copysign;r.word=dbits(f(x,y));break;}
case 25:{float (* volatile f)(float,float)=ours?gmath_copysignf:copysignf;r.word=fbits(f(xf,yf));break;}
case 26:{double (* volatile f)(double,int)=ours?gmath_scalbn:scalbn;r.word=dbits(f(x,k));break;}
case 27:{float (* volatile f)(float,int)=ours?gmath_scalbnf:scalbnf;r.word=fbits(f(xf,k));break;}
case 28:{double (* volatile f)(double,int)=ours?gmath_ldexp:ldexp;r.word=dbits(f(x,k));break;}
case 29:{float (* volatile f)(float,int)=ours?gmath_ldexpf:ldexpf;r.word=fbits(f(xf,k));break;}
case 30:{double (* volatile f)(double,long)=ours?gmath_scalbln:scalbln;r.word=dbits(f(x,k));break;}
case 31:{float (* volatile f)(float,long)=ours?gmath_scalblnf:scalblnf;r.word=fbits(f(xf,k));break;}
case 32:{int a=12345;double (* volatile f)(double,int *)=ours?gmath_frexp:frexp;r.word=dbits(f(x,&a));r.aux=(uint64_t)(int64_t)a;break;}
case 33:{int a=12345;float (* volatile f)(float,int *)=ours?gmath_frexpf:frexpf;r.word=fbits(f(xf,&a));r.aux=(uint64_t)(int64_t)a;break;}
case 34:{double (* volatile f)(double)=ours?gmath_logb:logb;r.word=dbits(f(x));break;}
case 35:{float (* volatile f)(float)=ours?gmath_logbf:logbf;r.word=fbits(f(xf));break;}
case 36:{int (* volatile f)(double)=ours?gmath_ilogb:ilogb;r.word=(uint64_t)(int64_t)f(x);break;}
case 37:{int (* volatile f)(float)=ours?gmath_ilogbf:ilogbf;r.word=(uint64_t)(int64_t)f(xf);break;}
case 38:{double (* volatile f)(double,double)=ours?gmath_nextafter:nextafter;r.word=dbits(f(x,y));break;}
case 39:{float (* volatile f)(float,float)=ours?gmath_nextafterf:nextafterf;r.word=fbits(f(xf,yf));break;}
case 40:{double v=0;double (* volatile f)(double,double *)=ours?gmath_modf:modf;r.word=dbits(f(x,&v));r.aux=dbits(v);break;}
case 41:{float v=0;float (* volatile f)(float,float *)=ours?gmath_modff:modff;r.word=fbits(f(xf,&v));r.aux=fbits(v);break;}
case 42:{double (* volatile f)(double,double)=ours?gmath_remainder:remainder;r.word=dbits(f(x,y));break;}
case 43:{float (* volatile f)(float,float)=ours?gmath_remainderf:remainderf;r.word=fbits(f(xf,yf));break;}
case 44:{int a=12345;double (* volatile f)(double,double,int *)=ours?gmath_remquo:remquo;r.word=dbits(f(x,y,&a));r.aux=(uint64_t)(int64_t)a;break;}
case 45:{int a=12345;float (* volatile f)(float,float,int *)=ours?gmath_remquof:remquof;r.word=fbits(f(xf,yf,&a));r.aux=(uint64_t)(int64_t)a;break;}
case 46:{double (* volatile f)(double,double)=ours?gmath_fmod:fmod;r.word=dbits(f(x,y));break;}
case 47:{float (* volatile f)(float,float)=ours?gmath_fmodf:fmodf;r.word=fbits(f(xf,yf));break;}
case 48:{double (* volatile f)(double,double)=ours?gmath_fdim:fdim;r.word=dbits(f(x,y));break;}
case 49:{float (* volatile f)(float,float)=ours?gmath_fdimf:fdimf;r.word=fbits(f(xf,yf));break;}
case 50:{double (* volatile f)(double,double)=ours?gmath_fmin:fmin;r.word=dbits(f(x,y));break;}
case 51:{float (* volatile f)(float,float)=ours?gmath_fminf:fminf;r.word=fbits(f(xf,yf));break;}
case 52:{double (* volatile f)(double,double)=ours?gmath_fmax:fmax;r.word=dbits(f(x,y));break;}
case 53:{float (* volatile f)(float,float)=ours?gmath_fmaxf:fmaxf;r.word=fbits(f(xf,yf));break;}
case 54:{double (* volatile f)(const char *)=ours?gmath_nan:nan;r.word=dbits(f("123"));break;}
case 55:{float (* volatile f)(const char *)=ours?gmath_nanf:nanf;r.word=fbits(f("123"));break;}
case 56:{double (* volatile f)(double,double,double)=ours?gmath_fma:fma;r.word=dbits(f(x,y,z));break;}
case 57:{float (* volatile f)(float,float,float)=ours?gmath_fmaf:fmaf;r.word=fbits(f(xf,yf,zf));break;}
case 58:{double (* volatile f)(double,long double)=ours?gmath_nexttoward:nexttoward;r.word=dbits(f(x,direction));break;}
case 59:{float (* volatile f)(float,long double)=ours?gmath_nexttowardf:nexttowardf;r.word=fbits(f(xf,direction));break;}
case 60:{double (* volatile f)(double)=ours?gmath_sin:sin;r.word=dbits(f(x));break;}
case 61:{float (* volatile f)(float)=ours?gmath_sinf:sinf;r.word=fbits(f(xf));break;}
case 62:{double (* volatile f)(double)=ours?gmath_cos:cos;r.word=dbits(f(x));break;}
case 63:{float (* volatile f)(float)=ours?gmath_cosf:cosf;r.word=fbits(f(xf));break;}
case 64:{double (* volatile f)(double)=ours?gmath_tan:tan;r.word=dbits(f(x));break;}
case 65:{float (* volatile f)(float)=ours?gmath_tanf:tanf;r.word=fbits(f(xf));break;}
case 66:{double (* volatile f)(double)=ours?gmath_exp:exp;r.word=dbits(f(x));break;}
case 67:{float (* volatile f)(float)=ours?gmath_expf:expf;r.word=fbits(f(xf));break;}
case 68:{double (* volatile f)(double)=ours?gmath_exp2:exp2;r.word=dbits(f(x));break;}
case 69:{float (* volatile f)(float)=ours?gmath_exp2f:exp2f;r.word=fbits(f(xf));break;}
case 70:{double (* volatile f)(double)=ours?gmath_cbrt:cbrt;r.word=dbits(f(x));break;}
case 71:{float (* volatile f)(float)=ours?gmath_cbrtf:cbrtf;r.word=fbits(f(xf));break;}
case 72:{double (* volatile f)(double)=ours?gmath_log:log;r.word=dbits(f(x));break;}
case 73:{float (* volatile f)(float)=ours?gmath_logf:logf;r.word=fbits(f(xf));break;}
case 74:{double (* volatile f)(double)=ours?gmath_log2:log2;r.word=dbits(f(x));break;}
case 75:{float (* volatile f)(float)=ours?gmath_log2f:log2f;r.word=fbits(f(xf));break;}
case 76:{double (* volatile f)(double)=ours?gmath_log10:log10;r.word=dbits(f(x));break;}
case 77:{float (* volatile f)(float)=ours?gmath_log10f:log10f;r.word=fbits(f(xf));break;}
case 78:{double (* volatile f)(double,double)=ours?gmath_pow:pow;r.word=dbits(f(x,y));break;}
case 79:{float (* volatile f)(float,float)=ours?gmath_powf:powf;r.word=fbits(f(xf,yf));break;}
case 80:{double (* volatile f)(double)=ours?gmath_log1p:log1p;r.word=dbits(f(x));break;}
case 81:{float (* volatile f)(float)=ours?gmath_log1pf:log1pf;r.word=fbits(f(xf));break;}
case 82:{double (* volatile f)(double)=ours?gmath_expm1:expm1;r.word=dbits(f(x));break;}
case 83:{float (* volatile f)(float)=ours?gmath_expm1f:expm1f;r.word=fbits(f(xf));break;}
case 84:{double (* volatile f)(double)=ours?gmath_asinh:asinh;r.word=dbits(f(x));break;}
case 85:{float (* volatile f)(float)=ours?gmath_asinhf:asinhf;r.word=fbits(f(xf));break;}
case 86:{double (* volatile f)(double)=ours?gmath_acosh:acosh;r.word=dbits(f(x));break;}
case 87:{float (* volatile f)(float)=ours?gmath_acoshf:acoshf;r.word=fbits(f(xf));break;}
case 88:{double (* volatile f)(double)=ours?gmath_atanh:atanh;r.word=dbits(f(x));break;}
case 89:{float (* volatile f)(float)=ours?gmath_atanhf:atanhf;r.word=fbits(f(xf));break;}
case 90:{double (* volatile f)(double)=ours?gmath_sinh:sinh;r.word=dbits(f(x));break;}
case 91:{float (* volatile f)(float)=ours?gmath_sinhf:sinhf;r.word=fbits(f(xf));break;}
case 92:{double (* volatile f)(double)=ours?gmath_cosh:cosh;r.word=dbits(f(x));break;}
case 93:{float (* volatile f)(float)=ours?gmath_coshf:coshf;r.word=fbits(f(xf));break;}
case 94:{double (* volatile f)(double)=ours?gmath_tanh:tanh;r.word=dbits(f(x));break;}
case 95:{float (* volatile f)(float)=ours?gmath_tanhf:tanhf;r.word=fbits(f(xf));break;}
case 96:{double (* volatile f)(double)=ours?gmath_asin:asin;r.word=dbits(f(x));break;}
case 97:{float (* volatile f)(float)=ours?gmath_asinf:asinf;r.word=fbits(f(xf));break;}
case 98:{double (* volatile f)(double)=ours?gmath_acos:acos;r.word=dbits(f(x));break;}
case 99:{float (* volatile f)(float)=ours?gmath_acosf:acosf;r.word=fbits(f(xf));break;}
case 100:{double (* volatile f)(double)=ours?gmath_atan:atan;r.word=dbits(f(x));break;}
case 101:{float (* volatile f)(float)=ours?gmath_atanf:atanf;r.word=fbits(f(xf));break;}
case 102:{double (* volatile f)(double,double)=ours?gmath_atan2:atan2;r.word=dbits(f(x,y));break;}
case 103:{float (* volatile f)(float,float)=ours?gmath_atan2f:atan2f;r.word=fbits(f(xf,yf));break;}
case 104:{double (* volatile f)(double,double)=ours?gmath_hypot:hypot;r.word=dbits(f(x,y));break;}
case 105:{float (* volatile f)(float,float)=ours?gmath_hypotf:hypotf;r.word=fbits(f(xf,yf));break;}
case 106:{double (* volatile f)(double)=ours?gmath_erf:erf;r.word=dbits(f(x));break;}
case 107:{float (* volatile f)(float)=ours?gmath_erff:erff;r.word=fbits(f(xf));break;}
case 108:{double (* volatile f)(double)=ours?gmath_erfc:erfc;r.word=dbits(f(x));break;}
case 109:{float (* volatile f)(float)=ours?gmath_erfcf:erfcf;r.word=fbits(f(xf));break;}
case 110:{double (* volatile f)(double)=ours?gmath_tgamma:tgamma;r.word=dbits(f(x));break;}
case 111:{float (* volatile f)(float)=ours?gmath_tgammaf:tgammaf;r.word=fbits(f(xf));break;}
case 112:{double (* volatile f)(double)=ours?gmath_lgamma:lgamma;r.word=dbits(f(x));break;}
case 113:{float (* volatile f)(float)=ours?gmath_lgammaf:lgammaf;r.word=fbits(f(xf));break;}
 }
 r.error=errno;r.flags=fetestexcept(FE_ALL_EXCEPT);r.mode_after=fegetround();r.sign_after=signgam;return r;
}
int main(void){
 const char *names[]={"sqrt","floor","ceil","trunc","round","rint","fabs","lround","llround","nearbyint","lrint","llrint","copysign","scalbn","ldexp","scalbln","frexp","logb","ilogb","nextafter","modf","remainder","remquo","fmod","fdim","fmin","fmax","nan","fma","nexttoward","sin","cos","tan","exp","exp2","cbrt","log","log2","log10","pow","log1p","expm1","asinh","acosh","atanh","sinh","cosh","tanh","asin","acos","atan","atan2","hypot","erf","erfc","tgamma","lgamma"};
 int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
 uint64_t xs[]={0,UINT64_C(0x8000000000000000),UINT64_C(0x3fe0000000000000),UINT64_C(0xbff0000000000000),UINT64_C(0x4000000000000000),1,UINT64_C(0x7fefffffffffffff),UINT64_C(0x7ff0000000000000),UINT64_C(0xfff0000000000000),UINT64_C(0x7ff8000000000123),UINT64_C(0x7ff0000000000123),UINT64_C(0x3ff8000000000000)};
 uint32_t fs[]={0,UINT32_C(0x80000000),UINT32_C(0x3f000000),UINT32_C(0xbf800000),UINT32_C(0x40000000),1,UINT32_C(0x7f7fffff),UINT32_C(0x7f800000),UINT32_C(0xff800000),UINT32_C(0x7fc00123),UINT32_C(0x7f800123),UINT32_C(0x3fc00000)};
 const char *labels[]={"zero","negative-zero","half","negative-one","two","minsub","maxfinite","infinity","negative-infinity","qnan-payload","snan-payload","one-and-half"};
#if defined(__GLIBC__)
 fprintf(stderr,"glibc=%s\n",gnu_get_libc_version());
#endif
 fprintf(stderr,"long=%zu long-double-mantissa=%d math_errhandling=%d IV=%d DZ=%d OF=%d UF=%d IX=%d\n",sizeof(long)*8,LDBL_MANT_DIG,math_errhandling,FE_INVALID,FE_DIVBYZERO,FE_OVERFLOW,FE_UNDERFLOW,FE_INEXACT);
 puts("name,width,case,mode,seed,actual_seed,ours,host,ours_aux,host_aux,ours_flags,host_flags,ours_errno,host_errno,ours_mode,host_mode,ours_signgam,host_signgam");
 for(unsigned n=0;n<57;n++)for(unsigned w=0;w<2;w++)for(unsigned c=0;c<12;c++)for(unsigned m=0;m<4;m++)for(unsigned seed=0;seed<2;seed++){
  double x=rawd(xs[c]),y=2.0,z=-1.0;float xf=rawf(fs[c]),yf=2.0f,zf=-1.0f;
  long double d=1.0L+0x1p-63L;int k=c==6?2048:-1;
  if(!strcmp(names[n],"copysign")){y=-1;yf=-1;}
  if(!strcmp(names[n],"pow") && c==3){y=0.5;yf=0.5f;}
  result a=invoke((int)(2*n+w),1,x,y,z,xf,yf,zf,k,d,modes[m],(int)seed);
  result b=invoke((int)(2*n+w),0,x,y,z,xf,yf,zf,k,d,modes[m],(int)seed);
  printf("%s,%u,%s,%u,%u,%d,%016" PRIx64 ",%016" PRIx64 ",%016" PRIx64 ",%016" PRIx64 ",%d,%d,%d,%d,%d,%d,%d,%d\n",names[n],w?32:64,labels[c],m,seed,a.seed,a.word,b.word,a.aux,b.aux,a.flags,b.flags,a.error,b.error,a.mode_after,b.mode_after,a.sign_after,b.sign_after);
 }
 fesetround(FE_TONEAREST);return 0;
}
