#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Complete archive partition: unchanged legacy gate plus bounded native ABI.

The new native80 object can only read CW in its byte helper and return with a
single memory fldt in each floating wrapper. No exception weakens legacy code.
"""
import argparse, os, re, subprocess, tempfile
from pathlib import Path
NAMES='fabsl copysignl nanl fminl fmaxl floorl ceill truncl roundl rintl nearbyintl modfl frexpl ilogbl logbl'.split()
def run(*args):return subprocess.check_output(args,text=True)
PREFIXES=re.compile(r'^(?:lock|rep|repz|repnz|repe|repne|data16|addr32|notrack|bnd|cs|ds|es|ss|fs|gs|rex[.A-Z]*)$')
def instruction(text):
    words=text.split()
    while words and PREFIXES.fullmatch(words[0]):words.pop(0)
    return (words[0], ' '.join(words[1:])) if words else ('','')

def check_byte_engine(functions,header):
    names=['gmath_long_double_bytes']
    # ELFv1 PowerPC64 labels executable entries with a dot; the undotted
    # symbol is its function descriptor. Do not normalize x86 helper names.
    if ('architecture: i386' not in header and
        'architecture: powerpc:common64' in header and
        re.search(r'file format elf64-powerpc\b',header)):
        names.append('.gmath_long_double_bytes')
    assert any(name in functions for name in names),'missing byte-engine coverage'

def check_frames(path,wrappers,addresses,functions):
    frames=run(os.environ.get('READELF','readelf'),'--debug-dump=frames-interp',str(path))
    entries={};current=None
    for line in frames.splitlines():
        match=re.search(r'FDE .*pc=([0-9a-f]+)\.\.([0-9a-f]+)',line)
        if match:
            current=int(match[1],16);entries.setdefault(current,[]).append({'columns':None,'rows':[]});continue
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
        assert entries.get(start)==[expected], 'native80 CFA metadata mismatch '+fn

def frame_parser_selftest():
    from unittest.mock import patch
    positive="""00000000 00000014 00000000 FDE cie=00000000 pc=0000000000000000..000000000000000d
   LOC           CFA      ra
