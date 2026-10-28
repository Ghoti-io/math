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
 print('currentint benchmark guard controls are reduced-workload accounting evidence, not measured performance')
if __name__=='__main__':main()
