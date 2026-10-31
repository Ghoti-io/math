#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Real unary arctangent numerical/state defects in C17 and C++ callers."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

def main():
 e=os.environ;work=Path(e['PLANT_WORK']);work.mkdir(parents=True,exist_ok=True);records=[]
 def words(name):return shlex.split(e[name])
 def run(cmd,label,status=0):
  start=time.time();r=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
  (work/(label+'.log')).write_text(r.stdout+r.stderr);records.append(dict(label=label,command=cmd,returncode=r.returncode,elapsed_seconds=time.time()-start));(work/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
  if r.returncode!=status:raise RuntimeError(label+' actual status '+str(r.returncode)+' expected '+str(status)+' '+r.stderr[-600:])
  return r
 source=Path('src/elementary/atan.c').read_text()
 def build(label,text,status=1):
  file=work/(label+'.c');obj=work/(label+'.o');raw=work/(label+'-raw');unit=work/(label+'-unit')
  file.write_text('#include <errno.h>\n#include <fenv.h>\n'+text)
  run(words('PLANT_CC')+words('PLANT_CFLAGS')+['-Isrc/elementary','-c',str(file),'-o',str(obj)],label+'-compile')
  run(words('PLANT_CC')+words('PLANT_CFLAGS')+['tools/probe-atan.c',str(obj),e['PLANT_ARCHIVE']]+words('PLANT_LDFLAGS')+['-lm','-o',str(raw)],label+'-C-link')
  run(words('PLANT_CXX')+[e['PLANT_TEST_OBJ'],str(obj),e['PLANT_ARCHIVE']]+words('PLANT_UNIT_LDFLAGS')+['-lm','-o',str(unit)],label+'-CPP-link')
  result=run([str(raw),'tests/corpus'],label+'-C',status)
  if status and 'atan corpus invalid/accuracy/state failure' not in result.stderr:raise RuntimeError('atan source fault failed outside numerical/state layer '+label)
  run([str(unit),'--gtest_brief=1'],label+'-CPP',status)
  print('atan source/state '+label+' calibrated',flush=True)
 build('control',source,0)
 faults=[
 ('signaling-invalid-loss','(void)gmath_invalid();','(void)0;'),
 ('quiet-invalid-gain','if (!(word & UINT64_C(0x0008000000000000)))','if (1)'),
 ('nan-payload','return gmath_double(UINT64_C(0x7ff8000000000000));','return gmath_double(word | UINT64_C(0x0008000000000000));'),
 ('zero-inexact','if (!magnitude) {','if (!magnitude) {\n    atan_inexact();'),
 ('tiny-cutoff','UINT64_C(0x3e10000000000000)','UINT64_C(0x3e50000000000000)'),
 ('underflow-loss','(void)gmath_underflow(0);','atan_inexact();'),
 ('normal-underflow-gain','magnitude < UINT64_C(0x0010000000000000)','magnitude <= UINT64_C(0x0010000000000000)'),
 ('force-only-inexact','volatile double ignored = one + tiny;','volatile double ignored = one; (void)tiny;'),
 ('large-early','UINT64_C(0x4350000000000000)','UINT64_C(0x4330000000000000)'),
 ('large-late','UINT64_C(0x4350000000000000)','UINT64_C(0x7ff0000000000000)'),
 ('large-constant','UINT64_C(0x3ff921fb54442d18)','UINT64_C(0x3ff921fb54442d19)'),
 ('large-sign','(word & GMATH_SIGN_BIT)','UINT64_C(0)'),
 ('kernel-abscissa','gmath_atan2(x, 1.0)','gmath_atan2(x, -1.0)'),
 ('infinity-inexact','  atan_inexact();\n  return result;','  if(magnitude < GMATH_INF_BITS) {atan_inexact();}\n  return result;')]
 marker='  uint64_t word = gmath_bits(x), magnitude = word & GMATH_ABS_MASK;'
 for label,operation in [('errno-zero','errno=0;'),('errno-clean','if(errno==0)errno=17;'),('incoming-inexact','(void)feclearexcept(FE_INEXACT);'),('incoming-invalid','(void)feclearexcept(FE_INVALID);'),('mixed-incoming','if((fetestexcept(FE_INVALID|FE_DIVBYZERO)&(FE_INVALID|FE_DIVBYZERO))==(FE_INVALID|FE_DIVBYZERO))(void)feclearexcept(FE_DIVBYZERO);'),('mode','(void)fesetround(FE_TONEAREST);')]:faults.append((label,marker,'  '+operation+'\n'+marker))
 for label,old,new in faults:
  if source.count(old)!=1:raise RuntimeError('atan mutation anchor differs '+label)
  build(label,source.replace(old,new,1))
 # Signed-zero loss is deliberately confined to the first return-by-bits path.
 old='    return gmath_double(word);'
 if source.count(old)!=2:raise RuntimeError('atan raw-return anchors differ')
 build('zero-sign',source.replace(old,'    return gmath_double(0);',1))
 macros=run(words('PLANT_CC')+words('PLANT_CFLAGS')+['-dM','-E','src/elementary/atan.c'],'macros').stdout
 if '#define __SSE__ ' in macros:
  operation='uint32_t control;__asm__ volatile("stmxcsr %0":"=m"(control)::"memory");control^=UINT32_C(0x8000);__asm__ volatile("ldmxcsr %0"::"m"(control):"memory");'
  build('native-control',source.replace(marker,'  '+operation+'\n'+marker,1))
 else:print('atan SSE control plant SKIPPED: actual compiler target lacks SSE',flush=True)
 print('atan 21 source/state plants and supported native control defect detect in C17/C++, with passing control',flush=True)
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:raise SystemExit('atan plants: FAIL: '+str(error))
