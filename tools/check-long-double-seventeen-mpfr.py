#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent directed MPFR focused checks for the seventeen raw adapters.

Uses the MPFR C ABI directly; no numerical approximation is shared with the
implementation. This focused tool is not a substitute for the pinned external
MPFR/mpmath release oracle or the full state/ABI controls.
"""
import argparse,ctypes as C,ctypes.util,importlib.util,json,subprocess,sys
from fractions import Fraction as F
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('assertion-enabled Python required')
z=importlib.util.spec_from_file_location('seventeen_scale',Path(__file__).with_name('check-long-double-scale.py'))
s=importlib.util.module_from_spec(z);z.loader.exec_module(s);b=s.base
z=importlib.util.spec_from_file_location('seventeen_contract',Path(__file__).with_name('check-long-double-seventeen.py'))
contract=importlib.util.module_from_spec(z);z.loader.exec_module(contract);c=contract.c
NAMES='sin cos tan asin acos atan atan2 sinh cosh tanh asinh acosh atanh erf erfc gamma lgamma'.split()
class MP(C.Structure):_fields_=[('prec',C.c_long),('sign',C.c_int),('exp',C.c_long),('limbs',C.c_void_p)]
lib=C.CDLL(ctypes.util.find_library('mpfr') or 'libmpfr.so.6')
ptr=C.POINTER(MP)
lib.mpfr_init2.argtypes=[ptr,C.c_long];lib.mpfr_clear.argtypes=[ptr]
lib.mpfr_set_str.argtypes=[ptr,C.c_char_p,C.c_int,C.c_int]
lib.mpfr_set_inf.argtypes=[ptr,C.c_int];lib.mpfr_set_zero.argtypes=[ptr,C.c_int]
lib.mpfr_set_inf.restype=None;lib.mpfr_set_zero.restype=None
lib.mpfr_get_str.argtypes=[C.c_void_p,C.POINTER(C.c_long),C.c_int,C.c_size_t,ptr,C.c_int];lib.mpfr_get_str.restype=C.c_void_p
lib.mpfr_free_str.argtypes=[C.c_void_p]
lib.mpfr_number_p.argtypes=[ptr];lib.mpfr_get_version.restype=C.c_char_p
for name in NAMES:
    if name=='lgamma':getattr(lib,'mpfr_lgamma').argtypes=[ptr,C.POINTER(C.c_int),ptr,C.c_int]
    elif name=='atan2':getattr(lib,'mpfr_atan2').argtypes=[ptr,ptr,ptr,C.c_int]
    else:getattr(lib,'mpfr_'+name).argtypes=[ptr,ptr,C.c_int]
def evaluate(op,x,y,rnd,signs=(0,0),kinds=('finite','finite')):
    a,bb,out=MP(),MP(),MP()
    for v in (a,bb,out):lib.mpfr_init2(C.byref(v),6000)
    try:
        for v,value,kind,sign in ((a,x,kinds[0],signs[0]),(bb,y,kinds[1],signs[1])):
            if kind=='inf':lib.mpfr_set_inf(C.byref(v),-1 if sign else 1);continue
            if not value:lib.mpfr_set_zero(C.byref(v),-1 if sign else 1);continue
            text=('-' if value<0 else '')+format(abs(value.numerator),'b')+'@'+str(-(value.denominator.bit_length()-1))
            assert not lib.mpfr_set_str(C.byref(v),text.encode(),2,0)
        fn=getattr(lib,'mpfr_'+NAMES[op])
        if op==6:fn(C.byref(out),C.byref(a),C.byref(bb),rnd)
        elif op==16:
            sign=C.c_int();fn(C.byref(out),C.byref(sign),C.byref(a),rnd)
        else:fn(C.byref(out),C.byref(a),rnd)
        if not lib.mpfr_number_p(C.byref(out)):return None
        exponent=C.c_long();p=lib.mpfr_get_str(None,C.byref(exponent),2,0,C.byref(out),0)
        try:digits=C.string_at(p).decode()
        finally:lib.mpfr_free_str(p)
        sign=-1 if digits.startswith('-') else 1;digits=digits.lstrip('-')
        assert abs(exponent.value-len(digits))<=1000000,'bounded MPFR output exponent'
        return b.scale(sign*int(digits,2),exponent.value-len(digits))
    finally:
        for v in (a,bb,out):lib.mpfr_clear(C.byref(v))
def cases():
    rows=[]
    for fmt in (64,80,128,106):
        for op in range(17):
            values=[F(1,2),F(-1,2)]
            if op==11:values=[F(3,2),F(3)]
            for x in values:rows.append([fmt,op,*b.pack(fmt,'finite',int(x<0),x),*b.pack(fmt,'finite',0,F(3,4))])
        for exponent in (127,1023,16383) if fmt in (80,128) else (127,1023):
            for op in range(3):rows.append([fmt,op,*b.pack(fmt,'finite',0,b.scale(1,exponent)),0,0])
        for op in (0,2,3,5,7,9,10,12,13,14):
            rows.append([fmt,op,*b.pack(fmt,'finite',0,b.scale(1,-1074 if fmt in (64,106) else -16445 if fmt==80 else -16494)),0,0])
        for op in (13,14):rows.append([fmt,op,*b.pack(fmt,'finite',0,F(16)),0,0])
        if fmt==106:
            for op in (0,1,2,3,4,5,10,11,12,15,16):
                if op in (3,12):raw=(0x3fe0000000000000,1)
                else:raw=(0x3ff0000000000000,1)
                rows.append([fmt,op,*raw,0,0])
    return rows

def reference(row):
    cell={'input':['focused-mpfr',*row]};direct=c.special(cell['input'])
    if direct is not None:cell['reference']=direct;return cell
    fmt,op,ah,al,bh,bl=row;ka,sa,_,x=b.decode(fmt,(ah,al));kb,sb,_,y=b.decode(fmt,(bh,bl))
    lo,hi=(evaluate(op,x,y,rnd,(sa,sb),(ka,kb))for rnd in(3,2))
    assert lo is not None and hi is not None,'nonfinite MPFR output lacks independent special contract'
    assert lo<=hi and(lo>0 or hi<0),'certified nonzero ordinary sign'
    e=b.exponent(max(abs(lo),abs(hi)))-2303;unit=b.scale(1,e)
    limit=c.finite_limit(fmt);virtual=2*c.overflow_threshold(fmt)-limit
    range_='overflow'if min(abs(lo),abs(hi))>=virtual else'finite'if max(abs(lo),abs(hi))<=limit else'edge'
    cell['reference']={'interval':[format(lo//unit,'x'),format(-((-hi)//unit),'x'),e],'sign':int(hi<0),'range':range_,'independent_precision':6000}
    return cell

def verify(cell,line):
    oh,ol,flags,err=line.split();assert int(err)==123,'focused errno preservation'
    contract.verify(cell,f'{oh} {ol} {flags} 173 1 0')

def rejecting_controls():
    def line(raw,flags):return f'{raw[0]:016x} {raw[1]:016x} {flags} 123'
    domain=reference([64,3,*c.raw(64,2),0,0]);verify(domain,line(b.pack(64,'nan',0,F(0)),1))
    tiny=reference([64,0,*c.raw(64,b.scale(1,-1074)),0,0]);verify(tiny,line(c.raw(64,0),12))
    # A far result exceeds the finite maximum's bounded virtual neighbor.
    value=2*c.finite_limit(64);e=b.exponent(value)-2303;n=int(value/b.scale(1,e))
    far={'input':['overflow-control',64,0,0,0,0,0],'reference':{'interval':[format(n,'x'),format(n,'x'),e],'sign':0,'range':'overflow','independent_precision':6000}}
    verify(far,line(b.pack(64,'inf',0,F(0)),20))
    angle=reference([64,6,*c.raw(64,0,1),*c.raw(64,-1)]);lo,hi=contract.bounds(angle['reference']['interval']);verify(angle,line(c.s.rounded(64,(lo+hi)/2,1),4))
    limit=reference([64,5,*b.pack(64,'inf',0,F(0)),0,0]);lo,hi=contract.bounds(limit['reference']['interval']);verify(limit,line(c.s.rounded(64,(lo+hi)/2,0),4))
    lo,hi=contract.bounds(angle['reference']['interval'])
    for cell,output,message in((domain,line(c.raw(64,0),1),'exact special result'),(tiny,line(c.raw(64,0,1),12),'classification/sign'),(far,line(c.raw(64,c.finite_limit(64)),4),'range overflow result'),(angle,line(c.s.rounded(64,-(lo+hi)/2,0),4),'classification/sign')):
        try:verify(cell,output)
        except contract.Rejected as error:assert message in str(error),'intended focused assertion'
        else:raise AssertionError('focused MPFR rejecting control accepted')
    return 4

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--json',type=Path);args=ap.parse_args()
    rows=cases();payload=''.join(f'{f} {op} {ah:x} {al:x} {bh:x} {bl:x}\n'for f,op,ah,al,bh,bl in rows)
    run=subprocess.run([str(args.probe.resolve())],input=payload,text=True,capture_output=True,timeout=3600)
    assert run.returncode==0,(run.returncode,len(run.stdout.splitlines()),run.stderr)
    lines=run.stdout.splitlines();assert len(lines)==len(rows)
    for i,(row,line) in enumerate(zip(rows,lines,strict=True)):
        try:verify(reference(row),line)
        except Exception as error:raise AssertionError((i,row,line))from error
    controls=rejecting_controls()
    evidence={'actual_exit':0,'directed_mpfr_cases':len(rows),'rejecting_controls':controls,'mpfr_version':lib.mpfr_get_version().decode(),'precision':6000,'rows':rows,'outputs':lines}
    if args.json:args.json.write_text(json.dumps(evidence,sort_keys=True)+'\n')
    print('seventeen directed MPFR: passed',len(rows),'raw layout cases')
if __name__=='__main__':main()
