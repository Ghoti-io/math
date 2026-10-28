#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Calibrate native-long parsing, accounting, checksums and fresh selection."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from long_scale_population import pairs


def invoke(probe,root):
    return subprocess.run([str(probe),str(root)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120,check=False)


def parse(text,longbits,path=None):
    lines=text.splitlines()
    if len(lines)!=2:raise RuntimeError('missing/duplicate long scale output')
    normalized=[]
    for width,line in zip((64,32),lines):
        prefix,sep,directory=line.partition(' from ')
        if not sep or not directory or (path is not None and directory!=str(path)):raise RuntimeError('long scale output directory differs')
        match=re.fullmatch(r'longscale\.(64|32)\.long(32|64) ([0-9a-f]{16}) ([1-9][0-9]*) skipped (0|[1-9][0-9]*) state ([0-9a-f]{16}) ([1-9][0-9]*)',prefix)
        if not match or int(match[1])!=width or int(match[2])!=longbits:raise RuntimeError('long scale output schema/native width differs')
        normalized.append(prefix)
    return '\n'.join(normalized)+'\n'


def wanted(root,longbits):
    lines=(root/'long_scale-special.hash').read_text().splitlines()
    if len(lines)!=4:raise RuntimeError('long scale reference output accounting differs')
    expected=[]
    for i,(width,bits) in enumerate(((64,32),(64,64),(32,32),(32,64))):
        if not lines[i].startswith('longscale.%d.long%d '%(width,bits)):raise RuntimeError('long scale reference width/order differs')
    for bits in (32,64):
        offset=0 if bits==32 else 1
        paired='\n'.join(lines[i]+' from reference' for i in (offset,offset+2))+'\n'
        normalized=parse(paired,bits)
        if bits==longbits:expected=normalized
    return expected



def verify(probe,root,longbits):
    r=invoke(probe,root)
    if r.returncode or r.stderr or parse(r.stdout,longbits,root)!=wanted(root,longbits):raise RuntimeError('long scale result/state/accounting differs: '+r.stderr+r.stdout)
    return r.stdout


def wide32(word):
    sign=(word>>31)<<63;a=word&0x7fffffff;e=a>>23;f=a&0x7fffff
    if e==255:return sign|0x7ff0000000000000|(f<<29)
    if e:return sign|((e+896)<<52)|(f<<29)
    if not f:return sign
    top=f.bit_length()-1
    return sign|((top+874)<<52)|((f^(1<<top))<<(52-top))


def validate_widened(root):
    result={}
    for name,width in (('scalbln',64),('scalblnf',32)):
        rawlines=(root/(name+'-special.corpus')).read_text().splitlines();expected=[]
        for row in rawlines[4:]:
            x,n,y,flags=row.split();x=int(x,16);word=int(n,16);y=int(y,16);flags=int(flags)
            signed=word if word<1<<63 else word-(1<<64)
            if not -(1<<31)<=signed<1<<31 or (width==32 and flags==1):continue
            if width==32:x,y=wide32(x),wide32(y)
            expected.append('%016x %016x %016x'%(x,word,y))
        lines=(root/(name+'.corpus')).read_text().splitlines();header=rawlines[:3]
        header[2]=header[2].rsplit(' entries ',1)[0]+' entries '+str(len(expected))
        if lines[:3]!=header or lines[3:]!=expected:raise RuntimeError('complete long scale widened rows/exclusions differ '+name)
        h=0xcbf29ce484222325
        for line in expected:
            for b in int(line.split()[2],16).to_bytes(8,'little'):h=((h^b)*0x100000001b3)&((1<<64)-1)
        result[name]=('%016x'%h,str(len(expected)))
    return result


def verify_numeric(probe,root):
    wants=validate_widened(root)
    with tempfile.TemporaryDirectory(prefix='longscale-overlay-') as t:
        stage=Path(t)
        for path in Path('tests/corpus').glob('*.corpus'):(stage/path.name).symlink_to(path.resolve())
        for name in wants:
            target=stage/(name+'.corpus');target.unlink(missing_ok=True);target.symlink_to((root/(name+'.corpus')).resolve())
        r=invoke(probe,stage)
        if r.returncode:raise RuntimeError('fresh generic numeric probe failed '+r.stderr)
        for name,(h,n) in wants.items():
            if [line.split() for line in r.stdout.splitlines()].count(['math.'+name+'.hash',h])!=1 or [line.split() for line in r.stdout.splitlines()].count(['math.'+name+'.count',n])!=1:raise RuntimeError('fresh numeric output differs '+name)
        # Use the real generic checker with a matching two-family overlay hash.
        original=Path('tests/corpus/trig.hash').read_text().splitlines();wanted_lines=[]
        for line in original:
            fields=line.split()
            if len(fields)==4 and fields[0]=='fn' and fields[1] in wants:
                h,n=wants[fields[1]];line='fn '+fields[1]+' '+h+' '+n
            wanted_lines.append(line)
        hashes=stage/'trig.hash';hashes.write_text('\n'.join(wanted_lines)+'\n')
        r=subprocess.run(['sh','tools/check-corpus-hash.sh',str(probe),str(stage),str(hashes)],capture_output=True,text=True,timeout=120)
        if r.returncode:raise RuntimeError('fresh all-function hash checker failed '+r.stdout+r.stderr)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('probe',type=Path);ap.add_argument('--corpus',type=Path,default=Path('tests/corpus'))
    ap.add_argument('--long-bits',type=int,choices=(32,64),required=True);ap.add_argument('--fresh',type=Path);ap.add_argument('--seed',type=int);ap.add_argument('--count',type=int);ap.add_argument('--numeric-probe',type=Path)
    a=ap.parse_args();probe=a.probe.resolve();root=(a.fresh or a.corpus).resolve();good=verify(probe,root,a.long_bits);validate_widened(root)
    if a.fresh:
        if a.seed is None or a.count is None or a.numeric_probe is None:ap.error('fresh requires seed/count/numeric-probe')
        for name in ('scalbln','scalblnf'):
            lines=(root/(name+'-special.corpus')).read_text().splitlines()
            if lines[2]!='# seed %d count %d fresh True entries %d'%(a.seed,a.count,len(lines)-4):raise RuntimeError('fresh long scale metadata/count differs')
            width=64 if name=='scalbln' else 32
            actual=[]
            for row in lines[4:]:
                fields=row.split();n=int(fields[1],16);actual.append((int(fields[0],16),n if n<1<<63 else n-(1<<64)))
            if actual!=pairs(width,a.seed,a.count):raise RuntimeError('fresh requested input population differs '+name)
        verify_numeric(a.numeric_probe.resolve(),root)
        with tempfile.TemporaryDirectory(prefix='longscale-empty-') as t:
            r=invoke(probe,Path(t))
            if r.returncode!=1 or t not in r.stderr:raise RuntimeError('fresh empty-directory counterfactual escaped')
        print('long scale fresh: metadata, count, directory, complete widened rows/exclusions and all-function hashes verified');return
    with tempfile.TemporaryDirectory(prefix='longscale-controls-') as t:
        stage=Path(t)
        for p in root.iterdir():
            if p.name in ('scalbln-special.corpus','scalblnf-special.corpus','scalbln.corpus','scalblnf.corpus','long_scale-special.hash'):shutil.copy2(p,stage/p.name)
        defects=0
        for family,width in (('scalbln',64),('scalblnf',32)):
            data=(root/(family+'-special.corpus')).read_bytes();lines=data.splitlines(keepends=True)
            cases={'empty':b'', 'provenance':data.replace(b'MPFR 4.2.2',b'MPFR 0.0.0',1),'wrong-family':data.replace(('# function '+family).encode(),b'# function wrong',1),
              'negative-seed':data.replace(b'# seed 20261028',b'# seed -1',1),'overflow-seed':data.replace(b'# seed 20261028',b'# seed 18446744073709551616',1),
              'entry-overflow':data.replace(('entries '+str(len(lines)-4)).encode(),b'entries 2000001',1),'fresh-value':data.replace(b'fresh False',b'fresh Wrong',1),
              'truncated':b''.join(lines[:-1]),'no-newline':data[:-1],'extra-row':data+lines[-1],
              'duplicate':b''.join(lines[:5])+lines[4]+b''.join(lines[6:]),'nul':b''.join(lines[:4])+lines[4][:-1]+b'\0garbage\n'+b''.join(lines[5:]),
              'overlong':b''.join(lines[:4])+b'0'*300+b'\n'+b''.join(lines[5:]),'extra-field':b''.join(lines[:4])+lines[4][:-1]+b' extra\n'+b''.join(lines[5:]),
              'n-width':b''.join(lines[:4])+lines[4].replace(b'8000000000000000',b'800000000000000',1)+b''.join(lines[5:])}
            fields=lines[4].split();fields[2]=b'1'*len(fields[2]);cases['illegal-output']=b''.join(lines[:4])+b' '.join(fields)+b'\n'+b''.join(lines[5:])
            for name,bad in cases.items():
                if bad==data:raise RuntimeError('ineffective loader fixture '+name)
                (stage/(family+'-special.corpus')).write_bytes(bad);r=invoke(probe,stage)
                other=32 if width==64 else 64
                if r.returncode!=1 or 'long scale probe failed width'+str(width) not in r.stderr or 'long scale probe failed width'+str(other) in r.stderr:raise RuntimeError('wrong loader rejection '+family+' '+name)
                defects+=1
            (stage/(family+'-special.corpus')).write_bytes(data)
        print('long scale: %d isolated native loader/value defects detected'%defects)
        spec=importlib.util.spec_from_file_location('long_scale_checks','tools/check-long-scale.py');checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)
        for name in checks.EXPECTED:
            original=(stage/name).read_bytes();(stage/name).write_bytes(original+b'\n')
            r=subprocess.run([sys.executable,'tools/check-long-scale.py',str(stage)],capture_output=True,text=True,timeout=30)
            if r.returncode!=1 or name not in r.stderr:raise RuntimeError('payload checksum corruption escaped '+name)
            (stage/name).write_bytes(original)
        fake=stage/'recording-probe';fake.chmod(0o700) if fake.exists() else None
        def recording(text,status=0,stderr=''):
            fake.write_text('#!'+sys.executable+'\nimport sys\nsys.stdout.write('+repr(text)+')\nsys.stderr.write('+repr(stderr)+')\nsys.exit('+str(status)+')\n');fake.chmod(0o700)
        # Exact real-process accounting/path check, separate from numerical evidence.
        recording(good);verify(fake,root,a.long_bits)
        lines=good.splitlines(keepends=True);changed=lines[0].split();bad_outputs=['',lines[0],good+lines[0],lines[1]+lines[0],good.replace(' from '+str(root),' from wrong',1)]
        for column in (1,2,4,6,7):
            fields=changed.copy();fields[column]='%016x'%(int(fields[column],16)^1) if column in (1,6) else str(int(fields[column])+1)
            bad_outputs.append(' '.join(fields)+'\n'+lines[1])
        for bad in bad_outputs:
            recording(bad)
            try:verify(fake,root,a.long_bits)
            except RuntimeError:pass
            else:raise RuntimeError('complete output control escaped')
        for status,stderr in ((1,''),(0,'unexpected\n')):
            recording(good,status,stderr)
            try:verify(fake,root,a.long_bits)
            except RuntimeError:pass
            else:raise RuntimeError('process status/stderr control escaped')
        print('long scale: five checksum corruptions, valid recording and twelve process/output controls detected')

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as error:
        print('long scale controls: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
