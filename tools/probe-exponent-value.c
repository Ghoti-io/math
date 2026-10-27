/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 */
#include "../tests/exponent_value_probe.h"
int main(int argc, char ** argv) {
  if (argc > 2) {
    return 2;
  }
  const char * directory = argc == 2 ? argv[1] : "tests/corpus";
  int double_status = expv_probe(directory, 64, 1);
  int float_status = expv_probe(directory, 32, 1);
  return double_status || float_status ? 1 : 0;
}
