/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 */
#include "../tests/long_scale_probe.h"
int main(int argc, char ** argv) {
  if (argc > 2) {
    return 2;
  }
  const char * directory = argc == 2 ? argv[1] : "tests/corpus";
  int d = ls_probe(directory, 64, 1), f = ls_probe(directory, 32, 1);
  return d || f ? 1 : 0;
}
