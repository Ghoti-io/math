/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff */
#include "../tests/remaining_probe.h"
int main(int argc, char ** argv) {
  if (argc != 2)
    return 2;
  return remaining_probe(argv[1], 1, 1);
}
