#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
"""Required runtime-pinned oracle; unavailable or mismatched tools fail."""
import argparse,importlib.util,json,re,subprocess,uuid
from pathlib import Path

def run_named(engine,root,image,arguments,capture=False,timeout=180):
    name='ghoti-long-double-eleven-'+uuid.uuid4().hex[:12]
    try:
        return subprocess.run([engine,'run','--rm','--name',name,'--timeout',str(timeout),'--cgroups=disabled','--cgroupns=host','--userns=keep-id','--security-opt','label=disable','-v',str(root)+':/work:Z','-w','/work',image,*arguments],check=False,capture_output=capture,text=True,timeout=timeout+10)
    finally:
        subprocess.run([engine,'rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)

def resolve_instrument(root):
    # Reuse the repository's public image tag and exact runtime-version pin.
    # Locally rebuilt images legitimately have different immutable IDs.
    spec=importlib.util.spec_from_file_location('eleven_required_oracle',root/'tools/oracle/oracle.py')
    instrument=importlib.util.module_from_spec(spec);spec.loader.exec_module(instrument)
    instrument.engine_run=lambda ref,argv,capture=False,timeout=None:run_named(instrument.ENGINE,root,ref,argv,capture,timeout or 30)
    try:image,version=instrument.check_pin(timeout=30)
    except instrument.Unavailable as error:raise SystemExit('required eleven oracle unavailable: '+str(error)) from error
    identity=subprocess.check_output([instrument.ENGINE,'image','inspect','--format','{{.Id}}',image],text=True,timeout=30).strip().removeprefix('sha256:')
    if not re.fullmatch('[0-9a-f]{64}',identity):raise SystemExit('invalid immutable oracle image identity')
    return instrument.ENGINE,identity,version

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=Path('tests/corpus'));parser.add_argument('--probe',type=Path);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1];directory=args.directory.resolve();relative=directory.relative_to(root)
    engine,identity,version=resolve_instrument(root)
    evidence=root/'build/linux/long-double-eleven-evidence';evidence.mkdir(parents=True,exist_ok=True);token=uuid.uuid4().hex
    (evidence/('oracle-instrument-'+token+'.json')).write_text(json.dumps({'immutable_image_id':identity,'runtime_pin':version})+'\n')
    fresh=evidence/('fresh-'+token+'.json')
    command=['python','tools/check-long-double-eleven.py','--verify-oracle','--directory',str(relative),*(['--fresh-json',str(fresh.relative_to(root))] if args.probe else [])]
    result=run_named(engine,root,identity,command)
    if result.returncode:raise SystemExit('required eleven oracle failed: '+str(result.returncode))
    if args.probe:
        data=json.loads(fresh.read_text());cells=data['cells'];rows=[c[:6]+[0,3,0,0] for c in cells]
        result=subprocess.run([str(args.probe)],input=''.join(' '.join(f'{v:x}' for v in row)+'\n' for row in rows),text=True,capture_output=True,timeout=60,check=True)
        lines=result.stdout.splitlines()[1:]
        if len(lines)!=44:raise SystemExit('fresh output count')
        for cell,line in zip(cells,lines,strict=True):
            fields=line.split();actual=(int(fields[0],16),int(fields[1],16),*map(int,fields[2:]))
            if actual!=(*cell[6:9],173,1,0):raise SystemExit('fresh output mismatch '+str(cell)+' '+line)
        native=int(result.stdout.splitlines()[0].split()[1]);native_cells=[cell for cell in cells if cell[0]==native]
        native_rows=[[0,*cell[1:6],0,3,0,0] for cell in native_cells]
        replay=subprocess.run([str(args.probe)],input=''.join(' '.join(f'{v:x}' for v in row)+'\n' for row in native_rows),text=True,capture_output=True,timeout=60,check=True)
        lines=replay.stdout.splitlines()[1:]
        if len(lines)!=len(native_cells):raise SystemExit('fresh native output count')
        for cell,line in zip(native_cells,lines,strict=True):
            fields=line.split();actual=(int(fields[0],16),int(fields[1],16),*map(int,fields[2:]))
            if actual!=(*cell[6:9],173,1,0):raise SystemExit('fresh native output/state mismatch '+line)
        print('fresh external native wrapper outputs passed',len(native_cells),'format',native)
        print('fresh production outputs passed44cells seed',data['seed'])

if __name__=='__main__':main()
