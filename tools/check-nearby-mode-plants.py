#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Actual selected architecture-reader direction faults through C17 raw probes."""
import os
from pathlib import Path
import shlex
import subprocess

def main():
 e=os.environ;cc=shlex.split(e['MODE_CC']);flags=shlex.split(e['MODE_FLAGS']);runner=shlex.split(e.get('MODE_RUNNER',''));work=Path(e['MODE_WORK']);work.mkdir(parents=True,exist_ok=True)
 def run(args,label,status=0,input=None):
  p=subprocess.run(args,input=input,capture_output=True,text=True,timeout=180);(work/(label+'.log')).write_text(p.stdout+p.stderr)
  if p.returncode!=status:raise RuntimeError(label+' status '+str(p.returncode)+' '+p.stdout[-200:]+p.stderr[-200:])
  return p
 macro=run(cc+flags+['-dM','-E','-include','src/elementary/nearby_mode.h','-x','c','-'],'macros',input='').stdout
 if '#define GMATH_NEARBY_QUERY_NATIVE 1' not in macro:
  if e.get('MODE_REQUIRE_NATIVE')=='1':raise RuntimeError('architecture plant requires actual native reader')
  print('nearby native direction plant: SKIPPED standard-fenv query configuration');return
 source=Path('src/elementary/nearby.c').read_text();helper=Path('src/elementary/nearby_mode.h').read_text()
 if '__SSE__' in macro:key='x86';old='(control >> 13) & 3u';new='(control >> 12) & 3u'
 elif '__aarch64__' in macro:key='aarch64';old='(control >> 22) & 3u';new='(control >> 23) & 3u'
 elif '__s390x__' in macro:key='s390';old='code == 1u ? 3 : code == 3u ? 1 : (int)code';new='(int)code'
 elif 'GMATH_NEARBY_PPC_NATIVE' in macro:key='powerpc';old='code == 1u ? 3 : code == 3u ? 1 : (int)code';new='(int)code'
 elif 'GMATH_NEARBY_SPARC_NATIVE' in macro:key='sparc';old='code == 1u ? 3 : code == 3u ? 1 : (int)code';new='(int)code'
 else:raise RuntimeError('unknown native-reader plant configuration')
 # Limit repeated mapping anchors to the actually selected preprocessor branch.
 begin=helper.index('#elif defined(__s390x__)') if key=='s390' else helper.index('#elif defined(GMATH_NEARBY_PPC_NATIVE)') if key=='powerpc' else helper.index('#elif defined(GMATH_NEARBY_SPARC_NATIVE)') if key=='sparc' else 0
 end=helper.index('#elif',begin+6) if key in ['s390','powerpc'] else len(helper)
 region=helper[begin:end]
 if region.count(old)!=1:raise RuntimeError('native direction anchor differs '+key)
 for label,text,status in [('control',helper,0),('direction',helper[:begin]+region.replace(old,new,1)+helper[end:],1)]:
  file=work/(label+'.c');file.write_text(source);(work/'nearby_mode.h').write_text(text);binary=work/label
  run(cc+flags+['-Isrc/elementary','tools/probe-nearby.c',str(file),'-lm','-o',str(binary)],label+'-build')
  for width in [64,32]:
   p=run(runner+[str(binary),'tests/corpus',str(width)],label+'-'+str(width),status)
   if status and 'nearby mismatch' not in p.stderr:raise RuntimeError('direction plant fails outside value/state layer')
 print('nearby '+key+' actual native direction defect detects in both formats with passing control')
if __name__=='__main__':
 try:main()
 except (OSError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('nearby mode plants: FAIL: '+str(e))
