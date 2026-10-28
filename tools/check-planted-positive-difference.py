#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Real positive-difference numerical/state faults in C17 and C++ callers."""
import os
from pathlib import Path
import shlex
import subprocess

def main():
 e=os.environ;work=Path(e['PLANT_WORK']);work.mkdir(parents=True,exist_ok=True)
 def words(name):return shlex.split(e[name])
 def run(cmd,label,status=0):
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=180);(work/(label+'.log')).write_text(r.stdout+r.stderr)
  if r.returncode!=status:raise RuntimeError(label+' unexpected status '+str(r.returncode)+r.stderr[-400:])
  return r
 source=Path('src/elementary/positive_difference.c').read_text()
 def build(label,text,expected=(1,1),portable=False):
  file=work/(label+'.c');obj=work/(label+'.o');raw=work/(label+'-raw');unit=work/(label+'-unit')
  file.write_text('#include <errno.h>\n#include <fenv.h>\n'+text)
  flags=words('PLANT_CFLAGS')+(['-DGMATH_FDIM_PORTABLE_BITS'] if portable else [])
  run(words('PLANT_CC')+flags+['-Isrc/elementary','-c',str(file),'-o',str(obj)],label+'-compile')
  run(words('PLANT_CC')+flags+['tools/probe-positive-difference.c',str(obj),e['PLANT_ARCHIVE']]+words('PLANT_LDFLAGS')+['-lm','-o',str(raw)],label+'-raw-link')
  run(words('PLANT_CXX')+[e['PLANT_TEST_OBJ'],str(obj),e['PLANT_ARCHIVE']]+words('PLANT_UNIT_LDFLAGS')+['-lm','-o',str(unit)],label+'-unit-link')
  for width,suffix,want in [(64,'Double',expected[0]),(32,'Float',expected[1])]:
   r=run([str(raw),'tests/corpus',str(width)],label+'-C'+str(width),want)
   if want and 'positive difference mismatch' not in r.stderr and 'positive difference control-state mismatch' not in r.stderr:raise RuntimeError('source fault failed outside numerical/state layer '+label)
   if want and label.endswith('control-bit') and 'control-state mismatch' not in r.stderr:raise RuntimeError('control plant escaped snapshot layer')
   run([str(unit),'--gtest_filter=PositiveDifference.Pinned'+suffix,'--gtest_brief=1'],label+'-CPP'+str(width),want)
 build('control',source,(0,0));build('loop-control',source,(0,0),True)
 faults=[
 ('gap-cutoff','gap >= p + 3u','gap >= p + 2u'),
 ('tie-away','lost > half || (lost == half && (q & 1))','lost >= half'),
 ('parity','lost == half && (q & 1)','lost == half && !(q & 1)'),
 ('high-limb','unsigned top = hi ?','hi |= UINT64_C(1);\n  unsigned top = hi ?'),
 ('carry','hi += lo < old;','hi += 0;'),
 ('borrow','hi -= old < mb;','hi -= 0;'),
 ('rounded-overflow','*flags = 6;','*flags = 2;'),
 ('force-only-ix','volatile double ignored = one + tiny;','volatile double ignored = one; (void)tiny;'),
 ('invalid-loss','(void)gmath_invalid();','(void)0;'),
 ('quiet-invalid','? 1u : 0u;','? 1u : 1u;'),
 ('order','if (kx <= ky)','if (kx >= ky)'),
 ('zero-sign','return 0;','return sign;'),
 ('subtract-as-add','if ((x ^ y) & sign)','if (1)'),
 ('exponent','int e = ebv - (int)p + (int)top;','int e = ebv - (int)p + (int)top + 1;'),
 ('tiny-pack','return q >> (unsigned)(1 - bias - e);','return q >> (unsigned)(2 - bias - e);')]
 marker='  *flags = 0;'
 for label,operation in [('errno','errno=0;'),('zero-errno','if(errno==0)errno=17;'),
  ('incoming-ix','(void)feclearexcept(FE_INEXACT);'),('incoming-invalid','(void)feclearexcept(FE_INVALID);'),
  ('mixed-flags','if((fetestexcept(FE_INVALID|FE_DIVBYZERO)&(FE_INVALID|FE_DIVBYZERO))==(FE_INVALID|FE_DIVBYZERO))(void)feclearexcept(FE_DIVBYZERO);'),
  ('mode','(void)fesetround(FE_TONEAREST);')]:faults.append((label,marker,'  '+operation+'\n'+marker))
 for portable in [False,True]:
  for label,old,new in faults:
   count=2 if label=='zero-sign' else 1
   if source.count(old)!=count:raise RuntimeError('source mutation anchor differs '+label+': '+str(source.count(old)))
   # Binary32 alignment is at most49 bits, so high-word carry/borrow
   # deletion is equivalent there. Require the other format to remain passing.
   expected=(1,0) if label in ['carry','borrow'] else (1,1)
   build(('loop-' if portable else 'native-')+label,source.replace(old,new),expected,portable)
  for label,old,new,expected in [
   ('double-alias','uint64_t result = pd_core(gmath_bits(x), gmath_bits(y), 52, 11, 1023, &flags);','uint64_t result = pd_core(gmath_bits(y), gmath_bits(x), 52, 11, 1023, &flags);',(1,0)),
   ('float-alias','pd_core(bx, by, 23, 8, 127, &flags)','pd_core(by, bx, 23, 8, 127, &flags)',(0,1))]:
   if source.count(old)!=1:raise RuntimeError('format source anchor differs')
   build(('loop-' if portable else 'native-')+label,source.replace(old,new,1),expected,portable)
 # Actual fallback defect must detect only in the fallback configuration.
 old='while (x >> 1)';new='while (x >> 2)'
 if source.count(old)!=1:raise RuntimeError('loop source anchor differs')
 macros=run(words('PLANT_CC')+words('PLANT_CFLAGS')+['-dM','-E','src/elementary/positive_difference.c'],'macros').stdout
 processed=run(words('PLANT_CC')+words('PLANT_CFLAGS')+['-E','src/elementary/positive_difference.c'],'preprocessed').stdout
 top=processed.split('static unsigned pd_top(',1)[1].split('static void pd_unpack(',1)[0]
 intrinsic='__builtin_clzll' in top
 build('loop-only',source.replace(old,new,1),portable=True)
 if intrinsic:build('inactive-loop-only',source.replace(old,new,1),(0,0))
 else:print('positive difference inactive-loop control SKIPPED: actual compiler uses fallback',flush=True)
 if '__SSE__' in macros:
  operation='uint32_t control;__asm__ volatile("stmxcsr %0":"=m"(control)::"memory");control^=UINT32_C(0x8000);__asm__ volatile("ldmxcsr %0"::"m"(control):"memory");'
  build('native-control-bit',source.replace(marker,'  '+operation+'\n'+marker,1))
 else:print('positive difference SSE control plant SKIPPED: actual compiler target lacks SSE',flush=True)
 print('positive difference19shared/default+loop,2Double-only high-word/default+loop and2format/default+loop faults detect in C17/C++; equivalent Float high-word variants pass; real loop-only and supported control-state faults calibrated')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:raise SystemExit('positive difference plants: FAIL: '+str(error))
