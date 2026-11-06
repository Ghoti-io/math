#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent exact Fraction oracle; native ABI and synthetic runs stay distinct."""
import argparse, hashlib, json, random, subprocess
from fractions import Fraction as F
from pathlib import Path
SIGN=1<<63

def scale(n,e): return F(n<<e) if e>=0 else F(n,1<<-e)
def dec64(u):
    sign=u>>63; e=(u>>52)&2047; m=u&((1<<52)-1)
    if e==2047:return ('nan' if m else 'inf',sign, bool(m and not m&(1<<51)),F(0))
    return ('finite',sign,False,(-1 if sign else 1)*scale(m|((1<<52) if e else 0),(e or 1)-1075))
def decode(fmt,r):
    h,l=r
    if fmt==64:return dec64(h)
    if fmt==106:
        a,b=dec64(h),dec64(l); bad=b[0]!='finite' or (a[0]=='inf' and (l&~SIGN)!=0)
        if bad or a[0]=='nan' or b[0]=='nan':return ('nan',a[1],bad or a[2] or b[2],F(0))
        if a[0]=='inf':return a
        v=a[3]+b[3]
        if abs(v)>scale(1,1024)-scale(1,970)-scale(1,917):return ('nan',a[1],True,F(0))
        return ('finite',int(v<0) if v else (a[1] if not (h&~SIGN or l&~SIGN) else 0),False,v)
    if fmt==80:
        s=h>>15; e=h&32767;m=l
        if e and not m>>63:return ('nan',s,True,F(0))
        if e==32767:return ('inf' if m==1<<63 else 'nan',s,m!=1<<63 and not m&(1<<62),F(0))
        return ('finite',s,False,(-1 if s else 1)*scale(m,(e or 1)-16446))
    s=h>>63;e=(h>>48)&32767;m=((h&((1<<48)-1))<<64)|l
    if e==32767:return ('nan' if m else 'inf',s,bool(m and not m&(1<<111)),F(0))
    return ('finite',s,False,(-1 if s else 1)*scale(m|((1<<112) if e else 0),(e or 1)-16495))
def exponent(v):
    v=abs(v);e=v.numerator.bit_length()-v.denominator.bit_length()
    return e if v>=scale(1,e) else e-1
def nearest(v):
    q,r=divmod(v.numerator,v.denominator)
    return q+int(2*r>v.denominator or (2*r==v.denominator and q&1))
def pack_single(fmt,k,s,v):
    p,bias=(53,1023) if fmt==64 else (64,16383) if fmt==80 else (113,16383)
    exp=0;sig=0
    if k!='finite':exp=2*bias+1;sig=1<<(p-2) if k=='nan' else 0;s=0 if k=='nan' else s
    elif v:
        e=exponent(v);cut=max(e-p+1,2-bias-p);sig=nearest(abs(v)/scale(1,cut))
        if sig>=1<<p:sig>>=1;e+=1
        if e>bias:exp=2*bias+1;sig=0
        elif sig>=1<<(p-1):exp=max(1,e+bias)
    if fmt==80:return (exp|(s<<15),sig|((1<<63) if exp==32767 else 0))
    bits=((s<<(p+(11 if fmt==64 else 15)-1))|(exp<<(p-1))|(sig&((1<<(p-1))-1)))
    return (bits,0) if fmt==64 else (bits>>64,bits&((1<<64)-1))
def pack(fmt,k,s,v):
    if fmt!=106:return pack_single(fmt,k,s,v)
    h=pack_single(64,k,s,v)[0]
    if k!='finite' or not v:return h,0
    if (h&~SIGN)==0x7ff0000000000000:h=(s<<63)|0x7fefffffffffffff
    rem=v-dec64(h)[3];l=pack_single(64,'finite',int(rem<0),rem)[0]
    return h,l if l&~SIGN else 0

