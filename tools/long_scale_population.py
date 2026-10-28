# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Deterministic raw input selection, independent of numerical target generation."""
import random

def parameters(width):
    return (52,1023,2047) if width==64 else (23,127,255)

def pairs(width,seed,count):
    rng=random.Random(seed^width);p,bias,emax=parameters(width);sign=1<<(width-1);inf=emax<<p;seen=set()
    def add(raw,n):
        if 0<=raw<1<<width and -(1<<63)<=n<1<<63:seen.add((raw,n))
    def boundaries(raw,deltas):
        a=raw&(sign-1)
        if not a or a>=inf:return [0]
        stored=a>>p
        e=stored-bias if stored else a.bit_length()-1+1-bias-p
        return [0]+[base+d for base in (1-bias-e,1-bias-p-e,bias+1-e) for d in deltas]
    for stored in range(emax):
        for tail in (0,(1<<p)-1):
            for s in (0,sign):
                raw=s|(stored<<p)|tail
                for n in boundaries(raw,(0,)):add(raw,n)
    exponents={-(1<<63),-(1<<63)+1,-(1<<32)-1,-(1<<32),-(1<<32)+1,-(1<<31)-1,-(1<<31),-(1<<31)+1,
      -65536,-5001,-5000,-4999,-513,-512,-511,-1075,-1074,-1023,-1022,-151,-150,-149,-127,-126,-54,-53,-52,-25,-24,-23,-2,-1,
      0,1,2,23,24,25,52,53,54,126,127,128,149,150,151,511,512,513,1023,1024,1074,4999,5000,5001,65536,
      (1<<31)-2,(1<<31)-1,1<<31,(1<<31)+1,(1<<32)-1,1<<32,(1<<32)+1,(1<<63)-2,(1<<63)-1}
    for a in (0,1,2,3,5,(1<<p)-1,1<<p,(1<<(p+1))-1,bias<<p,inf-1,inf,inf|1,inf|(1<<(p-1)),(1<<width)-1-sign):
        for s in (0,sign):
            for n in exponents:add(s|a,n)
    for bit in range(p):
        for delta in (-1,0,1):
            for s in (0,sign):
                raw=s|((1<<bit)+delta)
                for n in boundaries(raw,(-1,0,1)):add(raw,n)
    for _ in range(count):
        raw=rng.getrandbits(width)
        for n in (rng.randrange(-2300,2301),*boundaries(raw,(-1,0,1))):add(raw,n)
    return sorted(seen)
