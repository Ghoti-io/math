#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Calibrate complete-payload, exact-cell, widening and publisher checks."""
import argparse
import ast
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

def module(path):
 spec=importlib.util.spec_from_file_location('ieee_checker',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
 p=argparse.ArgumentParser();p.add_argument('--checker',type=Path,default=Path('tools/check-ieee-remainder.py'));p.add_argument('--inner',action='store_true');a=p.parse_args();checker=module(a.checker)
 with tempfile.TemporaryDirectory(prefix='gmath-ieee-reference-controls-') as directory:
  root=Path(directory)
  for name in checker.FILES:shutil.copyfile(Path('tests/corpus')/name,root/name)
  checker.verify(root)
  def reject(diagnostic,fresh=False,seed=20261028,count=1000):
   try:checker.verify(root,fresh,seed,count)
   except RuntimeError as e:
    if diagnostic not in str(e):raise RuntimeError('wrong reference negative layer: '+str(e)) from e
   else:raise RuntimeError('reference fault escaped: '+diagnostic)
  for name in checker.FILES:
   file=root/name;old=file.read_bytes();file.write_bytes(old+b'\n')
   reject('complete reference checksum');file.write_bytes(old)
  for name in checker.FILES:
   file=root/name;old=file.read_bytes()
   with file.open('wb') as stream:stream.truncate(checker.LIMITS[name]+1)
   original_open=Path.open
   def guarded_open(path,*args,**kwargs):
    if path==file:raise RuntimeError('oversized payload was opened before rejection')
    return original_open(path,*args,**kwargs)
   try:
    with mock.patch.object(Path,'open',guarded_open):reject('reference payload exceeds bounded size')
   finally:file.write_bytes(old)
  # A valid alternate metadata representation bypasses only committed SHA;
  # independent exact certificates/population/widening checks still apply.
  for name in checker.FILES:
   if name.endswith('.corpus'):
    file=root/name;file.write_bytes(file.read_bytes().replace(b'fresh False',b'fresh True'))
  checker.verify(root,True,20261028,1000)
  fresh={name:(root/name).read_bytes() for name in checker.FILES}
  for width,name in [(64,'remainder'),(32,'remainderf')]:
   file=root/(name+'-special.corpus');lines=file.read_text().splitlines(keepends=True)
   index=next(i for i,line in enumerate(lines) if not line.startswith('#') and int(line.split()[3])!=0 and int(line.split()[2],16)&((1<<(width-1))-1)!=0)
   for column in (2,3,4):
    words=lines[index].split()
    if column==2:words[2]=('%0*x'%(width//4,int(words[2],16)^1))
    elif column==3:words[3]=str(int(words[3])+1)
    else:words[4]=str(1-int(words[4]))
    changed=list(lines);changed[index]=' '.join(words)+'\n';file.write_text(''.join(changed))
    reject('exact rational remainder/quotient certificate',True);file.write_bytes(fresh[file.name])
  for name in ['remainder.corpus','remainder_quotient.corpus','remainderf.corpus','remainderf_quotient.corpus']:
   file=root/name;lines=file.read_text().splitlines(keepends=True);index=next(i for i,v in enumerate(lines) if not v.startswith('#'));words=lines[index].split();words[2]='%016x'%(int(words[2],16)^1);lines[index]=' '.join(words)+'\n';file.write_text(''.join(lines))
   reject('complete widened rows/exclusions differ',True);file.write_bytes(fresh[name])
  file=root/'remainder-special.corpus';file.write_bytes(fresh[file.name].replace(b'seed 20261028',b'seed 20261029'))
  reject('requested seed/count/fresh metadata differs',True)
  reject('complete ordered population mismatch',True,20261029,1000);file.write_bytes(fresh[file.name])
  file=root/'ieee_remainder-special.hash';data=file.read_text();words=data.splitlines()[0].split();words[2]='%016x'%(int(words[2],16)^1);file.write_text(' '.join(words)+'\n'+'\n'.join(data.splitlines()[1:])+'\n');reject('independent raw/state hash/count manifest differs',True);file.write_bytes(fresh[file.name])
  print('IEEE remainder: seven checksum/oversize-before-open faults each, six exact-result/quotient/flag certificate faults, four widened payload faults, metadata/population and manifest faults detect')
  if not a.inner:
   source=a.checker.read_text();anchor='(r,q,invalid)!=answer(x,y,width)'
   if source.count(anchor)!=1:raise RuntimeError('exact certificate counterfactual anchor')
   disabled=root/'disabled-checker.py';disabled.write_text(source.replace(anchor,'False'))
   q=subprocess.run([sys.executable,__file__,'--checker',str(disabled),'--inner'],capture_output=True,text=True,timeout=240)
   if q.returncode!=1 or 'wrong reference negative layer' not in q.stderr:raise RuntimeError('disabled certificate control did not fail at missing layer: '+q.stdout[-500:]+q.stderr[-500:])
   print('IEEE remainder: actual disabled-certificate counterfactual is rejected at the missing certificate layer')
 # Execute the actual own publisher definitions with their standard-library
 # globals; this isolates publication accounting from optional MPFR imports.
 tree=ast.parse(Path('tools/oracle/gen_corpus_float_scale.py').read_text());functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('publish','publish_set')]
 if len(functions)!=2:raise RuntimeError('publisher definitions missing')
 env=dict(Path=Path,tempfile=tempfile,shutil=shutil,os=os);exec(compile(ast.Module(body=functions,type_ignores=[]),'own-publisher-controls','exec'),env)
 for exists in (False,True):
  with tempfile.TemporaryDirectory(prefix='gmath-ieee-publication-success-') as d:
   root=Path(d);payloads={name:'new '+name for name in sorted(checker.FILES)}
   if exists:
    for name in payloads:(root/name).write_text('old');(root/name).chmod(0o640)
   env['publish_set'](root,payloads)
   if {file.name for file in root.iterdir()}!=set(payloads):raise RuntimeError('successful publication set/cleanup differs')
   for name,text in payloads.items():
    if (root/name).read_text()!=text or (root/name).stat().st_mode&0o777!=(0o640 if exists else 0o644):raise RuntimeError('successful publication content/permissions differ')
 for exists in (False,True):
  for failure in range(7):
   with tempfile.TemporaryDirectory(prefix='gmath-ieee-publication-') as d:
    root=Path(d);payloads={name:'new '+name for name in sorted(checker.FILES)}
    if exists:
     for name in payloads:(root/name).write_text('old '+name);(root/name).chmod(0o640)
    original=Path.replace;calls=0
    def fail_nth(path,target):
     nonlocal calls
     if path.name.startswith('new'):
      calls+=1
      if calls==failure+1:raise OSError('injected set replacement')
     return original(path,target)
    try:
     with mock.patch.object(Path,'replace',fail_nth):env['publish_set'](root,payloads)
    except OSError as e:
     if 'injected' not in str(e):raise
    else:raise RuntimeError('publication replacement fault escaped')
    for name in payloads:
     if exists:
      if (root/name).read_text()!='old '+name or (root/name).stat().st_mode&0o777!=0o640:raise RuntimeError('rollback changed existing payload/permissions')
     elif (root/name).exists():raise RuntimeError('rollback left new payload')
    if any(p.name.startswith('.') for p in root.iterdir()):raise RuntimeError('publication temporary set leaked')
 print('IEEE remainder: two successful publications and fourteen seven-position existing/absent publication rollback/permission/cleanup controls pass; not crash atomicity')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('IEEE remainder reference controls: FAIL: '+str(e))