def expected(fmt,op,a,b,mode,incoming):
    k,s,invalid,v=decode(fmt,a); flags=incoming; whole=(0,0);e=0
    if op==2:return pack(fmt,'nan',0,F(0)),whole,e,flags
    if op in (3,4):
        kb,sb,ib,vb=decode(fmt,b)
        if invalid or ib:k='nan';flags|=1
        elif k=='nan' and kb!='nan':k,s,v=kb,sb,vb
        elif k!='nan' and kb!='nan':
            ka=(-1 if s else 1)*float('inf') if k=='inf' else v
            ky=(-1 if sb else 1)*float('inf') if kb=='inf' else vb
            choose=(ka<ky if op==4 else ka>ky) or (ka==ky==0 and (s<sb if op==3 else s>sb))
            if choose:k,s,v=kb,sb,vb
        return pack(fmt,k,s,v),whole,e,flags
    flags|=int(invalid)
    if op==13:
        e=2147483647 if k in ('inf','nan') else -2147483648 if not v else exponent(v)
        flags|=int(k!='finite' or not v)
        # Native integer interface has no meaningful floating result.
        return pack(fmt,k,s,v),whole,e,flags
    if k=='nan':
        r=pack(fmt,k,s,v);return r,r if op==11 else whole,e,flags
    if op==0:s=0;v=abs(v)
    elif op==1:s=(b[0]>>15)&1 if fmt==80 else b[0]>>63;v=-abs(v) if s else abs(v)
    elif op==14:
        if k=='inf':s=0
        elif not v:k='inf';s=1;flags|=2
        else:v=F(exponent(v));s=int(v<0)
    elif op==12:
        if k=='finite' and v:
            e=exponent(v)+1;v/=scale(1,e)
            if fmt==106:
                import importlib.util
                spec=importlib.util.spec_from_file_location('frexp_scale_oracle',Path(__file__).with_name('check-long-double-scale.py'))
                oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
                result=oracle.rounded(106,v,s);rv=decode(106,result)[3]
                if rv!=v:flags|=4
                if abs(rv)==1:e+=1;result=pack(106,'finite',s,rv/2)
                return result,whole,e,flags
    elif op==11:
        if k=='inf':whole=pack(fmt,k,s,v);k='finite';v=F(0)
        else:
            n=abs(v.numerator)//v.denominator;n=-n if s else n
            whole=pack(fmt,k,s,F(n));v-=n
    elif 5<=op<=10 and k=='finite':
        av=abs(v);q,r=divmod(av.numerator,av.denominator)
        inc=bool(r) and (s if op==5 else not s if op==6 else False)
        if op==8:inc=2*r>=av.denominator
        if op==9 or (op==10 and mode==0):inc=2*r>av.denominator or (2*r==av.denominator and q&1)
        if op==10 and mode:inc=bool(r) and (s if mode==1 else not s if mode==2 else False)
        v=F((-1 if s else 1)*(q+int(inc)))
    return pack(fmt,k,s,v),whole,e,flags

def fixtures():
    rows=[];rng=random.Random(20261104)
    for fmt in (64,80,128,106):
        values=[pack(fmt,'finite',s,F(0)) for s in (0,1)]
        for s in (0,1):
            for v in [F(1,2),F(3,2),F(5,2),F(7,2),F(1,4),F(15,8),F(1),F(2),scale(1,55)+F(1,2),F(1)+scale(1,-60),F(1,2)+scale(1,-64),F(1,2)-scale(1,-64),scale(1,-1074),scale(1,1023)]:
                values.append(pack(fmt,'finite',s,-v if s else v))
            values.extend([pack(fmt,'inf',s,F(0)),pack(fmt,'nan',0,F(0))])
        if fmt==80:values.extend([(0,(1<<63)-1),(0x8000,(1<<63)-1),(0,1),(1,1<<63),(0,1<<63),(0x3fff,1),(0x7fff,(1<<63)|1),(0x7ffe,(1<<64)-1)])
        if fmt==128:values.extend([(0x0000ffffffffffff,(1<<64)-1),(0x8000ffffffffffff,(1<<64)-1),(0,1),(0x0001000000000000,0),(0x7ffeFFFFFFFFFFFF,(1<<64)-1),(0x7fff000000000000,1),(0x3fff000000000000,1)])
        if fmt in (64,106):values.extend([(1,0),(0x0010000000000000,0),(0x7fefffffffffffff,0),(0x7ff0000000000001,0)])
        if fmt==106:values.extend([(0x3ff0000000000000,1),(0x3ff0000000000000,0xbff0000000000000),(0x3ff0000000000000,0xbfefffffffffffff),(1,2),(0x3ff0000000000000,0x8000000000000001),(0x3ff0000000000000,0x7ff0000000000000),(0x3ff0000000000000,0x7ff8000000000000),(0x3ff0000000000000,0x7ff0000000000001)])
        if fmt==106:
            for sign in (0,SIGN):
                values.extend([(0x7fefffffffffffff|sign,lo|sign) for lo in (0x7c8ffffffffffffe,0x7c8fffffffffffff,0x7c90000000000000,0x7fefffffffffffff)])
        for _ in range(18):
            v=scale(rng.randrange(1,1<<112),rng.randrange(-1150,900));values.append(pack(fmt,'finite',0,v))
        for _ in range(36):
            if fmt in (64,106):
                h=(rng.randrange(2047)<<52)|rng.getrandbits(52)|(rng.getrandbits(1)<<63)
                l=((rng.randrange(2047)<<52)|rng.getrandbits(52)|(rng.getrandbits(1)<<63)) if fmt==106 else 0
            elif fmt==80:
                h=rng.randrange(32767)|(rng.getrandbits(1)<<15);l=rng.getrandbits(63)|((1<<63) if h&32767 else 0)
            else:
                h=(rng.randrange(32767)<<48)|rng.getrandbits(48)|(rng.getrandbits(1)<<63);l=rng.getrandbits(64)
            values.append((h,l))
        for idx,a in enumerate(values):
            for op in range(15):
                if fmt==106 and op==12:continue # Frozen historical population; DD supplemental gate covers frexp.
                bs=[values[(idx+7)%len(values)]] if op not in (1,3,4) else [values[0],values[1],values[(idx+7)%len(values)],pack(fmt,'nan',0,F(0))]
                for b in bs:
                    for mode in range(4) if op==10 else [0]:rows.append((fmt,op,a,b,mode,(0,2,3)[idx%3],(0,4,31)[idx%3]))
    return rows

