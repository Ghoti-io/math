#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Bounded all-twelve references, genuine calls, state, and rejecting controls."""
import argparse, copy, hashlib, importlib.util, json, os, re, shlex, subprocess, sys, tempfile, uuid
from fractions import Fraction as F
from pathlib import Path
import error_gamma_reference as r
spec=importlib.util.spec_from_file_location('error_gamma_contract',Path(__file__).with_name('check-long-double-seventeen.py'))
k=importlib.util.module_from_spec(spec);spec.loader.exec_module(k)
NAME='error-gamma.json'
SHA256='4b2830f68a3b59be5c42defe6ad40f9176eb51979137e1a4e2bc79eb03497353'

def need(condition,message):
    if not condition:raise k.Rejected(message)

def validate(data):
    need(type(data)is dict and set(data)=={'schema','oracle','mpfr_precision','independent_min_precision','bound_bits','population_sha256','cells'},'reference manifest schema')
    for key,value in {'schema':1,'oracle':r.PIN,'mpfr_precision':4096,'independent_min_precision':8192,'bound_bits':2304}.items():
        need(type(data[key])is type(value)and data[key]==value,'fixed reference provenance '+key)
    rows=r.population();cells=data['cells']
    need(type(cells)is list and len(cells)==len(rows),'complete population count')
    observed=[];counts={};regions={};kinds={};ordinary=exact=0
    for cell in cells:
        need(type(cell)is dict and set(cell)=={'input','reference'},'cell schema')
        row=cell['input'];need(type(row)is list and len(row)==7 and type(row[0])is str and len(row[0])<160 and all(type(v)is int for v in row[1:]),'bounded input schema')
        _,fmt,op,ah,al,bh,bl=row
        need(fmt in (32,*r.c.FORMATS)and 13<=op<=16 and all(0<=v<1<<64 for v in (ah,al,bh,bl)),'input integer bounds')
        need(not(bh|bl)and(fmt not in (32,64)or not al)and(fmt!=32 or ah<1<<32)and(fmt!=80 or ah<1<<16),'reserved input bits')
        observed.append(row);family=row[0].split('/')[0];key=f'{family}/{fmt}/{r.c.NAMES[op]}'
        counts[key]=counts.get(key,0)+1
        tag=row[0].rsplit('/',1)[1]
        region=next((prefix for prefix in ('negative-root','pole','recurrence','huge-negative-remote','huge-positive-range','remote','tiny-reciprocal','erfc-rounded-normal','erfc-negative-saturation','erfc-normal','erfc-zero','erf-dd-saturation','erf-saturation','lgamma-rounded-overflow','gamma-rounded-normal','gamma-rounded-overflow','gamma-normal','gamma-zero','gamma-overflow','switch','input-normal','negative-minimum-subnormal','minimum-subnormal','signaling-nan','quiet-nan','infinity','malformed')if tag.startswith(prefix)),tag)
        region_key=f'{family}/{fmt}/{region}';regions[region_key]=regions.get(region_key,0)+1
        ref=cell['reference'];direct=r.special(row)
        if direct is not None:
            need(type(ref)is dict and set(ref)==set(direct),'exact/range reference schema')
            if 'exact'in direct:
                entry=ref['exact'];need(type(entry)is list and len(entry)==3 and all(type(v)is str and re.fullmatch('[0-9a-f]{16}',v)for v in entry[:2])and type(entry[2])is int and 0<=entry[2]<=31,'exact reference encoding')
            else:
                entry=ref['tiny'];need(type(entry)is list and len(entry)==2 and all(type(v)is int for v in entry),'range proof encoding')
            need(ref==direct,'exact special contract');exact+=1
            kind='tiny-range-proof'if 'tiny'in ref else'far-overflow-proof'if ref['exact'][2]==20 else'exact-special'
            kinds[kind]=kinds.get(kind,0)+1
        else:
            need(type(ref)is dict and set(ref)=={'interval','sign','range','independent_precision'},'ordinary reference schema')
            lo,hi=k.bounds(ref['interval'])
            need(type(ref['sign'])is int and ref['sign']==int(hi<0),'reference sign')
            need(type(ref['independent_precision'])is int and 8192<=ref['independent_precision']<=1000000,'independent precision provenance')
            kind='overflow'if min(abs(lo),abs(hi))>=r.virtual(fmt)else'finite'if max(abs(lo),abs(hi))<=r.limit(fmt)else'edge'
            need(ref['range']==kind,'independent range classification');ordinary+=1
            kinds[kind]=kinds.get(kind,0)+1
    need(observed==rows,'independent input population sequence')
    need(data['population_sha256']==hashlib.sha256(r.canonical(rows)).hexdigest(),'population SHA256')
    need(len(counts)==24,'all operation/layout populations')
    return {'cells':len(cells),'ordinary':ordinary,'exact_specials':kinds.get('exact-special',0),'exact_or_range_proofs':exact,'operation_layout_counts':counts,'region_counts':regions,'reference_kinds':kinds}

