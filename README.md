# Ghoti.io Math

Deterministic elementary functions that give the same bits on every host. It is part of the
[Ghoti.io suite](https://github.com/Ghoti-io/suite).

## What is implemented

`gmath_sin`, `gmath_cos`, `gmath_tan`, `gmath_atan2`, `gmath_exp`, `gmath_log`, `gmath_pow` and
`gmath_hypot` on `double` (`ghoti.io/math/elementary.h`): within 1 ulp of the true value
(measured at most 0.57 ulp, apart from results in the subnormal range of `exp`, `pow` and
`hypot`, which are rounded twice and are within 0.75), the same bits on every target, using
IEEE operations in a fixed order and integer arithmetic, with the special values and exceptions
of C99 Annex F.

And the functions of `<math.h>` that C specifies exactly (`ghoti.io/math/basic.h`), so that a
shape library takes nothing from libm: `gmath_sqrt` (correctly rounded: the target's instruction
where it rounds correctly, a portable method with the same bits elsewhere, both gated),
`gmath_floor`, `gmath_ceil`, `gmath_trunc`, `gmath_round` (half away from zero), `gmath_rint`
(half to even, whatever the rounding mode), `gmath_fabs`, `gmath_copysign`, `gmath_scalbn`,
`gmath_ldexp`, `gmath_frexp` and `gmath_ilogb`. There is no `fma`: fusing is forbidden (AD-17).
`make check-libm` refuses every libm symbol, in this library and in the shape libraries.

* `sin`, `cos`, `tan`: the argument is reduced exactly (Cody-Waite below 2^30 where that is
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
* `hypot`: the squares as exact sums, the correctly rounded `gmath_sqrt` of their sum and one
  correction from the exact residual, so there is no host `sqrt`, and no spurious overflow or
  underflow.
* `sqrt`: see `documentation/design.md`; the portable method is Newton's iteration from a table
  start, the estimate of Markstein's with an exact residual, and a last exact test of the residual
  that makes the rounding right.

`make bench` times all of them against the host libm, per argument range.

Exact binary remainder is available as `gmath_fmod(double, double)` and
`gmath_fmodf(float, float)` in `basic.h`. Both keep the dividend's sign,
including zero, and compute subnormal results without rounding or raising an
exception. Infinite dividends and zero divisors raise invalid; NaNs are
canonicalized, and a signaling NaN in either argument raises invalid. Neither
function changes `errno` or depends on the rounding mode. These are the first
remainder additions toward broader libm coverage.

`gmath_fmin`, `gmath_fmax`, `gmath_fminf` and `gmath_fmaxf` select exact input
values, with negative zero preferred for minimum and positive zero for maximum.
A single quiet NaN returns the other number; two quiet NaNs return the canonical
NaN; a signaling NaN in either argument raises invalid and returns the canonical
NaN. These functions preserve `errno` and the rounding mode. Other float
elementary functions beyond `gmath_log2f` are not yet provided. The ongoing scope and verification
limits are recorded in `documentation/libm-progress.md`.

`gmath_log2`, `gmath_log10` and `gmath_log2f` add binary/decimal logarithms,
with a one-ulp contract in their result format under round-to-nearest. Binary
powers have exact `log2`/`log2f` results without inexact. The binary64 paths
retain the existing high-precision logarithm and split reciprocal products;
the float path uses an exact table product and a short series in double.
Zeros raise divide-by-zero and return -infinity; negative values raise invalid;
NaNs use the canonical policy. Other positive finite values may raise inexact.

And exact conversion between decimal and `double` (`ghoti.io/math/decimal.h`):
* `gmath_decimal_parse` reads the decimal grammar CSS, SVG and `strtod` share.
* `gmath_decimal_to_double` takes digits and a power of ten.
* Both round correctly, ties to even, for an input of any length, and return IEEE 754's inexact,
  overflow and underflow as flags.
* `gmath_decimal_shortest` gives the fewest digits that read back to the same `double`, the
  nearest when there is a choice.
* None of them reads the locale or the rounding mode, allocates, or raises an exception, so the
  same text gives the same bits everywhere. See `documentation/design.md`, "Decimal conversion".

Also `gmath_version_string()`, `gmath_version_number()` and `gmath_result_string()`, and the gates every
library in the shape family runs in `make test`.

### How the accuracy is checked

`tests/corpus/` holds the oracle's answers for every function: 19,431 inputs each for
`sin`, `cos` and `tan` and 7,798 to 15,544 for the others, with the correctly rounded
result and the exact value's distance from it (for `sqrt`, the rounding functions and the exponent
functions, which have one correct answer, 2,341 to 47,036 inputs and the answer itself, which the test
requires to the bit), written by MPFR (through gmpy2,
cross-checked against mpmath) in a pinned container (`tools/oracle/containers/mpfr`; `make
oracle-build`, `make oracle-version`). The special values of Annex F are in it too, checked
in the generator against a second statement of the rules.
`make test` checks every result against it with no container, and checks the
hash of all the results against `tests/corpus/trig.hash` (the value over all nineteen, and one per function), the value the other
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

The remainder corpus has a separate, container-free oracle:
`tools/oracle/gen_corpus_remainder.py` uses exact rational arithmetic to compute
`x - trunc(x/y)*y`, and verifies that the result is exactly representable.
`make check-remainder-corpus` reproduces the committed files and checks a fresh
sample in every rounding mode. `make check-planted-remainder` verifies that
deliberate defects fail the tests. The remainder result hashes are supplemental
entries in `trig.hash`, preserving the existing aggregate hash.

To regenerate the committed remainder files from the library directory:

```bash
python3 tools/oracle/gen_corpus_remainder.py --out tests/corpus --seed 20261026 --count 3000
make corpus-hash-update
```

Pass the same `PREFIX` used for the build when updating the hash.

Extrema use the independent rational/IEEE oracle in
`tools/oracle/gen_corpus_extrema.py`. `make check-extrema-corpus` reproduces its
committed files and checks fresh cases in all rounding modes;
`make check-planted-extrema` checks implementation and hash defects. To
regenerate those committed files, run:

```bash
python3 tools/oracle/gen_corpus_extrema.py --out tests/corpus --seed 20261026 --count 3000
make corpus-hash-update
```

Base-logarithm references use the pinned MPFR image, cross-checked against
mpmath, with direct binary32 rounding for float results. `make
check-logbase-oracle` checks a fresh sample and regenerates the reciprocal
constants for comparison when the image is available. Without it, the fresh
check skips loudly and the committed corpus still runs;
`GHOTI_ORACLE_REQUIRED=1` makes the missing image a failure. Regenerate with
`make oracle-fit-logbase oracle-logbase corpus-hash-update`, passing the build's
`PREFIX`. `make check-planted-logbase` checks implementation defects, the oracle
self-check, wrong hashes and omitted probe entries.

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
