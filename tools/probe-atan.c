/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 */
#include "../tests/atan_corpus.h"
int main(int argc,char **argv) {
  if(argc!=2) {fputs("usage: probe-atan DIRECTORY\n",stderr);return 2;}
  return a64_probe(argv[1],1);
}
