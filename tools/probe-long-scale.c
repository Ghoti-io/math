/* SPDX-License-Identifier: LGPL-3.0-only
 * Copyright (C) 2026 Corey Pennycuff
 */
#include "../tests/long_scale_probe.h"
static int raw_diagnostics(void) {
  fenv_t saved;
  int error = errno;
  if (fegetenv(&saved) || fesetround(FE_TONEAREST) ||
      feclearexcept(FE_ALL_EXCEPT)) {
    return 2;
  }
  uint64_t input = 1, output;
  double x, y;
  memcpy(&x, &input, sizeof x);
  int before_all = fetestexcept(FE_ALL_EXCEPT);
  int before_standard = fetestexcept(LS_STANDARD_EXCEPTIONS);
  errno = 733;
  double (*volatile fn)(double, long) = gmath_scalbln;
  y = fn(x, LONG_MIN);
  int actual_errno = errno, after_all = fetestexcept(FE_ALL_EXCEPT);
  int after_standard = fetestexcept(LS_STANDARD_EXCEPTIONS);
  memcpy(&output, &y, sizeof output);
  printf("longscale.diagnostics long%u all-mask %x standard-mask %x "
         "before-all %x before-standard %x after-all %x after-standard %x "
         "result %016" PRIx64 " errno %d\n",
         LONG_MAX == INT32_MAX ? 32u : 64u, FE_ALL_EXCEPT,
         LS_STANDARD_EXCEPTIONS, before_all, before_standard, after_all,
         after_standard, output, actual_errno);
  int status = fesetenv(&saved);
  errno = error;
  return status ? 2 : 0;
}
int main(int argc, char ** argv) {
  if (argc == 2 && !strcmp(argv[1], "--diagnostics")) {
    return raw_diagnostics();
  }
  if (argc > 2) {
    return 2;
  }
  const char * directory = argc == 2 ? argv[1] : "tests/corpus";
  int d = ls_probe(directory, 64, 1), f = ls_probe(directory, 32, 1);
  return d || f ? 1 : 0;
}
