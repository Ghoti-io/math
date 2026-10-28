/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 */
#include "../tests/nearby_probe.h"
int main(int argc, char ** argv) {
  if (argc > 3)
    return 2;
  const char * directory = argc > 1 ? argv[1] : "tests/corpus";
  if (argc == 3 && strcmp(argv[2], "32") && strcmp(argv[2], "64"))
    return 2;
  return ((argc < 3 || !strcmp(argv[2], "64")) && nb_probe(directory, 64, 1)) ||
      ((argc < 3 || !strcmp(argv[2], "32")) && nb_probe(directory, 32, 1));
}
