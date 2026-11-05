#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Reject malformed probe records and certify supported native state fixtures."""
import argparse,importlib.util,json,subprocess,sys
from fractions import Fraction
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('seventeen probe controls require assertion-enabled Python')
def invoke(path,payload):return subprocess.run([str(path.resolve())],input=payload,capture_output=True,timeout=60)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--state-probe',type=Path,required=True);ap.add_argument('--fault-directory',type=Path);ap.add_argument('--json',type=Path);args=ap.parse_args()
 valid=b'64 0 0 0 0 0\n';positive=invoke(args.probe,valid)
 assert positive.returncode==0 and positive.stdout==b'0000000000000000 0000000000000000 0 123\n','raw positive control'
 invalid=[b'',b'\n',b'64',b'64 0 0 0 0 0',b'64 0 0 0 0\n',b'64 0 0 0 0 0 0\n',b'64 -1 0 0 0 0\n',b'64 +0 0 0 0 0\n',b'64 17 0 0 0 0\n',b'65 0 0 0 0 0\n',b'64 0 10000000000000000 0 0 0\n',b'64 0 0 0 0 0\0\n',b'x'*513+b'\n',valid+b'64 0']
 for payload in invalid:assert invoke(args.probe,payload).returncode==2,('raw malformed accepted',payload)
 z=importlib.util.spec_from_file_location('probe_scale',Path(__file__).with_name('check-long-double-scale.py'));scale=importlib.util.module_from_spec(z);z.loader.exec_module(scale);base=scale.base
 first=invoke(args.state_probe,b'0 0 0 0 0 0 0 0 0 0\n');assert first.returncode==0,'state positive control'
 header=first.stdout.splitlines()[0].decode().split();native=int(header[1]);mask=int(header[header.index('mxcsr-mask')+1],16)
 one=base.pack(native,'finite',0,Fraction(1));zero=base.pack(native,'finite',1,Fraction(0));pzero=base.pack(native,'finite',0,Fraction(0))
 profiles=[0]+([1,2]if mask&0x8040==0x8040 else[])+([3]if mask&0x8000 else[])
 pcs=(0,2,3)if native==80 else(0,)
 rows=[];expected=[]
 for op in range(17):
  a=one if op in(4,11,15,16)else zero
  out=one if op in(1,8,14,15)else pzero if op in(4,11,16)else zero
  for rc in range(4):
   for pc in pcs:
    for profile in profiles:
     for seed in(0,1,2,4,8,16):rows.append([0,op,*a,*one,rc,pc,seed,profile]);expected.append(out)
 payload=''.join(' '.join(format(x,'x')for x in row)+'\n'for row in rows).encode()
 run=invoke(args.state_probe,payload);assert run.returncode==0,run.stderr
 lines=run.stdout.splitlines()[1:];assert len(lines)==len(rows)
 for row,want,line in zip(rows,expected,lines,strict=True):
  ah,al,flags,errno,controls,entry=line.split()
  assert(int(ah,16),int(al,16))==want,(row,line,want)
  assert int(flags)==int(entry) and(int(entry)&row[8])==row[8]and int(errno)==173 and int(controls)==1,(row,line)
 state_invalid=[b'',b'\n',b'0 0 0 0 0 0 0 0 0',b'0 0 0 0 0 0 0 0 0 0',b'0 0 0 0 0 0 0 0 0 4\n',b'0 0 0 0 0 0 0 1 0 0\n',b'0 0 0 0 0 0 0 0 0 0 extra\n',b'0 0 0 0 0 0 0 0 0 0\0\n',b'x'*513+b'\n']
 for payload in state_invalid:assert invoke(args.state_probe,payload).returncode==2,('state malformed accepted',payload)
 faults=0
 if args.fault_directory:
  # Positive controls above run first. Every compiled fault must reach its
  # intended setup assertion, including a false-success implementation.
  for name,payload,message in[
   ('clear',b'0 0 0 0 0 0 0 0 0 0\n',b'clear flags'),
   ('round',b'0 0 0 0 0 0 1 0 0 0\n',b'rounding mode'),
   ('raise',b'0 0 0 0 0 0 0 0 1 0\n',b'seed flags'),
   ('round-noop',b'0 0 0 0 0 0 1 0 0 0\n',b'rounding mode'),
   ('raise-noop',b'0 0 0 0 0 0 0 0 1 0\n',b'requested flags absent')]:
   result=invoke(args.fault_directory/name,payload);assert result.returncode==2 and message in result.stderr,(name,result.returncode,result.stderr);faults+=1
  unsupported=invoke(args.fault_directory/'no-sse',b'0 0 0 0 0 0 0 0 0 2\n')
  assert unsupported.returncode==3 and b'unsupported MXCSR'in unsupported.stderr,'unsupported SSE fixture accepted';faults+=1
 summary={'actual_exit':0,'raw_rejecting_records':len(invalid),'state_rejecting_records':len(state_invalid),'native_identity_state_rows':len(rows),'supported_profiles':profiles,'mxcsr_writable_mask':mask,'compiled_rejecting_controls':faults}
 if args.json:args.json.write_text(json.dumps(summary,sort_keys=True)+'\n')
 print('seventeen probe controls:',json.dumps(summary,sort_keys=True))
if __name__=='__main__':main()
