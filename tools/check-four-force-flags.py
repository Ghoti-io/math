#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-3.0-only
# Copyright (C) 2026 Corey Pennycuff
"""Natural public flags and explicitly calibrated exception-force mutations.

Calibration clears only relevant flags immediately before the selected force,
inside staged test sources. It is not a natural public-call deletion witness.
Production sources and caller control state are never modified by this tool.
"""
import sys
if not __debug__ or sys.flags.optimize:
    raise SystemExit('force flag checks require assertion-enabled Python')
import argparse, hashlib, json, os, shlex, subprocess
from pathlib import Path

PROBE = r'''
/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff */
#include <ghoti.io/math/elementary.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fenv.h>
#include "fp_controls.h"
static unsigned hits,preflags;
static int armed,mask;
static unsigned flags(void) {
 int f=fetestexcept(FE_ALL_EXCEPT);
 return ((f&FE_INVALID)?1u:0)|((f&FE_DIVBYZERO)?2u:0)|((f&FE_INEXACT)?4u:0)|((f&FE_UNDERFLOW)?8u:0)|((f&FE_OVERFLOW)?16u:0);
}
static int native_flags(unsigned f) {
 return ((f&1)?FE_INVALID:0)|((f&2)?FE_DIVBYZERO:0)|((f&4)?FE_INEXACT:0)|((f&8)?FE_UNDERFLOW:0)|((f&16)?FE_OVERFLOW:0);
}
void gmath_test_force_checkpoint(int f) {
 if(!armed || f!=mask) {fputs("force-check: checkpoint routing\n",stderr);exit(2);}
 ++hits;preflags|=flags();
 if(feclearexcept(f)) {fputs("force-check: checkpoint setup\n",stderr);exit(2);}
}
struct row {unsigned family,word,required,sites;};
static const struct row rows[]={
 {0,0xc2b40000,12,1},{0,0xc2c80000,12,1},{0,0x3f000000,4,0},{0,0,0,0},
 {1,0xc2fd0000,12,2},{1,0xc30c8000,12,2},{1,0x3f000000,4,0},{1,0xc2fe0000,0,0},{1,0,0,0},
 {2,0x3f000000,4,4},{2,0xbf000000,4,4},{2,0x40000000,4,4},{2,0xc0000000,4,4},
 {2,0x2b800000,4,0},{2,1,12,0},{2,0x7f800000,4,0},{2,0,0,0},
 {3,0x40000000,4,8},{3,0xc0000000,4,8},{3,0x41d80000,4,8},
 {3,1,4,16},{3,2,4,16},{3,0x80000001,4,16},{3,4,0,0},{3,0x3f800000,0,0},{3,0,0,0},
 {0,0x80000000,0,0},{0,0x7f800000,0,0},{0,0xff800000,0,0},{0,0x7fc12345,0,0},{0,0x7f812345,1,0},
 {1,0x80000000,0,0},{1,0x7f800000,0,0},{1,0xff800000,0,0},{1,0x7fc12345,0,0},{1,0x7f812345,1,0},
 {2,0x80000000,0,0},{2,0xff800000,4,0},{2,0x7fc12345,0,0},{2,0x7f812345,1,0},
 {3,0x80000000,0,0},{3,0x7f800000,0,0},{3,0xff800000,0,0},{3,0x7fc12345,0,0},{3,0x7f812345,1,0}};
int main(int argc,char **argv) {
 if(argc!=2)return 2;
 int failures=0;
 int site=atoi(argv[1]);if(site < -1 || site>4)return 2;
 float (*volatile functions[4])(float)={gmath_expf,gmath_exp2f,gmath_atanf,gmath_cbrtf};
 const int modes[4]={FE_TONEAREST,FE_DOWNWARD,FE_UPWARD,FE_TOWARDZERO};
 for(unsigned i=0;i<sizeof rows/sizeof rows[0];++i) {
  const struct row *r=&rows[i];if(site>=0 && !(r->sites&(1u<<(unsigned)site)))continue;
  for(unsigned mode=0;mode<4;++mode)for(unsigned seed=0;seed<32;++seed) {
   unsigned relevant=site<2?12u:4u;if(site<0)relevant=0;
   if(site>=0 && (seed&relevant))continue;
   if(feclearexcept(FE_ALL_EXCEPT)||fesetround(modes[mode]))return 2;
   if(seed && feraiseexcept(native_flags(seed)))return 2;
   unsigned entry=flags();if(entry!=seed) {fputs("force-check: entry setup\n",stderr);return 2;}
   hits=preflags=0;armed=site>=0;mask=native_flags(relevant);
   uint64_t controls=gmath_test_controls();int before=fegetround();errno=173;
   float x;memcpy(&x,&r->word,4);float y=functions[r->family](x);
   int err=errno;unsigned f=flags();int after=fegetround();uint64_t state=gmath_test_controls();
   uint32_t out;memcpy(&out,&y,4);
   unsigned mag=r->word&0x7fffffffu,expected=out;
   if(mag>0x7f800000u)expected=0x7fc00000u;
   else if(!mag)expected=r->family<2?0x3f800000u:r->word;
   else if(mag==0x7f800000u)expected=r->family<2?((r->word>>31)?0u:0x7f800000u):r->family==2?((r->word&0x80000000u)|0x3fc90fdbu):r->word;
   if(out!=expected) {fputs("force-check: special result\n",stderr);return 2;}
   if(err!=173 || before!=after || controls!=state || hits!=(unsigned)(site>=0)) {
    fputs("force-check: state/path\n",stderr);return 2;
   }
   printf("%u %08x %u %u %08x %u %u %u\n",r->family,r->word,mode,seed,out,f,hits,preflags);
   if(f!=(seed|r->required)) {
    fprintf(stderr,"force-check: flags family%u input%08x mode%u seed%u got%u expected%u\n",r->family,r->word,mode,seed,f,seed|r->required);++failures;
   }
  }
 }
 return failures?1:0;
}
'''

