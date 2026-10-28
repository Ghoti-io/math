#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Observed positive-difference loader/byte/process controls, not timing evidence."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import mock
spec=importlib.util.spec_from_file_location('fdim_checker',Path(__file__).with_name('check-positive-difference.py'));checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--numeric',type=Path,required=True);a=p.parse_args();binary=str(a.probe.resolve())
 data=checker.check(Path('tests/corpus'));checker.probe([binary],Path('tests/corpus'),data)
 with tempfile.TemporaryDirectory(prefix='fdim-controls-') as t:
  root=Path(t)
  for name,text in data.items():(root/name).write_text(text)
  loader=value_faults=0
  for width in [64,32]:
   name='fdim%d-special.corpus'%width;path=root/name;text=data[name];lines=text.splitlines(True)
   one='3ff0000000000000' if width==64 else '3f800000';zero='0'*(width//4)
   ordinary=next(i for i,line in enumerate(lines[4:],4) if line.split()[:2]==[one,zero])
   faults=[text.replace('Pinned oracle: positive_difference','Pinned oracle: wrong',1),text.replace('# function fdim','# function wrong',1),text.replace('seed 20261028','seed -1',1),text.replace('seed 20261028','seed 4294967296',1),text.replace('count 2000','count 50001',1),text.replace('fresh false','fresh falsehood',1),text.replace('entries '+str(len(lines)-4),'entries 400001',1),text.replace('# x y nearest-result flags','# input wrong',1),''.join(lines[:-1]),''.join(lines[:5]+[lines[4]]+lines[5:]),''.join(lines[:4]+[lines[5],lines[4]]+lines[6:]),text+'\x00hidden\n',text+'x'*600+'\n',text.rstrip('\n'),text+'extra\n',text.replace(lines[4],lines[4].rstrip()+' extra\n',1)]
   for kind in ['uppercase','overwidth','negative-result','bad-flags','count-low','count-high']:
    changed=lines.copy();fields=changed[ordinary].split()
    if kind=='uppercase':fields[0]=fields[0].upper()
    elif kind=='overwidth':fields[0]='0'+fields[0]
    elif kind=='negative-result':fields[2]='%0*x'%(width//4,int(fields[2],16)|(1<<(width-1)))
    elif kind=='bad-flags':fields[3]='3'
    else:changed[2]=changed[2].replace('entries '+str(len(lines)-4),'entries '+str(len(lines)-4+(-1 if kind=='count-low' else 1)))
    if kind not in ['count-low','count-high']:changed[ordinary]=' '.join(fields)+'\n'
    faults.append(''.join(changed))
   for index,changed in enumerate(faults):
    path.write_text(changed);r=subprocess.run([binary,str(root),str(width)],capture_output=True,text=True,timeout=60)
    if r.returncode!=1 or 'positive difference corpus invalid' not in r.stderr:raise RuntimeError('loader/schema fault escaped %d/%d'%(width,index))
    loader+=1
   for column in range(4):
    changed=lines.copy();fields=changed[ordinary].split();fields[column]=('%0*x'%(width//4,int(fields[column],16)^1)) if column<3 else '2';changed[ordinary]=' '.join(fields)+'\n';path.write_text(''.join(changed))
    r=subprocess.run([binary,str(root),str(width)],capture_output=True,text=True,timeout=60)
    if r.returncode!=1 or 'positive difference mismatch' not in r.stderr:raise RuntimeError('real row-field corruption escaped numerical/state layer %d/%d'%(width,column))
    value_faults+=1
   path.write_text(text)
  for name,text in data.items():
   path=root/name;path.write_text(text+'\n')
   try:checker.check(root)
   except RuntimeError as error:
    if 'checksum differs' not in str(error):raise
   else:raise RuntimeError('complete checksum corruption escaped')
   path.write_text(text)
  name=next(iter(checker.EXPECTED));path=root/name
  with path.open('wb') as file:file.truncate(33*1024*1024)
  try:
   with mock.patch.object(Path,'read_bytes',side_effect=RuntimeError('read before size check')):checker.check(root)
  except RuntimeError as error:
   if 'payload exceeds bound' not in str(error):raise
  else:raise RuntimeError('oversize-before-read control escaped')
  path.write_text(data[name])
  good=checker.probe([binary],root,data);script=root/'record.py'
  def record(text,status=0,error=''):
   script.write_text('import sys\nsys.stdout.write('+repr(text)+')\nsys.stderr.write('+repr(error)+')\nsys.exit('+str(status)+')\n')
  record(good);checker.probe([sys.executable,str(script)],root,data)
  first=good.splitlines(True)[0];fields=first.split()
  def change(index,value):
   f=fields.copy();f[index]=value;return good.replace(first,' '.join(f)+'\n',1)
  faults=[good.split('\n',1)[1],good+good,change(2,'0000000000000000'),change(4,str(int(fields[4])+1)),change(6,'0000000000000000'),change(8,str(int(fields[8])-1)),change(10,'ignored'),change(12,'1'),change(14,'0'),change(16,'true'),''.join(reversed(good.splitlines(True)))]
  for text,status,error in [(x,0,'') for x in faults]+[(good,1,''),(good,0,'unexpected')]:
   record(text,status,error)
   try:checker.probe([sys.executable,str(script)],root,data)
   except RuntimeError:pass
   else:raise RuntimeError('observed process/output fault escaped')
  numeric=subprocess.run([str(a.numeric.resolve()),'tests/corpus'],capture_output=True,text=True,timeout=120)
  if numeric.returncode:raise RuntimeError('numeric protocol positive failed')
  checker.numeric_output(numeric.stdout,numeric.stderr)
  first=next(line+'\n' for line in numeric.stdout.splitlines() if '.hash' in line);fields=first.split();bad=' '.join([fields[0],'0000000000000000'])+'\n'
  for stdout,stderr,diagnostic in [(bad+numeric.stdout,'','duplicate generic'),(numeric.stdout,'diagnostic','generic overlay diagnostics'),(numeric.stdout+'unknown\n','','schema differs')]:
   try:checker.numeric_output(stdout,stderr)
   except RuntimeError as error:
    if diagnostic not in str(error):raise
   else:raise RuntimeError('numeric protocol direct fault escaped')
  # Feed the real fresh-overlay path recorded valid output and counterfactual
  # duplicate/stderr processes. Read-only reconstruction is calibrated once;
  # its cached positive result keeps these accounting controls bounded.
  fresh={name:text.replace('fresh false','fresh true') for name,text in data.items()}
  for name,text in fresh.items():(root/name).write_text(text)
  checker.check(root,checker.SEED,checker.COUNT,True,False)
  numeric_script=root/'numeric-record';numeric_script.chmod(0o700) if numeric_script.exists() else None
  def numeric_record(stdout,stderr):
   numeric_script.write_text('#!'+sys.executable+'\nimport sys\nsys.stdout.write('+repr(stdout)+')\nsys.stderr.write('+repr(stderr)+')\n');numeric_script.chmod(0o700)
  numeric_record(numeric.stdout,'')
  with mock.patch.object(checker,'check',return_value=fresh):checker.fresh_controls(Path(binary),None,numeric_script,root,checker.SEED,checker.COUNT)
  for stdout,stderr,diagnostic in [(bad+numeric.stdout,'','duplicate generic'),(numeric.stdout,'diagnostic','generic overlay diagnostics')]:
   numeric_record(stdout,stderr)
   try:
    with mock.patch.object(checker,'check',return_value=fresh):checker.fresh_controls(Path(binary),None,numeric_script,root,checker.SEED,checker.COUNT)
   except RuntimeError as error:
    if diagnostic not in str(error):raise
   else:raise RuntimeError('actual fresh-overlay protocol wiring fault escaped')
  for args in [[],[str(root),'16'],[str(root),'64','extra']]:
   r=subprocess.run([binary]+args,capture_output=True,text=True,timeout=30)
   if r.returncode!=2:raise RuntimeError('command schema fault escaped')
 print('positive difference%d loader/schema negatives,%d real row-field faults,5 SHA corruptions,oversize-before-read,13 observed process/output,3 command and direct/actual-overlay duplicate/diagnostic controls pass'%(loader,value_faults))
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:raise SystemExit('positive difference controls: FAIL: '+str(error))
