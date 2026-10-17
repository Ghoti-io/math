# Ghoti.io Math

Deterministic elementary functions that give the same bits on every host. It is part of the
[Ghoti.io suite](https://github.com/Ghoti-io/suite).

## What is implemented

`gmath_sin`, `gmath_cos` and `gmath_tan` on `double` (`ghoti.io/math/elementary.h`):
within 1 ulp of the true value for every finite argument up to `DBL_MAX`
(measured at most 0.53 ulp over the corpus), the same bits on every target, using only
`+ - * /` and integer arithmetic. The argument is reduced exactly (Cody-Waite below 2^20 where
that is provably as good, Payne-Hanek otherwise), so a huge argument near a
multiple of pi/2 is as accurate as any other. The reduced argument is then
looked up in a 16 KB table (sin, cos, tan and cot of its leading six bits) and
corrected by a short polynomial in double. `make bench` times the three
against the host libm.
`atan2`, `exp`, `log`, `pow` and `hypot` are still to come.

Also `gmath_version_string()` and `gmath_version_number()`, and the gates every
library in the shape family runs in `make test`.

### How the accuracy is checked

`tests/corpus/` holds 19,431 inputs per function with the correctly rounded
result and the exact value's distance from it, written by MPFR (through
gmpy2, cross-checked against mpmath) in a pinned container
(`tools/oracle/containers/mpfr`; `make oracle-build`, `make oracle-version`).
`make test` checks every result against it with no container, and checks the
hash of all the results against `tests/corpus/trig.hash`, the value the other
targets must print (`suite/tools/xarch/shape.sh`, `suite/tools/xwin/shape.sh`).
When the container is present `make test` also checks a fresh sample drawn that
day; `GHOTI_ORACLE_REQUIRED=1` makes its absence a failure instead of a printed
SKIPPED. `make check-planted` builds the library with a coefficient perturbed, a
reduction branch skipped and a dozen other defects and requires each to fail.
`make oracle-fit` regenerates the reduction constants and the kernel's table and
polynomials (`src/elementary/trig_tables.h`, `trig_kernel_table.h`); `make oracle-corpus` and
`make corpus-hash-update` regenerate the corpus and its hash after a deliberate
change.

## Building

```bash
make test PREFIX="$PWD/.local"
make install PREFIX="$PWD/.local"
```

Dependencies are found by pkg-config and nothing else; a missing one is an
error that names the fix. The libraries this one needs: cutil.

Determinism is a requirement, not a hope: every `double` stage builds with
`-ffp-contract=off` and no x87, and elementary functions come from `math`, not
libm. `make check-gates` shows each of those rules failing on a planted
violation.

## License

LGPL-3.0-only. See `COPYING` and `COPYING.LESSER`. Patches are not being
accepted at this time; see `CONTRIBUTING.md`.
