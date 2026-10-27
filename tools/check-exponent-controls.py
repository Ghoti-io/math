#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Calibrate the real exponent parser, complete checksums and output accounting."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import struct


def invoke(probe,directory):
    return subprocess.run([str(probe),str(directory)],text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,timeout=60,check=False)


def output(text):
    rows=[]
    for line in text.splitlines():
        prefix,sep,path=line.partition(' from ')
        if not sep or not path:raise RuntimeError('missing exponent output provenance')
        fields=prefix.split()
        if len(fields)!=6 or fields[0] not in ('exponent.logb','exponent.logbf') or fields[3]!='state':
            raise RuntimeError('bad exponent output fields')
        if any(len(fields[i])!=16 or any(c not in '0123456789abcdef' for c in fields[i]) for i in (1,4)):
            raise RuntimeError('bad exponent hash')
        if any(not fields[i].isascii() or not fields[i].isdigit() or int(fields[i])<=0 for i in (2,5)):
            raise RuntimeError('bad exponent count')
        rows.append(prefix)
    if len(rows)!=2 or rows[0].split()[0]!='exponent.logb' or rows[1].split()[0]!='exponent.logbf':
        raise RuntimeError('missing/duplicate exponent outputs')
    return '\n'.join(rows)+'\n'


def verify(probe,root):
    result=invoke(probe,root)
    if result.returncode or output(result.stdout)!=(root/'exponent_value-special.hash').read_text():
        raise RuntimeError('exponent raw output mismatch: '+result.stderr+result.stdout)
    if any(line.partition(' from ')[2]!=str(root) for line in result.stdout.splitlines()):
        raise RuntimeError('exponent requested directory not selected')
    return result.stdout


def wide32(word):
    sign=(word>>31)<<63;a=word&0x7fffffff;e=a>>23;f=a&0x7fffff
    if e==255:return 0x7ff8000000000000 if f else sign|0x7ff0000000000000
    if e:return sign|((e+896)<<52)|(f<<29)
    if not f:return sign
    top=f.bit_length()-1
    return sign|((top+874)<<52)|((f^(1<<top))<<(52-top))


