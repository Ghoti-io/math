#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Independent directed MPFR / mpmath seventeen-family reference output."""
import argparse,hashlib,json,os,platform,sys
from fractions import Fraction as F
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('seventeen corpus oracle requires assertion-enabled Python')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import long_double_seventeen_cases as c
from long_double_seventeen_corpus_io import write_new
import gmpy2 as g
import mpmath as mp
PREC=4096
BOUND_BITS=2304

def power(e):
 if type(e)is not int or abs(e)>1000000:raise RuntimeError('bounded reference exponent required before integer construction')
 return c.b.scale(1,e)
def encoded(value):return(json.dumps(value,sort_keys=True,separators=(',',':'))+'\n').encode()
def exact(v):return F(*(int(z)for z in v.as_integer_ratio()))
def operands(row):
 _,fmt,op,ah,al,bh,bl=row
 return c.b.decode(fmt,(ah,al)),c.b.decode(fmt,(bh,bl))
def mpfr_arg(value):
 kind,sign,_,x=value
 if kind=='inf':return g.mpfr('-inf'if sign else'inf')
 if not x and sign:return g.mpfr('-0')
 v=g.mpfr(g.mpq(x.numerator,x.denominator));assert exact(v)==x,'input projection lost a bit';return v

def independent(row,precision):
 _,_,op,*_=row;a,b=operands(row);k,sign,_,x=a;kb,sb,_,y=b
 with mp.workprec(precision):
  def argument(value):
   kind,sign,_,x=value
   return(-mp.inf if sign else mp.inf)if kind=='inf'else mp.mpf(x.numerator)/x.denominator
  xx,yy=argument(a),argument(b)
  if op==6 and(k=='inf'or kb=='inf'or not x or not y):
   if k=='inf':coefficient=F(1,4)if kb=='inf'and not sb else F(3,4)if kb=='inf'else F(1,2)
   elif kb=='inf':coefficient=F(1)if sb else F(0)
   elif not x:coefficient=F(1)if sb else F(0)
   else:coefficient=F(1,2)
   value=mp.pi*coefficient.numerator/coefficient.denominator
   if sign:value=-value
  elif op==6:value=mp.atan2(xx,yy)
  elif op==16:value=mp.re(mp.loggamma(xx))
  else:value=getattr(mp,c.NAMES[op])(xx)
  sign,mantissa,exponent,_=value._mpf_
  return power(exponent)*(-int(mantissa)if sign else int(mantissa))

def oracle(row):
 direct=c.special(row)
 if direct is not None:return direct
 _,fmt,op,*_=row;a,b=operands(row);bounds=[]
 for rounding in(g.RoundDown,g.RoundUp):
  with g.context(precision=PREC,round=rounding,emin=-1000000,emax=1000000):
   x,y=mpfr_arg(a),mpfr_arg(b)
   value=g.atan2(x,y)if op==6 else g.lgamma(x)[0]if op==16 else getattr(g,c.NAMES[op])(x)
   assert g.is_finite(value),'working exponent range exhausted'
   bounds.append(exact(value))
 lo,hi=bounds;assert lo<=hi and(lo>0 or hi<0),'ordinary result must have a certified nonzero sign'
 work=8192
 if op in(0,1,2):work+=max(0,c.b.exponent(a[3]))
 while True:
  other=independent(row,work);pad=power(-7000)*max(abs(lo),abs(hi))
  if lo-pad<=other<=hi+pad:break
  work*=2
 top=c.b.exponent(max(abs(lo),abs(hi)));e=top-BOUND_BITS+1;unit=power(e)
 left=lo//unit;right=-((-hi)//unit)
 assert left<=right and right-left<=2
 sign=int(hi<0);magnitude=min(abs(lo),abs(hi))
 if magnitude>=2*c.overflow_threshold(fmt)-c.finite_limit(fmt):range_='overflow'
 elif max(abs(lo),abs(hi))<=c.finite_limit(fmt):range_='finite'
 else:range_='edge'
 return {'interval':[format(left,'x'),format(right,'x'),e],'sign':sign,'range':range_,'independent_precision':work}

