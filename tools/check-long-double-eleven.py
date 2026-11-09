#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Eleven-family bounded literal population, exact cells and pinned MPFR oracle."""
import sys
if not __debug__ or sys.flags.optimize:
    raise SystemExit('long-double eleven gates require assertion-enabled Python')
import argparse, hashlib, importlib.util, json, os, random, subprocess, tempfile
from fractions import Fraction as F
from pathlib import Path
z=importlib.util.spec_from_file_location('eleven_scale',Path(__file__).with_name('check-long-double-scale.py'))
s=importlib.util.module_from_spec(z);z.loader.exec_module(s);b=s.base
FORMATS=(64,80,128,106)
NAMES='sqrt cbrt hypot exp exp2 expm1 log log2 log10 log1p pow'.split()
PIN='mpfr 4.2.2 gmpy2 2.3.2 mpmath 1.4.1 python 3.14.7'
REFERENCE_SHA256='d360abeec5a0b79b331c4a28fa08d5c18c4faf84146fcb4b1f4778b35d499b5e'
MAX_BYTES=2*1024*1024

def raw(fmt,v,sign=0):return b.pack(fmt,'finite',int(v<0) if v else sign,v)
def cases(seed=20261104):
    rng=random.Random(seed);out=[]
    for fmt in FORMATS:
        minimum=-1074 if fmt in (64,106) else -16445 if fmt==80 else -16494
        tiny=b.scale(1,minimum)
        for op in range(11):
            pairs=[(F(0),F(0)),(F(1),F(2)),(F(2),F(3)),(F(4),F(1,2)),(F(9),F(1,2))]
            if op in (0,1,2):pairs += [(tiny,tiny),(b.scale(1,1000),b.scale(1,999)),(F(-8),F(0)),(F(3),F(4))]
            elif op in (3,4,5):pairs += [(tiny,F(0)),(-tiny,F(0)),(F(-1),F(0)),(F(-12001),F(0)),(F(12001),F(0))]
            elif op in (6,7,8):pairs += [(tiny,F(0)),(F(-1),F(0)),(F(10),F(0)),(F(100),F(0))]
            elif op==9:pairs += [(tiny,F(0)),(-tiny,F(0)),(F(-1),F(0)),(F(-2),F(0)),(F(-1,2),F(0))]
            else:pairs += [(F(-1),F(1,2)),(F(-8),F(3)),(F(0),F(-3)),(F(2),F(-1074)),(F(4),F(-1,2))]
            for _ in range(3):
                x=F(rng.randrange(1,1<<20),1<<16);y=F(rng.randrange(-50,51),8)
                pairs.append((x,y))
            for x,y in pairs:out.append([fmt,op,*raw(fmt,x),*raw(fmt,y)])
            zero=raw(fmt,F(0));inf=b.pack(fmt,'inf',0,F(0));nan=b.pack(fmt,'nan',0,F(0))
            out += [[fmt,op,*inf,*zero],[fmt,op,*nan,*zero]]
        if fmt==106:
            out += [[106,6,0x3ff0000000000000,1,0,0],[106,3,1,0,0,0],
                    [106,10,0x3ff0000000000000,1,0x7fe0000000000000,0],
                    [106,0,0x3ff0000000000000,1,0,0],[106,1,0x3ff0000000000000,1,0,0],
                    [106,2,0x3ff0000000000000,0,1,0]]
    return out