def load(directory):
    payload=k.roots.bounded_read(directory/NAME,4*1024*1024)
    need(hashlib.sha256(payload).hexdigest()==SHA256,'authenticated payload SHA256')
    data=json.loads(payload,parse_constant=lambda _:(_ for _ in ()).throw(k.Rejected('nonfinite JSON')))
    need(r.canonical(data)==payload,'canonical JSON')
    return data,validate(data)

def verify(cell,line,incoming=0):
    if cell['input'][1]!=32:
        k.verify(cell,line,incoming);return
    ah,al,flags,err,controls,entry=k.result_fields(line)
    need(ah<1<<32 and al==0,'Float result encoding')
    need(err==173 and controls==1,'caller state preservation')
    need(entry&incoming==incoming and (incoming or not entry),'incoming flags')
    ref=cell['reference']
    if 'exact'in ref:
        need([f'{ah:016x}',f'{al:016x}']==ref['exact'][:2],'exact special result');required=ref['exact'][2]
    else:
        sign=ah>>31;mag=ah&0x7fffffff
        need(sign==ref['sign'],'ordinary result sign')
        if mag==0x7f800000:
            need(ref['range']in ('overflow','edge'),'range overflow result')
            if ref['range']=='edge':
                lo,hi=k.bounds(ref['interval']);need(min(abs(lo),abs(hi))>=r.limit(32),'overflow edge enclosure')
            required=20
        else:
            need(mag<0x7f800000 and ref['range']!='overflow','ordinary finite classification')
            value=r.decode(ah,32);lo,hi=k.bounds(ref['interval'])
            neighbors=[]
            for direction in (-1,1):
                word=r.neighbor(32,value,direction)[0]
                neighbors.append((-1 if word>>31 else 1)*r.virtual(32)if word&0x7fffffff==0x7f800000 else r.decode(word,32))
            need(neighbors[0]<=lo and hi<=neighbors[1],'ordinary actual-neighbor enclosure')
            required=12 if abs(value)<r.normal(32)else 4
    need(flags==required|entry,'exception flags (including incoming flags)')

def command_row(cell,mode=0,pc=0,incoming=0,profile=0,native=False):
    family=cell['input'][0].split('/')[0];fmt=cell['input'][1]
    code=0 if native else 63 if family=='double'else fmt
    return [code,*cell['input'][2:],mode,pc,incoming,profile]

