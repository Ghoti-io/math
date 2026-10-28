#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Mandatory reference integrity, exact cube certificates and raw probe controls."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from cbrtf_reference import inputs, flags, certify, SIGN, INF, QNAN, wide
PROVENANCE='# Pinned oracle: tools/oracle/gen_corpus_cbrtf.py; MPFR 4.2.2 gmpy2 2.3.2 mpmath 1.4.1'
EXPECTED={'cbrtf-special.corpus': '34319e96d6812c799b37f906ebc8966e32f90c2e7d3cfb50c1adb9e14b71b229', 'cbrtf.corpus': 'ffba6fb78e59dde41bddcbbe56bc56b1786e62e126b5f30e548b3663ae2d2103'}
RAW_EXPECTED=('b56d6fe265757f09',74696,840360)

def read(root, seed=None, count=None):
    payload=(root/'cbrtf-special.corpus').read_bytes()
    if not payload.endswith(b'\n') or b'\x00' in payload: raise RuntimeError('raw framing')
    lines=payload.decode('ascii').splitlines()
    if len(lines)<3 or lines[0]!=PROVENANCE: raise RuntimeError('raw provenance')
    m=re.fullmatch(r'# seed ([0-9]{1,20}) count ([0-9]{1,5}) fresh (True|False) entries ([0-9]{1,7})',lines[1])
    if not m: raise RuntimeError('raw metadata')
    actual_seed,actual_count,fresh,entries=int(m[1]),int(m[2]),m[3],int(m[4])
    if not 0<=actual_seed<1<<64 or not 0<=actual_count<=50000 or not 0<entries<=2000000: raise RuntimeError('raw bounds')
    if seed is not None and (actual_seed,actual_count,fresh)!=(seed,count,'True'): raise RuntimeError('requested selection ignored')
    rows=[];previous=-1;generic=[]
    for line in lines[2:]:
        if not re.fullmatch('[0-9a-f]{8} [0-9a-f]{8} [0-9a-f]{8} [0-9a-f]{2}',line): raise RuntimeError('raw schema')
        x,y,e,f=(int(v,16) for v in line.split());a=x&~SIGN
        if x<=previous or f!=flags(x) or (e&~SIGN)>0x3f000000: raise RuntimeError('raw order/flags/error')
        if a>INF:
            if (y,e)!=(QNAN,0): raise RuntimeError('NaN reference')
        elif a in (0,INF):
            if (y,e)!=(x,0): raise RuntimeError('special reference')
        else:
            if ((x^y)&SIGN) or not 0x00800000<=y&~SIGN<INF: raise RuntimeError('root class')
            certify(x,y,e)
        if not (a>INF and not a&0x00400000): generic.append(f'{wide(x):016x} {wide(y):016x} {e:08x}\n')
        rows.append(x);previous=x
    if len(rows)!=entries or rows!=inputs(actual_seed,actual_count): raise RuntimeError('complete ordered population mismatch')
    text=PROVENANCE+'\n'+f'# seed {actual_seed} count {actual_count} fresh {fresh} entries {len(generic)}\n'+''.join(generic)
    if (root/'cbrtf.corpus').read_text()!=text: raise RuntimeError('complete widened reference mismatch')
    return entries

def run(probe,root,expected=None):
    p=subprocess.run([str(probe),str(root)],capture_output=True,text=True,timeout=60)
    if p.returncode or p.stderr: raise RuntimeError('raw probe failed: '+p.stderr[:300])
    m=re.fullmatch(r'cbrtf.raw ([0-9a-f]{16}) ([0-9]+) statecalls ([0-9]+) bound ([0-9.]+) from '+re.escape(str(root))+r'\n',p.stdout)
    if not m or float(m[4])>0.51: raise RuntimeError('raw output schema/path/budget')
    record=(m[1],int(m[2]),int(m[3]))
    if expected and record!=expected: raise RuntimeError('raw result hash/count/state-count differs')
    return record

