#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Compiled per-API and shared arithmetic/state defect calibration."""
import sys
if sys.flags.optimize:
 raise SystemExit('remaining-fifteen: optimized Python execution is unsupported')
import argparse,os,shlex,subprocess,tempfile,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--directory',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
def run(cmd,log):
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=300);log.write_text(r.stdout+r.stderr);return r
cc=shlex.split(os.environ['REMAINING_CC']);flags=shlex.split(os.environ['REMAINING_CFLAGS']);link=shlex.split(os.environ['REMAINING_LINK']);archive=os.environ['REMAINING_ARCHIVE']
plants=[]
for width in [64,32]:
 for kind,name in enumerate(['erf','erfc','tgamma','lgamma']):
  fn=name+('f' if width==32 else '')
  old='EG_%s(%s, %d)'%('DOUBLE' if width==64 else 'FLOAT',name,kind)
  new=('double gmath_%s(double x){return gmath_double(eg_core(gmath_bits(x),52,1023,%d)^4u);}'%(fn,kind)) if width==64 else ('float gmath_%s(float x){uint32_t b;memcpy(&b,&x,4);b=(uint32_t)eg_core(b,23,127,%d)^4u;memcpy(&x,&b,4);return x;}'%(fn,kind))
  plants.append((fn+'-public-result','error_gamma.c',old,new,fn))
# Replace one named wrapper body, leaving every other public entry point intact.
exact=Path('src/elementary/remaining_exact.c').read_text()
for fn,body in [
 ('fma','return gmath_double(rx_fma(gmath_bits(x),gmath_bits(y),gmath_bits(z),52,1023)^4u);'),
 ('fmaf','uint32_t a,b,c;memcpy(&a,&x,4);memcpy(&b,&y,4);memcpy(&c,&z,4);a=(uint32_t)rx_fma(a,b,c,23,127)^4u;memcpy(&x,&a,4);return x;'),
 ('nan','(void)tag;return gmath_double(GMATH_QNAN_BITS^4u);'),
 ('nanf','(void)tag;uint32_t b=UINT32_C(0x7fc00004);float x;memcpy(&x,&b,4);return x;'),
 ('nexttoward','unsigned char bytes[sizeof y];const volatile unsigned char *source=(const volatile unsigned char *)&y;for(unsigned i=0;i<sizeof y;++i)bytes[i]=source[i];return gmath_double(rx_toward(gmath_bits(x),bytes,52,1023)^4u);'),
 ('nexttowardf','unsigned char bytes[sizeof y];const volatile unsigned char *source=(const volatile unsigned char *)&y;for(unsigned i=0;i<sizeof y;++i)bytes[i]=source[i];uint32_t a;memcpy(&a,&x,4);a=(uint32_t)rx_toward(a,bytes,23,127)^4u;memcpy(&x,&a,4);return x;')]:
 original_name='gmath_'+fn;renamed='remaining_original_'+fn
 rewritten=re.sub(r'\b'+original_name+r'\b',renamed,exact)
 signatures={'fma':('double','double x,double y,double z','x,y,z'), 'fmaf':('float','float x,float y,float z','x,y,z'), 'nan':('double','const char *tag','tag'), 'nanf':('float','const char *tag','tag'), 'nexttoward':('double','double x,long double y','x,y'), 'nexttowardf':('float','float x,long double y','x,y')}
 result_type,args,call=signatures[fn]
 if result_type=='double':wrapper='double '+original_name+'('+args+'){return gmath_double(gmath_bits('+renamed+'('+call+'))^4u);}'
 else:wrapper='float '+original_name+'('+args+'){float out='+renamed+'('+call+');uint32_t bits;memcpy(&bits,&out,4);bits^=4u;memcpy(&out,&bits,4);return out;}'
 plants.append((fn+'-public-result','remaining_exact.c',exact,rewritten+'\n'+wrapper+'\n',fn))
