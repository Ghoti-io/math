#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Optional actual-prior C/C++ result, state, alias and numerical-guard controls."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from adjacent_baseline import load,validate,write_header,digest_file

def words(name):return shlex.split(os.environ[name])
def run(argv,name,status=0,diagnostic=None):
    p=subprocess.run(argv,capture_output=True,text=True,timeout=120)
    (work/(name+'.log')).write_text(p.stdout+p.stderr)
    if (status is not None and p.returncode!=status) or (diagnostic and diagnostic not in p.stdout+p.stderr):
        raise RuntimeError(name+': unexpected status/diagnostic '+str(p.returncode)+'\n'+p.stdout[-2000:]+p.stderr[-2000:])
    return p

CPP=r'''#include "cbrtf_probe.h"
int main(void) {
  if (GMATH_CBRTF_REFERENCE==gmath_cbrtf) {fputs("cbrtf reference aliases current function\n",stderr);return 2;}
  fputs(GMATH_CBRTF_BASELINE_IDENTITY,stdout);
  fenv_t saved;int old_errno=errno;if (fegetenv(&saved)) return 2;
  const int modes[]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
  uint32_t random=0x63756265u;uint64_t count=0;int status=0;
  for (int mode:modes) for (unsigned i=0;i<65536;i++) {
    random^=random<<13;random^=random>>17;random^=random<<5;
    uint32_t a=0,b=0;int ok=cf_call_with(gmath_cbrtf,"current",random,mode,(int)(i%32),i&1?733:0,&a);
    int prior=cf_call_with(GMATH_CBRTF_REFERENCE,"prior",random,mode,(int)(i%32),i&1?733:0,&b);
    if (!ok||!prior||a!=b) {fprintf(stderr,"cbrtf C++ prior mismatch input%08" PRIx32 " mode%d current%08" PRIx32 " prior%08" PRIx32 "\n",random,mode,a,b);status=1;goto done;}
    ++count;
  }
 done:
  if (fesetenv(&saved)) {status=1;}
  errno=old_errno;
  if (!status) printf("cbrtf.cpp logical observations %" PRIu64 "\n",count);
  return status;
}
'''

def tools(reference,metadata,label,current=None,alias=False):
    header=work/(label+'.identity.h');write_header(header,metadata,'cbrtf')
    symbol='gmath_cbrtf' if alias else 'gmath_cbrtf_prior'
    common=['-include',str(header),'-DGMATH_CBRTF_REFERENCE='+symbol]
    objects=([str(current)] if current else [])+[str(reference),os.environ['NATIVE_LIBRARY']]
    raw=work/(label+'-raw');compare=work/(label+'-compare');cpp=work/(label+'-cpp');bench=work/(label+'-bench')
    for name,source,binary in [('raw','tools/probe-cbrtf.c',raw),('compare','tools/compare-cbrtf.c',compare)]:
        run(words('NATIVE_CC')+words('NATIVE_CFLAGS')+common+[source,*objects]+words('NATIVE_LDFLAGS')+['-lm','-o',str(binary)],label+'-'+name+'-build')
    run(words('NATIVE_CXX')+words('NATIVE_INCLUDE')+['-Itests',*common,str(work/'caller.cpp'),*objects]+words('NATIVE_LDFLAGS')+['-lm','-o',str(cpp)],label+'-cpp-build')
    run(words('NATIVE_CC')+words('NATIVE_CFLAGS')+['-include',str(header),'-DGMATH_CBRTF_BASELINE='+symbol,'tools/bench-cbrtf.c',*objects]+words('NATIVE_LDFLAGS')+['-lm','-o',str(bench)],label+'-bench-build')
    return raw,compare,cpp,bench