def controls(probe):
    header=PROVENANCE+'\n# seed 0 count 0 fresh True entries 1\n'
    row='00000000 00000000 00000000 00\n'
    cases={'empty':'','provenance':header.replace('MPFR','MPRF')+row,'missing':header,
       'meta':header.replace('entries 1','entries 2')+row,'negative':header.replace('count 0','count -1')+row,
       'large':header.replace('count 0','count 50001')+row,
       'missing-space':header.replace('count 0 fresh','count 0fresh')+row,'extra-space':header.replace('seed 0','seed  0')+row,'seed':header.replace('seed 0','seed 18446744073709551616')+row,
       'NUL':header+row+'\x00\n','overlong':header+'0'*300+'\n','noLF':header+row.rstrip(),
       'extra':header+row+'bad\n','duplicate':header.replace('entries 1','entries 2')+row+row,
       'badflags':header+row.replace(' 00\n',' 10\n'),'negativezero':header+row.replace('00000000 00000000','00000000 80000000'),
       'sNaN':header+'7f800001 7fc00000 00000000 00\n','qNaN':header+'7fc00000 7fc00000 00000000 01\n',
       'payload':header+'7fc00007 7fc00007 00000000 00\n','rootclass':header+'40000000 00000000 00000000 10\n',
       'error':header+'40000000 3fa14518 7fc00000 10\n'}
    with tempfile.TemporaryDirectory(prefix='gmath-cbrtf-loader-') as d:
        root=Path(d);file=root/'cbrtf-special.corpus';file.write_text(header+row);run(probe,root)
        for name,text in cases.items():
            file.write_bytes(text.encode());p=subprocess.run([str(probe),str(root)],capture_output=True,text=True,timeout=10)
            if p.returncode!=1 or 'cbrtf raw/state/reference failure' not in p.stderr: raise RuntimeError('loader negative escaped: '+name)
    print(f'cbrtf: valid loader control and {len(cases)} negatives detected')

def output_controls(root):
    h,n,c=RAW_EXPECTED
    good=f'cbrtf.raw {h} {n} statecalls {c} bound 0.499889389 from {root}\n'
    cases=[('hash',good.replace(h,'0000000000000000'),'',0),('count',good.replace(str(n),str(n+1)),'',0),
           ('state-count',good.replace(str(c),str(c+1)),'',0),('bound',good.replace('0.499889389','0.9'),'',0),
           ('path',good.replace(' from '+str(root),' from wrong'),'',0),('missing','', '',0),
           ('duplicate',good+good,'',0),('stderr',good,'unexpected error',0),('status',good,'',1)]
    with tempfile.TemporaryDirectory(prefix='gmath-cbrtf-output-') as d:
        script=Path(d)/'probe'
        def put(out,err,status):
            script.write_text('#!'+sys.executable+'\nimport sys\nsys.stdout.write('+repr(out)+')\nsys.stderr.write('+repr(err)+')\nsys.exit('+str(status)+')\n');script.chmod(0o700)
        put(good,'',0);run(script,root,RAW_EXPECTED)
        for name,out,err,status in cases:
            put(out,err,status)
            try: run(script,root,RAW_EXPECTED)
            except RuntimeError: pass
            else: raise RuntimeError('output control escaped: '+name)
    print('cbrtf: valid recording process and nine output/process controls pass (not numerical oracle evidence)')