def rounding(fmt,v):return s.rounded(fmt,v,int(v<0))
def special(row):
    fmt,op,ah,al,bh,bl=row;k,sg,iv,x=b.decode(fmt,(ah,al));kb,sb,ib,y=b.decode(fmt,(bh,bl)) if op in (2,10) else ('finite',0,False,F(0))
    nan=b.pack(fmt,'nan',0,F(0));zero=raw(fmt,F(0));one=raw(fmt,F(1))
    if iv or ib:return nan,1,None
    if op==2 and (k=='inf' or kb=='inf'):return b.pack(fmt,'inf',0,F(0)),0,None
    if op==10:
        if kb=='finite' and not y or k=='finite' and x==1:return one,0,None
        if k=='nan' or kb=='nan':return nan,0,None
        odd=y.denominator==1 and bool(y.numerator&1)
        sign=sg and odd
        if kb=='inf':
            if abs(x)==1:return one,0,None
            big=k=='inf' or abs(x)>1
            return (b.pack(fmt,'inf',0,F(0)) if big!=bool(sb) else zero),0,None
        if k=='inf' or not x:
            if not x and k=='finite' and y<0:return b.pack(fmt,'inf',sign,F(0)),2,None
            infinity=(k=='inf')!=(y<0)
            return b.pack(fmt,'inf' if infinity else 'finite',sign,F(0)),0,None
        if x<0 and y.denominator!=1:return nan,1,None
        if abs(x)==1:return raw(fmt,F(-1 if odd else 1)),0,None
    elif k=='nan' or kb=='nan':return nan,0,None
    if op in (0,1):
        if op==0 and sg and (k=='inf' or x):return nan,1,None
        if k=='inf' or not x:return b.pack(fmt,k,sg,x),0,None
    if op==2 and not x and not y:return zero,0,None
    if op in (3,4,5):
        if k=='inf':return (raw(fmt,F(-1)) if op==5 and sg else zero if sg else b.pack(fmt,'inf',0,F(0))),0,None
        if not x:return (raw(fmt,F(0),sg) if op==5 else one),0,None
    if op in (6,7,8,9):
        if k=='inf':return (nan,1,None) if sg else (b.pack(fmt,'inf',0,F(0)),0,None)
        if op==9 and not x:return raw(fmt,F(0),sg),0,None
        arg=1+x if op==9 else x
        if not arg:return b.pack(fmt,'inf',1,F(0)),2,None
        if arg<0:return nan,1,None
        if arg==1:return zero,0,None
    return None

