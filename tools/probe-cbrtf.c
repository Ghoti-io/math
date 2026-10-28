/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff */
#include "../tests/cbrtf_probe.h"
int main(int argc,char **argv) {if (argc>2) return 2;return cf_run(argc==2?argv[1]:"tests/corpus",1);}
