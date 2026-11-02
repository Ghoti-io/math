#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Complete-payload/population, public caller-state and closed ULP-cell gates."""
import sys
if sys.flags.optimize:
 raise SystemExit('remaining-fifteen: optimized Python execution is unsupported')
import argparse,hashlib,os,re,shlex,subprocess,tempfile,random
from pathlib import Path
from fractions import Fraction as F
from remaining_reference import SEED,NAMES,population,params,decode
PIN='344b928c5cd4800826c98360ae563f0b325796bb2c620b70507750f9c6d41b55'
TESTS={'LoadedRowsAndCallerState','NativeDirectionBeyondResultPrecision','ExactFusedCancellationAndTininess','CanonicalConstructorsAndControlPreservation','UnsupportedNativeEncodingIsInvalid','PreserveFlushToZeroAndDenormalControls','RawNativeAbiSignalingAndUnsupported','RawPseudoDenormalEquivalence','LgammaPreservesPlatformSigngam','ExactDyadicPowersAllCallerStates'}
def run(cmd,env=None,stdin=None):
 e={k:v for k,v in os.environ.items() if not k.startswith('GTEST_')};e.update(env or {})
 return subprocess.run([str(c) for c in cmd],input=stdin,capture_output=True,text=True,env=e,timeout=300)
def validate(directory,seed=SEED,count=128,canonical=True):
 if not(0<=seed<1<<64 and 0<=count<=2048):raise ValueError('requested seed/count outside bounds')
 if (directory/'remaining-fifteen.corpus').stat().st_size>16*1024*1024:raise ValueError('oversized payload')
 data=(directory/'remaining-fifteen.corpus').read_bytes()
 if len(data)>16*1024*1024 or b'\r' in data or not data.endswith(b'\n'):raise ValueError('noncanonical or oversized payload')
 if canonical and hashlib.sha256(data).hexdigest()!=PIN:raise ValueError('complete payload differs')
 if (directory/'remaining-fifteen.sha256').read_text()!=hashlib.sha256(data).hexdigest()+'  remaining-fifteen.corpus\n':raise ValueError('SHA differs')
 lines=data.decode('ascii').splitlines()
 if lines[:2]!=['# remaining-fifteen-v1 seed=%d count=%d MPFR-directed1200/2400 mpmath Fraction-FMA/MPFR5000'%(seed,count),'# name width mode x y z target required allowed residual-low residual-high; residual scale=2^30 ULP']:raise ValueError('metadata differs')
 expected=list(population(seed,count));rows=[l.split() for l in lines[2:]]
 if len(rows)!=len(expected):raise ValueError('population count differs')
 for fields,row in zip(rows,expected):
  name,w,mode,x,y,z=row
  if len(fields)!=11 or fields[:6]!=[name,str(w),str(mode),format(x,'016x'),format(y,'016x'),format(z,'016x')]:raise ValueError('population/order differs')
  if not re.fullmatch('[0-9a-f]{16}',fields[6]) or any(not re.fullmatch('-?[0-9]+',v) or len(v)>15 for v in fields[7:]):raise ValueError('target/flags/cell malformed')
 return data,rows

def probe(probe,directory,rows,log):
 r=run([probe,directory]);log.write_text(r.stdout+r.stderr)
 if r.returncode:raise ValueError('public probe failed: '+str(log))
 loaded=re.findall(r'remaining-fifteen: loaded (.+)',r.stderr)
 if loaded!=[str(directory/'remaining-fifteen.corpus')] or 'remaining-fifteen: %d rows;'%len(rows) not in r.stderr:raise ValueError('fresh path/count ignored')
 values=re.findall(r'^remaining-result (\d+) ([0-9a-f]{16}) (\d+)$',r.stdout,re.M)
 if len(values)!=len(rows):raise ValueError('omitted result output')
 maxerror=F()
 for i,(fields,output) in enumerate(zip(rows,values)):
  index,word,flags=output
  if int(index)!=i:raise ValueError('result index differs')
  name,w,mode,x,y,z,t,req,allow,lo,hi=fields;w=int(w);target=int(t,16);result=int(word,16);req=int(req);allow=int(allow)
  # Raw public probe measures all standard flag classes.
  if int(flags)&req!=req or int(flags)&~allow:raise ValueError('result flags differ')
  p,b,s,inf=params(w)
  if name.startswith(('fma','nexttoward','nan')) or target&(s-1)>=inf or (int(lo)==int(hi)==0):
   if result!=target:raise ValueError('exact result differs')
  else:
   if result&(s-1)>=inf:raise ValueError('finite result escaped')
   unit=F(2)**max(((target&(s-1))>>p)-b-p,1-b-p)
   # Closed target residual interval. Candidate must be within one ULP
   # using spacing of the true target's binade, including asymmetric cells.
   distance=(decode(result,w)-decode(target,w))/unit
   err=max(abs(distance-F(int(lo),1<<30)),abs(distance-F(int(hi),1<<30)))
   power=not ((target&(s-1))&((1<<p)-1)) and (target&(s-1))>1<<p
   towardzero=int(hi)>0 if target&s else int(lo)<0
   limit=F(1,2) if power and towardzero else F(1)
   err/=limit
   if err>1:raise ValueError('closed ULP cell exceeded at row%d %s error=%s'%(i,name,err))
   maxerror=max(maxerror,err)
 hashes='\n'.join(l for l in r.stdout.splitlines() if l.startswith('math.'))+'\n'
 if len(hashes.splitlines())!=30:raise ValueError('all15 supplemental hashes missing')
 return hashes,float(maxerror)