def mpfr_oracle(row,directed=False):
    import gmpy2 as g,mpmath as mp,platform
    actual=f'{g.mpfr_version().lower()} gmpy2 {g.version()} mpmath {mp.__version__} python {platform.python_version()}'
    if actual!=PIN:raise RuntimeError('required pinned oracle mismatch: '+actual)
    direct=special(row)
    if direct:
        if directed:
            answer,flags,_=direct;value=b.decode(row[0],answer)[3];return answer,flags,encode_bounds(value,value)
        return direct
    fmt,op,ah,al,bh,bl=row;x=b.decode(fmt,(ah,al))[3];y=b.decode(fmt,(bh,bl))[3]
    # More than the complete DD component span plus all finite pow amplification.
    def evaluate(rounding):
        with g.context(precision=5000,round=rounding,emin=-100000,emax=100000):
            xx=g.mpfr(g.mpq(x.numerator,x.denominator));yy=g.mpfr(g.mpq(y.numerator,y.denominator))
            fun=[g.sqrt,g.cbrt,None,g.exp,g.exp2,g.expm1,g.log,g.log2,g.log10,g.log1p,None][op]
            v=g.sqrt(xx*xx+yy*yy) if op==2 else xx**yy if op==10 else fun(xx)
            if g.is_infinite(v):return v
            return F(*v.as_integer_ratio())
    lo,hi=evaluate(g.RoundDown),evaluate(g.RoundUp)
    if not isinstance(lo,F) or not isinstance(hi,F):
        # Inputs selected here only overflow the destination, not the MPFR range.
        raise RuntimeError('oracle working exponent range exhausted')
    left=rounding(fmt,lo);right=rounding(fmt,hi)
    if left!=right:raise RuntimeError('literal nearest cell not closed at5000bits: '+str(row))
    expected=left;kind,_,_,rounded_value=b.decode(fmt,expected)
    flags=20 if kind=='inf' else 0 if lo==hi==rounded_value else 12 if abs(rounded_value)<b.scale(1,-969 if fmt==106 else -1022 if fmt==64 else -16382) else 4
    # Independent mpmath evaluation must lie in the directed MPFR enclosure.
    with mp.workprec(5100):
        xx=mp.mpf(x.numerator)/x.denominator;yy=mp.mpf(y.numerator)/y.denominator
        v=(mp.sign(xx)*mp.root(abs(xx),3) if op==1 else mp.sqrt(xx*xx+yy*yy) if op==2 else
           mp.power(xx,yy) if op==10 else [mp.sqrt,None,None,mp.exp,lambda z:mp.power(2,z),mp.expm1,mp.log,lambda z:mp.log(z,2),mp.log10,mp.log1p][op](xx))
        sign,man,ex,_=v._mpf_;mv=b.scale(-man if sign else man,ex)
        # Mpmath's independent rounded value can differ from an exact endpoint
        # by its last bit; pad by its documented working precision unit.
        pad=b.scale(1,b.exponent(mv)-5090) if mv else b.scale(1,-5090)
        if not lo-pad<=mv<=hi+pad:raise RuntimeError('mpmath/MPFR disagreement')
    # Exact roots are additionally proved by rational powers.
    rv=b.decode(fmt,expected)[3];target=x if op<2 else x*x+y*y
    if op<3 and kind=='inf':
        # Finite hypot can overflow. Infinity has no finite neighbor value:
        # compare the exact radicand with the virtual overflow midpoint.
        limit=s.LIMIT if fmt==106 else b.scale(1,1024 if fmt==64 else 16384)-b.scale(1,(1023 if fmt==64 else 16383)-(52 if fmt==64 else 63 if fmt==80 else 112))
        spacing=b.scale(1,917 if fmt==106 else (1023 if fmt==64 else 16383)-(52 if fmt==64 else 63 if fmt==80 else 112))
        if op!=2 or target<(limit+spacing/2)**2:raise RuntimeError('exact virtual overflow midpoint certificate')
        flags=20
    elif op<3:
        degree=3 if op==1 else 2;sign=rv<0;av=abs(rv);target=abs(target)
        prev=s.neighbor(fmt,av,-1);nxt=s.neighbor(fmt,av,1)
        pv=b.decode(fmt,prev)[3];nk,_,_,nv=b.decode(fmt,nxt)
        if ((pv+av)/2)**degree>target or nk=='finite' and target>((nv+av)/2)**degree:raise RuntimeError('exact root midpoint certificate')
        exact=av**degree==target
        flags=0 if exact else 12 if av<b.scale(1,-969 if fmt==106 else -1022 if fmt==64 else -16382) else 4
    else:
        # Irrational intervals add IX even when their endpoint's dyadic packing
        # happens to be exact; exact algebraic identities have collapsed bounds.
        if lo!=hi and not flags:flags=4
        if flags==4 and b.decode(fmt,expected)[0]=='finite' and abs(rv)<b.scale(1,-969 if fmt==106 else -1022 if fmt==64 else -16382):flags=12
    enclosure=None
    if op>=3 and b.decode(fmt,expected)[0]=='finite':
        predecessor=s.neighbor(fmt,rv,-1);successor=s.neighbor(fmt,rv,1)
        pk,_,_,pv=b.decode(fmt,predecessor);nk,_,_,nv=b.decode(fmt,successor)
        if pk=='finite' and lo<pv or nk=='finite' and hi>nv:raise RuntimeError('open local-ULP error cell')
        enclosure=[f'{v:016x}' for v in (*predecessor,*successor)]
    return expected,flags,encode_bounds(lo,hi) if directed else enclosure

def encode_bounds(lo,hi):
    encoded=[]
    for value in (lo,hi):
        n,d=value.numerator,value.denominator
        shift=(abs(n)&-abs(n)).bit_length()-1 if n else 0
        encoded.extend([format(n>>shift,'x'),shift-(d.bit_length()-1)])
    return encoded