def invoke(probe,rows,work,label):
    result=subprocess.run([str(probe.resolve())],input=''.join(' '.join(format(v,'x')for v in row)+'\n'for row in rows),text=True,capture_output=True,timeout=900)
    (work/(label+'.json')).write_text(json.dumps({'rows':rows,'actual_exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr},sort_keys=True)+'\n')
    need(result.returncode==0,'probe execution failed (not defect detection): '+str(result.returncode))
    lines=result.stdout.splitlines();need(len(lines)==len(rows)+1 and lines[0].startswith('native '),'probe header/count')
    fields=lines[0].split();return int(fields[1]),int(fields[-1],16),lines[1:]

def measured_error(cell,line):
    ref=cell['reference'];fmt=cell['input'][1]
    if 'interval'not in ref or ref['range']=='overflow':return None
    ah,al,*_=k.result_fields(line)
    if fmt==32:
        if ah&0x7fffffff>=0x7f800000:return None
        value=r.decode(ah,32)
        def adjacent(direction):
            word=r.neighbor(32,value,direction)[0]
            return (-1 if word>>31 else 1)*r.virtual(32)if word&0x7fffffff==0x7f800000 else r.decode(word,32)
    else:
        kind,_,_,value=r.c.b.decode(fmt,(ah,al))
        if kind!='finite':return None
        def adjacent(direction):
            kind,_,_,v=r.c.b.decode(fmt,r.neighbor(fmt,value,direction))
            return v if kind=='finite'else direction*r.virtual(fmt)
    lo,hi=k.bounds(ref['interval'])
    return max((value-lo)/(value-adjacent(-1))if lo<value else F(0),(hi-value)/(adjacent(1)-value)if hi>value else F(0))

def check(probe,data,work):
    native,mask,_=invoke(probe,[command_row(data['cells'][0])],work,'capabilities')
    need(native in r.c.FORMATS,'supported actual native layout')
    baseline_pc=3 if native==80 else 0
    cells=data['cells'];expected=cells+[v for v in cells if v['input'][0].startswith(f'long/{native}/')]
    rows=[command_row(v,pc=baseline_pc)for v in cells]+[command_row(v,pc=baseline_pc,native=True)for v in expected[len(cells):]]
    _,_,lines=invoke(probe,rows,work,'numerical');baseline={};errors={}
    for cell,line in zip(expected,lines,strict=True):
        try:verify(cell,line)
        except k.Rejected as error:raise k.Rejected(str(error)+'; '+cell['input'][0]+'; '+line)from error
        key=tuple(cell['input']);
        if key in baseline:k.same_output(baseline[key],line)
        baseline[key]=line
        error=measured_error(cell,line)
        group='/'.join(cell['input'][0].split('/')[:3])
        if error is not None and (group not in errors or error>errors[group][0]):errors[group]=(error,cell['input'][0])
    profiles=[0]+([1,2]if mask&0x8040==0x8040 else [])+([3]if mask&0x8000 else [])
    pcs=(0,2,3)if native==80 else (0,)
    states=[];chosen=[]
    # Full state product for every public ordinary API, then boundary and
    # early-return rows in every supported flush profile with varied flags.
    public=[v for v in cells if not v['input'][0].startswith('long/')or v['input'][1]==native]
    for cell in public:
        tag=cell['input'][0];is_native=tag.startswith('long/')
        if tag.endswith('/ordinary'):
            for mode in range(4):
                for incoming in (0,1,2,4,8,16,31):
                    for profile in profiles:
                        for pc in pcs:
                            states.append(command_row(cell,mode,pc,incoming,profile,is_native));chosen.append((cell,incoming))
        elif any(word in tag for word in ('gamma-','erfc-','erf-dd-saturation','erf-saturation','huge-positive-range','signaling-nan','quiet-nan','pole-','remote-','tiny-reciprocal','minimum-subnormal','/zero','/negative-zero','/infinity','/one','/two','/malformed','/negative-root','/reflection')):
            for profile in profiles:
                index=len(states);incoming=(0,1,2,4,8,16,31)[index%7]
                states.append(command_row(cell,index%4,pcs[index%len(pcs)],incoming,profile,is_native));chosen.append((cell,incoming))
    lines=[]
    for offset in range(0,len(states),512):
        _,_,part=invoke(probe,states[offset:offset+512],work,'state-'+str(offset//512));lines.extend(part)
    for (cell,incoming),line in zip(chosen,lines,strict=True):
        try:verify(cell,line,incoming);k.same_output(baseline[tuple(cell['input'])],line)
        except k.Rejected as error:raise k.Rejected(str(error)+'; state '+cell['input'][0]+'; '+line)from error
    return {'raw_and_narrow_rows':len(cells),'native_public_rows':len(expected)-len(cells),'state_rows':len(states),'native_layout':native,'flush_profiles':profiles,'ordinary_precision_controls':list(pcs),'ordinary_incoming_flags':[0,1,2,4,8,16,31],'maximum_result_local_errors':{key:{'ULP_upper_1e12':str(-((-value[0]*10**12)//1)),'exact_fraction':[str(value[0].numerator),str(value[0].denominator)],'input':value[1]}for key,value in errors.items()}}

def controls(probe,data,work):
    count=0
    def reject(action,message):
        nonlocal count
        try:action()
        except k.Rejected as error:need(message in str(error),'intended rejecting assertion: '+str(error));count+=1
        else:raise k.Rejected('defect escaped '+message)
    cell=next(v for v in data['cells']if v['input'][0]=='double/64/erfc/ordinary')
    native,_,lines=invoke(probe,[command_row(cell)],work,'control-good');verify(cell,lines[0])
    fields=lines[0].split();fields[0]='0000000000000000';reject(lambda:verify(cell,' '.join(fields)),'actual-neighbor')
    fields=lines[0].split();fields[2]=str(int(fields[2])^4);reject(lambda:verify(cell,' '.join(fields)),'exception flags')
    fields=lines[0].split();fields[2]=str(int(fields[2])|1);reject(lambda:verify(cell,' '.join(fields)),'exception flags (including incoming flags)')
    _,_,seeded=invoke(probe,[command_row(cell,incoming=2)],work,'control-incoming-good');verify(cell,seeded[0],2)
    fields=seeded[0].split();fields[2]=str(int(fields[2])&~2);reject(lambda:verify(cell,' '.join(fields),2),'exception flags (including incoming flags)')
    # Exercise the separate Float verifier and the actual native ABI for every
    # operation. Only a successful genuine call reaches output corruption.
    selected=[v for v in data['cells']if v['input'][0].endswith('/ordinary')and(v['input'][0].startswith('float/')or v['input'][0].startswith(f'long/{native}/'))]
    need(len(selected)==8,'Float/native ordinary control population')
    rows=[command_row(v,pc=3 if native==80 else 0,native=v['input'][0].startswith('long/'))for v in selected]
    _,_,good=invoke(probe,rows,work,'control-float-native-good')
    for target,output in zip(selected,good,strict=True):
        verify(target,output);wrong=output.split();wrong[:2]=['0000000000000000','0000000000000000']
        reject(lambda:verify(target,' '.join(wrong)),'ordinary actual-neighbor enclosure')
    fields=lines[0].split();fields[4]='0';reject(lambda:verify(cell,' '.join(fields)),'control preservation')
    bad=copy.deepcopy(data);bad['cells'].pop();reject(lambda:validate(bad),'population count')
    bad=copy.deepcopy(data);bad['cells'][1]=bad['cells'][0];reject(lambda:validate(bad),'input population')
    changed=copy.deepcopy(cell);changed['reference']['interval'][2]+=10
    reject(lambda:verify(changed,lines[0]),'actual-neighbor')
    # Verifier-policy control: a narrow enclosure straddling the finite limit
    # permits the maximum finite value, but cannot certify infinity. This is
    # synthetic policy data, never a numerical reference for a public call.
    limit=r.limit(32);e=r.c.b.exponent(limit)-2303;unit=F(2)**e;mantissa=int(limit/unit)
    edge={'input':['synthetic-overflow-policy',32,15,0,0,0,0],'reference':{'interval':[format(mantissa-1,'x'),format(mantissa+1,'x'),e],'sign':0,'range':'edge','independent_precision':8192}}
    verify(edge,'000000007f7fffff 0000000000000000 4 173 1 0')
    reject(lambda:verify(edge,'000000007f800000 0000000000000000 20 173 1 0'),'overflow edge enclosure')
    # Authentication does not accept a changed payload with a new sidecar pin.
    with tempfile.TemporaryDirectory(prefix='reference-',dir=work)as folder:
        path=Path(folder);payload=r.canonical(data);(path/NAME).write_bytes(payload);load(path)
        changed=payload.replace(b'"schema":1',b'"schema":2');(path/NAME).write_bytes(changed)
        (path/(NAME+'.sha256')).write_text(hashlib.sha256(changed).hexdigest()+'\n')
        reject(lambda:load(path),'authenticated payload SHA256')
    # Missing execution modes must reject before loading data or producing a
    # success-like status, including when an earlier invocation left files.
    with tempfile.TemporaryDirectory(prefix='missing-mode-',dir=work)as folder:
        folder=Path(folder)
        for filename in ('status.json','oracle-status.json'):(folder/filename).write_text('{"actual_exit":0}\n')
        result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--directory',str(r.ROOT/'tests/corpus'),'--work',str(folder)],capture_output=True,text=True,timeout=60)
        (work/'missing-mode-control.log').write_text(result.stdout+result.stderr)
        need(result.returncode==1 and 'execution mode requires --probe or --oracle'in result.stderr,'intended missing-mode assertion')
        need(not(folder/'status.json').exists()and not(folder/'oracle-status.json').exists(),'missing-mode stale statuses removed');count+=1
    # Compile a real runtime cutoff defect, linking it before the normal
    # archive. Setup, compilation, crashes and timeouts never count as catches.
    if os.environ.get('ERROR_GAMMA_CC'):
        source=Path('src/elementary/error_gamma.c').read_text();old='rm_cmp(x, rm_uint(28))';need(source.count(old)==1,'compiled defect site')
        planted=work/'error_gamma.c';planted.write_text(source.replace(old,'rm_cmp(x, rm_uint(7))'))
        cc=shlex.split(os.environ['ERROR_GAMMA_CC']);flags=shlex.split(os.environ['ERROR_GAMMA_FLAGS']);link=shlex.split(os.environ['ERROR_GAMMA_LINK']);obj=work/'defect.o';exe=work/'defect-probe'
        for label,args in [('compile',cc+flags+['-I','src/elementary','-c',str(planted),'-o',str(obj)]),('link',cc+flags+[os.environ['ERROR_GAMMA_CALLER'],str(obj),os.environ['ERROR_GAMMA_ARCHIVE']]+link+['-o',str(exe)])]:
            result=subprocess.run(args,capture_output=True,text=True,timeout=300);(work/('defect-'+label+'.log')).write_text(result.stdout+result.stderr);need(result.returncode==0,'compiled control setup '+label)
        victim=next(v for v in data['cells']if v['input'][0]=='double/64/erfc/switch-16-0-1')
        _,_,good=invoke(probe,[command_row(victim)],work,'compiled-good');verify(victim,good[0])
        _,_,bad=invoke(exe,[command_row(victim)],work,'compiled-defect');reject(lambda:verify(victim,bad[0]),'actual-neighbor')
    else:raise k.Rejected('compiled controls require explicit compiler/link context')
    return count

def oracle(directory,work):
    # The pinned external instrument is required, with no host fallback.
    engine=os.environ.get('GHOTI_CONTAINER_ENGINE','podman');entries=[line.split('\t')for line in (r.ROOT/'tools/oracle/containers/IMAGES').read_text().splitlines()if line.startswith('mpfr\t')]
    need(len(entries)==1 and entries[0][2]==r.PIN,'oracle runtime pin')
    try:identity=subprocess.check_output([engine,'image','inspect','--format','{{.Id}}',entries[0][1]],text=True,timeout=30).strip()
    except (OSError,subprocess.CalledProcessError,subprocess.TimeoutExpired)as error:raise k.Rejected('required oracle image unavailable')from error
    need(re.fullmatch('(?:sha256:)?[0-9a-f]{64}',identity),'oracle image identity')
    style=os.environ.get('GHOTI_CONTAINER_STYLE','podman'if Path(engine).name.startswith('podman')else'docker');need(style in ('podman','docker'),'oracle engine style')
    def run(arguments,label,timeout):
        name='ghoti-error-gamma-'+uuid.uuid4().hex[:12];cmd=[engine,'run','--rm','--cpus=1','--memory=1536m','--memory-swap=1536m','--name',name]
        if style=='podman':cmd+=['--timeout',str(timeout),'--cgroupns=host','--userns=keep-id','--security-opt','label=disable']
        else:cmd+=['--user',str(os.getuid())+':'+str(os.getgid())]
        cmd+=['-e','PYTHONDONTWRITEBYTECODE=1','-v',str(r.ROOT)+':/work:ro','-w','/work',identity,'nice','-n','10',*arguments]
        try:
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout+10);(work/(label+'.log')).write_text(result.stdout+result.stderr);need(result.returncode==0,'required oracle '+label+' failed');return result.stdout
        finally:subprocess.run([engine,'rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
    need(run(['mpfr-version'],'version',30).strip()==r.PIN,'actual oracle runtime')
    run(['python','tools/oracle/gen_error_gamma_corpus.py','--out',str(Path('/work')/directory.resolve().relative_to(r.ROOT)/NAME),'--verify'],'regeneration',6500)
    # A real pinned positive control precedes the unavailable-instrument
    # control. The child must erase stale success files and reject availability;
    # a crash, numerical assertion or timeout is not this intended rejection.
    with tempfile.TemporaryDirectory(prefix='unavailable-',dir=work)as folder:
        folder=Path(folder);fake=folder/'engine';fake.write_text('#!/bin/sh\nexit 1\n');fake.chmod(0o755)
        child_work=folder/'negative';child_work.mkdir()
        for filename in ('status.json','oracle-status.json'):(child_work/filename).write_text('{"actual_exit":0}\n')
        result=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--directory',str(directory.resolve()),'--work',str(child_work),'--oracle'],capture_output=True,text=True,timeout=60,env=dict(os.environ,GHOTI_CONTAINER_ENGINE=str(fake)))
        (work/'unavailable-control.log').write_text(result.stdout+result.stderr)
        need(result.returncode==1 and 'required oracle image unavailable'in result.stderr,'intended unavailable-instrument assertion')
        need(not(child_work/'status.json').exists()and not(child_work/'oracle-status.json').exists(),'stale oracle statuses removed')
    (work/'oracle-status.json').write_text(json.dumps({'actual_exit':0,'immutable_image_id':identity,'runtime_pin':r.PIN,'corpus_sha256':SHA256,'rejecting_availability_controls':1,'stale_statuses_removed':True},sort_keys=True)+'\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=Path('tests/corpus'));p.add_argument('--probe',type=Path);p.add_argument('--work',type=Path,required=True);p.add_argument('--controls',action='store_true');p.add_argument('--oracle',action='store_true');a=p.parse_args();a.work.mkdir(parents=True,exist_ok=True);(a.work/'status.json').unlink(missing_ok=True);(a.work/'oracle-status.json').unlink(missing_ok=True)
    need(a.probe is not None or a.oracle,'execution mode requires --probe or --oracle')
    data,summary=load(a.directory)
    if a.probe:summary.update(check(a.probe,data,a.work))
    if a.controls:need(a.probe is not None,'controls require genuine compiled probe');summary['rejecting_controls']=controls(a.probe,data,a.work)
    if a.oracle:oracle(a.directory,a.work);summary['required_oracle']=True
    (a.work/'status.json').write_text(json.dumps(summary,sort_keys=True)+'\n');print('error/gamma assurance:',json.dumps(summary,sort_keys=True))
if __name__=='__main__':main()