def main():
    metadata=load(os.environ['NATIVE_METADATA']);reference=Path(os.environ['NATIVE_REFERENCE'])
    if metadata['revision']!='412417c7a0edc5b0066296e578400dd21d4685e4':raise RuntimeError('baseline revision differs from expected revision')
    validate(metadata,reference,os.environ['NATIVE_LIB_CFLAGS'],os.environ['NATIVE_CC'])
    (work/'caller.cpp').write_text(CPP)
    envkeys=['NATIVE_CC','NATIVE_CXX','NATIVE_CFLAGS','NATIVE_LIB_CFLAGS','NATIVE_INCLUDE','NATIVE_LDFLAGS','NATIVE_LIBRARY','NATIVE_REFERENCE','NATIVE_METADATA']
    (work/'context.json').write_text(json.dumps({k:os.environ[k] for k in envkeys},indent=2)+'\n')
    source=Path('src/elementary/float_cbrt.c').read_text()
    fixtures={'valid':reference}
    bodies={
      'result':'float y=gmath_cbrtf(x);uint32_t u;memcpy(&u,&y,4);u^=1u;memcpy(&y,&u,4);return y;',
      'NaN-payload':'float y=gmath_cbrtf(x);uint32_t u;memcpy(&u,&y,4);if ((u&0x7fffffffu)>0x7f800000u) {u|=1u;memcpy(&y,&u,4);}return y;',
      'flags':'float y=gmath_cbrtf(x);feraiseexcept(FE_INVALID);return y;',
      'errno':'float y=gmath_cbrtf(x);errno=991;return y;',
      'mixed-incoming':'float y=gmath_cbrtf(x);if ((fetestexcept(FE_INVALID|FE_DIVBYZERO)&(FE_INVALID|FE_DIVBYZERO))==(FE_INVALID|FE_DIVBYZERO)) feclearexcept(FE_INVALID|FE_DIVBYZERO);return y;',
      'mode':'float y=gmath_cbrtf(x);fesetround(FE_UPWARD);return y;'}
    for name,body in bodies.items():
        file=work/(name+'.c');obj=work/(name+'.o');file.write_text('#include <ghoti.io/math/elementary.h>\n#include <stdint.h>\n#include <string.h>\n#include <errno.h>\n#include <fenv.h>\nfloat gmath_cbrtf_prior(float x){'+body+'}\n')
        run(words('NATIVE_CC')+words('NATIVE_LIB_CFLAGS')+['-c',str(file),'-o',str(obj)],name+'-compile');fixtures[name]=obj
    file=work/'wrong-format.c';file.write_text('double gmath_cbrtf_prior(double x){(void)x;return 1.0;}\n');obj=work/'wrong-format.o';run(words('NATIVE_CC')+words('NATIVE_LIB_CFLAGS')+['-c',str(file),'-o',str(obj)],'wrong-format-compile');fixtures['wrong-format']=obj
    count=0
    for name,ref in fixtures.items():
        fields=dict(metadata);fields['object_sha256']=digest_file(ref)
        raw,compare,cpp,bench=tools(ref,fields,name)
        expected=0 if name=='valid' else 1
        run([str(raw),os.environ['NATIVE_CORPUS']],name+'-raw',expected,None if name=='valid' else 'prior')
        run([str(cpp)],name+'-cpp',expected,None if name=='valid' else 'prior')
        count+=2
        # Result-only comparison does not test flags/errno. Its explicit ending-mode check does test mode.
        if name in ('valid','result','mode','wrong-format'):
            run([str(compare),'0','2139095040','65537','3','0'],name+'-compare',expected);count+=1
        # Timing guards request UF/IX, not mixed IV/DZ; do not claim the latter here.
        if name!='mixed-incoming':run([str(bench)],name+'-bench',0 if name=='valid' else 2);count+=name!='mixed-incoming'
    raw,compare,cpp,bench=tools(reference,metadata,'alias',alias=True)
    for kind,binary,args,code in [('raw',raw,[os.environ['NATIVE_CORPUS']],1),('compare',compare,['0','100','1','3','0'],2),('cpp',cpp,[],2),('bench',bench,[],2)]:
        run([str(binary),*args],'alias-'+kind,code,'aliases');count+=1
    # Current-code defects which ordinary nearest accuracy/class tests need not detect.
    (work/'elem_common.h').write_bytes(Path('src/elementary/elem_common.h').read_bytes());(work/'cbrt_table.h').write_bytes(Path('src/elementary/cbrt_table.h').read_bytes())
    mutants=[('gate-disabled','residue>UINT64_C(0x00800000)&&residue<UINT64_C(0x0f800000)','residue>0&&residue<UINT64_C(0x0fffffff)'),
      ('sign-after-narrow','double scaled=gmath_double((bits+((uint64_t)(int64_t)q<<52))|((uint64_t)(word&0x80000000u)<<32));\n      result=(float)scaled;',
       'double scaled=gmath_double(bits+((uint64_t)(int64_t)q<<52));\n      result=(float)scaled;if (word&0x80000000u) result=-result;')]
    for name,old,new in mutants:
        if source.count(old)!=1:raise RuntimeError('native current mutation anchor: '+name)
        file=work/(name+'.c');obj=work/(name+'.o');file.write_text(source.replace(old,new,1));run(words('NATIVE_CC')+words('NATIVE_LIB_CFLAGS')+['-c',str(file),'-o',str(obj)],name+'-compile')
        raw,compare,cpp,bench=tools(reference,metadata,name,current=obj)
        run([str(cpp)],name+'-cpp',1,'prior');count+=1
        observed=False
        for mode in range(4):
            result=run([str(compare),'0','2139095040','65537','3',str(mode)],name+'-compare-mode'+str(mode),None)
            if result.returncode==1 and 'cbrtf mismatch input' in result.stderr:observed=True;break
            if result.returncode!=0:raise RuntimeError('current mutation comparison failed for unrelated reason')
        if not observed:raise RuntimeError('current mutation escaped all-mode prior comparison: '+name)
        count+=1
    print('cbrtf native controls: %d actual/wrong/alias/current-defect C/C++ result/state controls pass'%count)
if __name__=='__main__':
    work=Path(os.environ['NATIVE_WORK']);work.mkdir(parents=True,exist_ok=True)
    try:main()
    except (OSError,RuntimeError,subprocess.SubprocessError) as e:
        print('cbrtf native controls: FAIL: '+str(e),file=sys.stderr);sys.exit(1)
