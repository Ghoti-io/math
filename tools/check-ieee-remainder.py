#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Mandatory exact-reference integrity, populations and actual probe accounting."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from ieee_remainder_reference import answer,population,bits,reference_hashes,self_check,coverage
PROVENANCE='# Pinned oracle: ieee_remainder MPFR 4.2.2 gmpy2 2.3.2'
EXPECTED={'ieee_remainder-special.hash': '89908544037f9c4847bca9a14e5cafd113fd86cdd4f90dcc0ca6558619dd7e1f', 'remainder-special.corpus': 'cd32a59cd4153d9ca24d098bcc64e7f8a716210af0f79e9141372a4b8be7f090', 'remainder.corpus': '71c1bbbe0b626c9a02ca4f3ee6fe08e6fd892c1b110a369fd5e3a9b03b783acb', 'remainder_quotient.corpus': 'e8c1798f61467c887c3c195aa3c7474c49643757112399c79b33eef8edf7bb5c', 'remainderf-special.corpus': 'b3b0fe70497dc1df865d89a6f6d3d3d2f8b61d2236f484208013457315e4fb05', 'remainderf.corpus': 'f6e791339d4f2916e78c515703438438a52db885084c0cfab8c2256b7253d1e2', 'remainderf_quotient.corpus': '58aad8e4ae7e1a1727801fd33edd2aeba9f509f64607dc3ee0c094f8f78cd233'}
FILES={'remainder-special.corpus','remainderf-special.corpus','remainder.corpus','remainderf.corpus','remainder_quotient.corpus','remainderf_quotient.corpus','ieee_remainder-special.hash'}

LIMITS={name:(4096 if name.endswith('.hash') else 20000000 if name=='remainderf-special.corpus' else 32000000) for name in FILES}
def bounded(file):
 limit=LIMITS[file.name]
 if file.stat().st_size>limit:raise RuntimeError('reference payload exceeds bounded size: '+file.name)
 with file.open('rb') as stream:data=stream.read(limit+1)
 if len(data)>limit:raise RuntimeError('reference payload exceeds bounded size: '+file.name)
 return data

def signal_integer(raw,width):
 p=52 if width==64 else 23;eb=11 if width==64 else 8;a=raw&((1<<(width-1))-1)
 return a>(((1<<eb)-1)<<p) and not a&(1<<(p-1))
def quiet_integer(raw,width):
 p=52 if width==64 else 23;eb=11 if width==64 else 8;a=raw&((1<<(width-1))-1)
 return a>(((1<<eb)-1)<<p) and bool(a&(1<<(p-1)))
def widened_integer(raw,width):
 if width==64:return 0x7ff8000000000000 if raw&0x7fffffffffffffff>0x7ff0000000000000 else raw
 sign=(raw&0x80000000)<<32;field=(raw>>23)&255;fraction=raw&0x7fffff
 if field==255:return 0x7ff8000000000000 if fraction else sign|0x7ff0000000000000
 if field:return sign|((field+896)<<52)|(fraction<<29)
 if not fraction:return sign
 top=fraction.bit_length()-1
 return sign|((top+874)<<52)|((fraction-(1<<top))<<(52-top))

