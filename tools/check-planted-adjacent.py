#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Adjacent-value source/state, payload, raw output and pinned oracle controls."""
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile

PAYLOADS=('nextafter-special.corpus','nextafterf-special.corpus','nextafter.corpus','nextafterf.corpus','adjacent-special.hash')


def run(args,log,environment=None):
    with log.open('w') as out:
        result=subprocess.run(args,stdout=out,stderr=subprocess.STDOUT,env=environment,timeout=60,check=False)
    if result.returncode not in (0,1):raise RuntimeError('unexpected status%d: %s\n%s'%(result.returncode,args,log.read_text()[-3000:]))
    return result.returncode


def replace(text,old,new,name):
    tokens=re.findall(r'[A-Za-z_][A-Za-z_0-9]*|[0-9]+[A-Za-z_0-9]*|>>|<<|==|!=|<=|>=|&&|\|\||[^\s]',old)
    pattern=r'\s*'.join(map(re.escape,tokens))
    if len(re.findall(pattern,text))!=1:raise RuntimeError('plant anchor must match once: '+name)
    return re.sub(pattern,lambda unused:new,text,count=1)


def widen_float(raw):
    sign=(raw>>31)<<63;exponent=(raw>>23)&255;mantissa=raw&0x7fffff
    if exponent==255:return sign|(0x7ff<<52)|(mantissa<<29)
    if exponent:return sign|((exponent+896)<<52)|(mantissa<<29)
    if not mantissa:return sign
    leading=mantissa.bit_length()-1
    return sign|((leading+874)<<52)|((mantissa-(1<<leading))<<(52-leading))


def verify_widened(directory):
    for single,name in ((False,'nextafter'),(True,'nextafterf')):
        raw=(directory/(name+'-special.corpus')).read_text().splitlines();expected=[]
        for line in raw[4:]:
            x,y,result,flags=map(lambda word:int(word,16),line.split())
            if single:
                snan=lambda word:(word&0x7fffffff)>0x7f800000 and not word&0x00400000
                if snan(x) or snan(y):continue
                x,y,result=map(widen_float,(x,y,result))
            expected.append('%016x %016x %016x'%(x,y,result))
        header=[raw[0],'# function '+name,raw[2].rsplit(' entries ',1)[0]+' entries '+str(len(expected)),
                '# binary64 words; binary32 inputs/results exactly widened and sNaNs excluded']
        if (directory/(name+'.corpus')).read_text().splitlines()!=header+expected:
            raise RuntimeError('widened adjacent payload differs from certified raw data: '+name)


def fresh(binary,directory,seed,count):
    directory=Path(directory).resolve();populations={}
    for name in ('nextafter','nextafterf'):
        lines=(directory/(name+'-special.corpus')).read_text().splitlines()
        population=sum(bool(line) and not line.startswith('#') for line in lines)
        if lines[1]!='# function '+name+'_raw' or lines[2]!='# seed %d count %d fresh True entries %d'%(int(seed),int(count),population):raise RuntimeError('fresh metadata/count/function mismatch')
        populations[name]=population
    with tempfile.TemporaryDirectory(prefix='adjacent-selection-') as temporary:
        stage=Path(temporary);env=dict(os.environ,GMATH_ADJACENT_CORPUS_DIR=str(directory))
        args=[str(Path(binary).resolve()),'--gtest_filter=Adjacent.ExactReferencesAllModes','--gtest_brief=1'];log=stage/'selected.log'
        if run(args,log,env):raise RuntimeError('fresh adjacent values fail')
        for name,population in populations.items():
            if '%s: %d reference entries from %s'%(name,population,directory) not in log.read_text():raise RuntimeError('requested adjacent data not selected')
        verify_widened(directory)
        probe=Path(binary).resolve().parent/'tools'/'probe-adjacent';actual=stage/'raw.actual'
        if run([str(probe),str(directory)],actual):raise RuntimeError('fresh adjacent raw/state probe failed')
        if actual.read_bytes()!=(directory/'adjacent-special.hash').read_bytes():raise RuntimeError('fresh adjacent raw/state hashes differ')
        empty=stage/'empty';empty.mkdir();env['GMATH_ADJACENT_CORPUS_DIR']=str(empty);log=stage/'empty.log'
        if run(args,log,env)!=1 or 'missing adjacent corpus: '+str(empty) not in log.read_text():raise RuntimeError('ignored directory escaped empty control')
    print('adjacent fresh: requested metadata, populations %s and directory verified'%populations,flush=True)


