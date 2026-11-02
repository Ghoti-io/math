# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Exact inverse-hyperbolic raw populations and rational seam selection."""
from fractions import Fraction
import random
from log1p_expm1_reference import decode,encode
SEED=20261107
MIDPOINT_SOURCE_SHA="bf9fc56023bfa6b6c73ed03838baa49a843c52b82cdabd2ec2e46d513a8bad44"
MIDPOINT_CASES={64:(0x3fad536a36a3f7e0,0x3fb334f746802cd0,0x3fc4750353fb5470,0x3fc62c3e0404ae50,0x3fc8e247130384a0,0x3fd03332d3ee98b8,0x3fd20d215c5e58b4,0x3fd474f2ea4ab44c,0x3fd5e74ce5045eb4,0x3fd6250097decae4,0x3fd7321fc1210150,0x3fd7a220748e5394,0x3fdaaaaaaaaaaab7,0x3fe3387756a5a434,0x3fe3a07c999d49fe,0x3fe3ba72cd14bae4,0x3fe45d0673faf3d6,0x3fe7414f849f555c,0x3fe7722373ffe1a6,0x3fe8eb6e39a8fd7c,0x3feaea5cef761378,0x3fedfb633a099f2c,0x3fee72e80af35ede,0x3fef5cfb81733fe4,0x3fef99ae56d87042,0x3fefffffffffff9e,0x3ff000000000002c,0x3ff0000000000053,0x3ff000000000005f,0x3ff21a50860fed17,0x3ff26082fcf047cb,0x3ff8600000000000,0x3ffaa00000000000,0x3ffdd3a727915d07,0x4002267b5f03fe7e,0x4002ce912a05626c,0x400991de2f25fec7,0x40155dc9a50f4fb6,0x401f51999810088b,0x401ffee95ef9f50f,0x4021a1f92a08a9de,0x40230e039dd430d8,0x4026078ee6f3e5fb,0x40286413fcecc76b,0x402aa2289788323b,0x402b11344dd49bf8,0x402b4de126325a3a,0x402b91fb41cd3c53,0x402f2651848e0c41,0x402fb1d99815feaa,0x40302dcc46e892b8,0x53a24c9255e15a30,0x61b4658bd3764817,0x7279095e1d3b6391,0x76b7ee643283d159),32:(0x3a27a431,0x3bfc7d8f,0x3c1b3e9d,0x3e0a39e0,0x3e0a3eb8,0x3e97dfb8,0x3ea8b364,0x3ebd2524,0x3ed6a964,0x3eead9e0,0x3eee5c9c,0x3efffff2,0x3efffff5,0x3efffff8,0x3efffffb,0x3efffffe,0x3f000002,0x3f000005,0x3f000008,0x3f00000b,0x3f00000e,0x3f179930,0x3f1c6a64,0x3f4cb6b0,0x3f501a9a,0x3f5e6ee0,0x3f5fb2a6,0x3f6d059c,0x3f6f61fc,0x3f7fff8b,0x3f7fffa3,0x3f800024,0x3f8c8000,0x3f9711c1,0x3fad0000,0x3faff874,0x3fbad369,0x3fc017a6,0x3ffdfcc7,0x4003ecb6,0x40048d78,0x4065c7fc,0x40ed4432,0x40feffff,0x4102e3af,0x411007f3,0x41114dd1,0x412d9da7,0x4133af14,0x4134125f,0x413a5831,0x417826ab,0x43f96405,0x47d5ce97,0x5c03de65,0x5e616550,0x5f48969f,0x603d308b,0x6b67b655)}

def population(width,seed,count,adversarial=True):
    p,bias=(52,1023) if width==64 else (23,127)
    sign=1<<(width-1);one=bias<<p;inf=(2*bias+1)<<p
    words={0,sign,inf,sign|inf,inf|(1<<(p-1)),sign|inf|(1<<(p-1))}
    def add(word):
        if 0<=word<inf:words.update((word,sign|word))
    centers=[0,1<<p,one,(bias-1)<<p,(bias-(60 if width==64 else 26))<<p,
             (bias+60)<<p,inf-1]
    for q in [Fraction(5,12),Fraction(13,12),Fraction(1,5),Fraction(2),Fraction(4)]:centers.append(encode(q,width))
    for center in centers:
        for delta in range(-16,17):add(center+delta)
    for delta in range(-128,129):add(one+delta)
    for field in range(0,2*bias+1,8 if width==64 else 2):
        for mantissa in [0,1,(1<<p)-1]:add((field<<p)|mantissa)
    for exponent in [-60,-54,-53,-52,-27,-26,-25,-24,-23,-12,-1,0,1,4,5,30,59,60,61]:
        center=encode(Fraction(2)**exponent,width)
        for delta in range(-8,9):add(center+delta)
    for bit in range(p-1):
        for s in [0,sign]:words.update((s|inf|(1<<bit),s|inf|(1<<(p-1))|(1<<bit)))
    for s in [0,sign]:words.update((s|inf|((1<<(p-1))-1),s|inf|((1<<p)-1)))
    for i in range(1,257):
        add(encode(Fraction(i,256),width));add(encode(1+Fraction(i,256),width))
    # Inverse images of logarithm-argument powers, independently rational.
    for n in sorted(set([0,1,2,3,4,8,16,23,24,25,52,53,54,59,60,61,127,128,1023]+list(range(0,1024,31)))):
        y=Fraction(2)**n
        for q in [(y-1/y)/2,(y+1/y)/2,(y-1)/(y+1)]:
            center=encode(q,width)
            for delta in [-1,0,1]:add(center+delta)
    if adversarial:
        for center in MIDPOINT_CASES[width]:
            for delta in [-1,0,1]:add(center+delta)
    rng=random.Random(seed+width)
    for _ in range(count):
        add(rng.randrange(inf))
        add(encode(abs(Fraction(rng.randrange(-4096,4097),256)+Fraction(rng.getrandbits(p),1<<p)),width))
        add(encode(Fraction(rng.getrandbits(p),1<<p),width))
    return sorted(words)
