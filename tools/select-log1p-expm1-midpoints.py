#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Reproduce literal midpoint cases from independent base-search output."""
import argparse,hashlib,json
from fractions import Fraction
from pathlib import Path
from log1p_expm1_reference import MIDPOINT_CASES,population

def select(directory,report=None):
    if (directory/'log1p-expm1.corpus').stat().st_size>16*1024*1024:raise ValueError('search file exceeds bound')
    data=(directory/'log1p-expm1.corpus').read_bytes()
    if (directory/'log1p-expm1.sha256').read_text()!=hashlib.sha256(data).hexdigest()+'  log1p-expm1.corpus\n':raise ValueError('search SHA mismatch')
    lines=data.decode().splitlines()
    if not lines or lines[0]!='# log1p-expm1-v1 seed=20261104 count=4096 MPFR-directed-1200/2400 mpmath-independent midpoint-search=1':raise ValueError('wrong midpoint search metadata')
    rows=[line.split() for line in lines[2:]]
    expected=[(w,x) for w in (64,32) for x in population(w,20261104,4096,adversarial=False)]
    if [(int(r[0]),int(r[1],16)) for r in rows]!=expected:raise ValueError('wrong independent base search population')
    result={64:set(),32:set()}
    for width in (64,32):
        for exponential in (0,1):
            offset=2+4*exponential
            ordered=sorted((r for r in rows if int(r[0])==width),key=lambda r:abs(int(r[offset+2])+int(r[offset+3])),reverse=True)
            for r in ordered[:16]:
                result[width].add(int(r[1],16)&((1<<(width-1))-1))
                if report is not None:
                    p=52 if width==64 else 23;sign=1<<(width-1);target=int(r[offset],16);a=target&(sign-1)
                    left,right=Fraction(-1,2),Fraction(1,2)
                    if not a&((1<<p)-1) and a>1<<p:
                        if target&sign:right=Fraction(1,4)
                        else:left=Fraction(-1,4)
                    low,high=Fraction(int(r[offset+2]),1<<30),Fraction(int(r[offset+3]),1<<30)
                    distance=min(low-left,right-high)
                    report.append(dict(width=width,function='expm1' if exponential else 'log1p',input=r[1],target=r[offset],
                        residual_low=str(low),residual_high=str(high),score_abs_low_plus_high=abs(int(r[offset+2])+int(r[offset+3])),
                        closed_midpoint_distance_in_target_ULP=str(distance)))
    return {w:tuple(sorted(result[w])) for w in (64,32)}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--check',action='store_true');p.add_argument('--report',type=Path);a=p.parse_args()
    report=[];result=select(a.directory,report)
    if a.report:a.report.write_text(json.dumps(report,indent=2)+'\n')
    if a.check:
        if result!=MIDPOINT_CASES:raise SystemExit('midpoint literals do not match independent selector')
    else:print('MIDPOINT_CASES={'+','.join('%d:(%s)'%(w,','.join(hex(x) for x in result[w])) for w in (64,32))+'}')