def run(command, log, expected=0):
    result=subprocess.run(command,capture_output=True,timeout=180)
    log.write_bytes(result.stdout+result.stderr)
    assert result.returncode==expected,(str(log),result.returncode,expected)
    return result

def inject(source, site, deletion):
    hook='gmath_test_force_checkpoint(FE_UNDERFLOW|FE_INEXACT); ' if site<2 else 'gmath_test_force_checkpoint(FE_INEXACT); '
    force='(void)gmath_underflow(0);' if site<2 else 'af_inexact();' if site==2 else 'fc_ix();'
    if site<2:
        word='ef_result_word' if site==0 else 'f_result_word'
        anchor='  if ('+word+' < 0x00800000u) {'
        assert source.count(anchor)==1,'nonunique call-site anchor'
        start=source.index(anchor)
        end=source.index('\n  }',start)+4
        block=source[start:end];assert block.count(force)==1
        replacement=block.replace(force,hook+('(void)0;' if deletion else force))
        source=source[:start]+replacement+source[end:]
    else:
        anchor=('  af_inexact();\n  return uf_narrow;' if site==2 else
                '  fc_ix();return result;' if site==3 else
                'if (!fc_exact_power(a)) fc_ix();')
        assert source.count(anchor)==1,'nonunique call-site anchor'
        replacement=anchor.replace(force,hook+('(void)0;' if deletion else force))
        if site==4:replacement='if (!fc_exact_power(a)) { '+hook+('(void)0;' if deletion else force)+' }'
        source=source.replace(anchor,replacement,1)
    return '#include <fenv.h>\nextern void gmath_test_force_checkpoint(int);\n'+source

