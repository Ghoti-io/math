# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Raw hyperbolic populations, using exact rational packing and integer draws."""
from fractions import Fraction
from math import isqrt
import random
from log1p_expm1_reference import decode,encode
SEED=20261105
# Selected from independent seed20261106/count4096 base output, with both signs.
MIDPOINT_SOURCE_SHA="0cbd1532498a6cf905a5e30617e8843066881b474fbe250091865faf300fd868"
MIDPOINT_CASES={64:(0x3e4d1093aef4bdd6,0x3e4ffffffffffff0,0x3e4ffffffffffff1,0x3e4ffffffffffff2,0x3e4ffffffffffff3,0x3e4ffffffffffff4,0x3e4ffffffffffff5,0x3e4ffffffffffff6,0x3e4ffffffffffff7,0x3e4ffffffffffff8,0x3e4ffffffffffff9,0x3e4ffffffffffffa,0x3e4ffffffffffffb,0x3e4ffffffffffffc,0x3e4ffffffffffffd,0x3e4ffffffffffffe,0x3e4fffffffffffff,0x3ee89f176c023611,0x3f1efcb1da12cad3,0x3f5ea1b5440402bd,0x3f7b2739a6967ef8,0x3fbe000000000000,0x3fce000000000000,0x3fdf400000000000,0x3fe0200000000000,0x3fe0c00000000000,0x3fe7e00000000000,0x3fe8a00000000000,0x3fece00000000000,0x3fed600000000000,0x3fede00000000000,0x3fef600000000000,0x3feffffffffffffb,0x3feffffffffffffe,0x3ff000000000000f,0x3ff7a29940315831,0x4000000000000006,0x40003f6899858b93,0x40180013edeb8732,0x401a0518e56f221f,0x402da27f6d95368e,0x402ffffffffffffb,0x4030000000000004,0x4030ade9974de92a,0x40330fc1931f09ba,0x40330fc1931f09bb,0x40330fc1931f09bc,0x40330fc1931f09bd,0x40330fc1931f09be,0x40330fc1931f09bf,0x40330fc1931f09c0,0x40330fc1931f09c1,0x40330fc1931f09c2,0x40330fc1931f09c3,0x40330fc1931f09c4,0x40330fc1931f09c5,0x40330fc1931f09c6,0x40330fc1931f09c7,0x40330fc1931f09c8,0x40330fc1931f09c9,0x40330fc1931f09d1,0x40330fc1931f09da,0x4043fc2028fb7684,0x40510393eb952dfd,0x406379792089bec2,0x40716b199daeb228,0x4073541fef01c615,0x40737a3b99880fa9,0x407b73e7528e1272,0x407bd0f8f2e1715b,0x407d983c51b88eaa,0x407f202350ba05b0,0x407ffffffffffffe,0x408067e5afeabc4a,0x4082412155294d24,0x408574c4d63a25b7),32:(0x39b504ec,0x39b504ed,0x39b504ee,0x39b504ef,0x39b504f0,0x39b504f1,0x39b504f2,0x39b504f3,0x39b504f4,0x39b504f5,0x39b504f6,0x39b504f7,0x39b504f8,0x39b504f9,0x39b504fa,0x39b504fb,0x39e8e70d,0x3adbce1c,0x3b256179,0x3c90d56e,0x3cfb6b9e,0x3d400000,0x3dd80000,0x3e380000,0x3e980000,0x3ea80000,0x3ec40000,0x3eea0000,0x3f000000,0x3f000005,0x3f0037e2,0x3f1d0000,0x3f1e0000,0x3f360000,0x3f370000,0x3f3d0000,0x3f460000,0x3f480000,0x3f540000,0x3f7ffffa,0x3f800001,0x40000002,0x407fffff,0x409eb77f,0x40c59357,0x40f9330d,0x40fecaf0,0x41102caf,0x41102cb0,0x41102cb1,0x41102cb2,0x41102cb3,0x41102cb4,0x41102cb5,0x41102cb6,0x41102cb7,0x41102cb8,0x41102cb9,0x41102cba,0x41102cbb,0x41102cbc,0x41102cbd,0x41102cbe,0x411c8da4,0x41200008,0x4165eac3,0x417167f4,0x41abe688,0x4220dc98,0x4243015d,0x4280ece6,0x429e55a4)}


def population(width,seed,count,adversarial=True):
    p,bias=(52,1023) if width==64 else (23,127)
    sign=1<<(width-1);one=bias<<p;inf=(2*bias+1)<<p
    words={0,sign,inf,sign|inf}
    def add(word):
        if 0<=word<inf:words.update((word,sign|word))
    cut=0x408633ce8fb9f87e if width==64 else 0x42b2d4fd
    centers=[0,1<<p,one,(bias-1)<<p,(bias-(60 if width==64 else 26))<<p,
             cut,inf-1,encode(Fraction(40),width),encode(Fraction(20 if width==64 else 10),width)]
    ln2=2*sum((Fraction(1,3)**(2*n+1)/(2*n+1) for n in range(128)),Fraction())
    # True nearest tanh->1 and cosh->1 boundaries, not merely explicit guards.
    centers.append(encode((Fraction(55,2) if width==64 else 13)*ln2,width))
    centers.append(encode(Fraction(2)**-26 if width==64 else Fraction(isqrt(2<<256),1<<140),width))
    for center in centers:
        for delta in range(-16,17):add(center+delta)
    for field in range(0,2*bias+1,8 if width==64 else 2):
        for mantissa in [0,1,(1<<p)-1]:add((field<<p)|mantissa)
    for exponent in [-60,-54,-53,-52,-27,-26,-25,-24,-23,-13,-12,-11,-1,0,1,4,5,9]:
        center=encode(Fraction(2)**exponent,width)
        for delta in range(-8,9):add(center+delta)
    for bit in range(p-1):
        for s in [0,sign]:words.update((s|inf|(1<<bit),s|inf|(1<<(p-1))|(1<<bit)))
    for s in [0,sign]:words.update((s|inf|((1<<(p-1))-1),s|inf|((1<<p)-1)))
    for i in range(1,257):add(encode(Fraction(i,256),width))
    for n in sorted(set([0,1,2,28,29,57,58,127,128,129,1023,1024,1025]+list(range(0,1026,31)))):
        for q in [Fraction(n),Fraction(2*n+1,2)]:
            center=encode(q*ln2,width)
            for delta in [-1,0,1]:add(center+delta)
    if adversarial:
        for center in MIDPOINT_CASES[width]:
            for delta in [-1,0,1]:add(center+delta)
    rng=random.Random(seed+width)
    for _ in range(count):
        add(rng.randrange(inf))
        add(encode(abs(Fraction(rng.randrange(-8192,8193),8)+Fraction(rng.getrandbits(p),1<<p)),width))
    return sorted(words)