0000000000000000 rsp+8    c-8
0000000000000004 rsp+32   c-8
000000000000000c rsp+8    c-8
"""
    wrappers={'fixture':'fabsl'};addresses={'fixture':[0,4,8,12]}
    functions={'fixture':[('sub',''),('mov',''),('add',''),('ret','')]}
    def check(text):
        with patch(__name__+'.run',return_value=text):check_frames(Path('mocked-object'),wrappers,addresses,functions)
    check(positive)
    for row in ['0000000000000006 rsp+32 c-16', '0000000000000006 rbp+16 c-8', '0000000000000006 exp u']:
        wrong=positive.replace('000000000000000c rsp+8',row+'\n000000000000000c rsp+8')
        try:check(wrong)
        except AssertionError as error:assert 'native80 CFA metadata mismatch' in str(error)
        else:raise AssertionError('unexpected CFA/return-address row was silently ignored: '+row)
    headers=[
        ('file format elf64-powerpc\narchitecture: powerpc:common64',True),
        ('file format elf64-powerpcle\narchitecture: powerpc:common64',False),
        ('file format elf32-powerpc\narchitecture: powerpc:common',False),
        ('file format elf64-x86-64\narchitecture: i386:x86-64',False)]
    for header,dotted in headers:
        check_byte_engine({'gmath_long_double_bytes':[]},header)
        for functions,accepted in [({'.gmath_long_double_bytes':[]},dotted),({},False),({'.gmath_long_double_bytes_wrong':[]},False)]:
            try:check_byte_engine(functions,header)
            except AssertionError as error:
                assert not accepted and 'missing byte-engine coverage' in str(error)
            else:assert accepted,'unexpected dotted/missing helper accepted: '+header
    print('long-double ABI: ELFv1 dotted-entry selection fixtures pass; x86/ELF32/little-endian spellings stay strict (synthetic parser fixtures only)')
    print('long-double ABI: mocked readelf positive passes; intermediate wrong return-address/CFA rows reject')

# Reuse the scaling gate's narrow isolated flag-helper policy.
import importlib.util
_flag_spec=importlib.util.spec_from_file_location('scale_abi',Path(__file__).with_name('check-long-double-scale-abi.py'))
_flag_abi=importlib.util.module_from_spec(_flag_spec);_flag_spec.loader.exec_module(_flag_abi)
BASIC_FLAG_HELPERS=_flag_abi.FLAG_HELPERS | {'ldb_raise_divbyzero'}

def check_object(path,objdump='objdump'):
    text=run(objdump,'-dr','--no-show-raw-insn',str(path));header=run(objdump,'-f',str(path))
    x86='architecture: i386' in header
    amd64='architecture: i386:x86-64' in header
    markers=re.findall(r'\bgmath_long_double_format_(64|80|128|106)\b',run(os.environ.get('NM','nm'),'-a',str(path)))
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
    assert BASIC_FLAG_HELPERS.issubset({_flag_abi.helper_name(fn) for fn in functions}),'missing isolated flag helper coverage'
    transfers=0
    for fn,insns in functions.items():
        loads=0
        for op,operand in insns:
            assert not _flag_abi.control_write(op,operand,x86),'forbidden control write '+op
            if _flag_abi.floating_arithmetic(op,x86):
                assert _flag_abi.helper_name(fn) in BASIC_FLAG_HELPERS,'floating arithmetic outside flag helper '+fn+': '+op
            if x86:
                assert op not in ('ldmxcsr','vldmxcsr','fldcw','fldenv','frstor','fxrstor','fxrstor64','xrstor','xrstor64'), 'forbidden control write '+op
                if op.startswith('f'):
                    if op=='fnstcw':assert fn.split('.')[0] in ('gmath_long_double_bytes','ld_native_mode','nearby_mode_extended80'),'unexpected control read'
                    elif _flag_abi.helper_name(fn) in BASIC_FLAG_HELPERS:pass
                    elif op=='fldt':
                        assert fn in wrappers and wrappers[fn]!='ilogbl' and '(' in operand and '%st' not in operand,'unexpected native80 transfer'
                        loads+=1;transfers+=1
                    elif op in ('flds','fldl','fstps','fstpl','fldz','fld1') and not amd64:pass
                    else:raise AssertionError('forbidden x87 instruction '+fn+': '+op)
            else:
                assert not (op=='msr' and 'fpcr' in operand),'forbidden control write fpcr'
                assert op not in ('mtfsf','mtfsfi','mtfsb0','mtfsb1','lfpc'),'forbidden control write '+op
        assert loads<=1,'multiple native80 transfers in '+fn
    if x86 and native==80:
        assert transfers==14,'missing native80 wrapper transfer coverage'
        if amd64:
            for fn,name in wrappers.items():
                body=functions[fn]
                if body[0][0]=='endbr64':body=body[1:]
                ret=next((i for i,(op,_) in enumerate(body) if op=='ret'),-1)
                assert ret>=0,'native80 wrapper missing return '+fn
                body=body[:ret+1]
                pointer=name in ('modfl','frexpl');binary=name in ('copysignl','fminl','fmaxl')
                expected=[('sub','$0x18,%rsp'),('mov','%rdi,%r8') if pointer else ('xor','%r8d,%r8d'),
                          ('mov',f'$0x{NAMES.index(name):x},%edi'),('lea','0x20(%rsp),%rsi'),
                          ('lea','0x30(%rsp),%rdx') if binary else ('xor','%edx,%edx'),('mov','%rsp,%rcx'),('call',None)]
                if name!='ilogbl':expected.append(('fldt','(%rsp)'))
                expected.extend([('add','$0x18,%rsp'),('ret','')])
                assert len(body)==len(expected),'native80 wrapper instruction count mismatch '+fn
                for (op,operand),(want_op,want_operand) in zip(body,expected):
                    assert op==want_op,'native80 wrapper instruction contract '+fn+': '+op
                    if want_operand is None:
                        assert ('<gmath_long_double_bytes>' in operand or operand.split()[-1]=='gmath_long_double_bytes-0x4'),'native80 wrapper wrong/missing helper '+fn
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
    native=re.findall(r'^\S+\s+[a-zA-Z]\s+gmath_long_double_format_(64|80|128|106)$',symbols,re.M)
    assert len(native)==1,'missing caller format marker'
    names=list(NAMES)
    targets={};defined=[];private_engine=False
    for line in symbols.splitlines():
        fields=line.split()
        if len(fields)<2:continue
        kind,name=fields[-2:];name=name.lstrip('.')
        if name in ('gmath_long_double_bytes',):private_engine=True
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
    return relocations

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--caller-object',type=Path);ap.add_argument('--archive',type=Path);ap.add_argument('--object',type=Path);ap.add_argument('--source-root',type=Path,default=Path('src'));ap.add_argument('--self-test-frames',action='store_true');args=ap.parse_args()
    if args.caller_object:
        refs=check_caller(args.caller_object,os.environ.get('OBJDUMP','objdump'));print('long-double caller: all15 public symbols and call/target relocations verified');return
    if args.self_test_frames:frame_parser_selftest();return
    objdump=os.environ.get('OBJDUMP','objdump');ar=os.environ.get('AR','ar')
    if args.object:check_object(args.object,objdump);print('long-double ABI: new object instruction contract passed');return
    assert args.archive,'archive required'
    names=run(ar,'t',str(args.archive)).splitlines()
    expected=[p.stem+'.o' for p in args.source_root.rglob('*.c')]
    assert len(names)==len(set(names)),'duplicate archive members'
    assert sorted(names)==sorted(expected),'unexpected archive member or missing coverage'
    assert names.count('long_double_basic.o')==1,'missing new object'
    assert names.count('long_double_scale.o')==1,'missing scaling object'
    assert names.count('long_double_nine.o')==1,'missing integer-arithmetic object'
    assert names.count('long_double_eleven.o')==1,'missing roots/explog object'
    assert names.count('long_double_seventeen.o')==1,'missing final real-function object'
    legacy=[]
    with tempfile.TemporaryDirectory(prefix='gmath-long-double-abi-') as tmp:
        for name in names:
            path=Path(tmp)/name;path.write_bytes(subprocess.check_output([ar,'p',str(args.archive),name]))
            if name=='long_double_basic.o':transfers=check_object(path,objdump)
            elif name=='long_double_scale.o':
                import importlib.util
                spec=importlib.util.spec_from_file_location('scale_abi',Path(__file__).with_name('check-long-double-scale-abi.py'))
                scale_abi=importlib.util.module_from_spec(spec);spec.loader.exec_module(scale_abi)
                scale_transfers=scale_abi.check_object(path,objdump)
            elif name=='long_double_nine.o':
                import importlib.util
                spec=importlib.util.spec_from_file_location('nine_abi',Path(__file__).with_name('check-long-double-nine-abi.py'))
                nine_abi=importlib.util.module_from_spec(spec);spec.loader.exec_module(nine_abi)
                nine_transfers=nine_abi.check_object(path,objdump)
            elif name=='long_double_eleven.o':
                import importlib.util
                spec=importlib.util.spec_from_file_location('eleven_abi',Path(__file__).with_name('check-long-double-eleven-abi.py'))
                eleven_abi=importlib.util.module_from_spec(spec);spec.loader.exec_module(eleven_abi)
                eleven_transfers=eleven_abi.check_object(path,objdump)
            elif name=='long_double_seventeen.o':
                import importlib.util
                spec=importlib.util.spec_from_file_location('seventeen_abi',Path(__file__).with_name('check-long-double-seventeen-abi.py'))
                seventeen_abi=importlib.util.module_from_spec(spec);spec.loader.exec_module(seventeen_abi)
                seventeen_transfers=seventeen_abi.check_object(path,objdump)
            else:legacy.append(str(path))
        subprocess.run([str(Path(__file__).with_name('check-no-x87.sh')),*legacy],check=True)
    print(f'long-double ABI: all {len(names)} members covered; {len(legacy)} legacy objects unchanged gate; {transfers} foundation, {scale_transfers} scaling and {nine_transfers} integer-arithmetic and {eleven_transfers} roots/explog and {seventeen_transfers} final real-function checked native80 returns')
if __name__=='__main__':main()
