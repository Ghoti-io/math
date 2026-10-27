#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact integer-return rounding: Fraction plus independent pinned MPFR.

Full raw corpora carry both signed32 and signed64 results/invalid classes.
Common valid signed32 subsets store exactly widened double integer results
for architecture-independent hashing of all four public APIs.
"""
import argparse
from fractions import Fraction
from pathlib import Path
import random
import struct
import tempfile
import gmpy2


def value(raw, width):
    mantissa, bias, exponent_bits = (52,1023,11) if width==64 else (23,127,8)
    exponent=(raw>>mantissa)&((1<<exponent_bits)-1)
    fraction=raw&((1<<mantissa)-1)
    if exponent==(1<<exponent_bits)-1:return None
    integer=fraction if exponent==0 else fraction+(1<<mantissa)
    shift=(1-bias if exponent==0 else exponent-bias)-mantissa
    q=Fraction(integer*(1<<shift)) if shift>=0 else Fraction(integer,1<<-shift)
    return -q if raw>>(width-1) else q


def answer(raw,width):
    q=value(raw,width)
    if q is None:return (-(1<<31),1,-(1<<63),1)
    magnitude,remainder=divmod(abs(q.numerator),q.denominator)
    rounded=magnitude+(2*remainder>=q.denominator)
    if q<0:rounded=-rounded
    with gmpy2.context(precision=1200):
        independent=int(gmpy2.rint_round(gmpy2.mpfr(q.numerator)/q.denominator))
    if rounded!=independent:raise RuntimeError('Fraction/MPFR integer disagreement')
    results=[]
    for bits in (32,64):
        invalid=not -(1<<(bits-1))<=rounded<(1<<(bits-1))
        results.extend((-(1<<(bits-1)) if invalid else rounded,int(invalid)))
    return tuple(results)


def population(seed,count,width):
    rng=random.Random(seed+width);rows=set()
    mantissa,exponents=(52,2047) if width==64 else (23,255)
    sign=1<<(width-1);inf=exponents<<mantissa
    def add(raw):
        if 0<=raw<1<<width:rows.add(raw)
    for exponent in range(exponents+1):
        for tail in (0,1,(1<<mantissa)-1,rng.getrandbits(mantissa)):
            add((exponent<<mantissa)|tail);add(sign|(exponent<<mantissa)|tail)
    for bit in range(mantissa):
        for delta in (-1,0,1):add((1<<bit)+delta);add(sign|((1<<bit)+delta))
    pack='>d' if width==64 else '>f';word='>Q' if width==64 else '>I'
    centers=[0.5,1.0]+[k+0.5 for k in range(1,257)]
    centers += [float(2**31)+delta for delta in (-1,-0.5,0,0.5,1)]
    centers += [float(2**63),float(2**64)]
    for x in centers:
        raw=struct.unpack(word,struct.pack(pack,x))[0]
        for delta in (-2,-1,0,1,2):add(raw+delta);add(sign|(raw+delta))
    for raw in (inf,inf|1,inf|(1<<(mantissa-1)),inf|(1<<mantissa)-1):add(raw);add(raw|sign)
    for _ in range(count):add(rng.getrandbits(width))
    return sorted(rows)


def publish(path,text):
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix='.'+path.name+'.',delete=False) as out:
            temporary=Path(out.name);out.write(text)
        temporary.chmod(path.stat().st_mode&0o777 if path.exists() else 0o644)
        temporary.replace(path)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def header(family,seed,count,fresh,size):
    return '# Pinned oracle: tools/oracle/gen_corpus_intround.py; MPFR %s gmpy2 %s\n# function %s\n# seed %d count %d fresh %s entries %d\n'%(gmpy2.mpfr_version().split()[-1],gmpy2.version(),family,seed,count,fresh,size)


def selected(raw,width,index):
    mantissa,bias,maximum=(52,1023,2047) if width==64 else (23,127,255)
    field=(raw>>mantissa)&maximum
    return index%251==0 or field in (0,maximum,bias-1,bias,bias+30,bias+31,bias+62,bias+63,bias+64)


def hash_word(h,word):
    for i in range(8):h=((h^((word>>(8*i))&255))*0x100000001b3)&((1<<64)-1)
    return h


def probe_reference(groups,long_bits):
    nearest=all_modes=0xcbf29ce484222325;full_count=state_count=0
    for width,rows in groups:
        for index,raw in enumerate(rows):
            a,fa,b,fb=answer(raw,width)
            native=(a,fa) if long_bits==32 else (b,fb)
            for result,flag in (native,(b,fb)):
                nearest=hash_word(hash_word(nearest,result&((1<<64)-1)),flag);full_count+=1
            if selected(raw,width,index):
                for mode in range(4):
                    for result,flag in (native,(b,fb)):
                        all_modes=hash_word(hash_word(all_modes,result&((1<<64)-1)),flag)
                state_count+=4*7*2
    return ('math.intround_long.bits %d\nmath.intround_full.hash %016x\nmath.intround_full.count %d\n'
            'math.intround_all_modes.hash %016x\nmath.intround_state.count %d\n')%(long_bits,nearest,full_count,all_modes,state_count)


def self_check():
    cases=((64,0,(0,0,0,0)),(64,0x3fe0000000000000,(1,0,1,0)),
           (64,0xbfe0000000000000,(-1,0,-1,0)),
           (64,0x41dfffffffe00000,(-(1<<31),1,1<<31,0)),
           (64,0xc1e00000000fffff,(-(1<<31),0,-(1<<31),0)),
           (64,0xc1e0000000100000,(-(1<<31),1,-(1<<31)-1,0)),
           (64,0x43dfffffffffffff,(-(1<<31),1,(1<<63)-1024,0)),
           (64,0x43e0000000000000,(-(1<<31),1,-(1<<63),1)),
           (64,0xc3e0000000000000,(-(1<<31),1,-(1<<63),0)),
           (32,1,(0,0,0,0)),(32,0x3f000000,(1,0,1,0)),
           (32,0x4f000000,(-(1<<31),1,1<<31,0)),
           (32,0xdf000000,(-(1<<31),1,-(1<<63),0)),
           (32,0x7f800001,(-(1<<31),1,-(1<<63),1)))
    for width,raw,expected in cases:
        if answer(raw,width)!=expected:raise RuntimeError('integer oracle fixed-case disagreement')
    from unittest import mock
    factory=tempfile.NamedTemporaryFile
    def failed_write(*args,**kwargs):
        temporary=factory(*args,**kwargs)
        def broken(text):raise OSError('injected write failure')
        temporary.write=broken
        return temporary
    for exists in (False,True):
        for fault in ('write','replace'):
            with tempfile.TemporaryDirectory(prefix='intround-publication-') as directory:
                path=Path(directory)/'reference'
                if exists:path.write_bytes(b'previous');path.chmod(0o640)
                patch=mock.patch.object(tempfile,'NamedTemporaryFile',side_effect=failed_write) if fault=='write' else mock.patch.object(Path,'replace',side_effect=OSError('injected replace failure'))
                try:
                    with patch:publish(path,'new reference')
                except OSError as error:
                    if 'injected' not in str(error):raise
                else:raise RuntimeError('publication failure escaped')
                if exists:
                    if path.read_bytes()!=b'previous' or path.stat().st_mode&0o777!=0o640:raise RuntimeError('failed publication changed destination')
                elif path.exists():raise RuntimeError('failed publication created destination')
                if list(Path(directory).glob('.reference.*')):raise RuntimeError('publication temporary leaked')
    for mode in (None,0o640,0o644):
        with tempfile.TemporaryDirectory(prefix='intround-permission-') as directory:
            path=Path(directory)/'reference'
            if mode is not None:path.write_bytes(b'previous');path.chmod(mode)
            publish(path,'new reference')
            if path.read_text()!='new reference' or path.stat().st_mode&0o777!=(0o644 if mode is None else mode):raise RuntimeError('publication data/permissions differ')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',required=True,type=Path);p.add_argument('--seed',type=int,default=20261027)
    p.add_argument('--count',type=int,default=3000);p.add_argument('--fresh',action='store_true');args=p.parse_args()
    if not 0<=args.seed<1<<64:p.error('--seed must be unsigned64')
    if not 0<=args.count<=10000000:p.error('--count must be in0..10000000')
    self_check()
    args.out.mkdir(parents=True,exist_ok=True)
    groups=[]
    for width in (64,32):
        rows=population(args.seed,args.count,width);groups.append((width,rows));full=[];common=[]
        for raw in rows:
            r32,b32,r64,b64=answer(raw,width)
            full.append(('%0*x %016x %d %016x %d\n')%(width//4,raw,r32&((1<<64)-1),b32,r64&((1<<64)-1),b64))
            if not b32:
                q=value(raw,width)
                input_bits=raw if width==64 else ((raw>>31)<<63 if not q else struct.unpack('>Q',struct.pack('>d',float(q)))[0])
                result_bits=struct.unpack('>Q',struct.pack('>d',r32))[0]
                common.append('%016x %016x\n'%(input_bits,result_bits))
        family='intround%d'%width
        publish(args.out/(family+'.corpus'),header(family,args.seed,args.count,args.fresh,len(full))+'# raw input; signed32 result invalid; signed64 result invalid\n'+''.join(full))
        family='lround' if width==64 else 'lroundf'
        publish(args.out/(family+'.corpus'),header(family,args.seed,args.count,args.fresh,len(common))+'# common valid signed32 results, exactly widened binary64\n'+''.join(common))
        print('intround%d: %d full rows; %d common rows'%(width,len(full),len(common)),flush=True)
    for bits in (32,64):
        publish(args.out/('intround-long%d.hash'%bits),probe_reference(groups,bits))


if __name__=='__main__':main()
