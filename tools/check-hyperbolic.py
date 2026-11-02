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
from hyperbolic_reference import SEED, population

TEST_NAMES={'IndependentFamilyCorpusAndCallerState','AnalyticSpecialValuesAndFlagPriority',
            'SymmetryMonotonicityAndBounds','ClosedCellsAndNormalSubnormalBoundary',
            'PreserveFlushToZeroControlAndState'}

def clean_env(env=None):
    return {key:value for key,value in (os.environ if env is None else env).items() if not key.startswith('GTEST_')}

def run(cmd,log,env=None):
    with log.open('w') as f:return subprocess.run(cmd,env=clean_env(env),stdout=f,stderr=subprocess.STDOUT,timeout=180).returncode

def require_defect(cmd,log,env,stage):
    code=run(cmd,log,env)
    output=log.read_text()
    if code!=1 or '[  FAILED  ] Hyperbolic.' not in output or 'hyperbolic: rejected at row' not in output or 'stage='+stage+' ' not in output:
        raise RuntimeError('defect failed outside intended numerical/state/loader assertion: '+str(log))

def validate(directory,seed=SEED,count=512):
    if not(0<=seed<1<<64 and 0<=count<=10000):raise ValueError('seed/count outside bounds')
    if (directory/'hyperbolic.corpus').stat().st_size>16*1024*1024:raise ValueError('reference file exceeds bound')
    data=(directory/'hyperbolic.corpus').read_bytes()
    pin=(directory/'hyperbolic.sha256').read_text()
    if pin!=hashlib.sha256(data).hexdigest()+'  hyperbolic.corpus\n':raise ValueError('hyperbolic SHA differs')
    if b'\r' in data or not data.endswith(b'\n'):raise ValueError('noncanonical LF')
    lines=data.decode('ascii').splitlines()
    if len(lines)<2:raise ValueError('missing headers')
    expected_header='# hyperbolic-v1 seed=%d count=%d MPFR-directed-1200/2400 mpmath-independent'%(seed,count)
    if lines[0]!=expected_header:raise ValueError('wrong requested population metadata')
    if lines[1]!='# width input sinh-target/flags/residual-low/high cosh-target/flags/residual-low/high tanh-target/flags/residual-low/high; residual scale=2^30 ULP':raise ValueError('wrong column/scale metadata')
    rows=[line.split() for line in lines[2:]]
    expected=[(width,word) for width in (64,32) for word in population(width,seed,count)]
    if len(rows)!=len(expected):raise ValueError('omitted/extra rows')
    for row,(width,word) in zip(rows,expected):
        if len(row)!=14 or row[0]!=str(width) or row[1]!=format(word,'0%dx'%(width//4)):raise ValueError('wrong input/population/order')
    return data

def verify_candidate(test,directory,data,log,inherited=None):
    env=dict(clean_env(inherited),GMATH_HYPERBOLIC_CORPUS_DIR=str(directory))
    if run([str(test)],log,env):raise RuntimeError('positive family control failed')
    output=log.read_text();rows=len(data.decode().splitlines())-2
    ran=re.findall(r'\[ RUN\s+\]\s+Hyperbolic\.(\w+)',output)
    passed=set(re.findall(r'\[\s+OK\s+\]\s+Hyperbolic\.(\w+)',output))
    skipped=set(re.findall(r'\[\s+SKIPPED\s+\]\s+Hyperbolic\.(\w+)',output))
    if len(ran)!=5 or set(ran)!=TEST_NAMES or passed|skipped!=TEST_NAMES or skipped-{'PreserveFlushToZeroControlAndState'}:
        raise RuntimeError('candidate omitted required family tests')
    loaded=[Path(line.removeprefix('hyperbolic: loaded ')).resolve() for line in output.splitlines() if line.startswith('hyperbolic: loaded ')]
    if not loaded or any(path!=(directory/'hyperbolic.corpus') for path in loaded):
        raise RuntimeError('candidate ignored requested reference directory')
    if 'hyperbolic: %d rows;'%rows not in output:
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
        print('hyperbolic: complete requested fresh population/SHA/path/count/public API checks passed');return
    # Reference faults exercise the actual test loader/numerical/state checks;
    # every disposable source/object/binary is reclaimed before returning.
    with tempfile.TemporaryDirectory(prefix='reference-',dir=a.work) as temp:
        directory=Path(temp);env_bad=dict(env,GMATH_HYPERBOLIC_CORPUS_DIR=str(directory))
        lines=data.decode().splitlines()
        variants={'empty':'','missing-newline':data.decode().rstrip('\n'),'truncated':'\n'.join(lines[:2]+[lines[2].split()[0]])+'\n',
                  'wrong-width':'\n'.join(lines[:2]+[lines[2].replace('64 ','16 ',1)]+lines[3:])+'\n',
                  'oversized-word':'\n'.join(lines[:2]+[lines[2].replace('0000000000000000','f'*80,1)]+lines[3:])+'\n',
                  'oversized-residual':'\n'.join(lines[:2]+[lines[2].replace(' 0 0 ', ' '+'9'*80+' 0 ',1)]+lines[3:])+'\n',
                  'wrong-column-header':'\n'.join([lines[0],lines[1].replace('scale=2^30','scale=2^29')]+lines[2:])+'\n'}
        # Zero is an independently exact input, so changing its target must fail.
        fields=lines[2].split();fields[2]='3ff0000000000000'
        variants['wrong-target']='\n'.join(lines[:2]+[' '.join(fields)]+lines[3:])+'\n'
        fields=lines[2].split();fields[3]='2'
        variants['wrong-flags']='\n'.join(lines[:2]+[' '.join(fields)]+lines[3:])+'\n'
        for name,text in variants.items():
            (directory/'hyperbolic.corpus').write_text(text)
            require_defect([str(a.test)],a.work/(name+'.log'),env_bad,
                'accuracy' if name=='wrong-target' else 'reference' if name=='wrong-flags' else 'loader')
        for width in [64,32]:
            one=0x3ff0000000000000 if width==64 else 0x3f800000
            position=next(i for i,line in enumerate(lines[2:],2) if line.split()[:2]==[str(width),format(one,'0%dx'%(width//4))])
            for kind in range(3):
                fields=lines[position].split();field=2+4*kind;fields[field]=format(int(fields[field],16)+8,'0%dx'%(width//4))
                (directory/'hyperbolic.corpus').write_text('\n'.join(lines[:position]+[' '.join(fields)]+lines[position+1:])+'\n')
                require_defect([str(a.test)],a.work/('ordinary-result-%d-%d.log'%(width,kind)),env_bad,'accuracy')
        # Exercise every complete-payload protection even when an attacker
        # updates a digest to match a parse-valid, incomplete/wrong population.
        reordered=lines[:2]+[lines[3],lines[2]]+lines[4:]
        duplicate=lines[:2]+[lines[3],lines[3]]+lines[4:]
        validators={
            'omission':('\n'.join(lines[:-1])+'\n').encode(),
            'order':('\n'.join(reordered)+'\n').encode(),
            'duplicate':('\n'.join(duplicate)+'\n').encode(),
            'CRLF':data.replace(b'\n',b'\r\n'),
            'seed':data.replace(b'seed=20261105',b'seed=20261104',1),
            'columns':data.replace(b'scale=2^30',b'scale=2^29',1),
        }
        for name,payload in validators.items():
            (directory/'hyperbolic.corpus').write_bytes(payload)
            (directory/'hyperbolic.sha256').write_text(hashlib.sha256(payload).hexdigest()+'  hyperbolic.corpus\n')
            try:validate(directory)
            except ValueError:pass
            else:raise RuntimeError('payload defect escaped: '+name)
        (directory/'hyperbolic.corpus').write_bytes(data)
        (directory/'hyperbolic.sha256').write_text('0'*64+'  hyperbolic.corpus\n')
        try:validate(directory)
        except ValueError:pass
        else:raise RuntimeError('wrong digest escaped')
        for name,bounds in [('interval-inverted',('1','0')),('interval-outside',('-536870914','0'))]:
            fields=lines[2].split();fields[4:6]=bounds
            (directory/'hyperbolic.corpus').write_text('\n'.join(lines[:2]+[' '.join(fields)]+lines[3:])+'\n')
            require_defect([str(a.test)],a.work/(name+'.log'),env_bad,'reference' if name=='interval-inverted' else 'loader')
        # A parse-valid changed residual need not violate a one-ULP result
        # contract. Its integrity belongs to the complete-payload digest gate.
        fields=lines[2].split();fields[4:6]=['-1','0']
        shifted=('\n'.join(lines[:2]+[' '.join(fields)]+lines[3:])+'\n').encode()
        (directory/'hyperbolic.corpus').write_bytes(shifted)
        (directory/'hyperbolic.sha256').write_text(hashlib.sha256(data).hexdigest()+'  hyperbolic.corpus\n')
        try:validate(directory)
        except ValueError:pass
        else:raise RuntimeError('residual digest mutation escaped')
        # Demonstrate that a two-zero-row fake fresh report cannot pass the
        # public requested-population wrapper, even with a matching new digest.
        zero_rows=[next(line for line in lines[2:] if line.split()[:2]==[str(width),'0'*(width//4)]) for width in [64,32]]
        subset=('\n'.join(lines[:2]+zero_rows)+'\n').encode();(directory/'hyperbolic.corpus').write_bytes(subset)
        (directory/'hyperbolic.sha256').write_text(hashlib.sha256(subset).hexdigest()+'  hyperbolic.corpus\n')
        code=run([sys.executable,__file__,'--fresh','--seed',str(SEED),'--count','512','--test',str(a.test),'--directory',str(directory),'--work',str(directory/'fresh-control')],a.work/'fresh-truncation.log')
        if code!=1 or 'omitted/extra rows' not in (a.work/'fresh-truncation.log').read_text():raise RuntimeError('truncated fresh sample escaped requested population check')
        # The real test with its directory environment deliberately ignored
        # still passes its default data. The wrapper must reject that context.
        wrapper=directory/'ignore-directory.py'
        wrapper.write_text('#!'+sys.executable+'\nimport os\nos.environ.pop("GMATH_HYPERBOLIC_CORPUS_DIR",None)\nos.execv('+repr(str(a.test))+', ['+repr(str(a.test))+'])\n');wrapper.chmod(0o755)
        (directory/'hyperbolic.corpus').write_bytes(data)
        (directory/'hyperbolic.sha256').write_text(hashlib.sha256(data).hexdigest()+'  hyperbolic.corpus\n')
        try:verify_candidate(wrapper,directory,data,a.work/'ignored-directory.log')
        except RuntimeError as error:
            if 'ignored requested reference directory' not in str(error):raise
        else:raise RuntimeError('ignored directory escaped actual path check')
    hostile=dict(env,GTEST_FILTER='NoSuchSuite.*',GTEST_TOTAL_SHARDS='37',GTEST_SHARD_INDEX='36',GTEST_FAIL_FAST='1')
    verify_candidate(a.test,a.directory,data,a.work/'filter-shard-neutralized.log',hostile)
    with tempfile.TemporaryDirectory(prefix='filter-',dir=a.work) as temp:
        wrapper=Path(temp)/'filtered.py'
        wrapper.write_text('#!'+sys.executable+'\nimport os\nos.execv('+repr(str(a.test))+', ['+repr(str(a.test))+', "--gtest_filter=Hyperbolic.IndependentFamilyCorpusAndCallerState"])\n');wrapper.chmod(0o755)
        try:verify_candidate(wrapper,a.directory,data,a.work/'omitted-tests.log')
        except RuntimeError as error:
            if 'omitted required family tests' not in str(error):raise
        else:raise RuntimeError('omitted family tests escaped exact run-name check')
    source=Path('src/elementary/hyperbolic.c').read_text()
    mutations={
      'double-errno':('static double hy_double(double x,unsigned kind) {','static double hy_double(double x,unsigned kind) { errno=0;'),
      'float-errno':('static float hy_float(float x,unsigned kind) {','static float hy_float(float x,unsigned kind) { errno=0;'),
      'double-mode':('static double hy_double(double x,unsigned kind) {','static double hy_double(double x,unsigned kind) { (void)fesetround(FE_UPWARD);'),
      'float-mode':('static float hy_float(float x,unsigned kind) {','static float hy_float(float x,unsigned kind) { (void)fesetround(FE_UPWARD);'),
      'double-incoming':('static double hy_double(double x,unsigned kind) {','static double hy_double(double x,unsigned kind) { (void)feclearexcept(FE_ALL_EXCEPT);'),
      'float-incoming':('static float hy_float(float x,unsigned kind) {','static float hy_float(float x,unsigned kind) { (void)feclearexcept(FE_ALL_EXCEPT);'),
      'forced-inexact':('volatile double ignored=one+tiny;','volatile double ignored=one+tiny*0.0;'),
      'tiny-underflow':('(void)gmath_underflow(0)','hy_inexact()'),
      'sinh-local-reciprocal':('hy_add(t,hy_div(t,denominator))','t'),
      'cosh-local-square':('hy_mul(t,t)','t'),
      'tanh-denominator':('hy_add(t,two)','hy_add(t,hy_times(two,0.5))'),
      'exp-series':('hy_exp_coeff[n]','hy_exp_coeff[n ? n : 1]'),
      'half-scale':('exponent-half','exponent-half*0'),
      'early-large-approximation':('if(a>=40.0)','if(a>=0.5)'),
      'cosh-reciprocal-sign':('kind==0?hy_neg(reciprocal):reciprocal','hy_neg(reciprocal)'),
      'double-odd-sign':('sign=kind==1?0:word&GMATH_SIGN_BIT','sign=UINT64_C(0)'),
      'early-overflow-double':('0x408633ce8fb9f87e','0x408633ce8fb9f87d'),
      'early-overflow-float':('0x42b2d4fd','0x42b2d4fc'),
      'early-tanh-saturation-double':('0x4034000000000000','0x3ff0000000000000'),
      'early-tanh-saturation-float':('0x41200000','0x3f800000'),
      'signaling-invalid-double':('if(!(a&UINT64_C(0x0008000000000000)))(void)gmath_invalid();','if(0)(void)gmath_invalid();'),
      'signaling-invalid-float':('if(!(a&UINT32_C(0x00400000)))(void)gmath_invalid();','if(0)(void)gmath_invalid();'),
    }
    state_names={'double-errno','float-errno','double-mode','float-mode','double-incoming','float-incoming',
                 'forced-inexact','tiny-underflow','early-overflow-double','early-overflow-float',
                 'signaling-invalid-double','signaling-invalid-float'}
    variants={name:(source.replace(before,after),'state' if name in state_names else 'accuracy') for name,(before,after) in mutations.items()}
    for name,(before,after) in mutations.items():
        if before not in source:raise RuntimeError('source defect anchor missing: '+name)
    # Format-local guards and individual public-result faults complement shared
    # primitive faults; the other format's source remains the genuine control.
    for width,start,end in [(64,source.index('static double hy_double'),source.index('static uint32_t hy_fbits')),
                            (32,source.index('static float hy_float'),source.index('double gmath_sinh'))]:
        body=source[start:end]
        for label,before,after in [('tiny-underflow','(void)gmath_underflow(0)','hy_inexact()'),
                                   ('tiny-inexact','else hy_inexact();','else (void)0;')]:
            if before not in body:raise RuntimeError('format-local guard anchor missing')
            variants['format-%d-%s'%(width,label)]=(source[:start]+body.replace(before,after)+source[end:],'state')
        typ='double' if width==64 else 'float';suffix='' if width==64 else 'f';dispatch='hy_double' if width==64 else 'hy_float'
        bits='gmath_bits' if width==64 else 'hy_fbits';one='UINT64_C(0x3ff0000000000000)' if width==64 else 'UINT32_C(0x3f800000)';offset='0x1p-48' if width==64 else '0x1p-18f'
        for kind,fn in enumerate(['sinh','cosh','tanh']):
            before='%s gmath_%s%s(%s x){return %s(x,%d);}'%(typ,fn,suffix,typ,dispatch,kind)
            after='%s gmath_%s%s(%s x){%s value=%s(x,%d);return %s(x)==%s?value+%s:value;}'%(typ,fn,suffix,typ,typ,dispatch,kind,bits,one,offset)
            if before not in source:raise RuntimeError('public format-specific anchor missing')
            variants['result-%s%s'%(fn,suffix)]=(source.replace(before,after),'accuracy')
    for fn,typ,dispatch,kind,bits,one,bad in [
        ('sinh','double','hy_double',0,'gmath_bits','UINT64_C(0x3ff0000000000000)','gmath_double(gmath_bits(value)^GMATH_SIGN_BIT)'),
        ('tanh','double','hy_double',2,'gmath_bits','UINT64_C(0x3ff0000000000000)','gmath_double(GMATH_QNAN_BITS)'),
        ('coshf','float','hy_float',1,'hy_fbits','UINT32_C(0x3f800000)','0.0f'),
        ('tanhf','float','hy_float',2,'hy_fbits','UINT32_C(0x3f800000)','2.0f')]:
        before='%s gmath_%s(%s x){return %s(x,%d);}'%(typ,fn,typ,dispatch,kind)
        after='%s gmath_%s(%s x){%s value=%s(x,%d);return fegetround()!=FE_TONEAREST&&%s(x)==%s?%s:value;}'%(typ,fn,typ,typ,dispatch,kind,bits,one,bad)
        variants['directed-sanity-'+fn]=(source.replace(before,after),'sanity')
    cc=shlex.split(os.environ['HYP_CC']);cxx=shlex.split(os.environ['HYP_CXX'])
    cflags=shlex.split(os.environ['HYP_CFLAGS']);link=shlex.split(os.environ['HYP_LINK'])
    objects=shlex.split(os.environ['HYP_TEST_OBJ'])+shlex.split(os.environ.get('HYP_HELPER_OBJ',''))
    no_control_writes(Path(os.environ['HYP_RUNTIME_OBJ']))
    with tempfile.TemporaryDirectory(prefix='source-',dir=a.work) as temp:
        directory=Path(temp);path=directory/'hyperbolic.c';obj=directory/'hyperbolic.o';exe=directory/'test'
        # A write followed by restoration evades before/after mode snapshots,
        # so calibrate the object-level prohibition with actual compiled code.
        restored=source.replace('static double hy_double(double x,unsigned kind) {',
            'static double hy_double(double x,unsigned kind) { int saved=fegetround(); (void)fesetround(FE_TONEAREST); (void)fesetround(saved);')
        path.write_text('#include <fenv.h>\n'+restored)
        if run(cc+cflags+['-Isrc/elementary','-c',str(path),'-o',str(obj)],a.work/'restored-control-compile.log'):raise RuntimeError('control-write fixture failed to compile')
        try:no_control_writes(obj)
        except ValueError:pass
        else:raise RuntimeError('restored control write escaped scoped object gate')
        for name,(variant,stage) in variants.items():
            path.write_text('#include <errno.h>\n#include <fenv.h>\n'+variant)
            if run(cc+cflags+['-Isrc/elementary','-c',str(path),'-o',str(obj)],a.work/(name+'-compile.log')):raise RuntimeError('defect compile failed: '+name)
            if run(cxx+objects+[str(obj),os.environ['HYP_ARCHIVE']]+link+['-o',str(exe)],a.work/(name+'-link.log')):raise RuntimeError('defect link failed: '+name)
            require_defect([str(exe)],a.work/(name+'.log'),env,stage)
    print('hyperbolic: positive; loader, ordinary accuracy, residual, integrity, fresh population/path controls; %d numerical/state source defects and restored-control object fault passed'%len(variants))
if __name__=='__main__':main()
