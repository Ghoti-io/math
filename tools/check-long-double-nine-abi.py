#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Complete archive partition: unchanged legacy gate plus bounded native ABI.

Numerical decisions are integer-only; isolated flag helpers, read-only controls,
native80 transfers and every CFA row are checked.
"""
import sys
if not __debug__ or sys.flags.optimize:
    raise SystemExit("long-double nine gates require assertion-enabled Python")

import argparse, os, re, subprocess, tempfile
from pathlib import Path
NAMES='lroundl llroundl lrintl llrintl fmodl remainderl remquol fdiml fmal'.split()
def run(*args):return subprocess.check_output(args,text=True,timeout=60)
PREFIXES=re.compile(r'^(?:lock|rep|repz|repnz|repe|repne|data16|addr32|notrack|bnd|cs|ds|es|ss|fs|gs|rex[.A-Z]*)$')
def instruction(text):
    words=text.split()
    while words and PREFIXES.fullmatch(words[0]):words.pop(0)
    return (words[0], ' '.join(words[1:])) if words else ('','')

def check_byte_engine(functions,header):
    names=['gmath_long_double_nine_bytes']
    # ELFv1 PowerPC64 labels executable entries with a dot; the undotted
    # symbol is its function descriptor. Do not normalize x86 helper names.
    if ('architecture: i386' not in header and
        'architecture: powerpc:common64' in header and
        re.search(r'file format elf64-powerpc\b',header)):
        names.append('.gmath_long_double_nine_bytes')
    assert any(name in functions for name in names),'missing byte-engine coverage'

def check_frames(path,wrappers,addresses,functions):
    frames=run(os.environ.get('READELF','readelf'),'--debug-dump=frames-interp',str(path))
    entries={};current=None
    for line in frames.splitlines():
        match=re.search(r'FDE .*pc=([0-9a-f]+)\.\.([0-9a-f]+)',line)
        if match:
            current=int(match[1],16);entries.setdefault(current,[]).append({'end':int(match[2],16),'columns':None,'rows':[]});continue
        if not line.strip():continue
        if re.match(r'\s*[0-9a-f]+\s+[0-9a-f]+\s+(?:[0-9a-f]+\s+)?(?:CIE|ZERO terminator)\b',line) or line.startswith('Contents of the '):current=None;continue
        if current is None:continue
        entry=entries[current][-1]
        if line.split()[:1]==['LOC']:
            if entry['columns'] is not None:entry['rows'].append((None,line.strip()))
            entry['columns']=line.split();continue
        match=re.match(r'\s*([0-9a-f]+)\s+(.+?)\s*$',line)
        # Retain every row, including unsupported CFA/RA expressions. Filtering
        # only recognized rules would silently erase an intermediate bad row.
        entry['rows'].append((int(match[1],16),*match[2].split()) if match else (None,line.strip()))
    for fn in wrappers:
        insns=functions[fn];pcs=addresses[fn]
        start=pcs[0];body=next(i for i,(op,_) in enumerate(insns) if op=='sub')
        ret=next(i for i,(op,_) in enumerate(insns) if op=='ret')
        # After sub rsp, CFA is old rsp+8 = current rsp+32. At ret it is rsp+8.
        expected={'columns':['LOC','CFA','ra'],'rows':[(start,'rsp+8','c-8'),(pcs[body+1],'rsp+32','c-8'),(pcs[ret],'rsp+8','c-8')]}
        coverage=entries.get(start,[])
        assert len(coverage)==1 and coverage[0]['end']>=pcs[ret]+1,'native80 FDE range does not cover ret '+fn
        assert [{k:v for k,v in entry.items() if k!='end'} for entry in coverage]==[expected], 'native80 CFA metadata mismatch '+fn

FLAG_HELPERS={'lds_raise_invalid','lds_raise_overflow','lds_raise_underflow','lds_raise_inexact'}
def helper_name(fn):return fn.lstrip('.').split('.')[0]
def control_write(op,operand,x86):
    if x86:return op in ('ldmxcsr','vldmxcsr','fldcw','fldenv','frstor','fxrstor','fxrstor64','xrstor','xrstor64')
    return (op=='msr' and 'fpcr' in operand.lower()) or op in ('mtfsf','mtfsfi','mtfsb0','mtfsb1','lfpc','sfpc') or (op=='vmsr' and re.search(r'\bfpscr\b',operand,re.I)) or (op in ('ld','ldx') and re.search(r',\s*%fsr\s*(?:!.*)?$',operand,re.I))
def floating_arithmetic(op,x86):
    if x86:
        return bool(re.match(r'^v?(?:(?:add|sub|mul|div|min|max|sqrt|rcp|rsqrt|round|cmp|comi|ucomi|hadd|hsub|addsub|dpp)(?:ss|sd|ps|pd)|cvt|fmadd|fmsub|fnmadd|fnmsub)',op))
    if re.fullmatch(r'(?:fcvt(?:[ampnz][su]|l2?|n2?|nt|lt|xn2?)?|[su]cvtf|frint(?:[aimnpzx]|32[xz]|64[xz]))',op):return True
    return bool(re.match(r'^(?:f(?:add|sub|mul|div|sqrt|cmp|madd|msub|nmadd|nmsub|cti|cfid)|v(?:add|sub|mul|div|sqrt|cmp|cvt)\.|(?:a|s|m|d|sq|c)(?:d|e)br$)',op))

def parser_controls():
    from unittest.mock import patch
    for op,operand in [('sfpc','%r0'),('vmsr','fpscr, r0'),('vmsr','FPSCR,r1'),('msr','fpcr,x0')]:
        assert control_write(op,operand,False),'control write parser missed '+op
    for op,operand in [('efpc','%r0'),('vmrs','r0,fpscr'),('vmsr','fpexc,r0')]:
        assert not control_write(op,operand,False),'unrelated instruction rejected'
    for op in ('addsd','vaddss','mulpd','vfmadd132sd','cvtsi2sd','ucomisd'):
        assert floating_arithmetic(op,True),'SSE arithmetic parser missed '+op
    assert not floating_arithmetic('paddd',True) and not floating_arithmetic('movsd',True)
    for op in ('fcvt','fcvtas','fcvtau','fcvtms','fcvtmu','fcvtns','fcvtnu','fcvtps','fcvtpu','fcvtzs','fcvtzu','scvtf','ucvtf','frinta','frinti','frintm','frintn','frintp','frintx','frintz','frint32x','frint32z','frint64x','frint64z','fcvtl','fcvtl2','fcvtn','fcvtn2','fcvtxn','fcvtxn2','fcvtnt','fcvtlt'):
        assert floating_arithmetic(op,False),'AArch64 conversion/rounding escaped '+op
    for op in ('fmov','ldr','str','ld','ldx','st','stx','fcvt-not-an-op'):
        assert not floating_arithmetic(op,False),'allowed transfer rejected '+op
    for op in ('ld','ldx'):
        for operand in ('[%sp + 8], %fsr','[%g1],%fsr','[%g1], %fsr ! status'):
            assert control_write(op,operand,False),'SPARC FSR write escaped'
        for operand in ('[%g1], %f0','[%g1], %g2'):
            assert not control_write(op,operand,False),'SPARC value transfer rejected'
    for op,operand in [('st','%fsr, [%g1]'),('stx','%fsr, [%g1]')]:
        assert not control_write(op,operand,False),'SPARC FSR read rejected'
    positive="""00000000 00000014 00000000 FDE cie=00000000 pc=0000000000000000..000000000000000d
   LOC           CFA      ra
