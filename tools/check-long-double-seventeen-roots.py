#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Container-free, authenticated lgamma root/grid reference certificate.

This checker validates pinned oracle data and exact rational consequences.
It never uses a host math implementation and never repairs missing/corrupt data.
See documentation/long-double-seventeen-roots.md for the analytic proof.
"""
import argparse,copy,hashlib,json,math,os,re,stat,subprocess,sys,tempfile
from fractions import Fraction as F
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('root certificates require assertion-enabled Python')
ROOTS_SHA256='6792ca3a3f7df59516b8ae42b90dff7185820b971632a0c2d1c79f41fb5c9e82'
PIN='mpfr 4.2.2 gmpy2 2.3.2 mpmath 1.4.1 python 3.14.7'
NAME='long-double-seventeen-roots.json'
MAX_BYTES=2*1024*1024
HEX=re.compile(r'(?:0|[1-9a-f][0-9a-f]*|-[1-9a-f][0-9a-f]*)\Z')

def power(e):return F(1<<e)if e>=0 else F(1,1<<-e)
def need(condition,message):
 if not condition:raise ValueError(message)
def canonical(data):return(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n').encode()
def bounded_read(path,maximum):
 descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  before=os.fstat(descriptor);need(stat.S_ISREG(before.st_mode)and 0<before.st_size<=maximum,'bounded regular certificate file required')
  data=b''
  while len(data)<=maximum:
   chunk=os.read(descriptor,min(65536,maximum+1-len(data)))
   if not chunk:break
   data+=chunk
  after=os.fstat(descriptor)
  need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'certificate changed during read')
  need(len(data)==before.st_size,'certificate short read')
  named=os.stat(path,follow_symlinks=False)
  need((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(named.st_dev,named.st_ino,named.st_size,named.st_mtime_ns,named.st_ctime_ns),'certificate path changed during read')
  return data
 finally:os.close(descriptor)
def integer(value,bits):
 need(type(value)is str and len(value)<=((bits+3)//4+1)and HEX.fullmatch(value),'canonical bounded hexadecimal integer required')
 out=int(value,16);need(abs(out).bit_length()<=bits,'hexadecimal integer bit bound');return out

def enclosure(value,expected_sign=None):
 need(type(value)is list and len(value)==3,'dyadic enclosure schema')
 lo=integer(value[0],65);hi=integer(value[1],65);e=value[2]
 need(type(e)is int and -8192<=e<=8192,'dyadic enclosure exponent bound')
 need(lo<=hi and hi-lo<=2 and (lo>0 or hi<0),'strict nonzero dyadic enclosure required')
 need(max(abs(lo),abs(hi)).bit_length()in(64,65),'normalized64-bit dyadic enclosure required')
 if expected_sign is not None:need(lo>0 if expected_sign>0 else hi<0,'enclosure sign certificate')
 return lo*power(e),hi*power(e)

def validate(data):
 keys={'cancellation_region','schema','oracle','mpfr_precision','mpmath_precision','mpmath_absolute_crosscheck_tolerance_exponent','distance_bits','grid_bits','roots','positive','minimum_nonzero_lgamma_exponent','cancellation_region_absolute_width_exponent','dd_relative_population_gap_exponent','relative_precision_reserve_bits'}
 need(type(data)is dict and set(data)==keys,'root registry schema keys')
 fixed={'cancellation_region':'negative[-256,-2] excluding poles; positive[1/2,3]','schema':1,'oracle':PIN,'mpfr_precision':4096,'mpmath_precision':8192,'mpmath_absolute_crosscheck_tolerance_exponent':-5800,'distance_bits':1152,'grid_bits':1074,'cancellation_region_absolute_width_exponent':-4100,'dd_relative_population_gap_exponent':-2098}
 for key,value in fixed.items():need(type(data[key])is type(value)and data[key]==value,'fixed root certificate contract '+key)
 roots=data['roots'];need(type(roots)is list and len(roots)==508,'complete508-root population required')
 population=[];magnitudes=[F(1,4)];unit=power(-1074)
 for row in roots:
  need(type(row)is dict and set(row)=={'n','side','distance','bracket_lgamma','grid_lgamma'},'root row schema')
  n,side=row['n'],row['side'];need(type(n)is int and 3<=n<=256 and side in('left','right'),'root index/side bound')
  need((n,side)not in population,'duplicate root index/side');population.append((n,side))
  need(type(row['distance'])is list and len(row['distance'])==2,'root distance schema')
  m=integer(row['distance'][0],1152);e=row['distance'][1]
  need(m.bit_length()==1152 and type(e)is int and -4096<=e<=-1152,'normalized1152-bit root distance required')
  low,high=m*power(e),(m+1)*power(e)
  need(0<low<high<F(1,2),'root bracket inside pole half-interval')
  residue_factor=math.factorial(n if side=='left'else n-1)
  need(F(1,2)<low*residue_factor<high*residue_factor<2,'pole residue scale sanity bound')
  signs=row['bracket_lgamma'];need(type(signs)is list and len(signs)==2,'root endpoint sign population')
  enclosure(signs[0],1);enclosure(signs[1],-1)
  pole=-n if side=='left'else 1-n;direction=1 if side=='left'else -1
  xlo,xhi=sorted((F(pole)+direction*low,F(pole)+direction*high))
  cell=xlo//unit;need(xhi//unit==cell and cell*unit<xlo<xhi<(cell+1)*unit,'root excluded from universal2^-1074 local lattice')
  grid=row['grid_lgamma'];need(type(grid)is list and len(grid)==2,'nearest lattice bound population')
  expected=(1,-1)if side=='left'else(-1,1)
  for j,index in enumerate((cell,cell+1)):
   x=index*unit
   if x.denominator==1 and x<=0:need(grid[j]is None,'integer pole must be explicitly excluded')
   else:
    need(grid[j]is not None,'omitted nearest finite lattice endpoint')
    lo,hi=enclosure(grid[j],expected[j]);magnitudes.append(lo if lo>0 else -hi)
 need(population==[(n,side)for n in range(3,257)for side in('left','right')],'ordered complete root index/side coverage')
 positive=data['positive'];need(type(positive)is list and len(positive)==4,'positive1/2 adjacent-grid population')
 for row,(integer_,direction)in zip(positive,[(n,d)for n in(1,2)for d in(-1,1)],strict=True):
  need(type(row)is dict and set(row)=={'integer','direction','lgamma'},'positive lattice row schema')
  need(type(row['integer'])is int and type(row['direction'])is int and(row['integer'],row['direction'])==(integer_,direction),'positive lattice index/direction')
  sign=-direction if integer_==1 else direction
  lo,hi=enclosure(row['lgamma'],sign);magnitudes.append(lo if lo>0 else -hi)
 minimum=min(magnitudes);G=0
 while minimum<=power(-G):G+=1
 need(type(data['minimum_nonzero_lgamma_exponent'])is int and data['minimum_nonzero_lgamma_exponent']==-G,'global minimum lgamma bound')
 reserve=4100-G-2098
 need(reserve>2 and type(data['relative_precision_reserve_bits'])is int and data['relative_precision_reserve_bits']==reserve,'4352-bit/Stirling relative precision reserve')
 # Exact rational range/root-count witnesses. The analytic identities and
 # convexity reducing all grid points to registry endpoints are documented.
 need(F(64*22,7*225)<1,'negative half-integer minimum witness')
 need(F(16,9)**2>3 and F(4,3)**4>3,'first negative intervals/positive outer range witnesses')
 need(F(4)*(1<<1073)/math.factorial(256)<power(-608),'representable negative outer-range gamma exclusion')
 return {'roots':508,'positive_grid_points':4,'minimum_nonzero_lgamma_exponent':-G,'relative_precision_reserve_bits':reserve,'nearest_finite_grid_enclosures':len(magnitudes)-1}

def load(directory):
 payload=bounded_read(directory/NAME,MAX_BYTES)
 pin=bounded_read(directory/(NAME+'.sha256'),65)
 need(pin==bytes(ROOTS_SHA256+'\n','ascii'),'pinned SHA256 file differs (repinning is not regeneration)')
 need(hashlib.sha256(payload).hexdigest()==ROOTS_SHA256,'pinned SHA256 payload mismatch')
 data=json.loads(payload,parse_constant=lambda value:(_ for _ in()).throw(ValueError('nonfinite JSON number')))
 need(canonical(data)==payload,'canonical JSON required')
 return data,validate(data)

def controls(directory):
 original,summary=load(directory);count=0
 def rejected(data,needle):
  nonlocal count
  try:validate(data)
  except(ValueError,TypeError)as error:need(needle in str(error),'control rejected at unintended assertion: '+str(error));count+=1
  else:raise ValueError('planted semantic corruption accepted')
 bad=copy.deepcopy(original);bad['roots'].pop();rejected(bad,'complete508-root')
 bad=copy.deepcopy(original);bad['roots'][1]=bad['roots'][0];rejected(bad,'duplicate root')
 bad=copy.deepcopy(original);bad['roots'][0]['bracket_lgamma'][0][0]='0';rejected(bad,'strict nonzero')
 bad=copy.deepcopy(original);bad['roots'][0]['grid_lgamma'][0]=None;rejected(bad,'omitted nearest finite')
 bad=copy.deepcopy(original);bad['relative_precision_reserve_bits']+=1;rejected(bad,'precision reserve')
 bad=copy.deepcopy(original);bad['roots'][0]['distance']=bad['roots'][4]['distance'];rejected(bad,'pole residue scale')
 with tempfile.TemporaryDirectory(prefix='gmath-seventeen-root-controls-')as name:
  work=Path(name);payload=(directory/NAME).read_bytes();pin=(directory/(NAME+'.sha256')).read_bytes()
  (work/NAME).write_bytes(payload);(work/(NAME+'.sha256')).write_bytes(pin);load(work)
  changed=canonical({**original,'schema':2})
  (work/NAME).write_bytes(changed)
  (work/(NAME+'.sha256')).write_text(hashlib.sha256(changed).hexdigest()+'\n')
  try:load(work)
  except ValueError as error:need('pinned SHA256 file' in str(error),'repinning control assertion');count+=1
  else:raise ValueError('repinning accepted')
  need((work/NAME).read_bytes()==changed,'loader repaired corrupt payload')
  (work/(NAME+'.sha256')).write_bytes(pin)
  try:load(work)
  except ValueError as error:need('payload mismatch'in str(error),'payload corruption control assertion');count+=1
  else:raise ValueError('corrupt payload accepted')
  (work/NAME).unlink()
  try:load(work)
  except FileNotFoundError:count+=1
  else:raise ValueError('missing registry accepted')
  (work/NAME).write_bytes(payload)
  child=subprocess.run([sys.executable,'-O',str(Path(__file__).resolve()),'--directory',str(work)],capture_output=True,text=True,timeout=30)
  need(child.returncode!=0 and 'assertion-enabled Python'in child.stderr+child.stdout,'optimized Python accepted or rejected at unintended assertion');count+=1
 return count

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--directory',type=Path,default=Path(__file__).resolve().parents[1]/'tests/corpus');ap.add_argument('--controls',action='store_true');args=ap.parse_args()
 _,summary=load(args.directory)
 if args.controls:summary['rejecting_controls']=controls(args.directory)
 print('seventeen root/grid certificates:',json.dumps(summary,sort_keys=True))
if __name__=='__main__':main()
