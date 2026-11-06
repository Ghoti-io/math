#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Positive DD controls, authenticated loader faults and compiled source faults."""
import sys
if not __debug__ or sys.flags.optimize:raise SystemExit('DD controls require assertion-enabled Python')
import argparse,importlib.util,json,os,shlex,shutil,subprocess
from pathlib import Path
spec=importlib.util.spec_from_file_location('dd',Path(__file__).with_name('check-long-double-dd.py'))
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--basic',type=Path,required=True);ap.add_argument('--nine',type=Path,required=True);ap.add_argument('--work',type=Path,required=True);ap.add_argument('--corpus',type=Path,required=True);a=ap.parse_args()
 root=Path(__file__).resolve().parents[1];work=a.work.resolve();work.mkdir(parents=True,exist_ok=True)
 d.check(a.basic,a.nine,a.corpus)
 # Positive byte-level parsing controls precede every rejecting record.
 valid=b'106 12 3ff0000000000000 0000000000000001 0 0 0 3 0\n'
 positive=subprocess.run([str(a.basic.resolve())],input=valid,capture_output=True)
 assert positive.returncode==0 and len(positive.stdout.splitlines())==2,'strict record positive control failed'
 for label,payload in [('embedded-nul',valid[:-1]+b'\0hidden\n'),
                       ('nul-after-newline',valid+b'\0hidden\n'),
                       ('unterminated',valid[:-1]),('overlong',b'1'*512+b'\n')]:
  result=subprocess.run([str(a.basic.resolve())],input=payload,capture_output=True)
  (work/(label+'-rejection.log')).write_bytes(result.stdout+result.stderr)
  assert result.returncode==2 and b'malformed byte record' in result.stderr,'DD strict byte record accepted or wrong rejection: '+label
  print('DD controls: rejected byte record '+label,flush=True)
 literal=json.loads(a.corpus.read_text())
 for name in ('answer','population','truncated'):
  data=json.loads(json.dumps(literal))
  if name=='answer':data['answers'][0][0]^=1
  elif name=='population':data['cells'][0][1][0]^=1
  else:data['cells'].pop()
  path=work/(name+'.json');path.write_text(json.dumps(data))
  try:d.corpus(path)
  except AssertionError as error:assert 'authentication' in str(error)
  else:raise AssertionError('DD loader accepted '+name)
  print('DD controls: rejected literal '+name,flush=True)
 cc=shlex.split(os.environ.get('LONG_DOUBLE_DD_CC','cc'));flags=shlex.split(os.environ.get('LONG_DOUBLE_DD_FLAGS',''));link=shlex.split(os.environ.get('LONG_DOUBLE_DD_LINK','-lm'))
 defects=[
  ('frexp-flags','basic','int inexact=!lds_equal(&a,&rounded);','int inexact=0;'),
  ('frexp-carry','basic','r=ld_pack(106,&rounded); ++e;','r=ld_pack(106,&rounded);'),
  ('remainder-flags','nine','lds_flags(106,result,0,!lds_equal(&a,&rounded),0);','(void)rounded;'),
  ('remainder-width','nine','WIDTH=2098','WIDTH=106'),
  ('quotient-low-bits','nine','quotient=((quotient<<1)|(unsigned)take)&127;','quotient=((quotient<<1)|(unsigned)take)&63;'),
  ('quotient-parity','nine','(!cmp && (quotient&1))','(!cmp && !(quotient&1))'),
  ('remainder-zero-sign','nine','if(ld_top(&a)<0)sign=original_sign;','if(ld_top(&a)<0)sign=!original_sign;'),
  ('remainder-rounding','nine','ld_raw result=lds_dd(&a,0);','ld_raw result=lds_dd(&a,0); result.lo^=1;')]
 for name,group,old,new in defects:
  case=work/name;source=case/'src/elementary';source.mkdir(parents=True,exist_ok=True);(case/'tools').mkdir(exist_ok=True);(case/'tests').mkdir(exist_ok=True)
  for p in (root/'src/elementary').glob('*.h'):shutil.copy2(p,source/p.name)
  for stem in ('basic','nine'):shutil.copy2(root/('src/elementary/long_double_'+stem+'.c'),source/('long_double_'+stem+'.c'))
  for p in ('fp_controls.h','long_double_nine_abi.h'):shutil.copy2(root/'tests'/p,case/'tests'/p)
  probe='probe-long-double-dd-basic.c' if group=='basic' else 'probe-long-double-nine.c';shutil.copy2(root/'tools'/probe,case/'tools'/probe)
  path=source/('long_double_basic.c' if group=='basic' else 'long_double_nine_bits.h');text=path.read_text();assert old in text;path.write_text(text.replace(old,new,1))
  binary=case/'probe';obj=case/'production.o';caller=case/'caller.o'
  result=subprocess.run([*cc,*flags,'-fno-lto','-c',str(source/('long_double_'+group+'.c')),'-o',str(obj)],capture_output=True,text=True)
  (case/'object-compile.log').write_text(result.stdout+result.stderr);assert result.returncode==0,name+' object setup failure'
  result=subprocess.run([*cc,*flags,'-fno-lto','-c',str(case/'tools'/probe),'-o',str(caller)],capture_output=True,text=True)
  (case/'caller-compile.log').write_text(result.stdout+result.stderr);assert result.returncode==0,name+' caller setup failure'
  abi=root/('tools/check-long-double'+('-nine' if group=='nine' else '')+'-abi.py')
  result=subprocess.run([sys.executable,str(abi),'--caller-object',str(caller)],capture_output=True,text=True)
  (case/'caller-abi.log').write_text(result.stdout+result.stderr);assert result.returncode==0,name+' external caller setup failure'
  result=subprocess.run([*cc,*flags,'-fno-lto',str(caller),str(obj),*link,'-o',str(binary)],capture_output=True,text=True)
  (case/'compile.log').write_text(result.stdout+result.stderr);assert result.returncode==0,name+' link setup failure'
  try:d.check(binary if group=='basic' else a.basic,binary if group=='nine' else a.nine,a.corpus)
  except AssertionError as error:
   (case/'rejection.log').write_text(str(error)+'\n');assert 'DD row ' in str(error),name+' rejected outside numerical/state assertion: '+str(error)
  else:raise AssertionError('DD compiled defect escaped: '+name)
  print('DD controls: rejected compiled '+name+' at result/state assertion',flush=True)
if __name__=='__main__':main()
