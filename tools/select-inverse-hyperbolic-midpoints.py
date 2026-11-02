#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Reproduce midpoint-focused inputs from an independently pinned base search."""
import argparse,hashlib,json
from fractions import Fraction
from pathlib import Path
from inverse_hyperbolic_reference import MIDPOINT_CASES,MIDPOINT_SOURCE_SHA,population,decode

def distance(row,kind):
    width=int(row[0]);p,bias=(52,1023) if width==64 else (23,127)
    sign=1<<(width-1);offset=2+4*kind;target=int(row[offset],16);a=target&(sign-1)
    if not a or a>=((2*bias+1)<<p) or not int(row[offset+1])&2:return None
    left,right=Fraction(-1,2),Fraction(1,2)
    if not a&((1<<p)-1) and a>1<<p:
        if target&sign:right=Fraction(1,4)
        else:left=Fraction(-1,4)
    low,high=Fraction(int(row[offset+2]),1<<30),Fraction(int(row[offset+3]),1<<30)
    if not left-Fraction(1,1<<30)<=low<=high<=right+Fraction(1,1<<30):raise ValueError('residual outside nearest cell')
    # Rank the conservative upper distance of the entire closed interval to
    # its closest rounding midpoint, with the true binade spacing on each side.
    return min(max(abs(low-left),abs(high-left)),max(abs(low-right),abs(high-right)))

def select(directory,report):
    path=directory/'inverse-hyperbolic.corpus'
    if path.stat().st_size>16*1024*1024:raise ValueError('search exceeds size bound')
    data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
    if digest!=MIDPOINT_SOURCE_SHA:raise ValueError('independent base search SHA differs')
    if (directory/'inverse-hyperbolic.sha256').read_text()!=digest+'  inverse-hyperbolic.corpus\n':raise ValueError('search digest record differs')
    if b'\r' in data or not data.endswith(b'\n'):raise ValueError('search LF differs')
    lines=data.decode('ascii').splitlines()
    if lines[0]!='# inverse-hyperbolic-v1 seed=20261108 count=4096 MPFR-directed-1200/2400 mpmath-independent midpoint-search=1':raise ValueError('search metadata differs')
    if len(lines)<2 or lines[1]!='# width input asinh-target/flags/residual-low/high acosh-target/flags/residual-low/high atanh-target/flags/residual-low/high; residual scale=2^30 ULP':raise ValueError('search column/scale metadata differs')
    rows=[line.split() for line in lines[2:]]
    expected=[(w,x) for w in [64,32] for x in population(w,20261108,4096,adversarial=False)]
    if len(rows)!=len(expected):raise ValueError('search population count differs')
    for row,(width,word) in zip(rows,expected):
        if len(row)!=14 or row[:2]!=[str(width),format(word,'0%dx'%(width//4))]:raise ValueError('search population/order differs')
    result={64:set(),32:set()}
    for width in [64,32]:
        for kind,name in enumerate(['asinh','acosh','atanh']):
            candidates=[]
            for row in rows:
                if int(row[0])!=width or int(row[1],16)&(1<<(width-1)):continue
                score=distance(row,kind)
                if score is not None:candidates.append((score,int(row[1],16),row))
            ordered=sorted(candidates,key=lambda item:(item[0],item[1]))
            def region(word):
                x=decode(word,width)
                if kind==0:
                    return 'local' if x<=Fraction(1,2) else 'mixed' if x<=1 else 'general' if x<2**60 else 'huge'
                if kind==1:
                    return 'near-one' if x<Fraction(3,2) else 'ordinary' if x<4 else 'general' if x<2**60 else 'huge'
                return 'small' if x<=Fraction(1,5) else 'local' if x<=Fraction(1,2) else 'general' if x<Fraction(9,10) else 'pole'
            regions=[['local','mixed','general','huge'],['near-one','ordinary','general','huge'],['small','local','general','pole']][kind]
            groups=[('global',ordered[:16],16)]+[(label,[item for item in ordered if region(item[1])==label][:4],4) for label in regions]
            for selection,chosen,count in groups:
                if len(chosen)!=count:raise ValueError('too few '+selection+' midpoint candidates')
                for score,word,row in chosen:
                    result[width].add(word);offset=2+4*kind
                    report.append(dict(width=width,function=name,selection=selection,input=row[1],target=row[offset],
                        residual_low=row[offset+2],residual_high=row[offset+3],
                        conservative_midpoint_distance_in_target_ULP=str(score)))
    return {w:tuple(sorted(result[w])) for w in [64,32]}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True)
    p.add_argument('--check',action='store_true');p.add_argument('--report',type=Path);a=p.parse_args()
    report=[];result=select(a.directory,report)
    if a.report:a.report.write_text(json.dumps(report,indent=2)+'\n')
    if a.check:
        if result!=MIDPOINT_CASES:raise SystemExit('midpoint literals differ')
    else:print('MIDPOINT_CASES={'+','.join('%d:(%s)'%(w,','.join(hex(x) for x in result[w])) for w in [64,32])+'}')
