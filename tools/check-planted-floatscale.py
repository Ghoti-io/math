#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Float scaling/decomposition source, state, payload and oracle controls."""
import os
import re
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


def run(args,log,environment=None):
    with log.open('w') as out:
        result=subprocess.run(args,stdout=out,stderr=subprocess.STDOUT,env=environment,timeout=60,check=False)
    if result.returncode not in (0,1):raise RuntimeError('unexpected status%d: %s\n%s'%(result.returncode,args,log.read_text()[-3000:]))
    return result.returncode


def fresh(binary,directory,seed,count):
    directory=Path(directory).resolve();lines=(directory/'float_scale.corpus').read_text().splitlines()
    population=sum(bool(line) and not line.startswith('#') for line in lines)
    if lines[2]!='# seed %d count %d fresh True entries %d'%(int(seed),int(count),population):raise RuntimeError('fresh metadata/count mismatch')
    with tempfile.TemporaryDirectory(prefix='floatscale-selection-') as temporary:
        stage=Path(temporary);env=dict(os.environ,GMATH_FLOATSCALE_CORPUS_DIR=str(directory))
        args=[str(Path(binary).resolve()),'--gtest_filter=FloatScale.ExactReferencesAllModes','--gtest_brief=1'];log=stage/'selected.log'
        if run(args,log,env) or '%d reference entries from %s'%(population,directory) not in log.read_text():raise RuntimeError('requested Float scale data not selected')
        probe=Path(binary).resolve().parent/'tools'/'probe-float-scale'
        actual=stage/'raw.actual'
        if run([str(probe),str(directory)],actual):raise RuntimeError('fresh raw/state probe failed')
        if actual.read_bytes()!=(directory/'float_scale-special.hash').read_bytes():raise RuntimeError('fresh raw/state hashes differ')
        empty=stage/'empty';empty.mkdir();env['GMATH_FLOATSCALE_CORPUS_DIR']=str(empty);log=stage/'empty.log'
        if run(args,log,env)!=1 or 'missing Float scale corpus: '+str(empty) not in log.read_text():raise RuntimeError('ignored directory escaped empty control')
    print('Float scale fresh: requested metadata, %d rows and directory verified'%population,flush=True)