def certificate_controls(root):
    original=(root/'cbrtf-special.corpus').read_text();lines=original.splitlines()
    index=next(j for j in range(2,len(lines)) if 0<int(lines[j].split()[0],16)<INF and 0<(int(lines[j].split()[2],16)&~SIGN)<0x3f000000)
    x,y,e,f=lines[index].split();mutations={}
    for label,target,error in [('adjacent-target',int(y,16)+1,int(e,16)),
                               ('signed-error',int(y,16),int(e,16)^SIGN),
                               ('error-rounding',int(y,16),int(e,16)+1)]:
        changed=lines.copy();changed[index]=f'{x} {target:08x} {error:08x} {f}';mutations[label]='\n'.join(changed)+'\n'
    changed=lines[:-1];meta=changed[1].split();meta[-1]=str(int(meta[-1])-1);changed[1]=' '.join(meta);mutations['population-omission']='\n'.join(changed)+'\n'
    with tempfile.TemporaryDirectory(prefix='gmath-cbrtf-cert-') as d:
        stage=Path(d);(stage/'cbrtf.corpus').write_bytes((root/'cbrtf.corpus').read_bytes())
        for name,text in mutations.items():
            (stage/'cbrtf-special.corpus').write_text(text)
            try: read(stage)
            except (ValueError,RuntimeError) as error:
                expected=('complete ordered population mismatch' if name=='population-omission' else
                          'cbrtf nearest-target cube certificate failed' if name=='adjacent-target' else
                          'cbrtf signed-error cube certificate failed')
                if expected not in str(error): raise RuntimeError('certificate control failed for wrong reason: '+name+': '+str(error))
            else: raise RuntimeError('Python certificate fault escaped: '+name)
    print('cbrtf: four actual certificate/population corruptions rejected')


def certificate_calibration(root):
    # Prove a later raw/widened mismatch cannot masquerade as a cube-certificate rejection.
    global certify
    original=certify
    try:
        certify=lambda *args:None
        try: certificate_controls(root)
        except RuntimeError as error:
            if 'certificate control failed for wrong reason' not in str(error): raise
        else: raise RuntimeError('disabled certificate escaped control calibration')
    finally: certify=original
    print('cbrtf: disabled-certificate counterfactual rejected for the specific missing layer')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--corpus',type=Path,default=Path('tests/corpus'));p.add_argument('--probe',type=Path,required=True)
    p.add_argument('--fresh',action='store_true');p.add_argument('--seed',type=int);p.add_argument('--count',type=int);p.add_argument('--controls',action='store_true');p.add_argument('--unit',type=Path);a=p.parse_args()
    if a.fresh:
        if a.seed is None or a.count is None: p.error('fresh requires seed/count')
    else:
        if set(EXPECTED)!={'cbrtf-special.corpus','cbrtf.corpus'}: raise RuntimeError('incomplete mandatory reference checksum set')
        for name,digest in EXPECTED.items():
            if hashlib.sha256((a.corpus/name).read_bytes()).hexdigest()!=digest: raise RuntimeError('complete reference checksum: '+name)
    n=read(a.corpus,a.seed if a.fresh else None,a.count if a.fresh else None)
    record=run(a.probe,a.corpus,None if a.fresh else RAW_EXPECTED)
    if record[1]!=n: raise RuntimeError('probe ignored requested population')
    if a.fresh:
        with tempfile.TemporaryDirectory(prefix='gmath-cbrtf-empty-') as d:
            proc=subprocess.run([str(a.probe),d],capture_output=True,timeout=10)
            if proc.returncode!=1: raise RuntimeError('probe ignored directory')
    if a.unit:
        env=os.environ.copy();env['GMATH_CBRTF_CORPUS_DIR']=str(a.corpus)
        result=subprocess.run([str(a.unit),'--gtest_filter=Cbrtf.PinnedCorpusAndCallerState','--gtest_brief=1'],env=env,capture_output=True,text=True,timeout=60)
        if result.returncode or not re.search(r'^cbrtf.raw [0-9a-f]{16} '+str(n)+r' statecalls [0-9]+ bound [0-9.]+ from '+re.escape(str(a.corpus))+r'$',result.stdout,re.M):
            raise RuntimeError('unit ignored requested corpus directory/population: '+result.stdout+result.stderr)
    if a.controls:
        controls(a.probe);certificate_controls(a.corpus);certificate_calibration(a.corpus);output_controls(a.corpus)
    print(f'cbrtf: complete reference certificates and raw/state probe pass ({n} rows)')
if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as e:
        print('cbrtf: FAIL: '+str(e),file=sys.stderr);sys.exit(1)
