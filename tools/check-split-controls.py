#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Calibrate the real split parser, complete checksums and output accounting."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def invoke(probe,directory):
    return subprocess.run([str(probe),str(directory)],text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,timeout=60,check=False)


def output(text):
    rows=[]
    for line in text.splitlines():
        prefix,sep,path=line.partition(' from ')
        if not sep or not path:raise RuntimeError('missing split output provenance')
        fields=prefix.split()
        if len(fields)!=6 or fields[0] not in ('split.modf','split.modff') or fields[3]!='state':
            raise RuntimeError('bad split output fields')
        if any(len(fields[i])!=16 or any(c not in '0123456789abcdef' for c in fields[i]) for i in (1,4)):
            raise RuntimeError('bad split hash')
        if any(not fields[i].isascii() or not fields[i].isdigit() or int(fields[i])<=0 for i in (2,5)):
            raise RuntimeError('bad split count')
        rows.append(prefix)
    if len(rows)!=2 or rows[0].split()[0]!='split.modf' or rows[1].split()[0]!='split.modff':
        raise RuntimeError('missing/duplicate split outputs')
    return '\n'.join(rows)+'\n'


def verify(probe,root):
    result=invoke(probe,root)
    if result.returncode or output(result.stdout)!=(root/'fraction_split-special.hash').read_text():
        raise RuntimeError('split raw output mismatch: '+result.stderr+result.stdout)
    if any(line.partition(' from ')[2]!=str(root) for line in result.stdout.splitlines()):
        raise RuntimeError('split requested directory not selected')
    return result.stdout


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('probe',type=Path)
    ap.add_argument('--corpus',type=Path,default=Path('tests/corpus'));ap.add_argument('--fresh',type=Path);ap.add_argument('--seed',type=int);ap.add_argument('--count',type=int)
    a=ap.parse_args();probe=a.probe.resolve()
    if a.fresh:
        root=a.fresh.resolve()
        for name in ('modf','modff'):
            lines=(root/(name+'-special.corpus')).read_text().splitlines()
            rows=len(lines)-4
            if lines[2]!='# seed %d count %d fresh True entries %d'%(a.seed,a.count,rows):
                raise RuntimeError('fresh metadata/count mismatch')
        verify(probe,root)
        with tempfile.TemporaryDirectory(prefix='split-empty-') as t:
            r=invoke(probe,Path(t))
            if r.returncode!=1 or 'missing split corpus: '+t not in r.stderr:
                raise RuntimeError('empty-directory counterfactual failed')
        print('split fresh: requested metadata, counts, path and generated raw/state hashes verified');return
    root=a.corpus;good=verify(probe,root)
    with tempfile.TemporaryDirectory(prefix='split-controls-') as t:
        stage=Path(t)
        for p in root.glob('modf*-special.corpus'):shutil.copy2(p,stage/p.name)
        negatives=0
        for family,width in (('modf',64),('modff',32)):
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
              'wrong-flags':data.replace(zero+b' '+zero+b' '+zero+b' 0',zero+b' '+zero+b' '+zero+b' 1',1),
              'wrong-output':data.replace(zero+b' '+zero+b' '+zero+b' 0',zero+b' '+zero[:-1]+b'1 '+zero+b' 0',1)}
            for name,bad in cases.items():
                if bad==data:raise RuntimeError('ineffective loader plant '+name)
                (stage/(family+'-special.corpus')).write_bytes(bad);r=invoke(probe,stage)
                if r.returncode!=1 or 'split probe failed:' not in r.stderr:
                    raise RuntimeError('loader defect escaped '+family+' '+name)
                negatives+=1
            (stage/(family+'-special.corpus')).write_bytes(data)
        print('split: %d native loader/value defects detected'%negatives)
        # Full-file gate must detect every payload independently, including a
        # parse-valid output mutation. Never edit caller or committed evidence.
        import importlib.util
        spec=importlib.util.spec_from_file_location('split_checks','tools/check-fraction-split.py')
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
                r=subprocess.run([sys.executable,'tools/check-fraction-split.py',str(stage)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
                if r.returncode!=1 or name.encode() not in r.stderr:raise RuntimeError('checksum defect escaped '+name)
            (stage/name).write_bytes(original)
        print('split: fourteen full-payload and parse-valid semantic corruptions detected')
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
        print('split: valid recording process and eight output hash/count/order/path defects detected')
    for bad in ('',good.splitlines()[0]+'\n',good+good.splitlines()[0]+'\n',good.replace('state','wrong',1)):
        try:output(bad)
        except RuntimeError:pass
        else:raise RuntimeError('output omission/schema defect escaped')
    print('split: four output omission/schema controls detected')


if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,subprocess.TimeoutExpired) as error:
        print('split controls: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