def truncate256(value):
 if not value:return F(0)
 sign=-1 if value<0 else 1;a=abs(value);e=a.numerator.bit_length()-a.denominator.bit_length()
 if a<F(2)**e:e-=1
 unit=F(2)**(e-255);q=a/unit;return sign*(q.numerator//q.denominator)*unit

def raw_calibration(exe):
 rng=random.Random(27361);items=[]
 def item(sign,e,m):return sign,e,m
 def val(a):sg,e,m=a;return (-1 if sg else 1)*F(m)*F(2)**(e-255)
 one=item(0,0,1<<255)
 for a,b in [(one,item(1,-1,(1<<256)-1)),(one,item(1,-300,1<<255)),(one,item(0,-300,1<<255)),(item(0,0,(1<<255)+1),one)]:
  for op in range(4):items.append((op,a,b))
 for _ in range(256):
  a=item(rng.randrange(2),rng.randrange(-2400,2401),(1<<255)|rng.getrandbits(255));b=item(rng.randrange(2),rng.randrange(-2400,2401),(1<<255)|rng.getrandbits(255))
  for op in range(4):items.append((op,a,b))
 def text(a):sg,e,m=a;return '%d %d '%(sg,e)+' '.join('%08x'%((m>>(32*i))&0xffffffff) for i in range(7,-1,-1))
 r=run([exe,'--raw'],stdin=''.join('%d %s %s\n'%(op,text(a),text(b)) for op,a,b in items));assert r.returncode==0,r.stderr;lines=r.stdout.splitlines();assert len(lines)==len(items)
 for (op,a,b),line in zip(items,lines):
  av,bv=val(a),val(b);exact=[lambda:av+bv,lambda:av-bv,lambda:av*bv,lambda:av/bv][op]();fields=line.split();sg,e=map(int,fields[:2]);m=int(''.join(fields[2:]),16);assert val((sg,e,m))==truncate256(exact),(op,a,b,line)
 pack=[]
 for width in [64,32]:
  p,b,sign,inf=params(width)
  values=[F(0),F(1),F(2)**(1-b),F(2)**(1-b-p),F(2)**(-b-p),F(2)**(-b-p)+F(2)**(-b-p-100),F(2)**(1-b)-F(2)**(-b-p),F(2)**(b+1)-F(2)**(b-p),F(2)**(b+1)-F(2)**(b-p-1)]
  values += [F(1)+F(2)**(-p-1),F(1)+3*F(2)**(-p-1)]
  for v in values:
   for sg in [0,1]:
    if not v:a=(sg,0,0)
    else:
     e=v.numerator.bit_length()-v.denominator.bit_length()
     if v<F(2)**e:e-=1
     a=(sg,e,int(v*F(2)**(255-e)))
    pack.append((width,a))
  for _ in range(256):pack.append((width,(rng.randrange(2),rng.randrange(-1200,1101),(1<<255)|rng.getrandbits(255))))
 r=run([exe,'--raw'],stdin=''.join('5 %s %s\n'%(text(a),text((0,params(width)[0],0))) for width,a in pack));assert r.returncode==0,r.stderr;lines=r.stdout.splitlines();assert len(lines)==len(pack)
 from remaining_reference import encode
 for (width,a),line in zip(pack,lines):
  sign=1<<(width-1);wanted=encode(val(a),width)|(sign if a[0] else 0);assert int(line,16)==wanted,(width,a,line,hex(wanted))
 print('remaining-fifteen: %d raw256 exact truncation/cancellation and %d Fraction packing tie/range cases'%(len(items),len(pack)))

def calibrate_mp(exe):
 rng=random.Random(8162);cases=[]
 finite=lambda:rng.randrange(0x7ff0000000000000)|rng.choice([0,1<<63])
 for _ in range(512):
  x=finite();y=finite()
  for op in range(4):cases.append((op,x,y or 1))
  cases.append((4,x,rng.randrange(1,1<<32)))
 # Signed cancellation and normalization seams.
 for x in [1,0x0010000000000000,0x3ff0000000000000,0x7fefffffffffffff]:
  for y in [x,x+1,x-1,x|(1<<63)]:
   for op in range(4):
    if y&((1<<63)-1)<0x7ff0000000000000:cases.append((op,x,y or 1))
 r=run([exe],stdin=''.join('%d %x %x\n'%c for c in cases));assert r.returncode==0,r.stderr
 lines=r.stdout.splitlines();assert len(lines)==len(cases)
 for case,line in zip(cases,lines):
  op,x,y=case;a=decode(x,64);b=F(y) if op==4 else decode(y,64)
  exact=[lambda:a+b,lambda:a-b,lambda:a*b,lambda:a/b,lambda:a/b][op]()
  v=line.split();assert len(v)==10
  sign,e=map(int,v[:2]);mant=int(''.join(v[2:]),16);result=(-1 if sign else 1)*F(mant)*F(2)**(e-255)
  if not exact:assert result==0
  else:
   expected=truncate256(exact)
   assert result==expected,(case,line,exact,result)
   assert 1<<255<=mant<1<<256
 print('remaining-fifteen: %d exact Fraction MP calibration cases'%len(cases))

def inspect(objects):
 for obj in objects:
  undefined=run(['nm','-u',obj]).stdout
  if re.search(r'\b(?:fesetround|fesetenv|feupdateenv|feholdexcept)\b',undefined):raise ValueError('production control-writing reference')
  asm=run(['objdump','-d',obj]).stdout.lower()
  if not re.search(r'<[^>]+>:',asm):raise ValueError('empty object inspection')
  if re.search(r'\b(?:fldcw|ldmxcsr|vldmxcsr|frstor|fldenv|fxrstor\w*|xrstor\w*|sfpc|fscsr|fsrm|mtfs\w*)\b|\bmsr\s+fpcr|\bld\w*\s+[^\n]*%fsr',asm):raise ValueError('production control write')

def main():
 p=argparse.ArgumentParser();p.add_argument('--probe',type=Path,required=True);p.add_argument('--test',type=Path);p.add_argument('--mp-probe',type=Path);p.add_argument('--directory',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--fresh',action='store_true');p.add_argument('--seed',type=int);p.add_argument('--count',type=int);p.add_argument('--update-hash',action='store_true');a=p.parse_args()
 a.directory=a.directory.resolve();a.probe=a.probe.resolve();a.work.mkdir(parents=True,exist_ok=True)
 if a.fresh and (a.seed is None or a.count is None):raise ValueError('fresh requires seed/count')
 data,rows=validate(a.directory,a.seed if a.fresh else SEED,a.count if a.fresh else 128,not a.fresh)
 if a.mp_probe:
  calibrate_mp(a.mp_probe.resolve());raw_calibration(a.mp_probe.resolve())
 hashes,error=probe(a.probe,a.directory,rows,a.work/'public.log')
 hashfile=a.directory/'remaining-fifteen.hash'
 if a.update_hash:hashfile.write_text(hashes)
 elif not a.fresh and hashfile.read_text()!=hashes:raise ValueError('supplemental hashes differ')
 if a.test:
  r=run([a.test.resolve()],{'GMATH_REMAINING_CORPUS_DIR':str(a.directory)});(a.work/'unit.log').write_text(r.stdout+r.stderr)
  if r.returncode:raise ValueError('native unit failed')
  ran=re.findall(r'\[ RUN\s+\]\s+RemainingFifteen\.(\w+)',r.stdout)
  passed=set(re.findall(r'\[\s+OK\s+\]\s+RemainingFifteen\.(\w+)',r.stdout));skipped=set(re.findall(r'\[\s+SKIPPED\s+\]\s+RemainingFifteen\.(\w+)',r.stdout))
  if len(ran)!=10 or set(ran)!=TESTS or passed|skipped!=TESTS or skipped-{'UnsupportedNativeEncodingIsInvalid','PreserveFlushToZeroAndDenormalControls','RawNativeAbiSignalingAndUnsupported','RawPseudoDenormalEquivalence','LgammaPreservesPlatformSigngam'}:raise ValueError('native unit omitted required test')
  if 'RawNativeAbiSignalingAndUnsupported' in passed:
   symbols=run(['nm',a.test.resolve()]).stdout
   names=[line.split()[-1] for line in symbols.splitlines() if 'rp_raw_native_abi' in line]
   if len(names)!=1:raise ValueError('integer-only ABI caller symbol missing')
   asm=run(['objdump','-d','--disassemble='+names[0],a.test.resolve()]).stdout.lower()
   if not re.search(r'<[^>]+>:',asm) or re.search(r'\b(?:fldt|fstpt|fldl|fstpl|flds|fstps)\b',asm):raise ValueError('native ABI calibration caller used x87')
  loaded=re.findall(r'remaining-fifteen: loaded (.+)',r.stderr)
  if not loaded or any(path!=str(a.directory/'remaining-fifteen.corpus') for path in loaded) or 'remaining-fifteen: %d rows;'%len(rows) not in r.stderr:raise ValueError('native unit ignored requested path/count')
 if not a.fresh:
  attrs=run(['git','-C',Path(__file__).resolve().parents[1],'check-attr','text','eol','--','tests/corpus/remaining-fifteen.corpus','tests/corpus/remaining-fifteen.sha256','tests/corpus/remaining-fifteen.hash'])
  if attrs.returncode or len(attrs.stdout.splitlines())!=6 or any(not line.endswith((': text: set',': eol: lf')) for line in attrs.stdout.splitlines()):raise ValueError('new reference attributes must enforce canonical LF')
  inspect([Path(x) for x in shlex.split(os.environ.get('REMAINING_OBJECTS',''))])
  with tempfile.TemporaryDirectory(prefix='reference-',dir=a.work) as temp:
   bad=Path(temp);lines=data.decode().splitlines();changed=lines.copy();parts=changed[2].split();parts[6]='0000000000000002';changed[2]=' '.join(parts)
   variants={'empty':'','header':'# wrong\n'+ '\n'.join(lines[1:])+'\n','truncated':'\n'.join(lines[:-1])+'\n','bad-word':data.decode().replace('erf 64 0 0000000000000000','erf 64 0 '+'f'*80,1),'wrong-target':'\n'.join(changed)+'\n','missing-newline':data.decode().rstrip('\n')}
   for label,replacement in {'decimal-overflow':'9'*90,'negative-overflow':'-'+'9'*90}.items():
    f=lines[2].split();f[9]=replacement;variants[label]='\n'.join(lines[:2]+[' '.join(f)]+lines[3:])+'\n'
   for label,index,replacement in [('invalid-width',1,'16'),('invalid-mode',2,'4'),('wrong-name-width',0,'erff'),('unused-field',4,'0000000000000001'),('invalid-flags',7,'32'),('reversed-cell',9,'1')]:
    f=lines[2].split();f[index]=replacement;variants[label]='\n'.join(lines[:2]+[' '.join(f)]+lines[3:])+'\n'
   variants['header-seed-overflow']=data.decode().replace('seed=20261109','seed='+'9'*90,1)
   variants['header-count-overflow']=data.decode().replace('count=128','count='+'9'*90,1)
   for label,text in variants.items():
    (bad/'remaining-fifteen.corpus').write_text(text)
    r=run([a.probe,bad]);(a.work/('fault-'+label+'.log')).write_text(r.stdout+r.stderr)
    if label=='truncated':
     try:validate(bad)
     except (ValueError,FileNotFoundError):pass
     else:raise ValueError('truncation escaped complete payload gate')
    elif r.returncode!=1:raise ValueError('malformed/numerical reference defect failed outside intended assertion: '+label)
  with tempfile.TemporaryDirectory(prefix='rehash-',dir=a.work) as temp:
   bad=Path(temp);changed=data.decode().splitlines();fields=changed[6].split();fields[-1]=str(int(fields[-1])+1);changed[6]=' '.join(fields);changed=('\n'.join(changed)+'\n').encode();(bad/'remaining-fifteen.corpus').write_bytes(changed);(bad/'remaining-fifteen.sha256').write_text(hashlib.sha256(changed).hexdigest()+'  remaining-fifteen.corpus\n')
   try:validate(bad)
   except ValueError as e:
    if str(e)!='complete payload differs':raise
   else:raise ValueError('rehashed residual corruption escaped canonical independent pin')
 print(('remaining-fifteen: complete requested fresh population/SHA/path/count/public state; observed15 hashes' if a.fresh else 'remaining-fifteen: complete payload/population/path/count/all15 pinned hashes/public state')+' passed; maximum closed-cell error %.9g ULP'%error)
if __name__=='__main__':main()
