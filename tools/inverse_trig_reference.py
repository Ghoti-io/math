# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent raw population and exact dyadic encodings for inverse trig."""
import random
from fractions import Fraction

SEED=20261101

def decode(word,width):
    p,bias=(52,1023) if width==64 else (23,127)
    sign=1<<(width-1);a=word&(sign-1);e=a>>p;m=a&((1<<p)-1)
    if e==(bias*2+1):raise ValueError('nonfinite')
    if e:m+=1<<p
    return (-1 if word&sign else 1)*Fraction(m)*Fraction(2)**((e or 1)-bias-p)

def encode(q,width,negative_zero=False):
    p,bias=(52,1023) if width==64 else (23,127)
    sign=1<<(width-1) if q<0 or (not q and negative_zero) else 0;q=abs(q)
    if not q:return sign
    e=q.numerator.bit_length()-q.denominator.bit_length()
    if q<Fraction(2)**e:e-=1
    e=max(e,1-bias);v=q/Fraction(2)**(e-p);n,r=divmod(v.numerator,v.denominator)
    n+=int(2*r>v.denominator or (2*r==v.denominator and n%2))
    if n==1<<(p+1):n>>=1;e+=1
    return sign|(n if n<1<<p else ((e+bias)<<p)|(n-(1<<p)))

def rat(value):
    n,d=value.as_integer_ratio();return Fraction(int(n),int(d))

# Near-midpoint inputs selected solely from directed MPFR/mpmath outputs of
# independent seed20261102/count4096, sixteen closest cells per function/format.
MIDPOINT_CASES = {
    64: (0x3d2bb8cb23481f21,0x3d84ee1cbdc52628,0x3fc9f9ef7317e8dc,0x3fd1bd170f7c70f2,0x3fd345b44d2ef3c2,0x3fd4f8c00d862b9e,0x3fd95f12bdd6c9b6,0x3fd9c990b68c1e7a,0x3fdf400000000000,0x3fe18a08f2af9b3b,0x3fe1a4b1cfb770d7,0x3fe248f797d2ac36,0x3fe2a2e02685ec53,0x3fe4a911f3022de3,0x3fe4fd7052139282,0x3fe6b63610f6c8a1,0x3fe87c41a321286d,0x3fe883ec19715bef,0x3fe904f9f84f8c99,0x3fead6546ee4a430,0x3feaf740a547f78a,0x3feec79ad3336581,0x3fefffffffffff9f,0x3fefffffffffffc2),
    32: (0x371c4440,0x3ca0b1c0,0x3d200000,0x3e1b6028,0x3e1c8078,0x3e5c1da8,0x3e786af0,0x3e823f3a,0x3e983336,0x3e983fc0,0x3e9a36c6,0x3ed057c0,0x3ed2fefe,0x3ee59acc,0x3eeaee7c,0x3f12edc3,0x3f6745fc,0x3f6f5ebe,0x3f7227da,0x3f772daf,0x3f7bd406,0x3f7f6619,0x3f7fff9a,0x3f7fffb8),
}

def population(width,seed,count):
    p,bias=(52,1023) if width==64 else (23,127)
    sign=1<<(width-1);one=bias<<p;inf=(2*bias+1)<<p
    words={0,sign,one,sign|one,inf,sign|inf,inf|1,sign|inf|1,inf|(1<<(p-1)),sign|inf|(1<<(p-1))}
    def add(w):
        if 0<=w<inf:words.update((w,sign|w))
    for center in [0,1<<p,one,one-(1<<p), (bias-30 if width==64 else bias-12)<<p,
                   (bias-60 if width==64 else bias-28)<<p]:
        for delta in range(-8,9):add(center+delta)
    for word in MIDPOINT_CASES[width]:add(word)
    for delta in range(1,129):add(one-delta)
    for e in range(0,bias+1,4):
        for mantissa in [0,1,(1<<p)-1]:add((e<<p)|mantissa)
    for i in range(1,257):add(encode(Fraction(i,256),width))
    rng=random.Random(seed+width)
    for _ in range(count):
        add(rng.randrange(one));add(encode(Fraction(rng.getrandbits(p+1),1<<(p+1)),width))
    return sorted(words)