def decode_bounds(fields):
    if len(fields)!=4 or any(type(fields[i])!=str or len(fields[i])>1500 for i in (0,2)) or any(type(fields[i])!=int or abs(fields[i])>100000 for i in (1,3)):raise ValueError('bounded directed enclosure fields')
    lo=b.scale(int(fields[0],16),fields[1]);hi=b.scale(int(fields[2],16),fields[3])
    if lo>hi:raise ValueError('reversed directed enclosure')
    return lo,hi

BOUNDARY_SHA256='c396580e38043dc07c87a39f3c2e315fef6b4732bdc602a885e009ce39191e6e'
def boundary_inputs():
    import gmpy2 as g
    rows=[]
    for fmt in FORMATS:
        maximum=1023 if fmt in (64,106) else 16383
        minimum=-1074 if fmt in (64,106) else -16445 if fmt==80 else -16494
        normal=-969 if fmt==106 else -1022 if fmt==64 else -16382
        p=53 if fmt==64 else 64 if fmt==80 else 113
        gap=b.scale(1,917 if fmt==106 else maximum-p+1)
        limit=s.LIMIT if fmt==106 else b.scale(1,maximum+1)-gap
        targets=[limit+gap/2,b.scale(1,minimum-1),b.scale(1,normal)-b.scale(1,minimum-1)]
        for op in (3,5,10):
            for target in targets:
                with g.context(precision=5000,emin=-100000,emax=100000):
                    value=g.mpfr(g.mpq(target.numerator,target.denominator))
                    argument=g.log(value) if op==3 else g.log1p(value) if op==5 else g.root(value,3)
                    center=rounding(fmt,F(*argument.as_integer_ratio()))
                cv=b.decode(fmt,center)[3]
                candidates=[center,s.neighbor(fmt,cv,-1),s.neighbor(fmt,cv,1)]
                for candidate in candidates:
                    v=b.decode(fmt,candidate)[3]
                    rows.append([fmt,op,*candidate,*raw(fmt,F(3) if op==10 else F(0))])
                    if op==10:rows.append([fmt,op,*raw(fmt,-v),*raw(fmt,F(3))])
    # Finite overflow and its adjacent last-finite cell are independently certified.
    for fmt in FORMATS:
        p=53 if fmt==64 else 64 if fmt==80 else 113;maximum=1023 if fmt in (64,106) else 16383
        gap=b.scale(1,917 if fmt==106 else maximum-p+1);limit=s.LIMIT if fmt==106 else b.scale(1,maximum+1)-gap
        rows.append([fmt,2,*raw(fmt,limit),*raw(fmt,limit)])
    # Positive base two isolates range transitions driven by a large,
    # fractional exponent rather than the existing fixed odd exponent three.
    for fmt in FORMATS:
        maximum=1023 if fmt in (64,106) else 16383
        minimum=-1074 if fmt in (64,106) else -16445 if fmt==80 else -16494
        normal=-969 if fmt==106 else -1022 if fmt==64 else -16382
        p=53 if fmt==64 else 64 if fmt==80 else 113
        gap=b.scale(1,917 if fmt==106 else maximum-p+1)
        limit=s.LIMIT if fmt==106 else b.scale(1,maximum+1)-gap
        targets=[limit+gap/2,b.scale(1,minimum-1),b.scale(1,normal)-b.scale(1,minimum-1)]
        for target in targets:
            with g.context(precision=5000,emin=-100000,emax=100000):
                value=g.mpfr(g.mpq(target.numerator,target.denominator))
                center=rounding(fmt,F(*g.log2(value).as_integer_ratio()))
            exponent=b.decode(fmt,center)[3]
            for candidate in (center,s.neighbor(fmt,exponent,-1),s.neighbor(fmt,exponent,1)):
                rows.append([fmt,10,*raw(fmt,F(2)),*candidate])
    return list(dict.fromkeys(tuple(row) for row in rows))

