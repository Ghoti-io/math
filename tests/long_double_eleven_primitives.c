/* SPDX-License-Identifier: LGPL-3.0-only */
#define GMATH_LONG_DOUBLE_ELEVEN_RAW_ONLY
#include "../src/elementary/long_double_eleven.c"
#include <stdio.h>
#include <stdlib.h>
static lde_fixed read_fixed(const char *hex,int sign) {
 lde_fixed a={{0},sign};size_t n=strlen(hex);if(n>8*LDE_FW)abort();
 for(size_t i=0;i<n;++i) {char c=hex[n-i-1];unsigned x=c>='0'&&c<='9'?(unsigned)(c-'0'):c>='a'&&c<='f'?(unsigned)(c-'a'+10):99;if(x>15)abort();a.w[i/8]|=x<<(4*(i%8));}
 return a;
}
int main(void) {
 int op,up,shift,as,bs;char ah[1105],bh[1105];
 while(scanf("%d %d %d %d %d %1104s %1104s",&op,&up,&shift,&as,&bs,ah,bh)==7) {
  lde_fixed a=read_fixed(ah,as),b=read_fixed(bh,bs),out;
  if(op==0)out=lde_fadd(a,b);else if(op==1)out=lde_fmul(a,b,up);else if(op==2)out=lde_fdiv(a,b,up);else if(op==3)out=lde_fshift(a,shift,up);else abort();
  printf("%d ",out.sign);for(int i=LDE_FW-1;i>=0;--i)printf("%08x",out.w[i]);putchar('\n');
 }
 return 0;
}
