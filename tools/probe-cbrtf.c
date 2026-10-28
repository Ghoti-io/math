/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff */
#include "../tests/cbrtf_probe.h"
int main(int argc,char **argv) {
  if (argc>2) return 2;
#ifdef GMATH_CBRTF_REFERENCE
  fputs(GMATH_CBRTF_BASELINE_IDENTITY,stdout);
#endif
  const char *directory=argc==2?argv[1]:"tests/corpus";
  uint64_t hash=0;uint64_t mode_hashes[4]={0};int status=cf_run_record(directory,1,&hash,mode_hashes);
  if (!status&&!strcmp(directory,"tests/corpus")&&(hash!=GMATH_CBRTF_PINNED_HASH||!cf_pinned_modes(mode_hashes))) {
    fputs("cbrtf pinned result hash differs\n",stderr);return 1;
  }
  return status?status:cf_guard_witness();
}