plants.append(('powf-public-result','float_pow.c','done:\n','done:\n  r ^= 4u;\n','powf'))
plants += [
 ('fma-sign','remaining_exact.c','int result_sign = ps;','int result_sign = ps ^ 1;',None),
 ('fma-nearest-tie','remaining_exact.c','rx_bit(a, cut - 1) && (sticky || (q & 1))','rx_bit(a, cut - 1) && (sticky || (q & 1) || 1)',None),
 ('fmaf-downward-zero','remaining_exact.c','return mode == 1 ? sign : 0;','return mode == 1 && p != 23 ? sign : 0;','fmaf'),
 ('fma-after-rounding-tiny','remaining_exact.c','if (result < (UINT64_C(1) << p))','if (0 && result < (UINT64_C(1) << p))',None),
 ('adjacent-direction','remaining_exact.c','int outward =','cmp = -cmp;\n  int outward =',None),
 ('constructor-invalid','remaining_exact.c','(void)tag;','(void)tag; (void)gmath_invalid();','nan'),
 ('gamma-domain','error_gamma.c','if (neg && integer) {','if (0 && neg && integer) {',None),
 ('erfc-tail','error_gamma.c','rm_cmp(x, rm_uint(28))','rm_cmp(x, rm_uint(7))',None),
 ('pow-signaling-priority','float_pow.c','if (sn) {','if (0 && sn) {','powf'),
 ('pow-exact-binary','float_pow.c','if (integral) {','if (0 && integral) {','powf'),
 ('pow-exact-dyadic','float_pow.c','if (fp_exact_dyadic(ax, by, sign, &r))','if (0 && fp_exact_dyadic(ax, by, sign, &r))','powf') ]
with tempfile.TemporaryDirectory(prefix='compiled-',dir=a.work) as temp:
 d=Path(temp)
 for name,filename,old,new,fn in plants:
  source=Path('src/elementary')/filename;text=source.read_text();assert old in text,(name,old)
  planted=d/filename;planted.write_text(text.replace(old,new,1));obj=d/'runtime.o';exe=d/'probe'
  r=run(cc+flags+['-I','src/elementary','-c',str(planted),'-o',str(obj)],a.work/(name+'-compile.log'))
  if r.returncode:raise RuntimeError('source plant compilation failed: '+name)
  r=run(cc+flags+['tools/probe-remaining.c',str(obj),archive]+link+['-o',str(exe)],a.work/(name+'-link.log'))
  if r.returncode:raise RuntimeError('source plant link failed: '+name)
  r=run([str(exe.resolve()),str(a.directory.resolve())],a.work/(name+'-run.log'))
  if r.returncode!=1 or 'remaining-fifteen: rejected at row' not in r.stderr or not re.search(r'stage=(?:accuracy|flags|state|errno|mode|controls)\b',r.stderr) or fn and not re.search(r'fn='+fn+r'\b',r.stderr):raise RuntimeError('source plant escaped named public numerical/state assertion: '+name)
# Synthetic decoder defects must reach the actual representation assertions,
# including non-host layouts that the native public ABI cannot execute here.
decoder_plants=[('binary64-infinity','d.inf = a == GMATH_INF_BITS;','d.inf = 0;'),('binary80-pseudo','(exp ? (int)exp : 1) - 16383 - 63','(exp ? (int)exp : 2) - 16383 - 63'),('binary128-quiet','0x0000800000000000','0x0000400000000000'),('double-double-low','d.b = rm_raw(lo, 52, 1023);','d.b = rm_zero();')]
with tempfile.TemporaryDirectory(prefix='decoder-',dir=a.work) as temp:
 d=Path(temp);original=Path('src/elementary/remaining_exact.c').read_text()
 for name,old,new in decoder_plants:
  if old not in original:raise RuntimeError('missing decoder plant site: '+name)
  planted=d/'remaining_exact.c';planted.write_text(original.replace(old,new,1));source=d/'decode.c';source.write_text(Path('tools/probe-remaining-decode.c').read_text().replace('../src/elementary/remaining_exact.c',str(planted.resolve())))
  exe=d/'decode';r=run(cc+flags+['-I','src/elementary',str(source)]+link+['-o',str(exe)],a.work/(name+'-compile-link.log'))
  if r.returncode:raise RuntimeError('decoder plant build failed: '+name)
  r=run([str(exe.resolve())],a.work/(name+'-run.log'))
  if r.returncode!=1 or 'remaining-decode: rejected' not in r.stderr:raise RuntimeError('decoder plant missed its intended assertion: '+name)
print('remaining-fifteen: %d compiled defects (all15 named APIs, mode/tiny/domain/tail/flag) rejected at intended public assertions'%(len(plants)+len(decoder_plants)))
