#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Complete pinned bytes/populations and independent raw accuracy/state execution.

Fresh target cells originate in the pinned directed MPFR/mpmath generator;
this host checker reconstructs population/flags/generic rows, not transcendental
values. The C probe checks independent nearest cells and observed state.
"""
import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile
from atan_reference import (COUNT,SEED,SIGN,INF,QNAN,TINY,LARGE,PIO2,flags,population,selected)
EXPECTED={'atan-special.corpus': '4536e60e605ae4adf349928c1946ad20aade18a34209ac0f6f2bc852318f694e', 'atan.corpus': 'd5605413f8faf933c8239e9e56f5e087fab54297d7ff6abdb4926ba1d60388fb', 'atan-special.hash': '0f5a04865dfe34dbd9d6b99da65cea0bbbf587d9e2f0448bb661a5e96c8d7764'}
PROVENANCE='# Pinned oracle: atan MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1'
MAX_BYTES=8*1024*1024

def text(path):
 if not path.is_file() or not 0<path.stat().st_size<=MAX_BYTES:raise RuntimeError('atan payload missing/oversized before read')
 with path.open('rb') as stream:data=stream.read(MAX_BYTES+1)
 if len(data)>MAX_BYTES or b'\0' in data or b'\r' in data or not data.endswith(b'\n'):raise RuntimeError('atan noncanonical payload bytes')
 return data.decode('ascii')

def check(root,seed=SEED,count=COUNT,fresh=False,pinned=True):
 names=['atan-special.corpus','atan.corpus']+(['atan-special.hash'] if pinned else [])
 data={n:text(root/n) for n in names}
 if pinned:
  for n in names:
   if hashlib.sha256(data[n].encode('ascii')).hexdigest()!=EXPECTED[n]:raise RuntimeError('atan complete SHA256 differs: '+n)
 lines=data['atan-special.corpus'].splitlines()
 if len(lines)<5 or lines[:2]!=[PROVENANCE,'# function atan64']:raise RuntimeError('atan raw provenance/schema differs')
 meta=re.fullmatch(r'# seed (0|[1-9][0-9]*) count (0|[1-9][0-9]*) fresh (true|false) entries ([1-9][0-9]*)',lines[2])
 if not meta or (int(meta[1]),int(meta[2]),meta[3])!=(seed,count,str(fresh).lower()) or int(meta[4])>100000 or lines[3]!='# input nearest-target signed-error32 normalized-flags':raise RuntimeError('atan metadata differs')
 rows=[]
 for line in lines[4:]:
  match=re.fullmatch(r'([0-9a-f]{16}) ([0-9a-f]{16}) ([0-9a-f]{8}) ([0126])',line)
  if not match:raise RuntimeError('atan row schema differs')
  x,target,error=(int(match[i],16) for i in [1,2,3]);flag=int(match[4]);a=x&(SIGN-1);t=target&(SIGN-1)
  if flag!=flags(x) or (error&0x7fffffff)>0x3f000000:raise RuntimeError('atan reference flags/error shape differs')
  if a>INF:
   if target!=QNAN or error:raise RuntimeError('atan NaN target differs')
  elif not a:
   if target!=x or error:raise RuntimeError('atan zero target differs')
  elif not 0<t<=PIO2 or (target>>63)!=(x>>63):raise RuntimeError('atan normal target shape differs')
  elif a<TINY and target!=x:raise RuntimeError('atan tiny nearest target differs')
  elif a>=LARGE and target!=(PIO2|(x&SIGN)):raise RuntimeError('atan large nearest target differs')
  rows.append((x,target,error,flag))
 if len(rows)!=int(meta[4]) or [r[0] for r in rows]!=population(seed,count):raise RuntimeError('atan complete requested population differs')
 generic=[r for r in rows if not ((r[0]&(SIGN-1))>INF and not r[0]&(1<<51))]
 header=PROVENANCE+'\n# function atan\n# seed %d count %d fresh %s entries %d\n'%(seed,count,str(fresh).lower(),len(generic))+'# binary64 input/result; signed binary32 error in true binary64 ULP\n'
 expected=header+''.join('%016x %016x %08x\n'%r[:3] for r in generic)
 if data['atan.corpus']!=expected:raise RuntimeError('atan complete generic reconstruction differs')
 if pinned:
  h=data['atan-special.hash'].splitlines()
  if len(h)!=2 or h[0]!='# Observed implementation compatibility, not an independent oracle target':raise RuntimeError('atan compatibility schema differs')
 return data,len(rows),len(generic)

def probe(binary,root,data,rows,generic,seed,count,fresh,pinned):
 r=subprocess.run([str(binary.resolve()),str(root)],capture_output=True,text=True,timeout=180)
 pattern=r'atan64 raw ([0-9a-f]{16}) rows ([0-9]+) state ([0-9a-f]{16}) calls ([0-9]+) generic ([0-9a-f]{16}) rows ([0-9]+) from '+re.escape(str(root))+r' seed '+str(seed)+r' count '+str(count)+r' fresh '+str(fresh).lower()+r' maximum ([0-9]+\.[0-9]{9})\n'
 m=re.fullmatch(pattern,r.stdout)
 expected_calls=sum((32 if selected(int(line[:16],16),index) else 1)*8 for index,line in enumerate(data['atan-special.corpus'].splitlines()[4:],1))
 if r.returncode or r.stderr or not m or (int(m[2]),int(m[6]))!=(rows,generic) or not 0<=float(m[7])<=.60 or int(m[4])!=expected_calls:raise RuntimeError('atan actual raw/state output/count differs')
 if pinned and r.stdout.split(' from ')[0]!=data['atan-special.hash'].splitlines()[1]:raise RuntimeError('atan observed compatibility hash/count differs')
 return r.stdout,(m[5],str(generic))

def fresh_controls(a,data,rows,generic):
 output,atan=probe(a.probe,a.directory,data,rows,generic,a.seed,a.count,True,False)
 if a.unit:
  env=dict(os.environ,GMATH_ATAN_CORPUS_DIR=str(a.directory));cmd=[str(a.unit.resolve()),'--gtest_filter=Atan.PinnedCorpusAndCallerState','--gtest_brief=1']
  r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=180)
  if r.returncode or output not in r.stdout:raise RuntimeError('atan fresh unit ignores requested population/path')
  with tempfile.TemporaryDirectory(prefix='atan-empty-') as empty:
   env['GMATH_ATAN_CORPUS_DIR']=empty;r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=30)
   if r.returncode!=1:raise RuntimeError('atan empty-directory counterfactual escaped')
 if a.numeric:
  spec=importlib.util.spec_from_file_location('fdim_protocol',Path(__file__).with_name('check-positive-difference.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory(prefix='atan-overlay-') as t:
   overlay=Path(t)
   for path in Path('tests/corpus').iterdir():
    if path.is_file():(overlay/path.name).symlink_to(path.resolve())
   (overlay/'atan.corpus').unlink();(overlay/'atan.corpus').symlink_to((a.directory/'atan.corpus').resolve())
   wanted={f[1]:(f[2],f[3]) for f in map(str.split,Path('tests/corpus/trig.hash').read_text().splitlines()) if f and f[0]=='fn'};wanted['atan']=atan
   r=subprocess.run([str(a.numeric.resolve()),str(overlay)],capture_output=True,text=True,timeout=180);hashes,counts=module.numeric_output(r.stdout,r.stderr)
   if r.returncode or {n:(h,counts.get(n)) for n,h in hashes.items() if n!='trig'}!=wanted or hashes.get('trig')!='f5fa269eb60ee34f' or counts.get('trig')!='292711':raise RuntimeError('atan complete numeric overlay differs')
 print('atan complete fresh population/generic/path/raw/accuracy/state pass')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',type=Path,default=Path('tests/corpus'));p.add_argument('--seed',type=int,default=SEED);p.add_argument('--count',type=int,default=COUNT);p.add_argument('--fresh',action='store_true');p.add_argument('--probe',type=Path);p.add_argument('--unit',type=Path);p.add_argument('--numeric',type=Path);a=p.parse_args()
 if not 0<=a.seed<1<<64 or not 0<=a.count<=50000:p.error('atan seed/count outside bounds')
 if (a.unit or a.numeric) and (not a.fresh or not a.probe):p.error('unit/numeric require fresh and probe')
 data,rows,generic=check(a.directory,a.seed,a.count,a.fresh,not a.fresh)
 if a.fresh and a.probe:fresh_controls(a,data,rows,generic)
 elif a.probe:probe(a.probe,a.directory,data,rows,generic,a.seed,a.count,False,True)
 print('atan complete pinned SHA/population checks pass' if not a.fresh else 'atan complete fresh population checks pass')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:raise SystemExit('atan checks: FAIL: '+str(error))