def raw_loader_controls(probe,work):
    names=('nextafter-special.corpus','nextafterf-special.corpus')
    originals={name:(Path('tests/corpus')/name).read_text().splitlines(keepends=True) for name in names}
    cases=[];base=originals[names[0]]
    def changed(label,index,value):
        rows=list(base);rows[index]=value;cases.append((label,names[0],rows))
    changed('provenance',0,base[0].replace('MPFR 4.2.2','MPFR wrong'))
    changed('function',1,'# function wrong_raw\n')
    changed('columns',3,'# raw wrong-columns\n')
    rows=list(base);rows.pop(0);cases.append(('missing-header',names[0],rows))
    rows=list(base);rows[1],rows[2]=rows[2],rows[1];cases.append(('reordered-header',names[0],rows))
    population=len(base)-4
    changed('truncated-count',2,base[2].replace('entries '+str(population),'entries '+str(population+1)))
    changed('extended-count',2,base[2].replace('entries '+str(population),'entries '+str(population-1)))
    changed('excessive-count',2,base[2].replace('entries '+str(population),'entries 250001'))
    changed('negative-seed',2,base[2].replace('seed 20261027','seed -1'))
    changed('seed-overflow',2,base[2].replace('seed 20261027','seed 18446744073709551616'))
    changed('excessive-random',2,base[2].replace('count 2000','count 50001'))
    changed('duplicate-pair',10,base[9])
    changed('wrong-width',4,base[4][1:])
    changed('trailing-field',4,base[4].rstrip()+' extra\n')
    changed('embedded-NUL',4,base[4].rstrip()+'\0unexpected-trailing-field\n')
    for label,flag in (('reserved-flags','0000000000000002'),('incomplete-underflow','0000000000000008'),('incomplete-overflow','0000000000000004')):
        row=base[4].split();row[3]=flag;changed(label,4,' '.join(row)+'\n')
    row_index=next(i for i,line in enumerate(base[4:],4) if line.split()[3]=='0000000000000001')
    row=base[row_index].split();row[3]='0000000000000003';changed('invalid-with-reserved',row_index,' '.join(row)+'\n')
    rows=list(originals[names[1]]);row=rows[4].split();row[0]='0000000100000000';rows[4]=' '.join(row)+'\n';cases.append(('Float-width',names[1],rows))
    with tempfile.TemporaryDirectory(prefix='adjacent-loader-',dir=work) as temporary:
        stage=Path(temporary)
        def restore():
            for name,rows in originals.items():(stage/name).write_text(''.join(rows))
        restore()
        if run([probe,str(stage)],work/'loader-control.log'):raise RuntimeError('raw loader positive control failed')
        for label,name,rows in cases:
            restore();(stage/name).write_text(''.join(rows))
            if run([probe,str(stage)],work/('loader-'+label+'.log'))!=1:raise RuntimeError('raw loader fault escaped: '+label)
            print('  ok   adjacent raw-loader '+label+' detected',flush=True)
        restore()
        if run([probe,str(stage)],work/'loader-after-control.log'):raise RuntimeError('raw loader final positive control failed')


