#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Observed loader, checksum, process and publication failure controls."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
spec=importlib.util.spec_from_file_location('currentint_checker',Path(__file__).with_name('check-currentint.py'));checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);a=p.parse_args();binary=str(a.probe.resolve())
 data=checker.check(Path('tests/corpus'));checker.probe([binary],Path('tests/corpus'),data)
 with tempfile.TemporaryDirectory(prefix='currentint-controls-') as t:
  root=Path(t)
  for name,text in data.items():(root/name).write_text(text)
  count=0
  for width in [64,32]:
   name='currentint%d-special.corpus'%width;path=root/name;text=data[name];lines=text.splitlines(True)
   ordinary=next(i for i,line in enumerate(lines[4:],4) if line.split()[0] in ['3ff8000000000000','3fc00000'])
   faults=[text.replace('Pinned oracle: currentint','Pinned oracle: wrong',1),text.replace('# function currentint','# function wrong',1),
    text.replace('seed 20261028','seed -1',1),text.replace('seed 20261028','seed 18446744073709551616',1),text.replace('count 2000','count 50001',1),text.replace('fresh false','fresh falsehood',1),
    text.replace('# input four-modes','# input wrong',1),''.join(lines[:-1]),''.join(lines[:5]+[lines[4]]+lines[5:]),''.join(lines[:4]+[lines[5],lines[4]]+lines[6:]),
    text+'\x00hidden\n',text+'x'*600+'\n',text.rstrip('\n'),text+'extra\n',text.replace(lines[4],lines[4].rstrip()+' extra\n',1)]
   for column in range(1,17):
    changed=lines.copy();fields=changed[ordinary].split()
    fields[column]=('%016x'%(int(fields[column],16)^1)) if column%2 else str((int(fields[column])+1)%3)
    changed[ordinary]=' '.join(fields)+'\n';faults.append(''.join(changed))
   for kind in ['uppercase','overwidth','count-low','count-high']:
    changed=lines.copy();fields=changed[ordinary].split()
    if kind in ['uppercase','overwidth']:
     fields[0]=fields[0].upper() if kind=='uppercase' else '0'+fields[0];changed[ordinary]=' '.join(fields)+'\n'
    else:changed[2]=changed[2].replace('entries '+str(len(lines)-4),'entries '+str(len(lines)-4+(-1 if kind=='count-low' else 1)))
    faults.append(''.join(changed))
   for index,changed in enumerate(faults):
    path.write_text(changed);r=subprocess.run([binary,str(root),str(width)],capture_output=True,text=True,timeout=60)
    if r.returncode!=1 or 'currentint probe failed' not in r.stderr:raise RuntimeError('loader/value fault escaped %d/%d'%(width,index))
    count+=1
   path.write_text(text)
  for name,text in data.items():
   path=root/name;path.write_text(text+'\n')
   try:checker.check(root)
   except RuntimeError as e:
    if 'checksum differs' not in str(e):raise
   else:raise RuntimeError('complete checksum fault escaped')
   path.write_text(text)
  good=checker.probe([binary],root,data);script=root/'record.py'
  def record(text,status=0,error=''):
   script.write_text('import sys\nif sys.argv[1:]==["--identify"]:\n print("currentint.long.bits '+good.split()[0].split('.')[1][4:]+'");sys.exit(0)\nsys.stdout.write('+repr(text)+')\nsys.stderr.write('+repr(error)+')\nsys.exit('+str(status)+')\n')
  record(good);checker.probe([sys.executable,str(script)],root,data)
  first=good.splitlines(True)[0];fields=first.split()
  def change(index,value):
   f=fields.copy();f[index]=value;return good.replace(first,' '.join(f)+'\n',1)
  faults=[good.split('\n',1)[1],good+good,change(1,'0000000000000000'),change(2,str(int(fields[2])+1)),change(4,'0000000000000000'),change(5,str(int(fields[5])-1)),good.replace(str(root),'ignored')]
  for text,status,error in [(x,0,'') for x in faults]+[(good,1,''),(good,0,'unexpected')]:
   record(text,status,error)
   try:checker.probe([sys.executable,str(script)],root,data)
   except RuntimeError:pass
   else:raise RuntimeError('actual process/output fault escaped')
 print('currentint%d loader/value negatives,7 SHA corruptions and9 observed process/output faults detect with passing controls'%count)
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('currentint controls: FAIL: '+str(e))