0000000000000000 rsp+8    c-8
0000000000000004 rsp+32   c-8
000000000000000c rsp+8    c-8
"""
    wrappers={'fixture':'ldexpl'};addresses={'fixture':[0,4,8,12]}
    functions={'fixture':[('sub',''),('mov',''),('add',''),('ret','')]}
    def check(text):
        with patch(__name__+'.run',return_value=text):check_frames(Path('fixture'),wrappers,addresses,functions)
    check(positive)
    for end in ('0000000000000004','000000000000000c'):
        wrong=positive.replace('..000000000000000d','..'+end)
        try:check(wrong)
        except AssertionError as error:assert 'FDE range' in str(error)
        else:raise AssertionError('shortened FDE range accepted')
    for row in ('0000000000000006 rsp+32 c-16','0000000000000006 rbp+16 c-8','0000000000000006 exp u'):
        try:check(positive.replace('000000000000000c rsp+8',row+'\n000000000000000c rsp+8'))
        except AssertionError as error:assert 'CFA metadata' in str(error)
        else:raise AssertionError('intermediate CFA row accepted')
    def object_fixture(header,op,operand,reject=None):
        names=['gmath_'+name for name in NAMES]+['gmath_long_double_nine_bytes']+sorted(FLAG_HELPERS)
        disassembly=''.join(f'{i*16:04x} <{name}>:\n {i*16:04x}: ret\n' for i,name in enumerate(names))
        disassembly+=f'1000 <fixture_engine>:\n 1000: {op} {operand}\n 1004: ret\n'
        def result(*args):
            if args[0]==os.environ.get('NM','nm'):return '0000 r gmath_long_double_nine_format_128\n'
            return header if '-f' in args else disassembly
        with patch(__name__+'.run',side_effect=result):
            try:check_object(Path('synthetic'))
            except AssertionError as error:
                assert reject and reject in str(error),(op,str(error))
            else:assert reject is None,'planted instruction escaped object gate: '+op
    for op in ('fcvt','fcvtzs','scvtf','ucvtf','frintn','frint32x','frint64z'):
        object_fixture('architecture: aarch64',op,'d0, d1','floating arithmetic outside flag helper')
    for op in ('ld','ldx'):
        object_fixture('architecture: sparc:v9',op,'[%sp + 8], %fsr','forbidden control write')
    for header,op,operand in [('architecture: aarch64','fmov','d0, x0'),('architecture: aarch64','mrs','x0, fpcr'),('architecture: sparc:v9','ldx','[%g1], %g2'),('architecture: sparc:v9','ldd','[%g1], %f0'),('architecture: sparc:v9','stx','%fsr, [%g1]')]:
        object_fixture(header,op,operand)
    print('long-double nine ABI: conversion/rounding and FSR-write rejection fixtures pass; allowed transfers/readers and existing CFA coverage pass')

def check_object(path,objdump='objdump'):
    text=run(objdump,'-dr','--no-show-raw-insn',str(path));header=run(objdump,'-f',str(path))
    x86='architecture: i386' in header
    amd64='architecture: i386:x86-64' in header
    markers=re.findall(r'^\S+\s+[a-zA-Z]\s+gmath_long_double_nine_format_(64|80|128|106)$',run(os.environ.get('NM','nm'),'-a',str(path)),re.M)
    assert len(markers)==1,'missing/duplicate native format coverage marker'
    native=int(markers[0])
    functions={};addresses={};current=None
    for line in text.splitlines():
        m=re.match(r'^\s*[0-9a-f]+ <([^>]+)>:',line)
        if m:current=m[1];functions[current]=[];addresses[current]=[];continue
        relocation=re.match(r'^\s*[0-9a-f]+:\s+R_\S+\s+(\S+)',line)
        if relocation and current and functions[current] and functions[current][-1][0]=='call':
            op,operand=functions[current][-1];functions[current][-1]=(op,operand+' '+relocation[1]);continue
        m=re.match(r'^\s*([0-9a-f]+):\s+([a-z].*)',line)
        if m and current:
            functions[current].append(instruction(m[2]));addresses[current].append(int(m[1],16))
    assert functions and sum(map(len,functions.values())),'missing instruction coverage'
    wrappers={}
    for n in NAMES:
        matches=[k for k in functions if k.endswith('_gmath_'+n) or k=='gmath_'+n]
        assert len(matches)==1, 'missing/duplicate wrapper '+n
        wrappers[matches[0]]=n
    check_byte_engine(functions,header)
    assert FLAG_HELPERS.issubset({helper_name(fn) for fn in functions}),'missing isolated flag helper coverage'
    transfers=0
    for fn,insns in functions.items():
        loads=0
        for index,(op,operand) in enumerate(insns):
            assert not control_write(op,operand,x86),'forbidden control write '+op
            if floating_arithmetic(op,x86):
                assert helper_name(fn) in FLAG_HELPERS|{'gmath_invalid','gmath_overflow','gmath_underflow'},'floating arithmetic outside flag helper '+fn+': '+op
            if x86:
                if op.startswith('f'):
                    if op=='fnstcw':assert helper_name(fn) in ('ldn_mode','gmath_long_double_nine_bytes','gmath_long_double_nine_integer_bytes'),'unexpected control read'
                    elif op=='fwait':
                        assert helper_name(fn) in ('ldn_mode','gmath_long_double_nine_bytes','gmath_long_double_nine_integer_bytes') and index and insns[index-1][0]=='fnstcw','unexpected wait outside control read'
                    elif op=='fldt':
                        assert fn in wrappers and wrappers[fn] not in NAMES[:4] and '(' in operand and '%st' not in operand,'unexpected native80 transfer'
                        loads+=1;transfers+=1
                    elif op in ('flds','fldl','fstps','fstpl','fldz','fld1') and not amd64:pass
                    else:raise AssertionError('forbidden x87 instruction '+fn+': '+op)
        assert loads<=1,'multiple native80 transfers in '+fn
    if x86 and native==80:
        assert transfers==5,'missing native80 wrapper transfer coverage'
        if amd64:
            for fn,name in wrappers.items():
                body=functions[fn]
                if body[0][0]=='endbr64':body=body[1:]
                ret=next((i for i,(op,_) in enumerate(body) if op=='ret'),-1)
                assert ret>=0,'native80 wrapper missing return '+fn
                body=body[:ret+1]
                if name in NAMES[:4]:
                    current=int(name in ('lrintl','llrintl'))
                    expected=[('sub','$0x18,%rsp'),('mov',f'$0x{current:x},%edi'),('lea','0x20(%rsp),%rsi'),
                              ('mov','$0x40,%edx'),('call',None),('add','$0x18,%rsp'),('ret','')]
                    engine='gmath_long_double_nine_integer_bytes'
                else:
                    op={'fmodl':0,'remainderl':1,'remquol':2,'fdiml':3,'fmal':4}[name]
                    expected=[('sub','$0x18,%rsp'),('mov','%rdi,%r9') if name=='remquol' else ('xor','%r9d,%r9d'),
                              ('mov',f'$0x{op:x},%edi'),('lea','0x20(%rsp),%rsi'),('lea','0x30(%rsp),%rdx'),
                              ('lea','0x40(%rsp),%rcx') if name=='fmal' else ('xor','%ecx,%ecx'),
                              ('mov','%rsp,%r8'),('call',None),('fldt','(%rsp)'),('add','$0x18,%rsp'),('ret','')]
                    engine='gmath_long_double_nine_bytes'
                assert len(body)==len(expected),'native80 wrapper instruction count mismatch '+fn
                for (op,operand),(want_op,want_operand) in zip(body,expected):
                    assert op==want_op,'native80 wrapper instruction contract '+fn+': '+op
                    if want_operand is None:
                        assert ('<'+engine+'>' in operand or operand.split()[-1]==engine+'-0x4'),'native80 wrapper wrong/missing helper '+fn
                    else:
                        operand=operand.split('#')[0].replace(' ','')
                        assert operand==want_operand,'native80 wrapper operand contract '+fn+': '+operand
            check_frames(path,wrappers,addresses,functions)
    else:assert transfers==0,'unexpected native80 transfers for format'
    return transfers

def check_caller(path,objdump='objdump'):
    """Undefined public symbols plus relocations prove a distinct caller TU.

    Some ABIs address function descriptors before an indirect branch. Those
    target relocations are retained as evidence alongside ordinary call/jumps.
    Public definitions or a direct byte-engine dependency are never allowed.
    """
    symbols=run(os.environ.get('NM','nm'),'-a',str(path))
    disassembly=run(objdump,'-dr','--no-show-raw-insn',str(path))
    assert '.gnu.lto_' not in run(objdump,'-h',str(path)),'LTO caller is not an external ABI certificate'
    native=re.findall(r'^\S+\s+[a-zA-Z]\s+gmath_long_double_nine_format_(64|80|128|106)$',symbols,re.M)
    assert len(native)==1,'missing caller format marker'
    names=list(NAMES)
    targets={};defined=[];private_engine=False
    for line in symbols.splitlines():
        fields=line.split()
        if len(fields)<2:continue
        kind,name=fields[-2:];name=name.lstrip('.')
        if name in ('gmath_long_double_nine_bytes','gmath_long_double_nine_integer_bytes'):private_engine=True
        for public in names:
            if name=='gmath_'+public or name.endswith('_gmath_'+public):
                if kind!='U':defined.append(name)
                else:targets.setdefault(public,set()).add(name)
    assert not defined,'caller defines public wrapper: '+','.join(defined)
    assert not private_engine,'caller depends on private byte engine'
    assert set(targets)==set(names) and all(len(v)==1 for v in targets.values()),'caller missing external public-wrapper references'
    relocations={name:[] for name in names};previous=''
    for line in disassembly.splitlines():
        relocation=re.search(r'\b(R_\S+)\s+(\S+)',line)
        if relocation:
            target=re.split(r'[+@-]',relocation[2])[0].lstrip('.')
            for public,names in targets.items():
                if target in names:relocations[public].append((relocation[1],previous.strip()))
        elif re.match(r'\s*[0-9a-f]+:',line):previous=line
    assert all(relocations.values()),'caller missing public-wrapper target relocations'
    if 'architecture: i386' in run(objdump,'-f',str(path)):
        assert all(any(instruction(line.split(':',1)[1])[0] in ('call','callq','jmp','jmpq') for _,line in refs) for refs in relocations.values()),'x86 caller lacks external public call/jump instructions'
    if int(native[0])==80 and 'architecture: i386:x86-64' in run(objdump,'-f',str(path)):
        instructions=[]
        for line in disassembly.splitlines():
            m=re.match(r'\s*[0-9a-f]+:\s+([a-z].*)',line)
            if m:instructions.append(instruction(m[1]))
        assert not any(op=='fldt' for op,_ in instructions),'native80 caller loads an operand through x87'
        assert any(op=='fstpt' for op,_ in instructions),'native80 caller lacks ABI result store'
    return relocations

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--object',type=Path);ap.add_argument('--caller-object',type=Path);ap.add_argument('--self-test',action='store_true');args=ap.parse_args()
    if args.self_test:parser_controls();return
    if args.caller_object:
        references=check_caller(args.caller_object,os.environ.get('OBJDUMP','objdump'))
        for public,relocations in references.items():
            print('long-double nine caller: external '+public+' '+repr(relocations))
        print('long-double nine caller: all available public wrappers external; no public definitions, LTO or byte-engine dependency')
        return
    assert args.object,'object required'
    check_object(args.object,os.environ.get('OBJDUMP','objdump'))
    print('long-double nine ABI: all available wrappers, byte engine, controls and CFA metadata passed')
if __name__=='__main__':main()
