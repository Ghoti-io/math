#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Account for an identified actual-prior probe; not a numerical oracle."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from adjacent_baseline import identity_line,load
REVISION='a54cfbacafa735c0bc7fd1a56af869b8877fa501'

def expected(metadata,corpus):
 if metadata['revision']!=REVISION:raise RuntimeError('unexpected prior revision')
 path=corpus/'ieee_remainder-special.hash'
 if path.stat().st_size>4096:raise RuntimeError('oversize raw manifest')
 with path.open('rb') as f:payload=f.read(4097)
 if len(payload)>4096:raise RuntimeError('oversize raw manifest')
 lines=payload.decode('ascii').splitlines(keepends=True)
 if len(lines)!=2:raise RuntimeError('raw manifest record count')
 for name,line in zip(('remainder','remainderf'),lines):
  if re.fullmatch('ieeeraw '+name+r' [0-9a-f]{16} [1-9][0-9]{0,5} [1-9][0-9]{0,6} [0-9a-f]{16} [1-9][0-9]{0,7}\n',line) is None:raise RuntimeError('raw manifest schema')
 return identity_line(metadata,'ieee_remainder')+''.join('ieeeinitial width%d cases23 calls3312\n'%(64 if i==0 else 32)+line.rstrip('\n')+' from '+str(corpus)+'\n' for i,line in enumerate(lines))

def run(command,metadata,corpus):
 wanted=expected(metadata,corpus)
 p=subprocess.run(command+[str(corpus)],capture_output=True,text=True,timeout=120)
 if p.returncode or p.stderr or p.stdout!=wanted:raise RuntimeError('actual-prior identity/result/count/path/status differs')

def calibrate():
 metadata=dict(revision=REVISION,object_sha256='1'*64,flags_sha256='2'*64,compiler_sha256='3'*64)
 with tempfile.TemporaryDirectory(prefix='gmath-ieee-prior-driver-') as d:
  root=Path(d);corpus=root/'corpus';corpus.mkdir();(corpus/'ieee_remainder-special.hash').write_text('ieeeraw remainder 0000000000000001 1 3 0000000000000002 24\nieeeraw remainderf 0000000000000003 1 3 0000000000000004 24\n')
  good=expected(metadata,corpus);program=root/'record.py'
  faults=[good.split('\n',1)[1],good.replace(REVISION,'0'*40),good.replace('1'*64,'9'*64,1),good.replace('2'*64,'9'*64,1),good.replace('3'*64,'9'*64,1),good.replace(' 1 3 ',' 2 3 ',1),good.replace('0000000000000002','0000000000000009'),good.replace(str(corpus),'ignored'),'\n'.join(good.splitlines()[:2])+'\n']
  def script(output,status=0,error=''):
   program.write_text('import sys\nsys.stdout.write('+repr(output)+')\nsys.stderr.write('+repr(error)+')\nsys.exit('+str(status)+')\n')
  script(good);run([sys.executable,str(program)],metadata,corpus)
  for text,status,error in [(x,0,'') for x in faults]+[(good,1,''),(good,0,'unexpected')]:
   script(text,status,error)
   try:run([sys.executable,str(program)],metadata,corpus)
   except RuntimeError as e:
    if str(e)!='actual-prior identity/result/count/path/status differs':raise
   else:raise RuntimeError('driver accounting fault escaped')
 print('IEEE actual-prior driver: valid recording control and11 identity/hash/count/path/process faults pass; not numerical oracle evidence')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('probe',type=Path,nargs='?');p.add_argument('--metadata',type=Path);p.add_argument('--corpus',type=Path,default=Path('tests/corpus'));p.add_argument('--calibrate',action='store_true');a=p.parse_args()
 if a.calibrate:calibrate()
 if a.probe:
  if a.metadata is None:raise RuntimeError('actual-prior metadata required')
  run([str(a.probe.resolve())],load(a.metadata),a.corpus);print('IEEE identified actual-prior raw/state comparison passes')
 elif not a.calibrate:raise RuntimeError('probe or calibration required')
if __name__=='__main__':
 try:main()
 except (OSError,UnicodeError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('IEEE prior driver: FAIL: '+str(e))
