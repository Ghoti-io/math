#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Complete-payload/population gate and focused family defect checks."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
from inverse_trig_reference import SEED, population

def run(cmd,log,env=None):
    with log.open('w') as f:return subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180).returncode

def require_defect(cmd,log,env):
    code=run(cmd,log,env)
    output=log.read_text()
    if code!=1 or '[  FAILED  ] InverseTrig.' not in output or 'inverse-trig: rejected at row' not in output:
        raise RuntimeError('defect failed outside intended numerical/state/loader assertion: '+str(log))

def validate(directory):
    data=(directory/'inverse-trig.corpus').read_bytes()
    pin=(directory/'inverse-trig.sha256').read_text()
    if pin!=hashlib.sha256(data).hexdigest()+'  inverse-trig.corpus\n':raise ValueError('inverse-trig SHA differs')
    if b'\r' in data or not data.endswith(b'\n'):raise ValueError('noncanonical LF')
    lines=data.decode('ascii').splitlines()
    if len(lines)<2:raise ValueError('missing headers')
    if not lines[0].startswith('# inverse-trig-v1 seed=%d count=512 '%SEED):raise ValueError('wrong frozen population metadata')
    rows=[line.split() for line in lines[2:]]
    expected=[(width,word) for width in (64,32) for word in population(width,SEED,512)]
    if len(rows)!=len(expected):raise ValueError('omitted/extra rows')
    for row,(width,word) in zip(rows,expected):
        if len(row)!=10 or row[0]!=str(width) or row[1]!=format(word,'0%dx'%(width//4)):raise ValueError('wrong input/population/order')
    return data

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--test',type=Path,required=True)
    parser.add_argument('--directory',type=Path,required=True);parser.add_argument('--work',type=Path,required=True)
    a=parser.parse_args();a.test=a.test.resolve();a.directory=a.directory.resolve();a.work.mkdir(parents=True,exist_ok=True)
    data=validate(a.directory);env=dict(os.environ,GMATH_INVERSE_TRIG_CORPUS_DIR=str(a.directory))
    if run([str(a.test)],a.work/'control.log',env):raise RuntimeError('positive family control failed')
    # Reference faults exercise the actual test loader/numerical/state checks;
    # every disposable source/object/binary is reclaimed before returning.
    with tempfile.TemporaryDirectory(prefix='reference-',dir=a.work) as temp:
        directory=Path(temp);env_bad=dict(env,GMATH_INVERSE_TRIG_CORPUS_DIR=str(directory))
        lines=data.decode().splitlines()
        variants={'empty':'','missing-newline':data.decode().rstrip('\n'),'truncated':'\n'.join(lines[:2]+[lines[2].split()[0]])+'\n',
                  'wrong-width':'\n'.join(lines[:2]+[lines[2].replace('64 ','16 ',1)]+lines[3:])+'\n',
                  'oversized-word':'\n'.join(lines[:2]+[lines[2].replace('0000000000000000','f'*80,1)]+lines[3:])+'\n',
                  'oversized-residual':'\n'.join(lines[:2]+[lines[2].replace(' 0 0 ', ' '+'9'*80+' 0 ',1)]+lines[3:])+'\n'}
        # Zero is an independently exact input, so changing its target must fail.
        fields=lines[2].split();fields[2]='3ff0000000000000'
        variants['wrong-target']='\n'.join(lines[:2]+[' '.join(fields)]+lines[3:])+'\n'
        fields=lines[2].split();fields[3]='2'
        variants['wrong-flags']='\n'.join(lines[:2]+[' '.join(fields)]+lines[3:])+'\n'
        for name,text in variants.items():
            (directory/'inverse-trig.corpus').write_text(text)
            require_defect([str(a.test)],a.work/(name+'.log'),env_bad)
        # Exercise every complete-payload protection even when an attacker
        # updates a digest to match a parse-valid, incomplete/wrong population.
        reordered=lines[:2]+[lines[3],lines[2]]+lines[4:]
        duplicate=lines[:2]+[lines[3],lines[3]]+lines[4:]
        validators={
            'omission':('\n'.join(lines[:-1])+'\n').encode(),
            'order':('\n'.join(reordered)+'\n').encode(),
            'duplicate':('\n'.join(duplicate)+'\n').encode(),
            'CRLF':data.replace(b'\n',b'\r\n'),
            'seed':data.replace(b'seed=20261101',b'seed=20261100',1),
        }
        for name,payload in validators.items():
            (directory/'inverse-trig.corpus').write_bytes(payload)
            (directory/'inverse-trig.sha256').write_text(hashlib.sha256(payload).hexdigest()+'  inverse-trig.corpus\n')
            try:validate(directory)
            except ValueError:pass
            else:raise RuntimeError('payload defect escaped: '+name)
        (directory/'inverse-trig.corpus').write_bytes(data)
        (directory/'inverse-trig.sha256').write_text('0'*64+'  inverse-trig.corpus\n')
        try:validate(directory)
        except ValueError:pass
        else:raise RuntimeError('wrong digest escaped')
        for name,bounds in [('interval-inverted',('1','0')),('interval-outside',('-536870914','0'))]:
            fields=lines[2].split();fields[4:6]=bounds
            (directory/'inverse-trig.corpus').write_text('\n'.join(lines[:2]+[' '.join(fields)]+lines[3:])+'\n')
            require_defect([str(a.test)],a.work/(name+'.log'),env_bad)
        # A parse-valid changed residual need not violate a one-ULP result
        # contract. Its integrity belongs to the complete-payload digest gate.
        fields=lines[2].split();fields[4:6]=['-1','0']
        shifted=('\n'.join(lines[:2]+[' '.join(fields)]+lines[3:])+'\n').encode()
        (directory/'inverse-trig.corpus').write_bytes(shifted)
        (directory/'inverse-trig.sha256').write_text(hashlib.sha256(data).hexdigest()+'  inverse-trig.corpus\n')
        try:validate(directory)
        except ValueError:pass
        else:raise RuntimeError('residual digest mutation escaped')
    source=Path('src/elementary/inverse_trig.c').read_text()
    mutations={
      'inexact-force':('volatile double ignored=one+tiny;','volatile double ignored=one+tiny*0.0;'),
      'half-angle-scale':('(1.0-a)*0.5','(1.0-a)*0.25'),
      'root-residual-sign':('(z-square.hi)-square.lo','(square.hi-z)+square.lo'),
      'series-coefficient':('inverse_asin_coeff[n]','inverse_asin_coeff[n ? n : 1]'),
      'asin-sign':('negative ? inverse_scale(result,-1.0) : result','negative ? result : result'),
      'tiny-underflow':('(void)gmath_underflow(0)','inverse_inexact()'),
      'signaling-invalid':('if (!(a&UINT64_C(0x0008000000000000))) (void)gmath_invalid();','if (0) (void)gmath_invalid();'),
      'float-signaling-invalid':('if (!(a&UINT32_C(0x00400000))) (void)gmath_invalid();','if (0) (void)gmath_invalid();'),
      'acos-exact-zero':('if (cosine && word==UINT64_C(0x3ff0000000000000)) return 0.0;','if (cosine && word==UINT64_C(0x3ff0000000000000)) return 1.0;'),
    }
    cc=shlex.split(os.environ['INVERSE_CC']);cxx=shlex.split(os.environ['INVERSE_CXX'])
    cflags=shlex.split(os.environ['INVERSE_CFLAGS']);link=shlex.split(os.environ['INVERSE_LINK'])
    objects=shlex.split(os.environ['INVERSE_TEST_OBJ'])+shlex.split(os.environ.get('INVERSE_HELPER_OBJ',''))
    with tempfile.TemporaryDirectory(prefix='source-',dir=a.work) as temp:
        directory=Path(temp);path=directory/'inverse_trig.c';obj=directory/'inverse_trig.o';exe=directory/'test'
        for name,(before,after) in mutations.items():
            if before not in source:raise RuntimeError('source defect anchor missing: '+name)
            path.write_text(source.replace(before,after))
            if run(cc+cflags+['-Isrc/elementary','-c',str(path),'-o',str(obj)],a.work/(name+'-compile.log')):raise RuntimeError('defect compile failed: '+name)
            if run(cxx+objects+[str(obj),os.environ['INVERSE_ARCHIVE']]+link+['-o',str(exe)],a.work/(name+'-link.log')):raise RuntimeError('defect link failed: '+name)
            require_defect([str(exe)],a.work/(name+'.log'),env)
    print('inverse-trig: positive, 6 loader/target/state, 2 oversized, 2 interval, 7 integrity/population and %d source defects passed'%len(mutations))
if __name__=='__main__':main()
