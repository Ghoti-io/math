#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Calibrate mathematical and source-applicability guards without editing evidence."""
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
from cbrtf_reference import certify,fraction

def run(args,diagnostic=None):
    p=subprocess.run([sys.executable,'tools/oracle/check_cbrtf_fast_budget.py',*args],capture_output=True,text=True,timeout=20)
    if diagnostic is None:
        if p.returncode or 'PASS:' not in p.stdout: raise RuntimeError('valid budget control failed: '+p.stdout+p.stderr)
    elif p.returncode!=1 or diagnostic not in p.stderr or 'PASS:' in p.stdout:
        raise RuntimeError('budget fault did not fail at its intended layer: '+str(args)+'\n'+p.stdout+p.stderr)

def main():
    run([])
    for x,y,e in [(0x236e2a8e,0x361d6f3e,0x3efff8e0),(0xa36e2a8e,0xb61d6f3e,0xbefff8e0)]:
        certify(x,y,e)
    if not fraction(0x361d6f3e)**3<fraction(0x236e2a8e)<fraction(0x361d6f3f)**3:raise RuntimeError('guard witness directed rounding cell')
    source=Path('src/elementary/float_cbrt.c').read_text()
    faults=[('coefficient','1.0/3.0','1.0/2.0','seed operation allowance'),
      ('gate-disabled','residue>UINT64_C(0x00800000)&&residue<UINT64_C(0x0f800000)','residue>0&&residue<UINT64_C(0x0fffffff)','strict rounding-cell comparisons missing'),
      ('radius','residue>UINT64_C(0x00800000)','residue>UINT64_C(0x00000001)','rounding-cell margin does not enclose'),
      ('upper','residue<UINT64_C(0x0f800000)','residue<UINT64_C(0x0f900000)','asymmetric rounding-cell'),
      ('midpoint-mask','bits&UINT64_C(0x0fffffff)','bits&UINT64_C(0x1fffffff)','half-Float-cell residue mask'),
      ('range','bits<UINT64_C(0x4000000000000000)','bits<UINT64_C(0x4010000000000000)','normalized seed range guard'),
      ('seed-expression','gmath_cbrt_seed[j][1]','gmath_cbrt_seed[j][0]','Float source operation model')]
    with tempfile.TemporaryDirectory(prefix='gmath-cbrtf-budget-') as d:
        root=Path(d)
        for name,old,new,diagnostic in faults:
            if source.count(old)!=1: raise RuntimeError('budget mutation anchor not unique: '+name)
            file=root/(name+'.c');file.write_text(source.replace(old,new,1));run(['--source',str(file)],diagnostic)
        file=root/'preprocessor.c';file.write_text('#define fc_ix unused_ix\n'+source);run(['--source',str(file)],'complete Float translation unit changed')
        m=re.search(r'fc_cube_mask\[64\].*?UINT64_C\(0x([0-9a-f]+)\)',source,re.S)
        if not m: raise RuntimeError('performance mask anchor')
        changed=source[:m.start(1)]+f'{int(m[1],16)^1:016x}'+source[m.end(1):]
        file=root/'mask.c';file.write_text(changed);run(['--source',str(file)],'exact-cube performance mask differs')
        for option,name,diagnostic in [('--double-source','cbrt.c','old double source model'),('--helpers','elem_common.h','old helpers source model')]:
            file=root/name;file.write_text(Path('src/elementary',name).read_text()+'\n');run([option,str(file)],diagnostic)
        table=Path('src/elementary/cbrt_table.h').read_text();m=re.search(r'0x[0-9a-f.]+p[+-][0-9]+',table)
        word=struct.unpack('>Q',struct.pack('>d',float.fromhex(m[0])))[0]
        adjacent=struct.unpack('>d',struct.pack('>Q',word+1))[0].hex()
        file=root/'table.h';file.write_text(table[:m.start()]+adjacent+table[m.end():]);run(['--table',str(file)],'reciprocal table constant is not nearest')
    print('cbrtf budget: valid control and twelve mathematical/source applicability faults detect')
if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,subprocess.SubprocessError) as e:
        print('cbrtf budget controls: FAIL: '+str(e),file=sys.stderr);sys.exit(1)
