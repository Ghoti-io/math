#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Actual pinned atan oracle/certificate/publisher faults and dispatch accounting."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True);records=[]
 spec=importlib.util.spec_from_file_location('atan_oracle','tools/oracle/oracle.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
 def record(label,command,result,start):
  (a.work/(label+'.log')).write_text(result.stdout+result.stderr);records.append(dict(label=label,command=command,returncode=result.returncode,elapsed_seconds=time.time()-start));(a.work/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
 def engine(args,label,timeout=180):
  start=time.time();r=oracle.engine_run(ref,args,capture=True,timeout=timeout);record(label,args,r,start);return r
 try:ref,version=oracle.check_pin(timeout=20)
 except oracle.Unavailable as error:
  if oracle.REQUIRED:raise RuntimeError(str(error))
  print('atan numerical oracle/certificate/publisher controls SKIPPED optional engine: '+str(error),flush=True);ref=None
 source=Path('tools/oracle/gen_corpus_atan.py').read_text()
 def staged_script(text,path):
  text=text.replace('import argparse',"import sys\nsys.path.insert(0,'tools/oracle')\nimport argparse",1)
  text=text.replace('sys.path.insert(0,str(Path(__file__).resolve().parents[1]))',"sys.path.insert(0,'tools')",1)
  path.write_text(text)
 if ref:
  positive=engine(['python','tools/oracle/gen_corpus_atan.py','--self-test'],'publisher-positive')
  if positive.returncode or 'publisher2positives/8ordinary-exception' not in positive.stdout:raise RuntimeError('atan publisher/fixed controls failed')
  print(positive.stdout.strip(),flush=True)
  faults=[('decode','x=fraction(raw);a=abs(x);bounds=[]','x=fraction(raw)*2;a=abs(x);bounds=[]','independent input decoding differs'),
          ('target','target=round_word(low,negative_zero=bool(raw&SIGN))','target=round_word(low,negative_zero=bool(raw&SIGN))^1','uncertified atan target/error'),
          ('tiny-sign','return target,0 if raw&SIGN else 0x80000000','return target,0','fixed target/error differs'),
          ('tiny-range','if a<power(-104):','if a<power(-10):','tiny signed-error bound failed'),
          ('precision','with gmpy2.context(precision=precision,round=mode):','with gmpy2.context(precision=53,round=mode):','atan MPFR/mpmath disagreement'),
          ('version',"gmpy2.version()!='2.3.2'","gmpy2.version()!='0.0.0'",'atan oracle pin differs')]
  for label,old,new,diagnostic in faults:
   expected=2 if label=='precision' else 1
   if source.count(old)!=expected:raise RuntimeError('atan oracle fault anchor differs '+label)
   with tempfile.TemporaryDirectory(prefix='atan-oracle-',dir=a.work) as t:
    stage=Path(t);file=stage/'fault.py';out=stage/'out';staged_script(source.replace(old,new,1),file)
    r=engine(['python',str(file.resolve()),'--out',str(out.resolve()),'--count','0'],'oracle-'+label)
    if r.returncode!=1 or diagnostic not in r.stderr or (out.exists() and list(out.iterdir())):raise RuntimeError('atan actual oracle fault escaped/intended layer absent '+label)
  for label,replacement in [('ignored-seed','words=population(SEED,a.count)'),('ignored-count','words=population(a.seed,0)')]:
   old='words=population(a.seed,a.count)'
   if source.count(old)!=1:raise RuntimeError('atan request population anchor differs')
   with tempfile.TemporaryDirectory(prefix='atan-request-',dir=a.work) as t:
    stage=Path(t);file=stage/'fault.py';out=stage/'out';staged_script(source.replace(old,replacement,1),file)
    r=engine(['python',str(file.resolve()),'--out',str(out.resolve()),'--seed','123','--count','113','--fresh'],label+'-generate')
    if r.returncode:raise RuntimeError('atan request fault failed before publication')
    cmd=[sys.executable,'tools/check-atan.py','--directory',str(out),'--fresh','--seed','123','--count','113'];start=time.time();check=subprocess.run(cmd,capture_output=True,text=True,timeout=180);record(label+'-check',cmd,check,start)
    if check.returncode!=1 or 'complete requested population differs' not in check.stderr:raise RuntimeError('atan ignored request escaped population layer')
  # Mathematical model faults are separate from source-fingerprint controls.
  certificate=Path('tools/oracle/check_atan_budget.py').read_text()
  cert_faults=[('tiny','power(-60+54)/3 < 1','power(54)/3 < 1','atan tiny nearest cell'),
               ('tiny-error','power(-154)/3 < power(-150)','power(-140)/3 < power(-150)','atan tiny signed-error cell'),
               ('large','low-power(-54)','low-power(-2)','atan large nearest cell'),
               ('center','center=fraction(PIO2);','center=fraction(PIO2+1);','atan large nearest cell'),
               ('index','8<=index<=64','8<=index<=63','atan unary index endpoints')]
  normal=engine(['python','tools/oracle/check_atan_budget.py'],'certificate-positive')
  if normal.returncode or 'PASS:' not in normal.stdout:raise RuntimeError('atan normal guard certificate failed')
  for label,old,new,diagnostic in cert_faults:
   if certificate.count(old)!=1:raise RuntimeError('atan certificate anchor differs '+label)
   with tempfile.TemporaryDirectory(prefix='atan-budget-',dir=a.work) as t:
    file=Path(t)/'fault.py';text=certificate.replace(old,new,1).replace('ROOT=Path(__file__).resolve().parents[2]','ROOT=Path('+repr(str(Path.cwd()))+')',1);staged_script(text,file)
    r=engine(['python',str(file.resolve())],'certificate-'+label)
    if r.returncode!=1 or diagnostic not in r.stderr or 'PASS:' in r.stdout:raise RuntimeError('atan mathematical certificate fault escaped '+label)
  for label,flag,path,old,new in [('source','--source','src/elementary/atan.c','0x4350000000000000','0x4330000000000000'),('table','--table','src/elementary/atan2_table.h','54442d18','54442d19'),('helper','--helper','src/elementary/elem_common.h','gmath_underflow','gmath_underflow_changed')]:
   text=Path(path).read_text()
   if old not in text:raise RuntimeError('atan applicability fault anchor absent')
   with tempfile.TemporaryDirectory(prefix='atan-applicability-',dir=a.work) as t:
    file=Path(t)/Path(path).name;file.write_text(text.replace(old,new,1));r=engine(['python','tools/oracle/check_atan_budget.py',flag,str(file.resolve())],'applicability-'+label)
    if r.returncode!=1 or 'atan source applicability' not in r.stderr or 'PASS:' in r.stdout:raise RuntimeError('atan source applicability fault escaped')
  print('atan6actualoracle/pin faults,2ignoredrequests,5mathematical/3applicability certificate faults detect',flush=True)
 # Real wrapper subprocesses with a recording engine: argv accounting only.
 wrapper=Path('tools/oracle/oracle.py').read_text();_,pin_version=oracle.pin()
 with tempfile.TemporaryDirectory(prefix='atan-wrapper-',dir=a.work) as t:
  stage=Path(t);fake=stage/'engine';recordfile=stage/'record.json'
  fake.write_text('#!'+sys.executable+'\nimport sys,json\nfrom pathlib import Path\nargs=sys.argv[1:]\nif args[:2]==["image","exists"]:sys.exit(0)\nif args[-1:]==["mpfr-version"]:print('+repr(pin_version)+');sys.exit(0)\np=Path('+repr(str(recordfile.resolve()))+')\nold=json.loads(p.read_text()) if p.exists() else []\nold.append(args);p.write_text(json.dumps(old))\n');fake.chmod(0o700)
  env=dict(os.environ,GHOTI_CONTAINER_ENGINE=str(fake.resolve()),GHOTI_ORACLE_REQUIRED='1')
  dispatch=next(line for line in wrapper.splitlines() if line.startswith('    if a.cmd in ("logbase",'))
  omitted=dispatch.replace('"atan", "fresh-atan", ','')
  if omitted==dispatch:raise RuntimeError('atan family wrapper omission anchor absent')
  variants={'family':wrapper.replace(dispatch,omitted,1),'budget':wrapper.replace('    if a.cmd == "budget-atan":\n        return engine_run(ref, ["python", "tools/oracle/check_atan_budget.py"]).returncode\n','',1)}
  for command in ['atan','fresh-atan','budget-atan']:
   for fault in [False,True]:
    recordfile.unlink(missing_ok=True);selected=Path('tools/oracle/oracle.py')
    if fault:
     selected=stage/'wrong-wrapper.py';selected.write_text(variants['budget' if command=='budget-atan' else 'family'].replace('HERE = os.path.dirname(os.path.abspath(__file__))','HERE = '+repr(str(Path('tools/oracle').resolve())),1))
    out=stage/('out-'+command+str(fault));cmd=[sys.executable,str(selected),command,'--out',str(out.resolve()),'--seed','123','--count','17'];start=time.time();r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=30);record('wrapper-'+command+'-'+str(fault),cmd,r,start)
    calls=json.loads(recordfile.read_text()) if recordfile.exists() else [];actual=[args[args.index('python')+1:] for args in calls if 'python' in args]
    expected=[['tools/oracle/check_atan_budget.py']] if command=='budget-atan' else [['tools/oracle/gen_corpus_atan.py','--out',str(out.resolve()),'--seed','123','--count','17']+(['--fresh'] if command=='fresh-atan' else [])]
    if r.returncode or (actual==expected)==fault:raise RuntimeError('atan wrapper dispatch accounting differs '+command)
  env['GHOTI_CONTAINER_ENGINE']=str((stage/'absent').resolve())
  for required in [False,True]:
   env['GHOTI_ORACLE_REQUIRED']='1' if required else '0';out=stage/('absent-'+str(required));cmd=[sys.executable,'tools/oracle/oracle.py','fresh-atan','--out',str(out.resolve()),'--count','17'];start=time.time();r=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=30);record('absent-'+str(required),cmd,r,start)
   if r.returncode!=(1 if required else 3) or (out.exists() and list(out.iterdir())):raise RuntimeError('atan optional/required absence semantics differ')
 print('atan oracle controls pass; recording-engine dispatch/absence controls are accounting, not numerical oracle evidence',flush=True)
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:raise SystemExit('atan oracle controls: FAIL: '+str(error))
