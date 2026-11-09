#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Cheap state grids, fail-closed cache/parser controls and compiled defects."""
import sys
if not __debug__ or sys.flags.optimize:raise SystemExit('long-double eleven controls require assertion-enabled Python')
import argparse,hashlib,importlib.util,json,os,shlex,shutil,subprocess,tempfile
from fractions import Fraction as F
from pathlib import Path
z=importlib.util.spec_from_file_location('eleven',Path(__file__).with_name('check-long-double-eleven.py'))
m=importlib.util.module_from_spec(z);z.loader.exec_module(m)

def probe_run(probe,rows,expected,timeout=180):
    p=subprocess.run([str(probe)],input=''.join(' '.join(f'{v:x}' for v in r)+'\n' for r in rows),text=True,capture_output=True,timeout=timeout)
    if p.returncode:raise RuntimeError('state probe exit '+str(p.returncode)+' '+p.stderr)
    lines=p.stdout.splitlines()[1:]
    if len(lines)!=len(rows):raise RuntimeError('state row count')
    for r,e,line in zip(rows,expected,lines,strict=True):
        fields=line.split()
        if len(fields)!=6:raise RuntimeError('state field count')
        actual=(int(fields[0],16),int(fields[1],16));flags,err,controls,entry=map(int,fields[2:])
        if (entry&r[8])!=r[8] or not r[8] and entry:raise RuntimeError('seed/clear entry flags')
        if actual!=tuple(e[:2]) or flags!=(e[2]|entry) or err!=173 or controls!=1:raise RuntimeError(f'state mismatch {r} {line} expected{e} entry{entry}')
    return len(rows)

