/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 */
#include "../tests/positive_difference_probe.h"
int main(int argc,char ** argv) {
  if(argc<2||argc>3||(argc==3&&strcmp(argv[2],"64")&&strcmp(argv[2],"32"))) {
    fputs("usage: probe-positive-difference DIRECTORY [64|32]\n",stderr);return 2;
  }
  if(argc==3) {return ppd_probe(argv[1],!strcmp(argv[2],"64")?64u:32u,1);}
  return ppd_probe(argv[1],64,1)||ppd_probe(argv[1],32,1);
}
