# Inverse sine and cosine

`gmath_asin`, `gmath_acos`, `gmath_asinf` and `gmath_acosf` complete the
Float/Double inverse circular function names alongside atan and atan2. They are
one capability family, with one shared implementation and verification pass.
Consumers remain unchanged. Name coverage does not imply full libm behavioral
compatibility.

## Contract

The numerical target is one result ULP under nearest rounding. General correct
rounding, directed numerical accuracy, long double, full libm errno behavior,
and manually inconsistent floating-point controls are outside this contract.
The implementation never writes rounding controls. It preserves errno, mode,
incoming standard flags and coherent nontrapping control settings.

| Inputs | asin | acos | New flags |
| --- | --- | --- | --- |
| Quiet NaN | Canonical positive quiet NaN | Same | None |
| Signaling NaN | Canonical positive quiet NaN | Same | Invalid |
| Magnitude above one, including infinity | Canonical positive quiet NaN | Same | Invalid only |
| Signed zero | Input bits | Nearest pi/2 | None for asin; inexact for acos |
| +1 | Nearest pi/2 | +0 | Inexact for asin; none for acos |
| -1 | Nearest -pi/2 | Nearest pi | Inexact |
| Other valid input | Principal signed angle | Principal nonnegative angle | Inexact; underflow only for subnormal asin output |

For asin, magnitudes below 2^-30 (Double) or 2^-12 (Float) return their input
bits in every standard mode. For acos, magnitudes below 2^-60 or 2^-28 return
nearest pi/2 in every mode. Endpoint constants likewise use nearest bits in all
modes. These are deterministic special contracts, not directed libm rounding.

## Independently derived shared calculation

Integrating the binomial series for `(1-x*x)^(-1/2)` gives

```
asin(x) = x * sum(c[n] * x^(2*n))
c[0] = 1
c[n+1] / c[n] = (2*n+1)^2 / (2*(n+1)*(2*n+3))
```

For magnitudes at most one half, 33 positive terms are evaluated in compensated
Double arithmetic. The exact rational coefficient generator supplies split
high/low values. The omitted tail relative to x is at most
`c[33] * (1/4)^33 / (1-1/4) < 2^-74`. The gate checks coefficient regeneration.
This truncation bound is distinct from the rounding errors of the C evaluation;
it is not an all-input correct-rounding certificate.

For larger magnitudes `a`, `z=(1-a)/2` is exact by Sterbenz subtraction and
power-of-two scaling. Let `r=sqrt(z)`. An error-free product supplies the root
residual `z-r*r`; its first-order correction through asin is
`(z-r*r)/(2*r*sqrt(1-z))`. Both native and portable existing root backends are
supported. Then `2*asin(sqrt(z))` gives acos(a), or is subtracted from a split
pi/2 for asin(a). Negative acos uses a split pi subtraction. No old runtime
module or table is changed. In particular this does not compose two separately
rounded public atan2/sqrt answers or subtract nearly equal angles at acos(+1).

The correction's neglected quadratic terms and compensated arithmetic need a
separate rounding budget; the tail inequality alone does not prove a global
one-ULP bound. The independent reference populations below support the stated
numerical contract. No exhaustive proof or exhaustive input scan is claimed.
Float evaluates the same bounded Double calculation and narrows once; rare
Double/Float double-rounding does not justify a correct-rounding claim.

## References and gates

`tests/corpus/inverse-trig.corpus` retains all 7,770 compact raw inputs and both
per-input answers, flags and outward real-error intervals. The complete SHA256
pin is `inverse-trig.sha256`. Seed 20261101 uses 512 iterations per format, each supplying
a raw-exponent and a uniform-domain draw; both signs are retained, and all resulting seeded answers are
literal. Structured inputs include all endpoint neighbours through 128 steps,
tiny/subnormal/normal seams, signed zeros, NaNs, infinities and dyadic grids.
No full deterministic grids or raw performance JSON files are added.

The generator decodes inputs as exact rationals. Directed MPFR at 1200 bits
(escalating to 2400 when necessary) supplies enclosing result bounds; mpmath at
higher precision supplies independent output agreement. Exact rational packing
must select identical nearest targets. Outward residuals use units of 2^-30 ULP;
the checker closes both ends of each interval and handles the half-spacing side
of binade boundaries. Neither generator reads candidate coefficients or source.
Byte-identical regeneration is checked separately from a new seed/larger sample.

Run `make check-inverse-trig` for the complete-payload/population check, all four
public functions, selected all-mode/all-incoming-flag state checks, coefficient
regeneration and deliberate numerical/state/reference defects. Each temporary
defect object and binary is removed after the gate; diagnostic logs remain.
`make test` includes this gate. The new unit binary is `testInverse_trig`.
Standalone `corpus-hash` includes all four supplemental hashes; the original
87 hashes and legacy aggregate remain unchanged. The hash client introduces
no fenv/libm link dependency. Use `make prepare-corpora` before building/running
standalone cross probes, as documented in the README.

The committed population's closed sampled bounds are below 0.5000 ULP for all
four APIs. A separate 36,356-input seed/count sample also passes, with maxima
below 0.5000 ULP. These are sampled measurements, not global maxima. General
platform coverage, physical cross-target execution, Windows/LLP64, exhaustive
input/environment coverage and application performance are not claimed here.
No new benchmark or Valgrind campaign is part of this family; earlier failed
partial Valgrind scopes remain failed.

Reproduce independent complete-byte regeneration with the pinned image installed:

```sh
make check-inverse-trig-oracle
```

This opt-in target uses the normal oracle image/version pin, generates into
`build/linux/release/oracle-inverse-trig`, and compares both complete files. It
fails if the instrument is unavailable; it does not replace committed answers.
Reproduce the separate larger population and run its public-API checks with:

```sh
python3 tools/oracle/oracle.py inverse_trig --out build/inverse-trig-fresh --seed 20261102 --count 4096
make build/linux/release/apps/testInverse_trig
GMATH_INVERSE_TRIG_CORPUS_DIR=build/inverse-trig-fresh build/linux/release/apps/testInverse_trig
```

The 36,356-row larger sample's closed bounds in asin/acos/asinf/acosf order are
0.499881586 / 0.499854333 / 0.499906419 / 0.499996839 ULP. GCC16 and Clang nearest
numerical and selected all-mode state checks pass; default and forced-portable
root backends produce identical supplemental hashes. Directed numerical accuracy
is still unclaimed. ASan/UBSan focused tests pass. Eighty-four additional signed
near-midpoint inputs selected solely from this independent larger population
are retained in the committed population (7,770 rows total); they strengthen
rounding coverage without removing any prior literal seeded answers.


## Completed integration checks

Complete GCC16 suite coverage accounts for all 104 default gates. The main run
invoked 259 tests in 37 binaries: 258 passed and one native32-long test skipped
explicitly on LP64. The first cold command stopped at the explicit-header-include
rule. Adding the missing macros.h include to the generated coefficient header
left preprocessed implementation text and compiled object bytes unchanged.
Completed gates were reused with that identity evidence; remaining gates and
all main units then passed. The first failed command is not a passing run.
The symbol/header check now runs first in the default gate list, with the same
104 gates retained, to catch integration mistakes before expensive controls.

The new corpus and its SHA manifest force LF through Git attributes. A checkout
with core.autocrlf=true preserves their pinned bytes. Diagnostic records are
retained and temporary defect build files are reclaimed after verification.
