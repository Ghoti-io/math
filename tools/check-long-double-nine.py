#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent Fraction decisions and literal-answer integrity for nine APIs.

The unchanged foundation decodes bytes; the DD interval certificate proves
population brackets independently of candidate enumeration. No host libm is
used as a numerical oracle. Production callers are separately compiled.
"""
import sys
if not __debug__ or sys.flags.optimize:
    raise SystemExit("long-double nine gates require assertion-enabled Python")

import argparse, hashlib, importlib.util, json, os, random, re, subprocess, tempfile
from fractions import Fraction as F
from pathlib import Path
spec=importlib.util.spec_from_file_location('scale_oracle',Path(__file__).with_name('check-long-double-scale.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
b=s.base
scale,decode,pack,exponent=b.scale,b.decode,b.pack,b.exponent
MASK=(1<<64)-1
FORMATS=(64,80,128,106)

def integer(v,mode,away=False):
    sign=v<0;q,r=divmod(abs(v).numerator,abs(v).denominator)
    if away:inc=2*r>=abs(v).denominator
    elif mode==1:inc=bool(r) and sign
    elif mode==2:inc=bool(r) and not sign
    elif mode==3:inc=False
    else:inc=2*r>abs(v).denominator or (2*r==abs(v).denominator and q&1)
    return (-1 if sign else 1)*(q+int(inc))

def rounded(fmt,v,sign,mode):
    """Return bytes and exception classes, using exact target-grid division."""
    if not v:return pack(fmt,'finite',sign,F(0)),0
    if fmt==106:
        if abs(v)>s.LIMIT and mode:
            inward=mode==3 or mode==1 and not sign or mode==2 and sign
            if inward:
                rv=-s.LIMIT if sign else s.LIMIT
                return pack(fmt,'finite',sign,rv),20 if abs(v)>=s.LIMIT+scale(1,917) else 4
            return pack(fmt,'inf',sign,F(0)),20
        nearest=s.rounded(fmt,v,sign)
        k,_,_,nv=decode(fmt,nearest)
        if mode and (k=='inf' or nv!=v):
            d=-1 if mode==1 else 1 if mode==2 else 1 if sign else -1
            choices=[x for x in s.dd_candidates(v) if (x-v)*d>=0]
            if choices:nv=min(choices) if d>0 else max(choices);k='finite'
            else:k='inf'
        if k=='finite':
            result=pack(fmt,k,int(nv<0) if nv else sign,nv)
            if nv!=v:
                # Bracket the exact value using an endpoint on either side.
                reflected=2*v-nv
                other=s.neighbor(fmt,nv,1 if nv<v else -1)
                ok,_,_,ov=decode(fmt,other)
                if ok=='finite':
                    s.dd_no_interior(nv,ov)
                    assert min(nv,ov)<=v<=max(nv,ov)
                    if mode==0:
                        assert abs(v-nv)<=abs(v-ov)
                        if abs(v-nv)==abs(v-ov):s.dd_midpoint_parity(v,nv)
                elif mode==0:assert abs(v)<s.LIMIT+scale(1,916)
                del reflected
            overflow=abs(v)>=s.LIMIT+scale(1,917)
            flags=20 if overflow else (12 if abs(nv)<scale(1,-969) else 4) if nv!=v else 0
            return result,flags
        return pack(fmt,'inf',sign,F(0)),20
    p,bias=(53,1023) if fmt==64 else (64,16383) if fmt==80 else (113,16383)
    cut=max(exponent(v)-p+1,2-bias-p)
    q=abs(integer(v/scale(1,cut),mode))
    rv=scale(-q if sign else q,cut)
    # Directed inward overflow occurs when unbounded rounding reaches 2^(bias+1).
    if abs(rv)>=scale(1,bias+1):
        inward=mode==3 or mode==1 and not sign or mode==2 and sign
        if inward:
            rv=(-1 if sign else 1)*(scale(1,bias+1)-scale(1,bias-p+1))
            return pack(fmt,'finite',sign,rv),20
        return pack(fmt,'inf',sign,F(0)),20
    raw=pack(fmt,'finite',sign,rv)
    return raw,(12 if abs(rv)<scale(1,1-bias) else 4) if rv!=v else 0

def expected(row):
    fmt,op,ah,al,bh,bl,ch,cl,mode,pc,incoming,bits=row
    ka,sa,ia,a=decode(fmt,(ah,al));kb,sb,ib,y=decode(fmt,(bh,bl));kc,sc,ic,z=decode(fmt,(ch,cl))
    if op<4:
        n=integer(a,mode,away=op<2) if ka=='finite' else -(1<<(bits-1))
        bad=ka!='finite' or not -(1<<(bits-1))<=n<(1<<(bits-1))
        if bad:n=-(1<<(bits-1))
        f=1 if bad else 4 if op>=2 and F(n)!=a else 0
        return (0,0,n&MASK,0,f|incoming)
    invalid=ia or ib or (ic if op==8 else False)
    if op==8:invalid|=ka=='inf' and kb=='finite' and not y or kb=='inf' and ka=='finite' and not a
    nan=invalid or ka=='nan' or kb=='nan' or (kc=='nan' if op==8 else False)
    if nan:return (*pack(fmt,'nan',0,F(0)),0,0,incoming|int(bool(invalid)))
    q=0
    if op in (4,5,6,9):
        if ka=='inf' or kb=='finite' and not y:return (*pack(fmt,'nan',0,F(0)),0,0,incoming|1)
        if kb=='inf' or not a:return (*pack(fmt,'finite',sa,a),0,0,incoming)
        q=integer(a/y,3 if op==4 else 0);v=a-q*y
        q=(-1 if q<0 else 1)*(abs(q)%128) if op==6 else 0
        if fmt==106:
            raw,flags=rounded(fmt,v,int(v<0) if v else sa,0)
            return (*raw,0,q&MASK,incoming|flags)
        return (*pack(fmt,'finite',int(v<0) if v else sa,v),0,q&MASK,incoming)
    if op==7:
        if ka=='inf' and kb=='inf' and sa==sb:return (0,0,0,0,incoming)
        if ka=='inf':return (*pack(fmt,'inf',0,F(0)),0,0,incoming) if not sa else (0,0,0,0,incoming)
        if kb=='inf':return (*pack(fmt,'inf',0,F(0)),0,0,incoming) if sb else (0,0,0,0,incoming)
        v=max(a-y,F(0));raw,flags=rounded(fmt,v,0,0)
    else:
        ps=sa^sb
        if ka=='inf' or kb=='inf':
            if kc=='inf' and sc!=ps:return (*pack(fmt,'nan',0,F(0)),0,0,incoming|1)
            return (*pack(fmt,'inf',ps,F(0)),0,0,incoming)
        if kc=='inf':return (*pack(fmt,'inf',sc,F(0)),0,0,incoming)
        v=a*y+z;sign=int(v<0) if v else ps if ps==sc else int(mode==1)
        raw,flags=rounded(fmt,v,sign,mode)
    return (*raw,0,0,incoming|flags)

def fixtures(seed=20261104,count=32):
    rng=random.Random(seed);rows=[]
    for fmt in FORMATS:
        def raw(v,sign=0):return pack(fmt,'finite',int(v<0) if v else sign,F(v))
        minimum=-1074 if fmt in (64,106) else -16445 if fmt==80 else -16494
        maximum=1023 if fmt in (64,106) else 16383
        p=53 if fmt==64 else 64 if fmt==80 else 113 if fmt==128 else 106
        values=[raw(0),raw(0,1),raw(1),raw(-1),raw(F(1,2)),raw(-F(1,2)),raw(F(3,2)),raw(F(5,2))]
        for e in (minimum,minimum+1,-970,-969,-1,0,31,32,63,64,maximum):
            for sign in (1,-1):values.append(raw(sign*scale(1,e)))
        for width in (32,64):
            for v in (scale(1,width-1),scale(1,width-1)-F(1,2),scale(1,width-1)-F(3,2),scale(1,width-1)+F(1,2)):
                values.extend([raw(v),raw(-v)])
        values.extend([pack(fmt,'inf',i,F(0)) for i in (0,1)])
        values.append(pack(fmt,'nan',0,F(0)))
        if fmt==64:values.extend([(0x7ff0000000000001,0),(0x7fefffffffffffff,0)])
        elif fmt==80:values.extend([(0x7fff,0x8000000000000001),(0x3fff,1),(0,1<<63),(0x7ffe,MASK),(0, (1<<63)-1)])
        elif fmt==128:values.extend([(0x7fff000000000000,1),(0x7ffeffffffffffff,MASK),(0x0000ffffffffffff,MASK)])
        else:values.extend([(0x3ff0000000000000,1),(0x3ff0000000000000,0x8000000000000001),(0x3ff0000000000000,0xbff0000000000000),(0x3ff0000000000000,0x7ff0000000000001),(0x7fefffffffffffff,0x7c8fffffffffffff),(0x7fefffffffffffff,0x7c90000000000000)])
        for _ in range(count):
            v=scale(rng.randrange(1,1<<min(p,113)),rng.randrange(minimum-p+1,maximum-p+1))
            values.append(raw(-v if rng.getrandbits(1) else v))
        values=list(dict.fromkeys(values))
        for index,a in enumerate(values):
            for op in range(10):
                if fmt==106 and op in (4,5,6,9):continue # Frozen historical reference population.
                widths=(32,64) if op in (0,2) else (64,)
                for bits in widths:
                    for mode in range(4):
                        y=values[(index+7)%len(values)] if op>=4 else (0,0)
                        z=values[(index*3+5)%len(values)] if op==8 else (0,0)
                        inc=(0,1,2,4,8,16,31)[index%7];pc=(0,2,3)[index%3]
                        rows.append((fmt,op,*a,*y,*z,mode,pc,inc,bits))
        # Full mode/PC/incoming matrix for numerical endpoint, cancellation,
        # intermediate range, and minsub-product witnesses.
        triples=[(raw(F(3,2)),raw(1),raw(-1)),(raw(scale(1,maximum)),raw(2),raw(-scale(1,maximum))),
                 (raw(scale(1,minimum)),raw(F(1,2)),raw(0)),(raw(1),raw(1),raw(-1)),
                 (raw(-1),raw(1),raw(1)),(raw(0,1),raw(1),raw(0,1))]
        minnormal=scale(1,-969 if fmt==106 else -1022 if fmt==64 else -16382)
        for sign in (1,-1):
            for tail_sign in (1,-1):triples.append((raw(tail_sign*scale(1,minimum)),raw(F(1,2)),raw(sign*minnormal)))
        largest=s.LIMIT if fmt==106 else scale(1,maximum+1)-scale(1,maximum-p+1)
        for sign in (1,-1):triples.append((raw(sign*largest),raw(2),raw(0)))
        if fmt==128:triples.append((raw(scale(1,minimum)),raw(scale(1,minimum)),raw(0)))
        if fmt==106:
            for v in (F(1),scale(1,-969),s.LIMIT):
                # Exact halfway population probes with opposite signs and
                # separately certified lower/upper endpoint parity.
                endpoint=pack(fmt,'finite',0,v)
                nk,ns,ni,nv=decode(fmt,s.neighbor(fmt,v,1))
                if nk=='finite':
                    for sign in (1,-1):
                        for offset in (0,1):triples.append((raw(sign*F(1,2)),raw(nv-v),raw(sign*(v+offset*(nv-v)))))
        for op in (2,3,4,5,6,7,8,9):
            if fmt==106 and op in (4,5,6,9):continue # Frozen historical reference population.
            for a,y,z in triples:
                for mode in range(4):
                    for pc in (0,2,3):
                        for inc in (0,1,2,4,8,16):rows.append((fmt,op,*a,*y,*z,mode,pc,inc,64))
        # Both-operand NaN inspection, invalid-product priority even with qNaN.
        qnan=pack(fmt,'nan',0,F(0));snan=(0x7fff,0x8000000000000001) if fmt==80 else (0x7fff000000000000,1) if fmt==128 else (0x7ff0000000000001,0)
        for op in (4,5,6,7,8,9):
            if fmt==106 and op in (4,5,6,9):continue # Frozen historical reference population.
            for a,y,z in [(qnan,snan,raw(0)),(snan,qnan,raw(0)),(pack(fmt,'inf',0,F(0)),raw(0),qnan)]:
                rows.append((fmt,op,*a,*y,*z,0,3,0,64))
    # Append an independent endpoint/tie matrix for all conversion operations.
    # Earlier rows retain their exact order and operands; every destination
    # width now crosses every mode, x87 precision and individual flag seed.
    for fmt in FORMATS:
        for op in range(4):
            for bits in ((32,64) if op in (0,2) else (64,)):
                limit=scale(1,bits-1)
                values=[F(0),F(1,2),F(3,2),F(5,2)]
                values.extend(limit+offset for offset in (F(-3,2),F(-1),F(-1,2),F(-1,4),F(0),F(1,4),F(1,2),F(1)))
                inputs=[]
                for value in values:
                    for sign in (1,-1):inputs.append(pack(fmt,'finite',int(sign<0),sign*value))
                for a in dict.fromkeys(inputs):
                    for mode in range(4):
                        for pc in (0,2,3):
                            for inc in (0,1,2,4,8,16):rows.append((fmt,op,*a,0,0,0,0,mode,pc,inc,bits))
    for fmt in FORMATS:
        zero=pack(fmt,'finite',0,F(0));one=pack(fmt,'finite',0,F(1))
        inf=pack(fmt,'inf',0,F(0));minus_inf=pack(fmt,'inf',1,F(0));qnan=pack(fmt,'nan',0,F(0))
        snan=(0x7fff,0x8000000000000001) if fmt==80 else (0x7fff000000000000,1) if fmt==128 else (0x7ff0000000000001,0)
        for a,y,z in [(one,one,snan),(qnan,one,snan),(one,qnan,snan),(inf,zero,qnan),(zero,inf,qnan),(inf,one,minus_inf),(qnan,inf,minus_inf)]:
            for mode in range(4):
                for pc in (0,2,3):
                    for inc in (0,1,2,4,8,16):rows.append((fmt,8,*a,*y,*z,mode,pc,inc,64))
    return list(dict.fromkeys(rows))

def encode(row):return ' '.join(f'{v&MASK:016x}' for v in row)+'\n'
def validate(row):
    assert len(row)==17
    fmt,op,*_=row
    assert fmt in FORMATS and op in range(10)
    assert row[8]<4 and row[9] in (0,2,3) and row[10]<=31 and row[11] in (32,64) and row[16]<=31
    assert op in (0,2) or row[11]==64
    assert tuple(row[12:])==expected(row[:12]),('literal wrong answer',row,expected(row[:12]))

def fnv(h,row):
    for v in row:
        for byte in v.to_bytes(8,'little'):h=((h^byte)*1099511628211)&MASK
    return h

def manifest(rows):
    out=[]
    for fmt in FORMATS:
        for width in (32,64):
            h=14695981039346656037;n=0
            for r in rows:
                if r[0]==fmt and (r[1] not in (0,2) or r[11]==width):h=fnv(h,r);n+=1
            out.append(encode((fmt,width,h,n)))
    return ''.join(out).encode()

def cell_key(row):
    # Only the three current-mode operations need distinct mode answers.
    return tuple(row[:8])+(row[8] if row[1] in (2,3,8) else 0,row[11])

def cells_payload(cells):
    return ''.join(' '.join(f'{v:x}' for v in (*key,*answer))+'\n' for key,answer in cells.items()).encode()

def bounded(path,maximum):
    assert not path.is_symlink() and path.is_file() and 0<path.stat().st_size<=maximum,('missing/nonregular/oversized reference',str(path))
    with path.open('rb') as stream:data=stream.read(maximum+1)
    assert len(data)<=maximum,'reference grew beyond bound'
    return data

def metadata(directory):
    meta=json.loads(bounded(directory/'long-double-nine.json',65536))
    assert set(meta)=={'schema','seed','count','rows','bytes','formats','literal_cells','literal_bytes','corpus_sha256','hash_sha256','literal_sha256'}
    assert meta['schema']==2 and meta['formats']==list(FORMATS) and 0<meta['bytes']<=64*1024*1024
    assert isinstance(meta['seed'],int) and 0<=meta['seed']<=MASK and isinstance(meta['count'],int) and 0<=meta['count']<=1024
    assert meta['bytes']==289*meta['rows']
    assert 0<meta['literal_cells']<=100000 and 0<meta['literal_bytes']<=16*1024*1024
    return meta

def prepare(directory):
    meta=metadata(directory)
    literal=bounded(directory/'long-double-nine.seeds',16*1024*1024)
    hashes=bounded(directory/'long-double-nine.hash',4096)
    assert len(literal)==meta['literal_bytes'] and hashlib.sha256(literal).hexdigest()==meta['literal_sha256'],'literal answer SHA256 differs'
    assert hashlib.sha256(hashes).hexdigest()==meta['hash_sha256'],'semantic hash file SHA256 differs'
    cache=directory/'long-double-nine.corpus'
    if cache.exists() or cache.is_symlink():
        data=bounded(cache,64*1024*1024)
        assert len(data)==meta['bytes'] and hashlib.sha256(data).hexdigest()==meta['corpus_sha256'],'existing cache SHA256 differs'
        return meta
    cells={}
    assert literal.endswith(b'\n'),'literal answer missing final LF'
    for line in literal.splitlines(keepends=True):
        assert re.fullmatch(rb'[0-9a-f]{1,16}( [0-9a-f]{1,16}){14}\n',line),'malformed literal answer framing'
        values=tuple(int(x,16) for x in line.split());key,answer=values[:10],values[10:]
        assert key not in cells and all(v<=MASK for v in values),'duplicate/out-of-range literal answer'
        cells[key]=answer
    assert len(cells)==meta['literal_cells']
    rows=[];seen=set()
    for row in fixtures(meta['seed'],meta['count']):
        key=cell_key(row);assert key in cells,'missing literal answer cell'
        answer=cells[key];rows.append((*row,*answer[:4],answer[4]|row[10]));seen.add(key)
    assert seen==set(cells),'unexpected literal answer cell'
    data=''.join(map(encode,rows)).encode()
    assert len(rows)==meta['rows'] and len(data)==meta['bytes'] and hashlib.sha256(data).hexdigest()==meta['corpus_sha256'],'reconstructed cache SHA256 differs'
    assert manifest(rows)==hashes,'reconstructed semantic hashes differ'
    # Link a fully pinned same-directory temporary into the missing pathname.
    # An appearing existing cache is checked, never replaced, even on races.
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=directory,prefix='.long-double-nine-cache-',delete=False) as stream:
            temporary=Path(stream.name)
            assert stream.write(data)==len(data),'cache temporary short write'
            stream.flush();os.fsync(stream.fileno())
        verified=bounded(temporary,64*1024*1024)
        assert len(verified)==meta['bytes'] and hashlib.sha256(verified).hexdigest()==meta['corpus_sha256'],'cache temporary SHA256 differs'
        temporary.chmod(0o644)
        try:os.link(temporary,cache)
        except FileExistsError:
            appearing=bounded(cache,64*1024*1024)
            assert len(appearing)==meta['bytes'] and hashlib.sha256(appearing).hexdigest()==meta['corpus_sha256'],'appearing cache SHA256 differs'
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    return meta

def generate(directory,seed=20261104,count=32):
    if not isinstance(seed,int) or isinstance(seed,bool) or not 0<=seed<=MASK:
        raise ValueError('seed must be an unsigned64 integer')
    if not isinstance(count,int) or isinstance(count,bool) or not 0<=count<=1024:
        raise ValueError('count must be between0 and1024')
    rows=[(*r,*expected(r)) for r in fixtures(seed,count)]
    cells={}
    for row in rows:
        key=cell_key(row)
        if key not in cells:
            normalized=(*key[:8],key[8],3,0,key[9]);cells[key]=expected(normalized)
    payload=''.join(map(encode,rows)).encode();hashes=manifest(rows);literal=cells_payload(cells)
    if len(payload)>64*1024*1024 or len(literal)>16*1024*1024 or len(cells)>100000:
        raise ValueError('generated reference exceeds bounded-reference limits')
    directory.mkdir(parents=True,exist_ok=True)
    (directory/'long-double-nine.corpus').write_bytes(payload)
    (directory/'long-double-nine.hash').write_bytes(hashes)
    (directory/'long-double-nine.seeds').write_bytes(literal)
    meta={'schema':2,'seed':seed,'count':count,'rows':len(rows),'bytes':len(payload),'formats':list(FORMATS),'literal_cells':len(cells),'literal_bytes':len(literal),'corpus_sha256':hashlib.sha256(payload).hexdigest(),'hash_sha256':hashlib.sha256(hashes).hexdigest(),'literal_sha256':hashlib.sha256(literal).hexdigest()}
    (directory/'long-double-nine.json').write_text(json.dumps(meta,indent=2)+'\n')
    return rows

def load(directory):
    meta=prepare(directory);payload=bounded(directory/'long-double-nine.corpus',64*1024*1024);hashes=(directory/'long-double-nine.hash').read_bytes()
    literal=bounded(directory/'long-double-nine.seeds',16*1024*1024);seen=set();literal_keys=[]
    assert literal.endswith(b'\n'),'literal answer missing final LF'
    for line in literal.splitlines(keepends=True):
        assert re.fullmatch(rb'[0-9a-f]{1,16}( [0-9a-f]{1,16}){14}\n',line),'malformed literal answer framing'
        fields=tuple(int(x,16) for x in line.split());key,answer=fields[:10],fields[10:]
        assert key not in seen,'duplicate literal answer cell'
        normalized=(*key[:8],key[8],3,0,key[9])
        assert cell_key(normalized)==key,'noncanonical literal answer mode'
        validate((*normalized,*answer));seen.add(key);literal_keys.append(key)
    assert len(seen)==meta['literal_cells']
    assert payload.endswith(b'\n')
    lines=payload.splitlines(keepends=True);assert len(lines)==meta['rows']
    rows=[]
    for line in lines:
        assert re.fullmatch(rb'[0-9a-f]{16}( [0-9a-f]{16}){16}\n',line),'malformed corpus bytes'
        r=tuple(int(x,16) for x in line.split());validate(r);rows.append(r)
    assert len(set(rows))==len(rows),'duplicate literal rows'
    assert [r[:12] for r in rows]==fixtures(meta['seed'],meta['count']),'input population drift'
    assert manifest(rows)==hashes,'semantic hash drift'
    assert literal_keys==list(dict.fromkeys(cell_key(r[:12]) for r in rows)),'literal answer population/order drift'
    return rows

def run(probe,rows):
    info=subprocess.run([str(probe)],input='',capture_output=True,text=True,timeout=10)
    assert info.returncode==2 and len(info.stdout.splitlines())==1,'invalid probe header/control response'
    header=info.stdout.split();assert header[::2]==['native','size','long'],header
    native,width=int(header[1]),int(header[5]);assert native in FORMATS and width in (32,64)
    selected=[r for r in rows if r[0]==native and (r[1] not in (0,2) or r[11]==width)]
    full=rows+[(0,*r[1:]) for r in selected]
    payload=''.join(encode(r[:12]) for r in full)
    process=subprocess.run([str(probe)],input=payload,capture_output=True,text=True,timeout=180)
    assert process.returncode==0,('probe failed',process.returncode,process.stderr)
    output=process.stdout.splitlines();assert output[0].split()==header,'probe identity changed'
    lines=output[1:];assert len(lines)==len(full)
    observed=[hashlib.sha256(process.stdout.splitlines()[0].encode()),hashlib.sha256(process.stdout.splitlines()[0].encode())]
    for i,(row,line) in enumerate(zip(full,lines)):
        fields=line.split();assert len(fields)==8
        got=tuple(int(x,16) for x in fields[:4])+(int(fields[4]),)
        entry=int(fields[7]);assert 0<=entry<=31 and entry&row[10]==row[10],'requested entry flags not present'
        if not row[10]:assert entry==0,'clear-entry fixture acquired flags before operation'
        want=(*row[12:16],row[16]|entry)
        assert got==want and fields[5:7]==['173','1'],('probe mismatch',i,row,line)
        observed[int(i>=len(rows))].update((encode(row[:12])+line+'\n').encode())
    print('long-double nine observed input/state/output SHA256: synthetic='+observed[0].hexdigest()+' native='+observed[1].hexdigest())
    print(f'long-double nine: {len(rows)} synthetic and {len(selected)} native{native}/long{width} ABI calls pass values, flags, errno and controls')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--directory',type=Path,default=Path('tests/corpus'));ap.add_argument('--generate',action='store_true');ap.add_argument('--seed',type=int,default=20261104);ap.add_argument('--count',type=int,default=32);ap.add_argument('--probe',type=Path);args=ap.parse_args()
    if args.generate:rows=generate(args.directory,args.seed,args.count)
    else:rows=load(args.directory)
    meta=metadata(args.directory)
    print(f'long-double nine: independently recomputed {len(rows)} expanded rows, {meta["literal_cells"]} literal answer cells and complete input/state/output hashes')
    if args.probe:run(args.probe,rows)
if __name__=='__main__':main()
