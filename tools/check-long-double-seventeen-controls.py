#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Compiled numerical/state/ABI rejecting controls after positive witnesses."""
import argparse,importlib.util,json,os,shlex,subprocess,sys,uuid
from pathlib import Path
if not __debug__ or sys.flags.optimize:raise SystemExit('seventeen compiled controls require assertion-enabled Python')
sys.path.insert(0,str(Path(__file__).resolve().parent))
z=importlib.util.spec_from_file_location('seventeen_controls_reference',Path(__file__).with_name('check-long-double-seventeen.py'))
m=importlib.util.module_from_spec(z);z.loader.exec_module(m)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--probe',type=Path,required=True);ap.add_argument('--raw-probe',type=Path,required=True);ap.add_argument('--caller-object',type=Path,required=True);ap.add_argument('--object',type=Path,required=True);ap.add_argument('--directory',type=Path,default=Path('tests/corpus'));ap.add_argument('--work',type=Path,required=True);args=ap.parse_args()
 work=args.work.resolve()/('run-'+uuid.uuid4().hex);work.mkdir(parents=True)
 compiler=shlex.split(os.environ.get('LONG_DOUBLE_SEVENTEEN_CC','cc'))
 flags=shlex.split(os.environ.get('LONG_DOUBLE_SEVENTEEN_FLAGS','-O2 -Iinclude'))+['-fno-lto','-ffp-contract=off','-Isrc/elementary']
 link=shlex.split(os.environ.get('LONG_DOUBLE_SEVENTEEN_LINK','-lm'))
 def run(command,label):
  result=subprocess.run(command,capture_output=True,text=True,timeout=180)
  (work/(label+'.log')).write_text(result.stdout+result.stderr)
  (work/(label+'.command.json')).write_text(json.dumps(command)+'\n')
  m.need(result.returncode==0,'control build/positive execution failed '+label)
  return result
 data,_=m.load(args.directory)
 native,_,_=m.invoke(args.probe,[[64,0,0,0,0,0,0,0,0,0]])
 cell=next(v for v in data['cells']if v['input'][1]==native and v['input'][2]==0 and v['input'][0].endswith('/ordinary'))
 pc=3 if native==80 else 0
 base_row=[0,*cell['input'][2:],0,pc,0,0]
 _,_,lines=m.invoke(args.probe,[base_row]);m.verify(cell,lines[0]);(work/'baseline-output.txt').write_text(lines[0]+'\n')
 seeded=[*base_row];seeded[8]=2
 _,_,lines=m.invoke(args.probe,[seeded]);m.verify(cell,lines[0],2)
 run([sys.executable,'tools/check-long-double-seventeen-abi.py','--object',str(args.object.resolve())],'baseline-abi')
 source=Path('src/elementary/long_double_seventeen.c').read_text()
 def build_fault(text,name):
  path=work/(name+'.c');obj=work/(name+'.o');probe=work/name;path.write_text(text)
  run([*compiler,*flags,'-c',str(path),'-o',str(obj)],name+'-compile')
  run([*compiler,'-fno-lto',str(args.caller_object.resolve()),str(obj),*link,'-o',str(probe)],name+'-link')
  return obj,probe
 anchor='  int zero=a.kind==LD_FINITE && ld_top(&a)<0,sign=a.sign;'
 m.need(source.count(anchor)==1,'numerical fault anchor')
 numerical=source.replace(anchor,'''  if(op==LDS17_SIN && a.kind==LD_FINITE && ld_top(&a)>=0) {
    ld_raw out=lds17_zero(fmt,a.sign);lds_flags(fmt,out,0,1,0);return out;
  }
'''+anchor)
 _,probe=build_fault(numerical,'numerical')
 _,_,lines=m.invoke(probe,[base_row]);(work/'numerical-output.txt').write_text(lines[0]+'\n') # Process must return normally.
 try:m.verify(cell,lines[0])
 except m.Rejected as error:m.need('ordinary actual-neighbor enclosure'in str(error),'numerical control rejected at unintended assertion');(work/'numerical-detection.log').write_text(str(error)+'\n')
 else:raise m.Rejected('compiled numerical fault accepted')
 anchor='  ld_raw b={0,0};if(y)b=ld_read(y);ld_write(out,lds17_run('
 m.need(source.count(anchor)==1,'state fault anchor')
 state=source.replace('#include <float.h>','#include <float.h>\n#include <fenv.h>').replace(anchor,'  (void)feclearexcept(FE_ALL_EXCEPT);\n'+anchor)
 _,probe=build_fault(state,'incoming-flags')
 _,_,lines=m.invoke(probe,[seeded]);(work/'state-output.txt').write_text(lines[0]+'\n')
 try:m.verify(cell,lines[0],2)
 except m.Rejected as error:m.need('exception flags'in str(error),'state control rejected at unintended assertion');(work/'state-detection.log').write_text(str(error)+'\n')
 else:raise m.Rejected('compiled state fault accepted')
 # A second numerical fault stays inside the accepted one-ULP cell but
 # changes its selected word with RC. Detection must be the invariance check.
 low,high=m.bounds(cell['reference']['interval']);value=m.c.b.decode(native,m.result_fields(lines[0])[:2])[3]
 # 'lines' above came from the flags fault, whose numerical value is unchanged.
 direction=1 if value<low else -1 if value>high else 1
 anchor='  ld_raw b={0,0};if(y)b=ld_read(y);ld_write(out,lds17_run(LD_NATIVE,op,ld_read(x),b));'
 m.need(source.count(anchor)==1,'mode numerical fault anchor')
 replacement=f"""  ld_raw b={{0,0}};if(y)b=ld_read(y);ld_raw value=lds17_run(LD_NATIVE,op,ld_read(x),b);
  if(op==LDS17_SIN && fegetround()==FE_UPWARD) {{ld_value decoded=ld_decode(LD_NATIVE,value);value=lde_neighbor(LD_NATIVE,&decoded,{direction});}}
  ld_write(out,value);"""
 mode=source.replace('#include <float.h>','#include <float.h>\n#include <fenv.h>').replace(anchor,replacement)
 _,probe=build_fault(mode,'mode-dependent-neighbor')
 upward=list(base_row);upward[6]=2
 _,_,mode_lines=m.invoke(probe,[base_row,upward]);(work/'mode-output.txt').write_text('\n'.join(mode_lines)+'\n')
 for item in mode_lines:m.verify(cell,item)
 try:m.same_output(*mode_lines)
 except m.Rejected as error:m.need('mode-invariant'in str(error),'mode control rejected at unintended assertion');(work/'mode-detection.log').write_text(str(error)+'\n')
 else:raise m.Rejected('compiled mode-dependent valid-neighbor fault accepted')
 header=subprocess.check_output([os.environ.get('OBJDUMP','objdump'),'-f',str(args.object.resolve())],text=True)
 if native==80 and 'architecture: i386'in header:
  abi=source.replace('LDS17_UNARY(gmath_sinl,0)','LDS17_UNARY(gmath_sinl,1)');message='native80 wrapper operand contract'
 else:
  abi=source+'\nstatic double __attribute__((used,noinline)) abi_fault(double x) {volatile double y=x;return y+y;}\n';message='floating arithmetic outside flag helper'
 obj,_=build_fault(abi,'abi')
 detected=subprocess.run([sys.executable,'tools/check-long-double-seventeen-abi.py','--object',str(obj)],capture_output=True,text=True,timeout=60)
 (work/'abi-detection.log').write_text(detected.stdout+detected.stderr)
 m.need(detected.returncode!=0 and message in detected.stdout+detected.stderr,'compiled ABI fault rejected at unintended assertion')
 # The environment controls use independently compiled caller failures.
 for name,macro,result in[('clear','feclearexcept',1),('round','fesetround',1),('raise','feraiseexcept',1),('round-noop','fesetround',0),('raise-noop','feraiseexcept',0)]:
  stub=work/(name+'.c');stub.write_text(f'int probe_fault(int value) {{(void)value;return {result};}}\n')
  obj=work/(name+'.o')
  run([*compiler,*flags,'-D'+macro+'=probe_fault','-c','tools/probe-long-double-seventeen-state.c','-o',str(obj)],name+'-compile')
  run([*compiler,'-fno-lto',str(obj),str(args.object.resolve()),str(stub),*link,'-o',str(work/name)],name+'-link')
 obj=work/'no-sse.o'
 run([*compiler,*flags,'-U__SSE__','-c','tools/probe-long-double-seventeen-state.c','-o',str(obj)],'no-sse-compile')
 run([*compiler,'-fno-lto',str(obj),str(args.object.resolve()),*link,'-o',str(work/'no-sse')],'no-sse-link')
 run([sys.executable,'tools/check-long-double-seventeen-probe-controls.py','--probe',str(args.raw_probe.resolve()),'--state-probe',str(args.probe.resolve()),'--fault-directory',str(work),'--json',str(work/'probe-controls.json')],'probe-controls')
 count=m.loader_controls(args.directory)
 summary={'actual_exit':0,'compiled_numerical_state_abi_faults':4,'compiled_environment_controls':6,'loader_controls':count,'positive_native_wrapper_witnesses':2}
 (work/'status.json').write_text(json.dumps(summary,sort_keys=True)+'\n')
 print('seventeen compiled controls:',json.dumps(summary,sort_keys=True))
if __name__=='__main__':main()