def check(a):
    root=Path(__file__).resolve().parents[1];work=a.work.resolve();work.mkdir(parents=True,exist_ok=True)
    status=work/'status.json';status.unlink(missing_ok=True)
    cc=shlex.split(a.cc);flags=shlex.split(a.flags);link=shlex.split(a.link)
    probe=work/'caller.c';probe.write_text(PROBE)
    caller=work/'caller.o'
    run([*cc,*flags,'-fno-lto','-I'+str(root/'tests'),'-c',str(probe),'-o',str(caller)],work/'caller-build.log')
    archive=a.archive.resolve();baseline=work/'natural'
    run([*cc,'-fno-lto',str(caller),str(archive),*link,'-o',str(baseline)],work/'natural-link.log')
    original=run([str(baseline),'-1'],work/'natural.log')
    def records(output):
        out={}
        for line in output.decode('ascii').splitlines():
            f=line.split();assert len(f)==8
            key=(int(f[0]),int(f[1],16),int(f[2]),int(f[3]));assert key not in out
            out[key]=(int(f[4],16),int(f[5]),int(f[6]),int(f[7]))
        return out
    natural=records(original.stdout);assert len(natural)==45*4*32
    sites=[]
    for site,name in enumerate(('expf-subnormal','exp2f-subnormal','atanf-final','cbrtf-final','cbrtf-subnormal')):
        filename='explog.c' if site<2 else 'atan2.c' if site==2 else 'float_cbrt.c'
        source=(root/'src/elementary'/filename).read_text()
        positives=None
        for deleted in (False,True):
            label=name+('-deleted' if deleted else '-control');path=work/(label+'.c');path.write_text(inject(source,site,deleted))
            obj=work/(label+'.o');binary=work/label
            run([*cc,*flags,'-fno-lto','-I'+str(root/'src/elementary'),'-c',str(path),'-o',str(obj)],work/(label+'-compile.log'))
            run([*cc,'-fno-lto',str(caller),str(obj),str(archive),*link,'-o',str(binary)],work/(label+'-link.log'))
            r=run([str(binary),str(site)],work/(label+'.log'),1 if deleted else 0)
            if deleted:
                assert b'force-check: flags ' in r.stderr,'deletion failed outside intended flag assertion'
                mutants=records(r.stdout);assert positives and mutants.keys()==positives.keys(),'missing deletion rows'
                deletion_rows=[]
                for key,record in mutants.items():
                    assert key in natural and record[0]==natural[key][0] and record[2]==1,'deletion changed result or missed checkpoint'
                    assert record[1]==key[3],'deletion did not lose exactly the forced flags'
                    deletion_rows.append({'key':key,'result':record[0],'flags':record[1],'required_flags':natural[key][1],'hits':record[2],'pre_injection_flags':record[3]})
                continue
            positives=records(r.stdout)
            assert len(positives)==(2 if site<2 else 4 if site==2 else 3)*4*(8 if site<2 else 16)
            for key,record in positives.items():
                assert key in natural and record[:2]==natural[key][:2] and record[2]==1,'calibration changed results/state or missed site'
            assert positives
        sites.append({'site':name,'positive_rows':len(positives),'deletion_rejected_at_flags':True,'deletion_rows':deletion_rows,
                      'pre_injection_flag_masks':sorted({v[3] for v in positives.values()})})
    version=run([*cc,'--version'],work/'compiler-version.log').stdout.decode('utf-8',errors='strict')
    result={'compiler_command':cc,'compiler_version':version,'compile_flags':flags,'link_flags':link,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'actual_exit':0,'natural_rows':len(natural),'calibration':'test-only call-site flag clearing, not a natural public deletion witness','sites':sites,
            'runtime_sources_sha256':{n:hashlib.sha256((root/'src/elementary'/n).read_bytes()).hexdigest() for n in ('explog.c','atan2.c','float_cbrt.c')}}
    status.write_text(json.dumps(result,sort_keys=True)+'\n')
    print('four force flags: natural public state rows',len(natural),'; all five calibrated call-site deletions rejected (test-only instrumentation)')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--cc',default='cc');p.add_argument('--flags',required=True);p.add_argument('--link',required=True)
    try:check(p.parse_args())
    except (AssertionError,OSError,ValueError,subprocess.SubprocessError) as error:
        raise SystemExit('four force flags: FAIL: '+str(error))