def verify(root,fresh=False,seed=None,count=None,report=False):
 self_check()
 if set(EXPECTED)!=FILES:raise RuntimeError('incomplete mandatory reference checksum set')
 if not fresh:
  for name,digest in EXPECTED.items():
   if hashlib.sha256(bounded(root/name)).hexdigest()!=digest:raise RuntimeError('complete reference checksum: '+name)
 manifests=[]
 for width,name in [(64,'remainder'),(32,'remainderf')]:
  payload=bounded(root/(name+'-special.corpus'))
  if len(payload)>40000000 or not payload.endswith(b'\n') or b'\0' in payload or b'\r' in payload:raise RuntimeError('raw reference size/line encoding')
  lines=payload.decode('ascii').splitlines();prefix=PROVENANCE+'\n# function '+name+'\n'
  if len(lines)<5 or '\n'.join(lines[:2])+'\n'!=prefix or lines[3]!='# x y result quotient invalid':raise RuntimeError('raw reference provenance/schema')
  m=re.fullmatch(r'# seed (0|[1-9][0-9]{0,19}) count (0|[1-9][0-9]{0,4}) fresh (True|False) entries ([1-9][0-9]{0,5})',lines[2])
  if not m:raise RuntimeError('raw reference metadata')
  actual_seed,actual_count=int(m[1]),int(m[2]);entries=int(m[4])
  if actual_seed>=1<<64 or actual_count>50000 or entries>500000 or (fresh and (m[3]!='True' or (actual_seed,actual_count)!=(seed,count))):raise RuntimeError('requested seed/count/fresh metadata differs')
  expected_pairs=population(width,actual_seed,actual_count);rows=[];n=width//4
  for line in lines[4:]:
   mrow=re.fullmatch(r'([0-9a-f]{%d}) ([0-9a-f]{%d}) ([0-9a-f]{%d}) (-?[0-9]{1,3}) ([01])'%(n,n,n),line)
   if not mrow:raise RuntimeError('raw row schema')
   x,y,r=map(lambda s:int(s,16),mrow.groups()[:3]);q,invalid=int(mrow[4]),int(mrow[5])
   if str(q)!=mrow[4] or not -127<=q<=127 or (r,q,invalid)!=answer(x,y,width):raise RuntimeError('exact rational remainder/quotient certificate')
   rows.append((x,y,r,q,invalid))
  if len(rows)!=entries or [(x,y) for x,y,*_ in rows]!=expected_pairs:raise RuntimeError('complete ordered population mismatch')
  coverage(rows,width)
  header=prefix+lines[2]+'\n';generic=[(widened_integer(x,width),widened_integer(y,width),widened_integer(r,width),bits(float(q),64)) for x,y,r,q,f in rows if width==64 or not(signal_integer(x,width) or signal_integer(y,width))]
  for index,suffix in [(2,''),(3,'_quotient')]:
   expected=header.replace('entries %d'%entries,'entries %d'%len(generic))+''.join('%016x %016x %016x\n'%(v[0],v[1],v[index]) for v in generic)
   if bounded(root/(name+suffix+'.corpus'))!=expected.encode():raise RuntimeError('complete widened rows/exclusions differ: '+name+suffix)
  if report:
   signaling_pairs=sum(bool(signal_integer(x,width) or signal_integer(y,width)) for x,y,*_ in rows)
   quiet_pairs=sum(bool(quiet_integer(x,width) or quiet_integer(y,width)) and not(signal_integer(x,width) or signal_integer(y,width)) for x,y,*_ in rows)
   print('%s: raw %d generic %d signaling-pairs %d excluded %d quiet-only-pairs included %d'%(name,len(rows),len(generic),signaling_pairs,len(rows)-len(generic),quiet_pairs))
  raw,state,nearest,calls=reference_hashes(rows,width);manifests.append('ieeeraw %s %016x %d %d %016x %d\n'%(name,raw,entries,nearest,state,calls))
 manifest=''.join(manifests)
 if bounded(root/'ieee_remainder-special.hash')!=manifest.encode():raise RuntimeError('independent raw/state hash/count manifest differs')
 return manifest

def run(probe,root,manifest):
 p=subprocess.run([str(probe),str(root)],capture_output=True,text=True,timeout=120)
 expected=''.join(line+' from '+str(root)+'\n' for line in manifest.splitlines())
 if p.returncode or p.stderr or p.stdout!=expected:raise RuntimeError('actual raw output hash/count/order/path/status differs: '+p.stdout[-500:]+p.stderr[-500:])

def unit_check(unit,root,manifest):
 env=os.environ.copy();env['GMATH_IEEE_REMAINDER_CORPUS_DIR']=str(root)
 args=[str(unit),'--gtest_filter=IeeeRemainder.Pinned*','--gtest_shuffle=0','--gtest_brief=1']
 p=subprocess.run(args,env=env,capture_output=True,text=True,timeout=120)
 actual=''.join(x+'\n' for x in p.stdout.splitlines() if x.startswith('ieeeraw '))
 expected=''.join(line+' from '+str(root)+'\n' for line in manifest.splitlines())
 if p.returncode or actual!=expected:raise RuntimeError('unit ignored requested corpus path/population/hash: '+p.stdout[-1000:]+p.stderr[-1000:])
 with tempfile.TemporaryDirectory(prefix='gmath-ieee-empty-') as d:
  env['GMATH_IEEE_REMAINDER_CORPUS_DIR']=d;q=subprocess.run(args,env=env,capture_output=True,text=True,timeout=30)
  if q.returncode!=1 or 'IEEE remainder raw/state/reference failure' not in q.stderr:raise RuntimeError('unit ignored empty requested directory')

