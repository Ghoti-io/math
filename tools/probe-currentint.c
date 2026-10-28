/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 */
#include "../tests/current_ir_probe.h"
int main(int argc, char ** argv) {
#if defined(GMATH_CURRENTINT_REFERENCE)
  if (argc==2 && !strcmp(argv[1],"--baseline-identify")) {fputs(GMATH_CURRENTINT_BASELINE_IDENTITY,stdout);return 0;}
#endif
  if (argc==2 && !strcmp(argv[1],"--identify")) {printf("currentint.long.bits %u\n",LONG_MAX==INT64_MAX?64u:32u);return 0;}
  if (argc==2 && !strcmp(argv[1],"--control-cases")) {return cr_x86_control_cases(1);}
  if (argc < 2 || argc > 3) {return 2;}
  if (argc==3 && strcmp(argv[2],"32") && strcmp(argv[2],"64")) {return 2;}
  unsigned width=argc==3?(unsigned)strtoul(argv[2],NULL,10):0;
  if (argc==3) {return cr_probe(argv[1],width,1);}
  return cr_probe(argv[1],64,1) || cr_probe(argv[1],32,1);
}