def generate_boundaries(directory):
    existing=json.loads((directory/'long-double-eleven.boundaries.json').read_bytes())['cells']
    cells=[]
    for row in boundary_inputs():
        result,flags,enclosure=mpfr_oracle(list(row),True);cells.append([int(v) for v in row]+[int(v) for v in result]+[int(flags),enclosure])
    if cells[:len(existing)]!=existing:raise RuntimeError('existing boundary answers changed')
    payload=(json.dumps({'oracle':PIN,'cells':cells},separators=(',',':'))+'\n').encode()
    (directory/'long-double-eleven.boundaries.json').write_bytes(payload)
    (directory/'long-double-eleven.boundaries.hash').write_text(hashlib.sha256(payload).hexdigest()+'\n')
    print('generated supplemental MPFR-certified transition cells',len(cells),hashlib.sha256(payload).hexdigest())

def boundary_population(cells):
    rows=[tuple(cell[:6]) for cell in cells]
    if len(rows)!=len(set(rows)):raise ValueError('boundary duplicate input row')
    for fmt in FORMATS:
        actual={op:sum(cell[0]==fmt and cell[1]==op for cell in cells) for op in (2,3,5,10)}
        if actual!={2:1,3:9,5:9,10:27}:raise ValueError('boundary per-format/op population')
        powers=[cell for cell in cells if cell[0]==fmt and cell[1]==10]
        twos=[cell for cell in powers if b.decode(fmt,tuple(cell[2:4]))[3]==2]
        odds=[cell for cell in powers if b.decode(fmt,tuple(cell[4:6]))[3]==3]
        if len(twos)!=9 or len(odds)!=18 or sum(b.decode(fmt,tuple(cell[2:4]))[1] for cell in odds)!=9:raise ValueError('boundary power-family population')

def load_boundaries(directory):
    path=directory/'long-double-eleven.boundaries.json';payload=bounded_bytes(path,MAX_BYTES)
    if hashlib.sha256(payload).hexdigest()!=BOUNDARY_SHA256 or bounded_bytes(directory/'long-double-eleven.boundaries.hash',65).decode()!=BOUNDARY_SHA256+'\n':raise ValueError('boundary full pin mismatch')
    data=json.loads(payload)
    if set(data)!={'oracle','cells'} or data['oracle']!=PIN:raise ValueError('boundary metadata')
    if len(data['cells'])!=184:raise ValueError('boundary input population count')
    for cell in data['cells']:
        if len(cell)!=10 or cell[0] not in FORMATS or cell[1] not in (2,3,5,10) or any(type(v)!=int or not 0<=v<1<<64 for v in cell[:9]) or cell[8]>31:raise ValueError('boundary field')
        decode_bounds(cell[9])
    boundary_population(data['cells'])
    return data['cells']


def generate(directory):
    cells=[]
    for row in cases():
        answer,flags,enclosure=mpfr_oracle(row);cells.append(row+[int(v) for v in answer]+[int(flags),enclosure])
    payload=(json.dumps({'seed':20261104,'oracle':PIN,'cells':cells},separators=(',',':'))+'\n').encode()
    if len(payload)>MAX_BYTES:raise RuntimeError('literal population exceeds bounded loader')
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'long-double-eleven.json').write_bytes(payload)
    (directory/'long-double-eleven.hash').write_text(hashlib.sha256(payload).hexdigest()+'\n')
    print('generated pinned MPFR/mpmath/exact-root cells',len(cells))

def bounded_bytes(path,limit):
    if path.stat().st_size>limit:raise ValueError('oversized bounded input '+str(path))
    with path.open('rb') as stream:payload=stream.read(limit+1)
    if len(payload)>limit:raise ValueError('oversized bounded input '+str(path))
    return payload