def gamma_input_seeds():
 """Bounded inversion of log|Gamma|, never construction of huge Gamma."""
 seeds=[];witnesses=[]
 def log_bounds(value):
  result=[]
  for rounding in(g.RoundDown,g.RoundUp):
   with g.context(precision=4096,round=rounding):
    v=g.mpfr(g.mpq(value.numerator,value.denominator));result.append(exact(g.log(v)))
  return result
 for fmt in c.FORMATS:
  minimum=-1074 if fmt in(64,106)else-16445 if fmt==80 else-16494
  normal=-969 if fmt==106 else-1022 if fmt==64 else-16382
  jobs=[('overflow',c.finite_limit(fmt),None)]
  for tag,threshold in(('normal',power(normal)),('underflow',power(minimum-1))):
   n=0;upper=F(2)
   while upper>=threshold/4:
    n+=1;assert n<4096,'bounded negative Gamma pole search';upper*=F(2,2*n-1)
   for parity in(0,1):jobs.append((tag+'-sign'+str(parity),threshold,n if n%2==parity else n+1))
  for tag,threshold,n in jobs:
   tl,th=log_bounds(threshold);left,right=(F(2),F(20000))if n is None else(F(0),F(1,2))
   for iteration in range(4096):
    mid=(left+right)/2;x=mid if n is None else mid-n;values=[]
    for rounding in(g.RoundDown,g.RoundUp):
     with g.context(precision=4096,round=rounding):
      xx=g.mpfr(g.mpq(x.numerator,x.denominator));values.append(exact(g.lgamma(xx)[0]))
    if values[1]<tl:below=True
    elif values[0]>th:below=False
    else:raise ValueError('Gamma input seed directed comparison unresolved')
    if below==(n is None):left=mid
    else:right=mid
    lo,hi=(left,right)if n is None else(left-n,right-n)
    if n is not None and left==0:continue
    a=c.s.rounded(fmt,lo,int(lo<0));bb=c.s.rounded(fmt,hi,int(hi<0))
    if a==bb:break
   else:raise ValueError('bounded Gamma transition inversion did not terminate')
   with mp.workprec(8192):
    target=mp.log(mp.mpf(threshold.numerator)/threshold.denominator)
    independent=[mp.re(mp.loggamma(mp.mpf(v.numerator)/v.denominator))-target for v in(lo,hi)]
    assert independent[0]<0<independent[1]if n is None else independent[0]>0>independent[1],'independent Gamma input bracket'
   seeds.append((fmt,tag,a));witnesses.append({'format':fmt,'tag':tag,'pole':n,'bisections':iteration+1,'input_bracket':[str(lo),str(hi)],'seed':a})
 return seeds,witnesses

def derive():
 actual=f'{g.mpfr_version().lower()} gmpy2 {g.version()} mpmath {mp.__version__} python {platform.python_version()}'
 if actual!=c.PIN:raise SystemExit('required seventeen corpus oracle mismatch: '+actual)
 seeds,_=gamma_input_seeds();assert tuple(seeds)==c._GAMMA_SEEDS,'independent Gamma transition input recipes'
 rows=c.population();cells=[]
 for i,row in enumerate(rows):
  try:reference=oracle(row)
  except Exception as error:raise RuntimeError('oracle input '+repr(row))from error
  cells.append({'input':row,'reference':reference})
  if i%128==0:print('seventeen corpus reference',i,'of',len(rows),file=sys.stderr,flush=True)
 root_signs={}
 for cell in cells:
  identifier=cell['input'][0]
  if'/negative-root'in identifier:root_signs.setdefault(identifier.rsplit('-neighbor',1)[0],set()).add(cell['reference']['sign'])
 assert len(root_signs)==16 and all(v=={0,1}for v in root_signs.values()),'all-format root-neighbor sign/nonzero witnesses'
 return {'schema':1,'oracle':c.PIN,'mpfr_precision':PREC,'independent_min_precision':8192,'bound_bits':BOUND_BITS,'population_sha256':hashlib.sha256(encoded(rows)).hexdigest(),'cells':cells}

