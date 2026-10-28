#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Real loader/checksum/output/fresh-directory counterfactuals for nearby APIs."""
import argparse
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from nearby_reference import payloads,coverage,bits
spec=importlib.util.spec_from_file_location('nearby_checker',Path(__file__).with_name('check-nearby.py'));checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--unit',type=Path);p.add_argument('--numeric-probe',type=Path);p.add_argument('--fresh',type=Path);p.add_argument('--seed',type=int,default=20261028);p.add_argument('--count',type=int,default=2000);a=p.parse_args()
 binary=str(a.probe.resolve());data=checker.check(Path('tests/corpus'),20261028,2000,False);checker.probe([binary],Path('tests/corpus'),data)
 if a.fresh:
  fresh=checker.check(a.fresh,a.seed,a.count,True,False);checker.probe([binary],a.fresh,fresh)
  if a.unit:
   env=os.environ.copy();env['GMATH_NEARBY_CORPUS_DIR']=str(a.fresh)
   r=subprocess.run([str(a.unit.resolve()),'--gtest_filter=Nearby.Pinned*','--gtest_brief=1'],env=env,capture_output=True,text=True,timeout=120)
   expected=''.join(line+' from '+str(a.fresh)+'\n' for line in fresh['nearby-special.hash'].splitlines())
   if r.returncode or expected not in r.stdout:raise RuntimeError('fresh C++ requested population/path differs')
   with tempfile.TemporaryDirectory(prefix='nearby-empty-') as t:
    env['GMATH_NEARBY_CORPUS_DIR']=t;r=subprocess.run([str(a.unit.resolve()),'--gtest_filter=Nearby.Pinned*','--gtest_brief=1'],env=env,capture_output=True,text=True,timeout=120)
    if r.returncode!=1:raise RuntimeError('fresh C++ ignores requested directory')
  if a.numeric_probe:
   with tempfile.TemporaryDirectory(prefix='nearby-overlay-') as t:
    root=Path(t)
    for src in Path('tests/corpus').iterdir():
     if src.is_file():(root/src.name).symlink_to(src.resolve())
    for name in ['nearbyint.corpus','nearbyintf.corpus']:
     (root/name).unlink();(root/name).symlink_to((a.fresh/name).resolve())
    r=subprocess.run([str(a.numeric_probe.resolve()),str(root)],capture_output=True,text=True,timeout=120)
    wanted={line.split()[1]:(line.split()[2],line.split()[3]) for line in Path('tests/corpus/trig.hash').read_text().splitlines() if line.startswith('fn ')}
    from nearby_reference import feed
    for name in ['nearbyint','nearbyintf']:
     h=14695981039346656037;n=0
     for line in fresh[name+'.corpus'].splitlines():
      if not line.startswith('#'):h=feed(h,int(line.split()[1],16));n+=1
     wanted[name]=('%016x'%h,str(n))
    hashes=dict(re.findall(r'^math\.(\w+)\.hash[ \t]+([0-9a-f]+)$',r.stdout,re.M));counts=dict(re.findall(r'^math\.(\w+)\.count[ \t]+([0-9]+)$',r.stdout,re.M))
    got={key:(h,counts.get(key)) for key,h in hashes.items() if key!='trig'}
    if r.returncode or got!=wanted or hashes.get('trig')!='f5fa269eb60ee34f' or counts.get('trig')!='292711':raise RuntimeError('fresh complete80-function numerical overlay differs')
  print('nearby fresh complete population/widening/path/unit/80-set overlay pass');return
 for width,name in [(64,'nearbyint'),(32,'nearbyintf')]:
  words={int(line.split()[0],16) for line in data[name+'-special.corpus'].splitlines() if not line.startswith('#')}
  coverage(words,width);missing=words-{bits(float((1<<17)+0.5),width)}
  try:coverage(missing,width)
  except RuntimeError as e:
   if 'half-cell coverage missing' not in str(e):raise
  else:raise RuntimeError('actual observed half-cell omission escaped')
 with tempfile.TemporaryDirectory(prefix='nearby-controls-') as t:
  root=Path(t)
  for name,text in data.items():(root/name).write_text(text)
  checks=0
  for width,name in [(64,'nearbyint'),(32,'nearbyintf')]:
   original=data[name+'-special.corpus'];lines=original.splitlines(True);path=root/(name+'-special.corpus')
   first=lines[4].split();ordinary=next(i for i,line in enumerate(lines[4:],4) if line.split()[0] in ['3ff8000000000000','3fc00000'])
   fixtures=[original.replace('Pinned oracle: nearby','Pinned oracle: wrong',1),original.replace('# function '+name,'# function wrong',1),
    original.replace('seed 20261028','seed -1',1),original.replace('count 2000','count 50001',1),original.replace('fresh false','fresh maybe',1),
    original.replace('seed 20261028','seed 18446744073709551616',1),original.replace('# input nearest','# input wrong',1),
    ''.join(lines[:-1]),''.join(lines[:5]+[lines[4]]+lines[5:]),''.join(lines[:4]+[lines[5],lines[4]]+lines[6:]),
    original.replace(lines[4],lines[4].lstrip('0') or 'x\n',1),original.replace(lines[4],lines[4].replace(' 0\n',' 2\n'),1),
    original.replace(lines[4],lines[4].replace(' 0\n',' 1\n'),1),original.replace(lines[4],lines[4].rstrip()+' extra\n',1),
    original+'# unexpected row\n',original+'\x00junk\n',original+'x'*300+'\n',original.rstrip('\n'),''.join(lines[:4]),
    original.replace('entries '+str(len(lines)-4),'entries 0',1)]
   for kind in ['uppercase','overwidth','entries-low','entries-high']:
    changed=lines.copy()
    if kind in ['uppercase','overwidth']:
     fields=changed[ordinary].split();fields[0]=fields[0].upper() if kind=='uppercase' else '0'+fields[0];changed[ordinary]=' '.join(fields)+'\n'
    else:changed[2]=changed[2].replace('entries '+str(len(lines)-4),'entries '+str(len(lines)-4+(-1 if kind=='entries-low' else 1)))
    fixtures.append(''.join(changed))
   for column in [1,2,3,4]:
    changed=lines.copy();fields=changed[ordinary].split();fields[column]='%0*x'%(width//4,int(fields[column],16)^1);changed[ordinary]=' '.join(fields)+'\n';fixtures.append(''.join(changed))
   for i,changed in enumerate(fixtures):
    path.write_text(changed);r=subprocess.run([binary,str(root),str(width)],capture_output=True,text=True,timeout=30)
    if r.returncode!=1 or 'nearby probe failed' not in r.stderr:raise RuntimeError('loader/value negative escaped '+str(width)+'/'+str(i))
    checks+=1
   path.write_text(original)
  for name,text in data.items():
   path=root/name;path.write_text(text+'\n')
   try:checker.check(root,20261028,2000,False)
   except RuntimeError as e:
    if 'checksum differs' not in str(e):raise
   else:raise RuntimeError('complete checksum negative escaped')
   path.write_text(text)
  checker.probe([binary],root,data)
  # Accounting controls mutate actual observed process protocol, not oracle data.
  good=''.join(line+' from '+str(root)+'\n' for line in data['nearby-special.hash'].splitlines())
  script=root/'record.py'
  def record(text,status=0,error=''):
   script.write_text('import sys\nsys.stdout.write('+repr(text)+')\nsys.stderr.write('+repr(error)+')\nsys.exit('+str(status)+')\n')
  record(good);checker.probe([sys.executable,str(script)],root,data)
  line=good.splitlines(keepends=True)[0];fields=line.split()
  def fault(index,value):
   changed=fields.copy();changed[index]=value
   return good.replace(line,' '.join(changed)+'\n',1)
  faults=[good.split('\n',1)[1],good+good,fault(1,'0000000000000000'),fault(2,str(int(fields[2])+1)),fault(5,str(int(fields[5])-1)),good.replace(str(root),'ignored')]
  for text,status,error in [(x,0,'') for x in faults]+[(good,1,''),(good,0,'unexpected')]:
   record(text,status,error)
   try:checker.probe([sys.executable,str(script)],root,data)
   except RuntimeError:pass
   else:raise RuntimeError('actual output/process accounting fault escaped')
 print('nearby%d loader/value negatives,5 payload corruptions and8 accounting faults detect with passing controls'%checks)
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('nearby controls: FAIL: '+str(e))
