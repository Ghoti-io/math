#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Supplement the frozen historical populations with rounded native DD answers.

Exact Fraction quotient selection precedes output rounding. The scale oracle's
independent leader-cell interval proof certifies that the selected DD neighbors
have no population member between them; local midpoint parity determines ties.
Every invocation authenticates the literal population and answers, warm or cold.
"""
import sys
if not __debug__ or sys.flags.optimize:
    raise SystemExit('DD gates require assertion-enabled Python')
import argparse, hashlib, importlib.util, json, random, subprocess
from fractions import Fraction as F
from pathlib import Path
_spec=importlib.util.spec_from_file_location('nine',Path(__file__).with_name('check-long-double-nine.py'))
n=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(n)
b=n.b;s=n.s
SIGN=1<<63

def raw(v):return b.pack(106,'finite',int(v<0),v)
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def remainder_midpoints():
    """Exact x-y halfway results, with an independent DD adjacency certificate."""
    p=b.scale;anchor=F(1,4)-p(1,-100);gap=p(1,-153);cases=[]
    for sign in (1,-1):
        for index in (0,1):
            left=sign*(anchor+index*gap);right=sign*(anchor+(index+1)*gap)
            midpoint=(left+right)/2
            x=sign*(1+(2*index+1)*p(1,-154));y=sign*(F(3,4)+p(1,-100))
            assert b.decode(106,raw(x))[3]==x and b.decode(106,raw(y))[3]==y
            assert n.integer(x/y,3)==n.integer(x/y,0)==1
            assert x-y==midpoint and 2*midpoint==left+right
            assert b.decode(106,raw(left))[3]==left and b.decode(106,raw(right))[3]==right
            s.dd_no_interior(left,right)
            even=left if index==0 else right
            assert even/gap==int(even/gap) and int(even/gap)%2==0
            assert int((right if index==0 else left)/gap)%2==1
            s.dd_midpoint_parity(midpoint,even)
            for op in ('fmod','remainder','remquo','remquo-null'):
                cell=[op,list(raw(x)),list(raw(y))]
                result=reference(cell)
                assert result==[*raw(even),0,1 if op=='remquo' else 0,4]
                cases.append(cell)
    return cases

def population(seed=20261106):
    p=b.scale
    values=[(0,0),(SIGN,0),(1,0),(SIGN|1,0),raw(F(1)),raw(F(-1)),
            (0x3ff0000000000000,1),(0xbff0000000000000,SIGN|1),
            (0x4000000000000000,SIGN|1),(0xc000000000000000,1),
            (0x7fe0000000000000,1),(0x7fe0000000000000,SIGN|1),
            (0x3ff0000000000000,3), (0x3ff0000000000000,5),
            (0xbff0000000000000,SIGN|3), (0xbff0000000000000,SIGN|5),
            raw(p(1,-969)),raw(p(1,-1022)),raw(p(1,1023)),
            (0x3ff0000000000000,0xbff0000000000000),
            (0x3ff0000000000001,0xbff0000000000000),
            (0x7ff0000000000000,0),(0xfff0000000000000,0),
            (0x7ff8000000000000,0),(0x7ff0000000000001,0),
            (0x3ff0000000000000,0x7ff0000000000000)]
    # Exercise canonical packing at the finite DD endpoint and its neighbors.
    for sign in (1,-1):
        values.extend(raw(sign*(s.LIMIT-b.scale(k,917))) for k in (0,1,2))
    values.extend([(0x7fefffffffffffff,0x7fefffffffffffff),
                   (0xffefffffffffffff,0xffefffffffffffff),
                   (0x3ff0000000000000,0x7ff0000000000001)])
    pairs=[((0x3ff0000000000000,raw(p(1,-200))[0]),(0x3fe8000000000000,raw(p(1,-100))[0]))]
    for a in values:pairs.extend([(a,raw(F(3,4))),(raw(F(1)),a)])
    qnan=(0x7ff8000000000000,0);snan=(0x7ff0000000000001,0)
    pairs.extend([(qnan,snan),(snan,qnan),(raw(F(-2)),raw(F(1)))])
    infinity=(0x7ff0000000000000,0)
    for sign in (1,-1):
        pairs.extend((raw(sign*(s.LIMIT-b.scale(k,917))),infinity) for k in (0,1,2))
    for k in (1,2,3,127,128,129,255,256,257):
        pairs.extend([(raw(F(2*k+1,2)),raw(F(1))), (raw(F(-2*k-1,2)),raw(F(-1)))])
    pairs.extend([(raw(p(1,1023)),(1,0)),((0x7fe0000000000000,1),raw(F(3))),
                  ((0x3ff0000000000000,1),raw(p(1,-1000))),
                  (raw(p(1,-1074)*7),raw(p(1,-1074)*2))])
    rng=random.Random(seed)
    for _ in range(24):
        def sample():
            e=rng.randrange(-1022,1024); h=(rng.randrange(1<<52)|(e+1023)<<52)|(rng.randrange(2)<<63)
            lo=raw(p(rng.randrange(1,1<<20),rng.randrange(-1074,min(e-72,950))))[0] if e>-1000 else 1
            return h,lo|(rng.randrange(2)<<63)
        a,c=sample(),sample();values.append(a);pairs.append((a,c))
    return [[op,list(a),[0,0]] for a in values for op in ('frexp','frexp-null')]+[[op,list(a),list(c)] for a,c in pairs for op in ('fmod','remainder','remquo','remquo-null')]+remainder_midpoints()

def reference(cell):
    op,a,c=cell
    if not op.startswith('frexp'):
        opcode={'fmod':4,'remainder':5,'remquo':6,'remquo-null':9}[op]
        return list(n.expected([106,opcode,*a,*c,0,0,0,0,0,64]))
    k,sign,invalid,v=b.decode(106,a)
    if k!='finite' or not v:
        return [*b.pack(106,k,sign,v),0,int(invalid)]
    e=b.exponent(v)+1;fraction=v/b.scale(1,e)
    rr,flags=n.rounded(106,fraction,sign,0)
    _,_,_,value=b.decode(106,rr)
    assert abs(value)<=1
    if abs(value)==1:e+=1;rr=raw(value/2)
    assert F(1,2)<=abs(b.decode(106,rr)[3])<1
    return [*rr,e if op=='frexp' else 0,flags]

def corpus(path,write=False):
    cells=population();answers=[reference(c) for c in cells]
    # Literal witnesses independently pin the accepted exception and carry.
    assert reference(['frexp',[0x3ff0000000000000,1],[0,0]])==[0x3fe0000000000000,0,1,4]
    assert reference(['frexp',[0x4000000000000000,SIGN|1],[0,0]])==[0x3fe0000000000000,0,2,4]
    witness=['remquo',[0x3ff0000000000000,raw(b.scale(1,-200))[0]],[0x3fe8000000000000,raw(b.scale(1,-100))[0]]]
    assert reference(witness)==[0x3fd0000000000000,raw(-b.scale(1,-100))[0],0,1,4]
    for first,second in [((0x7ff8000000000000,0),(0x7ff0000000000001,0)),
                         ((0x7ff0000000000001,0),(0x7ff8000000000000,0))]:
        for op in ('fmod','remainder','remquo','remquo-null'):
            assert reference([op,list(first),list(second)])==[0x7ff8000000000000,0,0,0,1]
    for value in [(0x7fefffffffffffff,0x7fefffffffffffff),
                  (0xffefffffffffffff,0xffefffffffffffff),
                  (0x3ff0000000000000,0x7ff0000000000001)]:
        assert reference(['frexp',list(value),[0,0]])==[0x7ff8000000000000,0,0,1]
        for op in ('fmod','remainder','remquo','remquo-null'):
            assert reference([op,list(value),list(raw(F(1)))])==[0x7ff8000000000000,0,0,0,1]
    data={'schema':1,'seed':20261106,'cells':cells,'answers':answers,'population_sha256':digest(cells),'answers_sha256':digest(answers)}
    if write:path.write_text(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n')
    literal=json.loads(path.read_text())
    assert literal==data,'DD literal corpus payload/population authentication failed'
    return cells,answers

def check(basic,nine,path,native=False):
    cells,answers=corpus(path)
    literal_count=len(cells)
    fresh_population=population(20261107)
    fresh=[cell for cell in fresh_population if cell[0].startswith('frexp')][-48:]+[cell for cell in fresh_population if not cell[0].startswith('frexp')][-112:-16]
    cells+=fresh;answers+=[reference(c) for c in fresh]
    count=0
    for group,probe in [('frexp',basic),('remainder',nine)]:
        rows=[];wanted=[]
        for cell,answer in zip(cells,answers):
            op,a,c=cell
            if op.startswith('frexp')!=(group=='frexp'):continue
            for mode in range(4):
                for pc in (0,2,3):
                    for incoming in (0,1,2,4,8,16,3,20,31):
                        fmt=0 if native else 106
                        if group=='frexp':
                            rows.append(f'{fmt} {12 if op=="frexp" else 15} {a[0]:x} {a[1]:x} 0 0 {mode} {pc} {incoming}\n')
                        else:
                            opcode={'fmod':4,'remainder':5,'remquo':6,'remquo-null':9}[op]
                            rows.append(' '.join(f'{v:x}' for v in [fmt,opcode,*a,*c,0,0,mode,pc,incoming,64])+'\n')
                        wanted.append((cell,answer,incoming))
        run=subprocess.run([str(probe.resolve())],input=''.join(rows),text=True,capture_output=True,timeout=240)
        assert run.returncode==0,(group,run.stderr)
        lines=run.stdout.splitlines();head=lines.pop(0)
        if native:assert head.startswith('native 106 '),'native DD requested on another ABI: '+head
        assert len(lines)==len(wanted),'DD probe row count'
        for index,(line,(cell,answer,incoming)) in enumerate(zip(lines,wanted)):
            fields=line.split()
            if group=='frexp':
                h,l,wh,wl=(int(x,16) for x in fields[:4]);e,flags,err,state=map(int,fields[4:])
                expected=[answer[0],answer[1],answer[2],answer[3]|incoming]
                got=[h,l,e,flags]
                whole=b.pack(106,'nan',0,F(0)) if not native and b.decode(106,cell[1])[0]=='nan' else (0,0)
                assert (wh,wl)==whole,'DD frexp auxiliary NaN policy'
            else:
                h,l,integer,q=(int(x,16) for x in fields[:4]);flags,err,state,entry=map(int,fields[4:])
                assert entry==incoming,'DD incoming flags setup'
                got=[h,l,integer,q,flags];expected=answer[:-1]+[answer[-1]|incoming]
            assert got==expected and err==173 and state==1,f'DD row {index} {cell}: {got}, expected {expected}, errno={err}, state={state}'
        count+=len(lines)
    profiles=subprocess.run([str(basic.resolve()),'--state'],text=True,capture_output=True,timeout=60)
    assert profiles.returncode==0,'DD frexp profile check failed: '+profiles.stdout+profiles.stderr
    print(profiles.stdout.strip())
    if not native and head.startswith('native 106 '):
        check(basic,nine,path,native=True)
    print(f'DD supplemental: {literal_count} authenticated literals plus {len(fresh)} fresh samples; {count} '+('separate-object native ABI' if native else 'synthetic')+' rows; exact quotient, DD neighbor certificates, modes/flags/controls/errno passed')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--basic',type=Path);ap.add_argument('--nine',type=Path);ap.add_argument('--corpus',type=Path,default=Path('tests/corpus/long-double-dd.json'));ap.add_argument('--write',action='store_true');ap.add_argument('--native',action='store_true');a=ap.parse_args()
    if a.write:corpus(a.corpus,True)
    if a.basic and a.nine:check(a.basic,a.nine,a.corpus,a.native)
    elif not a.write:corpus(a.corpus)
