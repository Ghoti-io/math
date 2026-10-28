#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Observable nearby numerical/state faults, native/standard-fenv controls."""
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
 source=Path('src/elementary/nearby.c').read_text();helper=Path('src/elementary/nearby_mode.h').read_text()
 def build(label,text,expected=(1,1),header=helper,extra=[]):
  file=work/(label+'.c');obj=work/(label+'.o');raw=work/(label+'-raw');unit=work/(label+'-unit')
  file.write_text('#include <errno.h>\n#include <fenv.h>\n'+text);(work/'nearby_mode.h').write_text(header)
  run(words('PLANT_CC')+words('PLANT_CFLAGS')+extra+['-Isrc/elementary','-c',str(file),'-o',str(obj)],label+'-compile')
  run(words('PLANT_CC')+words('PLANT_CFLAGS')+['tools/probe-nearby.c',str(obj),env['PLANT_ARCHIVE']]+words('PLANT_LDFLAGS')+['-lm','-o',str(raw)],label+'-raw-link')
  run(words('PLANT_CXX')+[env['PLANT_TEST_OBJ'],str(obj),env['PLANT_ARCHIVE']]+words('PLANT_UNIT_LDFLAGS')+['-lm','-o',str(unit)],label+'-unit-link')
  for width,filt,want in [(64,'Nearby.PinnedDouble',expected[0]),(32,'Nearby.PinnedFloat',expected[1])]:
   p=run([str(raw),'tests/corpus',str(width)],label+'-C'+str(width),want)
   if want and not any(d in p.stderr for d in ['nearby mismatch','nearby control-state mismatch']):raise RuntimeError('fault failed outside numerical/state layer')
   if want and label=='native-control-bit' and 'nearby control-state mismatch' not in p.stderr:raise RuntimeError('control-bit plant did not fail at raw control layer')
   run([str(unit),'--gtest_filter='+filt,'--gtest_brief=1'],label+'-CPP'+str(width),want)
 build('native-control',source,(0,0));build('fenv-control',source,(0,0),extra=['-DGMATH_NEARBY_FENV_QUERY'])
 faults=[('fixed-nearest','int mode = nearby_mode();','int mode = 0;'),
 ('below-half-ties-away','increment = a > ((uint64_t)(bias - 1) << p);','increment = a >= ((uint64_t)(bias - 1) << p);'),
 ('odd-tie','((base & unit) != 0)','1'),('direction','if (mode == 2)','if (mode == 1)'),
 ('cut','unsigned cut = bias + p - (unsigned)(a >> p);','unsigned cut = bias + p - (unsigned)(a >> p) + 1;'),
 ('small-zero-sign','return sign | (increment ? one : 0);','return increment ? one : 0;'),
 ('large-sign','return sign | (base + (increment ? unit : 0));','return base + (increment ? unit : 0);'),
 ('snan-invalid','(void)gmath_invalid();','(void)0;'),
 ('quiet-invalid','if (!(a & quiet))','(void)gmath_invalid(); if (!(a & quiet))'),
 ('canonical','return inf | quiet;','return raw | quiet;'),
 ('fractional-ix','int mode = nearby_mode();','(void)feraiseexcept(FE_INEXACT);int mode = nearby_mode();')]
 marker='uint64_t sign_bit ='
 for name,operation in [('errno','errno=0;'),('zero-errno','if(errno==0)errno=7;'),
  ('incoming-ix','(void)feclearexcept(FE_INEXACT);'),('incoming-of','(void)feclearexcept(FE_OVERFLOW);'),
  ('mixed-flags','if((fetestexcept(FE_INVALID|FE_DIVBYZERO)&(FE_INVALID|FE_DIVBYZERO))==(FE_INVALID|FE_DIVBYZERO))(void)feclearexcept(FE_DIVBYZERO);'),
  ('round-mode','(void)fesetround(FE_TONEAREST);')]:faults.append((name,marker,operation+"\n  "+marker))
 for name,old,new in faults:
  if source.count(old)!=1:raise RuntimeError('nonunique nearby anchor '+name)
  build(name,source.replace(old,new,1))
 for width,name,old,new in [(64,'double-rint-alias','return gmath_double(nearby_word(gmath_bits(x), 52, 11, 1023));','return gmath_rint(x);'),(32,'float-rint-alias','raw = (uint32_t)nearby_word(raw, 23, 8, 127);','return gmath_rintf(x);')]:
  if source.count(old)!=1:raise RuntimeError('format alias anchor')
  build(name,source.replace(old,new,1),(1,0) if width==64 else (0,1))
 # Actual architecture-query mutation, only when the compiled target uses SSE.
 pre=run(words('PLANT_CC')+words('PLANT_CFLAGS')+['-dM','-E','-include','src/elementary/nearby_mode.h','-x','c','/dev/null'],'macros')
 if '__SSE__' in pre.stdout and '#define GMATH_NEARBY_QUERY_NATIVE 1' in pre.stdout:
  old='(control >> 13) & 3u'
  if helper.count(old)!=1:raise RuntimeError('native query anchor')
  build('native-query',source,header=helper.replace(old,'(control >> 12) & 3u',1))
 else:print('nearby SSE-query plant skipped: actual selected reader is not native SSE',flush=True)
 if '__SSE__' in pre.stdout:
  control_fault='uint32_t control;__asm__ volatile("stmxcsr %0":"=m"(control)::"memory");control^=UINT32_C(0x8000);__asm__ volatile("ldmxcsr %0"::"m"(control):"memory");'
  build('native-control-bit',source.replace(marker,control_fault+"\n  "+marker,1))
 shim='#include <fenv.h>\n#include <errno.h>\nstatic int nearby_errno_query(void){int mode=fegetround();errno=0;return mode;}\n#define fegetround nearby_errno_query\n#undef GMATH_NEARBY_FENV_QUERY\n#define GMATH_NEARBY_FENV_QUERY 1\n'
 build('fenv-errno-shim-control',shim+source,(0,0))
 if helper.count('errno = saved;')!=1:raise RuntimeError('fenv errno restore anchor')
 build('fenv-errno-restore',shim+source,header=helper.replace('errno = saved;','(void)saved;',1))
 print('nearby native/fenv/errno-shim controls,17 shared source/state faults,2 format alias defects and query/control/errno plants detect in C17/C++',flush=True)
if __name__=='__main__':
 try:main()
 except (OSError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('nearby plants: FAIL: '+str(e))
