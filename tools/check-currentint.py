#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Mandatory bytes, exact populations and current-integer raw/fresh selection."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile
from current_ir_reference import payloads, SEED, COUNT, feed
EXPECTED={'currentint32-special.corpus': '138f2722649f9700e11c3f3f44490f412131810093acbad2749816a564a27705', 'currentint-special.hash': 'b826f154d064a13e3ff0bb0432037343ac855c3c67fa56161571ea7d03a3d074', 'currentint64-special.corpus': '3edb91a44fe4b136975bc73aec5a10b4f8645e70bce4cd1c2754a7b75973467d', 'lrint.corpus': '7f09e2477a2056c0292eb9da38f7ec4e8edd706c5a2816876fe9940bde6e39dc', 'lrintf.corpus': 'e53eb8bbb157e7217162088031c19bc4918b2af4729572051056d082dede8b66', 'llrint.corpus': '9c31fb03693f90b3a47ea44e5fe409a41e63d6b0dbe8a82c39f43c2d18bf4383', 'llrintf.corpus': 'ea72d2efcb8dd4cafd6910c0f971dda347475c21262a1f5a0481af7a02da50da'}

def check(root,seed=SEED,count=COUNT,fresh=False,pinned=True):
 data=payloads(seed,count,fresh)
 for name,text in data.items():
  path=root/name
  if path.stat().st_size>48*1024*1024:raise RuntimeError('currentint payload exceeds bound')
  observed=path.read_bytes()
  if pinned and hashlib.sha256(observed).hexdigest()!=EXPECTED[name]:raise RuntimeError('currentint complete checksum differs: '+name)
  if observed!=text.encode():raise RuntimeError('currentint requested complete population/targets/widening differ: '+name)
 return data

def probe(command,root,data,longbits=None):
 identity=subprocess.run(command+['--identify'],capture_output=True,text=True,timeout=30)
 match=re.fullmatch(r'currentint.long.bits (32|64)\n',identity.stdout)
 if identity.returncode or identity.stderr or not match:raise RuntimeError('currentint compiled target identity differs')
 actual=int(match.group(1))
 if longbits is not None and longbits!=actual:raise RuntimeError('currentint requested/compiled long width differs')
 longbits=actual
 expected=''.join(line+' from '+str(root)+'\n' for line in data['currentint-special.hash'].splitlines() if line.startswith('currentint.long%d.'%longbits))
 r=subprocess.run(command+[str(root)],capture_output=True,text=True,timeout=180)
 if r.returncode or r.stderr or r.stdout!=expected:raise RuntimeError('currentint raw output/state/count/path differs: '+r.stdout[-300:]+r.stderr[-500:])
 return r.stdout

def fresh_controls(binary,unit,numeric,root,seed,count):
 data=check(root,seed,count,True,False);expected=probe([str(binary.resolve())],root,data)
 if unit:
  env=dict(os.environ,GMATH_CURRENTINT_CORPUS_DIR=str(root));cmd=[str(unit.resolve()),'--gtest_filter=CurrentInteger.Pinned*','--gtest_brief=1']
  r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=180)
  if r.returncode or expected not in r.stdout:raise RuntimeError('currentint fresh unit ignores requested population/path')
  with tempfile.TemporaryDirectory(prefix='currentint-empty-') as t:
   env['GMATH_CURRENTINT_CORPUS_DIR']=t;r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=30)
   if r.returncode!=1:raise RuntimeError('currentint empty-directory counterfactual escaped')
 if numeric:
  with tempfile.TemporaryDirectory(prefix='currentint-overlay-') as t:
   overlay=Path(t)
   for source in Path('tests/corpus').iterdir():
    if source.is_file():(overlay/source.name).symlink_to(source.resolve())
   wanted={f[1]:(f[2],f[3]) for f in map(str.split,Path('tests/corpus/trig.hash').read_text().splitlines()) if f and f[0]=='fn'}
   for family in ['lrint','lrintf','llrint','llrintf']:
    target=overlay/(family+'.corpus');target.unlink();target.symlink_to((root/target.name).resolve())
    h=14695981039346656037;n=0
    for row in data[family+'.corpus'].splitlines():
     if not row.startswith('#'):h=feed(h,int(row.split()[1],16));n+=1
    wanted[family]=('%016x'%h,str(n))
   r=subprocess.run([str(numeric.resolve()),str(overlay)],capture_output=True,text=True,timeout=180)
   hashes=dict(re.findall(r'^math\.(\w+)\.hash[ \t]+([0-9a-f]+)$',r.stdout,re.M));counts=dict(re.findall(r'^math\.(\w+)\.count[ \t]+([0-9]+)$',r.stdout,re.M))
   got={name:(h,counts.get(name)) for name,h in hashes.items() if name!='trig'}
   if r.returncode or got!=wanted or hashes.get('trig')!='f5fa269eb60ee34f' or counts.get('trig')!='292711':raise RuntimeError('currentint complete generic overlay differs')
 print('currentint complete fresh population/targets/widening/raw/path pass'+('; unit selection pass' if unit else '')+('; complete numeric overlay pass' if numeric else ''))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path);p.add_argument('--directory',type=Path,default=Path('tests/corpus'));p.add_argument('--seed',type=int,default=SEED);p.add_argument('--count',type=int,default=COUNT);p.add_argument('--fresh',action='store_true');p.add_argument('--unit',type=Path);p.add_argument('--numeric',type=Path);a=p.parse_args()
 if a.fresh and a.probe:fresh_controls(a.probe,a.unit,a.numeric,a.directory,a.seed,a.count)
 else:
  data=check(a.directory,a.seed,a.count,a.fresh,not a.fresh)
  if a.probe:probe([str(a.probe.resolve())],a.directory,data)
 print(('currentint complete exact fresh population checks pass' if a.fresh else 'currentint complete SHA/exact population checks pass')+('; compiled state checks pass' if a.probe else ''))
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('currentint checks: FAIL: '+str(e))
