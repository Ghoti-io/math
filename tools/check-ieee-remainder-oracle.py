#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Actual IEEE remainder/quotient oracle faults and wrapper accounting controls."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',type=Path,required=True);ap.add_argument('--probe',type=Path,required=True);a=ap.parse_args();a.work.mkdir(parents=True,exist_ok=True)
    spec=importlib.util.spec_from_file_location('ieee_remainder_oracle','tools/oracle/oracle.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
    source=Path('tools/oracle/gen_corpus_ieee_remainder.py').read_text()
    faults=[('MPFR-quotient', 'rr,qq=gmpy2.remquo(xx,yy);rr2=', 'rr,qq=gmpy2.remquo(xx,yy);qq+=1;rr2='), ('MPFR-remquo-result', 'rr,qq=gmpy2.remquo(xx,yy);rr2=', 'rr,qq=gmpy2.remquo(xx,yy);rr+=1;rr2='), ('MPFR-remainder-result', 'rr2=gmpy2.remainder(xx,yy)', 'rr2=gmpy2.remainder(xx,yy)+1'), ('three-quotient-bits', 'abs(qq)&127', 'abs(qq)&7'), ('Fraction-quotient', 'result,quo,invalid=answer(x,y,width)', 'result,quo,invalid=answer(x,y,width);quo+=1'), ('truncation-API', 'gmpy2.remainder(xx,yy)', 'gmpy2.fmod(xx,yy)'), ('adjacent-rational-target', 'result,quo,invalid=answer(x,y,width)', 'result,quo,invalid=answer(x,y,width);result^=1'), ('MPFR-pin', "gmpy2.version()!='2.3.2'", "gmpy2.version()!='untrusted'")]
    try:ref,version=oracle.check_pin(timeout=20)
    except oracle.Unavailable as error:
        if oracle.REQUIRED:raise RuntimeError(str(error))
        print('ieee_remainder oracle plants: SKIPPED optional pinned numerical/population controls: '+str(error));ref=None
    if ref:
        for name,old,new in faults:
            if source.count(old)!=1:raise RuntimeError('nonunique oracle anchor '+name)
            with tempfile.TemporaryDirectory(prefix='ieee_remainder-fault-',dir=a.work) as t:
                stage=Path(t);script=stage/'fault.py';output=stage/'out'
                changed=source.replace(old,new,1).replace('import argparse',"import sys\nsys.path.insert(0,'tools')\nsys.path.insert(0,'tools/oracle')\nimport argparse",1);script.write_text(changed)
                r=oracle.engine_run(ref,['python',str(script.resolve()),'--out',str(output.resolve()),'--seed','20261028','--count','0'],capture=True,timeout=120)
                (a.work/(name+'.log')).write_text(r.stdout+r.stderr)
                if r.returncode!=1 or not any(x in r.stderr for x in ('Fraction/MPFR remainder/quotient disagreement','requires pinned')):raise RuntimeError('actual oracle fault not detected '+name+' '+r.stdout+r.stderr)
                if output.exists() and list(output.iterdir()):raise RuntimeError('bad oracle published '+name)
                print('  ok   actual ieee_remainder oracle '+name+' rejected before publishing',flush=True)
        helper=Path('tools/ieee_remainder_reference.py').read_text()
        helper_faults=[
          ('helper-tie','or (2*r==ratio.denominator and q&1)','or (2*r==ratio.denominator)'),
          ('helper-sign','fragment=(q&127)*(-1 if (x^y)&sign else 1)','fragment=(q&127)*(-1 if x&sign else 1)'),
          ('helper-modulo','fragment=(q&127)','fragment=(q&7)'),
          ('helper-zero-sign','if remainder else x&sign','if remainder else 0'),
          ('helper-widening','return bits(value(raw,width),64)','return bits(value(raw,width),64)^1'),
          ('helper-signaling','return a>((1<<eb)-1)<<p and not a&(1<<(p-1))','return False'),
          ('missing-binades','for e in range(1-bias-p,bias+1):','for e in ():'),
          ('missing-nonzero-chunks','for gap in [0,1,6,7,10,11,12,13,22,23,24,39,40,41,80,100,200,2*bias-1]:','for gap in ():')]
        for name,old,new in helper_faults:
            if helper.count(old)!=1:raise RuntimeError('nonunique shared reference anchor '+name)
            with tempfile.TemporaryDirectory(prefix='ieee-helper-fault-',dir=a.work) as t:
                stage=Path(t);selected=stage/'ieee_remainder_reference.py';selected.write_text(helper.replace(old,new,1));script=stage/'fault.py';output=stage/'out'
                changed=source.replace("sys.path.insert(0,str(Path(__file__).resolve().parents[1]))","sys.path.insert(0,"+repr(str(stage.resolve()))+")",1)
                changed=changed.replace('import argparse',"import sys\nsys.path.insert(0,'tools/oracle')\nimport argparse",1)
                check="import ieee_remainder_reference as selected_reference\nif Path(selected_reference.__file__).resolve()!=Path("+repr(str(selected.resolve()))+"):raise RuntimeError('private reference selection failed')\n"
                changed=changed.replace('import gmpy2',check+'import gmpy2',1);script.write_text(changed)
                result=oracle.engine_run(ref,['python',str(script.resolve()),'--out',str(output.resolve()),'--seed','20261028','--count','0'],capture=True,timeout=120)
                (a.work/(name+'.log')).write_text(result.stdout+result.stderr)
                if result.returncode!=1 or not any(message in result.stderr for message in ('fixed reference contract control failed','fixed widening control failed','fixed signaling classification control failed','coverage missing')):raise RuntimeError('shared reference/coverage fault escaped '+name+result.stdout+result.stderr)
                if output.exists() and list(output.iterdir()):raise RuntimeError('shared reference fault published '+name)
                print('  ok   actual '+name+' rejected before publication',flush=True)
        for name,replacement in (('ignored-count','population(width,a.seed,0)'),('ignored-seed','population(width,20261028,a.count)')):
            with tempfile.TemporaryDirectory(prefix='ieee_remainder-population-',dir=a.work) as t:
                stage=Path(t);script=stage/'fault.py';output=stage/'out';old='population(width,a.seed,a.count)'
                if source.count(old)!=1:raise RuntimeError('population anchor not unique')
                changed=source.replace(old,replacement,1).replace('import argparse',"import sys\nsys.path.insert(0,'tools')\nsys.path.insert(0,'tools/oracle')\nimport argparse",1);script.write_text(changed)
                r=oracle.engine_run(ref,['python',str(script.resolve()),'--out',str(output.resolve()),'--seed','4294967291','--count','113','--fresh'],capture=True,timeout=120)
                if r.returncode:raise RuntimeError('population fault did not publish '+name+r.stderr)
                r=subprocess.run([sys.executable,'tools/check-ieee-remainder.py','--probe',str(a.probe.resolve()),'--corpus',str(output.resolve()),'--fresh','--seed','4294967291','--count','113'],capture_output=True,text=True,timeout=120)
                (a.work/(name+'.log')).write_text(r.stdout+r.stderr)
                if r.returncode!=1 or 'complete ordered population mismatch' not in r.stderr:raise RuntimeError('actual population fault escaped '+name+r.stdout+r.stderr)
                print('  ok   actual generator '+name+' rejected by complete population check',flush=True)
    # A recording engine calibrates actual wrapper argv dispatch, not numbers.
    wrapper=Path('tools/oracle/oracle.py').read_text();_,pin_version=oracle.pin()
    with tempfile.TemporaryDirectory(prefix='ieee_remainder-wrapper-',dir=a.work) as t:
        stage=Path(t);engine=stage/'engine';record=stage/'record.json';wrong=stage/'wrong-wrapper.py'
        engine.write_text('#!'+sys.executable+'\nimport sys,json\nfrom pathlib import Path\nargs=sys.argv[1:]\nif args[:2]==["image","exists"]:sys.exit(0)\nif args[-1:]==["mpfr-version"]:print('+repr(pin_version)+');sys.exit(0)\np=Path('+repr(str(record.resolve()))+')\nold=json.loads(p.read_text()) if p.exists() else []\nold.append(args);p.write_text(json.dumps(old))\n')
        engine.chmod(0o700);env=os.environ.copy();env['GHOTI_CONTAINER_ENGINE']=str(engine.resolve());env['GHOTI_ORACLE_REQUIRED']='1'
        dispatch=next(line for line in wrapper.splitlines() if line.startswith('    if a.cmd in ("logbase",'))
        omission=dispatch.replace('"ieee_remainder", "fresh-ieee_remainder", ','')
        if omission==dispatch:raise RuntimeError('wrapper family omission anchor absent')
        wrong.write_text(wrapper.replace(dispatch,omission,1))
        # Keep ROOT/HERE/pin lookup identical despite staging the actual source.
        wrong.write_text(wrong.read_text().replace('HERE = os.path.dirname(os.path.abspath(__file__))','HERE = '+repr(str(Path('tools/oracle').resolve())),1))
        for command in ('ieee_remainder','fresh-ieee_remainder'):
            for plant in (False,True):
                record.unlink(missing_ok=True);selected=wrong if plant else Path('tools/oracle/oracle.py')
                output=stage/('out-'+command+str(plant))
                r=subprocess.run([sys.executable,str(selected),'%s'%command,'--out',str(output.resolve()),'--seed','123','--count','17'],env=env,capture_output=True,text=True,timeout=30)
                calls=json.loads(record.read_text()) if record.exists() else []
                actual=[args[args.index('python')+1:] for args in calls if 'python' in args]
                expected=[['tools/oracle/gen_corpus_ieee_remainder.py','--out',str(output.resolve()),'--seed','123','--count','17']+(['--fresh'] if command.startswith('fresh-') else [])]
                if r.returncode or (actual==expected)==plant:raise RuntimeError('wrapper dispatch calibration wrong '+command+r.stdout+r.stderr)
                print('  ok   wrapper '+command+(' missing-family defect detected' if plant else ' valid dispatch'),flush=True)
        env['GHOTI_CONTAINER_ENGINE']=str((stage/'absent-engine').resolve())
        for required in (False,True):
            env['GHOTI_ORACLE_REQUIRED']='1' if required else '0';output=stage/('absent-'+str(required))
            r=subprocess.run([sys.executable,'tools/oracle/oracle.py','fresh-ieee_remainder','--out',str(output.resolve()),'--seed','123','--count','17'],env=env,capture_output=True,text=True,timeout=30)
            if r.returncode!=(1 if required else 3) or (output.exists() and list(output.iterdir())):raise RuntimeError('absent pinned engine semantics differ')
            print('  ok   '+('required' if required else 'optional')+' absent engine rejected/skipped without payloads',flush=True)
    print('ieee_remainder oracle controls pass; recording-engine controls are not numerical oracle evidence')

if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as error:
        print('ieee_remainder oracle controls: FAIL: '+str(error),file=sys.stderr);sys.exit(1)
