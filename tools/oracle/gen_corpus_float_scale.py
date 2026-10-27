#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact Float decomposition/scaling from Fraction and independent pinned MPFR.

Raw rows preserve signaling NaNs. Widened per-function corpora exclude sNaNs.
Scaling uses nearest bits and after-round tininess; flags are explicit contracts.
"""
import argparse
from pathlib import Path
import random
import os
import shutil
import tempfile
import gmpy2
from gen_corpus_floattrig import (Fraction,SIGN,INF,QNAN,value,wide,power,fraction,
                                 floor_log2,round32,rational)


def signaling(raw):return (raw&~SIGN)>INF and not raw&0x00400000

def scale(raw,n):
    a=raw&~SIGN
    if a>INF:return QNAN,int(signaling(raw))
    if not a or a==INF:return raw,0
    k=max(-512,min(512,n));exact=fraction(raw)*power(k)
    result=round32(exact)
    with gmpy2.context(precision=24,emin=-148,emax=128,subnormalize=True,round=gmpy2.RoundToNearest):
        m=gmpy2.mul_2exp(gmpy2.mpfr(value(raw)),k)
    other=((raw&SIGN)|INF) if gmpy2.is_infinite(m) else ((raw&SIGN) if gmpy2.is_zero(m) else round32(rational(m)))
    if result!=other:raise RuntimeError('Float scaling Fraction/MPFR disagreement')
    if (result&~SIGN)==INF:return result,20
    inexact=fraction(result)!=exact
    return result,(16|(8 if (result&~SIGN)<0x00800000 else 0)) if inexact else 0


def decompose(raw):
    a=raw&~SIGN
    if a>INF:return QNAN,0,int(signaling(raw)),0x7fffffff,1
    if a==INF:return raw,0,0,0x7fffffff,1
    if not a:return raw,0,0,-0x80000000,1
    q=fraction(raw);e=floor_log2(q)+1;f=round32(q/power(e))
    with gmpy2.context(precision=1200):
        me,mf=gmpy2.frexp(gmpy2.mpfr(value(raw)))
        ie=gmpy2.get_exp(gmpy2.mpfr(abs(value(raw))))-1
    if int(me)!=e or round32(rational(mf))!=f or int(ie)!=e-1:raise RuntimeError('Float decomposition Fraction/MPFR disagreement')
    return f,e,0,e-1,0


def population(seed,count):
    rng=random.Random(seed);seen=set()
    def add(raw):
        if 0<=raw<=0xffffffff:seen.add(raw)
    for exponent in range(256):
        for tail in (0,1,0x3fffff,0x7ffffe,0x7fffff,rng.getrandbits(23)):
            add((exponent<<23)|tail);add(SIGN|(exponent<<23)|tail)
    for bit in range(23):
        for delta in (-1,0,1):add((1<<bit)+delta);add(SIGN|((1<<bit)+delta))
    for raw in (1,2,3,5,0x7fffff,0x800000,0xffffff,0x1000000,0x3f800000,INF,INF|1,QNAN,0x7fffffff):add(raw);add(SIGN|raw)
    for _ in range(count):add(rng.getrandbits(32))
    return sorted(seen)


def exponents(raw):
    a=raw&~SIGN
    ns={-2147483648,-513,-512,-277,-151,-150,-149,-128,-127,-126,-25,-24,-23,-2,-1,0,1,2,23,24,25,126,127,128,149,150,151,277,512,513,2147483647}
    if a and a<INF:
        e=floor_log2(fraction(raw))+127
        for boundary in (255-e,1-e,-e,-22-e,-23-e,-24-e):
            ns.update((boundary-1,boundary,boundary+1))
    return sorted(ns)


def selected(raw,n,index):
    a=raw&~SIGN
    return index%251==0 or (a in (0,1,2,3,5,0x7fffff,0x800000,0xffffff,0x1000000,0x3f800000,0x7f7fffff,INF,INF|1,QNAN,0x7fffffff) and n in (-2147483648,-150,-24,-1,0,1,127,128,2147483647))


def hash_word(h,word):
    for i in range(8):h=((h^((word>>(8*i))&255))*0x100000001b3)&((1<<64)-1)
    return h


def answers(row):
    raw,n,r,flags,f,e,ff,ilog,ifl=row
    return ((r,0,flags),(r,0,flags),(f,e&0xffffffff,ff),(f,0,ff),(ilog&0xffffffff,0,ifl))


def probe_reference(rows):
    full=allm=0xcbf29ce484222325;states=0
    for index,row in enumerate(rows):
        for result in answers(row):
            for word in result:full=hash_word(full,word)
        if selected(row[0],row[1],index):
            for mode in range(4):
                for result in answers(row):
                    for word in result:allm=hash_word(allm,word)
            states+=4*7*5
    return 'math.floatscale_full.hash %016x\nmath.floatscale_full.count %d\nmath.floatscale_all_modes.hash %016x\nmath.floatscale_state.count %d\n'%(full,len(rows)*5,allm,states)


def publish(path,text):
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,prefix='.'+path.name+'.',delete=False) as out:
            temporary=Path(out.name);out.write(text)
        temporary.chmod(path.stat().st_mode&0o777 if path.exists() else 0o644);temporary.replace(path)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def publish_set(directory,payloads):
    """Stage a complete generation; roll back replaced files on an exception.

    Individual replacements are atomic. The set is not crash-atomic: mandatory
    complete-file checksums reject an interrupted mixed generation.
    """
    stage=Path(tempfile.mkdtemp(prefix='.float-scale-set.',dir=directory))
    installed=[];preserve=False
    try:
        for index,(name,text) in enumerate(payloads.items()):
            target=directory/name
            publish(stage/('new%d'%index),text)
            (stage/('new%d'%index)).chmod(target.stat().st_mode&0o777 if target.exists() else 0o644)
            if target.exists():shutil.copy2(target,stage/('old%d'%index))
        for index,name in enumerate(payloads):
            (stage/('new%d'%index)).replace(directory/name);installed.append((index,name))
    except BaseException:
        try:
            for index,name in reversed(installed):
                backup=stage/('old%d'%index)
                if backup.exists():os.replace(backup,directory/name)
                else:(directory/name).unlink(missing_ok=True)
        except OSError as error:
            preserve=True
            raise RuntimeError('Float scale rollback failed; recovery files retained at '+str(stage)) from error
        raise
    finally:
        if not preserve:shutil.rmtree(stage)


def self_check():
    for raw,n,result,flags in ((1,-1,0,24),(3,-1,2,24),(5,-1,2,24),(0xffffff,-1,0x800000,16),
      (SIGN|0xffffff,-1,SIGN|0x800000,16),(0x800000,-1,0x400000,0),(0x3f800000,128,INF,20),
      (0x3f800000,-149,1,0),(0x3f800000,-150,0,24),(0x80000000,2147483647,0x80000000,0),
      (INF,-2147483648,INF,0),(INF|1,0,QNAN,1),(QNAN,0,QNAN,0)):
        if scale(raw,n)!=(result,flags):raise RuntimeError('Float scaling fixed boundary control failed')
    for raw,expected in ((1,(0x3f000000,-148,0,-149,0)),(0x800000,(0x3f000000,-125,0,-126,0)),
      (0x3f800000,(0x3f000000,1,0,0,0)),(0,(0,0,0,-0x80000000,1)),(QNAN,(QNAN,0,0,0x7fffffff,1))):
        if decompose(raw)!=expected:raise RuntimeError('Float decomposition fixed boundary control failed')
    from unittest import mock
    factory=tempfile.NamedTemporaryFile
    def fail_write(*args,**kwargs):
        temporary=factory(*args,**kwargs)
        def broken(text):raise OSError('injected write failure')
        temporary.write=broken;return temporary
    for exists in (False,True):
        for fault in ('write','replace'):
            with tempfile.TemporaryDirectory(prefix='floatscale-publication-') as directory:
                path=Path(directory)/'reference'
                if exists:path.write_bytes(b'previous');path.chmod(0o640)
                patch=mock.patch.object(tempfile,'NamedTemporaryFile',side_effect=fail_write) if fault=='write' else mock.patch.object(Path,'replace',side_effect=OSError('injected replace failure'))
                try:
                    with patch:publish(path,'new')
                except OSError as error:
                    if 'injected' not in str(error):raise
                else:raise RuntimeError('publication failure escaped')
                if exists:
                    if path.read_bytes()!=b'previous' or path.stat().st_mode&0o777!=0o640:raise RuntimeError('failed publication changed destination')
                elif path.exists():raise RuntimeError('failed publication created destination')
                if list(Path(directory).glob('.reference.*')):raise RuntimeError('temporary reference leaked')
    for failure in range(5):
        for exists in (False,True):
            with tempfile.TemporaryDirectory(prefix='floatscale-set-control-') as directory:
                root=Path(directory);payloads={'item%d'%i:'new%d'%i for i in range(5)}
                if exists:
                    for name in payloads:(root/name).write_text('old');(root/name).chmod(0o640)
                replace=Path.replace;calls=0
                def fail_nth(path,target):
                    nonlocal calls
                    if path.name.startswith('new'):
                        calls+=1
                        if calls==failure+1:raise OSError('injected set replacement failure')
                    return replace(path,target)
                try:
                    with mock.patch.object(Path,'replace',fail_nth):publish_set(root,payloads)
                except OSError as error:
                    if 'injected' not in str(error):raise
                else:raise RuntimeError('set publication failure escaped')
                for name in payloads:
                    if exists:
                        if (root/name).read_text()!='old' or (root/name).stat().st_mode&0o777!=0o640:raise RuntimeError('set rollback changed prior generation')
                    elif (root/name).exists():raise RuntimeError('set rollback left a partial generation')
                if list(root.glob('.float-scale-set.*')):raise RuntimeError('set staging directory leaked')
    for mode in (None,0o640,0o644):
        with tempfile.TemporaryDirectory(prefix='floatscale-permission-') as directory:
            path=Path(directory)/'reference'
            if mode is not None:path.write_bytes(b'previous');path.chmod(mode)
            publish(path,'new')
            if path.stat().st_mode&0o777!=(0o644 if mode is None else mode):raise RuntimeError('publication permission changed')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seed',type=int,default=20261027)
    parser.add_argument('--count',type=int,default=1000);parser.add_argument('--fresh',action='store_true');args=parser.parse_args()
    if not 0<=args.seed<1<<64:parser.error('--seed must be unsigned64')
    if not 0<=args.count<=50000:parser.error('--count must be in0..50000')
    self_check();raws=population(args.seed,args.count);rows=[];scalelines=[];frexplines=[];iloglines=[]
    for raw in raws:
        f,e,ff,ilog,ifl=decompose(raw)
        if not signaling(raw):
            frexplines.append('%016x %016x %016x\n'%(wide(raw),wide(f),e&((1<<64)-1)))
            iloglines.append('%016x %016x\n'%(wide(raw),ilog&((1<<64)-1)))
        for n in exponents(raw):
            result,flags=scale(raw,n);rows.append((raw,n,result,flags,f,e,ff,ilog,ifl))
            if not signaling(raw):scalelines.append('%016x %016x %016x\n'%(wide(raw),n&((1<<64)-1),wide(result)))
    def header(family,size):
        return '# Pinned oracle: tools/oracle/gen_corpus_float_scale.py; MPFR %s gmpy2 %s\n# function %s\n# seed %d count %d fresh %s entries %d\n'%(gmpy2.mpfr_version().split()[-1],gmpy2.version(),family,args.seed,args.count,args.fresh,size)
    args.out.mkdir(parents=True,exist_ok=True)
    rawtext=''.join(' '.join('%08x'%(v&0xffffffff) for v in row)+'\n' for row in rows)
    payloads={'float_scale.corpus':header('float_scale',len(rows))+'# raw x n scale flags fraction exponent flags ilogb flags\n'+rawtext}
    for name,lines in (('scalbnf',scalelines),('frexpf',frexplines),('ilogbf',iloglines)):
        payloads[name+'.corpus']=header(name,len(lines))+'# exactly widened binary32 values; native int words sign-extended to64\n'+''.join(lines)
    payloads['float_scale-special.hash']=probe_reference(rows)
    publish_set(args.out,payloads)
    print('float_scale: %d raw rows; %d scale hash rows; %d decomposition hash rows'%(len(rows),len(scalelines),len(frexplines)),flush=True)


if __name__=='__main__':main()