def verify_bytes(committed,fresh):
 if committed!=fresh:raise ValueError('independent seventeen reference mismatch (no repair performed)')

def oracle_controls(fresh):
 import copy,importlib.util,tempfile
 spec=importlib.util.spec_from_file_location('seventeen_oracle_control_loader',Path(__file__).resolve().parents[1]/'check-long-double-seventeen.py')
 checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
 def privately_repinned(data,expected=None):
  saved=checker.REFERENCE_SHA256;payload=encoded(data)
  try:
   checker.REFERENCE_SHA256=hashlib.sha256(payload).hexdigest()
   with tempfile.TemporaryDirectory(prefix='seventeen-oracle-repin-')as name:
    directory=Path(name);write_new(directory/checker.NAME,payload);write_new(directory/(checker.NAME+'.sha256'),(checker.REFERENCE_SHA256+'\n').encode())
    if expected:
     try:checker.load(directory)
     except checker.Rejected as error:assert expected in str(error)
     else:raise AssertionError('fully repinned semantic corruption accepted')
    else:return checker.load(directory)[0]
  finally:checker.REFERENCE_SHA256=saved
 index=next(i for i,cell in enumerate(fresh['cells'])if cell['input'][1:3]==[64,0]and cell['input'][0].endswith('/ordinary'))
 bad=copy.deepcopy(fresh);bad['cells'][index]['reference']['interval']=[format(1<<2303,'x'),format(1<<2303,'x'),-2303]
 loaded=privately_repinned(bad)
 try:verify_bytes(encoded(loaded),encoded(fresh))
 except ValueError as error:assert 'independent seventeen reference mismatch'in str(error)
 else:raise AssertionError('repinned numerical answer escaped independent oracle')
 bad=copy.deepcopy(fresh);row=bad['cells'][index]['input'];row[3:5]=list(c.raw(64,F(3,8)));bad['cells'][index]['reference']=oracle(row)
 bad['population_sha256']=hashlib.sha256(encoded([v['input']for v in bad['cells']])).hexdigest()
 privately_repinned(bad,'independent input population sequence')
 bad=copy.deepcopy(fresh);index=next(i for i,cell in enumerate(bad['cells'])if'exact'in cell['reference']);bad['cells'][index]['reference']['exact'][2]^=1
 privately_repinned(bad,'independent exact special contract')
 print('seventeen oracle controls: fully repinned wrong numerical answer, numerically valid input substitution and exact-special corruption reject',flush=True)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--verify',action='store_true');ap.add_argument('--controls',action='store_true');ap.add_argument('--input-seeds',action='store_true');args=ap.parse_args()
 if args.input_seeds:
  actual=f'{g.mpfr_version().lower()} gmpy2 {g.version()} mpmath {mp.__version__} python {platform.python_version()}'
  assert actual==c.PIN,'required input-seed oracle pin'
  seeds,witnesses=gamma_input_seeds();write_new(args.out,encoded({'oracle':actual,'seeds':seeds,'witnesses':witnesses}));return
 data=derive();payload=encoded(data)
 if args.verify:
  if not args.out.is_file():raise SystemExit('seventeen corpus missing (no repair performed)')
  verify_bytes(args.out.read_bytes(),payload)
 else:
  write_new(args.out,payload)
 if args.controls:oracle_controls(data)
 print('seventeen corpus:',len(json.loads(payload)['cells']),'independent cells; SHA256',hashlib.sha256(payload).hexdigest())
if __name__=='__main__':main()
