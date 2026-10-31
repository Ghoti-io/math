#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Actual i686 no-SSE link, mode/state and fallback-regression checks.

X87_CC/X87_RUNNER select an installed native or cross toolchain. A missing
default 32-bit runtime skips explicitly; GMATH_REQUIRE_X87=1 requires execution.
Test-only raw probes link platform fenv, while the bare client never does.
"""
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

def main():
 e=os.environ;cc=shlex.split(e.get('X87_CC',e.get('CC','cc')));runner=shlex.split(e.get('X87_RUNNER',''))
 base=shlex.split(e.get('X87_FLAGS','-std=c17 -ffp-contract=off -fno-math-errno -Iinclude -Ibuild/linux/release/generated'))
 work=Path(e.get('X87_WORK','build/x87-rounding'));work.mkdir(parents=True,exist_ok=True);records=[]
 (work/'complete.json').unlink(missing_ok=True)
 def run(command,label,want=0):
  start=time.monotonic();record=dict(label=label,command=command,returncode=None)
  records.append(record)
  (work/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
  try:r=subprocess.run(command,capture_output=True,text=True,timeout=180)
  except subprocess.TimeoutExpired as error:
   def decoded(value):return value.decode(errors='replace') if isinstance(value,bytes) else value or ''
   (work/(label+'.log')).write_text(decoded(error.stdout)+decoded(error.stderr))
   record.update(timed_out=True,elapsed_seconds=time.monotonic()-start)
   (work/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
   raise RuntimeError(label+' exceeded 180 second command deadline') from error
  (work/(label+'.log')).write_text(r.stdout+r.stderr)
  record.update(returncode=r.returncode,elapsed_seconds=time.monotonic()-start)
  (work/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
  if want is not None and r.returncode!=want:raise RuntimeError(label+' status '+str(r.returncode)+' '+r.stderr[-500:])
  return r
 configured=bool(runner) or cc!=shlex.split(e.get('X87_DEFAULT_CC',e.get('CC','cc')))
 required=e.get('GMATH_REQUIRE_X87')=='1' or configured
 initial=run(cc+base+['-dM','-E','-x','c','/dev/null'],'compiler-macros').stdout
 if not any(x in initial for x in ['#define __i386__ ','#define __x86_64__ ']) or '#define GMATH_NEARBY_FENV_QUERY ' in initial:
  if required:raise RuntimeError('required x87 configuration is not a native x86 configuration')
  print('x87 rounding: SKIPPED non-x86 or explicitly forced platform-query configuration');return
 flags=base+['-m32','-march=i686','-mno-sse','-mno-sse2','-mfpmath=387']
 capability=work/'capability.c';capability.write_text('#include <stdint.h>\nint main(void) {return sizeof(void*)!=4;}\n')
 available=run(cc+flags+[str(capability),'-o',str(work/'capability')],'capability-build',None)
 if available.returncode:
  missing=any(x in available.stderr for x in ['bits/libc-header-start.h','bits/wordsize.h','Scrt1.o','crti.o','cannot find -lgcc','cannot find libgcc'])
  if required or not missing:raise RuntimeError('configured i686 no-SSE toolchain failed: '+available.stderr[-500:])
  print('x87 rounding: SKIPPED missing default 32-bit headers/runtime; set X87_CC/X87_RUNNER and GMATH_REQUIRE_X87=1')
  return
 run(runner+[str((work/'capability').resolve())],'capability-run')
 helper=Path('src/elementary/nearby_mode.h').read_text()
 old='((defined(__i386__) || defined(__x86_64__)) ||'
 regression='((defined(__SSE__) && (defined(__i386__) || defined(__x86_64__))) ||'
 if helper.count(old)!=1 or helper.count('(control >> 10) & 3u')!=1:raise RuntimeError('x87 source-control anchors differ')
 sources=sorted(Path('src').rglob('*.c'))
 for opt in ['0','2']:
  selected=flags+['-O'+opt,'-DGMATH_BUILD','-Isrc/elementary']
  macro=run(cc+selected+['-dM','-E','-include','src/elementary/nearby_mode.h',str(capability)],'O'+opt+'-macros').stdout
  if '#define __i386__ ' not in macro or '#define __SSE__ ' in macro or '#define GMATH_NEARBY_QUERY_NATIVE 1' not in macro:raise RuntimeError('actual no-SSE native backend differs')
  variants=[('native',helper,[]),('fallback',helper.replace(old,regression,1),['-fno-builtin-fegetround']),
            ('direction',helper.replace('(control >> 10) & 3u','(control >> 11) & 3u',1),[]),
            ('override',helper,['-DGMATH_NEARBY_FENV_QUERY','-fno-builtin-fegetround'])]
  common=[]
  for index,source in enumerate(sources):
   if source.name in ['nearby.c','current_intround.c']:continue
   obj=work/('O'+opt+'-common-'+str(index)+'.o')
   run(cc+selected+['-c',str(source),'-o',str(obj)],'O'+opt+'-common-'+str(index))
   common.append(str(obj))
  native_objects=None
  for kind,text,extra in variants:
   tag='O'+opt+'-'+kind;folder=work/tag;folder.mkdir(exist_ok=True);(folder/'nearby_mode.h').write_text(text);objects=[]
   for name in ['nearby.c','current_intround.c']:
    source=folder/name;source.write_bytes((Path('src/elementary')/name).read_bytes());obj=folder/(name+'.o')
    run(cc+selected+extra+['-c',str(source),'-o',str(obj)],tag+'-'+name+'-build');objects.append(str(obj))
   binary=folder/'client';command=cc+selected+['tools/probe-x87-rounding.c']+objects+common+['-o',str(binary)]
   link=run(command,tag+'-bare-link',None)
   if kind in ['fallback','override']:
    if not link.returncode or 'fegetround' not in link.stderr:raise RuntimeError(tag+' did not reject at unresolved fegetround link')
    run(command+['-lm'],tag+'-platform-link')
    result=run(runner+[str(binary.resolve())],tag+'-platform-run')
    if result.stdout!='x87 nearby/rint/currentint 4 modes 3 precisions 3 incoming states 6528 calls pass\n' or result.stderr:raise RuntimeError('platform x87 observation accounting differs')
   else:
    if link.returncode:raise RuntimeError(tag+' bare C link failed')
    result=run(runner+[str(binary.resolve())],tag+'-run',0 if kind=='native' else 1)
    if kind=='direction' and 'x87 api' not in result.stderr:raise RuntimeError('x87 direction defect failed outside value/state layer')
    if kind=='native' and (result.stdout!='x87 nearby/rint/currentint 4 modes 3 precisions 3 incoming states 6528 calls pass\n' or result.stderr):raise RuntimeError('native x87 observation accounting differs')
   if kind=='native':native_objects=objects+common
  # Reuse the existing complete raw all-mode/state probes. Platform fenv is
  # linked only into these independent test callers, not the production client.
  for family,source in [('nearby','tools/probe-nearby.c'),('currentint','tools/probe-currentint.c')]:
   binary=work/('O'+opt+'-'+family+'-raw')
   run(cc+selected+['-Wno-error=unused-function',source]+native_objects+['-lm','-o',str(binary)],'O'+opt+'-'+family+'-raw-build')
   manifest=Path('tests/corpus')/('nearby-special.hash' if family=='nearby' else 'currentint-special.hash')
   for width in ['64','32']:
    key=('nearby.nearbyint' + ('f' if width=='32' else '')) if family=='nearby' else 'currentint.long32.'+width
    rows=[line for line in manifest.read_text().splitlines() if line.startswith(key+' ')]
    if len(rows)!=1:raise RuntimeError('raw manifest selection differs: '+key)
    result=run(runner+[str(binary.resolve()),'tests/corpus',width],'O'+opt+'-'+family+'-'+width)
    if result.stdout!=rows[0]+' from tests/corpus\n' or result.stderr:raise RuntimeError('raw hash/state/count/path differs: '+key)
 (work/'complete.json').write_text(json.dumps(dict(returncode=0,optimizations=['O0','O2'],modes=4,precisions=3,incoming_states=3,apis=8,logical_bare_calls=13056,logical_platform_calls=26112,raw_probes=8),indent=2)+'\n')
 print('x87 i686 O0/O2 bare no-libm clients pass all4 modes/3 precisions; fallback fegetround links reject; direction faults detect; query override and8 existing raw probes pass')

if __name__=='__main__':
 try:main()
 except (OSError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('x87 rounding: FAIL: '+str(e))
