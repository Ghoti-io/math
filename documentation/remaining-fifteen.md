# Final fifteen Float/Double entry points

The new `gmath_` names are `powf`, `erf`/`erff`, `erfc`/`erfcf`,
`tgamma`/`tgammaf`, `lgamma`/`lgammaf`, `nan`/`nanf`,
`nexttoward`/`nexttowardf`, and `fma`/`fmaf`. They preserve errno, incoming
standard exception flags, rounding mode and coherent nontrapping controls.
Production never writes controls. Returned NaNs are canonical positive quiet NaNs.

The private MP256 core uses eight 32-bit significand limbs and a separate
exponent/sign. Its operations truncate toward zero; guard-word sticky
subtraction preserves cancellation and large-gap predecessors. Exact Fraction
calibration requires equality for 2,620 binary64-derived and 1,040 raw256 cases.
Another 556 Fraction cases cover nearest packing ties, subnormal transitions
and overflow. Constants come from this project's Machin pi, integer square
root, logarithm series and Bernoulli recurrence. The coefficient gate verifies
bytes, outward 600-bit construction enclosures, rational series/continued
fraction bounds, and conservative dispatch-tail inequalities. This does not
replace independent measurement of arithmetic error.

Erf uses 160 Maclaurin terms through magnitude 4, then the erfc complement.
Erfc above 4 uses 256 levels of Laplace's continued fraction. Positive gamma
arguments shift to at least 64 using a product recurrence and 64 Stirling terms.
Negative arguments use exact fractional reduction, a sine-of-pi series and
reflection. Lgamma returns the logarithm of absolute gamma without touching
signgam; a guarded platform regression checks that side effect separately.
MP256 retains cancellation near lgamma zeros. Error/gamma and powf have a
measured nearest one-result-ULP target, without global correct-rounding or
ordinary directed-accuracy claims. Other finite error/gamma calls add inexact,
including factorials except the explicit gamma cases at inputs 1 and 2. Lgamma
at inputs 1 and 2 returns exact positive zero. Range flags occur at rounded
result boundaries, with tininess after rounding. Conservative dispatch tails
are erf magnitude 7, erfc magnitude 28, positive tgamma 172, and negative
noninteger tgamma at or below -256. Negative integer poles dispatch first.

Powf classifies raw Float operands, widens finite values by integer packing,
reuses this project's unchanged Double pow, and packs the final Float in
integers. Signaling NaNs take priority over unit-base/zero-exponent identities;
quiet-NaN identities follow the existing power ladder. Narrowing contributes
Float inexact/range flags explicitly. Exact dyadic powers dispatch before the
Double approximation: strip the binary exponent, take any exact power-of-two
root of the odd significand, and bound the remaining odd power to 24 bits.
Reciprocals with a nonbinary odd base are not dyadic. Exact Float subnormals
therefore acquire no false underflow in directed modes; every remaining tiny
ordinary result requires underflow/inexact. Existing elementary algorithms never
fuse operations. The explicit FMA APIs use 132 limbs (4224 bits) for the exact
product-plus-sum and round once in each standard mode. Overflow is determined
after rounding at unbounded exponent; underflow needs an inexact, rounded tiny
result. Exact cancellation gives negative zero only in downward mode, while
same-signed zero terms retain their sign. A finite huge product followed by an
infinite addend has no intermediate overflow. Inf*zero is invalid even with a
quiet NaN addend. These APIs enable no contraction or hardware FMA elsewhere.

Nexttoward decodes native binary64, binary80, binary128 and canonical IBM
double-double object bytes without long-double arithmetic or direction
narrowing. Equal values retain the destination zero sign. Neighboring tiny
values use the existing nextafter underflow/inexact policy. Binary80 unnormal
and pseudo-special encodings are invalid; pseudo-denormals denote their
exponent-1 canonical values. An integer-only native80 ABI caller checks both
signs, pseudo/canonical equivalence, tiny directions, zero equality and signaling
encodings. On GCC/Clang native80 SysV x86-64, integer ABI tail thunks avoid
compiler/sanitizer x87 parameter copies. Other ABIs use byte extraction. Raw
test directions are constructed in all four supported native formats without
floating conversion. Private word helpers execute 75 synthetic representation
vectors in both result widths, including finite significands, exponent
extremes, low DD components, infinities and NaNs. These host synthetic checks
are distinct from executing another format's native ABI/runtime. NaN
constructors ignore every tag, including NULL and inaccessible pointers,
without reads, allocation, locale effects or new flags.

