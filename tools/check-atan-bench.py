#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Certify emitted corpus-member workloads and calibrate timed guards."""
import argparse
import importlib.util
from itertools import zip_longest
import os
from pathlib import Path
import re
import shlex
import subprocess

spec=importlib.util.spec_from_file_location('atan_cells',Path(__file__).with_name('check-atan.py'))
cells=importlib.util.module_from_spec(spec);spec.loader.exec_module(cells)
RANGES=['ordinary','direct','table','tiny-normal','subnormal','wide','zero','infinity','qNaN','sNaN','reciprocal']

def member(name,x):
 a=x&((1<<63)-1)
 if name=='ordinary':return 0x3fd0000000000000<=a<0x4010000000000000
 if name=='direct':return 0x3eb0000000000000<=a<0x3fc0000000000000
 if name=='table':return 0x3fc0000000000000<=a<0x3ff0000000000000
 if name=='tiny-normal':return 0x0010000000000000<=a<0x3e10000000000000
 if name=='subnormal':return 0<a<0x0010000000000000
 if name=='wide':return 0x4350000000000000<=a<0x7ff0000000000000
 if name=='zero':return a==0
 if name=='infinity':return a==0x7ff0000000000000
 if name=='qNaN':return a>0x7ff0000000000000 and bool(a&(1<<51))
 if name=='sNaN':return a>0x7ff0000000000000 and not a&(1<<51)
 if name=='reciprocal':return 0x4010000000000000<=a<0x4350000000000000
 raise RuntimeError('unknown atan benchmark range')

def selections(directory=Path('tests/corpus')):
 data,_,_=cells.check(directory)
 rows=[tuple(int(v,16) for v in line.split()[:3])+(int(line.split()[3]),) for line in data['atan-special.corpus'].splitlines()[4:]]
 result={}
 for name in RANGES:
  selected=[row for row in rows if member(name,row[0])]
  positive=[row for row in selected if not row[0]>>63];negative=[row for row in selected if row[0]>>63]
  result[name]=[row for pair in zip_longest(positive,negative) for row in pair if row is not None]
 return result

def certify(binary,directory=Path('tests/corpus')):
 sources=selections(directory)
 r=subprocess.run([str(binary.resolve()),str(directory),'--references'],capture_output=True,text=True,timeout=180)
 if r.returncode or r.stderr:raise RuntimeError('atan reference producer failed')
 lines=r.stdout.splitlines();cursor=0
 for name in RANGES:
  source=sources[name]
  if not source or cursor>=len(lines) or lines[cursor]!='atan.workload %s source %d used %d'%(name,len(source),min(4096,len(source))):raise RuntimeError('atan range population differs')
  cursor+=1
  for index in range(4096):
   x,target,error,flag=source[index%len(source)]
   wanted='atan.reference %s %d %016x %016x %08x %d'%(name,index,x,target,error,flag)
   if cursor>=len(lines) or lines[cursor]!=wanted:raise RuntimeError('atan independent emitted input/target/cell selection differs')
   cursor+=1
 if cursor!=len(lines):raise RuntimeError('atan extra emitted references')
 return 45056

