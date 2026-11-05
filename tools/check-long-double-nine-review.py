#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Focused regression controls for entry state, bounds, stack and configuration."""
import sys
if not __debug__ or sys.flags.optimize:
    raise SystemExit('long-double nine gates require assertion-enabled Python')
import argparse, hashlib, importlib.util, json, os, re, shlex, shutil, subprocess
from pathlib import Path

def posix_target(macros):
    return '#define _WIN32 ' not in macros and any(name in macros for name in
        ('#define __unix__ ','#define __unix ','#define __linux__ ','#define __APPLE__ '))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--directory',type=Path,default=Path('tests/corpus'));ap.add_argument('--work',type=Path,required=True);ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--section',choices=('all','clients','stack'),default='all');a=ap.parse_args()
    root=Path(__file__).resolve().parent.parent;work=a.work.resolve();work.mkdir(parents=True,exist_ok=True);directory=a.directory.resolve()
    cc=shlex.split(os.environ.get('LONG_DOUBLE_NINE_CC','cc'));flags=shlex.split(os.environ.get('LONG_DOUBLE_NINE_FLAGS',''))+['-fno-lto'];link=shlex.split(os.environ.get('LONG_DOUBLE_NINE_LINK','-lm'))
    def run(label,command,expect=None,env=None,timeout=180):
        p=subprocess.run(command,capture_output=True,text=True,env=env,timeout=timeout);(work/(label+'.log')).write_text(p.stdout+p.stderr)
        if expect is None:assert p.returncode==0,(label,p.stderr)
        else:assert p.returncode!=0 and expect in p.stdout+p.stderr,(label,p.stdout,p.stderr)
        return p
    spec=importlib.util.spec_from_file_location('nine_review_oracle',root/'tools/check-long-double-nine.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    if a.section=='all':
        run('abi-fixtures',[sys.executable,str(root/'tools/check-long-double-nine-abi.py'),'--self-test'])
        # Before-work rejection must leave even invalid/missing output arguments untouched.
        protected=work/'invalid-generation';protected.mkdir(exist_ok=True)
        for ext in ('corpus','hash','json','seeds'):shutil.copy2(directory/('long-double-nine.'+ext),protected/('long-double-nine.'+ext))
        def snapshot():return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in protected.iterdir() if p.is_file()}
        original=snapshot()
        for name in ('check-long-double-nine.py','check-long-double-nine-abi.py','check-long-double-nine-controls.py','prepare-long-double-nine.py','check-long-double-nine-review.py'):
            args=[str(root/'tools'/name),'--directory',str(protected),'--work',str(protected/'forbidden-output')]
            for label,extra,opt in [('O',['-O'],None),('OO',['-OO'],None),('env1',[],'1'),('env2',[],'2')]:
                env=dict(os.environ);env.pop('PYTHONOPTIMIZE',None)
                if opt:env['PYTHONOPTIMIZE']=opt
                run('optimized-'+name+'-'+label,[sys.executable,*extra,*args],expect='assertion-enabled Python',env=env)
                assert snapshot()==original and not (protected/'forbidden-output').exists(),'optimized gate modified outputs'
        for label,seed,count in [('negative-seed',-1,32),('wide-seed',1<<64,32),('negative-count',20261104,-1),('wide-count',20261104,1025)]:
            run(label,[sys.executable,str(root/'tools/check-long-double-nine.py'),'--generate','--directory',str(protected),'--seed',str(seed),'--count',str(count)],expect='ValueError')
            assert snapshot()==original,'invalid generation modified existing references'
    if a.section in ('all','stack'):
        macros=run('compiler-target-macros',[*cc,*flags,'-dM','-E','-x','c','/dev/null']).stdout
        assert posix_target('#define __linux__ 1\n') and posix_target('#define __APPLE__ 1\n')
        assert not posix_target('#define _WIN32 1\n#define __unix__ 1\n') and not posix_target('')
        posix=posix_target(macros)
        if not posix:print('nine stack/state: POSIX guarded-thread and DAZ/FTZ harness skipped for selected non-POSIX target; compiler stack-usage measurement retained')
        # Production stack measurement remains available on non-POSIX targets.
        measurements={};objects={}
        for optimization in (0,2):
            tag='O'+str(optimization);obj=work/(tag+'-runtime.o');binary=work/(tag+'-state')
            run(tag+'-production',[*cc,*flags,'-O'+str(optimization),'-fstack-usage','-c',str(root/'src/elementary/long_double_nine.c'),'-o',str(obj)])
            if posix:
                run(tag+'-harness',[*cc,*flags,'-O'+str(optimization),'-fstack-usage',str(root/'tools/probe-long-double-nine-state.c'),str(obj),*link,'-pthread','-o',str(binary)])
                run(tag+'-bounded-thread',[str(binary)])
            frames=[]
            for path in work.glob(tag+'*.su'):
                if not posix and path.name!=tag+'-runtime.su':continue
                for line in path.read_text().splitlines():
                    fields=line.split('\t');assert len(fields)==3 and fields[2] in ('static','dynamic,bounded'),('unbounded stack usage',line)
                    frames.append({'function':fields[0],'bytes':int(fields[1]),'kind':fields[2]})
            assert frames and sum(f['bytes'] for f in frames)<1024*1024,'fixed frames exceed conservative stack budget'
            measurements[tag]={'frames':frames,'sum_all_frames_bytes':sum(f['bytes'] for f in frames),'largest_frame_bytes':max(f['bytes'] for f in frames),'usable_thread_stack_bytes':2*1024*1024 if posix else None}
            objects[optimization]=obj
        (work/'stack-usage.json').write_text(json.dumps(measurements,indent=2)+'\n')
        if posix and '#define __x86_64__ ' in macros:
            native64=work/'native64.o'
            run('native64-state-production',[*cc,*flags,'-O2','-mlong-double-64','-c',str(root/'src/elementary/long_double_nine.c'),'-o',str(native64)])
            run('native64-state-link',[*cc,*flags,'-O2','-mlong-double-64',str(root/'tools/probe-long-double-nine-state.c'),str(native64),*link,'-pthread','-o',str(work/'native64-state')])
            run('native64-state',[str(work/'native64-state')])

        if posix and '#define __SSE__ ' in macros and ('#define __x86_64__ ' in macros or '#define __i386__ ' in macros):
            # DAZ/FTZ is exercised once, not once per unrelated arithmetic mutation.
            source=work/'state-fault';source.mkdir(exist_ok=True)
            for path in (root/'src/elementary').glob('*.h'):shutil.copy2(path,source/path.name)
            text=(root/'src/elementary/long_double_nine.c').read_text();anchor='ld_raw a=ld_read(x),b=ld_read(y),c={0,0};'
            assert text.count(anchor)==1
            text=text.replace(anchor,'#if defined(__SSE__) && (defined(__i386__) || defined(__x86_64__))\n{unsigned mx;__asm__ volatile("stmxcsr %0":"=m"(mx));if(mx&0x8000u)(void)gmath_invalid();}\n#endif\n  '+anchor)
            (source/'long_double_nine.c').write_text(text);bad=work/'state-fault.o'
            run('state-fault-compile',[*cc,*flags,'-O2','-c',str(source/'long_double_nine.c'),'-o',str(bad)])
            run('state-fault-link',[*cc,*flags,'-O2',str(root/'tools/probe-long-double-nine-state.c'),str(bad),*link,'-pthread','-o',str(work/'state-fault-probe')])
            run('state-fault-reject',[str(work/'state-fault-probe')],expect='nine state:')
        else:print('nine state: conditional FTZ defect skipped for selected unsupported target')
        if a.section=='stack':print('nine selected-target stack/state controls pass');return
    # C client positive, compiled bad seeding, and byte-ceiling rejection.
    client=work/'client.c';client.write_text('#include "'+str(root/'tests/long_double_nine_native.h')+'"\nint main(int n,char **v){return n==2?ld9_corpus(v[1],0):2;}\n')
    binary=work/'client';run('client-compile',[*cc,*flags,'-O2',str(client),str(a.archive.resolve()),*link,'-o',str(binary)])
    run('client-positive',[str(binary),str(directory)])
    oversized=work/'oversized';oversized.mkdir(exist_ok=True)
    with (oversized/'long-double-nine.corpus').open('wb') as stream:stream.truncate(64*1024*1024+1)
    run('oversized-reject',[str(binary),str(oversized)],expect='corpus byte ceiling rejected',timeout=5)
    info=run('native-info',[*cc,*flags,'-dM','-E','-x','c','/dev/null']).stdout
    native=80 if '#define __LDBL_MANT_DIG__ 64' in info else 128 if '#define __LDBL_MANT_DIG__ 113' in info else 106 if '#define __LDBL_MANT_DIG__ 106' in info else 64
    rows=[tuple(int(x,16) for x in line.split()) for line in (directory/'long-double-nine.corpus').open()]
    for label,seed,change in [('spurious-clear',0,'if(!inc)feraiseexcept(FE_INVALID);'),('missing-requested',1,'if(inc)feclearexcept(FE_ALL_EXCEPT);')]:
        case=work/label;case.mkdir(exist_ok=True)
        for h in (root/'tests').glob('*.h'):shutil.copy2(h,case/h.name)
        header=case/'long_double_nine_native.h';text=header.read_text();anchor='int before=fetestexcept(FE_ALL_EXCEPT);';assert text.count(anchor)==1;header.write_text(text.replace(anchor,change+'\n    '+anchor))
        cp=case/'client.c';cp.write_text('#include "long_double_nine_native.h"\nint main(int n,char **v){return n==2?ld9_corpus(v[1],0):2;}\n')
        run(label+'-compile',[*cc,*flags,'-O2',str(cp),str(a.archive.resolve()),*link,'-o',str(case/'client')])
        row=next(r for r in rows if r[0]==native and r[10]==seed and r[16]==1 and r[1]<4 and oracle.expected((*r[:10],0,r[11]))[-1]==1 and (r[1] not in (0,2) or r[11]==(32 if '#define __SIZEOF_LONG__ 4' in info else 64)))
        (case/'long-double-nine.corpus').write_text(oracle.encode(row))
        run(label+'-reject',[str(case/'client'),str(case)],expect='invalid pre-call seed state')
    alternate=work/'alternate';oracle.generate(alternate,20261201,0)
    assert (alternate/'long-double-nine.json').read_bytes()!=(directory/'long-double-nine.json').read_bytes()
    anchor=work/'link-anchor.c';anchor.write_text('int ld9_configured_link(void){return 7;}\n');anchor_obj=work/'link-anchor.o'
    run('link-anchor',[*cc,*flags,'-c',str(anchor),'-o',str(anchor_obj)])
    env=dict(os.environ);env['LONG_DOUBLE_NINE_FLAGS']=shlex.join([*flags,'-DLD9_REQUIRE_CONFIGURED_LINK']);env['LONG_DOUBLE_NINE_LINK']=shlex.join([*link,str(anchor_obj)])
    run('alternate-link-client',[sys.executable,str(root/'tools/check-long-double-nine-controls.py'),'--client-only','--directory',str(alternate),'--work',str(work/'configured-client'),'--archive',str(a.archive.resolve()),'--probe',str(work/'unused-probe')],env=env)
    cxx=shlex.split(os.environ.get('LONG_DOUBLE_NINE_CXX',os.environ.get('CXX','g++')))
    cppflags=[f for f in flags if not f.startswith('-std=')]
    gtest=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','gtest'],text=True))
    unit=work/'unit-client'
    run('unit-compile',[*cxx,*cppflags,'-std=c++17','-O2','-I'+str(root/'tests'),str(root/'tests/unit/test_long_double_nine.cpp'),str(a.archive.resolve()),*link,*gtest,'-pthread','-o',str(unit)])
    unit_env=dict(os.environ);unit_env['GMATH_LONG_DOUBLE_NINE_CORPUS_DIR']=str(alternate)
    run('alternate-unit',[str(unit)],env=unit_env)
    hp=alternate/'long-double-nine.hash';saved_hash=hp.read_bytes();hp.write_bytes(b'broken\n')
    try:run('alternate-unit-selection-reject',[str(unit)],expect='FAILED',env=unit_env)
    finally:hp.write_bytes(saved_hash)
    if a.section=='clients':print('nine client controls: compiled entry-seed faults, byte ceiling, selected alternate directory/link and actual unit selection pass')
    else:print('nine review controls: instruction fixtures, 20 optimized rejections, invalid generation, bounded O0/O2 stack, DAZ/FTZ, compiled entry-seed faults, byte ceiling and alternate directory/link pass')
if __name__=='__main__':main()
