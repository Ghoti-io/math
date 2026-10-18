# Ghoti.io Math

Deterministic elementary functions that give the same bits on every host. It is part of the
[Ghoti.io suite](https://github.com/Ghoti-io/suite).

## What is implemented

`gmath_sin`, `gmath_cos`, `gmath_tan`, `gmath_atan2`, `gmath_exp`, `gmath_log`, `gmath_pow` and
`gmath_hypot` on `double` (`ghoti.io/math/elementary.h`): within 1 ulp of the true value
(measured at most 0.57 ulp, apart from results in the subnormal range of `exp`, `pow` and
`hypot`, which are rounded twice and are within 0.75), the same bits on every target, using only
`+ - * /` and integer arithmetic, with the special values and exceptions of C99 Annex F.

* `sin`, `cos`, `tan`: the argument is reduced exactly (Cody-Waite below 2^20 where that is
  provably as good, Payne-Hanek otherwise), so a huge argument near a multiple of pi/2 is as
  accurate as any other. The reduced argument is looked up in a 16 KB table (sin, cos, tan and
  cot of its leading six bits) and corrected by a short polynomial in double.
* `exp`: Tang's table of 2^(j/128) as double-doubles, a reduction of the argument by a split
  ln2/128, a cubic-times-r^2 polynomial.
* `log`: Tang's table of 128 short multipliers (so that `c m - 1` is formed exactly in two parts),
  with the two rows around 1 holding `c = 1` so that `log` near 1 keeps its relative accuracy.
* `pow`: `exp(y log x)` with the logarithm as a double-double accurate to 2^-67, so a result
  that is exactly representable (`3^5`, `2^-1074`) is returned exactly.
* `atan2`: the octant reflection added in a double-double to a table-driven arctangent of the
  quotient, whose remainder is formed exactly.
* `hypot`: the squares as exact sums, the square root by Newton's iteration from a table start
  and one correction from the exact residual, so there is no host `sqrt`, and no spurious
  overflow or underflow.

`make bench` times all eight against the host libm, per argument range.

Also `gmath_version_string()` and `gmath_version_number()`, and the gates every
library in the shape family runs in `make test`.

### How the accuracy is checked

`tests/corpus/` holds the oracle's answers for every function: 19,431 inputs each for
`sin`, `cos` and `tan` and 7,798 to 15,544 for the others, with the correctly rounded
result and the exact value's distance from it, written by MPFR (through gmpy2,
cross-checked against mpmath) in a pinned container (`tools/oracle/containers/mpfr`; `make
oracle-build`, `make oracle-version`). The special values of Annex F are in it too, checked
in the generator against a second statement of the rules.
`make test` checks every result against it with no container, and checks the
hash of all the results against `tests/corpus/trig.hash` (the value over all eight, and one per function), the value the other
targets must print (`suite/tools/xarch/shape.sh`, `suite/tools/xwin/shape.sh`).
When the container is present `make test` also checks a fresh sample drawn that
day; `GHOTI_ORACLE_REQUIRED=1` makes its absence a failure instead of a printed
SKIPPED. `make check-planted` builds the library with a coefficient perturbed, a
reduction branch skipped, a table entry changed and some hundreds of other defects and requires each to fail.
`make oracle-fit` regenerates the reduction constants and the tables and
polynomials (`src/elementary/trig_tables.h`, `trig_kernel_table.h`, `explog_tables.h`,
`atan2_table.h`, `hypot_table.h`); `make oracle-corpus` and
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
