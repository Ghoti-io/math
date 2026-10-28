#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Observable currentint numerical/state faults, native/standard-fenv controls."""
import os
from pathlib import Path
import shlex
import subprocess

def main():
 env=os.environ;work=Path(env['PLANT_WORK']);work.mkdir(parents=True,exist_ok=True)
 def words(n):return shlex.split(env[n])
 def run(args,label,status=0):
  p=subprocess.run(args,capture_output=True,text=True,timeout=180);(work/(label+'.log')).write_text(p.stdout+p.stderr)
  if p.returncode!=status:raise RuntimeError(label+' unexpected status '+str(p.returncode)+' '+p.stderr[-300:])
  return p
 source=Path('src/elementary/current_intround.c').read_text();helper=Path('src/elementary/nearby_mode.h').read_text()
 def build(label,text,expected=(1,1),header=helper,extra=[]):
  file=work/(label+'.c');obj=work/(label+'.o');raw=work/(label+'-raw');unit=work/(label+'-unit')
  file.write_text('#include <errno.h>\n#include <fenv.h>\n'+text);(work/'nearby_mode.h').write_text(header)
  run(words('PLANT_CC')+words('PLANT_CFLAGS')+extra+['-Isrc/elementary','-c',str(file),'-o',str(obj)],label+'-compile')
  run(words('PLANT_CC')+words('PLANT_CFLAGS')+['tools/probe-currentint.c',str(obj),env['PLANT_ARCHIVE']]+words('PLANT_LDFLAGS')+['-lm','-o',str(raw)],label+'-raw-link')
  run(words('PLANT_CXX')+[env['PLANT_TEST_OBJ'],str(obj),env['PLANT_ARCHIVE']]+words('PLANT_UNIT_LDFLAGS')+['-lm','-o',str(unit)],label+'-unit-link')
  for width,filt,want in [(64,'CurrentInteger.PinnedDouble',expected[0]),(32,'CurrentInteger.PinnedFloat',expected[1])]:
   p=run([str(raw),'tests/corpus',str(width)],label+'-C'+str(width),want)
   if want and not any(d in p.stderr for d in ['currentint mismatch','currentint control-state mismatch']):raise RuntimeError('fault failed outside numerical/state layer')
   if want and label in ['control-bit','x87-control-bit'] and 'currentint control-state mismatch' not in p.stderr:raise RuntimeError('control fault escaped intended layer')
   run([str(unit),'--gtest_filter='+filt,'--gtest_brief=1'],label+'-CPP'+str(width),want)
 build('control',source,(0,0));build('fenv-control',source,(0,0),extra=['-DGMATH_NEARBY_FENV_QUERY'])
 faults=[('fixed-nearest','int mode = nearby_mode();','int mode = 0;'),
 ('ties-away','(fraction == halfway && (magnitude & 1))','(fraction == halfway)'),
 ('direction','if (mode == 2)','if (mode == 1)'),
 ('cut','unsigned cut = p - exponent;','unsigned cut = p - exponent + 1;'),
 ('integral-shift','significand << (exponent - p)','significand << (exponent - p + 1)'),
 ('return-sign','return sign ? -(int64_t)magnitude : (int64_t)magnitude;','return (int64_t)magnitude;'),
 ('range-halved','magnitude > maximum + sign','magnitude > (maximum >> 1) + sign'),
 ('invalid-loses-iv','(void)gmath_invalid();','(void)0;'),
 ('invalid-spurious-ix','(void)gmath_invalid();','(void)gmath_invalid(); (void)feraiseexcept(FE_INEXACT);'),
 ('force-only-ix','    ci_inexact();','    (void)0;'),
 ('tiny-collapsed','if (!a) {','if (a < ((uint64_t)(bias - 1) << p)) {'),
 ('minimum','return INT64_MIN;','return INT64_MAX;')]
 marker='uint64_t sign ='
 for name,operation in [('errno','errno=0;'),('zero-errno','if(errno==0)errno=7;'),
  ('incoming-ix','(void)feclearexcept(FE_INEXACT);'),('incoming-invalid','(void)feclearexcept(FE_INVALID);'),
  ('mixed-flags','if((fetestexcept(FE_INVALID|FE_DIVBYZERO)&(FE_INVALID|FE_DIVBYZERO))==(FE_INVALID|FE_DIVBYZERO))(void)feclearexcept(FE_DIVBYZERO);'),
  ('round-mode','(void)fesetround(FE_TONEAREST);')]:faults.append((name,marker,operation+'\n  '+marker))
 for name,old,new in faults:
  if source.count(old)!=1:raise RuntimeError('currentint mutation anchor '+name)
  build(name,source.replace(old,new,1))
 for name,old,new,expected in [
  ('double-alias','return (long)ci_round(gmath_bits(x), 52, 11, 1023, LONG_MAX);','return gmath_lround(x);',(1,0)),
  ('float-alias','return (long)ci_round(ci_float_bits(x), 23, 8, 127, LONG_MAX);','return gmath_lroundf(x);',(0,1)),
  ('wide-double-range','return (long long)ci_round(gmath_bits(x), 52, 11, 1023, LLONG_MAX);','return (long long)ci_round(gmath_bits(x), 52, 11, 1023, INT32_MAX);',(1,0)),
  ('wide-float-range','return (long long)ci_round(ci_float_bits(x), 23, 8, 127, LLONG_MAX);','return (long long)ci_round(ci_float_bits(x), 23, 8, 127, INT32_MAX);',(0,1))]:
  if source.count(old)!=1:raise RuntimeError('format anchor')
  build(name,source.replace(old,new,1),expected)
 macros=run(words('PLANT_CC')+words('PLANT_CFLAGS')+['-dM','-E','-include','src/elementary/nearby_mode.h','-x','c','/dev/null'],'macros').stdout
 if '__SSE__' in macros:
  operation='uint32_t control;__asm__ volatile("stmxcsr %0":"=m"(control)::"memory");control^=UINT32_C(0x8000);__asm__ volatile("ldmxcsr %0"::"m"(control):"memory");'
  build('control-bit',source.replace(marker,operation+'\n  '+marker,1))
  operation='uint16_t cw;__asm__ volatile("fnstcw %0":"=m"(cw)::"memory");cw=(uint16_t)((cw&~0x300u)|((cw&0x300u)==0x300u?0x200u:0x300u));__asm__ volatile("fldcw %0"::"m"(cw):"memory");'
  build('x87-control-bit',source.replace(marker,operation+'\n  '+marker,1))
  print('currentint two actual SSE/x87 control faults detected',flush=True)
 else:print('currentint SSE/x87 control faults SKIPPED: compiler target lacks SSE',flush=True)
 if '#define __SIZEOF_LONG__ 4' in macros:
  for name,old,new,expected in [
   ('long32-equality','magnitude > maximum + sign','magnitude >= maximum + sign',(1,1)),
   ('long32-narrow','magnitude > maximum + sign','(maximum == INT32_MAX ? (uint16_t)magnitude : magnitude) > maximum + sign',(1,1)),
   ('long32-premature-ix','  if (magnitude > maximum + sign) {','  if (fraction) {ci_inexact();}\n  if (magnitude > maximum + sign) {',(1,0))]:
   if source.count(old)!=1:raise RuntimeError('native32 anchor')
   build(name,source.replace(old,new,1),expected)
  print('currentint native-long32 equality/narrowing/premature-IX controls detect',flush=True)
 else:print('currentint native-long32 controls SKIPPED: equivalent/inapplicable signed64-long variants',flush=True)
 print('currentint18 shared faults and4 format/wide-range faults detect with native/fenv controls in C17/C++',flush=True)
if __name__=='__main__':
 try:main()
 except (OSError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('currentint plants: FAIL: '+str(e))
