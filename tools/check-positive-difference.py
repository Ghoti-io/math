#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Mandatory complete bytes/targets and observed positive-difference probe output."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
from positive_difference_reference import payloads, SEED, COUNT, feed
EXPECTED = {'fdim-special.hash': '41a445fb35c9a93f273caaa983c17fc43da13601eb57bd4a7280d44c80c30d59', 'fdim.corpus': '2439d8b7e598be1acf9801e05d241ea493e0414d5cbea11b297a09771ab29971', 'fdim32-special.corpus': '3b19fa016ce234a5cb34c294dfab356a349d80eff9e75a19573f3f530771111f', 'fdim64-special.corpus': '6af03f2027ae0ae869a0ae5bc49fda09bcfc7c7822e5ec76bb9f0d943117098d', 'fdimf.corpus': 'f86077aa9ffb280e5c1508e6ea52b3ab0abd95fafb38a29bc5adb161c0a53a17'}

def check(root,seed=SEED,count=COUNT,fresh=False,pinned=True):
 observed={}
 for name in EXPECTED:
  path=root/name
  if path.stat().st_size>32*1024*1024:raise RuntimeError('positive difference payload exceeds bound')
  data=path.read_bytes()
  if pinned and hashlib.sha256(data).hexdigest()!=EXPECTED[name]:raise RuntimeError('positive difference complete checksum differs: '+name)
  observed[name]=data
 data=payloads(seed,count,fresh)
 for name,text in data.items():
  if observed[name]!=text.encode():raise RuntimeError('positive difference complete population/targets/widening differs: '+name)
 return data

def expected_output(root,data,seed=SEED,count=COUNT,fresh=False):
 return ''.join(line+' from '+str(root)+' seed '+str(seed)+' count '+str(count)+' fresh '+str(fresh).lower()+'\n' for line in data['fdim-special.hash'].splitlines())

def probe(command,root,data,seed=SEED,count=COUNT,fresh=False):
 r=subprocess.run(command+[str(root)],capture_output=True,text=True,timeout=180)
 expected=expected_output(root,data,seed,count,fresh)
 if r.returncode or r.stderr or r.stdout!=expected:raise RuntimeError('positive difference raw output/state/count/path/metadata differs: '+r.stdout[-300:]+r.stderr[-500:])
 return r.stdout

def numeric_output(stdout,stderr):
 if stderr:raise RuntimeError('positive difference generic overlay diagnostics')
 hashes={};counts={};hardware=None
 for line in stdout.splitlines():
  match=re.fullmatch(r'math\.(\w+)\.(hash|count)[ \t]+([0-9a-f]+)',line)
  if match:
   name,kind,value=match.groups();target=hashes if kind=='hash' else counts
   if name in target:raise RuntimeError('positive difference duplicate generic overlay record')
   if kind=='hash' and not re.fullmatch('[0-9a-f]{16}',value):raise RuntimeError('positive difference generic hash shape differs')
   if kind=='count' and not value.isdecimal():raise RuntimeError('positive difference generic count shape differs')
   target[name]=value
  elif re.fullmatch(r'math\.sqrt_hardware\.available[ \t]+[01]',line):
   if hardware is not None:raise RuntimeError('positive difference duplicate generic availability record')
   hardware=line
  else:raise RuntimeError('positive difference generic overlay output schema differs: '+line)
 if set(hashes)!=set(counts) or hardware is None:raise RuntimeError('positive difference incomplete generic output schema')
 return hashes,counts

def fresh_controls(binary,unit,numeric,root,seed,count):
 data=check(root,seed,count,True,False);expected=probe([str(binary.resolve())],root,data,seed,count,True)
 if unit:
  env=dict(os.environ,GMATH_FDIM_CORPUS_DIR=str(root));cmd=[str(unit.resolve()),'--gtest_filter=PositiveDifference.Pinned*','--gtest_brief=1']
  r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=180)
  if r.returncode or expected not in r.stdout:raise RuntimeError('positive difference fresh unit ignores requested population/path')
  with tempfile.TemporaryDirectory(prefix='fdim-empty-') as t:
   env['GMATH_FDIM_CORPUS_DIR']=t;r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=30)
   if r.returncode!=1:raise RuntimeError('positive difference empty-directory counterfactual escaped')
 if numeric:
  with tempfile.TemporaryDirectory(prefix='fdim-overlay-') as t:
   overlay=Path(t)
   for path in Path('tests/corpus').iterdir():
    if path.is_file():(overlay/path.name).symlink_to(path.resolve())
   wanted={f[1]:(f[2],f[3]) for f in map(str.split,Path('tests/corpus/trig.hash').read_text().splitlines()) if f and f[0]=='fn'}
   for family in ['fdim','fdimf']:
    path=overlay/(family+'.corpus');path.unlink();path.symlink_to((root/path.name).resolve())
    h=14695981039346656037;n=0
    for row in data[family+'.corpus'].splitlines():
     if not row.startswith('#'):h=feed(h,int(row.split()[2],16));n+=1
    wanted[family]=('%016x'%h,str(n))
   r=subprocess.run([str(numeric.resolve()),str(overlay)],capture_output=True,text=True,timeout=180)
   hashes,counts=numeric_output(r.stdout,r.stderr)
   got={name:(h,counts.get(name)) for name,h in hashes.items() if name!='trig'}
   if r.returncode or got!=wanted or hashes.get('trig')!='f5fa269eb60ee34f' or counts.get('trig')!='292711':raise RuntimeError('positive difference complete generic overlay differs')
 print('positive difference complete fresh population/targets/widening/raw/path pass'+('; unit selection pass' if unit else '')+('; complete numeric overlay pass' if numeric else ''))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path);p.add_argument('--directory',type=Path,default=Path('tests/corpus'));p.add_argument('--seed',type=int,default=SEED);p.add_argument('--count',type=int,default=COUNT);p.add_argument('--fresh',action='store_true');p.add_argument('--unit',type=Path);p.add_argument('--numeric',type=Path);a=p.parse_args()
 if a.fresh and a.probe:fresh_controls(a.probe,a.unit,a.numeric,a.directory,a.seed,a.count)
 else:
  data=check(a.directory,a.seed,a.count,a.fresh,not a.fresh)
  if a.probe:probe([str(a.probe.resolve())],a.directory,data,a.seed,a.count,a.fresh)
 print(('positive difference complete exact fresh population checks pass' if a.fresh else 'positive difference complete SHA/exact population checks pass')+('; compiled state checks pass' if a.probe else ''))
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('positive difference checks: FAIL: '+str(e))