def widened_controls(work):
    verify_widened(Path('tests/corpus'))
    with tempfile.TemporaryDirectory(prefix='adjacent-widened-',dir=work) as temporary:
        stage=Path(temporary)
        for name in PAYLOADS:shutil.copyfile(Path('tests/corpus')/name,stage/name)
        for name in ('nextafter','nextafterf'):
            path=stage/(name+'.corpus');original=path.read_text();rows=original.splitlines(keepends=True)
            changes=[('value',rows[:4]+['0000000000000000 0000000000000000 0000000000000001\n']+rows[5:]),
                     ('omission',rows[:-1]),('extra-row',rows+rows[4:5])]
            for label,changed in changes:
                path.write_text(''.join(changed))
                try:verify_widened(stage)
                except RuntimeError:pass
                else:raise RuntimeError('widened payload control escaped '+name+'/'+label)
                path.write_text(original)
                print('  ok   adjacent widened '+name+'/'+label+' detected',flush=True)
        # The raw signaling input must never appear in widened Float evidence.
        path=stage/'nextafterf.corpus';original=path.read_text();rows=original.splitlines(keepends=True)
        population=len(rows)-4;rows[2]=rows[2].replace('entries '+str(population),'entries '+str(population+1))
        path.write_text(''.join(rows)+'7ff8000020000000 0000000000000000 7ff8000000000000\n')
        try:verify_widened(stage)
        except RuntimeError:pass
        else:raise RuntimeError('widened Float signaling inclusion escaped')
        path.write_text(original);verify_widened(stage)
        print('  ok   adjacent widened Float signaling inclusion detected',flush=True)


def dispatch_controls(work):
    # Execute the actual wrapper with a recording engine, never a second oracle.
    import contextlib
    import io
    import types
    path=Path('tools/oracle/oracle.py').resolve();original=path.read_text()
    old='"float_scale", "fresh-float_scale", "adjacent", "fresh-adjacent"):'
    if original.count(old)!=1:raise RuntimeError('dispatch fault anchor must match once')
    omitted=original.replace(old,'"float_scale", "fresh-float_scale"):',1)
    for command in ('adjacent','fresh-adjacent'):
        for faulty,source in ((False,original),(True,omitted)):
            namespace={'__name__':'adjacent_dispatch_control','__file__':str(path)}
            exec(compile(source,str(path),'exec'),namespace)
            calls=[]
            namespace['check_pin']=lambda:('recording-engine','recorded pin')
            def engine(image,argv,**kwargs):
                calls.append(argv);return types.SimpleNamespace(returncode=0)
            namespace['engine_run']=engine;saved=sys.argv
            try:
                sys.argv=['oracle.py',command,'--out',str(work.resolve()/'dispatch-output'),'--seed','777','--count','0']
                with contextlib.redirect_stderr(io.StringIO()):status=namespace['main']()
            finally:sys.argv=saved
            valid=(status==0 and len(calls)==1 and calls[0][0:2]==['python','tools/oracle/gen_corpus_adjacent.py'] and
                   calls[0][calls[0].index('--seed')+1]=='777' and calls[0][calls[0].index('--count')+1]=='0' and
                   ('--fresh' in calls[0])==(command=='fresh-adjacent'))
            if valid==faulty:raise RuntimeError('dispatch control failed/omission escaped '+command)
        print('  ok   adjacent '+command+' dispatch control and actual family-omission fault detected',flush=True)


