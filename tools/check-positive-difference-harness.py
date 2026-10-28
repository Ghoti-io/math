#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Actual caller-harness restoration controls in C17 and C++, not API timing."""
import os
from pathlib import Path
import shlex
import subprocess

def main():
 e=os.environ;work=Path(e['HARNESS_WORK']);work.mkdir(parents=True,exist_ok=True)
 source=Path('tests/positive_difference_probe.h').read_text()
 files=work/'late';files.mkdir(exist_ok=True)
 data=Path('tests/corpus/fdim64-special.corpus').read_bytes();(files/'fdim64-special.corpus').write_bytes(data[:-1])
 empty=work/'empty';empty.mkdir(exist_ok=True)
 body=r'''
#include "HEADER"
int main(int argc,char **argv) {
 fenv_t saved;if(argc!=2||fegetenv(&saved))return 2;
 if(fesetround(FE_DOWNWARD)||feclearexcept(FE_ALL_EXCEPT)||feraiseexcept(FE_INVALID|FE_DIVBYZERO))return 2;
 int before=fetestexcept(FE_ALL_EXCEPT);uint64_t controls=ppd_controls();errno=733;
 int inner;
 if(!strcmp(argv[1],"inner")||!strcmp(argv[1],"mismatch")||!strcmp(argv[1],"flag-mismatch")) {
  uint64_t hash=GMATH_FNV_BASIS;
  int mismatch=strcmp(argv[1],"inner")!=0;
  inner=ppd_call(UINT64_C(0x0010000000000000),UINT64_C(0x000fffffffffffff),!strcmp(argv[1],"mismatch")?2:1,!strcmp(argv[1],"flag-mismatch")?2u:0u,64,FE_TONEAREST,0,0,&hash,0)!=mismatch;
 } else {inner=ppd_probe(argv[1],64,0)!=1;}
 int ok=!inner&&errno==733&&fegetround()==FE_DOWNWARD&&fetestexcept(FE_ALL_EXCEPT)==before&&ppd_controls()==controls;
 if(fesetenv(&saved))return 2;
 if(!ok){fputs("positive difference caller harness restoration mismatch\n",stderr);return 1;}
 return 0;
}
'''
 variants=[('control',source,'inner',0),('operation-mismatch-control',source,'mismatch',0),('flag-mismatch-control',source,'flag-mismatch',0),('late-record-control',source,str(files),0),('missing-file-control',source,str(empty),0),
  ('inner-env-loss',source.replace('if (fesetenv(&saved)) {status = 1;}','(void)0;',1),'inner',1),
  ('outer-errno-loss',source.replace('errno=saved_errno;return status;','(void)saved_errno;return status;',1),str(empty),1),
  ('failure-only-restore-loss',source.replace('expected, got_flags, want, got_errno, error, got_mode, mode);\n      goto done;','expected, got_flags, want, got_errno, error, got_mode, mode);\n      return 1;',1),'mismatch',1)]
 for language in ['C','CPP']:
  for label,text,arg,status in variants:
   if label in ['inner-env-loss','outer-errno-loss','failure-only-restore-loss'] and text==source:raise RuntimeError('harness mutation anchor absent')
   header=work/(language+'-'+label+'.h');header.write_text(text);file=work/(language+'-'+label+('.c' if language=='C' else '.cpp'));file.write_text(body.replace('HEADER',header.name));binary=work/(language+'-'+label)
   command=shlex.split(e['HARNESS_CC' if language=='C' else 'HARNESS_CXX'])+shlex.split(e['HARNESS_CFLAGS' if language=='C' else 'HARNESS_CXXFLAGS'])+['-Itests',str(file),e['HARNESS_ARCHIVE']]+shlex.split(e['HARNESS_LDFLAGS'])+['-lm','-o',str(binary)]
   r=subprocess.run(command,capture_output=True,text=True,timeout=60);(work/(language+'-'+label+'-compile.log')).write_text(r.stdout+r.stderr)
   if r.returncode:raise RuntimeError('caller harness compile failed '+label+r.stderr[-400:])
   r=subprocess.run([str(binary.resolve()),arg],capture_output=True,text=True,timeout=120);(work/(language+'-'+label+'.log')).write_text(r.stdout+r.stderr)
   if r.returncode!=status or (status and 'caller harness restoration mismatch' not in r.stderr):raise RuntimeError('caller harness outcome differs '+language+label)
 print('positive difference caller harness:10 C17/C++ positives and6 real restoration faults pass; outer fenv force-deletion detection is not claimed')
if __name__=='__main__':
 try:main()
 except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:raise SystemExit('positive difference harness: FAIL: '+str(error))
