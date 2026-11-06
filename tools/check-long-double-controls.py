#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Compile distinct numerical/state/forbidden-instruction defects and reject each."""
import argparse, os, shlex, shutil, subprocess, sys
from pathlib import Path

def target_features(macros):
    names={line.split()[1]:line.split()[2:] for line in macros.splitlines() if line.startswith('#define ') and len(line.split())>=3}
    x86=bool({'__i386__','__x86_64__'} & names.keys())
    native80=names.get('__LDBL_MANT_DIG__')==['64'] and names.get('__LDBL_MAX_EXP__')==['16384']
    return x86, x86 and '__x86_64__' in names and '__ELF__' in names and native80

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',required=True,type=Path);ap.add_argument('--work',required=True,type=Path);ap.add_argument('--archive',required=True,type=Path);args=ap.parse_args()
    root=Path(__file__).resolve().parent.parent;work=args.work.resolve();work.mkdir(parents=True,exist_ok=True)
    cc=shlex.split(os.environ.get('LONG_DOUBLE_CC','cc'));flags=shlex.split(os.environ.get('LONG_DOUBLE_FLAGS',''))
    checker=root/'tools/check-long-double.py';abi=root/'tools/check-long-double-abi.py'
    subprocess.run([sys.executable,str(abi),'--self-test-frames'],check=True)
    macros=subprocess.check_output([*cc,*flags,'-dM','-E','-x','c','/dev/null'],text=True)
    (work/'compiler-macros.txt').write_text(macros)
    x86,wrappers=target_features(macros)
    for arch in ('__aarch64__','__powerpc64__','__s390x__','__sparc__'):
        assert target_features('#define '+arch+' 1\n#define __LDBL_MANT_DIG__ 113\n')==(False,False)
    assert target_features('#define __i386__ 1\n')==(True,False)
    assert target_features('#define __x86_64__ 1\n#define __ELF__ 1\n#define __LDBL_MANT_DIG__ 64\n#define __LDBL_MAX_EXP__ 16384\n')==(True,True)
    print('long-double controls: non-x86/i386/AMD64 selection fixtures pass (synthetic compiler evidence; no target execution claim)')
    for payload,reason in [
        ('80 0 0 0 0 0 4 3 0\n','invalid row fields'),
        ('80 0 0 0 0 0 4294967296 3 0\n','invalid row fields'),
        ('80 0 0 0 0 0 18446744073709551616 3 0\n','malformed or truncated row'),
        ('80 0 0 0 0 0 -1 3 0\n','malformed or truncated row'),
        ('80 0 0 0 0 0 0 1 0\n','invalid row fields'),
        ('999 0 0 0 0 0 0 3 0\n','invalid row fields'),
        ('80 15 0 0 0 0 0 3 0\n','invalid row fields'),
        ('80 0 0 0 0 0 0 3 32\n','invalid row fields'),
        ('80 0 0 0 0 0 0 3\n','malformed or truncated row'),
        ('80 0 0 0 0 0 0 3 0 extra\n','malformed or truncated row'),
        ('garbage\n','malformed or truncated row'),
        ('80 0 0 0 0 0 0 3 0\n80 0 0\n','malformed or truncated row'),
        ('','input error or no rows')]:
        rejection=subprocess.run([str(args.probe.resolve())],input=payload,capture_output=True,text=True)
        assert rejection.returncode==2 and reason in rejection.stderr,'malformed probe row accepted or rejected for wrong reason'
    print('long-double controls: thirteen invalid/truncated/empty probe inputs reject for the intended parser reason')
    baseline=subprocess.run([sys.executable,str(checker),'--probe',str(args.probe.resolve()),'--corpus',str(root/'tests/corpus/long-double-foundation.json')],capture_output=True,text=True)
    (work/'unmodified.log').write_text(baseline.stdout+baseline.stderr);assert baseline.returncode==0,'unmodified positive control failed'
    defects=[
        ('pack','long_double_bits.h','r.hi |= ((uint64_t)exp <<','r.hi |= ((uint64_t)(exp ^ 1) <<','numerical'),
        ('round','long_double_basic.c','op == LD_ROUND ? half :','op == LD_ROUND ? half && sticky :','numerical'),
        ('nan','long_double_basic.c','if (op == LD_NAN_OP) { a.kind=LD_NAN;','if (op == LD_NAN_OP) { a.kind=LD_INF;','numerical'),
        ('state','long_double_basic.c','if (x && op != LD_NAN_OP) a=ld_read(x);','(void)gmath_invalid(); if (x && op != LD_NAN_OP) a=ld_read(x);','numerical'),
        ('arithmetic','long_double_basic.c','if (x && op != LD_NAN_OP) a=ld_read(x);','__asm__ volatile("fadd %st(0), %st(0)"); if (x && op != LD_NAN_OP) a=ld_read(x);','forbidden x87 instruction'),
        ('control','long_double_basic.c','if (x && op != LD_NAN_OP) a=ld_read(x);','{ unsigned short cw; __asm__ volatile("fnstcw %0" : "=m"(cw)); __asm__ volatile("fldcw %0" :: "m"(cw)); } if (x && op != LD_NAN_OP) a=ld_read(x);','forbidden control write'),
    ]
    if x86:
        anchor='if (x && op != LD_NAN_OP) a=ld_read(x);'
        defects.extend([
            ('prefixed-arithmetic','long_double_basic.c',anchor,'__asm__ volatile(".byte 0x2e; fadd %st(0), %st(0)"); '+anchor,'forbidden x87 instruction'),
            ('prefixed-control','long_double_basic.c',anchor,'{ unsigned short cw; __asm__ volatile("fnstcw %0" : "=m"(cw)); __asm__ volatile(".byte 0x2e; fldcw %0" :: "m"(cw)); } '+anchor,'forbidden control write')])
    else:
        defects=defects[:4]
        print('long-double controls: SKIPPED x87 instruction plants: compiler target is not x86')
    if wrappers:
        defects.extend([
            ('output-slot','long_double_basic.c','fldt (%rsp)','fldt 8(%rsp)','native80 wrapper operand contract'),
            ('stack-restoration','long_double_basic.c','addq $24, %rsp','addq $16, %rsp','native80 wrapper operand contract'),
            ('missing-helper','long_double_basic.c','call gmath_long_double_bytes','','native80 wrapper instruction count'),
            ('wrong-helper','long_double_basic.c','call gmath_long_double_bytes','call gmath_long_double_bytes+1','native80 wrapper wrong/missing helper'),
            ('cfa','long_double_basic.c','.cfi_adjust_cfa_offset 24','', 'native80 CFA metadata mismatch')])
    else:print('long-double controls: SKIPPED AMD64 native80 wrapper plants: inapplicable compiler ABI')
    for name,filename,old,new,reason in defects:
        case=work/name;source=case/'src/elementary';source.mkdir(parents=True,exist_ok=True);(case/'tools').mkdir(exist_ok=True);(case/'tests').mkdir(exist_ok=True)
        shutil.copy2(root/'tests/fp_controls.h',case/'tests/fp_controls.h')
        for p in (root/'src/elementary').glob('*.h'):shutil.copy2(p,source/p.name)
        shutil.copy2(root/'src/elementary/long_double_basic.c',source/'long_double_basic.c');shutil.copy2(root/'tools/probe-long-double.c',case/'tools/probe-long-double.c')
        path=source/filename;text=path.read_text();assert text.count(old)==(5 if name=='output-slot' else 1),(name,'mutation anchor not unique');path.write_text(text.replace(old,new))
        output=case/'probe';cmd=[*cc,*flags,str(case/'tools/probe-long-double.c'),'-lm','-o',str(output)]
        compile=subprocess.run(cmd,capture_output=True,text=True);(case/'compile.log').write_text(compile.stdout+compile.stderr);assert compile.returncode==0,name+' failed to compile, not a valid control'
        if reason=='numerical':
            result=subprocess.run([sys.executable,str(checker),'--probe',str(output)],capture_output=True,text=True)
            assert result.returncode!=0 and 'AssertionError: row ' in result.stderr,name+' did not fail for a result/state mismatch'
        else:
            obj=case/'long_double_basic.o';subprocess.run([*cc,*flags,'-c',str(source/'long_double_basic.c'),'-o',str(obj)],check=True)
            result=subprocess.run([sys.executable,str(abi),'--object',str(obj)],capture_output=True,text=True)
            assert result.returncode!=0 and reason in result.stderr,name+' did not fail for '+reason
        (case/'rejection.log').write_text(result.stdout+result.stderr)
        print('long-double controls: rejected compiled '+name+' defect ('+reason+')')
    # Archive population controls fail before instruction inspection, so an
    # empty/wrong archive cannot masquerade as successful legacy coverage.
    archive=args.archive.resolve();ar=os.environ.get('AR','ar')
    for label,extra in [('missing',False),('unexpected',True)]:
        target=work/(label+'.a');shutil.copy2(archive,target)
        if extra:
            source=work/'unexpected.c';source.write_text('int unexpected_member(void) { return 0; }\n')
            obj=work/'unexpected.o';subprocess.run([*cc,*flags,'-c',str(source),'-o',str(obj)],check=True)
            subprocess.run([ar,'rcs',str(target),str(obj)],check=True)
        else:subprocess.run([ar,'d',str(target),'long_double_basic.o'],check=True)
        result=subprocess.run([sys.executable,str(abi),'--archive',str(target),'--source-root',str(root/'src')],capture_output=True,text=True)
        assert result.returncode!=0 and 'unexpected archive member or missing coverage' in result.stderr,label+' population control failed for wrong reason'
        (work/(label+'-rejection.log')).write_text(result.stdout+result.stderr)
        print('long-double controls: rejected '+label+' archive member population')
    # Synthetic macro availability is separate from a real native ABI witness.
    ddflags=['-U__LDBL_MANT_DIG__','-D__LDBL_MANT_DIG__=106','-U__LDBL_MAX_EXP__','-D__LDBL_MAX_EXP__=1024']
    availability=work/'dd-availability.c'
    availability.write_text('#include <ghoti.io/math/basic.h>\n_Static_assert(GMATH_HAVE_FREXPL == 1 && GMATH_HAVE_FMODL == 1 && GMATH_HAVE_REMAINDERL == 1 && GMATH_HAVE_REMQUOL == 1, "DD APIs available");\nint main(void) { (void)&gmath_frexpl; (void)&gmath_fmodl; (void)&gmath_remainderl; (void)&gmath_remquol; return 0; }\n')
    subprocess.run([*cc,*flags,*ddflags,'-c',str(availability),'-o',str(work/'dd-availability.o')],check=True)
    for source_name,names in [('basic',['frexpl']),('nine',['fmodl','remainderl','remquol'])]:
        ddobj=work/('dd-'+source_name+'-definitions.o')
        subprocess.run([*cc,*flags,*ddflags,'-c',str(root/('src/elementary/long_double_'+source_name+'.c')),'-o',str(ddobj)],check=True)
        symbols=subprocess.check_output([os.environ.get('NM','nm'),str(ddobj)],text=True)
        (work/('dd-'+source_name+'-definition-symbols.txt')).write_text(symbols)
        for name in names:assert '_gmath_'+name in symbols,'missing DD definition '+name
    print('long-double controls: all four DD declarations and definitions available (synthetic macro fixture only)')
    print('long-double controls: unmodified baseline passes; '+str(len(defects))+' compiled defects and two archive coverage defects rejected')
if __name__=='__main__':main()
