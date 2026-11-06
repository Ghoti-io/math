#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Actual compiled arithmetic/state/ABI faults and strict literal-client controls."""
import sys
if not __debug__ or sys.flags.optimize:
    raise SystemExit("long-double nine gates require assertion-enabled Python")

import argparse, contextlib, importlib.util, json, os, shlex, shutil, subprocess, sys
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--work',type=Path,required=True);ap.add_argument('--archive',type=Path,required=True);ap.add_argument('--directory',type=Path,default=Path('tests/corpus'));ap.add_argument('--client-only',action='store_true');args=ap.parse_args()
    root=Path(__file__).resolve().parent.parent;work=args.work.resolve();work.mkdir(parents=True,exist_ok=True)
    cc=shlex.split(os.environ.get('LONG_DOUBLE_NINE_CC','cc'));flags=shlex.split(os.environ.get('LONG_DOUBLE_NINE_FLAGS',''))+['-fno-lto']
    directory=args.directory.resolve();link=shlex.split(os.environ.get('LONG_DOUBLE_NINE_LINK','-lm'))
    abi=root/'tools/check-long-double-nine-abi.py';checker=root/'tools/check-long-double-nine.py'
    spec=importlib.util.spec_from_file_location('nine',checker);oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    if args.client_only:
        client=work/'configured-client.c'
        client.write_text('#include "'+str(root/'tests/long_double_nine_native.h')+'"\n#ifdef LD9_REQUIRE_CONFIGURED_LINK\nextern int ld9_configured_link(void);\n#endif\nint main(int n,char **v){\n#ifdef LD9_REQUIRE_CONFIGURED_LINK\nif(ld9_configured_link()!=7)return 3;\n#endif\nreturn n==2?ld9_corpus(v[1],0):2;}\n')
        binary=work/'configured-client'
        subprocess.run([*cc,*flags,str(client),str(args.archive.resolve()),*link,'-o',str(binary)],check=True,timeout=60)
        subprocess.run([str(binary),str(directory)],check=True,timeout=180)
        print('long-double nine configured client: '+str(directory));return
    rows=oracle.load(directory)
    review=[sys.executable,str(root/'tools/check-long-double-nine-review.py'),'--directory',str(directory),'--work',str(work/'review'),'--archive',str(args.archive.resolve())]
    subprocess.run(review,check=True,timeout=600)
    def run(command,log,input=None):
        p=subprocess.run(command,input=input,capture_output=True,text=True,timeout=180);log.write_text(p.stdout+p.stderr);return p
    def expect_reject(command,log,reason=None,input=None):
        p=run(command,log,input);assert p.returncode and (not reason or reason in p.stderr+p.stdout),(command,'fault escaped',p.stdout,p.stderr)
    def numerical_reject(binary,log):
        # The immutable literal/cache population was independently recomputed
        # once above. Reuse those exact answers for each compiled candidate.
        try:
            with log.open('w') as output,contextlib.redirect_stdout(output):oracle.run(binary,rows)
        except AssertionError as error:
            log.write_text(str(error)+'\n');assert 'probe mismatch' in str(error),'fault failed for a nonnumerical reason'
        else:raise AssertionError('compiled numerical fault escaped: '+str(binary))
    def compile_case(name,filename,old,new):
        case=work/name;src=case/'src/elementary';src.mkdir(parents=True,exist_ok=True);(case/'tools').mkdir(exist_ok=True);(case/'tests').mkdir(exist_ok=True)
        for p in (root/'src/elementary').glob('*.h'):shutil.copy2(p,src/p.name)
        shutil.copy2(root/'src/elementary/long_double_nine.c',src/'long_double_nine.c');shutil.copy2(root/'tools/probe-long-double-nine.c',case/'tools/probe-long-double-nine.c');shutil.copy2(root/'tests/fp_controls.h',case/'tests/fp_controls.h');shutil.copy2(root/'tests/long_double_nine_abi.h',case/'tests/long_double_nine_abi.h')
        p=src/filename;text=p.read_text()
        if name in ('quotient-width','quotient-parity','remainder-zero-sign'):
            # These historical plants must still hit the binary-format path;
            # the independent DD supplement plants its own corresponding faults.
            prefix,separator,body=text.partition('static ld_raw ldn_remainder(')
            assert separator and body.count(old)==1,(name,'binary-path anchor count')
            text=prefix+separator+body.replace(old,new,1)
        else:
            assert text.count(old)==(2 if name=='cfa' else 1),(name,'anchor count')
            text=text.replace(old,new,1)
        p.write_text(text)
        obj=case/'runtime.o';result=run([*cc,*flags,'-c',str(src/'long_double_nine.c'),'-o',str(obj)],case/'compile.log');assert not result.returncode,(name,'compile failed')
        return case,obj
    # Positive numerical and actual-object gates precede every fault family.
    with (work/'positive.log').open('w') as output,contextlib.redirect_stdout(output):oracle.run(args.probe.resolve(),rows)
    assert not run([sys.executable,str(abi),'--self-test'],work/'abi-parser.log').returncode
    defects=[
      ('ties-away','long_double_nine_bits.h','if(!current) increment=ld_bit(&a,LD_ZERO_BIT-1);','if(!current) increment=ld_bit(&a,LD_ZERO_BIT-1) && ld_any_below(&a,LD_ZERO_BIT-1);'),
      ('current-tie','long_double_nine_bits.h','(ld_any_below(&a,LD_ZERO_BIT-1)||(magnitude&1))','(ld_any_below(&a,LD_ZERO_BIT-1)||!(magnitude&1))'),
      ('range-after-round','long_double_nine_bits.h','(increment && magnitude==limit)','(increment && magnitude>limit)'),
      ('integer-inexact','long_double_nine_bits.h','if(current && fractional)lds_raise_inexact();','if(0 && current && fractional)lds_raise_inexact();'),
      ('invalid-inexact','long_double_nine_bits.h','lds_raise_invalid();return -(int64_t)maximum-1;','lds_raise_invalid();lds_raise_inexact();return -(int64_t)maximum-1;'),
      ('quotient-width','long_double_nine_bits.h','quotient=((quotient<<1)|(unsigned)take)&127;','quotient=((quotient<<1)|(unsigned)take)&7;'),
      ('quotient-parity','long_double_nine_bits.h','(!cmp && (quotient&1))','(!cmp && !(quotient&1))'),
      ('remainder-zero-sign','long_double_nine_bits.h','if(ld_top(&a)<0)sign=original_sign;','if(ld_top(&a)<0)sign=!original_sign;'),
      ('difference-mode','long_double_nine_bits.h','ldn_round(fmt,&sum,0)','ldn_round(fmt,&sum,2)'),
      ('fma-directed','long_double_nine_bits.h','return ldn_round(fmt,&product,mode);','return ldn_round(fmt,&product,0);'),
      ('fma-zero-sign','long_double_nine_bits.h','product.sign=ps==c.sign?ps:mode==1;','product.sign=0;'),
      ('fma-low-product','long_double_nine_bits.h','uint64_t t=(uint64_t)a->w[i]*b->w[j]+out.w[i+j]+carry;','uint64_t t=(uint64_t)a->w[i]*b->w[j]+out.w[i+j]+carry;if(i+j<520)t=0;'),
      ('snan-second','long_double_nine_bits.h','int invalid=a.invalid||b.invalid||c.invalid;','int invalid=a.invalid||c.invalid;'),
      ('snan-third','long_double_nine_bits.h','int invalid=a.invalid||b.invalid||c.invalid;','int invalid=a.invalid||b.invalid;'),
      ('dd-directed','long_double_nine_bits.h','if(mode>0 && inexact)','if(0 && mode>0 && inexact)'),
      ('dd-directed-overflow','long_double_nine_bits.h','if(mode>0 && ld_cmpmag(&result,&limit)>0)','if(0 && mode>0 && ld_cmpmag(&result,&limit)>0)'),
      ('after-round-tininess','long_double_scale_bits.h','else if(inexact) lds_raise_inexact();','else if(inexact) {if(ld_top(&v)+LD_BASE==minimum && !ld_any_below(&v,ld_top(&v)))lds_raise_underflow();else lds_raise_inexact();}'),
      ('dd-tie','long_double_scale_bits.h','c=ld_bit(&candidate,ld_top(&gap)) ? 1:-1;','c=ld_bit(&candidate,ld_top(&gap)) ? -1:1;'),
      ('underflow','long_double_scale_bits.h','(void)gmath_underflow(0);','lds_raise_inexact();'),
    ]
    # The invalid failure has two branches; target the first (nonfinite/range)
    # with surrounding text to retain a unique mutation anchor.
    defects[4]=('invalid-inexact','long_double_nine_bits.h','if(a.kind!=LD_FINITE || ld_top(&a)>=LD_ZERO_BIT+64) {\n    lds_raise_invalid();','if(a.kind!=LD_FINITE || ld_top(&a)>=LD_ZERO_BIT+64) {\n    lds_raise_invalid();lds_raise_inexact();')
    for name,filename,old,new in defects:
        case,obj=compile_case(name,filename,old,new)
        caller=case/'caller.o';assert not run([*cc,*flags,'-c',str(case/'tools/probe-long-double-nine.c'),'-o',str(caller)],case/'caller-compile.log').returncode
        assert not run([sys.executable,str(abi),'--caller-object',str(caller)],case/'caller-abi.log').returncode
        binary=case/'probe';assert not run([*cc,*flags,str(caller),str(obj),*link,'-o',str(binary)],case/'link.log').returncode
        numerical_reject(binary,case/'rejection.log')
        print('long-double nine controls: rejected compiled '+name,flush=True)
    macros=run([*cc,*flags,'-dM','-E','-x','c','/dev/null'],work/'compiler-macros.log').stdout
    x86='#define __x86_64__ ' in macros or '#define __i386__ ' in macros
    wrappers='#define __x86_64__ ' in macros and '#define __LDBL_MANT_DIG__ 64' in macros
    faults=[('marker','long_double_nine.c','gmath_long_double_nine_format_','gmath_unrecognized_nine_format_','format coverage marker')]
    if x86:faults += [
      ('control','long_double_nine.c','ld_raw a=ld_read(x),b=ld_read(y),c={0,0};','{unsigned short cw=0x37f;__asm__ volatile("fldcw %0"::"m"(cw));}ld_raw a=ld_read(x),b=ld_read(y),c={0,0};','forbidden control write'),
      ('arithmetic','long_double_nine.c','ld_raw a=ld_read(x),b=ld_read(y),c={0,0};','__asm__ volatile("addsd %xmm0, %xmm0");ld_raw a=ld_read(x),b=ld_read(y),c={0,0};','floating arithmetic outside flag helper')]
    if wrappers:faults += [
      ('return-slot','long_double_nine.c','fldt (%rsp)','fldt 8(%rsp)','operand contract'),
      ('cfa','long_double_nine.c','.cfi_adjust_cfa_offset 24','','CFA metadata'),
      ('helper','long_double_nine.c','call gmath_long_double_nine_bytes','call gmath_long_double_nine_bytes+1','wrong/missing helper'),
      ('current-control','long_double_nine_bits.h','return (int)((control >> 10) & 3u);','return nearby_mode();','numerical')]
    for name,filename,old,new,reason in faults:
        case,obj=compile_case(name,filename,old,new)
        if reason=='numerical':
            caller=Path(os.environ['LONG_DOUBLE_NINE_CALLER']).resolve();binary=case/'probe'
            assert not run([*cc,*flags,str(caller),str(obj),*link,'-o',str(binary)],case/'link.log').returncode
            numerical_reject(binary,case/'rejection.log')
        else:expect_reject([sys.executable,str(abi),'--object',str(obj)],case/'rejection.log',reason)
        print('long-double nine controls: rejected compiled '+name,flush=True)
    caller_faults=0
    if wrappers:
        case,_=compile_case('caller-load','long_double_nine.c','#include "long_double_nine_bits.h"','#include "long_double_nine_bits.h"\n')
        path=case/'tests/long_double_nine_abi.h';text=path.read_text();old='movl %edi,%r10d';assert text.count(old)==1
        text=text.replace(old,r'fldt (%rsi)\n\tfstp %st(0)\n\tmovl %edi,%r10d');path.write_text(text)
        caller=case/'caller.o';assert not run([*cc,*flags,'-c',str(case/'tools/probe-long-double-nine.c'),'-o',str(caller)],case/'caller-compile.log').returncode
        expect_reject([sys.executable,str(abi),'--caller-object',str(caller)],case/'rejection.log','caller loads an operand through x87')
        caller_faults=1
        print('long-double nine controls: rejected compiled caller operand load',flush=True)
    # Real C loader controls, including foreign-format rows and independently
    # repinned wrong answers (the rational oracle must still reject them).
    client=work/'client.c';client.write_text('#include "'+str(root/'tests/long_double_nine_native.h')+'"\nint main(int n,char **v){return n==2?ld9_corpus(v[1],0):2;}\n')
    binary=work/'client';assert not run([*cc,*flags,str(client),str(args.archive.resolve()),*link,'-o',str(binary)],work/'client-compile.log').returncode
    assert not run([str(binary),str(directory)],work/'client-positive.log').returncode
    corpus=(directory/'long-double-nine.corpus').read_bytes();hashes=(directory/'long-double-nine.hash').read_bytes()
    mutants={'empty':b'','missing-lf':corpus[:-1],'nul-eof':corpus+b'\0','extra-column':corpus.split(b'\n',1)[0]+b' 0000000000000000\n','overflow-token':b'0'+corpus,'foreign-op':corpus.replace(b'0000000000000040 0000000000000000',b'0000000000000040 00000000000000ff',1)}
    for name,payload in mutants.items():
        case=work/('corpus-'+name);case.mkdir(exist_ok=True);(case/'long-double-nine.corpus').write_bytes(payload);(case/'long-double-nine.hash').write_bytes(hashes)
        expect_reject([str(binary),str(case)],case/'client-rejection.log')
    for name,payload in {'empty':b'','duplicate':hashes+hashes,'nul':hashes+b'\0','truncated':hashes[:-1],'wrong':hashes.replace(b'0000000000000040',b'0000000000000041',1)}.items():
        case=work/('hash-'+name);case.mkdir(exist_ok=True);(case/'long-double-nine.corpus').write_bytes(corpus);(case/'long-double-nine.hash').write_bytes(payload)
        expect_reject([str(binary),str(case)],case/'client-rejection.log')
    bad=[list(r) for r in rows];bad[0][14]^=1
    case=work/'repinned-wrong-answer';case.mkdir(exist_ok=True)
    for ext in ('corpus','hash','json','seeds'):shutil.copy2(directory/('long-double-nine.'+ext),case/('long-double-nine.'+ext))
    payload=''.join(oracle.encode(r) for r in bad).encode();hp=oracle.manifest(bad)
    (case/'long-double-nine.corpus').write_bytes(payload);(case/'long-double-nine.hash').write_bytes(hp)
    meta=json.loads((case/'long-double-nine.json').read_text());meta['corpus_sha256']=oracle.hashlib.sha256(payload).hexdigest();meta['hash_sha256']=oracle.hashlib.sha256(hp).hexdigest();(case/'long-double-nine.json').write_text(json.dumps(meta))
    expect_reject([sys.executable,str(checker),'--directory',str(case)],case/'oracle-rejection.log','literal wrong answer')
    literal_case=work/'repinned-wrong-literal-cell';literal_case.mkdir(exist_ok=True)
    for ext in ('corpus','hash','json','seeds'):shutil.copy2(directory/('long-double-nine.'+ext),literal_case/('long-double-nine.'+ext))
    seed_path=literal_case/'long-double-nine.seeds';seed_lines=seed_path.read_text().splitlines();fields=seed_lines[0].split();fields[12]=format(int(fields[12],16)^1,'x');seed_lines[0]=' '.join(fields);seed_payload=('\n'.join(seed_lines)+'\n').encode();seed_path.write_bytes(seed_payload)
    meta_path=literal_case/'long-double-nine.json';meta=json.loads(meta_path.read_text());meta['literal_sha256']=oracle.hashlib.sha256(seed_payload).hexdigest();meta['literal_bytes']=len(seed_payload);meta_path.write_text(json.dumps(meta))
    expect_reject([sys.executable,str(checker),'--directory',str(literal_case)],literal_case/'rejection.log','literal wrong answer')
    cache_case=work/'cache-reconstruction';cache_case.mkdir(exist_ok=True)
    for ext in ('hash','json','seeds'):shutil.copy2(directory/('long-double-nine.'+ext),cache_case/('long-double-nine.'+ext))
    cache=cache_case/'long-double-nine.corpus'
    if cache.exists():cache.unlink()
    assert not run([sys.executable,str(root/'tools/prepare-long-double-nine.py'),'--directory',str(cache_case)],cache_case/'positive.log').returncode
    assert cache.read_bytes()==corpus,'cold cache reconstruction differs'
    corrupt=corpus+b'\0';cache.write_bytes(corrupt)
    expect_reject([sys.executable,str(root/'tools/prepare-long-double-nine.py'),'--directory',str(cache_case)],cache_case/'corrupt-rejection.log','existing cache SHA256 differs')
    assert cache.read_bytes()==corrupt,'corrupt cache was silently repaired'
    from unittest.mock import patch
    def cache_fixture(name):
        case=work/('prepare-'+name);case.mkdir(exist_ok=True)
        for ext in ('hash','json','seeds'):shutil.copy2(directory/('long-double-nine.'+ext),case/('long-double-nine.'+ext))
        path=case/'long-double-nine.corpus'
        if path.exists():path.unlink()
        return case,path
    def refused(case,callback,fragment):
        try:callback()
        except (AssertionError,OSError) as error:
            (case/'rejection.log').write_text(str(error)+'\n');assert fragment in str(error),(case,str(error))
        else:raise AssertionError('preparation fault accepted: '+str(case))
        assert not list(case.glob('.long-double-nine-cache-*')),'leaked temporary after refusal'
    case,path=cache_fixture('partial-cache');partial=corpus[:73];path.write_bytes(partial)
    refused(case,lambda:oracle.prepare(case),'existing cache SHA256 differs');assert path.read_bytes()==partial
    case,path=cache_fixture('malformed-literal');payload=(case/'long-double-nine.seeds').read_bytes()[:-1];(case/'long-double-nine.seeds').write_bytes(payload)
    mp=case/'long-double-nine.json';meta=json.loads(mp.read_text());meta['literal_sha256']=oracle.hashlib.sha256(payload).hexdigest();meta['literal_bytes']=len(payload);mp.write_text(json.dumps(meta))
    refused(case,lambda:oracle.prepare(case),'');assert not path.exists()
    real_temporary=oracle.tempfile.NamedTemporaryFile
    for failure in ('write-error','short-write','close-error','corrupt-write'):
        case,path=cache_fixture(failure)
        def temporary(*args,**kwargs):
            stream=real_temporary(*args,**kwargs)
            class Stream:
                name=stream.name
                def __enter__(self):return self
                def __exit__(self,*args):
                    stream.close()
                    if failure=='close-error':raise OSError('injected close failure')
                def write(self,data):
                    if failure=='write-error':stream.write(data[:17]);raise OSError('injected write failure')
                    if failure=='short-write':stream.write(data[:17]);return 17
                    if failure=='corrupt-write':stream.write(b'X'+data[1:]);return len(data)
                    return stream.write(data)
                def flush(self):return stream.flush()
                def fileno(self):return stream.fileno()
            return Stream()
        with patch.object(oracle.tempfile,'NamedTemporaryFile',side_effect=temporary):
            refused(case,lambda:oracle.prepare(case),{'write-error':'injected write failure','short-write':'short write','close-error':'injected close failure','corrupt-write':'temporary SHA256 differs'}[failure])
        assert not path.exists(),'failed writer published a cache'
    case,path=cache_fixture('publication-error')
    with patch.object(oracle.os,'link',side_effect=OSError('injected publication failure')):
        refused(case,lambda:oracle.prepare(case),'injected publication failure')
    assert not path.exists()
    for valid in (True,False):
        case,path=cache_fixture('race-good' if valid else 'race-corrupt')
        def appear(source,destination):
            Path(destination).write_bytes(corpus if valid else corpus[:17])
            raise FileExistsError('injected concurrent publisher')
        with patch.object(oracle.os,'link',side_effect=appear):
            if valid:oracle.prepare(case)
            else:refused(case,lambda:oracle.prepare(case),'appearing cache SHA256 differs')
        assert path.read_bytes()==(corpus if valid else corpus[:17]),'raced cache was overwritten'
        assert not list(case.glob('.long-double-nine-cache-*'))
    print('long-double nine preparation: cold/full pins, partial and malformed inputs, write/short-write/close/corrupt-write/publication failures and good/bad races pass',flush=True)
    # Every archive member stays covered by the old/new partition gate.
    archive=work/'missing-nine.a';shutil.copy2(args.archive,archive)
    assert not run([os.environ.get('AR','ar'),'d',str(archive),'long_double_nine.o'],work/'archive-delete.log').returncode
    expect_reject([sys.executable,str(root/'tools/check-long-double-abi.py'),'--archive',str(archive),'--source-root',str(root/'src')],work/'archive-rejection.log','missing coverage')
    print(f'long-double nine controls: {len(defects)+len(faults)+caller_faults} compiled faults, 11 strict client corruptions, independently repinned wrong answer corrupt-cache refusal, cold reconstruction and missing archive member controls pass',flush=True)
if __name__=='__main__':main()