def main():
    if len(sys.argv)>1:
        if len(sys.argv)!=6 or sys.argv[1]!='--verify-fresh':raise RuntimeError('usage: --verify-fresh BINARY DIR SEED COUNT')
        fresh(*sys.argv[2:]);return 0
    env=os.environ;work=Path(env['PLANT_WORK']);work.mkdir(parents=True,exist_ok=True)
    cc,cflags=shlex.split(env['PLANT_CC']),shlex.split(env['PLANT_CFLAGS'])
    cxx,ldflags=shlex.split(env['PLANT_CXX']),shlex.split(env['PLANT_LDFLAGS'])
    original=Path('src/elementary/adjacent.c').read_text()
    plants=[
      ('nan-x','if (ax>infinity||ay>infinity)','if (ay>infinity)'),
      ('nan-y','if (ax>infinity||ay>infinity)','if (ax>infinity)'),
      ('signaling-x','(ax>infinity&&!(x&quiet))','(0)'),
      ('signaling-y','(ay>infinity&&!(y&quiet))','(0)'),
      ('quiet-x','!(x&quiet)','(x&quiet)'),
      ('quiet-y','!(y&quiet)','(y&quiet)'),
      ('canonical-nan','return infinity|quiet;','return infinity|quiet|1;'),
      ('opposing-zero-equality','if (x==y||(ax==0&&ay==0))','if (x==y)'),
      ('equality-sign','return y;','return x;'),
      ('equality-no-flags','return y;','(void)gmath_underflow(0);return y;'),
      ('zero-direction','return (y&sign)|UINT64_C(1);','return (x&sign)|UINT64_C(1);'),
      ('zero-underflow','if (ax==0) { (void)gmath_underflow(0);','if (ax==0) { (void)0;'),
      ('positive-order','sign+magnitude;','sign-magnitude;'),
      ('negative-order','?sign-magnitude:', '?sign+magnitude:'),
      ('ordering-direction','adjacent_key(x,sign)<adjacent_key(y,sign)','adjacent_key(x,sign)>adjacent_key(y,sign)'),
      ('sign-step','if (upward!=negative)','if (upward==negative)'),
      ('increment','++x;','--x;'),
      ('decrement','--x;','++x;'),
      ('overflow-flags','if (result_magnitude==infinity&&ax<infinity) { (void)gmath_overflow(0);','if (result_magnitude==infinity&&ax<infinity) { (void)0;'),
      ('normal-boundary-flags','else if (result_magnitude<minimum_normal)','else if (result_magnitude<=minimum_normal)'),
      ('zero-result-flags','else if (result_magnitude<minimum_normal)','else if (result_magnitude!=0&&result_magnitude<minimum_normal)'),
      ('subnormal-result-flags','else if (result_magnitude<minimum_normal)','else if (result_magnitude==0&&minimum_normal!=0)'),
      ('float-quiet','UINT64_C(0x00400000)','UINT64_C(0x00200000)'),
      ('float-minimum','UINT64_C(0x00800000)','UINT64_C(0x01000000)'),
      ('double-quiet','UINT64_C(0x0008000000000000)','UINT64_C(0x0004000000000000)'),
      ('double-minimum','UINT64_C(0x0010000000000000)','UINT64_C(0x0020000000000000)')]
    for api,signature in (('nextafter','double gmath_nextafter(double x,double y) {'),
                          ('nextafterf','float gmath_nextafterf(float x,float y) {')):
        for name,statement in (('errno','errno=0;'),('mode','(void)fesetround(FE_TONEAREST);'),
                               ('incoming-flags','(void)feclearexcept(FE_ALL_EXCEPT);')):
            plants.append((api+'-'+name,signature,signature+' '+statement))
        plants.append((api+'-zero-errno',signature,signature+' if(errno==0) errno=E2BIG;'))
        plants.append((api+'-mixed-flags',signature,signature+' if(fetestexcept(FE_ALL_EXCEPT)==(FE_INVALID|FE_DIVBYZERO)) (void)feclearexcept(FE_ALL_EXCEPT);'))
    for name,old,new in [('control',None,None)]+plants:
        stage=work/name;stage.mkdir(parents=True,exist_ok=True)
        text=original if old is None else replace(original,old,new,name)
        source=stage/'adjacent.c';source.write_text('#include <errno.h>\n#include <fenv.h>\n'+text)
        shutil.copyfile('src/elementary/elem_common.h',stage/'elem_common.h')
        obj=stage/'adjacent.o';binary=stage/'testAdjacent'
        if run(cc+cflags+['-c',str(source),'-o',str(obj)],stage/'compile.log'):raise RuntimeError('plant compile failed: '+name)
        if run(cxx+['-o',str(binary),env['PLANT_TEST_OBJ'],str(obj)]+ldflags,stage/'link.log'):raise RuntimeError('plant link failed: '+name)
        result=run([str(binary),'--gtest_brief=1'],stage/'test.log')
        if result!=(0 if old is None else 1):raise RuntimeError('plant escaped/control failed: '+name)
        if (name.endswith('-zero-errno') or name.endswith('-mixed-flags')) and 'Adjacent.SelectedIncomingState' not in (stage/'test.log').read_text():raise RuntimeError('conditional state plant did not reach selected-state guard: '+name)
        print('  ok   adjacent '+name+(' passes' if old is None else ' detected'),flush=True)
    for name in PAYLOADS:
        stage=work/('checksum-'+name);stage.mkdir(parents=True,exist_ok=True)
        for payload in PAYLOADS:shutil.copyfile(Path('tests/corpus')/payload,stage/payload)
        path=stage/name;data=path.read_bytes();path.write_bytes(data[:-1]+b'x')
        if run([sys.executable,'tools/check-adjacent-reference.py',str(stage)],stage/'test.log')!=1:raise RuntimeError('payload corruption escaped '+name)
        print('  ok   adjacent payload '+name+' corruption detected',flush=True)
    output=work/'raw-control.txt'
    if run([env['PLANT_RAW_PROBE']],output):raise RuntimeError('raw probe control failed')
    if run([sys.executable,'tools/check-adjacent-output.py',str(output)],work/'raw-control.log'):raise RuntimeError('raw comparison control failed')
    lines=output.read_text().splitlines(keepends=True)
    for index in range(len(lines)):
        changed=list(lines);key,value=changed[index].split();changed[index]=key+' '+('0' if value!='0' else '1')+'\n'
        path=work/('raw-field%d.txt'%index);path.write_text(''.join(changed))
        if run([sys.executable,'tools/check-adjacent-output.py',str(path)],work/('raw-field%d.log'%index))!=1:raise RuntimeError('output field corruption escaped')
    print('  ok   adjacent all eight output-field corruptions detected',flush=True)
    raw_loader_controls(env['PLANT_RAW_PROBE'],work)
    widened_controls(work)
    dispatch_controls(work)
    sys.path.insert(0,str(Path('tools/oracle').resolve()));import oracle
    try:image,_=oracle.check_pin(timeout=60)
    except oracle.Unavailable as error:
        if oracle.REQUIRED:raise RuntimeError('pinned adjacent oracle required: '+str(error)) from error
        print('  SKIPPED pinned adjacent oracle controls: '+str(error),flush=True);return 0
    generator=Path('tools/oracle/gen_corpus_adjacent.py').read_text()
    faults=[('rational-direction','shrinking=(x<0)==up','shrinking=(x<0)!=up'),
      ('rational-tiny-spacing','),1-bias-m)', '),2-bias-m)'),
      ('mpfr-precision','precision=m+1','precision=m'),
      ('negative-epsilon-in-restricted-context','EPS if up else NEG_EPS','EPS if up else -EPS'),
      ('second-signaling-nan','or (b>inf and not y&quiet)','or False'),
      ('normal-boundary-flags','24 if r<minimum','24 if r<=minimum'),
      ('equality-zero-sign','if x==y or not (a|b):return y,0','if x==y or not (a|b):return x,0')]
    for name,old,new in [('control',None,None)]+faults:
        stage=work/('oracle-'+name);stage.mkdir(parents=True,exist_ok=True)
        if old is not None and generator.count(old)!=1:raise RuntimeError('oracle anchor must match once: '+name)
        source=stage/'gen_corpus_adjacent.py';source.write_text(generator if old is None else generator.replace(old,new,1))
        for helper in ('gen_corpus_float_scale.py','gen_corpus_floattrig.py'):
            shutil.copyfile(Path('tools/oracle')/helper,stage/helper)
        result=oracle.engine_run(image,['python',str(source.resolve()),'--out',str((stage/'references').resolve()),'--seed','777','--count','0'],capture=True,timeout=60)
        (stage/'test.log').write_text(result.stdout+result.stderr)
        if old is None:
            if result.returncode!=0:raise RuntimeError('oracle positive control failed: '+result.stderr[-3000:])
        elif result.returncode!=1 or not any(message in result.stderr for message in ('Fraction/MPFR disagreement','fixed boundary control failed','reference neighbor not exactly representable')):
            raise RuntimeError('oracle fault escaped/wrong failure: '+name)
        print('  ok   adjacent oracle '+name+(' passes' if old is None else ' detected'),flush=True)
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (RuntimeError,OSError,KeyError,subprocess.SubprocessError) as error:
        print('check-planted-adjacent: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
