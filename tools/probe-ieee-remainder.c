/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff */
#include "../tests/ieee_remainder_probe.h"
static int probe(const char *dir,unsigned width){ir_result r={0,0,0,0,0};if(ir_run(dir,width,1,&r))return 1;if(!strcmp(dir,"tests/corpus")&&!ir_pinned(r,width)){fputs("IEEE remainder pinned hash/count differs\n",stderr);return 1;}return 0;}
int main(int argc,char **argv){
 if(argc>3)return 2;
 const char *dir=argc>=2?argv[1]:"tests/corpus";
 if(argc==3){if(!strcmp(argv[2],"32"))return probe(dir,32);if(!strcmp(argv[2],"64"))return probe(dir,64);return 2;}
 return probe(dir,64)||probe(dir,32);
}