def check(probe,corpus=None):
    witness=(F(1)+scale(1,-1074))/2
    assert (witness/scale(1,-1074)).denominator==2, 'DD frexp unavailability witness changed'
    rows=fixtures();p=subprocess.Popen([str(probe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    header=p.stdout.readline().split();native=int(header[1]);assert header[0]=='native'
    # communicate avoids pipe backpressure on the bounded bulk fixture population.
    native_rows=[(0,*r[1:]) for r in rows if r[0]==native]
    allrows=rows+native_rows
    payload=''.join(f'{f} {o} {a[0]:x} {a[1]:x} {b[0]:x} {b[1]:x} {m} {pc} {inc}\n' for f,o,a,b,m,pc,inc in allrows)
    output,_=p.communicate(payload);assert p.returncode==0, f'probe exit {p.returncode}'
    lines=output.splitlines();assert len(lines)==len(allrows),(len(lines),len(allrows))
    hashes={str(f):hashlib.sha256() for f in (64,80,128,106)}
    for i,(row,line) in enumerate(zip(allrows,lines)):
        f,op,a,b,m,pc,inc=row;fmt=f or native;r,w,e,flags=expected(fmt,op,a,b,m,inc)
        fields=line.split();got=(int(fields[0],16),int(fields[1],16));gw=(int(fields[2],16),int(fields[3],16));ge,gf,err,state=map(int,fields[4:])
        assert (op==13 or got==r) and (op!=11 or gw==w) and ge==e and gf==flags and err==173 and state==1, f'row {i} {row}: actual {line}; expected {r} {w} {e} flags={flags}'
        if f:hashes[str(f)].update((json.dumps([row,[r,w,e,flags]],separators=(',',':'))+'\n').encode())
    digest={k:v.hexdigest() for k,v in hashes.items()}
    if corpus:
        data=json.loads(Path(corpus).read_text());assert digest==data['sha256'],(digest,data)
        for name,sha in data.get('files',{}).items():assert hashlib.sha256(Path(corpus).with_name(name).read_bytes()).hexdigest()==sha,'frozen answer/hash payload differs: '+name
    print('long-double: historical 14-operation DD reference population retained; rounded frexp is checked separately')
    print(f'long-double: {len(rows)} synthetic exact-rational rows across four formats; {len(native_rows)} native ABI rows (format {native}); state/flags/errno passed')
    return digest
def write_corpus(path):
    lines=[];hashes={f:14695981039346656037 for f in (64,80,128,106)};counts={f:0 for f in hashes}
    for row in fixtures():
        f,o,a,b,m,pc,inc=row;r,w,e,flags=expected(f,o,a,b,m,inc)
        lines.append(f'{f} {o} {a[0]:016x} {a[1]:016x} {b[0]:016x} {b[1]:016x} {m} {pc} {inc} {r[0]:016x} {r[1]:016x} {w[0]:016x} {w[1]:016x} {e} {flags}\n')
        result=(0,0) if o==13 else r
        for value in (*result,*w,e,flags):
            for byte in (value&((1<<64)-1)).to_bytes(8,'little'):
                hashes[f]=((hashes[f]^byte)*1099511628211)&((1<<64)-1)
        counts[f]+=1
    Path(path).write_text(''.join(lines))
    Path(path).with_suffix('.hash').write_text(''.join(f'format {f} {hashes[f]:016x} {counts[f]}\n' for f in hashes))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--probe',required=True,type=Path);ap.add_argument('--corpus');ap.add_argument('--write-corpus');ap.add_argument('--write-answers');args=ap.parse_args()
    digests=check(args.probe,args.corpus)
    if args.write_corpus:Path(args.write_corpus).write_text(json.dumps({'seed':20261104,'availability':{'64':15,'80':15,'128':15,'106':14},'deferred':['IBM DD frexpl'],'sha256':digests},indent=2)+'\n')

    if args.write_answers:
        write_corpus(args.write_answers)
        doc=json.loads(Path(args.write_corpus).read_text())
        paths=[Path(args.write_answers),Path(args.write_answers).with_suffix('.hash')]
        doc['files']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        Path(args.write_corpus).write_text(json.dumps(doc,indent=2)+'\n')
