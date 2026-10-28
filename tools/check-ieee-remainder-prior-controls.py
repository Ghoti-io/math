#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Native actual-prior source/state and declared-identity counterfactuals."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from adjacent_baseline import validate,load,digest_file,write_header
REVISION='a54cfbacafa735c0bc7fd1a56af869b8877fa501'
def words(name):return shlex.split(os.environ[name])
def command(args,label,expect=0):
 p=subprocess.run(args,capture_output=True,text=True,timeout=120);(work/(label+'.log')).write_text(p.stdout+p.stderr)
 if p.returncode!=expect:raise RuntimeError(label+': unexpected status '+str(p.returncode))
 return p

def main():
 metadata=load(os.environ['NATIVE_METADATA']);prior=Path(os.environ['NATIVE_REFERENCE']);flags=os.environ['NATIVE_LIB_CFLAGS'];cc=os.environ['NATIVE_CC'];corpus=os.environ.get('NATIVE_CORPUS','tests/corpus')
 if metadata['revision']!=REVISION:raise RuntimeError('unexpected prior revision')
 validate(metadata,prior,flags,cc)
 for name,changed in [('object',{**metadata,'object_sha256':'0'*64}),('flags',{**metadata,'flags_sha256':'0'*64}),('compiler',{**metadata,'compiler_sha256':'0'*64})]:
  try:validate(changed,prior,flags,cc)
  except RuntimeError as e:
   if ('baseline library flags' if name=='flags' else 'baseline '+name) not in str(e):raise
  else:raise RuntimeError(name+' identity defect escaped')
 for name,actual_flags,actual_cc in [('actual-flags',flags+' -DGMATH_BASELINE_CONTEXT_CONTROL=1',cc),('actual-driver',flags,cc+' -pipe')]:
  try:validate(metadata,prior,actual_flags,actual_cc)
  except RuntimeError as e:
   if ('baseline library flags' if name=='actual-flags' else 'baseline compiler') not in str(e):raise
  else:raise RuntimeError(name+' invocation identity defect escaped')
 source=subprocess.check_output(['git','show',REVISION+':src/elementary/ieee_remainder.c'],timeout=30).decode();helper=subprocess.check_output(['git','show',REVISION+':src/elementary/elem_common.h'],timeout=30)
 if helper!=Path('src/elementary/elem_common.h').read_bytes():raise RuntimeError('prior helper changed')
 (work/'elem_common.h').write_bytes(helper)
 faults=[('control',source,(0,0)),('result',source.replace('return sign|irq_pack(r,e,p,bias);','(void)sign;(void)e;(void)r;return xb;'),(1,1)),('nan-payload',source.replace('return inf|quiet;','return inf|quiet|1u;'),(1,1)),('quotient',source.replace('if(quo)*quo=((xb^yb)&sign_bit)?-(int)q:(int)q;','if(quo){unsigned changed=q?((unsigned)q^8u):0u;*quo=((xb^yb)&sign_bit)?-(int)changed:(int)changed;}'),(1,1)),('invalid',source.replace('(void)gmath_invalid();','(void)0;',1),(1,1)),('null-state',source.replace('uint64_t sign_bit=','if(!quo){errno=732;}uint64_t sign_bit='),(1,1)),('float-only',source.replace('return sign|irq_pack(r,e,p,bias);','return p==23?sign:sign|irq_pack(r,e,p,bias);'),(0,1))]
 for label,text,expected in faults:
  if label!='control' and text==source:raise RuntimeError('missing source mutation anchor')
  file=work/(label+'.c');obj=work/(label+'.o');file.write_text('#include <errno.h>\n'+text)
  command(words('NATIVE_CC')+words('NATIVE_LIB_CFLAGS')+['-c',str(file),'-o',str(obj)],label+'-compile')
  symbols=subprocess.check_output(shlex.split(os.environ.get('NATIVE_NM','nm'))+['-g','--defined-only',str(obj)],text=True,timeout=30).splitlines();args=[]
  for fn in ['remainder','remainderf','remquo','remquof']:
   names=[line.split()[-1] for line in symbols if line.split()[-1].endswith('_gmath_'+fn)]
   if len(names)!=1:raise RuntimeError('unexpected prior source symbols')
   args+=['--redefine-sym',names[0]+'=gmath_ieee_prior_'+fn]
  command(shlex.split(os.environ.get('NATIVE_OBJCOPY','objcopy'))+args+[str(obj)],label+'-rename')
  actual={**metadata,'object_sha256':digest_file(obj)};header=work/(label+'.h');write_header(header,actual,'ieee_remainder');binary=work/(label+'-probe')
  command(words('NATIVE_CC')+words('NATIVE_CFLAGS')+['-include',str(header),'-DGMATH_IEEE_REMAINDER_PRIOR','tools/probe-ieee-remainder.c',os.environ['NATIVE_LIBRARY'],str(obj)]+words('NATIVE_LDFLAGS')+['-lm','-o',str(binary)],label+'-link')
  for width,status in zip(['64','32'],expected):
   result=command([str(binary),corpus,width],label+'-'+width,status)
   if status and 'IEEE actual-prior mismatch' not in result.stderr:raise RuntimeError('fault failed outside actual-prior comparison')
  bench=work/(label+'-bench')
  command(words('NATIVE_CC')+words('NATIVE_CFLAGS')+['-include',str(header),'-DGMATH_IEEE_REMAINDER_PRIOR','tools/bench-ieee-remainder.c',os.environ['NATIVE_LIBRARY'],str(obj)]+words('NATIVE_LDFLAGS')+['-lm','-o',str(bench)],label+'-bench-link')
  result=command([str(bench),'--validate-only'],label+'-bench',0 if label=='control' else 2)
  diagnostic='actual-prior full quotient' if label=='quotient' else 'actual-prior exact bits' if label=='nan-payload' else 'actual-prior'
  if label!='control' and diagnostic not in result.stderr:raise RuntimeError('benchmark fault failed outside intended actual-prior comparison')
 print('IEEE native prior controls: valid probe/benchmark, six actual numerical/state defects, format isolation, three metadata and two actual-invocation identity defects pass')
if __name__=='__main__':
 work=Path(os.environ['NATIVE_WORK']);work.mkdir(parents=True,exist_ok=True)
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:raise SystemExit('IEEE native prior controls: FAIL: '+str(e))
