#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Container-free pinned references, actual-neighbor numerical/state checks.

No host math library supplies expected results. Ordinary finite comparisons
accept the one-local-ULP contract; exact identities/domains/flags remain exact.
"""
import argparse,copy,hashlib,importlib.util,json,os,re,subprocess,sys,tempfile,uuid
from fractions import Fraction as F
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('seventeen corpus checks require assertion-enabled Python')
sys.path.insert(0,str(Path(__file__).resolve().parent))
import long_double_seventeen_cases as c
from long_double_seventeen_corpus_io import write_new
z=importlib.util.spec_from_file_location('seventeen_root_io',Path(__file__).with_name('check-long-double-seventeen-roots.py'))
roots=importlib.util.module_from_spec(z);z.loader.exec_module(roots)
NAME='long-double-seventeen.json'
REFERENCE_SHA256='d2f40112fde109d21d334c24a4c0e80107e8b64a000c9094c163a750ebaa7e75'
MAX_BYTES=4*1024*1024
CONSTANTS_SHA256='b36b197d33f3edcae8478b3bcd2feeb85589455e5233c2afe237dbe82bb56e12'
HEX=re.compile(r'(?:0|[1-9a-f][0-9a-f]*|-[1-9a-f][0-9a-f]*)\Z')
class Rejected(RuntimeError):pass
def need(condition,message):
 if not condition:raise Rejected(message)
def canonical(data):return(json.dumps(data,sort_keys=True,separators=(',',':'))+'\n').encode()
def bounds(value):
 need(type(value)is list and len(value)==3,'reference enclosure schema')
 lo,hi,e=value
 need(all(type(v)is str and len(v)<=578 and HEX.fullmatch(v)for v in(lo,hi)),'bounded canonical enclosure integers')
 a,bb=int(lo,16),int(hi,16)
 need(type(e)is int and -1000000<=e<=1000000,'bounded reference exponent')
 need(a<=bb and bb-a<=2 and max(abs(a),abs(bb)).bit_length()in(2304,2305),'normalized reference enclosure')
 need(a>0 or bb<0,'nonzero reference sign enclosure')
 return c.b.scale(a,e),c.b.scale(bb,e)
def check_constants(path=None):
 path=Path(path)if path is not None else Path(__file__).resolve().parents[1]/'src/elementary/long_double_seventeen_constants.h'
 payload=roots.bounded_read(path,2*1024*1024)
 need(hashlib.sha256(payload).hexdigest()==CONSTANTS_SHA256,'constant header SHA256 mismatch')

def validate(data):
 need(type(data)is dict and set(data)=={'schema','oracle','mpfr_precision','independent_min_precision','bound_bits','population_sha256','cells'},'reference manifest schema')
 for key,value in{'schema':1,'oracle':c.PIN,'mpfr_precision':4096,'independent_min_precision':8192,'bound_bits':2304}.items():need(type(data[key])is type(value)and data[key]==value,'fixed reference provenance '+key)
 rows=c.population();cells=data['cells'];need(type(cells)is list and len(cells)==len(rows),'complete independent population count')
 observed=[];ordinary=exact=0
 for cell in cells:
  need(type(cell)is dict and set(cell)=={'input','reference'},'reference cell schema')
  row=cell['input'];need(type(row)is list and len(row)==7 and type(row[0])is str and len(row[0])<=96 and all(type(v)is int for v in row[1:]),'bounded raw input schema')
  _,fmt,op,ah,al,bh,bl=row
  need(fmt in c.FORMATS and 0<=op<17 and all(0<=v<(1<<64)for v in(ah,al,bh,bl)),'raw input integer bounds')
  need((fmt!=64 or not(al|bl))and(fmt!=80 or ah<1<<16 and bh<1<<16),'reserved input bits')
  need(op==6 or not(bh|bl),'unary operand padding')
  observed.append(row)
  ref=cell['reference'];direct=c.special(row)
  if direct is not None and 'tiny'in direct:
   need(type(ref)is dict and set(ref)=={'tiny'}and type(ref['tiny'])is list and len(ref['tiny'])==2 and all(type(v)is int for v in ref['tiny'])and ref==direct,'exact tiny range witness');ordinary+=1
  elif direct is not None:
   need(type(ref)is dict and set(ref)=={'exact'}and type(ref['exact'])is list and len(ref['exact'])==3,'exact reference schema')
   need(all(type(v)is str and re.fullmatch('[0-9a-f]{16}',v)for v in ref['exact'][:2])and type(ref['exact'][2])is int and 0<=ref['exact'][2]<=31,'exact reference encoding')
   need(ref==direct,'independent exact special contract');exact+=1
  else:
   need(type(ref)is dict and set(ref)=={'interval','sign','range','independent_precision'},'ordinary reference schema')
   lo,hi=bounds(ref['interval'])
   need(type(ref['sign'])is int and ref['sign']in(0,1)and ref['sign']==int(hi<0),'ordinary reference sign')
   need(type(ref['independent_precision'])is int and 8192<=ref['independent_precision']<=1000000,'independent precision provenance')
   need(ref['range']in('finite','edge','overflow'),'ordinary range classification')
   if ref['range']=='overflow':need(min(abs(lo),abs(hi))>=2*c.overflow_threshold(fmt)-c.finite_limit(fmt),'overflow reference range')
   elif ref['range']=='finite':need(max(abs(lo),abs(hi))<=c.finite_limit(fmt),'finite reference range')
   else:need(max(abs(lo),abs(hi))>c.finite_limit(fmt)and min(abs(lo),abs(hi))<2*c.overflow_threshold(fmt)-c.finite_limit(fmt),'edge reference range')
   # Exact factorials independently constrain their intervals without imposing
   # exact output/rounding: these ordinary calls still addIX by contract.
   kind,_,_,x=c.b.decode(fmt,(ah,al))
   if op==15 and kind=='finite'and x.denominator==1 and 1<x<=4:
    import math
    need(lo<=F(math.factorial(int(x)-1))<=hi,'exact factorial reference enclosure')
   ordinary+=1
 need(observed==rows,'independent input population sequence')
 expected_sha=hashlib.sha256(canonical(rows)).hexdigest();need(data['population_sha256']==expected_sha,'independent population provenance hash')
 return{'cells':len(cells),'ordinary':ordinary,'exact_specials':exact,'formats':4,'apis':17}
def load(directory):
 payload=roots.bounded_read(directory/NAME,MAX_BYTES);pin=roots.bounded_read(directory/(NAME+'.sha256'),65)
 need(pin==(REFERENCE_SHA256+'\n').encode(),'reference source/hash pin mismatch')
 need(hashlib.sha256(payload).hexdigest()==REFERENCE_SHA256,'reference payload SHA256 mismatch')
 data=json.loads(payload,parse_constant=lambda _:(_ for _ in()).throw(Rejected('nonfinite reference JSON')))
 need(canonical(data)==payload,'canonical reference JSON')
 return data,validate(data)
def result_fields(line):
 fields=line.split();need(len(fields)==6,'probe result field count')
 try:
  need(all(len(v)==16 and re.fullmatch('[0-9a-f]{16}',v)for v in fields[:2]),'probe raw result encoding')
  values=(int(fields[0],16),int(fields[1],16),*map(int,fields[2:]))
  need(0<=values[2]<=31 and 0<=values[5]<=31,'bounded exception masks')
  return values
 except ValueError as error:raise Rejected('probe result syntax')from error
def verify(cell,line,incoming=0):
 fmt=cell['input'][1];ah,al,flags,err,controls,entry=result_fields(line)
 need(err==173,'errno preservation');need(controls==1,'floating control preservation')
 need((entry&incoming)==incoming and(incoming or not entry),'requested incoming flags')
 need((fmt!=64 or al==0)and(fmt!=80 or ah<1<<16),'reserved output bits')
 ref=cell['reference'];actual=(ah,al)
 if 'exact'in ref:
  expected=ref['exact'];need(actual==(int(expected[0],16),int(expected[1],16)),'exact special result')
  required=expected[2]
 elif ref.get('range')=='overflow':
  need(actual==c.b.pack(fmt,'inf',ref['sign'],F(0)),'range overflow result');required=20
 else:
  if'tiny'in ref:
   e,wanted_sign=ref['tiny'];lo,hi=(c.b.scale(-1,e),F(0))if wanted_sign else(F(0),c.b.scale(1,e))
  else:lo,hi=bounds(ref['interval']);wanted_sign=ref['sign']
  kind,sign,invalid,value=c.b.decode(fmt,actual)
  need(not invalid and sign==wanted_sign,'ordinary result classification/sign')
  if kind=='inf':
   need(ref.get('range')=='edge'and(hi<=-c.finite_limit(fmt)if sign else lo>=c.finite_limit(fmt)),'overflow edge enclosure')
   need(actual==c.b.pack(fmt,'inf',sign,F(0)),'canonical infinite result encoding');required=20
  else:
   need(kind=='finite','ordinary finite classification')
   need(actual==c.b.pack(fmt,'finite',sign,value),'canonical finite result encoding')
   if'/negative-root'in cell['input'][0]:need(bool(value),'nonzero root-neighbor result')
   before=c.b.decode(fmt,c.s.neighbor(fmt,value,-1));after=c.b.decode(fmt,c.s.neighbor(fmt,value,1))
   virtual=2*c.overflow_threshold(fmt)-c.finite_limit(fmt)
   lower=before[3]if before[0]=='finite'else -virtual
   upper=after[3]if after[0]=='finite'else virtual
   need(lower<=lo and hi<=upper,'ordinary actual-neighbor enclosure')
   if fmt==106:
    if before[0]=='finite':c.s.dd_no_interior(before[3],value)
    if after[0]=='finite':c.s.dd_no_interior(value,after[3])
   tiny=abs(value)<c.b.scale(1,-969 if fmt==106 else-1022 if fmt==64 else-16382)
   required=12 if tiny else 4
 need(flags==(required|entry),'exception flags (including incoming flags)')
def same_output(first,second):
 need(result_fields(first)[:2]==result_fields(second)[:2],'mode-invariant numerical output')

def invoke(probe,rows,timeout=1800):
 payload=''.join(' '.join(format(v,'x')for v in r)+'\n'for r in rows)
 try:result=subprocess.run([str(probe.resolve())],input=payload,text=True,capture_output=True,timeout=timeout)
 except subprocess.TimeoutExpired as error:raise Rejected('probe timeout (not numerical detection)')from error
 if os.environ.get('LONG_DOUBLE_SEVENTEEN_EVIDENCE'):
  evidence=Path(os.environ['LONG_DOUBLE_SEVENTEEN_EVIDENCE']);evidence.mkdir(parents=True,exist_ok=True)
  (evidence/('probe-'+uuid.uuid4().hex+'.json')).write_text(json.dumps({'rows':rows,'actual_exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr},sort_keys=True)+'\n')
 need(result.returncode==0,'probe execution failed: '+str(result.returncode)+' after '+str(max(0,len(result.stdout.splitlines())-1))+' rows; '+result.stderr)
 lines=result.stdout.splitlines();need(lines and lines[0].startswith('native '),'probe native-format header')
 header=lines[0].split();native=int(header[1]);mask=int(header[header.index('mxcsr-mask')+1],16)
 need(len(lines)==len(rows)+1,'probe output row count')
 return native,mask,lines[1:]
def check(probe,data,state_repetitions=24,native_only=False):
 # Header is queried separately so capabilities never come from manifest.
 native,mask,_=invoke(probe,[[64,0,0,0,0,0,0,0,0,0]])
 pcs=(0,2,3)if native==80 else(0,);pc=pcs[-1]
 cells=data['cells'];rows=[];expected=[]
 if not native_only:
  for cell in cells:rows.append([*cell['input'][1:],0,pc,0,0]);expected.append(cell)
 native_cells=[cell for cell in cells if cell['input'][1]==native]
 for cell in native_cells:rows.append([0,*cell['input'][2:],0,pc,0,0]);expected.append(cell)
 _,_,lines=invoke(probe,rows)
 baseline={}
 for cell,line in zip(expected,lines,strict=True):
  try:verify(cell,line)
  except Rejected as error:raise Rejected(str(error)+'; cell='+cell['input'][0]+'; result='+line)from error
  key=tuple(cell['input'][1:])
  if key in baseline:same_output(baseline[key],line)
  else:baseline[key]=line
 profiles=[0]+([1,2]if mask&0x8040==0x8040 else[])+([3]if mask&0x8000 else[])
 states=[];chosen=[];seeds=(0,1,2,4,8,16)
 if state_repetitions:
  for op in range(17):
   cell=next(v for v in native_cells if v['input'][2]==op and v['input'][0].endswith('/ordinary'))
   need('interval'in cell['reference']and cell['reference']['range']=='finite','ordinary nonidentity state representative')
   for index in range(state_repetitions):
    profile=profiles[(index//(12 if state_repetitions==48 else 6))%len(profiles)];seed=seeds[(index//4+index//24)%6]
    states.append([0,*cell['input'][2:],index%4,pcs[index%len(pcs)],seed,profile]);chosen.append((cell,seed))
  _,_,lines=invoke(probe,states)
  for(cell,seed),line in zip(chosen,lines,strict=True):
   try:
    verify(cell,line,seed);same_output(baseline[tuple(cell['input'][1:])],line)
   except Rejected as error:raise Rejected(str(error)+'; state cell='+cell['input'][0]+'; result='+line)from error
 special_groups={}
 for cell in native_cells:
  ref=cell['reference'];tag=cell['input'][0];kind=None
  if'/quiet-nan'in tag:kind='quiet-nan'
  elif'/signaling-nan'in tag:kind='signaling-nan'
  elif'/malformed'in tag:kind='malformed'
  elif'exact'in ref and ref['exact'][2]==1:kind='domain'
  elif'exact'in ref and ref['exact'][2]==2:kind='pole'
  if kind:special_groups.setdefault((cell['input'][2],kind),cell)
 special_rows=[];special_expected=[];special_counts={}
 if state_repetitions:
  need({'quiet-nan','signaling-nan','domain','pole'}<={kind for _,kind in special_groups},'special early-return state coverage')
  if native in(80,106):need(any(kind=='malformed'for _,kind in special_groups),'malformed early-return state coverage')
  for index,((op,kind),cell)in enumerate(special_groups.items()):
   seed=(2,8,16)[index%3];special_counts[kind]=special_counts.get(kind,0)+1
   special_rows.append([0,*cell['input'][2:],1+index%3,pcs[index%len(pcs)],seed,profiles[-1]]);special_expected.append((cell,seed))
  _,_,lines=invoke(probe,special_rows)
  for(cell,seed),line in zip(special_expected,lines,strict=True):
   verify(cell,line,seed);same_output(baseline[tuple(cell['input'][1:])],line)
 # Targeted range/tininess witnesses are independent of candidate flags.
 # They cover every supported flush profile without a large state product.
 boundaries={};normal=c.b.scale(1,-969 if native==106 else -1022 if native==64 else -16382)
 for cell in native_cells:
  ref=cell['reference'];kind=None
  tag=cell['input'][0]
  if'/overflow-boundary'in tag:
   kind='overflow-edge'if ref.get('range')=='edge'else'overflow-finite-side'if ref.get('range')=='finite'else'overflow-transition-side'
  # Keep each immediate Gamma input direction: neighboring results can lie
  # in different independently known range/tininess classes.
  elif'/gamma-transition-'in tag:kind='gamma-'+tag.split('/gamma-transition-',1)[1]
  elif'tiny'in ref:kind='tiny'
  elif'interval'in ref:
   if ref['range']in('edge','overflow'):kind='overflow-edge'if ref['range']=='edge'else'far-overflow'
   else:
    lo,hi=bounds(ref['interval'])
    if max(abs(lo),abs(hi))<normal:kind='tiny'
    elif'/normal-boundary0'in cell['input'][0]:kind='normal-boundary'
  elif ref['exact'][2]==20:kind='far-overflow'
  if kind:boundaries.setdefault((cell['input'][2],kind),cell)
 boundary_rows=[];boundary_expected=[]
 if state_repetitions:
  need({'overflow-finite-side','overflow-transition-side','far-overflow'}<={kind for _,kind in boundaries},'separate overflow seam and far-range coverage')
  for cell in boundaries.values():
   for index,profile in enumerate(profiles):
    for seed in(0,2):
     boundary_rows.append([0,*cell['input'][2:],index%4,pcs[index%len(pcs)],seed,profile]);boundary_expected.append((cell,seed))
  if boundary_rows:
   _,_,lines=invoke(probe,boundary_rows)
   for(cell,seed),line in zip(boundary_expected,lines,strict=True):
    try:verify(cell,line,seed);same_output(baseline[tuple(cell['input'][1:])],line)
    except Rejected as error:raise Rejected(str(error)+'; boundary state cell='+cell['input'][0]+'; result='+line)from error
 boundary_counts={key:0 for key in('overflow-edge','overflow-finite-side','overflow-transition-side','far-overflow')}
 for(op,kind)in boundaries:boundary_counts[kind]=boundary_counts.get(kind,0)+1
 return{'raw_reference_rows':0 if native_only else len(cells),'native_public_wrapper_rows':len(native_cells),'ordinary_nonidentity_state_rows':len(states),'special_state_rows':len(special_rows),'special_state_kinds':special_counts,'boundary_state_rows':len(boundary_rows),'boundary_kinds':boundary_counts,'state_profiles':profiles}
def boundary_controls(data):
 def line(raw,flags):return f'{raw[0]:016x} {raw[1]:016x} {flags} 173 1 0'
 count=0
 # Repack the selected exact value independently; equal numerical sums do
 # not authenticate a DD component encoding or an extended80 exponent.
 gamma=next(v for v in data['cells']if v['input'][1:3]==[106,15]and c.b.decode(106,tuple(v['input'][3:5]))[3]==3)
 verify(gamma,line(c.raw(106,2),4))
 normal80=next(v for v in data['cells']if v['input'][1:3]==[80,0]and'/normal-boundary0'in v['input'][0])
 verify(normal80,line(c.raw(80,c.b.scale(1,-16382)),4))
 for cell,raw,flags in((gamma,(0x3ff0000000000000,0x3ff0000000000000),4),
                        (gamma,(0x4000000000000000,0x8000000000000000),4),
                        (normal80,(0,1<<63),4)):
  try:verify(cell,line(raw,flags))
  except Rejected as error:need('canonical finite result encoding'in str(error),'canonical encoding assertion');count+=1
  else:raise Rejected('noncanonical selected output accepted')
 cell=next(v for v in data['cells']if v['input'][1:3]==[64,0]and'/normal-boundary0'in v['input'][0])
 normal=c.raw(64,c.b.scale(1,-1022));subnormal=c.s.neighbor(64,c.b.scale(1,-1022),-1)
 verify(cell,line(normal,4));verify(cell,line(subnormal,12))
 for raw,flags in((normal,12),(subnormal,4)):
  try:verify(cell,line(raw,flags))
  except Rejected as error:need('exception flags'in str(error),'selected tininess assertion');count+=1
  else:raise Rejected('wrong selected-result tininess flags accepted')
 tiny=next(v for v in data['cells']if v['input'][1:3]==[64,0]and v['input'][0].endswith('/minimum-subnormal'))
 zero=line(c.raw(64,0),12);small=line(c.raw(64,c.b.scale(1,-1074)),12)
 verify(tiny,zero);verify(tiny,small)
 try:same_output(zero,small)
 except Rejected as error:need('mode-invariant'in str(error),'mode invariance assertion');count+=1
 else:raise Rejected('mode-dependent adjacent valid result accepted')
 # Exact rational contract witness at a virtual overflow edge. This tests
 # verifier semantics only; production reference values remain oracle-only.
 limit=c.finite_limit(64);gap=2*(c.overflow_threshold(64)-limit);value=limit+gap/4;e=c.b.exponent(value)-2303;integer=int(value/c.b.scale(1,e))
 edge={'input':['synthetic-overflow-policy',64,0,0,0,0,0],'reference':{'interval':[format(integer,'x'),format(integer,'x'),e],'sign':0,'range':'edge','independent_precision':8192}}
 maximum=c.raw(64,limit);infinity=c.b.pack(64,'inf',0,F(0))
 verify(edge,line(maximum,4));verify(edge,line(infinity,20))
 for raw,flags in((maximum,20),(infinity,4)):
  try:verify(edge,line(raw,flags))
  except Rejected as error:need('exception flags'in str(error),'selected overflow flags assertion');count+=1
  else:raise Rejected('wrong selected overflow flags accepted')
 limit=c.finite_limit(106);gap=2*(c.overflow_threshold(106)-limit);value=limit+gap/4;e=c.b.exponent(value)-2303;integer=int(value/c.b.scale(1,e))
 dd_edge={'input':['synthetic-DD-edge-encoding',106,0,0,0,0,0],'reference':{'interval':[format(integer,'x'),format(integer,'x'),e],'sign':0,'range':'edge','independent_precision':8192}}
 verify(dd_edge,line(c.b.pack(106,'inf',0,F(0)),20))
 try:verify(dd_edge,line((0x7ff0000000000000,0x8000000000000000),20))
 except Rejected as error:need('canonical infinite result encoding'in str(error),'canonical edge infinity assertion');count+=1
 else:raise Rejected('noncanonical DD edge infinity accepted')
 return count

def loader_controls(directory):
 data,_=load(directory);count=boundary_controls(data)
 def reject(bad,message):
  nonlocal count
  try:validate(bad)
  except Rejected as error:need(message in str(error),'unintended loader control assertion '+str(error));count+=1
  else:raise Rejected('corrupt manifest accepted')
 bad=copy.deepcopy(data);bad['cells'].pop();reject(bad,'population count')
 bad=copy.deepcopy(data);bad['cells'][1]=bad['cells'][0];reject(bad,'input population')
 bad=copy.deepcopy(data);bad['cells'][0]['input'][4]=1;reject(bad,'reserved input bits')
 bad=copy.deepcopy(data);bad['cells'][0]['input'][5]=1;reject(bad,'unary operand padding')
 bad=copy.deepcopy(data);idx=next(i for i,v in enumerate(bad['cells'])if v['input'][1]==80);bad['cells'][idx]['input'][3]|=1<<16;reject(bad,'reserved input bits')
 bad=copy.deepcopy(data);bad['oracle']='untrusted';reject(bad,'provenance')
 bad=copy.deepcopy(data);idx=next(i for i,v in enumerate(bad['cells'])if 'exact'in v['reference']);bad['cells'][idx]['reference']['exact'][2]^=1;reject(bad,'exact special contract')
 from unittest.mock import patch
 import types
 with tempfile.TemporaryDirectory(prefix='seventeen-corpus-controls-')as name:
  work=Path(name);payload=(directory/NAME).read_bytes();pin=(directory/(NAME+'.sha256')).read_bytes()
  write_new(work/NAME,payload);write_new(work/(NAME+'.sha256'),pin);load(work)
  changed=canonical({**data,'schema':2});(work/NAME).write_bytes(changed);(work/(NAME+'.sha256')).write_text(hashlib.sha256(changed).hexdigest()+'\n')
  try:load(work)
  except Rejected as error:need('source/hash pin'in str(error),'repin assertion');count+=1
  else:raise Rejected('repinning accepted')
  need((work/NAME).read_bytes()==changed,'loader repaired corruption')
  (work/NAME).write_bytes(payload);(work/(NAME+'.sha256')).write_bytes(pin)
  corrupt=b'['+payload[1:];(work/NAME).write_bytes(corrupt)
  try:load(work)
  except Rejected as error:need('payload SHA256'in str(error),'payload corruption assertion');count+=1
  else:raise Rejected('corrupt payload accepted')
  need((work/NAME).read_bytes()==corrupt,'corrupt payload repaired')
  (work/NAME).unlink()
  try:load(work)
  except FileNotFoundError:count+=1
  else:raise Rejected('missing immutable corpus accepted')
  need(not(work/NAME).exists(),'missing corpus repaired')
  (work/NAME).write_bytes(payload)
  constant=Path(__file__).resolve().parents[1]/'src/elementary/long_double_seventeen_constants.h'
  corrupt=constant.read_bytes()+b' '
  (work/'constants.h').write_bytes(corrupt)
  try:check_constants(work/'constants.h')
  except Rejected as error:need('constant header SHA256'in str(error),'constant authentication assertion');count+=1
  else:raise Rejected('corrupt constant header accepted')
  child=subprocess.run([sys.executable,'-O',str(Path(__file__).resolve()),'--directory',str(work),'--prepare'],capture_output=True,text=True,timeout=30)
  need(child.returncode!=0 and 'assertion-enabled'in child.stdout+child.stderr,'optimized Python rejection assertion');count+=1
  real_read=roots.os.read
  def swapped(fd,size):
   if not swapped.done:
    swapped.done=True;(work/'replacement').write_bytes(b'corrupt replacement');os.replace(work/'replacement',work/NAME)
   return real_read(fd,size)
  swapped.done=False
  with patch.object(roots.os,'read',side_effect=swapped):
   try:roots.bounded_read(work/NAME,MAX_BYTES)
   except ValueError as error:need(str(error)in('certificate changed during read','certificate path changed during read'),'atomic reader replacement assertion');count+=1
   else:raise Rejected('atomic reader replacement accepted')
  need((work/NAME).read_bytes()==b'corrupt replacement','atomic replacement repaired')
  (work/NAME).write_bytes(payload)
  def swapped_write(fd,size):
   if not swapped_write.done:
    swapped_write.done=True;(work/'replacement').write_bytes(b'corrupt replacement');os.replace(work/'replacement',work/'atomic-output')
   return real_read(fd,size)
  swapped_write.done=False
  with patch('long_double_seventeen_corpus_io.os.read',side_effect=swapped_write):
   try:write_new(work/'atomic-output',payload)
   except OSError as error:need('path changed during verification'in str(error),'atomic writer replacement assertion');count+=1
   else:raise Rejected('atomic writer replacement accepted')
  need((work/'atomic-output').read_bytes()==b'corrupt replacement','atomic output repaired')
  original_stat=roots.os.fstat
  def raced(fd):
   value=original_stat(fd);raced.calls+=1
   return value if raced.calls==1 else types.SimpleNamespace(st_dev=value.st_dev,st_ino=value.st_ino,st_size=value.st_size,st_mtime_ns=value.st_mtime_ns+1,st_ctime_ns=value.st_ctime_ns)
  raced.calls=0
  with patch.object(roots.os,'fstat',side_effect=raced):
   try:roots.bounded_read(work/NAME,MAX_BYTES)
   except ValueError as error:need('changed during read'in str(error),'race assertion');count+=1
   else:raise Rejected('racing read accepted')
  with patch.object(roots.os,'read',return_value=b''):
   try:roots.bounded_read(work/NAME,MAX_BYTES)
   except ValueError as error:need('short read'in str(error),'short read assertion');count+=1
   else:raise Rejected('short read accepted')
  real_write=os.write
  def short(fd,value):
   short.calls+=1
   return real_write(fd,value[:7])if short.calls==1 else 0
  short.calls=0
  with patch('long_double_seventeen_corpus_io.os.write',side_effect=short):
   try:write_new(work/'short',payload)
   except OSError as error:need('short write'in str(error),'short write assertion');count+=1
   else:raise Rejected('short write accepted')
  saved=(work/'short').read_bytes()
  try:write_new(work/'short',payload)
  except FileExistsError:count+=1
  else:raise Rejected('short output repaired')
  need((work/'short').read_bytes()==saved,'short output changed')
 return count

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--directory',type=Path,default=Path('tests/corpus'));ap.add_argument('--probe',type=Path);ap.add_argument('--prepare',action='store_true');ap.add_argument('--controls',action='store_true');ap.add_argument('--state-repetitions',type=int,default=24);ap.add_argument('--native-only',action='store_true');args=ap.parse_args()
 need(args.state_repetitions in(0,24,48),'bounded supported state selection')
 check_constants()
 data,summary=load(args.directory)
 if args.controls:summary['loader_rejecting_controls']=loader_controls(args.directory)
 if args.probe:summary.update(check(args.probe,data,args.state_repetitions,args.native_only))
 print('seventeen authenticated references:',json.dumps(summary,sort_keys=True))
if __name__=='__main__':main()
