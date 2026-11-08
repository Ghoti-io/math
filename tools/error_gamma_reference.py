# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Focused input recipes and exact contracts; no finite oracle shortcuts."""
import hashlib, importlib.util, json, sys
from fractions import Fraction as F
from pathlib import Path
if not __debug__ or sys.flags.optimize:
    raise SystemExit('error/gamma checks require assertion-enabled Python')
import long_double_seventeen_cases as c
from remaining_reference import encode, decode, params
ROOT = Path(__file__).resolve().parents[1]
PIN = c.PIN
# Filled from required independent inversion; regeneration rederives every seed.
SEAMS = [
    [32, 14, 'erfc-normal', [0x41131ce0, 0x0]],
    [32, 14, 'erfc-zero', [0x4120ddfc, 0x0]],
    [32, 14, 'erf-saturation', [0x407ad445, 0x0]],
    [32, 13, 'erf-saturation', [0x407ad445, 0x0]],
    [32, 15, 'gamma-overflow', [0x420c2910, 0x0]],
    [32, 14, 'erfc-rounded-normal', [0x41131ce0, 0x0]],
    [32, 15, 'gamma-rounded-overflow', [0x420c2910, 0x0]],
    [32, 14, 'erfc-negative-saturation', [0xc07547cb, 0x0]],
    [32, 15, 'gamma-normal-sign0', [0xc20fffc4, 0x0]],
    [32, 15, 'gamma-rounded-normal-sign0', [0xc20fffc4, 0x0]],
    [32, 15, 'gamma-normal-sign1', [0xc20bf74f, 0x0]],
    [32, 15, 'gamma-rounded-normal-sign1', [0xc20bf74f, 0x0]],
    [32, 15, 'gamma-zero-sign0', [0xc21ffe32, 0x0]],
    [32, 15, 'gamma-zero-sign1', [0xc223fff5, 0x0]],
    [64, 14, 'erfc-normal', [0x403a8b12fc6e4892, 0x0]],
    [64, 14, 'erfc-zero', [0x403b39dc41e48bfc, 0x0]],
    [64, 14, 'erf-saturation', [0x4017afb48dc96627, 0x0]],
    [64, 13, 'erf-saturation', [0x4017afb48dc96627, 0x0]],
    [64, 15, 'gamma-overflow', [0x406573fae561f647, 0x0]],
    [64, 14, 'erfc-rounded-normal', [0x403a8b12fc6e4892, 0x0]],
    [64, 15, 'gamma-rounded-overflow', [0x406573fae561f647, 0x0]],
    [64, 14, 'erfc-negative-saturation', [0xc017744f8f74e94a, 0x0]],
    [64, 15, 'gamma-normal-sign0', [0xc0657ffe45f8aa76, 0x0]],
    [64, 15, 'gamma-rounded-normal-sign0', [0xc0657ffe45f8aa76, 0x0]],
    [64, 15, 'gamma-normal-sign1', [0xc0659ffffd729afe, 0x0]],
    [64, 15, 'gamma-rounded-normal-sign1', [0xc0659ffffd729afe, 0x0]],
    [64, 15, 'gamma-zero-sign0', [0xc0667ffffbc63256, 0x0]],
    [64, 15, 'gamma-zero-sign1', [0xc0665ffd05edca00, 0x0]],
    [80, 14, 'erfc-normal', [0x4005, 0xd5126065b720a4e8]],
    [80, 14, 'erfc-zero', [0x4005, 0xd57cddb32ed4a1d6]],
    [80, 14, 'erf-saturation', [0x4001, 0xd0d8e9797c8fb413]],
    [80, 13, 'erf-saturation', [0x4001, 0xd0d8e9797c8fb413]],
    [80, 15, 'gamma-overflow', [0x4009, 0xdb718c066b352e21]],
    [80, 14, 'erfc-rounded-normal', [0x4005, 0xd5126065b720a4e8]],
    [80, 15, 'gamma-rounded-overflow', [0x4009, 0xdb718c066b352e21]],
    [80, 14, 'erfc-negative-saturation', [0xc001, 0xcf29205aa2682c91]],
    [80, 15, 'gamma-normal-sign0', [0xc009, 0xdb7ffff5c5ffcdf5]],
    [80, 15, 'gamma-rounded-normal-sign0', [0xc009, 0xdb7ffff5c5ffcdf5]],
    [80, 15, 'gamma-normal-sign1', [0xc009, 0xdb9ffffffe829047]],
    [80, 15, 'gamma-rounded-normal-sign1', [0xc009, 0xdb9ffffffe829047]],
    [80, 15, 'gamma-zero-sign0', [0xc009, 0xdc3ffff9a465074a]],
    [80, 15, 'gamma-zero-sign1', [0xc009, 0xdc5fffffff13aa65]],
    [128, 14, 'erfc-normal', [0x4005aa24c0cb6e41, 0x49d010bec1719978]],
    [128, 14, 'erfc-zero', [0x4005ab9c8393ddd2, 0x517e5404d6dd3c9d]],
    [128, 14, 'erf-saturation', [0x4002177842bce674, 0x48bc471eea540735]],
    [128, 13, 'erf-saturation', [0x4002177842bce674, 0x48bc471eea540735]],
    [128, 15, 'gamma-overflow', [0x4009b6e3180cd66a, 0x5c4206f128ba77f5]],
    [128, 14, 'erfc-rounded-normal', [0x4005aa24c0cb6e41, 0x49d010bec1719978]],
    [128, 15, 'gamma-rounded-overflow', [0x4009b6e3180cd66a, 0x5c4206f128ba77f5]],
    [128, 14, 'erfc-negative-saturation', [0xc00216348a585939, 0x8f7a86034cb5b0b4]],
    [128, 15, 'gamma-normal-sign0', [0xc009b6ffffeb8bff, 0x9be98e5cd1b61365]],
    [128, 15, 'gamma-rounded-normal-sign0', [0xc009b6ffffeb8bff, 0x9be98e5cd1b61365]],
    [128, 15, 'gamma-normal-sign1', [0xc009b73ffffffd05, 0x208d58d9b2e47e8e]],
    [128, 15, 'gamma-rounded-normal-sign1', [0xc009b73ffffffd05, 0x208d58d9b2e47e8e]],
    [128, 15, 'gamma-zero-sign0', [0xc009b97ffd1c9713, 0x588cde7b42b06957]],
    [128, 15, 'gamma-zero-sign1', [0xc009b9bfffff9504, 0x3dd1443bfd637e1e]],
    [106, 14, 'erfc-normal', [0x4039d7adac608e86, 0xbcde73fc64dd1988]],
    [106, 14, 'erfc-zero', [0x403b39dc41e48bfc, 0x3cdeae17c7980f14]],
    [106, 14, 'erf-saturation', [0x4020e7eddfc34bed, 0xbcca0722de1df83f]],
    [106, 13, 'erf-saturation', [0x4020e7eddfc34bed, 0xbcca0722de1df83f]],
    [106, 15, 'gamma-overflow', [0x406573fae561f647, 0x3d04eedf869c027c]],
    [106, 13, 'erf-dd-saturation', [0x403b39dc41e48bfc, 0x3cdeae17c7980f14]],
    [106, 14, 'erfc-rounded-normal', [0x4039d7adac608e86, 0xbcde73fc64dd1988]],
    [106, 15, 'gamma-rounded-overflow', [0x406573fae561f647, 0x3d04eedf869c027c]],
    [106, 14, 'erfc-negative-saturation', [0xc03b39dc41e48bfc, 0xbcdeae17c7980f14]],
    [106, 15, 'gamma-normal-sign0', [0xc064bffffed67adc, 0x3cfb8219ba40eca8]],
    [106, 15, 'gamma-rounded-normal-sign0', [0xc064bffffed67adc, 0x3cfb8219ba40eca8]],
    [106, 15, 'gamma-normal-sign1', [0xc0649fff3efc93c0, 0xbce101a671678bf4]],
    [106, 15, 'gamma-rounded-normal-sign1', [0xc0649fff3efc93c0, 0xbce101a671678bf4]],
    [106, 15, 'gamma-zero-sign0', [0xc0667ffffbc63256, 0x3d0f0452e4e6d11d]],
    [106, 15, 'gamma-zero-sign1', [0xc0665ffd05edca00, 0x3cfb96776300a2fe]],
    [32, 16, 'lgamma-rounded-overflow', [0x7c44af8e, 0x0]],
    [64, 16, 'lgamma-rounded-overflow', [0x7f5754d9278b51a7, 0x0]],
    [80, 16, 'lgamma-rounded-overflow', [0x7ff1, 0xb8d54c8bfffdebf5]],
    [128, 16, 'lgamma-rounded-overflow', [0x7ff171aa9917fffb, 0xd7ea44ae6d203df6]],
    [106, 16, 'lgamma-rounded-overflow', [0x7f5754d9278b51a7, 0x7bfbc1f01e99fd68]],
    [32, 13, 'erf-saturation-negative', [0xc07ad445, 0x0]],
    [64, 13, 'erf-saturation-negative', [0xc017afb48dc96627, 0x0]],
    [80, 13, 'erf-saturation-negative', [0xc001, 0xd0d8e9797c8fb413]],
    [128, 13, 'erf-saturation-negative', [0xc002177842bce674, 0x48bc471eea540735]],
    [106, 13, 'erf-saturation-negative', [0xc020e7eddfc34bed, 0x3cca0722de1df83f]],
    [106, 13, 'erf-dd-saturation-negative', [0xc03b39dc41e48bfc, 0xbcdeae17c7980f14]],
]

