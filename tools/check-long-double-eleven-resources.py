#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
import argparse,gzip,hashlib,json,os,random,shlex,subprocess,sys,tarfile
if not __debug__ or sys.flags.optimize:raise SystemExit("long-double eleven resource checks require assertion-enabled Python")
from fractions import Fraction as F
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--work',type=Path,required=True);args=parser.parse_args();base=args.work;base.mkdir(parents=True,exist_ok=True);work=base/'primitive-build';work.mkdir(exist_ok=True);P=4352;r=random.Random(20261104);cases=[]
def rounded(n,d,up):return -((-n)//d) if up else n//d
edge=[0,1,2,3,(1<<32)-1,1<<32,(1<<P)-1,1<<P,(1<<P)+1,(1<<(P+14))-1,1<<(P+14)]
for _ in range(80):edge.append(r.getrandbits(r.randrange(1,P+21)))
for magnitude in edge:
 for sign in (-1,1):
  a=magnitude*sign
  b=r.choice(edge)*(1 if r.randrange(2) else -1)
  if abs(a+b).bit_length()<=P+64:cases.append((0,0,0,a,b,a+b))
  for up in (0,1):
   cases.append((1,up,0,a,b,rounded(a*b,1<<P,up)))
   divisor=(1<<P)+r.getrandbits(P-1)
   cases.append((2,up,0,a,divisor,rounded(a*(1<<P),divisor,up)))
   divisor=r.choice([1,3,(1<<32)-1,(1<<P)-1])
   if (abs(a)*(1<<P)//divisor).bit_length()<=P+63:cases.append((2,up,0,a,divisor,rounded(a*(1<<P),divisor,up)))
   shift=r.choice([-5000,-4352,-33,-1,0,1,31,40])
   if shift<=0 or abs(a).bit_length()+shift<=P+64:
    expected=rounded(a,1<<-shift,up)if shift<0 else a<<shift;cases.append((3,up,shift,a,0,expected))
for value in edge:cases.append((0,0,0,value,-value,0))
# Explicit sticky/carry/sign boundaries.
for up in (0,1):
 for sign in (-1,1):
  a=sign*((1<<P)-1);b=(1<<P)+1;cases.append((1,up,0,a,b,rounded(a*b,1<<P,up)))
cc=shlex.split(os.environ.get('LONG_DOUBLE_ELEVEN_CC','cc'));flags=shlex.split(os.environ.get('LONG_DOUBLE_ELEVEN_FLAGS','-O2 -Iinclude'));cmd=cc+flags+['-fno-lto','-ffp-contract=off','tests/long_double_eleven_primitives.c','-lm','-o',str(work/'probe')]
code=subprocess.run(cmd,capture_output=True,text=True);(base/'primitive-compile.log').write_text(code.stdout+code.stderr);assert code.returncode==0
payload=''.join(f'{op} {up} {shift} {int(a<0)} {int(b<0)} {abs(a):x} {abs(b):x}\n'for op,up,shift,a,b,_ in cases)
p=subprocess.run([str(work/'probe')],input=payload,capture_output=True,text=True,timeout=120);assert p.returncode==0
lines=p.stdout.splitlines();assert len(lines)==len(cases)
for row,line in zip(cases,lines,strict=True):
 sign,hexvalue=line.split();actual=(-1 if int(sign) else 1)*int(hexvalue,16);assert actual==row[-1],(row,actual)
 if actual==0:assert int(sign)==0
source_sha={str(path):hashlib.sha256(path.read_bytes()).hexdigest()for path in Path('src/elementary').glob('long_double_eleven*')}
status={'actual_exit':0,'exact_integer_directed_cases':len(cases),'seed':20261104,'source_sha256':source_sha}
archive=base/'primitive-build.tar.gz';hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in work.iterdir()if p.is_file()}
with tarfile.open(archive,'w:gz')as tar:tar.add(work,arcname=work.name)
with gzip.open(archive,'rb')as stream:
 while stream.read(1048576):pass
with tarfile.open(archive)as tar:assert{Path(m.name).name:hashlib.sha256(tar.extractfile(m).read()).hexdigest()for m in tar if m.isfile()}==hashes
import shutil;shutil.rmtree(work);status['verified_artifacts']=len(hashes);status['pruned']=True
(base/'primitive-status.json').write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(status))

if sys.platform!='linux':
 print('UNSUPPORTED: guarded two-MiB pthread stack regression requires Linux mmap/pthread stack semantics; primitive calibration passed')
else:
 stack=base/'stack-build';stack.mkdir(exist_ok=True)
 for level in ('O0','O2'):
  obj=stack/(level+'.o');binary=stack/level
  for command in (cc+flags+['-'+level,'-fno-lto','-fstack-usage','-c','src/elementary/long_double_eleven.c','-o',str(obj)],cc+flags+['-'+level,'-fno-lto','tests/long_double_eleven_stack.c',str(obj),'-pthread','-lm','-o',str(binary)]):
   p=subprocess.run(command,capture_output=True,text=True,timeout=60)
   (stack/(level+'-compile.log')).write_text(p.stdout+p.stderr)
   if p.returncode:raise RuntimeError('guarded stack compilation failed '+p.stderr)
  result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=120)
  (stack/(level+'-run.log')).write_text(result.stdout+result.stderr)
  if result.returncode:raise RuntimeError('two-MiB guarded stack regression failed '+str(result.returncode))
 print('2 MiB usable guarded pthread stacks: O0 and O2 pass')