`make check-remaining` authenticates the complete canonical payload/SHA and
reproducible population, validates closed ULP intervals, requested paths/counts,
fifteen pinned hashes, exact primitives, decoder controls and caller state.
The native `LoadedRowsAndCallerState` unit checks the rows it loads; full SHA
and population authentication belongs to this mandatory Python gate or the
authenticated fresh wrapper, not the standalone unit. Selected state keys
include both pow operands, exponent parity/dispatch region and result flags;
FMA keys include all operands, result flags and mode. Representatives exercise
all four modes and all 32 requested incoming-flag subsets, comparing against
the actual flags observed after seeding (including incidental inexact).
Supported FTZ/DAZ combinations are checked. Compiled defects and malformed or
changed references must fail at intended assertions, never through build
failure or crash. All critical Python runners reject optimized execution;
actual `-O` and `PYTHONOPTIMIZE` invocations calibrate that rejection before
success or output. The standalone hash client hashes canonical-nearest FMA
rows and adds no fenv runtime dependency. The native default suite adds only
`check-remaining`: 108 gates including the previous 107.

The explicit required preflight `make check-remaining-oracle` fails if its
instrument is unavailable. It regenerates MPFR directed 1200/2400-bit bounds
and independent mpmath results. FMA additionally requires exact Fraction
agreement with MPFR at 5000 bits before packing; 1200 bits cannot resolve all
extreme alignment tails. Seam selection covers 20 negative pole intervals,
both roots where present, range boundaries and immediate raw neighbors.
Every NaN payload bit is covered with both signs in relevant operands.

The extended selector ranks fixed, predeclared candidates with directed MPFR
256-bit intervals, taking the best two per declared region. Its catalog records
candidate/finite counts and conservative midpoint distances. It adds 46 unary
centers across global fixed-raw/grid, switch-4, CF, recurrence and negative
reflection regions, plus eight finite powf pairs from global, near-unit,
negative-odd and tiny-result regions. Immediate input neighbors are appended
without changing any earlier row or answer. Float tgamma's recurrence region
uses 32 because values near 64 overflow. This finite search is reproducible
midpoint evidence, not an exhaustive or globally hardest-case claim. The final
independent reference generator certifies every appended result anew.

Fresh work has two explicit steps; validation never auto-starts a container:

```sh
python3 tools/run-remaining-oracle.py --out build/fresh-remaining --seed 20261110 --count 1024
make check-remaining-fresh REMAINING_FRESH_DIR=build/fresh-remaining REMAINING_FRESH_SEED=20261110 REMAINING_FRESH_COUNT=1024
```

The wrapper authenticates requested seed/count, full population/SHA, actual
loaded path/row count, numerical cells and state. Missing data is a failure.
The old 107 result sets and legacy aggregate remain unchanged; the fifteen new
sets form the appended overlay. Evidence from the earlier implementation
attempts is retained separately from the review-fix validation records.

Review-fix validation used 17,908 canonical rows and 44,783 independent larger
rows (seed 20261110, count 1024), retaining every earlier answer as a byte-exact
prefix. Maximum measured closed-cell error was 0.5 ULP. Each canonical probe
made 131,264 selected state calls; the larger probe made 136,512. Ten native
tests, 75 synthetic decoder vectors in both result widths, 14 actual optimized
Python rejection invocations, and 30 compiled defect controls passed. The nine
explicit exact-power cases additionally exercise all four modes and all 32
seed requests. Focused GCC, Clang and ASan/UBSan checks passed; the prior 107
hashes and legacy aggregate remain unchanged. One cold default GCC16 full
suite exits zero: 108 gates, 41 main binaries and 284 tests, with 283 passes
and one expected native32-long skip. All ten new family tests pass. The
frozen tracked bytes and tree remain unchanged through test completion and
after temporary-build archival and removal. Other native ABIs and exhaustive
input spaces remain unrun.
