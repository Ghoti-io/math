#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Complete-payload/population gate and focused family defect checks."""
import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
import shlex
import subprocess
import tempfile
from log1p_expm1_reference import SEED, population

def run(cmd,log,env=None):
    with log.open('w') as f:return subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180).returncode

def require_defect(cmd,log,env):
    code=run(cmd,log,env)
    output=log.read_text()
    if code!=1 or '[  FAILED  ] Log1pExpm1.' not in output or 'log1p-expm1: rejected at row' not in output:
        raise RuntimeError('defect failed outside intended numerical/state/loader assertion: '+str(log))

def validate(directory,seed=SEED,count=512):
    if not(0<=seed<1<<64 and 0<=count<=10000):raise ValueError('seed/count outside bounds')
    if (directory/'log1p-expm1.corpus').stat().st_size>16*1024*1024:raise ValueError('reference file exceeds bound')
    data=(directory/'log1p-expm1.corpus').read_bytes()
    pin=(directory/'log1p-expm1.sha256').read_text()
    if pin!=hashlib.sha256(data).hexdigest()+'  log1p-expm1.corpus\n':raise ValueError('log1p-expm1 SHA differs')
    if b'\r' in data or not data.endswith(b'\n'):raise ValueError('noncanonical LF')
    lines=data.decode('ascii').splitlines()
    if len(lines)<2:raise ValueError('missing headers')
    expected_header='# log1p-expm1-v1 seed=%d count=%d MPFR-directed-1200/2400 mpmath-independent'%(seed,count)
    if lines[0]!=expected_header:raise ValueError('wrong requested population metadata')
    rows=[line.split() for line in lines[2:]]
    expected=[(width,word) for width in (64,32) for word in population(width,seed,count)]
    if len(rows)!=len(expected):raise ValueError('omitted/extra rows')
    for row,(width,word) in zip(rows,expected):
        if len(row)!=10 or row[0]!=str(width) or row[1]!=format(word,'0%dx'%(width//4)):raise ValueError('wrong input/population/order')
    return data

def verify_candidate(test,directory,data,log):
    env=dict(os.environ,GMATH_LOG1P_EXPM1_CORPUS_DIR=str(directory))
    if run([str(test)],log,env):raise RuntimeError('positive family control failed')
    output=log.read_text();rows=len(data.decode().splitlines())-2
    loaded=[Path(line.removeprefix('log1p-expm1: loaded ')).resolve() for line in output.splitlines() if line.startswith('log1p-expm1: loaded ')]
    if not loaded or any(path!=(directory/'log1p-expm1.corpus') for path in loaded):
        raise RuntimeError('candidate ignored requested reference directory')
    if 'log1p-expm1: %d rows;'%rows not in output:
        raise RuntimeError('candidate did not report requested population count')
    return env

def no_control_writes(obj):
    undefined=subprocess.check_output(['nm','-u',str(obj)],text=True)
    if any(name in undefined for name in ['fesetround','fesetenv','feupdateenv','feholdexcept']):
        raise ValueError('runtime object references a control-writing operation')
    disassembly=subprocess.check_output(['objdump','-d',str(obj)],text=True).lower()
    if not re.search(r'<[^>]+>:',disassembly):raise RuntimeError('object inspection read no instructions')
    forbidden=r'\b(?:fldcw|ldmxcsr|vldmxcsr|frstor|fldenv|fxrstor\w*|xrstor\w*|sfpc|fscsr|fsrm|mtfs\w*)\b|\bmsr\s+fpcr|\bld\w*\s+[^\n]*%fsr'
    if re.search(forbidden,disassembly):raise ValueError('runtime object contains a control write')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--test',type=Path,required=True)
    parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--fresh',action='store_true');parser.add_argument('--seed',type=int);parser.add_argument('--count',type=int)
    a=parser.parse_args();a.test=a.test.resolve();a.directory=a.directory.resolve();a.work.mkdir(parents=True,exist_ok=True)
    if a.fresh and (a.seed is None or a.count is None):raise ValueError('fresh verification requires seed and count')
    if not a.fresh and (a.seed is not None or a.count is not None):raise ValueError('seed/count options require --fresh')
    data=validate(a.directory,a.seed if a.fresh else SEED,a.count if a.fresh else 512)
    env=verify_candidate(a.test,a.directory,data,a.work/'control.log')
    if a.fresh:
        print('log1p-expm1: complete requested fresh population/SHA/path/count/public API checks passed');return
    # Reference faults exercise the actual test loader/numerical/state checks;
    # every disposable source/object/binary is reclaimed before returning.
    with tempfile.TemporaryDirectory(prefix='reference-',dir=a.work) as temp:
        directory=Path(temp);env_bad=dict(env,GMATH_LOG1P_EXPM1_CORPUS_DIR=str(directory))
        lines=data.decode().splitlines()
        variants={'empty':'','missing-newline':data.decode().rstrip('\n'),'truncated':'\n'.join(lines[:2]+[lines[2].split()[0]])+'\n',
                  'wrong-width':'\n'.join(lines[:2]+[lines[2].replace('64 ','16 ',1)]+lines[3:])+'\n',
                  'oversized-word':'\n'.join(lines[:2]+[lines[2].replace('0000000000000000','f'*80,1)]+lines[3:])+'\n',
                  'oversized-residual':'\n'.join(lines[:2]+[lines[2].replace(' 0 0 ', ' '+'9'*80+' 0 ',1)]+lines[3:])+'\n'}
        # Zero is an independently exact input, so changing its target must fail.
        fields=lines[2].split();fields[2]='3ff0000000000000'
        variants['wrong-target']='\n'.join(lines[:2]+[' '.join(fields)]+lines[3:])+'\n'
        fields=lines[2].split();fields[3]='2'
        variants['wrong-flags']='\n'.join(lines[:2]+[' '.join(fields)]+lines[3:])+'\n'
        for name,text in variants.items():
            (directory/'log1p-expm1.corpus').write_text(text)
            require_defect([str(a.test)],a.work/(name+'.log'),env_bad)
        for width in [64,32]:
            one=0x3ff0000000000000 if width==64 else 0x3f800000
            position=next(i for i,line in enumerate(lines[2:],2) if line.split()[:2]==[str(width),format(one,'0%dx'%(width//4))])
            fields=lines[position].split();fields[2]=format(int(fields[2],16)+8,'0%dx'%(width//4))
            (directory/'log1p-expm1.corpus').write_text('\n'.join(lines[:position]+[' '.join(fields)]+lines[position+1:])+'\n')
            require_defect([str(a.test)],a.work/('ordinary-result-%d.log'%width),env_bad)
        # Exercise every complete-payload protection even when an attacker
        # updates a digest to match a parse-valid, incomplete/wrong population.
        reordered=lines[:2]+[lines[3],lines[2]]+lines[4:]
        duplicate=lines[:2]+[lines[3],lines[3]]+lines[4:]
        validators={
            'omission':('\n'.join(lines[:-1])+'\n').encode(),
            'order':('\n'.join(reordered)+'\n').encode(),
            'duplicate':('\n'.join(duplicate)+'\n').encode(),
            'CRLF':data.replace(b'\n',b'\r\n'),
            'seed':data.replace(b'seed=20261103',b'seed=20261102',1),
        }
        for name,payload in validators.items():
            (directory/'log1p-expm1.corpus').write_bytes(payload)
            (directory/'log1p-expm1.sha256').write_text(hashlib.sha256(payload).hexdigest()+'  log1p-expm1.corpus\n')
            try:validate(directory)
            except ValueError:pass
            else:raise RuntimeError('payload defect escaped: '+name)
        (directory/'log1p-expm1.corpus').write_bytes(data)
        (directory/'log1p-expm1.sha256').write_text('0'*64+'  log1p-expm1.corpus\n')
        try:validate(directory)
        except ValueError:pass
        else:raise RuntimeError('wrong digest escaped')
        for name,bounds in [('interval-inverted',('1','0')),('interval-outside',('-536870914','0'))]:
            fields=lines[2].split();fields[4:6]=bounds
            (directory/'log1p-expm1.corpus').write_text('\n'.join(lines[:2]+[' '.join(fields)]+lines[3:])+'\n')
            require_defect([str(a.test)],a.work/(name+'.log'),env_bad)
        # A parse-valid changed residual need not violate a one-ULP result
        # contract. Its integrity belongs to the complete-payload digest gate.
        fields=lines[2].split();fields[4:6]=['-1','0']
        shifted=('\n'.join(lines[:2]+[' '.join(fields)]+lines[3:])+'\n').encode()
        (directory/'log1p-expm1.corpus').write_bytes(shifted)
        (directory/'log1p-expm1.sha256').write_text(hashlib.sha256(data).hexdigest()+'  log1p-expm1.corpus\n')
        try:validate(directory)
        except ValueError:pass
        else:raise RuntimeError('residual digest mutation escaped')
        # Demonstrate that a two-zero-row fake fresh report cannot pass the
        # public requested-population wrapper, even with a matching new digest.
        zero_rows=[next(line for line in lines[2:] if line.split()[:2]==[str(width),'0'*(width//4)]) for width in [64,32]]
        subset=('\n'.join(lines[:2]+zero_rows)+'\n').encode();(directory/'log1p-expm1.corpus').write_bytes(subset)
        (directory/'log1p-expm1.sha256').write_text(hashlib.sha256(subset).hexdigest()+'  log1p-expm1.corpus\n')
        code=run([sys.executable,__file__,'--fresh','--seed',str(SEED),'--count','512','--test',str(a.test),'--directory',str(directory),'--work',str(directory/'fresh-control')],a.work/'fresh-truncation.log')
        if code!=1 or 'omitted/extra rows' not in (a.work/'fresh-truncation.log').read_text():raise RuntimeError('truncated fresh sample escaped requested population check')
        # The real test with its directory environment deliberately ignored
        # still passes its default data. The wrapper must reject that context.
        wrapper=directory/'ignore-directory.py'
        wrapper.write_text('#!'+sys.executable+'\nimport os\nos.environ.pop("GMATH_LOG1P_EXPM1_CORPUS_DIR",None)\nos.execv('+repr(str(a.test))+', ['+repr(str(a.test))+'])\n');wrapper.chmod(0o755)
        (directory/'log1p-expm1.corpus').write_bytes(data)
        (directory/'log1p-expm1.sha256').write_text(hashlib.sha256(data).hexdigest()+'  log1p-expm1.corpus\n')
        try:verify_candidate(wrapper,directory,data,a.work/'ignored-directory.log')
        except RuntimeError as error:
            if 'ignored requested reference directory' not in str(error):raise
        else:raise RuntimeError('ignored directory escaped actual path check')
    source=Path('src/elementary/log1p_expm1.c').read_text()
    mutations={
      'huge-log-addition':('if(x<0x1p60)sum=gmath_two_sum(1.0,x);','if(1)sum=gmath_two_sum(1.0,x);'),
      'double-errno':('static double plus_double(double x,int exponential) {','static double plus_double(double x,int exponential) { errno=0;'),
      'float-errno':('static float plus_float(float x,int exponential) {','static float plus_float(float x,int exponential) { errno=0;'),
      'double-mode':('static double plus_double(double x,int exponential) {','static double plus_double(double x,int exponential) { (void)fesetround(FE_UPWARD);'),
      'float-mode':('static float plus_float(float x,int exponential) {','static float plus_float(float x,int exponential) { (void)fesetround(FE_UPWARD);'),
      'double-incoming':('static double plus_double(double x,int exponential) {','static double plus_double(double x,int exponential) { (void)feclearexcept(FE_ALL_EXCEPT);'),
      'float-incoming':('static float plus_float(float x,int exponential) {','static float plus_float(float x,int exponential) { (void)feclearexcept(FE_ALL_EXCEPT);'),
      'forced-inexact':('volatile double ignored=one+tiny;','volatile double ignored=one+tiny*0.0;'),
      'tiny-underflow':('(void)gmath_underflow(0)','plus_inexact()'),
      'log-correction':('sum.lo/sum.hi','0.0*sum.lo/sum.hi'),
      'log-series':('plus_log_coeff[n]','plus_log_coeff[n ? n : 1]'),
      'exp-series':('plus_exp_coeff[n]','plus_exp_coeff[n ? n : 1]'),
      'exp-reconstruction':('gmath_pair minus_one={-1.0,0.0}','gmath_pair minus_one={0.0,0.0}'),
      'negative-saturation':('if(x<=-40.0)','if(x<=-1.0)'),
      'early-overflow-double':('0x40862e42fefa39f0','0x40862e42fefa39ef'),
      'early-overflow-float':('0x42b17218','0x42b17217'),
      'log-pole':('return gmath_div_by_zero(GMATH_SIGN_BIT);','return gmath_double(GMATH_INF_BITS|GMATH_SIGN_BIT);'),
      'signaling-invalid':('if(!(a&UINT64_C(0x0008000000000000)))(void)gmath_invalid();','if(0)(void)gmath_invalid();'),
      'float-signaling-invalid':('if(!(a&UINT32_C(0x00400000)))(void)gmath_invalid();','if(0)(void)gmath_invalid();'),
    }
    cc=shlex.split(os.environ['PLUS_CC']);cxx=shlex.split(os.environ['PLUS_CXX'])
    cflags=shlex.split(os.environ['PLUS_CFLAGS']);link=shlex.split(os.environ['PLUS_LINK'])
    objects=shlex.split(os.environ['PLUS_TEST_OBJ'])+shlex.split(os.environ.get('PLUS_HELPER_OBJ',''))
    no_control_writes(Path(os.environ['PLUS_RUNTIME_OBJ']))
    with tempfile.TemporaryDirectory(prefix='source-',dir=a.work) as temp:
        directory=Path(temp);path=directory/'log1p_expm1.c';obj=directory/'log1p_expm1.o';exe=directory/'test'
        # A write followed by restoration evades before/after mode snapshots,
        # so calibrate the object-level prohibition with actual compiled code.
        restored=source.replace('static double plus_double(double x,int exponential) {',
            'static double plus_double(double x,int exponential) { int saved=fegetround(); (void)fesetround(FE_TONEAREST); (void)fesetround(saved);')
        path.write_text('#include <fenv.h>\n'+restored)
        if run(cc+cflags+['-Isrc/elementary','-c',str(path),'-o',str(obj)],a.work/'restored-control-compile.log'):raise RuntimeError('control-write fixture failed to compile')
        try:no_control_writes(obj)
        except ValueError:pass
        else:raise RuntimeError('restored control write escaped scoped object gate')
        for name,(before,after) in mutations.items():
            if before not in source:raise RuntimeError('source defect anchor missing: '+name)
            path.write_text('#include <errno.h>\n#include <fenv.h>\n'+source.replace(before,after))
            if run(cc+cflags+['-Isrc/elementary','-c',str(path),'-o',str(obj)],a.work/(name+'-compile.log')):raise RuntimeError('defect compile failed: '+name)
            if run(cxx+objects+[str(obj),os.environ['PLUS_ARCHIVE']]+link+['-o',str(exe)],a.work/(name+'-link.log')):raise RuntimeError('defect link failed: '+name)
            require_defect([str(exe)],a.work/(name+'.log'),env)
    print('log1p-expm1: positive; loader, ordinary accuracy, residual, integrity, fresh population/path controls; %d numerical/state source defects and restored-control object fault passed'%len(mutations))
if __name__=='__main__':main()