def load(directory):
    path=directory/'long-double-eleven.json';payload=bounded_bytes(path,MAX_BYTES)
    if len(payload)>MAX_BYTES:raise ValueError('oversized literal population')
    digest=bounded_bytes(directory/'long-double-eleven.hash',65).decode('ascii')
    if digest!=REFERENCE_SHA256+'\n' or digest!=hashlib.sha256(payload).hexdigest()+'\n':raise ValueError('literal hash/pin mismatch')
    data=json.loads(payload)
    if payload!=(json.dumps(data,separators=(',',':'))+'\n').encode():raise ValueError('noncanonical or duplicate literal fields')
    if set(data)!={'seed','oracle','cells'} or data['seed']!=20261104 or data['oracle']!=PIN:raise ValueError('literal metadata mismatch')
    if len(data['cells'])!=len(cases()):raise ValueError('literal count mismatch')
    for expected,cell in zip(cases(),data['cells'],strict=True):
        if len(cell)!=10 or cell[:6]!=expected or any(type(v)!=int or not 0<=v<1<<64 for v in cell[:9]):raise ValueError('literal field/input population mismatch')
        if cell[8]>31:raise ValueError('literal flag mismatch')
        enclosure=cell[9]
        if enclosure is not None:
            if len(enclosure)!=4 or any(type(v)!=str or len(v)!=16 or any(ch not in '0123456789abcdef' for ch in v) for v in enclosure):raise ValueError('bounded enclosure field')
            nums=[int(v,16) for v in enclosure];value=b.decode(cell[0],tuple(cell[6:8]))[3]
            if tuple(nums[:2])!=s.neighbor(cell[0],value,-1) or tuple(nums[2:])!=s.neighbor(cell[0],value,1):raise ValueError('invalid population cell')
    return data

def prepare(directory):
    data=load(directory);rows=[]
    for c in data['cells']:
        # Every literal has a synthetic baseline. Boundary cells also span all
        # caller rounding modes, x87 PCs, separately seeded flags and DAZ/FTZ.
        rows.append(c[:6]+[0,3,0,0]+c[6:9])
    payload=''.join(' '.join(f'{v:x}' for v in r)+'\n' for r in rows).encode()
    cache=directory/'long-double-eleven.corpus'
    if cache.exists():
        if bounded_bytes(cache,len(payload))!=payload:raise ValueError('corrupt cache (left unchanged)')
    else:
        fd,tmp=tempfile.mkstemp(prefix='.long-double-eleven.',dir=directory)
        try:
            with os.fdopen(fd,'wb') as out:
                if out.write(payload)!=len(payload):raise OSError('short cache write')
                out.flush();os.fsync(out.fileno())
            if bounded_bytes(Path(tmp),len(payload))!=payload:raise ValueError('corrupt temporary cache write')
            try:os.link(tmp,cache)
            except FileExistsError:
                if bounded_bytes(cache,len(payload))!=payload:raise ValueError('racing corrupt cache')
        finally:os.unlink(tmp)
    return data

def verify_boundary_output(cell,actual,flags):
    fmt,op=cell[:2];expected=tuple(cell[6:8])
    if op==2 or cell[8]==0:
        if actual!=expected or flags!=cell[8]:raise RuntimeError('exact root/identity boundary output')
        return
    lo,hi=decode_bounds(cell[9]);kind,sign,_,value=b.decode(fmt,actual)
    if kind=='nan' or sign!=b.decode(fmt,expected)[1]:raise RuntimeError('boundary result kind/sign')
    if actual!=b.pack(fmt,kind,sign,value):raise RuntimeError('boundary noncanonical '+kind+' encoding')
    if kind=='inf':
        limit=s.LIMIT if fmt==106 else b.scale(1,1024 if fmt==64 else 16384)-b.scale(1,(1023 if fmt==64 else 16383)-(52 if fmt==64 else 63 if fmt==80 else 112))
        if (sign and hi> -limit) or (not sign and lo<limit) or flags!=20:raise RuntimeError('boundary infinity enclosure/flags')
    else:
        predecessor=b.decode(fmt,s.neighbor(fmt,value,-1));successor=b.decode(fmt,s.neighbor(fmt,value,1))
        # Infinity denotes the signed virtual endpoint beyond the last finite
        # value. DD's last gap is 2^917, not its leading component's spacing.
        outer=s.LIMIT+b.scale(1,917) if fmt==106 else b.scale(1,1024 if fmt==64 else 16384)
        lower=predecessor[3] if predecessor[0]=='finite' else -outer
        upper=successor[3] if successor[0]=='finite' else outer
        if lo<lower or hi>upper:raise RuntimeError('boundary selected-neighbor enclosure')
        required=0 if lo==hi==value else 12 if abs(value)<b.scale(1,-969 if fmt==106 else -1022 if fmt==64 else -16382) else 4
        if flags!=required:raise RuntimeError('boundary selected-result flags')

