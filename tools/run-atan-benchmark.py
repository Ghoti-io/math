#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Certify actual workloads, record build/host identity, then retain paired runs.

Output belongs in a build directory: runtime context may contain machine paths.
Compiler arguments are caller-declared provenance, not source authentication.
Existing evidence is never overwritten. No CPU isolation/governor claim.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import time
active_context=None
spec=importlib.util.spec_from_file_location('atan_bench',Path(__file__).with_name('check-atan-bench.py'));bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)

def digest(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as file:
  for block in iter(lambda:file.read(1<<20),b''):h.update(block)
 return h.hexdigest()

def observed(command):
 try:
  r=subprocess.run(command,capture_output=True,text=True,timeout=30)
  return dict(command=command,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
 except (OSError,subprocess.SubprocessError) as error:return dict(command=command,error=str(error))

def main():
 global active_context
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--cc',required=True);p.add_argument('--flags',required=True);p.add_argument('--library-flags',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--runs',type=int,default=1);p.add_argument('--cpu',type=int);p.add_argument('--certify-only',action='store_true');a=p.parse_args()
 if not 1<=a.runs<=20:p.error('--runs must be1..20')
 if a.cpu is not None:
  if not hasattr(os,'sched_setaffinity'):p.error('--cpu requires affinity support')
  os.sched_setaffinity(0,{a.cpu})
 a.out.mkdir(parents=True,exist_ok=True)
 lock=a.out/'context.json'
 # Exclusive creation prevents a second invocation from replacing any run.
 with lock.open('x') as file:json.dump(dict(status='preparing'),file)
 active_context=lock
 context=dict(schema=1,status='certifying',binary=str(a.binary.resolve()),binary_sha256=digest(a.binary),archive=str(a.archive.resolve()),archive_sha256=digest(a.archive),compiler_command=shlex.split(a.cc),declared_caller_flags=shlex.split(a.flags),declared_library_flags=shlex.split(a.library_flags),compiler=observed(shlex.split(a.cc)+['--version']),platform=dict(system=platform.system(),machine=platform.machine(),release=platform.release(),processor=platform.processor()),cpu_isolation=False,governor_control=False,affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,host_libc=observed(['getconf','GNU_LIBC_VERSION']),dynamic_libraries=observed(['ldd',str(a.binary.resolve())]))
 cpu=Path('/proc/cpuinfo')
 if cpu.exists():
  text=cpu.read_text();context['cpu_model']=next((line.split(':',1)[1].strip() for line in text.splitlines() if line.startswith(('model name','Hardware'))),None)
 context['loader_environment']={key:os.environ.get(key) for key in ['LD_PRELOAD','LD_LIBRARY_PATH','LD_AUDIT','GLIBC_TUNABLES']}
 context['source_sha256']={str(path):digest(path) for path in [Path('tools/bench-atan.c'),Path('src/elementary/atan.c'),Path('src/elementary/atan2.c'),Path('src/elementary/atan2_table.h'),Path('src/elementary/elem_common.h'),Path('tests/fp_controls.h')] if path.exists()}
 context['host_libm']={}
 for path in re.findall(r'libm\.[^ \t\n]+[ \t]+=>[ \t]+([^ \t\n]+)',context['dynamic_libraries'].get('stdout','')):
  if Path(path).is_file():context['host_libm'][path]=digest(path)
 lock.write_text(json.dumps(context,indent=2)+'\n')
 count=bench.certify(a.binary);context['certified_reference_rows']=count;context['status']='certified';lock.write_text(json.dumps(context,indent=2)+'\n')
 if a.certify_only:
  context['status']='certification_only';context['record_count']=0;lock.write_text(json.dumps(context,indent=2)+'\n')
  print('atan benchmark context recorded; %d rows certified; no timing run'%count);return
 records=[]
 for run in range(1,a.runs+1):
  start=time.time()
  with (a.out/('run-%d.log'%run)).open('x') as out:r=subprocess.run([str(a.binary.resolve()),'tests/corpus'],stdout=out,stderr=subprocess.STDOUT,timeout=600)
  (a.out/('run-%d-status.json'%run)).write_text(json.dumps(dict(returncode=r.returncode,elapsed_seconds=time.time()-start))+'\n')
  if r.returncode:raise RuntimeError('paired benchmark failed; partial evidence retained, no replacement run')
  identity,parsed=bench.records((a.out/('run-%d.log'%run)).read_text())
  if 'benchmark_identity' in context and context['benchmark_identity']!=identity:raise RuntimeError('benchmark build identity changed between runs')
  context['benchmark_identity']=identity
  records.extend(dict(run=run,**record) for record in parsed)
  if digest(a.binary)!=context['binary_sha256'] or digest(a.archive)!=context['archive_sha256']:raise RuntimeError('binary/archive changed during measurement')
  (a.out/'records.json').write_text(json.dumps(records,indent=2)+'\n');print('atan paired run%d retains22cases'%run,flush=True)
 context['status']='complete';context['record_count']=len(records);lock.write_text(json.dumps(context,indent=2)+'\n')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
  if active_context is not None:
   try:
    context=json.loads(active_context.read_text());context['status']='failed';context['error']=str(error);active_context.write_text(json.dumps(context,indent=2)+'\n')
   except (OSError,ValueError):pass
  raise SystemExit('atan benchmark runner: FAIL: '+str(error))
