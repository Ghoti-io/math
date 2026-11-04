#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Compile numerical, state, range, ABI and corpus faults; require rejection."""
import argparse, hashlib, json, os, re, shlex, shutil, signal, subprocess, sys
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',required=True,type=Path);ap.add_argument('--work',required=True,type=Path);ap.add_argument('--archive',type=Path);ap.add_argument('--tininess-only',action='store_true');ap.add_argument('--retained-caller',type=Path);args=ap.parse_args()
    root=Path(__file__).resolve().parent.parent;work=args.work.resolve();work.mkdir(parents=True,exist_ok=True)
    cc=shlex.split(os.environ.get('LONG_DOUBLE_SCALE_CC','cc'));flags=shlex.split(os.environ.get('LONG_DOUBLE_SCALE_FLAGS',''))+['-fno-lto']
    checker=root/'tools/check-long-double-scale.py';abi=root/'tools/check-long-double-scale-abi.py'
    def execute(command,input=None,timeout=180,env=None):
        child=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,start_new_session=True)
        try:
            out,err=child.communicate(input,timeout=timeout)
            return subprocess.CompletedProcess(command,child.returncode,out,err)
        except subprocess.TimeoutExpired:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            child.communicate(timeout=5)
            raise AssertionError('controller subprocess deadline exceeded: '+str(command)) from None
        finally:
            if child.poll() is None:
                try:os.killpg(child.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                child.communicate(timeout=5)
    def run(command,log,**kw):
        p=execute(command,**kw);log.write_text(p.stdout+p.stderr);return p
    minnormal_anchor='else if(inexact) lds_raise_inexact();'
    minnormal_fault='else if(inexact) {if(!adjacent && ld_top(&v)+LD_BASE==minimum && !ld_any_below(&v,ld_top(&v))) lds_raise_underflow();else lds_raise_inexact();}'
    if args.tininess_only:
        p=run([sys.executable,str(checker),'--probe',str(args.probe.resolve()),'--tininess-only'],work/'positive.log');assert p.returncode==0,'retained tininess positive failed'
        source=work/'src/elementary';source.mkdir(parents=True)
        for path in (root/'src/elementary').glob('*.h'):shutil.copy2(path,source/path.name)
        shutil.copy2(root/'src/elementary/long_double_scale.c',source/'long_double_scale.c')
        path=source/'long_double_scale_bits.h';text=path.read_text();assert text.count(minnormal_anchor)==1;path.write_text(text.replace(minnormal_anchor,minnormal_fault))
        obj=work/'long_double_scale.o';p=run([*cc,*flags,'-c',str(source/'long_double_scale.c'),'-o',str(obj)],work/'compile.log');assert p.returncode==0
        caller=args.retained_caller.resolve() if args.retained_caller else work/'caller.o'
        if not args.retained_caller:
            p=run([*cc,*flags,'-c',str(root/'tools/probe-long-double-scale.c'),'-o',str(caller)],work/'caller-compile.log');assert p.returncode==0
        if not args.retained_caller:
            p=run([sys.executable,str(abi),'--caller-object',str(caller)],work/'caller-evidence.log');assert p.returncode==0
        binary=work/'probe';p=run([*cc,*flags,str(caller),str(obj),'-lm','-o',str(binary)],work/'link.log');assert p.returncode==0
        p=run([sys.executable,str(checker),'--probe',str(binary),'--tininess-only'],work/'rejection.log')
        assert p.returncode!=0 and 'AssertionError: row ' in p.stderr and 'flags=4' in p.stderr,'rounded-minnormal scaling-only UF fault escaped new witness'
        print('tininess controls: retained true-ABI caller passes; scaling-only UF-at-inexact-rounded-minnormal fault rejects on new IX-only witness')
        return
    assert args.archive,'archive required for complete controls'
    p=run([sys.executable,str(abi),'--self-test'],work/'abi-parser-controls.log');assert p.returncode==0
    p=run([sys.executable,str(checker),'--self-test-parity'],work/'dd-parity-controls.log');assert p.returncode==0
    p=run([sys.executable,str(checker),'--probe',str(args.probe.resolve()),'--corpus',str(root/'tests/corpus/long-double-scale.json'),'--count','4'],work/'positive.log');assert p.returncode==0,'positive control failed'
    for payload in ['', '80 0 0 0 0 0 0 3 0\n','80 0 0 0 0 0 4 3 0 1\n','80 0 0 0 0 0 0 1 0 1\n','999 0 0 0 0 0 0 3 0 1\n','80 5 0 0 0 0 0 3 0 1\n','80 0 0 0 0 0 0 3 32 1\n','80 0 0 0 0 0 0 3 0 2147483648\n','80 0 0 0 0 0 0 3 0 9999999999999999999999999\n','80 0 0 0 0 0 0 3 0 1 extra\n','80 0 0 0 0 0 18446744073709551616 3 0 1\n','80 0 0 0 0 0 0 3 0 1\0junk','80 0 0 0 0 0 0 3 0 1\0junk\n','x'*512]:
        p=execute([str(args.probe.resolve())],input=payload,timeout=10);assert p.returncode==2,'malformed probe input accepted'
    macros_result=execute([*cc,*flags,'-dM','-E','-x','c','/dev/null'],timeout=60);assert macros_result.returncode==0;macros=macros_result.stdout
    x86='#define __x86_64__ ' in macros or '#define __i386__ ' in macros
    wrappers='#define __x86_64__ ' in macros and '#define __LDBL_MANT_DIG__ 64' in macros
    defects=[
      ('scaling-minnormal-uf','long_double_scale_bits.h',minnormal_anchor,minnormal_fault,'numerical'),
      ('round','long_double_scale_bits.h','ld_bit(&a,cut-1)&&(ld_any_below(&a,cut-1)||ld_bit(&a,cut))','ld_bit(&a,cut-1)','numerical'),
      ('dd-residual','long_double_scale_bits.h','r=fmt==106?lds_dd(&a,0):ld_pack(fmt,&a)','r=fmt==106?ld_pack_single(64,&a):ld_pack(fmt,&a)','numerical'),
      ('dd-neighbor','long_double_scale_bits.h','if(c<0) {best=candidate;','if(c<0 && step==0) {best=candidate;','numerical'),
      ('state','long_double_scale.c','ld_raw a=ld_read(x),b={0,0};','(void)gmath_invalid();ld_raw a=ld_read(x),b={0,0};','numerical'),
      ('range','long_double_scale_bits.h','exponent>40000L?40000:exponent< -40000L?-40000:(int)exponent','(int)(short)exponent','numerical'),
      ('underflow','long_double_scale_bits.h','(void)gmath_underflow(0);','lds_raise_inexact();','numerical'),
      ('dd-tie','long_double_scale_bits.h','c=ld_bit(&candidate,ld_top(&gap)) ? 1:-1;','c=ld_bit(&candidate,ld_top(&gap)) ? -1:1;','numerical'),
    ]
    if x86: defects += [
      ('sse-arithmetic','long_double_scale.c','ld_raw a=ld_read(x),b={0,0};','__asm__ volatile("addsd %xmm0, %xmm0");ld_raw a=ld_read(x),b={0,0};','floating arithmetic outside flag helper'),
      ('arithmetic','long_double_scale.c','ld_raw a=ld_read(x),b={0,0};','__asm__ volatile("fadd %st(0), %st(0)");ld_raw a=ld_read(x),b={0,0};','forbidden x87 instruction'),
      ('control','long_double_scale.c','ld_raw a=ld_read(x),b={0,0};','{unsigned short cw=0x37f;__asm__ volatile("fldcw %0"::"m"(cw));}ld_raw a=ld_read(x),b={0,0};','forbidden control write')]
    if wrappers: defects += [
      ('slot','long_double_scale.c','fldt (%rsp)','fldt 8(%rsp)','native80 wrapper operand contract'),
      ('restore','long_double_scale.c','addq $24, %rsp','addq $16, %rsp','native80 wrapper operand contract'),
      ('helper','long_double_scale.c','call gmath_long_double_scale_bytes','call gmath_long_double_scale_bytes+1','native80 wrapper wrong/missing helper'),
      ('cfa','long_double_scale.c','.cfi_adjust_cfa_offset 24','','native80 CFA metadata mismatch')]
    if '#define __s390__ ' in macros or '#define __s390x__ ' in macros:
        defects.append(('s390-sfpc','long_double_scale.c','ld_raw a=ld_read(x),b={0,0};','__asm__ volatile("sfpc %0"::"d"(0));ld_raw a=ld_read(x),b={0,0};','forbidden control write sfpc'))
    if '#define __arm__ ' in macros:
        defects.append(('arm-fpscr','long_double_scale.c','ld_raw a=ld_read(x),b={0,0};','__asm__ volatile("vmsr fpscr, %0"::"r"(0));ld_raw a=ld_read(x),b={0,0};','forbidden control write vmsr'))
    extra_format=80 if '#define __LDBL_MANT_DIG__ 53' in macros else 64
    defects += [
      ('marker-missing','long_double_scale.c','gmath_long_double_scale_format_','gmath_unrecognized_scale_format_','missing/duplicate native format coverage marker'),
      ('marker-duplicate','long_double_scale.c','#include "long_double_scale_bits.h"','#include "long_double_scale_bits.h"\nstatic const unsigned gmath_long_double_scale_format_'+str(extra_format)+' __attribute__((used))='+str(extra_format)+';','missing/duplicate native format coverage marker')]
    for name,filename,old,new,reason in defects:
        case=work/name;source=case/'src/elementary';source.mkdir(parents=True,exist_ok=True);(case/'tools').mkdir(exist_ok=True);(case/'tests').mkdir(exist_ok=True)
        for p in (root/'src/elementary').glob('*.h'):shutil.copy2(p,source/p.name)
        shutil.copy2(root/'src/elementary/long_double_scale.c',source/'long_double_scale.c');shutil.copy2(root/'tools/probe-long-double-scale.c',case/'tools/probe-long-double-scale.c');shutil.copy2(root/'tests/fp_controls.h',case/'tests/fp_controls.h')
        path=source/filename;text=path.read_text();assert text.count(old)==1,(name,'mutation anchor count');path.write_text(text.replace(old,new))
        if reason=='numerical':
            binary=case/'probe';obj=case/'long_double_scale.o';caller=case/'caller.o'
            p=run([*cc,*flags,'-c',str(source/'long_double_scale.c'),'-o',str(obj)],case/'production-compile.log');assert p.returncode==0,name+' production failed to compile'
            p=run([*cc,*flags,'-c',str(root/'tools/probe-long-double-scale.c') if name=='scaling-minnormal-uf' else str(case/'tools/probe-long-double-scale.c'),'-o',str(caller)],case/'caller-compile.log');assert p.returncode==0,name+' caller failed to compile'
            p=run([sys.executable,str(abi),'--caller-object',str(caller)],case/'caller-abi.log');assert p.returncode==0,name+' caller did not retain external public calls'
            p=run([*cc,*flags,str(caller),str(obj),'-lm','-o',str(binary)],case/'compile.log');assert p.returncode==0,name+' failed to link'
            p=run([sys.executable,str(checker),'--probe',str(binary),*(['--tininess-only'] if name=='scaling-minnormal-uf' else ['--count','4'])],case/'rejection.log');assert p.returncode!=0 and 'AssertionError: row ' in p.stderr,name+' missed expected numerical/state rejection'
        else:
            obj=case/'long_double_scale.o';p=run([*cc,*flags,'-c',str(source/'long_double_scale.c'),'-o',str(obj)],case/'compile.log');assert p.returncode==0,name+' failed to compile'
            p=run([sys.executable,str(abi),'--object',str(obj)],case/'rejection.log');assert p.returncode!=0 and reason in p.stderr,name+' missed expected ABI rejection'
        print('long-double scale controls: rejected compiled '+name+' ('+reason+')',flush=True)
    # A caller that includes definitions must fail even when the compiler can
    # inline them. Keep a positive caller object and a compiled guard fault.
    caller=work/'external-caller.o'
    p=run([*cc,*flags,'-c',str(root/'tools/probe-long-double-scale.c'),'-o',str(caller)],work/'external-caller-compile.log');assert p.returncode==0
    p=run([sys.executable,str(abi),'--caller-object',str(caller)],work/'external-caller-positive.log');assert p.returncode==0
    case=work/'caller-definitions';source=case/'src/elementary';source.mkdir(parents=True);(case/'tools').mkdir();(case/'tests').mkdir()
    for path in (root/'src/elementary').glob('*.h'):shutil.copy2(path,source/path.name)
    text=(root/'src/elementary/long_double_scale.c').read_text();anchor='#ifndef GMATH_LONG_DOUBLE_SCALE_RAW_ONLY';assert text.count(anchor)==1
    (source/'long_double_scale.c').write_text(text.replace(anchor,'#if 1'))
    shutil.copy2(root/'tools/probe-long-double-scale.c',case/'tools/probe-long-double-scale.c');shutil.copy2(root/'tests/fp_controls.h',case/'tests/fp_controls.h')
    bad=case/'caller.o';p=run([*cc,*flags,'-c',str(case/'tools/probe-long-double-scale.c'),'-o',str(bad)],case/'compile.log');assert p.returncode==0
    p=run([sys.executable,str(abi),'--caller-object',str(bad)],case/'rejection.log');assert p.returncode!=0 and 'caller defines public wrapper' in p.stderr,'inline-capable caller definitions accepted'
    print('long-double scale controls: external caller passes; compiled caller-definition guard fault rejects',flush=True)
    if wrappers:
        # Patch the range of a real compiled ELF64 FDE while retaining all
        # unwind rows. The new gate must reject coverage ending before ret.
        obj=work/'range-positive.o';p=run([*cc,*flags,'-c',str(root/'src/elementary/long_double_scale.c'),'-o',str(obj)],work/'range-compile.log');assert p.returncode==0
        p=run([sys.executable,str(abi),'--object',str(obj)],work/'range-positive.log');assert p.returncode==0
        frames=execute([os.environ.get('READELF','readelf'),'--debug-dump=frames-interp',str(obj)]).stdout
        symbols=execute([os.environ.get('NM','nm'),str(obj)]).stdout
        address=int(next(line.split()[0] for line in symbols.splitlines() if line.split()[-1].endswith('_gmath_ldexpl')),16)
        match=next(m for m in re.finditer(r'^([0-9a-f]+).*FDE .*pc=([0-9a-f]+)\.\.([0-9a-f]+)',frames,re.M) if int(m[2],16)==address)
        section=work/'frames.bin';tool=os.environ.get('OBJCOPY','objcopy')
        p=execute([tool,'--dump-section','.eh_frame='+str(section),str(obj)]);assert p.returncode==0
        data=bytearray(section.read_bytes());offset=int(match[1],16)+12
        assert int.from_bytes(data[offset:offset+4],'little')==int(match[3],16)-address,'unsupported FDE encoding for planted range control'
        data[offset:offset+4]=(1).to_bytes(4,'little');section.write_bytes(data)
        shortened=work/'range-shortened.o';p=execute([tool,'--update-section','.eh_frame='+str(section),str(obj),str(shortened)]);assert p.returncode==0
        p=run([sys.executable,str(abi),'--object',str(shortened)],work/'range-rejection.log');assert p.returncode!=0 and 'FDE range' in p.stderr,'shortened compiled FDE range accepted'
        print('long-double scale controls: rejected compiled shortened FDE range with unchanged rows',flush=True)
    for label,program in [('header','import time;time.sleep(60)'),('payload','import sys,time;data=sys.stdin.read();print("native 80 size 16 long 64",flush=True);time.sleep(60) if data else sys.exit(2)')]:
        fake=work/('hanging-'+label);fake.write_text('#!'+sys.executable+'\n'+program+'\n');fake.chmod(0o755)
        p=run([sys.executable,str(checker),'--probe',str(fake),'--count','0','--timeout','0.2'],work/('timeout-'+label+'.log'),timeout=10)
        assert p.returncode!=0 and 'probe deadline exceeded' in p.stderr,'nonterminating '+label+' probe escaped bounded rejection'
        if label=='header':
            try:execute([str(fake)],timeout=0.2)
            except AssertionError as error:
                assert 'controller subprocess deadline exceeded' in str(error)
                (work/'controller-timeout.log').write_text(str(error)+'\n')
            else:raise AssertionError('controller failed to kill/reap nonterminating child')
    print('long-double scale controls: initial-header and payload nonterminating probes killed/reaped at bounded deadlines',flush=True)
    # The literal client is compiled separately against the real archive.
    client=work/'client.c';client.write_text('#include "'+str(root/'tests/long_double_scale_native.h')+'"\nint main(int argc,char **argv){return argc==2?ldsc_corpus(argv[1],0):2;}\n')
    binary=work/'client';p=run([*cc,*flags,str(client),str(args.archive.resolve()),'-lm','-o',str(binary)],work/'client-compile.log');assert p.returncode==0,'native client compile failed'
    corpus=root/'tests/corpus';p=run([str(binary),str(corpus)],work/'client-positive.log');assert p.returncode==0,'native corpus positive failed'
    header=execute([str(args.probe.resolve())],input='',timeout=10).stdout.splitlines()[0].split();native=int(header[1])
    for name,kind in [('answer','answer'),('truncated','truncated'),('range-token','range'),('hash-junk','hash'),('duplicate-hash','duplicate'),('empty','empty'),('foreign-operation','operation'),('foreign-operand','operand'),('foreign-controls','controls'),('nul-eof','nul-eof'),('hash-nul','hash-nul'),('hash-overlong','hash-overlong')]:
        case=work/('corpus-'+name);case.mkdir(exist_ok=True)
        for ext in ('corpus','hash'):shutil.copy2(corpus/('long-double-scale.'+ext),case/('long-double-scale.'+ext))
        cp=case/'long-double-scale.corpus';hp=case/'long-double-scale.hash';lines=cp.read_text().splitlines()
        if kind=='answer':
            # Corrupt every format so the actual ABI necessarily observes it.
            lines=[' '.join(line.split()[:10]+['ffffffffffffffff']+line.split()[11:]) for line in lines];cp.write_text('\n'.join(lines)+'\n')
        elif kind=='truncated':cp.write_text(cp.read_text()+'80 0 0\n')
        elif kind=='range':cp.write_text(cp.read_text()+'18446744073709551616 0 0 0 0 0 0 3 0 0 0 0 0\n')
        elif kind=='empty':cp.write_text('')
        elif kind=='hash':hp.write_text(hp.read_text()+'junk\n')
        elif kind=='duplicate':hp.write_text(hp.read_text()*2)
        elif kind=='nul-eof':cp.write_bytes(cp.read_bytes().rstrip(b'\n')+b'\0junk')
        elif kind=='hash-nul':hp.write_bytes(hp.read_bytes().rstrip(b'\n')+b'\0junk')
        elif kind=='hash-overlong':hp.write_bytes(hp.read_bytes()+b'x'*512)
        else:
            for i,line in enumerate(lines):
                tokens=line.split()
                if int(tokens[0])!=native and tokens[1]=='0':
                    if kind=='operation':tokens[1]='1'  # alias: same answer/flags
                    elif kind=='operand':tokens[2]=f'{int(tokens[2],16)^1:016x}'
                    else:tokens[6]=str((int(tokens[6])+1)%4) # mode-independent
                    lines[i]=' '.join(tokens);break
            else:raise AssertionError('foreign input-only corruption row missing')
            cp.write_text('\n'.join(lines)+'\n')
        p=run([str(binary),str(case)],case/'rejection.log');assert p.returncode==1,'corrupt literal payload accepted: '+name
    # Re-pin a changed stored answer to show SHA metadata cannot substitute
    # for recomputing that answer against the current rational oracle.
    case=work/'repinned-answer';case.mkdir(exist_ok=True)
    for ext in ('corpus','hash','json'):shutil.copy2(corpus/('long-double-scale.'+ext),case/('long-double-scale.'+ext))
    cp=case/'long-double-scale.corpus';tokens=cp.read_text().splitlines();row=tokens[0].split();row[10]=f'{int(row[10],16)^1:016x}';tokens[0]=' '.join(row);cp.write_text('\n'.join(tokens)+'\n')
    jp=case/'long-double-scale.json';doc=json.loads(jp.read_text());doc['files'][cp.name]=hashlib.sha256(cp.read_bytes()).hexdigest();jp.write_text(json.dumps(doc))
    p=run([sys.executable,str(checker),'--validate-corpus',str(jp)],case/'rejection.log');assert p.returncode!=0 and 'committed row 1 disagrees with rational oracle' in p.stderr,'repinned wrong answer accepted'
    print('long-double scale controls: positive client passes; twelve corpus/hash corruptions, repinned wrong answer, fourteen malformed byte inputs and two hanging probes reject')
if __name__=='__main__':main()
