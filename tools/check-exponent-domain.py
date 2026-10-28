#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Check actual-prior finite-domain accounting; calibration needs no baseline."""
import argparse
import math
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from adjacent_baseline import identity_line,load,write_header

DOMAINS=('exponent.domain64 values 2098 modes 4 signs 2 subsets 32 errno 2 cases 1074176 hash f4c934bfef138325',
         'exponent.domain32 values 277 modes 4 signs 2 subsets 32 errno 2 cases 141824 hash 717cc11f90d36325')


def check(binary,metadata,timeout):
    r=subprocess.run([str(binary)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout,check=False)
    expected=identity_line(metadata,'exponent')+'\n'.join(DOMAINS)+'\n'
    if r.returncode or r.stderr or r.stdout!=expected:raise RuntimeError('domain status/identity/accounting/hash differs: '+r.stderr+r.stdout)
    return r.stdout


def calibrate():
    metadata={'revision':'f'*40,'object_sha256':'1'*64,'flags_sha256':'2'*64,'compiler_sha256':'3'*64}
    good=identity_line(metadata,'exponent')+'\n'.join(DOMAINS)+'\n'
    with tempfile.TemporaryDirectory(prefix='exponent-domain-driver-') as directory:
        binary=Path(directory)/'recording'
        def program(text,status=0,stderr='',sleep=0):
            binary.write_text('#!'+sys.executable+'\nimport sys,time\ntime.sleep('+repr(sleep)+')\nsys.stdout.write('+repr(text)+')\nsys.stderr.write('+repr(stderr)+')\nsys.exit('+str(status)+')\n');binary.chmod(0o700)
        # Pin old default header bytes while exercising the new family.
        literal='declared_revision '+metadata['revision']+' object_sha256 '+metadata['object_sha256']+' flags_sha256 '+metadata['flags_sha256']+' compiler_sha256 '+metadata['compiler_sha256']+'\n'
        for family in ('adjacent','exponent'):
            line=family+'.baseline '+literal
            if identity_line(metadata,family)!=line:raise RuntimeError('baseline identity format changed')
            header=Path(directory)/(family+'.h')
            if family=='adjacent':write_header(header,metadata)
            else:write_header(header,metadata,family)
            wanted='/* Generated baseline identity; caller-declared revision. */\n#define GMATH_'+family.upper()+'_BASELINE_IDENTITY '+json.dumps(line,ensure_ascii=True)+'\n'
            if header.read_text()!=wanted:raise RuntimeError('baseline header format changed')
        original=header.read_bytes()
        try:write_header(header,metadata,'bad\n#define INJECTED 1')
        except RuntimeError:pass
        else:raise RuntimeError('unsupported baseline family escaped')
        if header.read_bytes()!=original:raise RuntimeError('failed family changed header')
        print('  ok   adjacent default/exponent identity headers and invalid-family publication controls')
        program(good);check(binary,metadata,10)
        faults=[('missing Float',identity_line(metadata,'exponent')+DOMAINS[0]+'\n',0,''),
          ('duplicate row',good+DOMAINS[1]+'\n',0,''),('wrong values',good.replace('values 2098','values 2097'),0,''),
          ('wrong modes',good.replace('modes 4','modes 3',1),0,''),('wrong subsets',good.replace('subsets 32','subsets 16',1),0,''),
          ('wrong cases',good.replace('cases 1074176','cases 1073664'),0,''),('wrong hash',good.replace('f4c934bfef138325','f4c934bfef138324'),0,''),
          ('wrong identity',good.replace('exponent.baseline','adjacent.baseline',1),0,''),
          ('wrong order',identity_line(metadata,'exponent')+DOMAINS[1]+'\n'+DOMAINS[0]+'\n',0,''),
          ('failed process',good,1,''),('unexpected stderr',good,0,'warning\n')]
        for name,text,status,stderr in faults:
            program(text,status,stderr)
            try:check(binary,metadata,10)
            except RuntimeError:pass
            else:raise RuntimeError('domain calibration escaped '+name)
            print('  ok   exponent domain '+name+' detected')
        program(good,sleep=5)
        try:check(binary,metadata,0.05)
        except subprocess.TimeoutExpired:pass
        else:raise RuntimeError('domain timeout control escaped')
        print('  ok   exponent domain timeout detected and direct child reaped')
    print('exponent domain: parser/process calibration passes; not numerical oracle evidence')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('binary',nargs='?',type=Path)
    ap.add_argument('--baseline-metadata',type=Path);ap.add_argument('--timeout',type=float,default=120)
    ap.add_argument('--calibrate',action='store_true');a=ap.parse_args()
    if not math.isfinite(a.timeout) or a.timeout<=0:ap.error('--timeout must be finite and positive')
    if a.calibrate:calibrate();return
    if a.binary is None or a.baseline_metadata is None:ap.error('binary and --baseline-metadata are required')
    print(check(a.binary.resolve(),load(a.baseline_metadata),a.timeout),end='')
    print('exponent domain: 2375 values x4 modes x2 signs x32 subsets x2 errno;1216000 logical pairs verified; not exhaustive raw inputs')

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired) as error:
        print('exponent domain: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
