/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 * Raw fixtures can exercise all adapters; fmt=0 selects the actual native ABI.
 * Host libm is linked solely for test environment setup/observation. */
#define GMATH_LONG_DOUBLE_BASIC_RAW_ONLY
#include "../src/elementary/long_double_basic.c"
#include <errno.h>
#include <fenv.h>
#include <inttypes.h>
#include <stdio.h>
#include <ctype.h>
#include <stdlib.h>
#include "../tests/fp_controls.h"
static unsigned flags(void) {
  int f=fetestexcept(FE_ALL_EXCEPT);
  return ((f&FE_INVALID)?1u:0u)|((f&FE_DIVBYZERO)?2u:0u)|((f&FE_INEXACT)?4u:0u)|((f&FE_UNDERFLOW)?8u:0u)|((f&FE_OVERFLOW)?16u:0u);
}
static ld_raw native(int op,ld_raw a,ld_raw b,ld_raw *whole,int *e) {
  long double x,y,z,w; ld_write((unsigned char *)&x,a); ld_write((unsigned char *)&y,b);
  switch(op) {
#define U(n,k) case k: z=gmath_##n(x); break
    U(fabsl,LD_FABS); U(floorl,LD_FLOOR); U(ceill,LD_CEIL);
    U(truncl,LD_TRUNC); U(roundl,LD_ROUND); U(rintl,LD_RINT);
    U(nearbyintl,LD_NEARBY); U(logbl,LD_LOGB);
    case LD_COPY:z=gmath_copysignl(x,y);break;
    case LD_NAN_OP:z=gmath_nanl((const char *)(uintptr_t)1);break;
    case LD_MIN:z=gmath_fminl(x,y);break;
    case LD_MAX:z=gmath_fmaxl(x,y);break;
    case LD_MODF:z=gmath_modfl(x,&w);*whole=ld_read((const unsigned char *)&w);break;
#if GMATH_HAVE_FREXPL
    case LD_FREXP:z=gmath_frexpl(x,e);break;
#endif
    case 15:z=gmath_frexpl(x,NULL);*e=0;break;
    case LD_ILOGB:*e=gmath_ilogbl(x);return a;
    default:return a;
  }
  return ld_read((const unsigned char *)&z);
}
/* Reject hidden bytes and unterminated records before string conversion. */
static int probe_record(char *line,size_t capacity) {
  size_t count=0;int ch;
  while((ch=fgetc(stdin))!=EOF) {
    if(ch==0 || count+1>=capacity)return -1;
    line[count++]=(char)ch;
    if(ch=='\n')break;
  }
  if(ferror(stdin) || (count && line[count-1]!='\n'))return -1;
  line[count]=0;return count?1:0;
}
static int profile_population(void) {
  fenv_t saved;if(fegetenv(&saved))return 2;
  unsigned tested=0;int status=0;
#if defined(__SSE__) && (defined(__x86_64__) || defined(__i386__))
  _Alignas(16) unsigned char fx[512];uint32_t mask=0,original=0;
  __asm__ volatile("fxsave %0":"=m"(fx));memcpy(&mask,fx+28,4);if(!mask)mask=0xffbf;
  __asm__ volatile("stmxcsr %0":"=m"(original));
  const unsigned profiles[4]={0,0x40,0x8000,0x8040};
  for(unsigned profile=0;profile<4 && !status;++profile) {
    if(profiles[profile]&~mask) {printf("DD frexp profiles: unsupported MXCSR %x skipped\n",profiles[profile]);continue;}
    uint32_t control=(original&~0x8040u)|profiles[profile];__asm__ volatile("ldmxcsr %0"::"m"(control));
#else
  for(unsigned profile=0;profile<1 && !status;++profile) {
    (void)profile;
#endif
    ++tested;
    /* Literal fractions/flags: subnormal low tails must survive DAZ inputs,
     * and normalization must never leak low-component underflow with FTZ. */
    const ld_raw input[4]={{UINT64_C(0x3ff0000000000000),1},
      {UINT64_C(0xbff0000000000000),UINT64_C(0x8000000000000001)},
      {UINT64_C(0x4000000000000000),UINT64_C(0x8000000000000001)},{1,0}};
    const ld_raw output[4]={{UINT64_C(0x3fe0000000000000),0},
      {UINT64_C(0xbfe0000000000000),0},{UINT64_C(0x3fe0000000000000),0},
      {UINT64_C(0x3fe0000000000000),0}};
    const int exponents[4]={1,1,2,-1073};
    const unsigned incoming[9]={0,1,2,4,8,16,3,20,31};
    for(unsigned mode=0;mode<4 && !status;++mode)
      for(unsigned seed=0;seed<9 && !status;++seed)
        for(unsigned cell=0;cell<4 && !status;++cell)
          for(unsigned null_aux=0;null_aux<2 && !status;++null_aux) {
            if(feclearexcept(FE_ALL_EXCEPT) || fesetround((int[]){FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}[mode])) {status=2;break;}
            unsigned inc=incoming[seed];
            if(inc)feraiseexcept(((inc&1)?FE_INVALID:0)|((inc&2)?FE_DIVBYZERO:0)|((inc&4)?FE_INEXACT:0)|((inc&8)?FE_UNDERFLOW:0)|((inc&16)?FE_OVERFLOW:0));
            int before=fegetround(),e=0;uint64_t controls=gmath_test_controls();errno=173;
            ld_raw r;
            if(LD_NATIVE==106) {
              ld_raw whole={0,0};r=native(null_aux?15:LD_FREXP,input[cell],(ld_raw){0,0},&whole,&e);
            } else r=ld_run(106,LD_FREXP,input[cell],(ld_raw){0,0},0,NULL,null_aux?NULL:&e);
            if(r.hi!=output[cell].hi || r.lo!=output[cell].lo || e!=(null_aux?0:exponents[cell]) ||
               flags()!=(inc|(cell<3?4u:0u)) || errno!=173 || fegetround()!=before || gmath_test_controls()!=controls) {
              fprintf(stderr,"DD frexp profile mismatch: profile%u mode%u seed%u cell%u null%u\n",profile,mode,seed,cell,null_aux);status=1;
            }
          }
  }
  if(fesetenv(&saved))return 2;
  if(!status)printf("DD frexp profiles: %u supported control profiles passed\n",tested);
  return status;
}
int main(int argc,char **argv) {
  if(argc==2 && !strcmp(argv[1],"--state"))return profile_population();
  if(argc!=1)return 2;

  printf("native %u size %zu\n",LD_NATIVE,sizeof(long double)); fflush(stdout);
  unsigned rows=0;
  char line[512];
  int record=0;
  while ((record=probe_record(line,sizeof line))>0) {
    uintmax_t fields[9]; char *cursor=line,*end;
    int malformed=0;
    for (unsigned i=0;i<9 && !malformed;++i) {
      while (isspace((unsigned char)*cursor)) ++cursor;
      int base=i>=2 && i<=5 ? 16 : 10;
      if (!(base==16 ? isxdigit((unsigned char)*cursor) : isdigit((unsigned char)*cursor))) { malformed=1;break; }
      errno=0;fields[i]=strtoumax(cursor,&end,base);
      if (errno==ERANGE || end==cursor || (*end && !isspace((unsigned char)*end))) { malformed=1;break; }
      cursor=end;
    }
    while (isspace((unsigned char)*cursor)) ++cursor;
    if (malformed || *cursor) {
      fputs("long-double probe: malformed or truncated row\n",stderr);return 2;
    }
    if ((fields[0]!=0 && fields[0]!=64 && fields[0]!=80 && fields[0]!=128 && fields[0]!=106) ||
        fields[1]>15 || fields[6]>=4 || (fields[7]!=0 && fields[7]!=2 && fields[7]!=3) || fields[8]>31 ||
        fields[2]>UINT64_MAX || fields[3]>UINT64_MAX || fields[4]>UINT64_MAX || fields[5]>UINT64_MAX) {
      fputs("long-double probe: invalid row fields\n",stderr);return 2;
    }
    unsigned fmt=(unsigned)fields[0],op=(unsigned)fields[1],mode=(unsigned)fields[6],pc=(unsigned)fields[7],incoming=(unsigned)fields[8];
    (void)pc; /* Precision-control requests apply only to x87. */
    ld_raw a={(uint64_t)fields[2],(uint64_t)fields[3]},b={(uint64_t)fields[4],(uint64_t)fields[5]};
    ++rows;
    unsigned before_mx=0,after_mx=0; unsigned short before_cw=0,after_cw=0;
    feclearexcept(FE_ALL_EXCEPT);
    fesetround((int[]){FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO}[mode]);
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile("fnstcw %0":"=m"(before_cw));
    before_cw=(unsigned short)((before_cw&~0x300u)|((pc&3u)<<8));
    __asm__ volatile("fldcw %0"::"m"(before_cw));
    __asm__ volatile("stmxcsr %0":"=m"(before_mx));
    /* Deliberately disagree with native80 RC; preserve standard flags. */
    #if LD_NATIVE == 80
    before_mx=(before_mx&~0x6000u)|(((mode+1)&3u)<<13);
#endif
    __asm__ volatile("ldmxcsr %0"::"m"(before_mx));
#endif
    if (incoming) feraiseexcept(((incoming&1)?FE_INVALID:0)|((incoming&2)?FE_DIVBYZERO:0)|((incoming&4)?FE_INEXACT:0)|((incoming&8)?FE_UNDERFLOW:0)|((incoming&16)?FE_OVERFLOW:0));
    int round_before=fegetround(); uint64_t controls_before=gmath_test_controls();
    errno=173; ld_raw whole={0,0}; int exponent=0;
    ld_raw r=fmt ? ld_run(fmt,op==15?LD_FREXP:(int)op,a,b,(int)mode,&whole,op==15?NULL:&exponent) : native((int)op,a,b,&whole,&exponent);
    int err=errno; unsigned f=flags();
    int round_after=fegetround(); uint64_t controls_after=gmath_test_controls();
#if defined(__x86_64__) || defined(__i386__)
    __asm__ volatile("fnstcw %0":"=m"(after_cw));
    __asm__ volatile("stmxcsr %0":"=m"(after_mx));
#endif
    printf("%016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %016" PRIx64 " %d %u %d %u\n",r.hi,r.lo,whole.hi,whole.lo,exponent,f,err,(unsigned)(round_before==round_after && controls_before==controls_after && before_cw==after_cw && (before_mx&~63u)==(after_mx&~63u))); fflush(stdout);
  }
  if(record<0) {fputs("DD basic probe: malformed byte record\n",stderr);return 2;}
  if (ferror(stdin) || !rows) { fputs("long-double probe: input error or no rows\n",stderr);return 2; }
  return 0;
}
