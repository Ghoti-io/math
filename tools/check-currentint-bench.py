#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Reduced-workload actual benchmark guard counterfactuals, not timing evidence."""
import os
from pathlib import Path
import shlex
import subprocess

def main():
 e=os.environ;work=Path(e['BENCH_WORK']);work.mkdir(parents=True,exist_ok=True)
 source=Path('tools/bench-currentint.c').read_text().replace('#define N 4096','#define N 16',1).replace('#define PAIRS 401','#define PAIRS 3',1)
 mutations=[('control',source,0,''),('checksum',source.replace('hash+=call(api,i);','hash+=call(api,i)+1;',1),2,'timed checksum mismatch'),
  ('disabled-checksum',source.replace('hash+=call(api,i);','hash+=call(api,i)+1;',1).replace('if (hash!=expected_hash)','if (0 && hash!=expected_hash)',1),0,''),
  ('finite-range-classifier',source.replace('rounded >= boundary','rounded > boundary',1),2,'own per-input state mismatch')]
 for label,text,status,diagnostic in mutations:
  if label!='control' and text==source:raise RuntimeError('benchmark guard anchor absent')
  path=work/(label+'.c');binary=work/label;path.write_text(text)
  command=shlex.split(e['BENCH_CC'])+shlex.split(e['BENCH_CFLAGS'])+[str(path),e['BENCH_ARCHIVE']]+shlex.split(e['BENCH_LDFLAGS'])+['-lm','-o',str(binary)]
  r=subprocess.run(command,capture_output=True,text=True,timeout=60);(work/(label+'-compile.log')).write_text(r.stdout+r.stderr)
  if r.returncode:raise RuntimeError('benchmark guard compile failed '+label+r.stderr[-200:])
  r=subprocess.run([str(binary.resolve())],capture_output=True,text=True,timeout=60);(work/(label+'.log')).write_text(r.stdout+r.stderr)
  if r.returncode!=status or (diagnostic and diagnostic not in r.stderr):raise RuntimeError('benchmark guard counterfactual differs '+label)
  print('currentint reduced benchmark '+label+' control passes',flush=True)
 # Exercise actual-prior branches with explicit forwarding controls. These
 # are deliberate own test shims, not claimed historical baseline objects.
 declarations='\n#define GMATH_CURRENTINT_REFERENCE 1\n#define GMATH_CURRENTINT_BASELINE_IDENTITY "currentint test-only forwarding controls\\n"\n'
 wrappers='\n'
 for name,typ,arg in [('lrint','long','double'),('lrintf','long','float'),('llrint','long long','double'),('llrintf','long long','float')]:
  wrappers+=typ+' gmath_'+name+'_prior('+arg+' x) { '+typ+' result=gmath_'+name+'(x); CONTROL return result; }\n'
 for label,operation,status in [('reference-control','',0),('reference-result','if(!(fetestexcept(FE_INVALID)))result^=1;',2),('reference-invalid','if(fetestexcept(FE_INVALID))(void)feclearexcept(FE_INVALID);',2),('reference-errno','errno=199;',2)]:
  text=declarations+source+wrappers.replace('CONTROL',operation)
  path=work/(label+'.c');binary=work/label;path.write_text(text)
  r=subprocess.run(shlex.split(e['BENCH_CC'])+shlex.split(e['BENCH_CFLAGS'])+[str(path),e['BENCH_ARCHIVE']]+shlex.split(e['BENCH_LDFLAGS'])+['-lm','-o',str(binary)],capture_output=True,text=True,timeout=60)
  (work/(label+'-compile.log')).write_text(r.stdout+r.stderr)
  if r.returncode:raise RuntimeError('reference guard compile failed '+label+r.stderr[-400:])
  r=subprocess.run([str(binary.resolve()),'--validate-only'],capture_output=True,text=True,timeout=60);(work/(label+'.log')).write_text(r.stdout+r.stderr)
  if r.returncode!=status or (status and 'comparison per-input value/state mismatch' not in r.stderr):raise RuntimeError('reference branch counterfactual differs '+label+r.stderr[-200:])
  print('currentint reduced benchmark '+label+' passes',flush=True)
 # The forwarding wrapper is called N times by untimed checks, then once
 # per input in eight warmup and PAIRS timed batches. Fault only the latter.
 for label,operation in [('reference-timed-invalid','if(fetestexcept(FE_INVALID))(void)feclearexcept(FE_INVALID);'),('reference-timed-errno','errno=199;')]:
  fault='static unsigned calls; if((calls++ % (N*(1+8+PAIRS)))>=N) { '+operation+' }'
  text=declarations+source+wrappers.replace('CONTROL',fault)
  path=work/(label+'.c');binary=work/label;path.write_text(text)
  r=subprocess.run(shlex.split(e['BENCH_CC'])+shlex.split(e['BENCH_CFLAGS'])+[str(path),e['BENCH_ARCHIVE']]+shlex.split(e['BENCH_LDFLAGS'])+['-lm','-o',str(binary)],capture_output=True,text=True,timeout=60)
  (work/(label+'-compile.log')).write_text(r.stdout+r.stderr)
  if r.returncode:raise RuntimeError('timed reference compile failed '+label+r.stderr[-400:])
  r=subprocess.run([str(binary.resolve())],capture_output=True,text=True,timeout=60);(work/(label+'.log')).write_text(r.stdout+r.stderr)
  if r.returncode!=2 or 'timed comparison state mismatch' not in r.stderr:raise RuntimeError('timed reference fault escaped intended guard '+label+r.stderr[-200:])
  print('currentint reduced benchmark '+label+' passes',flush=True)
 print('currentint benchmark guard controls are reduced-workload accounting evidence, not measured performance')
if __name__=='__main__':main()
