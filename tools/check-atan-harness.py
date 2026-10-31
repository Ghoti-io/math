#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Calibrate actual unary caller/accuracy/loader restoration in C17 and C++."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

def main():
 e=os.environ;work=Path(e['HARNESS_WORK']);work.mkdir(parents=True,exist_ok=True);records=[]
 inner=Path('tests/atan_probe.h').read_text();outer=Path('tests/atan_corpus.h').read_text()
 late=work/'late';late.mkdir(exist_ok=True);latefile=late/'atan-special.corpus';latefile.write_bytes(Path('tests/corpus/atan-special.corpus').read_bytes()[:-1])
 missing=work/'missing';missing.mkdir(exist_ok=True)
 def words(name):return shlex.split(e[name])
 def run(cmd,label,want=0):
  start=time.time();r=subprocess.run(cmd,capture_output=True,text=True,timeout=180);(work/(label+'.log')).write_text(r.stdout+r.stderr);records.append(dict(label=label,command=cmd,returncode=r.returncode,elapsed_seconds=time.time()-start));(work/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
  if r.returncode!=want:raise RuntimeError(label+' actual status '+str(r.returncode)+' expected '+str(want)+' '+r.stderr[-500:])
  return r
 names=run(shlex.split(e.get('HARNESS_NM','nm'))+['-g','--defined-only',e['HARNESS_ARCHIVE']],'defined-symbols').stdout
 symbols={line.split()[-1] for line in names.splitlines() if line.strip() and line.split()[-1].endswith('_gmath_atan')}
 if len(symbols)!=1:raise RuntimeError('atan harness cannot identify public symbol')
 symbol=next(iter(symbols))
 if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',symbol):raise RuntimeError('atan harness symbol is not a C identifier')
 body=r'''
#include "OUTER"
#ifdef __cplusplus
extern "C" {
#endif
static uint64_t observed_calls;
double __real_SYMBOL(double);
double __wrap_SYMBOL(double x) {++observed_calls;return __real_SYMBOL(x);}
#ifdef __cplusplus
}
#endif
int main(int argc,char **argv) {
 if(argc!=3)return 2;
 uint64_t minimum=(uint64_t)strtoull(argv[2],NULL,10);
 fenv_t saved;if(fegetenv(&saved))return 2;int old_errno=errno;
 if(fesetround(FE_DOWNWARD)||feclearexcept(FE_ALL_EXCEPT)||feraiseexcept(FE_INVALID|FE_DIVBYZERO))return 2;
 int before=fetestexcept(FE_ALL_EXCEPT);uint64_t controls=gmath_test_controls();errno=733;
 int inner;
 if(!strcmp(argv[1],"inner")||!strcmp(argv[1],"mismatch")||!strcmp(argv[1],"flag-mismatch")) {
  int mismatch=strcmp(argv[1],"inner")!=0;
  inner=a64_call(UINT64_C(0x0010000000000000),!strcmp(argv[1],"mismatch")?UINT64_C(0x0010000000000001):UINT64_C(0x0010000000000000),!strcmp(argv[1],"flag-mismatch")?0u:2u,1,FE_TONEAREST,0,0)!=mismatch;
 } else if(!strcmp(argv[1],"accuracy")) {
  double maximum=0;inner=a64_accuracy(UINT64_C(0x3ff0000000000000),0,UINT64_C(0x3ff0000000000000),&maximum)!=0;
 } else if(!strcmp(argv[1],"valid")) {inner=a64_probe("tests/corpus",1)!=0;}
 else {inner=a64_probe(argv[1],0)!=1;}
 int ok=!inner&&observed_calls>=minimum&&errno==733&&fegetround()==FE_DOWNWARD&&fetestexcept(FE_ALL_EXCEPT)==before&&gmath_test_controls()==controls;
 if(fesetenv(&saved)) {return 2;}
 errno=old_errno;
 if(!ok){fputs("atan harness restoration/call-accounting mismatch\n",stderr);return 1;}
 printf("atan harness observed calls %" PRIu64 "\n",observed_calls);
 return 0;
}
'''.replace('SYMBOL',symbol)
 def outer_errno_loss(text):
  marker='  errno=saved_errno;';at=text.rfind(marker)
  if at<0:raise RuntimeError('outer errno restoration anchor absent')
  return text[:at]+text[at:].replace(marker,'  (void)saved_errno;',1)
 def accuracy_env_loss(text):
  start=text.index('static int a64_accuracy(');end=text.index('static int a64_line(',start);part=text[start:end];marker='if(fesetenv(&saved)) {status=1;}'
  if part.count(marker)!=1:raise RuntimeError('accuracy restore anchor absent')
  return text[:start]+part.replace(marker,'(void)0;',1)+text[end:]
 marker='input, got, expected, observed, want, got_errno, error, got_mode, mode);\n      goto done;'
 if inner.count(marker)!=1:raise RuntimeError('operation failure restoration anchor absent')
 variants=[('inner-control',inner,outer,'inner',1,0),('mismatch-control',inner,outer,'mismatch',1,0),('flag-mismatch-control',inner,outer,'flag-mismatch',1,0),('accuracy-control',inner,outer,'accuracy',0,0),('valid-control',inner,outer,'valid',1000,0),('late-control',inner,outer,str(late),1000,0),('missing-control',inner,outer,str(missing),0,0),
  ('inner-env-loss',inner.replace('if (fesetenv(&saved)) {status = 1;}','(void)0;',1),outer,'inner',1,1),
  ('inner-errno-loss',inner.replace('errno = saved_errno;','(void)saved_errno;',1),outer,'inner',1,1),
  ('failure-only-restore-loss',inner.replace(marker,marker.replace('goto done;','return 1;'),1),outer,'mismatch',1,1),
  ('accuracy-env-loss',inner,accuracy_env_loss(outer),'accuracy',0,1),
  ('outer-errno-loss',inner,outer_errno_loss(outer),str(missing),0,1)]
 for language in ['C','CPP']:
  for label,inside,outside,arg,minimum,want in variants:
   prefix=language+'-'+label;ih=work/(prefix+'-inner.h');oh=work/(prefix+'-outer.h');source=work/(prefix+('.c' if language=='C' else '.cpp'));binary=work/prefix
   ih.write_text(inside);oh.write_text(outside.replace('#include "atan_probe.h"','#include '+json.dumps(str(ih.resolve())),1));source.write_text(body.replace('OUTER',str(oh.resolve())))
   compiler=words('HARNESS_CC' if language=='C' else 'HARNESS_CXX');flags=words('HARNESS_CFLAGS' if language=='C' else 'HARNESS_CXXFLAGS')
   run(compiler+flags+['-Itests',str(source),e['HARNESS_ARCHIVE']]+words('HARNESS_LDFLAGS')+['-lm','-Wl,--wrap,'+symbol,'-o',str(binary)],prefix+'-build')
   result=run([str(binary),arg,str(minimum)],prefix,want)
   if want and 'atan harness restoration/call-accounting mismatch' not in result.stderr:raise RuntimeError('harness fault failed outside intended restoration layer')
 print('atan harness14 C17/C++ positives and10 real restore defects calibrated; late failures observe actual wrapped API calls; outer fenv-only deletion coverage unclaimed',flush=True)
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:raise SystemExit('atan harness: FAIL: '+str(error))
