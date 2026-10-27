# Libm gap closure

Implementation stays within math while independent work proceeds in the other
libraries. New APIs prepare later migrations; no consumer is migrated here.
The deterministic contracts in the public headers remain authoritative.

## Completed capabilities

- Exact binary64/binary32 remainder: `gmath_fmod` and `gmath_fmodf`, added in
  commit `39424c29c1caacca54d44122ee69069ae2004dfc`.
- Exact binary64/binary32 extrema: `gmath_fmin`, `gmath_fmax`, `gmath_fminf`
  and `gmath_fmaxf`. Numeric results preserve input bits; minimum orders -0
  below +0. One quiet NaN yields the other number; signaling NaNs yield the
  canonical NaN and raise invalid.

## Upcoming project-used gaps

1. Binary logarithm/exponential support (`log2`, `log2f`, `exp2`) and `log10`.
2. Cube root (`cbrt`).
3. Float rounding, square root and trig operations used by WebAssembly, model,
   and CJelly. Simple wrappers require proof that narrowing remains exact or
   correctly rounded; float elementary accuracy is a separate target.
4. Broader real-function coverage: inverse trig, hyperbolic functions,
   cancellation-safe `log1p`/`expm1`, remainder families, adjacent values and
   integer conversions, followed by special functions as justified.

## Notes for the next numerical phase

The current `src/elementary/explog.c` has precision reserve in `log_dd`.
Base conversion should retain that double-double result and a split reciprocal
of ln(2) or ln(10), rather than multiplying the already rounded public log.
A one-ulp target still requires a new error budget and MPFR reference evidence.

For exp2, a dedicated reduction by exact multiples of 1/128 can reuse the
existing exponential table and reconstruction polynomial. Converting only the
small residual with split ln(2) avoids introducing large-argument error through
`exp(x * rounded_ln2)`. Exact powers of two and the -1075/-1074/-1022/1024
boundaries need explicit handling and exception tests. Float log2 verification
must use binary32 rounding and ulp spacing, not a binary64 corpus tolerance.

## Verification and remaining limits

The new exact APIs have independent committed reference corpora, fresh samples,
raw-bit NaN/zero/infinity tests, all four rounding modes, errno/exception-state
checks, mutation checks and supplemental result hashes. Existing hashes remain
unchanged. Build/test validation and independent reviews accompany each commit.

The suite's cross-target scripts compare the legacy aggregate and do not yet
enforce these supplemental entries. Cross-target validation of the new APIs
remains pending; host verification must not be represented as cross-platform
execution evidence. Integrating that gate requires permission to edit suite.

Scalar call benchmarks compare against host libm on identical input ranges.
Extrema are approximately tied on the measured host. Remainder is faster in
some float/subnormal cases and slower in some double ranges; there is no claim
of an overall libm performance win. Compiler-inlined, shared-library, vector,
and application workloads still need separate measurements.

Standard C types and semantics also need an explicit compatibility boundary:
long double, complex arithmetic, full fenv/errno compatibility and FMA are not
covered by the current library. Existing `gmath_rint` deliberately uses ties to
even regardless of the host rounding mode.
