#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Actual unary loader/value/SHA/output/fresh-accounting counterfactuals.

Observed-output subprocesses calibrate accounting, not numerical oracles.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--unit',type=Path,required=True);p.add_argument('--numeric',type=Path,required=True);a=p.parse_args()
 e=os.environ;work=Path(e['CONTROL_WORK']);work.mkdir(parents=True,exist_ok=True);records=[]
 (work/'complete.json').unlink(missing_ok=True)
 spec=importlib.util.spec_from_file_location('atan_check',Path(__file__).with_name('check-atan.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 def run(cmd,label,want=0,env=None,timeout=180):
  start=time.time();r=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,env=env);(work/(label+'.log')).write_text(r.stdout+r.stderr);records.append(dict(label=label,command=cmd,returncode=r.returncode,elapsed_seconds=time.time()-start));(work/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
  if r.returncode!=want:raise RuntimeError(label+' actual status '+str(r.returncode)+' expected '+str(want)+' '+r.stderr[-400:])
  return r
 root=Path('tests/corpus');data,rows,generic=m.check(root);positive,compat=m.probe(a.probe,root,data,rows,generic,m.SEED,m.COUNT,False,True)
 (work/'raw-positive.log').write_text(positive)
 def unit(directory,label,want):
  env=dict(e,GMATH_ATAN_CORPUS_DIR=str(directory));result=run([str(a.unit.resolve()),'--gtest_filter=Atan.PinnedCorpusAndCallerState','--gtest_brief=1'],label,want,env)
  if want and 'atan corpus invalid/accuracy/state failure' not in result.stderr:raise RuntimeError('atan unit negative failed outside loader/value layer')
 unit(root,'unit-control',0)
 raw=data['atan-special.corpus'];lines=raw.splitlines(keepends=True)
 variants={}
 def replace(label,old,new):
  if raw.count(old)!=1:raise RuntimeError('atan fixture anchor differs '+label)
  variants[label]=raw.replace(old,new,1)
 variants['empty']='';variants['provenance']=raw.replace('MPFR 4.2.2','MPFR 4.2.1',1);variants['function']=raw.replace('# function atan64','# function atanf',1)
 replace('seed-negative','seed 20261028','seed -1');replace('seed-overflow','seed 20261028','seed 18446744073709551616');replace('seed-leading-zero','seed 20261028','seed 020261028')
 replace('count-overflow','count 2000','count 18446744073709551616');replace('count-limit','count 2000','count 50001');replace('count-negative','count 2000','count -1')
 replace('entries-zero','entries 28382','entries 0');replace('entries-limit','entries 28382','entries 100001');replace('entries-overflow','entries 28382','entries 18446744073709551616');replace('entries-leading-zero','entries 28382','entries 028382')
 replace('entries-short','entries 28382','entries 28381');replace('entries-long','entries 28382','entries 28383');replace('fresh-token','fresh false','fresh maybe');replace('meta-extra','entries 28382\n','entries 28382 extra\n')
 variants['nul-header']=raw.replace('# function','\0# function',1);variants['nul-row']=''.join(lines[:4])+lines[4].replace(' ', '\0',1)+''.join(lines[5:]);variants['nul-tail']=raw+'\0\n';variants['crlf']=raw.replace('\n','\r\n');variants['partial-final']=raw[:-1];variants['extra-blank']=raw+'\n'
 variants['duplicate']=''.join(lines[:5])+lines[4]+''.join(lines[5:]);variants['unordered']=''.join(lines[:4])+lines[5]+lines[4]+''.join(lines[6:]);variants['short-hex']=''.join(lines[:4])+lines[4][1:]+''.join(lines[5:]);variants['signed-hex']=''.join(lines[:4])+'-'+lines[4][1:]+''.join(lines[5:]);variants['upper-hex']=''.join(lines[:4])+lines[4].replace('0','A',1)+''.join(lines[5:]);variants['flag']=raw.replace(lines[4],lines[4][:-2]+'8\n',1);variants['overlong-row']=''.join(lines[:4])+'0'*300+'\n'+''.join(lines[5:])
 # Semantic shape rejects and one parse-valid general numerical-cell defect.
 def changed_row(predicate,mutate):
  copy=lines[:]
  for i,line in enumerate(copy[4:],4):
   fields=line.split();x=int(fields[0],16)
   if predicate(x):copy[i]=' '.join(mutate(fields))+'\n';return ''.join(copy)
  raise RuntimeError('atan semantic fixture has no witness')
 variants['quiet-target']=changed_row(lambda x:x==0x7ff8000000000000,lambda f:[f[0],'7ff8000000000001',f[2],f[3]])
 variants['zero-sign']=changed_row(lambda x:x==0x8000000000000000,lambda f:[f[0],'0000000000000000',f[2],f[3]])
 variants['large-target']=changed_row(lambda x:x==0x4350000000000000,lambda f:[f[0],'3ff921fb54442d19',f[2],f[3]])
 variants['error-nan']=changed_row(lambda x:x==0x3ff0000000000000,lambda f:[f[0],f[1],'7fc00000',f[3]])
 variants['normal-underflow-class']=changed_row(lambda x:x==0x0010000000000000,lambda f:[f[0],f[1],f[2],'6'])
 wrong=changed_row(lambda x:x==0x3ff0000000000000,lambda f:[f[0],'%016x'%(int(f[1],16)+16),f[2],f[3]])
 variants['general-cell']=wrong
 for label,content in variants.items():
  with tempfile.TemporaryDirectory(prefix='atan-loader-',dir=work) as t:
   directory=Path(t);(directory/'atan-special.corpus').write_bytes(content.encode('ascii'))
   result=run([str(a.probe.resolve()),str(directory)],'C-'+label,1)
   if 'atan corpus invalid/accuracy/state failure' not in result.stderr:raise RuntimeError('atan C negative failed outside loader/value layer')
   unit(directory,'CPP-'+label,1)
 # Missing/oversized/nonregular cases must not block at open.
 with tempfile.TemporaryDirectory(prefix='atan-files-',dir=work) as t:
  directory=Path(t);run([str(a.probe.resolve()),str(directory)],'missing-C',1);unit(directory,'missing-CPP',1)
  path=directory/'atan-special.corpus'
  with path.open('wb') as stream:stream.truncate(m.MAX_BYTES+1)
  run([str(a.probe.resolve()),str(directory)],'oversize-C',1);unit(directory,'oversize-CPP',1)
  original=Path.open
  try:
   def forbidden(*args,**kwargs):raise RuntimeError('oversized payload opened')
   Path.open=forbidden
   try:m.text(path)
   except RuntimeError as error:
    if 'oversized before read' not in str(error):raise
   else:raise RuntimeError('oversize host fixture escaped')
  finally:Path.open=original
  path.unlink();path.mkdir();run([str(a.probe.resolve()),str(directory)],'directory-C',1);path.rmdir()
  if hasattr(os,'mkfifo'):
   os.mkfifo(path);run([str(a.probe.resolve()),str(directory)],'fifo-C',1,timeout=10);path.unlink()
 # Mandatory complete SHA detects both parse-valid payload and runtime-hash changes.
 for name in ['atan-special.corpus','atan.corpus','atan-special.hash']:
  for kind in ['append','semantic']:
   with tempfile.TemporaryDirectory(prefix='atan-sha-',dir=work) as t:
    directory=Path(t)
    for n,text in data.items():(directory/n).write_text(text)
    original=data[name]
    if kind=='append':changed=original+'\n'
    elif name=='atan-special.corpus':changed=wrong
    elif name=='atan.corpus':changed=original.replace('3fe921fb54442d18','3fe921fb54442d19',1)
    else:changed=original.replace('281c70e9008ebb61','0000000000000000',1)
    if changed==original:raise RuntimeError('atan SHA semantic anchor missing')
    (directory/name).write_text(changed)
    try:m.check(directory)
    except RuntimeError as error:
     if 'complete SHA256 differs' not in str(error):raise
    else:raise RuntimeError('atan complete SHA fault escaped')
 # Mutate a cached actual positive output under real subprocess execution.
 # This calibrates accounting, not fresh numerical oracle generation.
 faults={'raw':lambda s:s.replace('raw 281c70e9008ebb61','raw 0000000000000000'),
  'state':lambda s:s.replace('state f2dc44556cd9a171','state 0000000000000000'),
  'generic':lambda s:s.replace('generic ec6946b8a9e1891b','generic 0000000000000000'),
  'rows':lambda s:s.replace('rows 28382','rows 28381'),
  'calls':lambda s:s.replace('calls 464640','calls 464632'),
  'path':lambda s:s.replace('from tests/corpus','from ignored'),
  'seed':lambda s:s.replace('seed 20261028','seed 0'),
  'count':lambda s:s.replace('count 2000','count 0'),
  'fresh':lambda s:s.replace('fresh false','fresh true'),
  'maximum':lambda s:re.sub(r'maximum [0-9.]+','maximum 0.700000000',s),
  'trailing':lambda s:s+'unexpected\n'}
 for label,mutate in list(faults.items())+[('stderr',lambda s:s),('status',lambda s:s)]:
  changed=mutate(positive)
  if label not in ['stderr','status'] and changed==positive:raise RuntimeError('atan process fixture unchanged '+label)
  file=work/('output-'+label);file.write_text('#!'+sys.executable+'\nimport sys\nsys.stdout.write('+repr(changed)+')\nsys.stderr.write('+repr('diagnostic\n' if label=='stderr' else '')+')\nsys.exit('+('1' if label=='status' else '0')+')\n');file.chmod(0o700)
  try:m.probe(file,root,data,rows,generic,m.SEED,m.COUNT,False,True)
  except RuntimeError:pass
  else:raise RuntimeError('atan observed process/output fault escaped '+label)
 # Full actual supplemental name/hash/count guard, one positive then three faults.
 numeric=run([str(a.numeric.resolve()),str(root)],'numeric-control').stdout
 for fault in ['omit','hash','count']:
  out=[]
  for line in numeric.splitlines():
   if fault=='omit' and line.startswith('math.atan.'):continue
   if fault in ['hash','count'] and line.startswith('math.atan.'+fault+' '):line=line.split()[0]+' '+('0000000000000000' if fault=='hash' else '0')
   out.append(line)
  file=work/('numeric-'+fault);file.write_text('#!'+sys.executable+'\nprint('+repr('\n'.join(out))+')\n');file.chmod(0o700)
  run(['sh','tools/check-corpus-hash.sh',str(file.resolve()),str(root),'tests/corpus/trig.hash'],'numeric-'+fault,1)
 # Actual accuracy deletion lets the same parse-valid bad target pass the C
 # value layer. A later outer maximum/SHA check must not masquerade as this.
 header=Path('tests/atan_corpus.h').read_text();anchor='status=!(bound<=0.60);'
 if header.count(anchor)!=1:raise RuntimeError('atan accuracy mutation anchor absent')
 wrong_header=work/'no-accuracy.h';wrong_header.write_text(header.replace(anchor,'status=0;',1));source=work/'no-accuracy.c';source.write_text(Path('tools/probe-atan.c').read_text().replace('../tests/atan_corpus.h',str(wrong_header.resolve()),1));binary=work/'no-accuracy'
 run(shlex.split(e['CONTROL_CC'])+shlex.split(e['CONTROL_CFLAGS'])+['-Itests',str(source),e['CONTROL_ARCHIVE']]+shlex.split(e['CONTROL_LDFLAGS'])+['-lm','-o',str(binary)],'disabled-accuracy-build')
 with tempfile.TemporaryDirectory(prefix='atan-bad-cell-',dir=work) as t:
  directory=Path(t);(directory/'atan-special.corpus').write_text(wrong)
  run([str(a.probe.resolve()),str(directory)],'enabled-accuracy-rejects',1)
  r=run([str(binary),str(directory)],'disabled-accuracy-counterfactual')
  maximum=re.search(r'maximum ([0-9.]+)',r.stdout)
  if not maximum or float(maximum[1])<15:raise RuntimeError('atan cell corruption not observed in disabled counterfactual')

 # Synthetic fresh path/counter accounting reuses the independently pinned
 # answers; it is NOT a newly generated independent numerical sample.
 with tempfile.TemporaryDirectory(prefix='atan-fresh-path-',dir=work) as t:
  directory=Path(t)
  for name in ['atan-special.corpus','atan.corpus']:(directory/name).write_text(data[name].replace('fresh false','fresh true',1))
  fresh_data,fresh_rows,fresh_generic=m.check(directory,m.SEED,m.COUNT,True,False)
  if fresh_rows!=rows:raise RuntimeError('same-row-count path control changed size')
  args=argparse.Namespace(probe=a.probe,unit=a.unit,numeric=a.numeric,directory=directory,seed=m.SEED,count=m.COUNT)
  m.fresh_controls(args,fresh_data,fresh_rows,fresh_generic)
  source=Path('tests/unit/test_atan.cpp').read_text().replace('../atan_corpus.h',str(Path('tests/atan_corpus.h').resolve()))
  if source.count('GMATH_ATAN_CORPUS_DIR')!=1:raise RuntimeError('atan old-family unit directory anchor differs')
  wrong_source=work/'wrong-directory.cpp';wrong_source.write_text(source.replace('GMATH_ATAN_CORPUS_DIR','GMATH_ATANF_CORPUS_DIR',1));wrong_unit=work/'wrong-directory'
  run(shlex.split(e['CONTROL_CXX'])+shlex.split(e['CONTROL_CXXFLAGS'])+['-Itests',str(wrong_source),e['CONTROL_ARCHIVE']]+shlex.split(e['CONTROL_UNIT_LDFLAGS'])+['-lm','-o',str(wrong_unit)],'old-directory-build')
  old=e.get('GMATH_ATANF_CORPUS_DIR');os.environ.pop('GMATH_ATANF_CORPUS_DIR',None)
  try:
   env=dict(os.environ,GMATH_ATAN_CORPUS_DIR=str(directory))
   result=run([str(wrong_unit.resolve()),'--gtest_filter=Atan.PinnedCorpusAndCallerState','--gtest_brief=1'],'old-directory-actual-fallback',env=env)
   if 'from tests/corpus seed 20261028 count 2000 fresh false' not in result.stdout:raise RuntimeError('actual same-size fallback not observed')
   args.unit=wrong_unit
   try:m.fresh_controls(args,fresh_data,fresh_rows,fresh_generic)
   except RuntimeError as error:
    if 'fresh unit ignores requested population/path' not in str(error):raise
   else:raise RuntimeError('actual former-family directory typo escaped')
  finally:
   if old is not None:os.environ['GMATH_ATANF_CORPUS_DIR']=old
  args.unit=None
  fresh_output,_=m.probe(a.probe,directory,fresh_data,fresh_rows,fresh_generic,m.SEED,m.COUNT,True,False)
  fake_probe=work/'fresh-wrong-generic';fake_probe.write_text('#!'+sys.executable+'\nimport sys\nsys.stdout.write('+repr(fresh_output.replace('generic ec6946b8a9e1891b','generic 0000000000000000'))+')\n');fake_probe.chmod(0o700);args.probe=fake_probe
  try:m.fresh_controls(args,fresh_data,fresh_rows,fresh_generic)
  except RuntimeError as error:
   if 'complete numeric overlay differs' not in str(error):raise
  else:raise RuntimeError('actual fresh generic hash cross-check escaped')
  args.probe=a.probe
  for label,output,diagnostic in [('duplicate',numeric+next(line for line in numeric.splitlines() if line.startswith('math.atan.hash '))+'\n','duplicate'),('diagnostic',numeric,'diagnostic')]:
   fake=work/('fresh-numeric-'+label);fake.write_text('#!'+sys.executable+'\nimport sys\nsys.stdout.write('+repr(output)+')\nsys.stderr.write('+repr('diagnostic\n' if label=='diagnostic' else '')+')\n');fake.chmod(0o700);args.numeric=fake
   try:m.fresh_controls(args,fresh_data,fresh_rows,fresh_generic)
   except RuntimeError as error:
    if diagnostic not in str(error):raise
   else:raise RuntimeError('actual fresh numeric protocol fault escaped '+label)
 # Exercise the actual process timeout mechanism with a shortened calibration
 # deadline; no target import, numerical-oracle or final-runtime claim.
 sleeper=work/'sleep';sleeper.write_text('#!'+sys.executable+'\nimport time\ntime.sleep(10)\n');sleeper.chmod(0o700)
 real_run=subprocess.run
 try:
  def short_run(*args,**kwargs):kwargs['timeout']=0.2;return real_run(*args,**kwargs)
  m.subprocess.run=short_run
  try:m.probe(sleeper,root,data,rows,generic,m.SEED,m.COUNT,False,True)
  except subprocess.TimeoutExpired:pass
  else:raise RuntimeError('actual probe timeout control escaped')
 finally:m.subprocess.run=real_run
 for label,arguments in [('negative-seed',['--seed','-1']),('count-limit',['--count','50001']),('unit-without-probe',['--unit',str(a.unit)])]:
  result=run([sys.executable,'tools/check-atan.py']+arguments,'cli-'+label,2)
  if 'pass' in result.stdout.lower():raise RuntimeError('invalid atan CLI printed success')
 (work/'complete.json').write_text(json.dumps(dict(returncode=0,loader_value_fixtures=len(variants),sha_faults=6,observed_process_faults=13,supplemental_faults=3,synthetic_fresh_path_positive=1,actual_old_directory_typo=1,fresh_accounting_faults=3,cli_negatives=3,actual_timeout=1))+'\n')
 print('atan C17/C++%d loader/value negatives,6SHA,13observed process/output and3supplemental controls; actual disabled-accuracy, same-row-count old-directory typo, fresh accounting and process timeout calibrated'%len(variants),flush=True)
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:raise SystemExit('atan controls: FAIL: '+str(error))
