#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent Fraction answers for native scaling and variable DD spacing.

No host arithmetic supplies numerical answers. The reused foundation oracle
only decodes bytes and packs a single IEEE value using rational division.
"""
import argparse, hashlib, importlib.util, json, os, random, re, signal, subprocess
from fractions import Fraction as F
from pathlib import Path
spec=importlib.util.spec_from_file_location('foundation',Path(__file__).with_name('check-long-double.py'))
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
decode,pack,pack_single,scale,exponent=base.decode,base.pack,base.pack_single,base.scale,base.exponent
SIGN=1<<63
LIMIT=scale(1,1024)-scale(1,970)-scale(1,917)

def step64(u,d):
    if u&~SIGN==0:return (SIGN if d<0 else 0)|1
    if u&~SIGN==0x7ff0000000000000 and ((d<0)==bool(u&SIGN)):return u
    return u+(1 if (d<0)==bool(u&SIGN) else -1)

def dd_candidates(v):
    # In a normalized representation the leader is nearest binary64. Only
    # the containing cell and boundary cells can supply either bracket.
    h=pack_single(64,'finite',int(v<0),v)[0]
    if h&~SIGN==0x7ff0000000000000:h=(h&SIGN)|0x7fefffffffffffff
    out=set()
    for leader in (step64(h,-1),h,step64(h,1)):
        k,_,_,head=base.dec64(leader)
        if k!='finite':continue
        residual=v-head
        low=pack_single(64,'finite',int(residual<0),residual)[0]
        for tail in (step64(low,-1),low,step64(low,1)):
            k,_,_,r=base.dec64(tail)
            if k=='finite' and abs(head+r)<=LIMIT:out.add(head+r)
    return out

def rounded(fmt,v,sign):
    if fmt!=106:return pack(fmt,'finite',sign,v)
    if abs(v)>=LIMIT+scale(1,916):return pack(fmt,'inf',sign,F(0))
    candidates=dd_candidates(v)
    distance=min(abs(x-v) for x in candidates)
    tied=sorted(x for x in candidates if abs(x-v)==distance)
    result=tied[0]
    if len(tied)>1:
        unit=tied[-1]-tied[0]
        result=next(x for x in tied if (x/unit).denominator==1 and int(x/unit)%2==0)
    return pack(fmt,'finite',int(result<0) if result else sign,result)

def neighbor(fmt,v,d):
    if fmt==106:
        choices=[x for x in dd_candidates(v) if (x-v)*d>0]
        if not choices:return pack(fmt,'inf',int(d<0),F(0))
        r=min(choices) if d>0 else max(choices)
        return pack(fmt,'finite',int(r<0) if r else int(v<0),r)
    p,bias=(53,1023) if fmt==64 else (64,16383) if fmt==80 else (113,16383)
    if not v:r=scale(d,2-bias-p)
    else:
        e=exponent(v);unit=scale(1,max(e-p+1,2-bias-p))
        if (d<0)==(v>0) and abs(v)==scale(1,e):unit=scale(1,max(e-p,2-bias-p))
        r=v+d*unit
    return pack(fmt,'finite',int(r<0) if r else int(v<0),r)

def dd_no_interior(left,right):
    """Independent interval certificate, without candidate-search radius.

    RN64 is monotone. A normalized sum strictly inside this interval must
    have a leader between RN64(left) and RN64(right), inclusive. Walk that
    entire leader range. For each head, use directed residual quantization
    to find its first sum strictly above left. If it reaches right there is
    no sum from that head in the interval. Extra nonnormalized sums are
    included, which strengthens rather than weakens the rejection.
    """
    if left>right:left,right=right,left
    left=max(left,-LIMIT);right=min(right,LIMIT)
    if left>=right:return
    def head(v):
        u=pack_single(64,'finite',int(v<0),v)[0]
        if not u&~SIGN:u=0
        return ((u&SIGN)|0x7fefffffffffffff) if u&~SIGN==0x7ff0000000000000 else u
    h,last=head(left),head(right);cells=0
    while True:
        hv=base.dec64(h)[3];r=left-hv
        low=pack_single(64,'finite',int(r<0),r)[0]
        k,_,_,lv=base.dec64(low)
        if k=='finite':
            if lv<=r:low=step64(low,1);k,_,_,lv=base.dec64(low)
            if k=='finite':assert hv+lv>=right,('DD interior value',left,right,h,low,hv+lv)
        cells+=1
        if h==last:break
        h=step64(h,1)
        if not h&~SIGN:h=0
        assert cells<16,'DD certificate interval unexpectedly spans many leader cells'

def dd_midpoint_parity(exact,result):
    """Certify the closed, equally distant endpoint independently of search.

    A normalized leader and its exactly representable residual prove that the
    reflected endpoint belongs to DD. An empty open interval then leaves a
    two-point tie, whose integer coefficient in the actual gap must be even.
    """
    other=2*exact-result
    if other==result or abs(other)>LIMIT:return
    h=pack_single(64,'finite',int(other<0),other)[0]
    if h&~SIGN==0x7ff0000000000000:h=(h&SIGN)|0x7fefffffffffffff
    residual=other-base.dec64(h)[3]
    low=pack_single(64,'finite',int(residual<0),residual)[0]
    kind,_,_,tail=base.dec64(low)
    if kind=='finite' and tail==residual:
        gap=abs(other-result)
        assert gap.numerator.bit_count()==1 and gap.denominator.bit_count()==1,'nonbinary DD tie gap'
        coefficient=result/gap
        assert coefficient.denominator==1 and int(coefficient)%2==0,'DD midpoint selected odd endpoint'

def midpoint_controls():
    rejected=0
    for sign in (-1,1):
        for head in (F(0),F(1,2)):
            unit=scale(1,-1074)
            for odd,even in ((1,0),(1,2)):
                exact=sign*(head+(F(1,2) if even==0 else F(3,2))*unit)
                correct=sign*(head+even*unit);wrong=sign*(head+odd*unit)
                dd_midpoint_parity(exact,correct)
                try:dd_midpoint_parity(exact,wrong)
                except AssertionError as error:
                    assert 'odd endpoint' in str(error);rejected+=1
                else:raise AssertionError('independent DD midpoint certificate accepted odd endpoint')
    assert rejected==8
    print('long-double scale: eight independent DD normal/tiny signed lower/upper-even midpoint controls reject odd endpoints')

def certify(fmt,op,a,n,r):
    if fmt!=106:return
    ka,_,_,va=decode(106,a);kr,_,_,vr=decode(106,r)
    if ka==kr=='finite':
        if op>=3:dd_no_interior(va,vr)
        elif -40000<=n<=40000:
            exact=va*scale(1,n)
            if exact!=vr:
                dd_no_interior(vr,2*exact-vr)
                dd_midpoint_parity(exact,vr)

def expected(fmt,op,a,b,n,inc):
    k,s,bad,v=decode(fmt,a);flags=inc|int(bad)
    if op>=3:
        kb,sb,ib,vb=decode(fmt,b);flags|=int(ib)
        if k=='nan' or kb=='nan':return pack(fmt,'nan',0,F(0)),flags
        if k==kb=='inf' and s==sb:return pack(fmt,kb,sb,vb),flags
        if k==kb=='finite' and v==vb:return pack(fmt,kb,sb,vb),flags
        if k=='inf':
            maximum=LIMIT if fmt==106 else decode(fmt,((0x7fefffffffffffff,0) if fmt==64 else (32766,(1<<64)-1) if fmt==80 else (0x7ffeffffffffffff,(1<<64)-1)))[3]
            return pack(fmt,'finite',s,-maximum if s else maximum),flags
        d=(-1 if sb else 1) if kb=='inf' else (1 if vb>v else -1)
        r=neighbor(fmt,v,d)
        kr,sr,_,vr=decode(fmt,r)
        if kr=='inf':flags|=20
        elif abs(vr)<scale(1,-969 if fmt==106 else -1022 if fmt==64 else -16382):flags|=12
        return r,flags
    if k!='finite' or not v:return pack(fmt,k,s,v),flags
    # Saturation only controls rational allocation; every native exponent
    # outside this range has the same proved terminal result.
    if n>40000:return pack(fmt,'inf',s,F(0)),flags|20
    if n< -40000:return pack(fmt,'finite',s,F(0)),flags|12
    exact=v*scale(1,n);r=rounded(fmt,exact,s)
    kr,sr,_,vr=decode(fmt,r)
    if kr=='inf':flags|=20
    elif vr!=exact:flags|=12 if abs(vr)<scale(1,-969 if fmt==106 else -1022 if fmt==64 else -16382) else 4
    return r,flags

def fixtures(count=96):
    rng=random.Random(20261114);rows=[]
    for fmt in (64,80,128,106):
        minimum=-1074 if fmt in (64,106) else -16445 if fmt==80 else -16494
        emin=-969 if fmt==106 else -1022 if fmt==64 else -16382
        p=53 if fmt==64 else 64 if fmt==80 else 113 if fmt==128 else 106
        values=[pack(fmt,k,s,F(0)) for k in ('finite','inf','nan') for s in (0,1)]
        nums=[F(1),F(3,2),F(1)+scale(1,-60),scale(1,minimum),scale(3,minimum),scale(1,emin),scale(1,emin)-scale(1,minimum),scale(1,emin)+scale(1,minimum),scale(1,1023),scale(1,-1000)]
        if fmt==106:nums += [LIMIT,LIMIT/2,(LIMIT-scale(1,917))/2,F(1)+scale(1,-1074),F(1)-scale(1,-1074),F(1)+scale(1,-53),F(1)+scale(1,-53)+scale(1,-106)]
        for v in nums:
            for s in (0,1):values.append(pack(fmt,'finite',s,-v if s else v))
        if fmt==80:values.extend([(0,1<<63),(0x3fff,1),(0x7fff,(1<<63)|1),(32766,(1<<64)-1)])
        if fmt==128:values.extend([(0x7fff000000000000,1),(0x7ffeffffffffffff,(1<<64)-1)])
        if fmt in (64,106):values.append((0x7ff0000000000001,0))
        if fmt==106:values.extend([(0x3ff0000000000000,1),(0x3ff0000000000000,SIGN|1),(0x3ff0000000000000,0xbff0000000000000),(1,2),(0x7fefffffffffffff,0x7c90000000000000),(0x3ff0000000000000,0x7ff0000000000001)])
        for _ in range(count):
            if fmt==106:
                hi=(rng.randrange(2047)<<52)|rng.getrandbits(52)|(rng.getrandbits(1)<<63)
                # arbitrary overlapping, cancelling, or separated tails
                lo=(rng.randrange(2047)<<52)|rng.getrandbits(52)|(rng.getrandbits(1)<<63)
                values.append((hi,lo))
            else:
                v=scale(rng.getrandbits(p),rng.randrange(minimum-p,1024 if fmt==64 else 16384)-p)
                values.append(pack(fmt,'finite',rng.randrange(2),v))
        for i,a in enumerate(values):
            ns=[0,1,-1,2,-2,minimum,emin,-emin,2147483647,-2147483648]
            ns.append(rng.randrange(-2200,2200) if fmt in (64,106) else rng.randrange(-33000,33000))
            for op in range(3):
                for n in ns:rows.append((fmt,op,a,(0,0),i%4,(0,2,3)[i%3],(0,4,31)[i%3],n))
            for op in (3,4):
                for b in (a,values[0],values[1],values[2],values[(i+7)%len(values)]):rows.append((fmt,op,a,b,i%4,(0,2,3)[i%3],(0,4,31)[i%3],0))
        # Long extrema are selected separately per actual probe width.
    return rows

def tininess_witnesses():
    """Raw half-ulp seams immediately below minimum normal, both signs.

    (2*N-q)/2 rounds up to N with IX only. The neighboring tiny ties
    (2*N-3*q)/2 and (2*N-5*q)/2 both round to N-2*q with UF/IX.
    """
    rows=[]
    for fmt in (64,80,128,106):
        emin=-969 if fmt==106 else -1022 if fmt==64 else -16382
        minimum=-1074 if fmt in (64,106) else -16445 if fmt==80 else -16494
        for sign in (0,1):
            for k in (1,3,5):
                if fmt==64:a=((sign<<63)|0x001fffffffffffff-(k-1),0)
                elif fmt==80:a=(1|(sign<<15),(1<<64)-k)
                elif fmt==128:a=((sign<<63)|0x0001ffffffffffff,(1<<64)-k)
                else:a=((sign<<63)|(55<<52),((1-sign)<<63)|k)
                exact=(-1 if sign else 1)*(scale(2,emin)-scale(k,minimum))
                assert decode(fmt,a)[3]==exact,'tininess witness input was rounded'
                value=scale(1,emin)-(scale(2,minimum) if k!=1 else 0)
                result=pack(fmt,'finite',sign,-value if sign else value);added=4 if k==1 else 12
                for mode in range(4):
                    for pc in (0,2,3):
                        for incoming in (0,2):
                            assert expected(fmt,1,a,(0,0),-1,incoming)==(result,incoming|added),'tininess oracle edge contract'
                            rows.append((fmt,1,a,(0,0),mode,pc,incoming,-1))
    return rows

def boundary_witnesses():
    """Identical boundaries cross every mode/PC, clear and separately seeded.

    FE_DIVBYZERO alone is preseeded: it cannot mask any required IX/UF/OF/INV.
    The original committed rows and their ordering are unchanged.
    """
    rows=[]
    for fmt in (64,80,128,106):
        minimum=-1074 if fmt in (64,106) else -16445 if fmt==80 else -16494
        emin=-969 if fmt==106 else -1022 if fmt==64 else -16382
        maximum=LIMIT if fmt==106 else decode(fmt,(0x7fefffffffffffff,0) if fmt==64 else (32766,(1<<64)-1) if fmt==80 else (0x7ffeffffffffffff,(1<<64)-1))[3]
        for sign in (0,1):
            def raw(value):return pack(fmt,'finite',sign,-value if sign else value)
            infinity=pack(fmt,'inf',sign,F(0));zero=raw(F(0))
            cases=[(1,raw(scale(1,minimum)),zero,-1),
                   (1,raw(scale(3,minimum)),zero,-1),
                   (1,raw(scale(1,minimum)),zero,0),
                   (1,raw(scale(1,emin)),zero,0),
                   (3,raw(scale(1,minimum)),zero,0),
                   (3,raw(scale(1,emin)-scale(1,minimum)),infinity,0),
                   (1,raw(maximum),zero,1),
                   (3,(0x7fff,(1<<63)|1) if fmt==80 else (0x7fff000000000000,1) if fmt==128 else (0x7ff0000000000001,0),zero,0)]
            if fmt==106:
                # Lower-even and upper-even ties, both signs, normal IX-only
                # and tiny UF/IX. These exact separated tails survive input.
                cases += [(1,(0x3ff0000000000000|(sign<<63),tail|(sign<<63)),zero,-1) for tail in (1,3)]
                cases += [(1,(tail|(sign<<63),0),zero,-1) for tail in (1,3)]
            for op,a,b,n in cases:
                for mode in range(4):
                    for pc in (0,2,3):
                        for incoming in (0,2):rows.append((fmt,op,a,b,mode,pc,incoming,n))
    return rows+tininess_witnesses()

def bounded_probe(probe,payload,timeout):
    process=subprocess.Popen([str(Path(probe).resolve())],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        output,error=process.communicate(payload,timeout=timeout)
        return process.returncode,output,error
    except subprocess.TimeoutExpired:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.communicate(timeout=5)  # kill and reap the whole pipe-owning group
        raise AssertionError('probe deadline exceeded') from None
    finally:
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL);process.communicate(timeout=5)

COMMITTED_COUNTS={64:5289,80:5418,128:5332,106:6149}
def row_values(row,result,flags):
    f,o,a,b,m,pc,inc,n=row
    return (f,o,*a,*b,m,pc,inc,n,*result,flags)
def fnv_row(h,values):
    for value in values:
        for byte in (value&((1<<64)-1)).to_bytes(8,'little'):h=((h^byte)*1099511628211)&((1<<64)-1)
    return h

def committed_rows(path):
    data=Path(path).read_bytes();assert data and b'\0' not in data,'invalid committed corpus bytes'
    for number,line in enumerate(data.splitlines(),1):
        assert len(line)<512,'overlong committed row'
        words=line.decode('ascii').split();assert len(words)==13,'committed row field count'
        fields=[]
        for i,word in enumerate(words):
            pattern=r'[0-9a-fA-F]+' if i in (2,3,4,5,10,11) else r'-?[0-9]+' if i==9 else r'[0-9]+'
            assert re.fullmatch(pattern,word),'invalid committed token'
            fields.append(int(word,16 if i in (2,3,4,5,10,11) else 10))
        f,o,ah,al,bh,bl,m,pc,inc,n,rh,rl,flags=fields
        assert f in COMMITTED_COUNTS and 0<=o<=4 and 0<=m<=3 and pc in (0,2,3) and 0<=inc<=31 and 0<=flags<=31
        assert -(1<<31)<=n<(1<<31) and all(0<=v<(1<<64) for v in (ah,al,bh,bl,rh,rl))
        yield number,(f,o,(ah,al),(bh,bl),m,pc,inc,n),(rh,rl),flags

def corpus_integrity(path):
    hashes={f:14695981039346656037 for f in COMMITTED_COUNTS};counts=dict.fromkeys(hashes,0)
    for number,row,result,flags in committed_rows(path):
        f,o,a,b,m,pc,inc,n=row
        want,wflags=expected(f,o,a,b,n,inc)
        assert (result,flags)==(want,wflags),f'committed row {number} disagrees with rational oracle'
        certify(f,o,a,n,result)
        hashes[f]=fnv_row(hashes[f],row_values(row,result,flags));counts[f]+=1
    assert counts==COMMITTED_COUNTS,'committed population mismatch'
    return hashes,counts

def validate_corpus(path):
    path=Path(path);doc=json.loads(path.read_text())
    # Numerical recomputation is independent of fixture generation and pins.
    hashes,counts=corpus_integrity(path.with_suffix('.corpus'))
    assert doc['seed']==20261114 and {int(k):v for k,v in doc['counts'].items()}==counts
    records=path.with_suffix('.hash').read_bytes().splitlines();seen={}
    for line in records:
        assert re.fullmatch(rb'format (64|80|128|106) [0-9a-f]{16} [0-9]+',line),'invalid committed hash record'
        _,fmt,digest,population=line.split();fmt=int(fmt);assert fmt not in seen
        seen[fmt]=(int(digest,16),int(population))
    assert seen=={f:(hashes[f],counts[f]) for f in counts},'committed semantic hash mismatch'
    for filename,digest in doc['files'].items():assert hashlib.sha256(path.with_name(filename).read_bytes()).hexdigest()==digest,'frozen payload differs: '+filename
    print(f'long-double scale: recomputed every committed answer/flag and semantic input hash ({sum(counts.values())} rows)')

def payload(row):
    f,o,a,b,m,pc,inc,n=row
    return f'{f} {o} {a[0]:x} {a[1]:x} {b[0]:x} {b[1]:x} {m} {pc} {inc} {n}\n'
def check(probe,corpus=None,count=96,timeout=120,tininess_only=False):
    rows=tininess_witnesses() if tininess_only else fixtures(count)+boundary_witnesses()
    # Acquiring the header is itself deadline-bounded. An empty input is the
    # probe's documented no-row error and returns its ABI header without work.
    code,output,error=bounded_probe(probe,'',timeout)
    header=output.splitlines()[0].split();assert header[0]=='native';native=int(header[1]);longbits=int(header[-1]);assert longbits in (32,64)
    assert code==2,'probe header acquisition did not reject empty input'
    if not tininess_only:
        for fmt in (64,80,128,106):
            for n in (-(1<<(longbits-1)),(1<<(longbits-1))-1):rows.append((fmt,2,pack(fmt,'finite',0,F(1)),(0,0),0,3,0,n))
    native_rows=[(0,*r[1:]) for r in rows if r[0]==native];allrows=rows+native_rows
    code,output,error=bounded_probe(probe,''.join(map(payload,allrows)),timeout)
    assert code==0,f'probe exit {code}: {error}'
    lines=output.splitlines();assert lines[0].split()==header
    lines=lines[1:];assert len(lines)==len(allrows)
    for i,(row,line) in enumerate(zip(allrows,lines)):
        f,o,a,b,m,pc,inc,n=row;r,flags=expected(f or native,o,a,b,n,inc)
        fields=line.split();actual=(int(fields[0],16),int(fields[1],16));gf,err,state=map(int,fields[5:])
        assert actual==r and gf==flags and err==173 and state==1,f'row {i} {row}: actual {line}; expected {r} flags={flags}'
        certify(f or native,o,a,n,r)
    if tininess_only:
        for fmt in (64,80,128,106):
            selected=[(row,line) for row,line in zip(allrows,lines) if row[0]==fmt]
            normal=sum((int(line.split()[5]) & ~row[6])==4 for row,line in selected)
            tiny=sum((int(line.split()[5]) & ~row[6])==12 for row,line in selected)
            assert (normal,tiny)==(48,96)
            print(f'tininess format{fmt} synthetic: rounded minnormal IX-only {normal}; neighboring tiny UF/IX {tiny}')
        actual=[(row,line) for row,line in zip(allrows,lines) if row[0]==0]
        normal=sum((int(line.split()[5]) & ~row[6])==4 for row,line in actual)
        tiny=sum((int(line.split()[5]) & ~row[6])==12 for row,line in actual)
        assert (normal,tiny)==(48,96)
        print(f'tininess format{native} native long{longbits}: rounded minnormal IX-only {normal}; neighboring tiny UF/IX {tiny}; both signs/all modes/PCs/clear and preseeded flags')
        return
    if corpus:validate_corpus(corpus)
    int_calls=sum(r[1]<2 for r in native_rows);long_calls=sum(r[1]==2 for r in native_rows)
    print(f'long-double scale: native long{longbits} eligible int-exponent calls {int_calls}; long-exponent calls {long_calls} (including actual LONG_MIN/MAX)')
    print(f'long-double scale: {len(boundary_witnesses())} boundary rows independently cross modes/PCs and clear/preseeded flags')
    print(f'long-double scale: {len(rows)} synthetic rational rows (four formats); {len(native_rows)} native ABI rows (format {native}, long{longbits}); values, flags, errno and controls agree')

def write_answers(path):
    path=Path(path);lines=[];hashes={f:14695981039346656037 for f in (64,80,128,106)};counts=dict.fromkeys(hashes,0)
    for row in fixtures():
        f,o,a,b,m,pc,inc,n=row;r,flags=expected(f,o,a,b,n,inc)
        lines.append(payload(row).rstrip()+f' {r[0]:016x} {r[1]:016x} {flags}\n')
        hashes[f]=fnv_row(hashes[f],row_values(row,r,flags))
        counts[f]+=1
    path.write_text(''.join(lines));hp=path.with_suffix('.hash');hp.write_text(''.join(f'format {f} {hashes[f]:016x} {counts[f]}\n' for f in hashes))
    path.with_suffix('.json').write_text(json.dumps({'seed':20261114,'counts':counts,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (path,hp)}},indent=2)+'\n')
def refresh_integrity(path):
    path=Path(path);hashes,counts=corpus_integrity(path)
    hp=path.with_suffix('.hash');hp.write_text(''.join(f'format {f} {hashes[f]:016x} {counts[f]}\n' for f in hashes))
    path.with_suffix('.json').write_text(json.dumps({'seed':20261114,'counts':counts,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (path,hp)}},indent=2)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--probe');ap.add_argument('--corpus');ap.add_argument('--write-answers');ap.add_argument('--count',type=int,default=96);ap.add_argument('--timeout',type=float,default=120);ap.add_argument('--validate-corpus');ap.add_argument('--refresh-integrity');ap.add_argument('--self-test-parity',action='store_true');ap.add_argument('--tininess-only',action='store_true');args=ap.parse_args()
    if args.self_test_parity:midpoint_controls()
    if args.probe:check(args.probe,args.corpus,args.count,args.timeout,args.tininess_only)
    if args.refresh_integrity:refresh_integrity(args.refresh_integrity)
    if args.validate_corpus:validate_corpus(args.validate_corpus)
    if args.write_answers:write_answers(args.write_answers)
