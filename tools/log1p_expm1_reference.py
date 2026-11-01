# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent raw populations and exact packing for cancellation-safe APIs."""
from fractions import Fraction
import random
SEED=20261103
# Sixteen largest target-relative residual scores per function/format from
# MPFR/mpmath seed20261104/count4096, de-duplicated with both signs retained.
MIDPOINT_CASES={64:(0x3d0726c5d0e4afdb,0x3d0fffffffffffff,0x3d8fffffffffffff,0x3e0fffffffffffff,0x3fba000000000000,0x3fefffffffffffdb,0x400351798fda3816,0x400601dcd201e0b0,0x40203cc087d877ee,0x40206db06ae7d7d3,0x4039a22e7635043a,0x403b98bc48f18937,0x403d237f0750c865,0x4043fffffffffffd,0x4047acc0106c9960,0x404bee32d2e8e977,0x4052dd0da05fe307,0x4052fd557a946b42,0x40531a9dd3228a5d,0x405572755b2082f4,0x405a4fce7b3a362b,0x405e9754a25311d6,0x4078b70c269c510f,0x4085bf5bafff56cd,0x475456d123ae72e4,0x4e4baf4b7748b8dc,0x518fffffffffffff,0x6db7c112bbad8ae8),32:(0x337fffff,0x34000000,0x34000001,0x347fffff,0x357fffff,0x367fffff,0x377fffff,0x3b5f5ec8,0x3c000000,0x3f11f759,0x3f2d0000,0x3f7fffb8,0x3f800074,0x3fb53ecb,0x40000001,0x42004685,0x42646afd,0x4280ff32,0x4283fd38,0x42a7565d,0x572f47a4,0x72fe5af7)}

def decode(word,width):
    p,bias=(52,1023) if width==64 else (23,127)
    sign=1<<(width-1);a=word&(sign-1);e=a>>p;m=a&((1<<p)-1)
    if e==2*bias+1:raise ValueError('nonfinite rational')
    if e:m+=1<<p
    return (-1 if word&sign else 1)*Fraction(m)*Fraction(2)**((e or 1)-bias-p)

def encode(q,width,negative_zero=False):
    p,bias=(52,1023) if width==64 else (23,127)
    sign=1<<(width-1) if q<0 or (not q and negative_zero) else 0;q=abs(q)
    if not q:return sign
    e=q.numerator.bit_length()-q.denominator.bit_length()
    if q<Fraction(2)**e:e-=1
    e=max(e,1-bias);value=q/Fraction(2)**(e-p);n,r=divmod(value.numerator,value.denominator)
    n+=int(2*r>value.denominator or (2*r==value.denominator and n%2))
    if n==1<<(p+1):n>>=1;e+=1
    if e>bias:return sign|((2*bias+1)<<p)
    return sign|(n if n<1<<p else ((e+bias)<<p)|(n-(1<<p)))

def population(width,seed,count,adversarial=True):
    p,bias=(52,1023) if width==64 else (23,127)
    sign=1<<(width-1);one=bias<<p;inf=(2*bias+1)<<p
    words={0,sign,inf,sign|inf,inf|1,sign|inf|1,inf|(1<<(p-1)),sign|inf|(1<<(p-1))}
    def add(word):
        word &= sign-1
        if 0<=word<inf:words.update((word,sign|word))
    centers=[0,1<<p,one,(bias-1)<<p,(bias-(60 if width==64 else 26))<<p,
             (bias+60)<<p,0x40862e42fefa39f0 if width==64 else 0x42b17218,
             encode(Fraction(40 if width==64 else 20),width),inf-1]
    for center in centers:
        for delta in range(-16,17):add(center+delta)
    for delta in range(-128,129):add(one+delta)
    for field in range(0,2*bias+1,8 if width==64 else 2):
        for mantissa in [0,1,(1<<p)-1]:add((field<<p)|mantissa)
    if adversarial:
        for exponent in [-60,-54,-53,-52,-51,-26,-25,-24,-23,-1,0,1,9,10,52,53,60]:
            center=encode(Fraction(2)**exponent,width)
            for delta in range(-8,9):add(center+delta)
        for bit in range(p-1):
            words.update((inf|(1<<bit),sign|inf|(1<<bit),
                          inf|(1<<(p-1))|(1<<bit),sign|inf|(1<<(p-1))|(1<<bit)))
        words.update((inf+(1<<(p-1))-1,sign|inf+(1<<(p-1))-1,inf+(1<<p)-1,sign|inf+(1<<p)-1))
    for i in range(1,257):add(encode(Fraction(i,256),width))
    # An exact rational ln2 approximation selects reduction boundaries without
    # reading implementation constants. Its omitted tail is below2^-405.
    ln2=2*sum((Fraction(1,3)**(2*n+1)/(2*n+1) for n in range(128)),Fraction())
    for n in sorted(set([-58,-57,-32,-1,0,1,2,31,63,127,128,255,511,512,1023,1024]+list(range(-50,1025,31)))):
        for q in [Fraction(n),Fraction(2*n+1,2)]:
            center=encode(abs(q*ln2),width)
            for delta in [-1,0,1]:add(center+delta)
    if adversarial:
        # Actual nearest transition to -1: exp(x)<=half the spacing above -1.
        boundary=encode((54 if width==64 else 25)*ln2,width)
        for delta in range(-8,9):add(boundary+delta)
        for word in MIDPOINT_CASES[width]:add(word)
    rng=random.Random(seed+width)
    for _ in range(count):
        add(rng.randrange(inf));add(encode(Fraction(rng.randrange(-1024,1025),8)+Fraction(rng.getrandbits(p),1<<p),width))
    return sorted(words)