def verify_widened(probe,root):
    # Reconstruct every widened row from raw references with integer-only
    # widening. Then execute the generic numeric probe with only these two
    # corpora overlaid; keep all existing function corpora independent.
    wants={}
    for family,width in (('logb',64),('logbf',32)):
        raw_lines=(root/(family+'-special.corpus')).read_text().splitlines()
        raw=raw_lines[4:]
        expected=[]
        for row in raw:
            x,y,flags=(int(field,16) for field in row.split())
            if width==32 and flags==1:continue
            if width==32:x,y=wide32(x),wide32(y)
            else:
                if x&0x7fffffffffffffff>0x7ff0000000000000:x=0x7ff8000000000000
                if y&0x7fffffffffffffff>0x7ff0000000000000:y=0x7ff8000000000000
            expected.append('%016x %016x'%(x,y))
        lines=(root/(family+'.corpus')).read_text().splitlines()
        header=raw_lines[:3];header[2]=header[2].rsplit(' entries ',1)[0]+' entries '+str(len(expected))
        if lines[:3]!=header or lines[3:]!=expected:
            raise RuntimeError('complete widened rows/exclusions differ '+family)
        h=0xcbf29ce484222325
        for row in expected:
            for byte in int(row.split()[1],16).to_bytes(8,'little'):h=((h^byte)*0x100000001b3)&((1<<64)-1)
        wants[family]=('%016x'%h,str(len(expected)))
    with tempfile.TemporaryDirectory(prefix='exponent-wide-') as temp:
        overlay=Path(temp)
        for source in Path('tests/corpus').glob('*.corpus'):(overlay/source.name).symlink_to(source.resolve())
        for family in wants:
            target=overlay/(family+'.corpus');target.unlink();target.symlink_to((root/target.name).resolve())
        golden=[]
        for line in Path('tests/corpus/trig.hash').read_text().splitlines():
            fields=line.split()
            if len(fields)==4 and fields[0]=='fn' and fields[1] in wants:
                h,count=wants[fields[1]];line='fn '+fields[1]+' '+h+' '+count
            golden.append(line)
        target=overlay/'trig.hash';target.write_text('\n'.join(golden)+'\n')
        r=subprocess.run(['sh','tools/check-corpus-hash.sh',str(probe),str(overlay),str(target)],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120,check=False)
        if r.returncode:raise RuntimeError('fresh complete numeric outputs differ '+r.stdout+r.stderr)
    print('exponent fresh: complete widened rows/exclusions and actual generic numeric hashes/counts verified')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('probe',type=Path)
    ap.add_argument('--corpus',type=Path,default=Path('tests/corpus'));ap.add_argument('--fresh',type=Path);ap.add_argument('--seed',type=int);ap.add_argument('--count',type=int);ap.add_argument('--numeric-probe',type=Path)
    a=ap.parse_args();probe=a.probe.resolve()
    if a.fresh:
        root=a.fresh.resolve()
        for name in ('logb','logbf'):
            lines=(root/(name+'-special.corpus')).read_text().splitlines()
            rows=len(lines)-4
            if lines[2]!='# seed %d count %d fresh True entries %d'%(a.seed,a.count,rows):
                raise RuntimeError('fresh metadata/count mismatch')
        verify(probe,root)
        if a.numeric_probe is None:raise RuntimeError('fresh requires --numeric-probe')
        verify_widened(a.numeric_probe.resolve(),root)
        with tempfile.TemporaryDirectory(prefix='exponent-empty-') as t:
            r=invoke(probe,Path(t))
            if r.returncode!=1 or 'missing exponent corpus: '+t not in r.stderr:
                raise RuntimeError('empty-directory counterfactual failed')
        print('exponent fresh: requested metadata, counts, path and generated raw/state hashes verified');return
    root=a.corpus;good=verify(probe,root)
    with tempfile.TemporaryDirectory(prefix='exponent-controls-') as t:
        stage=Path(t)
        for p in root.glob('logb*-special.corpus'):shutil.copy2(p,stage/p.name)
        negatives=0
        for family,width in (('logb',64),('logbf',32)):
            data=(root/(family+'-special.corpus')).read_bytes();lines=data.splitlines(keepends=True)
            zero=b'0'*(width//4)
            cases={'empty':b'', 'provenance':data.replace(b'MPFR 4.2.2',b'MPFR 0.0.0',1),
              'function':data.replace(('# function '+family+'\n').encode(),b'# function wrong\n',1),
              'metadata':data.replace(b'# seed',b'# wrong',1),
              'negative-seed':data.replace(b'# seed 20261027',b'# seed -1',1),
              'overflow-seed':data.replace(b'# seed 20261027',b'# seed 18446744073709551616',1),
              'truncated':b''.join(lines[:-1]),'no-newline':data[:-1],
              'duplicate':b''.join(lines[:5])+lines[4]+b''.join(lines[6:]),
              'nul':b''.join(lines[:4])+lines[4][:-1]+b'\0garbage\n'+b''.join(lines[5:]),
              'overlong':b''.join(lines[:4])+b'0'*300+b'\n'+b''.join(lines[5:]),
              'extra-field':b''.join(lines[:4])+lines[4][:-1]+b' extra\n'+b''.join(lines[5:]),
              'wrong-width':b''.join(lines[:4])+b'0'*(8 if width==64 else 16)+lines[4][width//4:]+b''.join(lines[5:]),
              'wrong-flags':b''.join(lines[:4])+zero+b' '+lines[4].split()[1]+b' 0\n'+b''.join(lines[5:]),
              'wrong-output':b''.join(lines[:4])+zero+b' '+zero+b' 2\n'+b''.join(lines[5:])}
            finite=lines[5].split();finite[1]=('%0*x'%(width//4,int(finite[1],16)^1)).encode()
            cases['finite-output']=b''.join(lines[:5])+b' '.join(finite)+b'\n'+b''.join(lines[6:])
            for name,bad in cases.items():
                if bad==data:raise RuntimeError('ineffective loader plant '+name)
                (stage/(family+'-special.corpus')).write_bytes(bad);r=invoke(probe,stage)
                if r.returncode!=1 or 'exponent probe failed:' not in r.stderr:
                    raise RuntimeError('loader defect escaped '+family+' '+name)
                negatives+=1
            (stage/(family+'-special.corpus')).write_bytes(data)
        print('exponent: %d native loader/value defects detected'%negatives)
        # Full-file gate must detect every payload independently, including a
        # parse-valid output mutation. Never edit caller or committed evidence.
        import importlib.util
        spec=importlib.util.spec_from_file_location('exponent_checks','tools/check-exponent-value.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        expected=module.EXPECTED
        for name in expected:shutil.copy2(root/name,stage/name)
        for name in expected:
            original=(stage/name).read_bytes()
            lines=original.splitlines(keepends=True)
            row=next(i for i,line in enumerate(lines) if not line.startswith(b'#'))
            fields=lines[row].split()
            column=1
            fields[column]=('%0*x'%(len(fields[column]),int(fields[column],16)^1)).encode()
            semantic=b''.join(lines[:row])+b' '.join(fields)+b'\n'+b''.join(lines[row+1:])
            for changed in (original+b'\n',semantic):
                (stage/name).write_bytes(changed)
                r=subprocess.run([sys.executable,'tools/check-exponent-value.py',str(stage)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
                if r.returncode!=1 or name.encode() not in r.stderr:raise RuntimeError('checksum defect escaped '+name)
            (stage/name).write_bytes(original)
        print('exponent: ten full-payload and parse-valid semantic corruptions detected')
        # Recording process exercises verify(), including subprocess dispatch,
        # accounting and the requested directory, rather than only its parser.
        fake=stage/'output-probe';lines=good.splitlines(keepends=True)
        first=lines[0].split(' from ')[0].split()
        changed_hash=first.copy();changed_hash[1]='%016x'%(int(first[1],16)^1)
        changed_count=first.copy();changed_count[2]=str(int(first[2])+1)
        changed_state=first.copy();changed_state[4]='%016x'%(int(first[4],16)^1)
        changed_calls=first.copy();changed_calls[5]=str(int(first[5])+1)
        wrong=[]
        for fields in (changed_hash,changed_count,changed_state,changed_calls):
            wrong.append(' '.join(fields)+' from '+str(root)+'\n'+lines[1])
        wrong += [lines[1]+lines[0],good.replace(' from '+str(root),' from wrong-path',1),'',good+lines[0]]
        fake.write_text('#!'+sys.executable+'\nimport sys\nsys.stdout.write('+repr(good)+')\n');fake.chmod(0o700)
        verify(fake,root)
        for bad in wrong:
            fake.write_text('#!'+sys.executable+'\nimport sys\nsys.stdout.write('+repr(bad)+')\n')
            try:verify(fake,root)
            except RuntimeError:pass
            else:raise RuntimeError('complete output verification defect escaped')
        print('exponent: valid recording process and eight output hash/count/order/path defects detected')
    for bad in ('',good.splitlines()[0]+'\n',good+good.splitlines()[0]+'\n',good.replace('state','wrong',1)):
        try:output(bad)
        except RuntimeError:pass
        else:raise RuntimeError('output omission/schema defect escaped')
    print('exponent: four output omission/schema controls detected')


if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,subprocess.TimeoutExpired) as error:
        print('exponent controls: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