def records(text,pairs=401):
 lines=text.splitlines()
 if len(lines)!=35+22*pairs or lines[0]!='8 paired warmups;%d alternating pairs4096; nearest only; corpus member workloads'%pairs or not lines[1].startswith('atan.identity compiler ') or not lines[1].endswith('; comparison host-libm; host errno/NaN payload unpromised'):raise RuntimeError('atan benchmark identity/count differs')
 result=[];cursor=2;sources=selections()
 for name in RANGES:
  count=len(sources[name])
  if lines[cursor]!='atan.workload %s source %d used %d'%(name,count,min(4096,count)):raise RuntimeError('atan workload summary differs')
  cursor+=1
  for entry in ['clean','UF/IX']:
   samples=[]
   for index in range(pairs):
    m=re.fullmatch('atan.pair '+re.escape(name)+' '+entry+' '+str(index)+r' own ([1-9][0-9]*) host ([1-9][0-9]*)',lines[cursor]);cursor+=1
    if not m:raise RuntimeError('atan raw pair order/count differs')
    samples.append(tuple(map(int,m.groups())))
   m=re.fullmatch(r'atan '+re.escape(name)+' '+entry+r' own ([0-9.]+) host ([0-9.]+) ratio ([0-9.]+) ([0-9.]+) ([0-9.]+)',lines[cursor]);cursor+=1
   if not m:raise RuntimeError('atan timing row missing/duplicated')
   own,host,p10,median,p90=map(float,m.groups())
   if not(own>0 and host>0 and 0<p10<=median<=p90):raise RuntimeError('atan timing quantiles invalid')
   ratios=sorted(a/b for a,b in samples)
   rebuilt=[sorted(a for a,b in samples)[pairs//2]/4096,sorted(b for a,b in samples)[pairs//2]/4096,ratios[pairs//10],ratios[pairs//2],ratios[pairs*9//10]]
   if any(abs(a-b)>0.00000051 for a,b in zip([own,host,p10,median,p90],rebuilt)):raise RuntimeError('atan aggregate differs from retained integer pairs')
   result.append(dict(range=name,entry=entry,own_ns=own,host_ns=host,ratio_p10=p10,ratio_median=median,ratio_p90=p90,pairs=samples,source_count=count,used_count=min(4096,count)))
 return lines[1],result

def controls():
 e=os.environ;work=Path(e['BENCH_WORK']);work.mkdir(parents=True,exist_ok=True)
 source=Path('tools/bench-atan.c').read_text()
 def build(text,name):
  path=work/(name+'.c');path.write_text(text.replace('"../tests/atan_corpus.h"','"'+str(Path('tests/atan_corpus.h').resolve())+'"'))
  binary=work/name
  cmd=shlex.split(e['BENCH_CC'])+shlex.split(e['BENCH_CFLAGS'])+['-DGMATH_ATAN_BENCH_PAIRS=7',str(path),e['BENCH_ARCHIVE']]+shlex.split(e['BENCH_LDFLAGS'])+['-lm','-o',str(binary)]
  r=subprocess.run(cmd,capture_output=True,text=True,timeout=180);(work/(name+'-compile.log')).write_text(r.stdout+r.stderr)
  if r.returncode:raise RuntimeError('atan benchmark control did not compile: '+name)
  return binary
 binary=build(source,'control');certify(binary)
 r=subprocess.run([str(binary.resolve()),'tests/corpus'],capture_output=True,text=True,timeout=180);(work/'control.log').write_text(r.stdout+r.stderr)
 if r.returncode or r.stderr:raise RuntimeError('atan reduced benchmark positive failed')
 control_text=r.stdout;records(control_text,7)
 plants={
  'timed-errno':('sink^=hash;','sink^=hash;if(!host) {errno=901;}','timed state mismatch'),
  'timed-invalid':('sink^=hash;','sink^=hash;if(!host) {feraiseexcept(FE_INVALID);}','timed state mismatch'),
  'timed-mode':('sink^=hash;','sink^=hash;if(!host) {fesetround(FE_UPWARD);}','timed state mismatch'),
  'timed-zero-sign':('hash=gmath_fnv_u64(hash,call(i));','hash=gmath_fnv_u64(hash,call(i)^((!host&&!input[i].x)?UINT64_C(0x8000000000000000):0));','timed checksum mismatch'),
  'timed-result':('hash=gmath_fnv_u64(hash,call(i));','hash=gmath_fnv_u64(hash,call(i)^(!host?1u:0u));','timed checksum mismatch')}
 for name,(old,new,message) in plants.items():
  if source.count(old)!=1:raise RuntimeError('atan benchmark plant anchor differs')
  binary=build(source.replace(old,new),name);r=subprocess.run([str(binary.resolve()),'tests/corpus'],capture_output=True,text=True,timeout=180)
  (work/(name+'.log')).write_text(r.stdout+r.stderr)
  if r.returncode!=2 or message not in r.stderr:raise RuntimeError('atan timed defect escaped intended guard: '+name)
 for name,old,new in [('reference-target','input[i].target,input[i].error,input[i].flags);','input[i].target^1u,input[i].error,input[i].flags);'),('range','a>=UINT64_C(0x3fd0000000000000)','a>=UINT64_C(0x3fe0000000000000)')]:
  if source.count(old)!=1:raise RuntimeError('atan reference control anchor differs')
  binary=build(source.replace(old,new),name)
  try:certify(binary)
  except RuntimeError:pass
  else:raise RuntimeError('atan reference selection fault escaped')
 for old,new in [('source ', 'source 9'),('atan.pair ordinary clean 0 ','atan.pair ordinary clean 1 ')]:
  corrupted=control_text.replace(old,new,1)
  try:records(corrupted,7)
  except RuntimeError:pass
  else:raise RuntimeError('atan timing accounting fault escaped')
 print('atan45056 emitted cells certified; reduced7-pair positive and5actual timed/2reference faults detect; no final timing evidence')

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binary',type=Path);p.add_argument('--controls',action='store_true');a=p.parse_args()
 if a.controls:controls()
 elif a.binary:print('atan emitted reference cells certified:',certify(a.binary))
 else:p.error('select --binary or --controls')