def main():
    if len(sys.argv)>1:
        if len(sys.argv)!=6 or sys.argv[1]!='--verify-fresh':raise RuntimeError('usage: --verify-fresh BINARY DIR SEED COUNT')
        fresh(*sys.argv[2:]);return 0
    env=os.environ;work=Path(env['PLANT_WORK']);work.mkdir(parents=True,exist_ok=True)
    cc,cflags=shlex.split(env['PLANT_CC']),shlex.split(env['PLANT_CFLAGS'])
    cxx,ldflags=shlex.split(env['PLANT_CXX']),shlex.split(env['PLANT_LDFLAGS'])
    original=Path('src/elementary/float_scale.c').read_text()
    plants=[
      ('snan-invalid','if ((fs_b & 0x00400000u) == 0) { (void)gmath_invalid();','if ((fs_b & 0x00400000u) == 0) { (void)0;'),
      ('canonical-nan','return fs_value(FS_NAN);','return fs_value(FS_NAN|1u);'),
      ('normal-exponent','*fs_e=(int)(fs_a>>23);','*fs_e=(int)(fs_a>>23)+1;'),
      ('subnormal-exponent','*fs_e=1-(int)fs_shift;','*fs_e=2-(int)fs_shift;'),
      ('fraction-exponent','(126u<<23)','(127u<<23)'),
      ('frexp-output-exponent','*e=fs_e-126;','*e=fs_e-127;'),
      ('special-output-exponent','if (e != NULL) { *e=0;','if (e != NULL) { *e=1;'),
      ('null-output','uint32_t fs_b=fs_word(x),fs_a=fs_b&FS_ABS;','uint32_t fs_b=fs_word(x),fs_a=fs_b&FS_ABS; if (e == NULL) return fs_value(FS_NAN);'),
      ('ilogb-invalid','if (fs_a>=FS_INF) {(void)gmath_invalid();','if (fs_a>=FS_INF) {(void)0;'),
      ('ilogb-zero-invalid','if (fs_a==0) {(void)gmath_invalid();','if (fs_a==0) {(void)0;'),
      ('ilogb-zero-sentinel','return GMATH_ILOGB0;','return 0;'),
      ('ilogb-finite','return fs_e-127;','return fs_e-126;'),
      ('scale-direction','int fs_ne=fs_e+fs_k;','int fs_ne=fs_e-fs_k;'),
      ('scale-normal-pack','((uint32_t)fs_ne<<23)','((uint32_t)(fs_ne-1)<<23)'),
      ('overflow-flags','if (fs_ne>=255) {(void)gmath_overflow(0);','if (fs_ne>=255) {(void)0;'),
      ('far-underflow-flags','if (fs_shift>24u) {(void)gmath_underflow(0);','if (fs_shift>24u) {(void)0;'),
      ('tie-even','(fs_rem==fs_half&&(fs_q&1u))','(fs_rem==fs_half)'),
      ('subnormal-underflow-flags','if (fs_q<FS_HIDDEN) { (void)gmath_underflow(0);','if (fs_q<FS_HIDDEN) { (void)0;'),
      ('after-round-tininess','if (fs_q<FS_HIDDEN)','if (fs_q<=FS_HIDDEN)'),
      ('rounded-normal-inexact','fs_inexact();','(void)0;'),
      ('alias-exponent','return gmath_scalbnf(x,n);','return gmath_scalbnf(x,-(n>512?512:(n< -512? -512:n)));'),
      ('errno','float gmath_scalbnf(float x,int n) {','float gmath_scalbnf(float x,int n) { errno=0;'),
      ('mode','float gmath_scalbnf(float x,int n) {','float gmath_scalbnf(float x,int n) { (void)fesetround(FE_TONEAREST);'),
      ('incoming-flags','float gmath_scalbnf(float x,int n) {','float gmath_scalbnf(float x,int n) { (void)feclearexcept(FE_ALL_EXCEPT);')]
    plants += [('ilogb-infinity-sentinel','fs_a>FS_INF?GMATH_ILOGBNAN:INT_MAX','fs_a>FS_INF?GMATH_ILOGBNAN:0'),
               ('ilogb-nan-sentinel','fs_a>FS_INF?GMATH_ILOGBNAN:INT_MAX','fs_a>FS_INF?0:INT_MAX')]
    for api,signature in (('ldexpf','float gmath_ldexpf(float x,int n) {'),
                          ('frexpf','float gmath_frexpf(float x,int * e) {'),
                          ('ilogbf','int gmath_ilogbf(float x) {')):
        for name,statement in (('errno','errno=0;'),('mode','(void)fesetround(FE_TONEAREST);'),
                               ('incoming-flags','(void)feclearexcept(FE_ALL_EXCEPT);')):
            plants.append((api+'-'+name,signature,signature+' '+statement))
    for variant in ('default','portable'):
        flags=cflags+(['-DGMATH_FLOATSCALE_PORTABLE_BITS'] if variant=='portable' else [])
        preprocessed=subprocess.run(cc+flags+['-E','src/elementary/float_scale.c'],capture_output=True,text=True,timeout=60,check=True).stdout
        builtin='__builtin_clz' in preprocessed
        local=plants+([('leading-bit-clz','__builtin_clz(fs_a)-8u','__builtin_clz(fs_a)-7u')] if builtin else
                      [('leading-bit-loop','while ((fs_a<<fs_shift)<FS_HIDDEN)','while ((fs_a<<fs_shift)<=FS_HIDDEN)')])
        if variant=='portable' and builtin:raise RuntimeError('portable profile did not disable builtin normalization')
        print('Float scale '+variant+' normalization: '+('builtin' if builtin else 'loop'),flush=True)
        for name,old,new in [('control',None,None)]+local:
            stage=work/(variant+'-'+name);stage.mkdir(parents=True,exist_ok=True);text=original
            if old is not None:
                tokens=re.findall(r'[A-Za-z_][A-Za-z_0-9]*|[0-9]+[A-Za-z_0-9]*|>>|<<|==|!=|<=|>=|&&|\|\||[^\s]',old)
                pattern=r'\s*'.join(map(re.escape,tokens))
                if len(re.findall(pattern,text))!=1:raise RuntimeError('plant anchor must match once: '+name)
                text=re.sub(pattern,lambda unused:new,text,count=1)
            source=stage/'float_scale.c';source.write_text('#include <errno.h>\n#include <fenv.h>\n'+text)
            shutil.copyfile('src/elementary/elem_common.h',stage/'elem_common.h')
            obj=stage/'float_scale.o';binary=stage/'testFloatScale'
            if run(cc+flags+['-c',str(source),'-o',str(obj)],stage/'compile.log'):raise RuntimeError('plant compile failed: '+name)
            if run(cxx+['-o',str(binary),env['PLANT_TEST_OBJ'],str(obj)]+ldflags,stage/'link.log'):raise RuntimeError('plant link failed: '+name)
            result=run([str(binary),'--gtest_brief=1'],stage/'test.log')
            if result!=(0 if old is None else 1):raise RuntimeError('plant escaped/control failed: '+variant+'/'+name)
            print('  ok   Float scale '+variant+'/'+name+(' passes' if old is None else ' detected'),flush=True)
    payloads=('float_scale.corpus','scalbnf.corpus','frexpf.corpus','ilogbf.corpus','float_scale-special.hash')
    for name in payloads:
        stage=work/('checksum-'+name);stage.mkdir(parents=True,exist_ok=True)
        for payload in payloads:shutil.copyfile(Path('tests/corpus')/payload,stage/payload)
        path=stage/name;data=path.read_bytes();path.write_bytes(data[:-1]+b'x')
        if run([sys.executable,'tools/check-floatscale-reference.py',str(stage)],stage/'test.log')!=1:raise RuntimeError('payload corruption escaped '+name)
        print('  ok   Float scale payload '+name+' corruption detected',flush=True)
    output=work/'raw-control.txt'
    if run([env['PLANT_RAW_PROBE']],output):raise RuntimeError('raw probe control failed')
    if run([sys.executable,'tools/check-floatscale-output.py',str(output)],work/'raw-control.log'):raise RuntimeError('raw comparison control failed')
    lines=output.read_text().splitlines(keepends=True)
    for index in range(len(lines)):
        changed=list(lines);key,value=changed[index].split();changed[index]=key+' '+('0' if value!='0' else '1')+'\n'
        path=work/('raw-field%d.txt'%index);path.write_text(''.join(changed))
        if run([sys.executable,'tools/check-floatscale-output.py',str(path)],work/('raw-field%d.log'%index))!=1:raise RuntimeError('output field corruption escaped')
    print('  ok   Float scale all four output-field corruptions detected',flush=True)
    sys.path.insert(0,str(Path('tools/oracle').resolve()));import oracle
    try:image,_=oracle.check_pin(timeout=60)
    except oracle.Unavailable as error:
        if oracle.REQUIRED:raise RuntimeError('pinned Float scale oracle required: '+str(error)) from error
        print('  SKIPPED pinned Float scale oracle controls: '+str(error),flush=True);return 0
    generator=Path('tools/oracle/gen_corpus_float_scale.py').read_text()
    faults=[('mpfr-rounding','round=gmpy2.RoundToNearest','round=gmpy2.RoundDown'),
      ('after-round-flags','(result&~SIGN)<0x00800000','(result&~SIGN)<=0x00800000'),
      ('special-invalid','if a>INF:return QNAN,int(signaling(raw))','if a>INF:return QNAN,0'),
      ('decomposition-exponent','e=floor_log2(q)+1','e=floor_log2(q)+2')]
    for name,old,new in [('control',None,None)]+faults:
        stage=work/('oracle-'+name);stage.mkdir(parents=True,exist_ok=True)
        if old is not None and generator.count(old)!=1:raise RuntimeError('oracle anchor must match once: '+name)
        source=stage/'gen_corpus_float_scale.py';source.write_text(generator if old is None else generator.replace(old,new,1))
        shutil.copyfile('tools/oracle/gen_corpus_floattrig.py',stage/'gen_corpus_floattrig.py')
        result=oracle.engine_run(image,['python',str(source.resolve()),'--out',str((stage/'references').resolve()),'--seed','777','--count','0'],capture=True,timeout=60)
        (stage/'test.log').write_text(result.stdout+result.stderr)
        if old is None:
            if result.returncode!=0:raise RuntimeError('oracle positive control failed: '+result.stderr[-3000:])
        elif result.returncode!=1 or not any(message in result.stderr for message in ('Fraction/MPFR disagreement','fixed boundary control failed')):
            raise RuntimeError('oracle fault escaped/wrong failure: '+name)
        print('  ok   Float scale oracle '+name+(' passes' if old is None else ' detected'),flush=True)
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,OSError,KeyError,subprocess.SubprocessError) as error:
        print('check-planted-floatscale: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