def states(probe,data):
    # Exact/cheap cases span all modes, PCs, individual incoming flags and
    # supported DAZ/FTZ. Nonexact expensive APIs separately span all modes.
    header=subprocess.run([str(probe)],input='40 0 0 0 0 0 0 3 0 0\n',text=True,capture_output=True,check=True).stdout.splitlines()[0]
    native=int(header.split()[1]);rows=[];answers=[]
    for fmt in m.FORMATS:
        for op in range(11):
            chosen=next(c for c in data['cells'] if c[0]==fmt and c[1]==op and c[2:6]==[0,0,0,0])
            for mode in range(4):
                for pc in (0,2,3):
                    for incoming in (0,1,2,4,8,16):
                        for flush in (0,1):
                            rows.append([0 if fmt==native else fmt,*chosen[1:6],mode,pc,incoming,flush]);answers.append(chosen[6:9])
            # Nonexact output for every API and mode, except functions whose
            # selected exact identity already exercises its special path.
            inexact=next((c for c in data['cells'] if c[0]==fmt and c[1]==op and c[8]&4),None)
            if inexact:
                for index in range(12):
                    mode=index%4;pc=(0,2,3)[index%3];incoming=(0,1,2,4,8,16)[index%6];flush=index//6
                    rows.append([0 if fmt==native else fmt,*inexact[1:6],mode,pc,incoming,flush]);answers.append(inexact[6:9])
        minimum=-1074 if fmt in (64,106) else -16445 if fmt==80 else -16494
        maximum=1023 if fmt in (64,106) else 16383
        for exponent in (minimum,minimum-1,minimum-2,maximum,maximum+1):
            argument=m.raw(fmt,F(exponent))
            if exponent<minimum:answer=[*m.raw(fmt,F(0)),12]
            elif exponent>maximum:answer=[*m.b.pack(fmt,'inf',0,F(0)),20]
            else:answer=[*m.raw(fmt,m.b.scale(1,exponent)),0]
            for index in range(12):
                rows.append([0 if fmt==native else fmt,4,*argument,0,0,index%4,(0,2,3)[index%3],(0,1,2,4,8,16)[index%6],index//6]);answers.append(answer)
        for op in range(11):
            for flag_class in (12,20):
                boundary=next((c for c in data['cells'] if c[0]==fmt and c[1]==op and c[8]==flag_class),None)
                if boundary:
                    for index,incoming in enumerate((0,1,2,4,8,16)):
                        rows.append([0 if fmt==native else fmt,*boundary[1:6],index%4,(0,2,3)[index%3],incoming,1]);answers.append(boundary[6:9])
        for base,exponent in ((F(81),F(1,4)),(F(6561),F(1,8))):
            arguments=[*m.raw(fmt,base),*m.raw(fmt,exponent)];answer=[*m.raw(fmt,F(3)),0]
            for mode in range(4):
                rows.append([0 if fmt==native else fmt,10,*arguments,mode,(0,2,3,3)[mode],(0,4,8,16)[mode],mode%2]);answers.append(answer)
        if fmt==106:
            for tail in (0x3ff0000000000000,0x4000000000000000,1):
                cell=[106,10,*m.raw(106,F(-1)),0x7fe0000000000000,tail];answer=m.special(cell)
                for mode in range(4):
                    rows.append([0 if native==106 else 106,*cell[1:],mode,3,0,mode%2]);answers.append([*answer[0],answer[1]])
        one=m.raw(fmt,F(1));inf=m.b.pack(fmt,'inf',0,F(0));qn=m.b.pack(fmt,'nan',0,F(0))
        sn={64:(0x7ff0000000000001,0),80:(0x7fff,0x8000000000000001),128:(0x7fff000000000000,1),106:(0x7ff0000000000001,0)}[fmt]
        special=[(2,inf,qn),(2,inf,sn),(10,one,sn),(10,one,qn),(10,qn,(0,0)),(10,sn,(0,0))]
        malformed=(1,0) if fmt==80 else (0x7ff0000000000000,1) if fmt==106 else None
        for api in range(11):
            special.append((api,sn,(0,0)))
            if malformed:special.append((api,malformed,(0,0)))
        for api in (2,10):
            for value in (sn,malformed):
                if value is not None:special.extend([(api,one,value),(api,value,one),(api,value,(0,0))])
        negative_zero=m.raw(fmt,F(0),1);negative_inf=m.b.pack(fmt,'inf',1,F(0))
        for op in range(11):special.extend([(op,negative_zero,(0,0)),(op,negative_inf,(0,0))])
        special.extend([(2,negative_zero,negative_zero),(2,negative_zero,(0,0)),(2,(0,0),negative_zero)])
        for base in (negative_zero,negative_inf):
            for exponent in (F(3),F(2),F(-3),F(-2),F(1,2)):
                special.append((10,base,m.raw(fmt,exponent)))
        if fmt==80:special.append((0,(1,0),(0,0)))
        if fmt==106:special.append((0,(0x7ff0000000000000,1),(0,0)))
        for op,a,b in special:
            row=[fmt,op,*a,*b];e=m.special(row)
            for mode in range(4):rows.append([0 if fmt==native else fmt,*row[1:],mode,3,0,0]);answers.append([*e[0],e[1]])
    count=probe_run(probe,rows,answers,timeout=300)
    print('eleven state: actual entry flags, exact identities, nonexact modes, malformed/signaling priority and controls',count)
    return count

def transition_result(row,cell,line):
    fields=line.split()
    if len(fields)!=6:raise RuntimeError('transition field count')
    actual=tuple(int(v,16) for v in fields[:2]);flags,err,controls,entry=map(int,fields[2:])
    if entry&row[8]!=row[8] or not row[8] and entry:raise RuntimeError('transition entry flags')
    # Verify the fresh required flags even when incoming flags mask them in a
    # seeded call: every selected cell also has an unseeded control.
    kind,_,_,value=m.b.decode(cell[0],actual)
    lo,hi=m.decode_bounds(cell[9])
    required=20 if kind=='inf' else 0 if lo==hi==value else 12 if abs(value)<m.b.scale(1,-969 if cell[0]==106 else -1022 if cell[0]==64 else -16382) else 4
    m.verify_boundary_output(cell,actual,(flags&~entry)|(required&entry))
    if flags!=required|entry:raise RuntimeError('transition result flags')
    if err!=173 or controls!=1:raise RuntimeError('transition caller state')

def transition_states(probe,directory,work):
    cells=m.load_boundaries(directory)
    p=subprocess.run([str(probe)],input='40 0 0 0 0 0 0 3 0 0\n',capture_output=True,text=True,check=True)
    native=int(p.stdout.splitlines()[0].split()[1]);rows=[];expected=[];counts={}
    # Cover every mode/PC and mode/flush pair per cell, without the full
    # mode x PC x flush product. Both clear and all-standard flags use it.
    profiles=[(mode,pc,(index+mode)%2) for mode in range(4) for index,pc in enumerate((0,2,3))]
    if {(mode,pc) for mode,pc,_ in profiles}!={(mode,pc) for mode in range(4) for pc in (0,2,3)} or {(mode,flush) for mode,_,flush in profiles}!={(mode,flush) for mode in range(4) for flush in (0,1)}:raise RuntimeError('transition profile pair coverage')
    # Nine exp/expm1 cells cover each fractional transition's adjacent inputs;
    # the final nine pow cells use base two and fractional exponents. Retain
    # both overflow and underflow sides, including their zero/finite outcomes.
    for fmt in m.FORMATS:
        for op in (3,5,10):
            selected=[c for c in cells if c[0]==fmt and c[1]==op]
            if op==10:selected=[c for c in selected if m.b.decode(fmt,tuple(c[2:4]))[3]==2]
            if len(selected)!=9:raise RuntimeError('transition selected population')
            for c in selected:
                for callfmt in ((fmt,0) if fmt==native else (fmt,)):
                    for incoming in (0,31):
                        for mode,pc,flush in profiles:
                            rows.append([callfmt,*c[1:6],mode,pc,incoming,flush]);expected.append(c)
                            label='native'+str(native) if callfmt==0 else 'raw'+str(fmt)
                            counts[label]=counts.get(label,0)+1
    p=subprocess.run([str(probe)],input=''.join(' '.join(f'{v:x}' for v in r)+'\n' for r in rows),capture_output=True,text=True,timeout=300)
    if p.returncode:raise RuntimeError('transition probe exit '+str(p.returncode)+' '+p.stderr)
    lines=p.stdout.splitlines()[1:]
    if len(lines)!=len(rows):raise RuntimeError('transition row count')
    for row,cell,line in zip(rows,expected,lines,strict=True):transition_result(row,cell,line)
    # Positive actual calls precede each metadata fault; no crash counts as a
    # detection. Each fault must fail its own state assertion.
    faults={}
    for fault,column,replacement,reason in [('errno',3,'174','transition caller state'),('controls',4,'0','transition caller state'),('incoming',5,'0','transition entry flags')]:
        index=next(i for i,r in enumerate(rows) if r[8]==31)
        row,cell,line=rows[index],expected[index],lines[index]
        transition_result(row,cell,line);fields=line.split();fields[column]=replacement
        try:transition_result(row,cell,' '.join(fields))
        except RuntimeError as error:
            if str(error)!=reason:raise
            faults[fault]=reason
        else:raise RuntimeError('transition state fault accepted '+fault)
    (work/'transition-states.json').write_text(json.dumps({'counts':counts,'total':len(rows),'profiles':profiles,'faults':faults,'rows':rows,'stdout':p.stdout},sort_keys=True)+'\n')
    print('supplemental exp/expm1/fractional-pow transition states',len(rows),counts,'calibrated caller-state faults',len(faults))

def boundary_policy_controls(probe,directory,work):
    cells=m.load_boundaries(directory)
    # The complete production boundary check is the genuine positive control.
    m.check(probe,directory,boundary_only=True)
    c=next(c for c in cells if c[0]==106 and c[1] in (3,5,10) and c[8]==4 and c[6] and c[7] and not m.b.decode(106,tuple(c[6:8]))[1])
    actual=tuple(c[6:8]);m.verify_boundary_output(c,actual,c[8])
    outcomes={}
    def reject(name,cell,output,flags,reason):
        try:m.verify_boundary_output(cell,output,flags)
        except RuntimeError as error:
            if str(error)!=reason:raise
            outcomes[name]=reason
        else:raise RuntimeError('boundary policy fault accepted '+name)
    infinity=next(cell for cell in cells if cell[0]==64 and cell[8]==20 and m.b.decode(64,tuple(cell[6:8]))[0]=='inf')
    m.verify_boundary_output(infinity,tuple(infinity[6:8]),20)
    reject('binary64-infinity-reserved-word',infinity,(infinity[6],1),20,'boundary noncanonical inf encoding')
    swapped=actual[::-1]
    if m.b.decode(106,swapped)[3]!=m.b.decode(106,actual)[3]:raise RuntimeError('DD fault changed component sum')
    reject('DD-swapped-components',c,swapped,c[8],'boundary noncanonical finite encoding')
    reject('DD-wrong-sum',c,m.raw(106,F(0)),4,'boundary selected-neighbor enclosure')
    for fmt in m.FORMATS:
        maximum=1023 if fmt in (64,106) else 16383
        precision=53 if fmt==64 else 64 if fmt==80 else 113
        gap=m.b.scale(1,917 if fmt==106 else maximum-precision+1)
        limit=m.s.LIMIT if fmt==106 else m.b.scale(1,maximum+1)-gap
        for sign in (0,1):
            value=-limit if sign else limit;output=m.raw(fmt,value)
            # The finite maximum's virtual outer endpoint admits a near
            # enclosure, while a farther finite answer must fail both signs.
            near=(-limit-gap/4,-limit-gap/4) if sign else (limit+gap/4,limit+gap/4)
            far=(-limit-2*gap,-limit-2*gap) if sign else (limit+2*gap,limit+2*gap)
            cell=[fmt,3,0,0,0,0,*m.b.pack(fmt,'inf',sign,F(0)),20,m.encode_bounds(*near)]
            m.verify_boundary_output(cell,output,4)
            cell[-1]=m.encode_bounds(*far)
            reject(str(fmt)+'-outer-'+str(sign),cell,output,4,'boundary selected-neighbor enclosure')
    (work/'boundary-policy-status.json').write_text(json.dumps(outcomes,sort_keys=True)+'\n')
    print('boundary policy: genuine production/reference and virtual-edge controls pass; noncanonical DD/infinity, wrong sum and signed outer-bound faults reject',len(outcomes))

def loader_controls(directory,work):
    valid=m.load(directory)
    with tempfile.TemporaryDirectory(prefix='cache-',dir=work) as temp:
        dst=Path(temp)
        for suffix in ('json','hash'):shutil.copy2(directory/('long-double-eleven.'+suffix),dst)
        m.prepare(dst);payload=(dst/'long-double-eleven.corpus').read_bytes()
        # Warm and racing preparations preserve exactly the same materialized bytes.
        subprocess.run([sys.executable,str(Path(__file__).with_name('prepare-long-double-eleven.py')),'--directory',str(dst)],check=True,capture_output=True)
        commands=[[sys.executable,str(Path(__file__).with_name('prepare-long-double-eleven.py')),'--directory',str(dst)] for _ in range(2)]
        (dst/'long-double-eleven.corpus').unlink();procs=[subprocess.Popen(c,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for c in commands]
        for proc in procs:
            _,err=proc.communicate(timeout=30)
            if proc.returncode:raise RuntimeError('racing preparation '+err.decode())
        if (dst/'long-double-eleven.corpus').read_bytes()!=payload:raise RuntimeError('race cache bytes')
        corrupt=payload[:-1]+b'!';(dst/'long-double-eleven.corpus').write_bytes(corrupt)
        try:m.prepare(dst)
        except ValueError as e:
            if 'corrupt cache' not in str(e):raise
        else:raise RuntimeError('corrupt cache accepted')
        if (dst/'long-double-eleven.corpus').read_bytes()!=corrupt:raise RuntimeError('corrupt cache changed')
        # Hash and bounded-field failures precede expensive evaluation.
        for mutation in (b'{}\n',b' '* (m.MAX_BYTES+1)):
            (dst/'long-double-eleven.json').write_bytes(mutation)
            try:m.load(dst)
            except (ValueError,KeyError):pass
            else:raise RuntimeError('bad bounded literal accepted')
    for script in ('prepare-long-double-eleven.py','check-long-double-eleven.py'):
        p=subprocess.run([sys.executable,'-O',str(Path(__file__).with_name(script)),'--directory',str(directory),'--prepare'] if script.startswith('check-') else [sys.executable,'-O',str(Path(__file__).with_name(script)),'--directory',str(directory)],capture_output=True,text=True)
        if p.returncode==0 or 'assertion-enabled' not in p.stderr:raise RuntimeError('optimized Python accepted')
    from unittest.mock import patch
    real_fdopen=os.fdopen
    class FaultWriter:
        def __init__(self,handle,fault):self.handle,self.fault=handle,fault
        def __enter__(self):return self
        def write(self,data):
            if self.fault=='short':return self.handle.write(data[:-1])
            if self.fault=='corrupt':return self.handle.write(data[:-1]+b'!')
            return self.handle.write(data)
        def flush(self):
            if self.fault=='flush':raise OSError('planted flush failure')
            return self.handle.flush()
        def fileno(self):return self.handle.fileno()
        def __exit__(self,*exc):
            self.handle.close()
            if self.fault=='close':raise OSError('planted close failure')
            return False
    for fault in ('short','corrupt','flush','fsync','close'):
        with tempfile.TemporaryDirectory(prefix='publish-'+fault+'-',dir=work) as temp:
            dst=Path(temp)
            for suffix in ('json','hash'):shutil.copy2(directory/('long-double-eleven.'+suffix),dst)
            def writer(fd,mode):return FaultWriter(real_fdopen(fd,mode),fault)
            with patch.object(m.os,'fdopen',side_effect=writer):
                try:
                    if fault=='fsync':
                        with patch.object(m.os,'fsync',side_effect=OSError('planted fsync failure')):m.prepare(dst)
                    else:m.prepare(dst)
                except (OSError,ValueError):pass
                else:raise RuntimeError('cache publication fault accepted '+fault)
            if (dst/'long-double-eleven.corpus').exists() or list(dst.glob('.long-double-eleven.*')):raise RuntimeError('failed cache publication leaked cache/temp '+fault)
    print('eleven cache publication: short/corrupt writes and flush/fsync/close failures publish no cache and clean temporary files')
    print('eleven loader: cold/warm/racing cache, corrupt unchanged, full pins/bounded fields and optimized Python reject')

def parser_controls(probe):
    valid='40 0 0 0 0 0 0 3 0 0\n'
    bad=['',valid[:-1],valid+'garbage\n',valid.replace('40','41',1),valid.replace(' 3 ',' 1 '),valid.replace('40','-40',1),'0'*1024+'\n',valid.replace(' 0\n',' 2\n'),valid.replace('40','10000000000000000',1),valid.replace('40','40\x00',1)]
    for row in bad:
        p=subprocess.run([str(probe)],input=row,capture_output=True,text=True,timeout=10)
        if p.returncode==0:raise RuntimeError('malformed probe input accepted '+repr(row))
    print('eleven parser: malformed/overlong/overflow/unsupported control inputs reject',len(bad))

def compiled_controls(work):
    cc=shlex.split(os.environ.get('LONG_DOUBLE_ELEVEN_CC','cc'));flags=shlex.split(os.environ.get('LONG_DOUBLE_ELEVEN_FLAGS','-O2 -Iinclude'))
    root=Path(__file__).resolve().parents[1];source=root/'src/elementary'
    harness='''#define GMATH_LONG_DOUBLE_ELEVEN_RAW_ONLY
#include "long_double_eleven.c"
#include <stdio.h>
#include <inttypes.h>
#include <fenv.h>
int main(void) {unsigned f,o;ld_raw a,b;while(scanf("%u %u %" SCNx64 " %" SCNx64 " %" SCNx64 " %" SCNx64,&f,&o,&a.hi,&a.lo,&b.hi,&b.lo)==6) {feclearexcept(FE_ALL_EXCEPT);ld_raw r=lde_run(f,o,a,b);printf("%016" PRIx64 " %016" PRIx64 " %d\\n",r.hi,r.lo,fetestexcept(FE_ALL_EXCEPT));}return 0;}
'''
    witnesses={'overflow':'64 2 7fefffffffffffff 0 1 0\n','root':'128 2 0 2 0 2\n','precision':'106 10 3ff0000000000000 1 7fe0000000000000 0\n','tail':'64 6 4000000000000000 0 0 0\n','flag':'64 0 4000000000000000 0 0 0\n'}
    mutations={'overflow':('long_double_eleven_bits.h','if(right.kind==LD_INF) {','if(0 && right.kind==LD_INF) {'),'root':('long_double_eleven_bits.h','int j=i-LD_BASE+degree;','int j=i-LD_BASE;'),
               'precision':('long_double_eleven_interval.h','#define LDE_PREC 4352','#define LDE_PREC 1024'),
               'tail':('long_double_eleven_interval.h','j<1400','j<1'),
               'flag':('long_double_eleven_bits.h','rounded.kind==LD_INF,!exact,0','rounded.kind==LD_INF,0,0')}
    baselines={};results={}
    for name,mutation in [('control',None),*mutations.items()]:
        cell=work/name;cell.mkdir(exist_ok=True)
        for file in source.glob('long_double_eleven*'):shutil.copy2(file,cell/file.name)
        if mutation:
            path=cell/mutation[0];text=path.read_text()
            if text.count(mutation[1])!=1:raise RuntimeError('fault target not unique '+name)
            path.write_text(text.replace(mutation[1],mutation[2]))
        (cell/'probe.c').write_text(harness)
        command=cc+flags+['-fno-lto','-I'+str(source),'-I'+str(root/'include'),str(cell/'probe.c'),'-lm','-o',str(cell/'probe')]
        p=subprocess.run(command,capture_output=True,text=True,timeout=60)
        (cell/'compile.log').write_text(p.stdout+p.stderr)
        if p.returncode:raise RuntimeError('fault compile '+name+' '+p.stderr)
        if name=='control':
            for key,row in witnesses.items():
                p=subprocess.run([str(cell/'probe')],input=row,capture_output=True,text=True,timeout=10,check=True);baselines[key]=p.stdout
        else:
            p=subprocess.run([str(cell/'probe')],input=witnesses[name],capture_output=True,text=True,timeout=10)
            results[name]={'actual_exit':p.returncode,'actual_stdout':p.stdout,'positive_control_stdout':baselines[name]}
            (work/'compiled-status.json').write_text(json.dumps(results,indent=2)+'\n')
            if p.returncode==0 and p.stdout==baselines[name]:raise RuntimeError('compiled fault escaped '+name)
    print('eleven compiled controls: clean witnesses pass; midpoint, precision, tail, inexact and overflow defects reject')

def abi_controls(work):
    cc=shlex.split(os.environ.get('LONG_DOUBLE_ELEVEN_CC','cc'));flags=shlex.split(os.environ.get('LONG_DOUBLE_ELEVEN_FLAGS','-O2 -Iinclude'))
    root=Path(__file__).resolve().parents[1];source=root/'src/elementary';checker=Path(__file__).with_name('check-long-double-eleven-abi.py')
    changes=[('arithmetic','ld_raw b={0,0};if(y)', 'volatile double fault_a=1.0,fault_b=0.5;fault_a+=fault_b;(void)fault_a;ld_raw b={0,0};if(y)','floating arithmetic outside flag helper')]
    import platform
    if platform.machine()=='s390x':
        changes.append(('extended-bfp','ld_raw b={0,0};if(y)','__asm__ volatile("axbr %f0,%f4");ld_raw b={0,0};if(y)','floating arithmetic outside flag helper'))
    if platform.machine() in ('x86_64','amd64'):
        changes += [('control','ld_raw b={0,0};if(y)','__asm__ volatile("fldcw (%rsp)");ld_raw b={0,0};if(y)','forbidden control write'),
                    ('output-slot','fldt (%rsp)','fldt 8(%rsp)','native80 wrapper operand contract'),
                    ('unwind','.cfi_adjust_cfa_offset 24','', 'native80 CFA metadata mismatch')]
    outcomes={}
    for name,old,new,reason in [('control-positive','','',''),*changes]:
        cell=work/('abi-'+name);cell.mkdir(exist_ok=True)
        for path in source.glob('long_double_eleven*'):shutil.copy2(path,cell/path.name)
        text=(cell/'long_double_eleven.c').read_text()
        if old:
            if text.count(old)!=1:raise RuntimeError('ABI fault target not unique '+name)
            text=text.replace(old,new);(cell/'long_double_eleven.c').write_text(text)
        obj=cell/'production.o';p=subprocess.run(cc+flags+['-fno-lto','-I'+str(source),'-c',str(cell/'long_double_eleven.c'),'-o',str(obj)],capture_output=True,text=True,timeout=60)
        (cell/'compile.log').write_text(p.stdout+p.stderr)
        if p.returncode:raise RuntimeError('ABI fault compile '+name+' '+p.stderr)
        p=subprocess.run([sys.executable,str(checker),'--object',str(obj)],capture_output=True,text=True,timeout=60)
        (cell/'gate.log').write_text(p.stdout+p.stderr);outcomes[name]={'actual_exit':p.returncode,'intended_reason':reason}
        if not old:
            if p.returncode:raise RuntimeError('ABI positive control failed '+p.stderr)
        elif p.returncode==0 or reason not in p.stderr:raise RuntimeError('ABI fault failed wrong assertion '+name+' '+p.stderr)
    if platform.machine() in ('x86_64','amd64'):
        cell=work/'abi-caller';cell.mkdir(exist_ok=True)
        text=(root/'tools/probe-long-double-eleven.c').read_text().replace('../src/elementary/long_double_eleven.c',str(source/'long_double_eleven.c')).replace('../tests/fp_controls.h',str(root/'tests/fp_controls.h')).replace('../tests/long_double_eleven_abi.h',str((cell/'abi.h').resolve()))
        (cell/'probe.c').write_text(text)
        header=(root/'tests/long_double_eleven_abi.h').read_text().replace('LDE_ASM_STRING(gmath_sqrtl)','"gmath_long_double_eleven_bytes"');(cell/'abi.h').write_text(header)
        obj=cell/'caller.o';p=subprocess.run(cc+flags+['-fno-lto','-c',str(cell/'probe.c'),'-o',str(obj)],capture_output=True,text=True,timeout=60)
        if p.returncode:raise RuntimeError('caller fault compile '+p.stderr)
        p=subprocess.run([sys.executable,str(checker),'--caller-object',str(obj)],capture_output=True,text=True,timeout=60)
        (cell/'gate.log').write_text(p.stdout+p.stderr)
        if not p.returncode or 'caller depends on private byte engine' not in p.stderr:raise RuntimeError('caller defect escaped intended gate '+p.stderr)
        outcomes['private-caller']={'actual_exit':p.returncode,'intended_reason':'caller depends on private byte engine'}
    (work/'abi-status.json').write_text(json.dumps(outcomes,indent=2)+'\n')
    print('eleven compiled ABI controls: clean object passes; arithmetic/control/output/unwind/privatecaller defects reject',len(outcomes)-1)

def hypot_boundary_cells(fmt):
    from math import isqrt
    maximum=1023 if fmt in (64,106) else 16383
    p=53 if fmt==64 else 64 if fmt==80 else 113
    gap=m.b.scale(1,917 if fmt==106 else maximum-p+1)
    limit=m.s.LIMIT if fmt==106 else m.b.scale(1,maximum+1)-gap
    midpoint=limit+gap/2;target=midpoint*midpoint-limit*limit
    cut=m.b.exponent(target)//2-(2200 if fmt==106 else p+8)
    scaled=target/m.b.scale(1,2*cut);q=isqrt(scaled.numerator//scaled.denominator)
    center=m.s.rounded(fmt,m.b.scale(q,cut),0);value=m.b.decode(fmt,center)[3]
    ys=[F(0),m.b.scale(1,-1074 if fmt in (64,106) else -16445 if fmt==80 else -16494),limit]
    ys += [m.b.decode(fmt,m.s.neighbor(fmt,value,d))[3] for d in (-1,1)]+[value]
    cells=[]
    for y in ys:
        overflow=limit*limit+y*y>=midpoint*midpoint
        expected=m.b.pack(fmt,'inf',0,F(0)) if overflow else m.raw(fmt,limit)
        cells.append(([fmt,2,*m.raw(fmt,limit),*m.raw(fmt,y)],[*expected,20 if overflow else 4 if y else 0]))
    if not {4,20} <= {answer[2] for _,answer in cells}:raise RuntimeError('hypot overflow neighbors do not straddle exact midpoint')
    return cells

def range_controls(probe):
    header=subprocess.run([str(probe)],input='40 0 0 0 0 0 0 3 0 0\n',capture_output=True,text=True,check=True).stdout.splitlines()[0]
    native=int(header.split()[1]);rows=[];answers=[]
    for fmt in m.FORMATS:
        for cell,answer in hypot_boundary_cells(fmt):
            for mode in range(4):rows.append([0 if native==fmt else fmt,*cell[1:],mode,3,0,0]);answers.append(answer)
    print('exact finite hypot overflow/adjacent boundary states',probe_run(probe,rows,answers))

def fresh_controls(probe,work):
    import math,random
    # x<=2^-8: the positive exponential tail is <=2*x^33/33!,
    # and the even alternating log partial sum is a lower bound with
    # next-term upper error x^33/33. No transcendental oracle is used.
    seed=int.from_bytes(os.urandom(4),'little');rng=random.Random(seed);rows=[];certificates=[]
    native=int(subprocess.run([str(probe)],input='40 0 0 0 0 0 0 3 0 0\n',capture_output=True,text=True,check=True).stdout.splitlines()[0].split()[1])
    for fmt in m.FORMATS:
        k=rng.randrange(8,17);x=F(1,1<<k);t=1+x;n=rng.randrange(-40,41);ten=rng.randrange(1,11)
        exp=sum((x**j/F(math.factorial(j)) for j in range(33)),F(0));exp_hi=exp+2*x**33/F(math.factorial(33))
        log=sum(((-1)**(j+1)*x**j/F(j) for j in range(1,33)),F(0));log_hi=log+x**33/33
        inputs=[(t*t,F(0),t,t,0),(t**3,F(0),t,t,0),(3*t,4*t,5*t,5*t,0),(x,F(0),exp,exp_hi,4),(F(n),F(0),m.b.scale(1,n),m.b.scale(1,n),0),(x,F(0),exp-1,exp_hi-1,4),(t,F(0),log,log_hi,4),(m.b.scale(1,n),F(0),F(n),F(n),0),(F(10)**ten,F(0),F(ten),F(ten),0),(x,F(0),log,log_hi,4),(t,F(3),t**3,t**3,0)]
        for op,(a,b,lo,hi,flags) in enumerate(inputs):
            rows.append([0 if native==fmt else fmt,op,*m.raw(fmt,a),*m.raw(fmt,b),0,3,0,0]);certificates.append((fmt,lo,hi,flags))
    p=subprocess.run([str(probe)],input=''.join(' '.join(f'{v:x}'for v in row)+'\n'for row in rows),capture_output=True,text=True,check=True,timeout=60);lines=p.stdout.splitlines()[1:]
    if len(lines)!=len(rows):raise RuntimeError('fresh exact-series count')
    for row,(fmt,lo,hi,flags),line in zip(rows,certificates,lines,strict=True):
        h,l,f,err,controls,entry=line.split();out=(int(h,16),int(l,16));kind,_,_,value=m.b.decode(fmt,out)
        if kind!='finite' or (int(f),int(err),int(controls),int(entry))!=(flags,173,1,0):raise RuntimeError('fresh exact-series state '+str(row)+' '+line)
        if not flags:
            if lo!=hi or value!=lo or out!=m.raw(fmt,lo):raise RuntimeError('fresh exact identity '+str(row))
        else:
            pred=m.b.decode(fmt,m.s.neighbor(fmt,value,-1))[3];succ=m.b.decode(fmt,m.s.neighbor(fmt,value,1))[3]
            if not pred<=lo<=hi<=succ:raise RuntimeError('fresh rational-series enclosure '+str(row))
    (work/'fresh-exact-series.json').write_text(json.dumps({'seed':seed,'rows':rows,'count':len(rows)})+'\n')
    print('fresh container-free exact roots/dyadics/rational-series production controls',len(rows),'seed',seed)

def boundary_population_controls(directory,work):
    data={'oracle':m.PIN,'cells':m.load_boundaries(directory)};saved=m.BOUNDARY_SHA256
    for fault,reason in (('omission','boundary input population count'),('duplicate','boundary duplicate input row'),('format-op','boundary per-format/op population')):
        bad=json.loads(json.dumps(data))
        if fault=='omission':bad['cells'].pop()
        elif fault=='duplicate':bad['cells'][-1]=bad['cells'][-2]
        else:bad['cells'][-1][1]=3
        with tempfile.TemporaryDirectory(prefix='boundary-'+fault+'-',dir=work) as temp:
            path=Path(temp);payload=(json.dumps(bad,separators=(',',':'))+'\n').encode();m.BOUNDARY_SHA256=hashlib.sha256(payload).hexdigest()
            (path/'long-double-eleven.boundaries.json').write_bytes(payload);(path/'long-double-eleven.boundaries.hash').write_text(m.BOUNDARY_SHA256+'\n')
            try:
                try:m.load_boundaries(path)
                except ValueError as error:
                    if reason not in str(error):raise
                else:raise RuntimeError('fully repinned boundary population fault accepted '+fault)
            finally:m.BOUNDARY_SHA256=saved
    print('fully repinned boundary omission/duplicate/format-op populations rejected for intended reasons')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--directory',type=Path,default=Path('tests/corpus'));p.add_argument('--work',type=Path,required=True);p.add_argument('--compiled-only',action='store_true');p.add_argument('--states-only',action='store_true');a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    if not a.compiled_only:
        data=m.prepare(a.directory);states(a.probe,data);range_controls(a.probe);fresh_controls(a.probe,a.work)
        boundary_policy_controls(a.probe,a.directory,a.work);transition_states(a.probe,a.directory,a.work)
        if not a.states_only:loader_controls(a.directory,a.work);boundary_population_controls(a.directory,a.work);parser_controls(a.probe)
    if not a.states_only:
        compiled_controls(a.work)
        abi_controls(a.work)
        subprocess.run([sys.executable,str(Path(__file__).with_name('check-long-double-eleven-resources.py')),'--work',str(a.work/'resources')],check=True,timeout=300)