def loader_controls(probe):
 with tempfile.TemporaryDirectory(prefix='gmath-ieee-loader-') as d:
  root=Path(d)
  for width,name in [(64,'remainder'),(32,'remainderf')]:
   n=width//4;row=('0'*n+' '+'0'*(n-1)+'1 '+'0'*n+' 0 0\n');header=PROVENANCE+'\n# function '+name+'\n# seed 0 count 0 fresh True entries 1\n# x y result quotient invalid\n';file=root/(name+'-special.corpus')
   def call(text,valid=False):
    file.write_bytes(text.encode());p=subprocess.run([str(probe),str(root),str(width)],capture_output=True,text=True,timeout=15)
    if p.returncode!=(0 if valid else 1) or (not valid and 'IEEE remainder raw/state/reference failure' not in p.stderr):raise RuntimeError('native loader fixture escaped/wrong failure')
   call(header+row,True)
   cases=['',header,header.replace('MPFR','MPRF')+row,header.replace('function '+name,'function bad')+row,header.replace('entries 1','entries 2')+row,header+row+row,header+row+'bad\n',header+row+'\0\n',header+row.rstrip(),header+'0'*300+'\n',header.replace('seed 0','seed -1')+row,header.replace('seed 0','seed 18446744073709551616')+row,header.replace('count 0','count 50001')+row,header.replace('entries 1','entries 500001')+row,header.replace('seed 0','seed 00')+row,header.replace('count 0 fresh','count 0fresh')+row,header+row.replace(' 0 0\n',' -0 0\n'),header+row.replace(' 0 0\n',' 128 0\n'),header+row.replace(' 0 0\n',' 0 2\n'),header+row.replace(' 0 0\n',' 0 1\n'),header+row.replace(' 0 0\n',' --1 0\n')]
   for text in cases:call(text)
   print(name+': valid native loader and '+str(len(cases))+' rejection fixtures pass')

def output_controls(root,manifest):
 expected=''.join(line+' from '+str(root)+'\n' for line in manifest.splitlines())
 with tempfile.TemporaryDirectory(prefix='gmath-ieee-output-') as d:
  script=Path(d)/'probe'
  def check(text,status=0,stderr='',valid=False):
   script.write_text('#!'+sys.executable+'\nimport sys\nsys.stdout.write('+repr(text)+')\nsys.stderr.write('+repr(stderr)+')\nsys.exit('+str(status)+')\n');script.chmod(0o700)
   try:run(script,root,manifest)
   except RuntimeError:
    if valid:raise
   else:
    if not valid:raise RuntimeError('output fault escaped')
  check(expected,valid=True)
  lines=expected.splitlines(keepends=True)
  cases=['',expected+lines[0],''.join(reversed(lines)),lines[0],expected.replace(str(root),'wrong-directory')]
  for column in range(2,7):
   words=lines[0].split();words[column]='0000000000000000' if column in (2,5) else str(int(words[column])+1);cases.append(' '.join(words)+'\n'+lines[1])
  for text in cases:check(text)
  check(expected,status=1);check(expected,stderr='unexpected error')
 print('IEEE remainder: valid recording process and twelve output/accounting faults pass')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--corpus',type=Path,default=Path('tests/corpus'));p.add_argument('--probe',type=Path,required=True);p.add_argument('--fresh',action='store_true');p.add_argument('--seed',type=int);p.add_argument('--count',type=int);p.add_argument('--controls',action='store_true');p.add_argument('--unit',type=Path);a=p.parse_args()
 if a.fresh and (a.seed is None or a.count is None):p.error('fresh requires seed/count')
 manifest=verify(a.corpus,a.fresh,a.seed,a.count,True);run(a.probe,a.corpus,manifest)
 if a.unit:unit_check(a.unit,a.corpus,manifest)
 if a.controls:loader_controls(a.probe);output_controls(a.corpus,manifest)
 print('IEEE remainder complete SHA/rational/population/widening/raw/state checks pass')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('IEEE remainder check: FAIL: '+str(e))
