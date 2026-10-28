#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""All-result-set overlays and real supplemental omission/corruption controls."""
import argparse
from pathlib import Path
import subprocess
import re
import sys
import tempfile
from ieee_remainder_reference import FNV_BASIS,fnv
DATA={'remainder':'remainder','remainderf':'remainderf','remquo':'remainder','remquof':'remainderf','remquo_quotient':'remainder_quotient','remquof_quotient':'remainderf_quotient'}

def bounded_text(file,limit=32000000):
 if file.stat().st_size>limit:raise RuntimeError('numeric payload exceeds bounded size')
 with file.open('rb') as stream:data=stream.read(limit+1)
 if len(data)>limit:raise RuntimeError('numeric payload exceeds bounded size')
 return data.decode('ascii')

def invoke(probe,corpus,manifest):
 p=subprocess.run(['sh','tools/check-corpus-hash.sh',str(probe),str(corpus),str(manifest)],capture_output=True,text=True,timeout=120)
 return p

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--corpus',type=Path,default=Path('tests/corpus'));p.add_argument('--controls',action='store_true');a=p.parse_args()
 with tempfile.TemporaryDirectory(prefix='gmath-ieee-numeric-') as d:
  stage=Path(d);overlay=stage/'corpus';overlay.mkdir();updates={}
  for file in Path('tests/corpus').iterdir():
   if file.is_file():(overlay/file.name).symlink_to(file.resolve())
  for corpus in set(DATA.values()):
   name=corpus+'.corpus';(overlay/name).unlink(missing_ok=True);(overlay/name).symlink_to((a.corpus/name).resolve())
   count=0;h=FNV_BASIS
   for line in bounded_text(a.corpus/name).splitlines():
    if line.startswith('#'):continue
    fields=line.split()
    if not re.fullmatch(r'[0-9a-f]{16} [0-9a-f]{16} [0-9a-f]{16}',line):raise RuntimeError('generic exact corpus row schema')
    h=fnv(h,int(fields[2],16));count+=1
   for function,path in DATA.items():
    if path==corpus:updates[function]='fn %s %016x %d\n'%(function,h,count)
  original=bounded_text(Path('tests/corpus/trig.hash'),65536).splitlines(keepends=True);seen=set();lines=[]
  for line in original:
   words=line.split()
   if words and words[0]=='fn' and words[1] in DATA:lines.append(updates[words[1]]);seen.add(words[1])
   else:lines.append(line)
  if seen!=set(DATA):raise RuntimeError('missing supplemental function manifest entries')
  manifest=stage/'fresh.hash';manifest.write_text(''.join(lines))
  r=invoke(a.probe.resolve(),overlay,manifest)
  if r.returncode:raise RuntimeError('real fresh numeric overlay failed: '+r.stdout+r.stderr)
  print(r.stdout,end='')
  if a.controls:
   observed=subprocess.run([str(a.probe.resolve()),'tests/corpus'],capture_output=True,text=True,timeout=120)
   if observed.returncode or observed.stderr:raise RuntimeError('actual numerical control process failed')
   fake=stage/'probe'
   def write(text):fake.write_text('#!'+sys.executable+'\nimport sys\nsys.stdout.write('+repr(text)+')\n');fake.chmod(0o700)
   write(observed.stdout);control=invoke(fake,Path('tests/corpus'),Path('tests/corpus/trig.hash'))
   if control.returncode:raise RuntimeError('recording numerical control failed')
   for function in DATA:
    prefix='math.'+function+'.';omitted=''.join(line+'\n' for line in observed.stdout.splitlines() if not line.startswith(prefix));write(omitted)
    bad=invoke(fake,Path('tests/corpus'),Path('tests/corpus/trig.hash'))
    if bad.returncode!=1 or 'per-function name lists differ' not in bad.stderr:raise RuntimeError('actual supplemental omission guard escaped '+function)
    old=next(line for line in observed.stdout.splitlines() if line.startswith(prefix+'hash '));write(observed.stdout.replace(old,prefix+'hash 0000000000000000'))
    bad=invoke(fake,Path('tests/corpus'),Path('tests/corpus/trig.hash'))
    if bad.returncode!=1 or 'FAIL: '+function+':' not in bad.stderr:raise RuntimeError('actual supplemental hash guard escaped '+function)
   print('IEEE remainder: six actual supplemental hash corruptions and six omissions detect; valid recording control passes')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('IEEE remainder numeric: FAIL: '+str(e))