def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()

def raw(fmt, value, sign=0):
    if fmt == 32:
        return encode(F(value), 32) | ((sign if not value else int(value < 0)) << 31), 0
    return c.raw(fmt, value, sign)

def value(fmt, pair):
    return decode(pair[0], 32) if fmt == 32 else c.b.decode(fmt, pair)[3]

def neighbor(fmt, x, direction):
    if fmt != 32:
        return c.s.neighbor(fmt, x, direction)
    word = encode(x, 32)
    if not x:
        return ((1 << 31) if direction < 0 else 0) | 1, 0
    return word + (direction if x > 0 else -direction), 0

def limit(fmt):
    return F(2)**128 - F(2)**104 if fmt == 32 else c.finite_limit(fmt)

def virtual(fmt):
    return F(2)**128 if fmt == 32 else 2*c.overflow_threshold(fmt)-c.finite_limit(fmt)

def normal(fmt):
    return F(2)**(-126 if fmt == 32 else -1022 if fmt == 64 else -969 if fmt == 106 else -16382)

def minimum(fmt):
    return -149 if fmt == 32 else -1074 if fmt in (64,106) else -16445 if fmt == 80 else -16494

def population(seams=None):
    rows=[]; seen=set()
    def add(family,fmt,op,tag,a,labelled=False):
        key=(family,fmt,op,*a,tag if labelled else None)
        if key not in seen:
            rows.append([f'{family}/{fmt}/{c.NAMES[op]}/{tag}',fmt,op,*a,0,0]);seen.add(key)
    # Authenticate the preexisting root registry before using its brackets.
    spec=importlib.util.spec_from_file_location('error_gamma_roots',ROOT/'tools/check-long-double-seventeen-roots.py')
    roots=importlib.util.module_from_spec(spec);spec.loader.exec_module(roots)
    certificates,_=roots.load(ROOT/'tests/corpus')
    for family,fmt in [('float',32),('double',64),*[('long',f)for f in c.FORMATS]]:
        for op in range(13,17):
            for x,tag,sign in [(F(0),'zero',0),(F(0),'negative-zero',1),(F(1,2),'ordinary',0),(-F(1,2),'reflection',0),(F(1),'one',0),(F(2),'two',0),(F(2)**minimum(fmt),'minimum-subnormal',0),(-F(2)**minimum(fmt),'negative-minimum-subnormal',0)]:
                add(family,fmt,op,tag,raw(fmt,x,sign))
            for sign in (0,1):
                if fmt==32:
                    specials=[((sign<<31)|0x7f800000,0),((sign<<31)|0x7fc12345,0),((sign<<31)|0x7f800001,0)]
                else:specials=[c.b.pack(fmt,'inf',sign,F(0)),c.nan(fmt,False,sign),c.nan(fmt,True,sign)]
                for tag,a in zip(('infinity','quiet-nan','signaling-nan'),specials):add(family,fmt,op,tag+str(sign),a)
            if fmt==80:add(family,fmt,op,'malformed',(1,1))
            if fmt==106:add(family,fmt,op,'malformed',(0x7ff0000000000000,1))
        for op in (13,14):
            for x in (F(4),F(16),F(128)):
                for direction in (-1,0,1):
                    a=raw(fmt,x)if not direction else neighbor(fmt,x,direction)
                    for sign in (1,-1):add(family,fmt,op,f'switch-{x}-{direction}-{sign}',raw(fmt,sign*value(fmt,a)))
            for direction in (-1,0,1):
                x=normal(fmt);a=raw(fmt,x)if not direction else neighbor(fmt,x,direction)
                for sign in (1,-1):add(family,fmt,op,f'input-normal-{direction}-{sign}',raw(fmt,sign*value(fmt,a)))
        for op in (15,16):
            add(family,fmt,op,'huge-positive-range',raw(fmt,F(2)**(127 if fmt==32 else 1023 if fmt in(64,106)else 16383)))
            for n in (1,2,3,8,31,64,128,256):
                x=F(-n)
                for direction in (-1,0,1):add(family,fmt,op,f'pole-{n}-{direction}',raw(fmt,x)if not direction else neighbor(fmt,x,direction))
            for x in (F(1),F(2),F(64),F(1024)):
                for direction in (-1,1):add(family,fmt,op,f'recurrence-{x}-{direction}',neighbor(fmt,x,direction))
            for sign in (-1,1):
                x=sign*F(2)**(-(128 if fmt==32 else 1024 if fmt in(64,106)else 16384))
                add(family,fmt,op,'tiny-reciprocal-'+str(sign),raw(fmt,x))
        for certificate in certificates['roots']:
            if certificate['n'] not in (4,5,7,16,32,64,128):continue
            n,side=certificate['n'],certificate['side'];m,e=certificate['distance'];lo=int(m,16)*F(2)**e;hi=lo+F(2)**e
            pole=-n if side=='left'else 1-n;direction=1 if side=='left'else -1
            left,right=sorted((pole+direction*lo,pole+direction*hi));seed=raw(fmt,(left+right)/2);x=value(fmt,seed)
            a=seed if x<left else neighbor(fmt,x,-1);b=neighbor(fmt,value(fmt,a),1)
            for index,item in enumerate((a,b)):
                v=value(fmt,item)
                if v.denominator!=1:add(family,fmt,16,f'negative-root-{n}-{side}-{index}',item)
        if fmt==106:
            for op in (15,16):
                for low in (1,0x8000000000000001):add(family,fmt,op,f'huge-negative-remote-{low:x}',(0xffe0000000000000,low))
            for op in (15,16):
                for high in (0x3ff0000000000000,0x4000000000000000,0xbff0000000000000,0xc070000000000000):
                    for low in (1,0x8000000000000001):add(family,fmt,op,f'remote-{high:x}-{low:x}',(high,low))
        for layout,op,tag,a in (SEAMS if seams is None else seams):
            if layout!=fmt:continue
            x=value(fmt,tuple(a))
            for direction in (-1,0,1):add(family,fmt,op,f'{tag}-{direction}',tuple(a)if not direction else neighbor(fmt,x,direction),True)
    return rows

def special(row):
    _,fmt,op,ah,al,_,_=row
    if fmt!=32:return c.special(row)
    # Projection into binary64 is exact, including independently decoded NaNs.
    p,b,s,inf=params(32);m=ah&(s-1);sign=int(bool(ah&s))
    if m>=inf:
        pair=c.nan(64,m>inf and not bool(m&(1<<22)),sign)if m>inf else c.b.pack(64,'inf',sign,F(0))
    else:pair=c.raw(64,decode(ah,32),sign)
    direct=c.special([row[0],64,op,*pair,0,0])
    if direct is None:return None
    if 'tiny'in direct:return {'tiny':[minimum(32)-2,direct['tiny'][1]]}
    h,l,flags=direct['exact'];kind,sg,_,v=c.b.decode(64,(int(h,16),int(l,16)))
    word=(0x7fc00000 if kind=='nan'else (sg<<31)|0x7f800000 if kind=='inf'else raw(32,v,sg)[0])
    return {'exact':[f'{word:016x}','0000000000000000',flags]}