def check(probe,directory,native_only=False,boundary_only=False):
    data=prepare(directory)
    boundaries=load_boundaries(directory);boundary_cell_ids={id(cell) for cell in boundaries}
    data={'cells':boundaries if boundary_only else data['cells']+boundaries}
    rows=[];expected=[]
    for c in data['cells']:
        rows.append(c[:6]+[0,3,0,0]);expected.append(c)
    if native_only:rows=[];expected=[]
    probe_input=''.join(' '.join(f'{v:x}' for v in r)+'\n' for r in rows) if rows else '40 0 0 0 0 0 0 3 0 0\n'
    proc=subprocess.run([str(probe)],input=probe_input,text=True,capture_output=True,timeout=1800)
    if proc.returncode:raise RuntimeError('production probe failed '+str(proc.returncode)+' '+proc.stderr)
    lines=proc.stdout.splitlines();header=lines.pop(0).split();native=int(header[1])
    if native_only:lines=[]
    if len(lines)!=len(rows):raise ValueError('probe count mismatch')
    for row,c,line in zip(rows,expected,lines,strict=True):
        fields=line.split()
        if len(fields)!=6:raise ValueError('probe output field count')
        actual=(int(fields[0],16),int(fields[1],16));flags,err,controls,entry=map(int,fields[2:])
        if id(c) in boundary_cell_ids:verify_boundary_output(c,actual,flags)
        if (id(c) not in boundary_cell_ids and (actual!=tuple(c[6:8]) or flags!=c[8])) or err!=173 or controls!=1 or entry!=0:
            raise RuntimeError(f'cell mismatch {row}: got{line}; expected{c[6:9]}')
    # Separate native ABI execution, using literal raw bytes until classification.
    native_cells=[c for c in data['cells'] if c[0]==native]
    native_rows=[[0]+c[1:6]+[0,3,0,0] for c in native_cells]
    proc=subprocess.run([str(probe)],input=''.join(' '.join(f'{v:x}' for v in r)+'\n' for r in native_rows),text=True,capture_output=True,timeout=1800,check=True)
    lines=proc.stdout.splitlines()[1:]
    if len(lines)!=len(native_cells):raise ValueError('native count mismatch')
    for c,line in zip(native_cells,lines,strict=True):
        p=line.split();got=(int(p[0],16),int(p[1],16),*map(int,p[2:]))
        if id(c) in boundary_cell_ids:verify_boundary_output(c,got[:2],got[2])
        if (id(c) not in boundary_cell_ids and got!=(*c[6:9],173,1,0)) or got[3:]!=(173,1,0):raise RuntimeError(f'native ABI mismatch {c[:6]} {got} {c[6:9]}')
    print(f'long-double eleven: {len(rows)} synthetic and {len(native_cells)} native{native} pinned cells pass')

def verify_oracle(data,directed=False):
    if directed and [tuple(cell[:6]) for cell in data['cells']]!=boundary_inputs():raise RuntimeError('boundary input sequence differs from transition registry')
    for cell in data['cells']:
        answer,flags,enclosure=mpfr_oracle(cell[:6],directed)
        if tuple(answer)!=tuple(cell[6:8]) or flags!=cell[8] or enclosure!=cell[9]:raise RuntimeError('repinned bad literal answer/enclosure')

def repinned_control(data):
    global REFERENCE_SHA256
    original=REFERENCE_SHA256
    bad=json.loads(json.dumps(data));bad['cells'][0][6:8]=list(raw(bad['cells'][0][0],F(1)))
    with tempfile.TemporaryDirectory(prefix='eleven-repinned-') as temp:
        directory=Path(temp);payload=(json.dumps(bad,separators=(',',':'))+'\n').encode();REFERENCE_SHA256=hashlib.sha256(payload).hexdigest()
        (directory/'long-double-eleven.json').write_bytes(payload);(directory/'long-double-eleven.hash').write_text(REFERENCE_SHA256+'\n')
        try:
            loaded=load(directory)
            try:verify_oracle(loaded)
            except RuntimeError as error:
                if 'repinned bad literal' not in str(error):raise
            else:raise RuntimeError('fully repinned bad answer escaped numerical oracle')
        finally:REFERENCE_SHA256=original
    print('repinned JSON/hash/sourceconstant bad answer rejected numerically after successful load')

def boundary_registry_control(data):
    global BOUNDARY_SHA256
    saved=BOUNDARY_SHA256
    bad=json.loads(json.dumps(data));row=bad['cells'][-1][:6]
    row[4:6]=list(raw(row[0],F(7,4)))
    answer,flags,bounds=mpfr_oracle(row,True)
    bad['cells'][-1]=row+[int(v) for v in answer]+[int(flags),bounds]
    # This replacement is numerically valid and retains all cheap populations.
    # Only the independently regenerated transition registry can reject it.
    with tempfile.TemporaryDirectory(prefix='eleven-registry-') as temp:
        directory=Path(temp);payload=(json.dumps(bad,separators=(',',':'))+'\n').encode();BOUNDARY_SHA256=hashlib.sha256(payload).hexdigest()
        (directory/'long-double-eleven.boundaries.json').write_bytes(payload);(directory/'long-double-eleven.boundaries.hash').write_text(BOUNDARY_SHA256+'\n')
        try:
            loaded=load_boundaries(directory)
            try:verify_oracle({'cells':loaded},True)
            except RuntimeError as error:
                if 'boundary input sequence differs from transition registry' not in str(error):raise
            else:raise RuntimeError('fully repinned substituted transition input accepted')
        finally:BOUNDARY_SHA256=saved
    print('fully repinned numerically valid substituted input rejected by independent transition registry')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('tests/corpus'));p.add_argument('--probe',type=Path);p.add_argument('--native-only',action='store_true');p.add_argument('--generate',action='store_true');p.add_argument('--generate-boundaries',action='store_true');p.add_argument('--boundary-only',action='store_true');p.add_argument('--verify-oracle',action='store_true');p.add_argument('--fresh-json',type=Path);p.add_argument('--prepare',action='store_true');a=p.parse_args()
    if a.verify_oracle:
        data=load(a.directory)
        verify_oracle(data)
        verify_oracle({'cells':load_boundaries(a.directory)},True)
        boundary_registry_control({'oracle':PIN,'cells':load_boundaries(a.directory)})
        repinned_control(data)
        print('mandatory pinned MPFR/mpmath/exact-root oracle verified',len(data['cells']),'original and',len(load_boundaries(a.directory)),'supplemental transition cells')
        if a.fresh_json:
            seed=int.from_bytes(os.urandom(4),'little');known={tuple(c[:6]) for c in data['cells']};selected={}
            for row in cases(seed):
                key=tuple(row[:2])
                if tuple(row) not in known and key not in selected:
                    answer,flags,enclosure=mpfr_oracle(row);selected[key]=row+[int(v) for v in answer]+[int(flags),enclosure]
            if len(selected)!=44:raise RuntimeError('fresh population incomplete')
            a.fresh_json.write_text(json.dumps({'seed':seed,'cells':list(selected.values())})+'\n')
            print('fresh directed MPFR/mpmath/exact cells',len(selected),'seed',seed)
    elif a.generate_boundaries:generate_boundaries(a.directory)
    elif a.generate:generate(a.directory)
    elif a.prepare:print('long-double eleven cache cells',len(prepare(a.directory)['cells']))
    elif a.probe:check(a.probe,a.directory,a.native_only,a.boundary_only)
    else:p.error('choose --generate, --prepare or --probe')
