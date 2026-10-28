# Libm gap closure

Implementation stays within math while independent work proceeds in the other
libraries. New APIs prepare later migrations; no consumer is migrated here.
The deterministic contracts in the public headers remain authoritative.

Current snapshot: 31 verified phases add 56 APIs, six performance optimizations
and certificate maintenance. Classic real-function name coverage is 76/171;
38 Float/Double additions remain, or 95 including long double. The phase
sections below retain historical counts and measurements.

## Current-mode integer conversion

Added `lrint`/`lrintf` and `llrint`/`llrintf`. Exact current-mode integer rounding
uses signed32/64 long and signed64 long long. Valid integral inputs add nothing;
valid fractions require IX only, including tiny inputs rounded to zero. Any NaN,
infinity or rounded destination-range failure returns MIN with invalid only;
range checks precede new IX. Caller errno/mode/incoming C flags survive under
the reviewed nearby reader's coherent nontrapping scope. Every old runtime
module and that reader remain byte-identical. A read-only scan found only audio's
independent host test lrint reference, which remains untouched.

Confirmed sequential full GCC14.2/GCC16.2 `make test` commands return zero.
Each main run invokes 242 tests/34 binaries: 241 pass and one native32-long unit
skips explicitly on LP64. Clang has the same counts unit-only. Five focused
ASan/UBSan tests give four passes/one skip; explicit-query gates/units pass.
All 80 old function sets and legacy `f5fa269eb60ee34f`/292711 remain unchanged;
new four sets bring total 84. Double forms hash `472e8d420d2337c2`/17739 each,
Float forms `1d43cc9f8126755f`/4861 each over common signed32-valid subsets.
Raw 34184/7042 rows contain all four-mode signed32/64 targets and drive 1145696 calls
per profile; actual flags/errno/mode/controls are asserted separately from
portable result/flag-class hashes. Seven complete SHA/LF gates and independent
Fraction/struct-decoded pinned MPFR rint targets agree; regeneration is identical.
Publication has ordinary exception rollback, not crash atomicity.

Six emulated targets match 84 sets default/portable and 24 O0/O2 native/query raw
profiles; twelve native clients link/run without libm. Native32 equality,
narrowing and premature-IX faults detect on i686/PowerPC32; LP64 runners skip
equivalent variants honestly. Real Python validation of compiled 32-bit probes
passes, and the old host-width counterfactual fails. The i686 raw caller lacks
fldl/flds argument loads. These are probes, not physical/full cross-target
GoogleTest claims. Three fresh complete 34184/7042 populations and larger 72184/
45041 populations pass both native compilers, including actual C++ path and
all 84-set overlays; larger has 3335824 state calls. No larger cross-target run.
Windows/LLP64, numerical soft-float, physical hosts, exhaustive input/environment
space and application timing remain unrun.

Independent mathematical/blind source reviews and follow-ups resolve findings.
The first full14 was deliberately interrupted for review, actual -2, never
passing; subsequent frozen full runs pass. Seventy loader/value negatives,
seven SHA corruptions, nine output/process faults, twelve hash/count/omission
controls, eighteen shared/four format-wide source/state faults plus conditional
SSE/x87/native32 controls and actual oracle/request/dispatch faults detect.
For this family, real force-only IX deletion witnesses preserve result bits but
lose IX. Earlier expf/exp2f/atanf/cbrtf narrow witness gaps remain unchanged.

Valgrind 3.24's five-test attempt exits 1 with four fenv failures/one skip and zero
reported memory errors/leaks; corpus early stops mean partial Memcheck scope.
Independent no-gmath volatile addition/division reproduces identical bits but
missing instrumented IX/IV; broader attribution remains inference. No assertions
weakened or passing Valgrind claim.

Four predeclared final runs retain 1408 cases, with 8 warmups / 401 alternating pairs
of 4096 equal inputs, integer timestamps, untimed per-input guards and checked
timed checksums. Ordinary own/host medians span 7.868–13.865 Double and 7.819–11.965
Float across GCC14 paths/modes/states, and 6.901–12.314 /7.081–10.805 GCC16.
Other ranges also trail. This exact portable baseline has a substantial measured
performance gap; no overall/application/platform win is claimed. Full proof,
failed-attempt history, limits, all case envelopes and machine-readable records
are in [current-integer-rounding.md](current-integer-rounding.md).

## Current-mode nearby integer rounding

Added `gmath_nearbyint`/`gmath_nearbyintf`: exact four-mode integral bits, signed
zeros and no new inexact; only signaling NaNs add invalid. Caller errno/mode/
incoming C flags are preserved. Old deterministic rint and every old runtime
module remain unchanged. Native six-target readers avoid libm; explicit/other
query ports use real platform fenv and may require its runtime. Coherent
nontrapping standard C controls are assumed; SPARC trap-type status and manually
inconsistent instruction modes are outside the guarantee.

Full GCC14.2/GCC16.2 gates return zero, 237 main tests/33 binaries each. Clang
passes the same counts unit-only; four ASan/UBSan tests pass. Independent proof,
blind reviews and follow-ups resolved findings. All 78 old result sets and legacy
`f5fa269eb60ee34f`/292711 remain unchanged; nearby adds sets79/80, hashes
`181c93ddf14441bf`/33997 and `c75989a801b50444`/6990. Exact Fraction and pinned
MPFR four-mode targets agree; five complete SHA/LF gates and byte-identical
regeneration protect references. Raw 34102/7042 rows drive 548632 separately
asserted state calls per profile; raw result/order hashes are in the detailed
report. Six emulated targets match 80 sets default/portable and 24 raw native/query
O0/O2 profiles; six real direction faults detect. These are probes, not physical
hosts/full cross-target GoogleTest. Three fresh and larger 72102/45041-row
samples pass both native compilers, including complete population, C++ path and
80-set overlays. Larger cross-target, Windows/RISC-V runtime, soft-float numerical
execution, exhaustive input/environment space and application timing are unrun.
No new Valgrind run or passing claim; earlier failed partial scopes and force-only
IX witness gaps remain unchanged.

All initial failed full/controller attempts remain recorded as failures. Public
aliases and legacy test-probe closures were fixed; an intermediate old atan link
passed unchanged replay, with precise cause unestablished. Optimized PPC64 can
inline the actual standard query, so cross dependency accounting now binds actual
backend selection rather than demanding an external query symbol. Final complete
runs pass. A late overview-only header correction was followed by GCC14 unit
rebuild/rerun and included in the complete GCC16 run.

Two final paired runs/compiler retain 576 cases with eight warmups, 401 alternating
pairs of 4096 inputs and integer timestamps. Ordinary own/host medians span 2.616–3.975
Double/3.046–4.087 Float GCC14 and 2.251–3.985/2.240–3.317 GCC16; most ranges also
trail. No overall/application/platform speed win. Every case's absolute ns/call
and paired p10/median/p90 envelope, proof, contracts, failure history and
reproduction are in [nearby-integer.md](nearby-integer.md). Broader standard
coverage is intentional; consumers remain unmigrated.

## Rejected wide-remainder investigation

A numerically compatible common-factor prototype improved measured Double wide
inputs about 4.4 times, but failed its predeclared ordinary 5% ceiling: nine of 144
ordinary medians exceed it, reaching 1.086; selected special cases reach 1.477.
The entire runtime/test/tool change was rejected and restored to 860e771. No API,
optimization or shipped test coverage is added. The completed capability counts
above remain unchanged. Independent reviewers reconciled all 1,248 records and 312
table rows. Candidate native gates passed after a stale-header rerun; all 78
result sets and six-target emulated probes also agree (SPARC needed an extended
wall bound). That numerical evidence does
not justify accepting the performance regressions. Experimental sources, proof,
validation limits and complete timing envelopes are retained in
[the rejection report](ieee-remainder-wide-performance.md).

## Completed capabilities

- Exact nearest-quotient remainder and seven signed quotient bits:
  `gmath_remainder`, `gmath_remainderf`, `gmath_remquo`, `gmath_remquof`.
  Quotient ties go to even; exact remainder bits, including signed zero and
  subnormals, are mode independent. Valid calls add no flags. Both operands
  participate in signaling-NaN dispatch; caller state is preserved. NULL
  omits the quotient output as a project extension. Consumers remain unmigrated.

- Binary32 cube root: `gmath_cbrtf`, using a guarded cubic seed and unchanged
  Double fallback with
  raw Float special dispatch and nearest one-Float-ULP accuracy. Exact binary
  powers whose exponents are divisible by three are exceptionless; other
  finite nonzero inputs require IX, including other exact cubes. Caller state
  is preserved. General correct/directed rounding is not promised. Common
  ranges remain slower than host libm; evidence and limits follow.

- Native-long power-of-two scaling: `gmath_scalbln` and `gmath_scalblnf`,
  using safe long comparisons before narrowing and unchanged existing kernels.
  Every native signed long32/long64 exponent is accepted, including extremes.
  Exact outputs, signed special values and caller state are preserved;
  Double before-round versus Float after-round tininess remains explicit.

- Exact floating exponent values: `gmath_logb` and `gmath_logbf`, including
  subnormals and either input sign. Zero gives negative infinity/divide-by-zero;
  infinity gives positive infinity; canonical NaNs raise invalid only for
  signaling inputs. Exact mode-independent results, positive exponent zero and
  preserved errno/mode/incoming flags have dedicated references and probes.

- Exact signed integral/fractional splitting: `gmath_modf` and `gmath_modff`.
  Both parts preserve the input sign, including zero; infinities return signed
  zero and store themselves. Canonical NaNs, signaling-invalid only, exact
  finite results in every mode, preserved errno/mode/incoming flags and an
  optional NULL integral output have explicit contracts. Consumers remain
  unmigrated. Numerical/state evidence and performance limits follow.

- Adjacent representable values: `gmath_nextafter` and `gmath_nextafterf`,
  with exact mode-independent integer stepping, y's bits on equality,
  canonical NaNs and explicit overflow/underflow/inexact rules. Unequal tiny
  steps require UF/IX even when exactly representable. errno, mode and
  incoming flags are preserved; full errno semantics are not promised.

- Exact binary32 decomposition/scaling: `gmath_frexpf`, `gmath_ilogbf`,
  `gmath_scalbnf` and `gmath_ldexpf`. Integer normalization and once-only
  nearest/ties-even packing preserve exact outputs and caller state in every
  mode; inexact scaling uses after-round tininess. The Double module remains
  unchanged. Numerical evidence, performance and limits follow.

- Exact binary64/binary32 remainder: `gmath_fmod` and `gmath_fmodf`, added in
  commit `39424c29c1caacca54d44122ee69069ae2004dfc`.
- Exact binary64/binary32 extrema: `gmath_fmin`, `gmath_fmax`, `gmath_fminf`
  and `gmath_fmaxf`. Numeric results preserve input bits; minimum orders -0
  below +0. One quiet NaN yields the other number; signaling NaNs yield the
  canonical NaN and raise invalid.
- Base logarithms: `gmath_log2`, `gmath_log10`, `gmath_log2f`, with independent
  MPFR/mpmath reference values, exact binary-power cases and a dedicated float
  table/series path. The public numerical contract is one ulp, with nearest
  rounding assumed and canonical special-value handling.
- Binary exponential: `gmath_exp2`, with exact integer powers including
  subnormals, direct base-two table reduction, a one-ulp numerical target,
  and explicit finite overflow/inexact-underflow behavior. GCC and Clang each
  pass all 108 unit tests; full GCC gates, pinned regeneration/fresh oracles,
  ASan/UBSan and independent review pass. A 111,631-input sample measures
  maximum error 0.505040 ulp normal and 0.749648 ulp subnormal. Common small
  inputs remain slower than host libm; wide ranges and exact integer powers
  are faster on the measured host (see design notes).

- Exact native integer rounding: `gmath_lround`, `gmath_lroundf`,
  `gmath_llround` and `gmath_llroundf`. Ties go away from zero in every mode;
  valid calls add no flags, while NaNs/infinities/out-of-range rounded results
  return the destination minimum with invalid only. Native long may be
  signed32 or signed64; long long is signed64. Caller errno/mode/incoming
  flags are preserved. Consumers remain unmigrated. Validation and timing
  evidence follows.

- Binary32 unary arctangent: `gmath_atanf`, reusing the verified Float atan2
  kernel with exact abscissa one. One Float ULP under nearest rounding;
  exact tiny input bits in every mode, canonical raw NaNs, signed zeros and
  infinity constants, explicit IX/UF and preserved caller state. A dedicated
  13,114-row independent reference corpus covers unary midpoint/seam cases.
  Consumers remain unmigrated. Full validation and performance limits follow.

- Binary32 two-argument arctangent: `gmath_atan2f`, with a short Float-specific
  series/table kernel, signed-zero/quadrant constants and explicit raw NaN
  handling. The numerical target is one Float ULP under nearest rounding;
  tiny positive-x ratios have true nearest bits in every mode, including
  corrected quotient midpoints and after-round UF. All nonzero mathematical
  angles require IX. Independent committed/larger references cover
  35,309/229,222 pairs with conservative sampled bound 0.50000003 ULP;
  the mathematical bound is 0.501457908 ULP. General correct rounding is not
  claimed. Table/direct timing samples beat host libm, while common/wide
  ranges remain slower; no overall speed win is claimed.

- Binary32 hypotenuse: `gmath_hypotf`, correctly rounded nearest/ties-even in
  every mode with exact-result/no-new-flags behavior. Signaling NaNs have
  explicit priority; finite inexact results use tininess after rounding and
  deterministic overflow flags. Exact 96-bit integer rounding backs a guarded
  native approximation. Committed/larger independent samples have
  35,910/229,568 rows; strict midpoint-square certificates enforce target bits,
  with closed error-cell upper bound 0.50000003 ULP at an exact finite tie.
  Native admission improves the common sample about 2.1 times versus the
  integer baseline, but ordinary calls remain about three times host libm.
  No overall performance win is claimed.

- Binary32 base-ten logarithm: `gmath_log10f`, reusing the unchanged natural
  float kernel with one double base conversion. Exact representable decimal
  powers 10^0 through 10^10 return integers without new flags in every mode;
  all other positive finite inputs require inexact and give normal outputs.
  The float nearest 10^11 remains inexact despite rounding to integer 11.
  Committed/larger directed populations contain 19,888/310,331 rows, with
  conservative measured maxima 0.49999504/0.49999852 ULP. Independent bound
  below 0.500168 ULP leaves reserve under the one-ULP contract. Ordinary
  timing remains about 1.10–1.27 times host libm; near-one inputs are faster,
  subnormal arguments near parity and exact-power timing varies. No overall
  performance win is claimed.

- Binary32 natural logarithm: `gmath_logf`, with exact float reduction and a
  dedicated five-term series using the existing logarithm table. One returns
  positive zero without flags; all other positive finite arguments require
  inexact and produce normal outputs. Raw NaN/domain/zero handling and state
  preservation have explicit tests. Committed/larger directed samples contain
  19,120/309,591 rows; conservative maximum error is 0.49999999 ULP, below the
  0.51 cap. A separate derivation bounds nearest error below 0.500168 ULP.
  Ordinary scalar calls remain about 1.76 times slower than host libm; measured
  subnormal and binary-power arguments are faster. No overall win is claimed.

- Binary32 natural exponential: `gmath_expf`, reusing the existing natural
  reduction/table/polynomial with independently certified float cutoffs.
  Only zeros are exact finite cases; every other finite nonzero input has
  explicit inexact/underflow/overflow policy. Directed pinned references cover
  27,228 committed and 317,759 larger-sample rows, with conservative closed
  error-cell maximum 0.50000003 ULP. Full GCC14/GCC16 gates, 157 unit tests on
  GCC14/GCC16/Clang, nine focused ASan/UBSan tests, independent reviews and
  six-target probes pass. Normal ranges remain about twice as slow as host
  libm, subnormal timing is near parity and tiny inputs are faster in the
  measured paired sample. No overall speed win is claimed.

- Binary32 base-two exponential: `gmath_exp2f`, reusing exact base-two
  reduction and the existing generated exponential table. Integer powers
  -149 through 127 are exact without exceptions; NaNs, finite tails and
  inexact tiny outputs have explicit float/state contracts. Directed pinned
  references cover 26,220 committed and 316,779 larger-sample rows. A complete
  reference-payload checksum also runs without the oracle image. The closed
  error-cell upper bound is 0.50000003 ULP against a 0.51 regression cap.
  Full GCC14/GCC16 gates, 148 unit tests on GCC14/GCC16/Clang, nine focused
  ASan/UBSan tests, independent reviews and six-target probes pass. Normal
  ranges remain about twice as slow as host libm; subnormal-result timing is
  near parity and tiny inputs are faster in the measured paired sample.

- Real cube root: `gmath_cbrt`, with integer normalization, generated midpoint
  seeds and a compensated Newton correction. GCC14.2, GCC16.2 and Clang each
  pass 118 unit tests; full GCC14/GCC16 gates pass (nested optional oracles
  skipped in the build image, executed on the host). Ten cube-root tests,
  ASan/UBSan, 21 arithmetic/table/state plants and independent review pass.
  A 116,075-input independently certified reference sample measures at most
  0.49999902 ulp. Ordinary calls are approximately tied with host libm, wide
  exponents slightly slower, subnormal arguments about twice as fast and exact
  binary cube powers about five times as fast on the measured host.

- Binary32 basic operations: `gmath_sqrtf`, `gmath_floorf`, `gmath_ceilf`,
  `gmath_truncf`, `gmath_roundf`, `gmath_rintf`, `gmath_fabsf`,
  `gmath_copysignf`. Integer rounding/sign results are exact in every mode;
  sqrt is correctly rounded under nearest. Independent pinned references
  cover 66,200 committed and 840,560 larger-sample results. Raw special-value
  probes cover NaNs, sign-only operands and state preservation. GCC14.2,
  GCC16.2 and Clang pass all 125 unit tests; full GCC gates, seven-test
  ASan/UBSan and independent reviews pass. Some rounding
  paths remain slower than host libm; normal sqrt/sign paths are approximately
  tied, while the measured subnormal sqrt path is substantially faster.

- Binary32 trigonometry: `gmath_sinf`, `gmath_cosf`, `gmath_tanf`, with
  bounded Taylor paths for |x|<=1, a private 80-fraction-bit wide reducer at
  |x|>=2^30 and the existing double fallback for uncertain cases. Directed
  MPFR/mpmath certification covers 62,574 committed and 934,914 larger-sample
  results; maximum errors remain about 0.502127/0.500046/0.501626 ulp.
  A broad-admission prototype exhaustively preserved the old results for all
  2,147,483,646 signed finite float inputs above magnitude 1; the final
  activation range is a subset. All 46 committed result hashes remain intact.
  A dedicated wide probe checks 16,062 nearest records and 449,736 state cases,
  across modes and incoming flags; numeric/raw probes pass on six emulated
  architectures, default/portable and raw -O0/-O2. Independent reviews and
  staged numerical/branch mutations accompany the change. Native full build
  and sanitizer validation are recorded with the final verification below.
  Direct same-binary paired measurements improve large inputs about 3.2–3.3
  times versus the previous implementation, while remaining about 1.7–2.4
  times slower than host libm. Small-angle sine retains some measured overhead;
  there is no overall performance-win claim.

## Next work

Investigate a bounded native-conversion optimization for the current-mode integer
family, using the committed portable implementation as an actual-prior baseline.
The measured ordinary gap is substantial. Hardware conversion must match exact
rounded results and invalid-versus-inexact priority, preserve incoming state and
handle tiny/denormal controls through a proved fallback. No fast path is admitted
without independent architectural proof, real prior comparisons and paired gains.
Keep portable/query configurations meaningful and preserve every old hash.

If no safe meaningful improvement is found, retain the verified baseline and
select another cohesive basic capability after a read-only usage audit. `fdim`/
`fdimf` are possible gaps; do not assume production use or full errno semantics.
Broader inverse trig, hyperbolic, `log1p`/`expm1`, long-double, complex and special
functions remain. Independent host references and consumers remain untouched.

## Initial remainder division optimization

This phase adds no API. The only runtime change replaces the initial normalized
integer division/modulus with compare/subtract: both significands lie in
[2^p,2^(p+1)), so their initial quotient is exactly zero or one. Identical q/r
reach the unchanged reduction, tie, sign and packing code. No other runtime,
table, reference payload or committed hash changes. Both native compilers emit
one fewer integer divide site; old / and % already shared one operation.

Final full GCC14.2/GCC16.2 commands return zero: 233 main tests in 32 binaries.
Clang passes those counts unit-only; nine focused ASan/UBSan tests pass.
Affected current GCC14 checks and final strengthened native controls were
rerun after review changes; the later GCC16 full includes the test plumbing.
Independent mathematical/blind reviews close all findings, with no deferred
implementation issues. All 78 sets and legacy f5fa269eb60ee34f/292711 remain.
Six emulated targets agree on 12 numeric and 24 actual-prior raw configurations;
raw corpus observations retain their prior hashes/state checks, with 6624
focused all-mode observations added separately. These are emulated probes,
not physical/full cross-target GoogleTest or exhaustive pair/state claims.

The actual prior module from a54cfbacafa735c0bc7fd1a56af869b8877fa501 is separately
compiled with identical library arguments and only four public symbols renamed.
Identity, actual older-object relinking, source/state and separate benchmark
comparator counterfactuals pass. Individual benchmark inputs check exact NaN
bits, all quotient bits and seeded state before batch timing. Three retained
fresh corpora and larger data also pass actual-prior comparisons on both
native compilers. Valgrind was not rerun; its earlier failed partial scope
and prior force-only IX witness gaps remain unchanged.

Two final runs per compiler/runtime context and comparison yield 768 timing
records. Ordinary paired current/prior medians are 0.873–0.937 Double and
0.854–0.918 Float: about 6–15% lower call times across the three paths. Some
specials regress, reaching 1.164 for a GCC14 NaN/domain case (3.760 versus
3.133 amortized median ns/call). Double wide medians are 1.002–1.004 versus
prior and still 4.103–4.181 versus host remquo; that bottleneck remains.
These are retained measured tradeoffs, without a general nonregression or
net/application/platform win claim. Fixed affinity is not CPU isolation.
[Complete proof, validation accounting, reproducible prior build and all
absolute/paired timing envelopes](ieee-remainder-performance.md).

## Exact IEEE remainder and quotient validation

This phase adds four APIs without changing any prior runtime module or table.
Integer positional reduction selects the full quotient's nearest/even parity,
retains signed magnitude modulo128 for remquo, and packs an exact signed
remainder. Signed zero follows x. Valid calls add no flags, even for subnormal
outputs. NaNs precede numeric domain errors: canonicalize either NaN, invalid
only if either signals; otherwise infinite x or zero y requires invalid only.
Finite x/infinite y returns x. Quotient output is zero for specials/domain and
zero dividends; NULL omits it as a documented extension. errno, mode and incoming
flags are preserved. Full errno/long-double parity is not promised.

Independent derivation and blind review closed ten findings in test coverage,
reference independence, allocation bounds, exception-safe unit cleanup,
portable reproducibility and benchmark accounting. No runtime defect was found.
The positional proof covers finite exponent gaps up to 2097/276 and bounded
11/40-bit chunks; tests do not enumerate every input pair or environment.
No other libm implementation source was read or copied. Standard positional
arithmetic is not claimed novel; MPFR supplies output oracles only.

Both final full GCC14.2/GCC16.2 `make test` invocations return zero with recorded
child status: 232 main tests in 32 binaries each. Clang passes 232/32 unit-only;
eight focused ASan/UBSan tests pass. The new numeric-overlay/omission gate landed
after GCC14 full began; current affected checks were explicitly rerun there,
and the later GCC16 full includes it. Runtime source remained frozen. Initial
build-only failures (target spelling, GTest macro bracing/main and strict C
indentation) were fixed before passing runs; none count as successful gates.

Committed references contain 100316 Double and 31008 Float raw pairs. Arbitrary
size Fraction division independently chooses the nearest/even quotient and
exact residual; direct pinned MPFR remainder/remquo must agree at 53/24-bit
precision. Every signed exponent binade is represented (2098/277 exponent
values), with odd unequal significands that keep residuals nonzero through
chunk seams 10/11/12, 39/40/41 and maximum normal gaps. This is domain stratification,
not exhaustive raw inputs. Fixed known targets, independent observed-row
coverage and independently decoded integer Float widening protect shared-helper
mistakes. All signaling payload single bits/maxima in both operands/signs are
covered. Float generic corpora exclude 3959 signaling-operand pairs, retaining
27049 rows and 211 quiet-only NaN pairs; Double generic keeps 100316 canonicalized
rows, including 205 quiet-only NaN pairs. Exception probes always use raw inputs.

All seven payloads have mandatory complete-file SHA256/LF protection; pinned
regeneration is byte-identical. All 72 previous function sets and legacy
`f5fa269eb60ee34f` over 292711 results remain unchanged. New sets (78 total):

| Set | Hash | Rows |
| --- | --- | ---: |
| remainder / remquo | 0c911b03aac2ba92 | 100316 each |
| remainderf / remquof | c0e9b42076c7567c | 27049 each |
| remquo_quotient | c83d811fbc46c08e | 100316 |
| remquof_quotient | c20a236a8b4a2bb5 | 27049 |

Raw result/quotient hashes are `de2cafdcc5da3465` / `d982af8aeb4c9bfb`.
Three API paths per pair (remainder, remquo/output, remquo/NULL) give 393972 nearest
calls. Selected pairs make 807504 separate all-mode/state calls, with ordered
hashes `84af9b980627e8f5` / `9f841414af40b535`. Flags, errno and mode are asserted
inline, not encoded as hardware-state digests. Requested incoming subsets can
merge on hardware. Six emulated targets agree on all 78 numerical sets default/
portable and 24 raw O0/O2 default/forced-integer-loop profiles. Each raw profile
checks those 393972+807504 calls. Final i686 O0 caller has no fldl/flds argument
loads. These are emulated probes, not physical-host/full cross-target GoogleTest.
Windows, exhaustive pairs/states and application timing remain unrun.

Three fresh samples contain 99429/30121, 100313/31005 and 100725/31417 Double/Float
raw pairs. Larger data contains 149316/80008 pairs, checking 687972 nearest and
1335048 selected-state calls natively; generic Float keeps 75871 rows. All four
pass complete seed/count/population/certificate/widening/raw/unit-directory
checks and actual 78-set numerical overlay. No larger cross-target run is
claimed. The actual former-family unit-directory typo is rejected with an
equal-sized valid fallback, as well as the disposable empty-directory control.
Caller evidence is never renamed.

Twenty-two shared actual runtime/state plants detect in both formats and C17/
C++; two format-local plants leave the other format passing. These run with
both native compilers and actual forced-loop normalization. A separate real
loop-bound defect detects on the fallback and passes as inactive/equivalent
under the intrinsic. Seven checksum and seven oversize-before-open controls,
42 loader negatives, rational/quotient/flag and widened-output corruptions,
complete output/count/order/path/status controls and all six hash omissions/
corruptions detect. Eight actual generator numerical/pin faults and eight
actual shared-answer/coverage faults reject before publication; ignored seed/
count faults publish privately and then fail complete-population checks.
An actual disabled-certificate counterfactual fails at its intended layer.
Positive existing/absent publication precedes 14 rollback controls; the reused
seven-file publisher rolls back exceptions, not process crashes. Both real
wrapper commands have recording-engine dispatch/omission/absence controls even
when optional numerical engines skip. Those are accounting evidence only.
Host pinned numerical controls execute; optional nested engines skip explicitly
inside the GCC16 image and required absence fails before publication.

Valgrind 3.24 invokes all eight focused tests: five pass, three fenv assertions
fail, suite exit 1. Both corpus probes stop on their first zero/zero invalid
case; correct canonical NaN bits are returned but invalid is missing under
instrumentation. Zero memory errors/leaks are reported, with partial memory
coverage because of early exits. A separate no-gmath volatile 0/0 reproducer
returns the same NaN bits natively/instrumented, with native IV versus no flags
under Valgrind. This directly establishes missing invalid instrumentation;
attribution of every discrepancy remains an inference. Assertions were not
weakened. This is a failed Valgrind run, not a passing suite. Earlier cbrtf and
scaling instrumenter limits and expf/exp2f/atanf/cbrtf force-only IX witness gaps
remain unchanged.

Reproduce the ordinary checks with `make check-ieee-remainder`,
`make check-ieee-remainder-portable`, `make check-planted-ieee-remainder`,
`make check-ieee-remainder-reference-controls` and
`make check-ieee-remainder-oracle`. The last runs pinned byte comparison and
fresh checks when the oracle is available. `tools/probe-ieee-remainder.c`
and `tests/ieee_remainder_probe.h` also provide a standalone C17 raw probe;
link the new module with the public/generated include directories and `-lm`
for test fenv only. `GMATH_IEEE_REMAINDER_PORTABLE_BITS` selects loop
normalization. The production library has no libm dependency. Suite runners
and all consumers remain unchanged.

Two predeclared final runs per native compiler produce 384 case records: eight
ranges, six API paths and two incoming states. Each case uses eight paired
warmups and 401 alternating pairs of 4096 identical values, integer timestamps,
untimed exact own/host remainder-bit checks and own state/errno/mode guards.
Host remquo quotient checks use only the three guaranteed low bits/sign;
independent references check this library's seven. NULL-output own remquo paths
compare with host remainder, never standard remquo with NULL. NaN payloads,
new host flags, exceptional errno and unspecified host NaN quotients may differ.
All guards pass. Fixed logical affinity does not establish CPU isolation or
controlled governor; exact compiler/flags, static archive, binary/source and
runtime-libm hashes are retained with the private measurement evidence.

Tables show minimum–maximum envelopes across both final runs and both entry
states (four observations per cell). ns columns are amortized median ns/call;
p10/median/p90 are paired own/host ratio quantiles. NULL rows use host remainder
as labelled in the tool. Call/loop/checksum/timestamp overhead and first-exception
amortization are included. No overall/application/platform speed win is claimed.
Several ranges remain slower; these measurements establish no cross-host result.
Ordinary median own/host ratios are 0.789–0.818 for Double remainder and
0.810–0.845 for Float remainder; quotient-output forms are 0.647–0.673 Double
and 0.666–0.734 Float. These ranges are faster on this measured host. Double
wide-gap remainder is 1.098–1.121 times host, while remquo is 4.074–4.162 times
host. NaN/domain quotient-output paths also trail in some cases. This measured
wide-gap cost remains a concrete performance gap.
`make bench-ieee-remainder` builds and runs the public paired benchmark.

### GCC14 paired measurements

| API / range | Own median ns | Host median ns | Ratio p10 | Ratio median | Ratio p90 |
| --- | ---: | ---: | ---: | ---: | ---: |
| remainder / normal | 10.310–12.316 | 12.616–15.089 | 0.790–0.808 | 0.814–0.818 | 0.832–0.914 |
| remquo / normal | 11.325–13.432 | 16.844–20.703 | 0.611–0.649 | 0.647–0.673 | 0.673–0.692 |
| remquo_null / normal | 10.656–12.610 | 13.321–15.394 | 0.792–0.807 | 0.799–0.821 | 0.809–0.862 |
| remainder / half-ties | 6.255–6.928 | 24.331–26.920 | 0.254–0.256 | 0.257 | 0.258–0.261 |
| remquo / half-ties | 6.905–7.905 | 6.541–7.506 | 1.015–1.051 | 1.050–1.058 | 1.057–1.065 |
| remquo_null / half-ties | 6.180–6.862 | 24.329–26.927 | 0.251 | 0.254–0.255 | 0.255–0.256 |
| remainder / quotient-wrap | 5.482–6.306 | 6.547–7.464 | 0.812–0.836 | 0.837–0.838 | 0.844–0.846 |
| remquo / quotient-wrap | 5.634–6.475 | 6.456–7.553 | 0.847–0.866 | 0.867–0.875 | 0.877–0.883 |
| remquo_null / quotient-wrap | 5.394–6.119 | 6.547–7.294 | 0.810–0.835 | 0.820–0.836 | 0.841–0.843 |
| remainder / subnormal | 17.242–18.593 | 187.228–202.190 | 0.091–0.092 | 0.092–0.093 | 0.093–0.095 |
| remquo / subnormal | 18.742–20.670 | 69.187–76.991 | 0.259–0.261 | 0.267–0.271 | 0.281–0.283 |
| remquo_null / subnormal | 17.013–18.376 | 187.223–198.829 | 0.088–0.091 | 0.090–0.092 | 0.092–0.095 |
| remainder / wide-gap | 676.152–704.425 | 616.109–636.723 | 1.088–1.096 | 1.098–1.114 | 1.099–1.146 |
| remquo / wide-gap | 676.016–716.856 | 165.551–171.898 | 4.023–4.050 | 4.080–4.162 | 4.094–4.322 |
| remquo_null / wide-gap | 675.876–705.362 | 616.117–638.352 | 1.088–1.096 | 1.097–1.108 | 1.098–1.139 |
| remainder / zero | 2.662–2.866 | 19.385–20.174 | 0.130–0.132 | 0.134–0.142 | 0.142–0.143 |
| remquo / zero | 2.674–2.872 | 5.838–6.651 | 0.423–0.446 | 0.429–0.464 | 0.435–0.533 |
| remquo_null / zero | 2.558–2.661 | 19.406–20.165 | 0.127 | 0.130–0.132 | 0.132–0.133 |
| remainder / infinite-divisor | 2.815–2.870 | 19.443–20.232 | 0.132–0.141 | 0.142 | 0.142–0.152 |
| remquo / infinite-divisor | 2.900–3.259 | 3.911–4.498 | 0.648–0.714 | 0.688–0.751 | 0.727–0.764 |
| remquo_null / infinite-divisor | 2.759–2.811 | 19.445–20.211 | 0.131–0.132 | 0.140–0.142 | 0.142–0.152 |
| remainder / NaN-domain | 2.740–3.004 | 78.527–80.112 | 0.033–0.037 | 0.036–0.037 | 0.038–0.040 |
| remquo / NaN-domain | 2.905–3.770 | 1.828–2.442 | 1.484–1.575 | 1.493–1.582 | 1.583–1.591 |
| remquo_null / NaN-domain | 2.602–2.610 | 78.530–80.069 | 0.032 | 0.033 | 0.034 |
| remainderf / normal | 11.851–12.348 | 14.151–14.700 | 0.826–0.829 | 0.838–0.845 | 0.849–0.853 |
| remquof / normal | 12.300–12.928 | 17.355–18.125 | 0.641–0.697 | 0.690–0.734 | 0.724–0.749 |
| remquof_null / normal | 11.666–12.053 | 14.112–14.719 | 0.815–0.817 | 0.822–0.824 | 0.830–0.845 |
| remainderf / half-ties | 6.647–6.779 | 25.729–26.473 | 0.252–0.256 | 0.256–0.258 | 0.259–0.262 |
| remquof / half-ties | 7.379–7.713 | 7.040–7.446 | 1.015–1.044 | 1.028–1.048 | 1.037–1.053 |
| remquof_null / half-ties | 6.565–6.717 | 25.819–26.505 | 0.251–0.253 | 0.254 | 0.256–0.259 |
| remainderf / quotient-wrap | 5.722–5.996 | 6.895–7.292 | 0.811–0.812 | 0.815–0.837 | 0.840–0.846 |
| remquof / quotient-wrap | 6.010–6.292 | 6.836–7.237 | 0.857–0.874 | 0.866–0.880 | 0.874–0.887 |
| remquof_null / quotient-wrap | 5.726–5.963 | 6.975–7.354 | 0.810 | 0.811–0.836 | 0.836–0.839 |
| remainderf / subnormal | 11.287–11.519 | 191.248–195.240 | 0.057–0.058 | 0.059 | 0.060–0.061 |
| remquof / subnormal | 11.900–12.532 | 70.638–73.950 | 0.164–0.166 | 0.168–0.169 | 0.171–0.174 |
| remquof_null / subnormal | 11.062–11.307 | 191.344–195.097 | 0.057 | 0.058–0.059 | 0.059–0.062 |
| remainderf / wide-gap | 27.701–28.333 | 207.065–212.106 | 0.130–0.131 | 0.133–0.134 | 0.136–0.137 |
| remquof / wide-gap | 29.131–30.405 | 111.060–116.424 | 0.256–0.258 | 0.260–0.262 | 0.265–0.267 |
| remquof_null / wide-gap | 27.208–27.768 | 207.432–210.719 | 0.129–0.130 | 0.131–0.132 | 0.134–0.135 |
| remainderf / zero | 2.869–3.007 | 19.808–20.205 | 0.132 | 0.142–0.147 | 0.152 |
| remquof / zero | 2.737–2.800 | 6.620–7.245 | 0.376–0.398 | 0.393–0.426 | 0.401–0.432 |
| remquof_null / zero | 2.717–2.806 | 19.796–20.182 | 0.131–0.132 | 0.133–0.142 | 0.142–0.143 |
| remainderf / infinite-divisor | 3.009–3.072 | 20.405–20.824 | 0.138–0.147 | 0.147–0.148 | 0.149–0.157 |
| remquof / infinite-divisor | 3.031–3.343 | 4.257–4.710 | 0.610–0.714 | 0.682–0.726 | 0.723–0.764 |
| remquof_null / infinite-divisor | 2.865–3.011 | 20.410–20.794 | 0.128–0.137 | 0.138–0.147 | 0.148–0.149 |
| remainderf / NaN-domain | 2.935–3.364 | 78.543–83.367 | 0.034–0.038 | 0.037–0.041 | 0.039–0.041 |
| remquof / NaN-domain | 2.842–3.537 | 2.237–3.075 | 1.148–1.267 | 1.160–1.274 | 1.273–1.410 |
| remquof_null / NaN-domain | 2.708–2.878 | 78.657–81.463 | 0.033 | 0.034–0.036 | 0.037 |

### GCC16 paired measurements

| API / range | Own median ns | Host median ns | Ratio p10 | Ratio median | Ratio p90 |
| --- | ---: | ---: | ---: | ---: | ---: |
| remainder / normal | 10.735–11.099 | 13.498–14.053 | 0.784–0.785 | 0.789–0.794 | 0.797–0.806 |
| remquo / normal | 11.964–12.228 | 18.273–18.429 | 0.623–0.653 | 0.655–0.667 | 0.669–0.683 |
| remquo_null / normal | 11.106–11.363 | 14.065–14.365 | 0.778–0.782 | 0.786–0.787 | 0.791–0.792 |
| remainder / half-ties | 6.518–6.654 | 25.738–26.275 | 0.251–0.252 | 0.253 | 0.254–0.255 |
| remquo / half-ties | 7.220–7.554 | 7.494–7.729 | 0.926–0.962 | 0.950–0.973 | 0.960–0.981 |
| remquo_null / half-ties | 6.549–6.687 | 25.739–26.271 | 0.252–0.254 | 0.254 | 0.255–0.256 |
| remainder / quotient-wrap | 5.863–5.995 | 6.976–7.130 | 0.814–0.838 | 0.839–0.841 | 0.871–0.878 |
| remquo / quotient-wrap | 6.003–6.291 | 7.532–7.837 | 0.760–0.785 | 0.784–0.807 | 0.801–0.822 |
| remquo_null / quotient-wrap | 5.782–5.979 | 6.976–7.130 | 0.788–0.833 | 0.838–0.839 | 0.849–0.867 |
| remainder / subnormal | 17.756–17.863 | 194.701–196.446 | 0.089–0.090 | 0.091 | 0.093–0.094 |
| remquo / subnormal | 20.395–20.661 | 75.189–77.156 | 0.256–0.261 | 0.266–0.270 | 0.279–0.281 |
| remquo_null / subnormal | 17.707–17.929 | 194.749–197.592 | 0.089–0.090 | 0.090–0.091 | 0.092–0.093 |
| remainder / wide-gap | 681.147–702.372 | 615.718–620.840 | 1.089–1.098 | 1.106–1.121 | 1.137–1.158 |
| remquo / wide-gap | 679.597–696.875 | 166.938–167.499 | 3.985–4.043 | 4.074–4.146 | 4.204–4.276 |
| remquo_null / wide-gap | 680.028–696.777 | 615.606–617.770 | 1.096–1.097 | 1.105–1.119 | 1.135–1.144 |
| remainder / zero | 2.975–3.010 | 19.664–19.678 | 0.132–0.151 | 0.152–0.153 | 0.153–0.164 |
| remquo / zero | 2.839–3.057 | 6.609–6.899 | 0.391–0.398 | 0.429–0.477 | 0.466–0.507 |
| remquo_null / zero | 2.807–2.833 | 19.646–19.676 | 0.133–0.142 | 0.143 | 0.143–0.163 |
| remainder / infinite-divisor | 3.009–3.017 | 19.739–19.750 | 0.146–0.150 | 0.152–0.153 | 0.153–0.173 |
| remquo / infinite-divisor | 2.963–3.196 | 5.019–5.441 | 0.529–0.568 | 0.586–0.612 | 0.604–0.642 |
| remquo_null / infinite-divisor | 2.865–3.054 | 19.710–19.754 | 0.140–0.142 | 0.143–0.145 | 0.153–0.164 |
| remainder / NaN-domain | 2.805–3.061 | 78.368–78.375 | 0.035–0.036 | 0.036–0.038 | 0.041–0.042 |
| remquo / NaN-domain | 2.865–3.142 | 2.460–2.884 | 1.028–1.111 | 1.091–1.214 | 1.138–1.291 |
| remquo_null / NaN-domain | 2.805–2.939 | 78.362–78.377 | 0.034 | 0.036–0.038 | 0.040 |
| remainderf / normal | 11.552–11.890 | 14.214–14.521 | 0.801–0.808 | 0.810–0.817 | 0.817–0.829 |
| remquof / normal | 11.822–12.129 | 17.189–17.797 | 0.651–0.681 | 0.666–0.705 | 0.674–0.716 |
| remquof_null / normal | 11.381–11.645 | 14.214–14.515 | 0.791–0.797 | 0.800–0.803 | 0.803–0.811 |
| remainderf / half-ties | 6.524–6.536 | 25.930–25.934 | 0.249–0.251 | 0.252 | 0.252–0.254 |
| remquof / half-ties | 7.221–7.235 | 7.496–7.694 | 0.936–0.960 | 0.940–0.964 | 0.952–0.972 |
| remquof_null / half-ties | 6.544–6.556 | 25.929–25.937 | 0.246–0.250 | 0.252–0.253 | 0.253 |
| remainderf / quotient-wrap | 5.907–6.093 | 6.829–6.976 | 0.814–0.835 | 0.858–0.883 | 0.883–0.902 |
| remquof / quotient-wrap | 5.994–6.033 | 7.102–7.291 | 0.819–0.838 | 0.826–0.843 | 0.836–0.852 |
| remquof_null / quotient-wrap | 5.723–5.936 | 6.829–6.977 | 0.809–0.837 | 0.833–0.839 | 0.860–0.870 |
| remainderf / subnormal | 11.078–11.159 | 191.376–191.540 | 0.057 | 0.058 | 0.059 |
| remquof / subnormal | 12.520–12.679 | 72.552–72.905 | 0.169–0.170 | 0.173 | 0.179–0.180 |
| remquof_null / subnormal | 10.933–11.140 | 191.451–191.808 | 0.056 | 0.057–0.058 | 0.058–0.060 |
| remainderf / wide-gap | 28.340–28.378 | 207.844–209.030 | 0.134 | 0.136–0.137 | 0.139–0.140 |
| remquof / wide-gap | 29.601–29.657 | 113.880–114.290 | 0.256 | 0.259–0.260 | 0.265–0.267 |
| remquof_null / wide-gap | 27.839–27.890 | 207.507–208.654 | 0.131–0.132 | 0.134 | 0.137 |
| remainderf / zero | 3.006–3.274 | 19.813–19.825 | 0.131–0.152 | 0.151–0.162 | 0.153–0.182 |
| remquof / zero | 2.686–3.054 | 6.969–7.220 | 0.366–0.376 | 0.386–0.431 | 0.440–0.453 |
| remquof_null / zero | 2.759–3.014 | 19.753–19.813 | 0.131–0.141 | 0.142–0.148 | 0.142–0.162 |
| remainderf / infinite-divisor | 2.898–3.139 | 20.362–20.438 | 0.127–0.147 | 0.146–0.152 | 0.148–0.167 |
| remquof / infinite-divisor | 2.643–3.087 | 4.070–4.640 | 0.611–0.643 | 0.629–0.678 | 0.664–0.733 |
| remquof_null / infinite-divisor | 2.750–3.208 | 20.045–20.419 | 0.128–0.140 | 0.137–0.157 | 0.157–0.158 |
| remainderf / NaN-domain | 2.803–3.142 | 78.506–78.528 | 0.035–0.037 | 0.036–0.040 | 0.041–0.042 |
| remquof / NaN-domain | 2.732–3.177 | 2.405–2.930 | 1.024–1.041 | 1.048–1.133 | 1.170–1.230 |
| remquof_null / NaN-domain | 2.849–2.890 | 78.487–78.527 | 0.035 | 0.036–0.037 | 0.038–0.039 |

## Float cube-root seed optimization

This phase changes only the Float cube-root runtime module. The own Double
kernel, helpers and table remain byte-identical. Normal inputs attempt the
existing cubic seed under a conservative all-mode rounding-cell gate; uncertain
cells and a performance-only exact-cube prefilter select the old kernel.
Subnormal inputs retain their prior path; exact normal binary powers return
raw bits. Sign is applied before narrowing. All public accuracy, raw-special,
exact-power, exception and caller-state contracts remain unchanged. The design
records the independent derivation and source-linked rational certificate,
including a bound on the actual prior post-Newton result, not only true cbrt.
No other libm implementation source was read or copied.

Both full default GCC14.2/GCC16.2 `make test` commands return zero with actual
child-status records. Each main sequence passes 224 tests in 31 binaries;
Clang passes those counts unit-only. Six focused ASan/UBSan tests pass. A test-only
output-array initialization and optional-tool revision checks landed after
GCC14 full began; affected current unit/probe/budget/controller/plant targets
were explicitly rerun, while the later GCC16 full includes them. Numerical
source remained frozen throughout. Independent mathematical and blind reviews,
with follow-ups, resolve ten implementation/verification findings; none are
deferred. The known Valgrind fenv instrumentation limitation from the initial
phase remains: no new passing Valgrind or expanded Memcheck coverage is claimed.

All 72 numerical sets, reference bytes and legacy aggregate
`f5fa269eb60ee34f` over 292,711 results remain unchanged, including cbrtf
`9062b0d1bd1deb80` over 74,650 widened rows. Raw nearest result/flag-class hash
`b56d6fe265757f09` still covers 74,696 inputs. Four new default compatibility
hashes pin the previous mode-specific ordered input/results; these are not
independent directed accuracy certificates. Twenty-one source/state plants
fail in C++ and C17 on both compilers, including three directed-only
single-input bit changes outside the supplemental midpoint witness. Twelve
mathematical/source counterfactuals detect, including preprocessing outside
function bodies. The optimization guard rejects all twenty optimized-Python
probes across five certificate scripts; five normal pinned host controls pass.
Optional nested engines skip explicitly in GCC16; the new pure-rational
certificate runs there without them.

Native GCC14 result scans match the actual separately compiled prior public
function from `412417c7a0edc5b0066296e578400dd21d4685e4` for all
4,278,190,080 signed finite Float encodings, including both zeros, under each
of four modes: **17,112,760,320 logical result pairs** in 128 disjoint step-one
intervals. This is result compatibility, not independent accuracy or exhaustive
exception/environment coverage. Separate default raw hooks check 840,360
logical API/state observations per profile, making two physical calls each;
nearest hash observations are included, not additional. Sixteen supplemental
midpoint mode/sign/entry-state pairs are counted separately. Requested incoming
subsets may merge on hardware; flags/errno/mode are asserted inline rather
than encoded in result-only hashes.

Six emulated targets agree on all 72 sets default/portable and 24 raw
O0/O2/default/forced-Double-loop profiles with actual prior hooks, four mode
hashes and midpoint fixtures. The final i686 O0 caller has no fldl/flds argument
loads. These are emulated probes, not physical hosts or full cross-target
GoogleTest. Native GCC14/GCC16 each also enumerate 100,663,296 production-seed
mode/remainder cases, select 3,072 nearest threshold-side classes across table
rows, and compare 27,648 result/state pairs across signs and three scale
quotients, including table/binade endpoints. Native C/C++ controls pass 35
actual/wrong/alias/current-defect configurations per compiler; their positive
C++ random caller separately completes 262,144 logical comparisons. Negative
fixtures stop on failure and do not receive that full count.

Byte-identical pinned regeneration, fresh selection/certificates and all
existing loader/oracle controls pass. Three retained fresh populations and the
123,716-row larger population pass complete population/cube/widening/path/unit
checks plus actual-prior all-mode numerical/state comparisons. Larger raw hash
is `a87ac9a06273e289`, with 1,401,904 logical calls and conservative sampled
error 0.499983355 ULP. No new larger cross-target run is claimed. Exact known
midpoint input `236e2a8e` has independently certified nearest output `361d6f3e`;
removing the gate instead yields the adjacent upper value. Deleting only the
final IX force still escapes samples: that narrow witness remains unverified,
as do the previously recorded expf/exp2f/atanf force-only gaps. The production
forces remain; observable IX-loss mutations are separate evidence.

The public baseline builder reproduces the own prior source/helper/object
with identical supplied library arguments and only its public symbol renamed.
A fresh build-directory reproduction passes. Actual object-switch/relink,
stale-binary, wrong flags/compiler/revision and restoration counterfactuals
pass. Identity binds caller-declared revision/build bytes, not arbitrary source
authenticity. Interval/count, positive finite timeout, completion-order failure
and tracked-child cancellation controls pass. Default gates need no prior
object or Git history; optional reproduction commands are in the design.

After validation, two predeclared paired runs per compiler compare current
against actual prior and separately against host libm: 13 ranges, two entry
states, 26 cases per run, 208 total records. Eight paired warmups precede 401
alternating pairs of 4,096 identical inputs. Integer timestamps, untimed bit/class
and coarse host-Double guards, strict own/prior state/errno/mode checks and
baseline identities accompany every run. Host numerical guards are not
independent accuracy proofs; host new flags, exceptional errno and NaN payloads
may differ. A fixed logical processor gives no isolation/governor claim.
Absolute median ns/call envelopes cover two runs and two entry states;
paired median ratios have their combined p10–p90 envelope in brackets.
Absolute envelope endpoints are independent and are not paired samples.

Actual-prior comparison:

| Range | GCC14 absolute ns (current / prior) | GCC14 ratio [p10–p90] | GCC16 absolute ns (current / prior) | GCC16 ratio [p10–p90] |
| --- | --- | --- | --- | --- |
| normal | 4.875–5.323 / 10.007–10.780 | 0.488–0.493 [0.485–0.506] | 5.039–5.259 / 8.255–8.578 | 0.609–0.615 [0.607–0.619] |
| binary-powers | 1.978–2.032 / 2.921–3.021 | 0.673–0.677 [0.665–0.685] | 2.161–2.443 / 2.998–3.127 | 0.708–0.714 [0.651–0.824] |
| other-exact-cubes | 8.771–9.084 / 8.578–8.883 | 1.022 [1.016–1.034] | 8.923–8.980 / 8.719–8.746 | 1.025 [1.021–1.030] |
| subnormal | 9.349–9.930 / 9.427–9.998 | 0.991–0.996 [0.950–1.013] | 8.753–8.920 / 8.776–8.903 | 1.001–1.002 [0.994–1.007] |
| wide | 5.339–5.571 / 9.999–10.319 | 0.533–0.541 [0.529–0.547] | 5.545–5.685 / 8.922–9.104 | 0.621–0.626 [0.620–0.628] |
| zero | 1.190–1.229 / 1.382–1.464 | 0.856–0.858 [0.714–1.000] | 1.377–1.405 / 1.181–1.204 | 1.166–1.167 [1.164–1.169] |
| infinity | 1.203–1.231 / 1.404–1.435 | 0.857–0.858 [0.833–0.862] | 1.378–1.407 / 1.182–1.207 | 1.166 [1.163–1.168] |
| quiet-NaN | 1.205–1.432 / 1.579–1.639 | 0.752–0.874 [0.749–1.001] | 1.574–1.605 / 1.377–1.405 | 1.143 [1.140–1.145] |
| signaling-NaN | 1.047–1.337 / 1.672–2.014 | 0.626–0.750 [0.625–0.796] | 1.670–1.673 / 1.461–1.466 | 1.140–1.143 [1.138–1.145] |
| large-exact-cubes | 8.916–9.044 / 8.739–8.864 | 1.020–1.021 [1.012–1.035] | 9.105–9.126 / 8.883–8.893 | 1.024–1.025 [1.021–1.029] |
| coarse | 5.413–5.569 / 10.805–10.976 | 0.501–0.507 [0.498–0.522] | 5.697–5.782 / 8.909–9.089 | 0.628–0.641 [0.626–0.645] |
| noncube-binary-powers | 4.523–5.278 / 9.078–10.581 | 0.498–0.502 [0.494–0.588] | 4.660–4.729 / 9.009–9.179 | 0.515–0.517 [0.507–0.519] |
| uncertain-rounding | 11.545–11.587 / 8.881–8.921 | 1.298–1.300 [1.293–1.335] | 11.823–11.828 / 8.904–8.915 | 1.327–1.328 [1.317–1.331] |

Host comparison:

| Range | GCC14 absolute ns (current / host) | GCC14 ratio [p10–p90] | GCC16 absolute ns (current / host) | GCC16 ratio [p10–p90] |
| --- | --- | --- | --- | --- |
| normal | 5.276–5.818 / 3.438–3.775 | 1.529–1.546 [1.522–1.560] | 5.094–7.316 / 3.219–4.489 | 1.569–1.600 [1.562–1.605] |
| binary-powers | 2.200–2.249 / 3.407–3.483 | 0.646–0.647 [0.643–0.649] | 1.927–1.961 / 3.336–3.400 | 0.576–0.578 [0.573–0.581] |
| other-exact-cubes | 9.083–9.266 / 3.244–3.304 | 2.794–2.803 [2.784–2.811] | 8.955–9.131 / 3.241–3.298 | 2.764–2.766 [2.752–2.776] |
| subnormal | 9.600–9.768 / 4.112–4.122 | 2.329–2.381 [2.312–2.394] | 8.757–8.920 / 4.069–4.137 | 2.153–2.155 [2.147–2.163] |
| wide | 5.452–5.636 / 3.504–3.554 | 1.559–1.595 [1.549–1.611] | 5.634–5.741 / 3.586–3.649 | 1.571–1.581 [1.566–1.589] |
| zero | 1.160–1.229 / 1.612–1.842 | 0.668–0.750 [0.623–0.752] | 1.158–1.183 / 1.934–1.975 | 0.598–0.601 [0.597–0.602] |
| infinity | 1.379–1.406 / 1.808–2.005 | 0.700–0.777 [0.600–0.780] | 1.179–1.227 / 2.121–2.248 | 0.546–0.547 [0.544–0.602] |
| quiet-NaN | 1.406–1.575 / 1.774–1.967 | 0.779–0.801 [0.603–0.891] | 1.182–1.205 / 2.165–2.207 | 0.546 [0.544–0.548] |
| signaling-NaN | 1.409–1.433 / 1.844–2.044 | 0.701–0.777 [0.602–0.780] | 1.206–1.252 / 2.208–2.252 | 0.546 [0.544–0.600] |
| large-exact-cubes | 9.051–9.227 / 3.248–3.303 | 2.789–2.792 [2.775–2.801] | 9.108–9.469 / 3.307–3.435 | 2.753–2.755 [2.746–2.763] |
| coarse | 5.629–5.670 / 3.582–3.589 | 1.568–1.583 [1.557–1.604] | 5.759–5.880 / 3.584–3.659 | 1.603–1.607 [1.597–1.615] |
| noncube-binary-powers | 4.702–4.710 / 3.364–3.376 | 1.394–1.396 [1.390–1.400] | 4.802–4.804 / 3.434–3.437 | 1.397–1.398 [1.393–1.402] |
| uncertain-rounding | 11.567–11.583 / 4.558–4.564 | 2.537–2.539 [2.530–2.569] | 11.832–12.068 / 4.570–4.657 | 2.590–2.591 [2.581–2.598] |

Ordinary current/prior medians 0.488–0.493 (GCC14) and 0.609–0.615 (GCC16)
show about 2.0 and 1.6 times faster calls in these samples. Wide and coarse
ranges improve too. Small/large exact cubes regress about 2–2.5%; subnormal
calls are near parity. The deliberately uncertain cell range regresses about
30–33%, and GCC16 special values regress about 14–17% (roughly 0.2 ns/call).
These measured tradeoffs are retained explicitly; there is no general
nonregression claim. Ordinary host ratios remain 1.529–1.600, with exact cubes
and subnormal ranges still slower. Absolute timings vary across contexts,
including a GCC16 host-comparison normal median as high as 7.316 ns while
paired ratios remain similar. Call/loop/checksum/timestamp costs and amortized
first exceptions are included. No net workload, application, vector, physical
cross-target, other-compiler or overall platform speed win is claimed. Windows,
exhaustive state/flag behavior and application timing remain unrun.

## Initial Float cube-root validation

This section records the initial wrapper phase; the seed optimization above
supersedes its normal-input dispatch and performance measurements.

`gmath_cbrtf` uses raw special dispatch, the unchanged own Double cube-root
kernel and one Float narrowing. Its public target is one Float ULP under
nearest. General correct rounding and directed numerical accuracy are not
promised. Signed zeros/infinities are exact and exceptionless; NaNs canonicalize,
invalid only for signaling inputs. Binary powers with exponents divisible by
three return exactly without new flags in every mode. All other finite nonzero
inputs require IX only, including exact cubes such as 27 and 125. Every finite nonzero input has
a normal, finite root. errno, mode and incoming flags are preserved.
`design.md` gives the composition/boundary proof. No other libm implementation
source was read or copied; own-project kernels and mathematical cube comparisons
supply the implementation and independent validation.

A read-only audit of 14,046 C/C++ source/header files found no direct cbrtf
calls within its exclusions. This addition intentionally advances broader
coverage; consumers remain unmigrated. Classic real-function name coverage is
66/171: 33 Double, 33 Float and zero long double. Missing 24 Double + 24 Float
means 48 Float/Double additions, or 105 including 57 long-double names. Complex
adds another 66. Counts are names, not full behavioral parity, and exclude
fenv/macros/vendor extensions.

Full default GCC14.2/GCC16.2 commands return zero with persisted actual child
statuses. Each main unit sequence has 223 tests in 31 binaries; Clang passes
those counts unit-only. Five focused ASan/UBSan tests pass with the sanitizer
runtime first in load order; an initial launch stopped before tests with a
runtime load-order diagnostic. The final certificate-control strengthening
landed after the GCC16 full run began, so the affected current checker target
was explicitly rerun there; the later GCC14 full run includes it. Independent
mathematical, blind and follow-up reviews resolve the implementation findings.

The selected Valgrind 3.24 corpus test exits 1 at input `00000001`: result
`26a14518` matches native, but required IX is absent. Memcheck reports zero
memory errors/leaks. The probe stops early, so memory coverage is partial and
the other four tests were not run under Valgrind. The existing independent
plain-arithmetic reproducer establishes missing UF/IX in this instrumenter;
broader attribution remains an inference. No assertions were weakened and no
passing Valgrind suite is claimed; the external follow-up remains recorded.

Pinned MPFR and independent mpmath agree, and exact rational cube inequalities
certify both nearest target and rounded signed-error cells. Committed references
have 74,696 raw and 74,650 widened entries. All 22 single-bit signaling payloads and
the maximum signaling payload retain both signs in raw probes; 46 signaling
inputs alone are excluded from generic widening. Both complete files have
mandatory SHA256/LF gates; pinned regeneration is byte-identical. The new
portable result set is `cbrtf 9062b0d1bd1deb80` over 74,650 rows. All 71 old
sets and legacy `f5fa269eb60ee34f` over 292,711 rows remain unchanged; every
old runtime module and table is byte-identical.

Raw nearest result/flag-class hash `b56d6fe265757f09` covers 74,696 inputs.
The probe separately asserts 840,360 all-mode/incoming-state calls, two errno
seeds and actual merged incoming flags. Selected/power/nonfinite rows request
all 32 subsets. Hashes do not encode every hardware-state observation. The
conservative closed-cell sampled maximum is 0.499889389 ULP against a 0.51
regression cap; this does not prove general correct rounding. The separate
nearest seam unit checks scaling across all normal Float binades, 64 table
seams/neighbors and both signs, without claiming independent exhaustive accuracy.

Three fresh raw populations of 73,841, 74,694 and 78,679 entries pass complete
requested seed/count, exact certificates, widened reconstruction, standalone
path and actual C++ unit-path checks. A larger sample has 123,716 raw/123,670
widened entries; its hash is `a87ac9a06273e289`, with 1,401,904 state calls and
maximum 0.499983355 ULP. A real former-family unit-directory typo is detected
even with a valid equal-sized fallback of 74,696 rows; caller evidence is never
renamed or replaced by the control.

Six emulated targets agree on all 72 numerical sets default/portable and 24
new raw O0/O2/default/forced-Double-loop profiles. The larger raw sample agrees
on six O2/default profiles. These are emulated probes, not physical-host/full
cross-target GoogleTest claims. Windows, exhaustive input/environment coverage,
physical-target and application timing remain unrun.

Twelve actual source/state plants fail in both C++ and C17, with a passing
control. Observable IX loss is detected, but deleting only the final IX force
escapes both sampled probes; that narrow witness coverage remains unverified
and the production force remains. Earlier expf/exp2f/atanf force-only gaps are
unchanged. Twenty-one loader negatives, four exact-certificate/population
corruptions, a disabled-certificate counterfactual and nine output/process
faults pass. Certificate negatives require their specific failure layer, so a
later raw/widened mismatch cannot masquerade as certificate rejection. Both
actual complete-file checksum corruptions detect. Seven actual oracle faults
fail before publication; ignored seed/count generator faults are rejected by
complete-population verification. Both real wrapper dispatch commands and
optional/required absence paths have recording-engine controls even without
a numerical engine; those controls are accounting evidence only. The unchanged
publisher supplies exception rollback, not crash atomicity.

Two predeclared final paired runs per native compiler use eight paired warmups,
401 alternating pairs of 4,096 identical inputs, nine ranges and clean/preseeded
UF/IX states: 18 cases per run. Integer timestamps precede floating timing
arithmetic. Untimed bit/class and coarse host-Double numerical guards are timing
controls; independent certified-reference accuracy checks remain separate.
Own batch flags/errno/mode are checked exactly; host new flags, exceptional errno
and NaN payloads may differ. Both contexts use one fixed logical processor,
without CPU isolation or governor changes. Exact compiler/library flags, target,
runtime-libm identity, source and binary hashes accompany the measurements.
Context differences are not attributed solely to compiler choice.

Absolute columns are independent min–max envelopes of median ns/call across
two runs and two entry states (gmath / host). Ratio columns enclose paired
median gmath/host ratios; brackets enclose each case's paired p10 through p90.
Absolute envelope endpoints are not paired samples.

| Range | GCC14 absolute ns (gmath / host) | GCC14 ratio [p10–p90] | GCC16 absolute ns (gmath / host) | GCC16 ratio [p10–p90] |
| --- | --- | --- | --- | --- |
| normal | 10.556–11.509 / 3.427–3.746 | 3.047–3.085 [2.820–3.217] | 8.462–8.961 / 3.274–3.481 | 2.556–2.562 [2.478–2.740] |
| binary-powers | 2.934–3.063 / 3.415–3.563 | 0.856–0.859 [0.839–0.871] | 3.190–3.267 / 3.476–3.582 | 0.914–0.920 [0.904–1.003] |
| other-exact-cubes | 9.255–9.597 / 3.376–3.490 | 2.739–2.744 [2.656–2.860] | 9.104–9.484 / 3.376–3.515 | 2.694–2.696 [2.548–2.833] |
| subnormal | 9.727–9.966 / 4.199–4.305 | 2.314–2.319 [2.216–2.454] | 9.094–9.311 / 4.219–4.312 | 2.154–2.158 [2.036–2.276] |
| wide | 10.034–10.412 / 3.496–3.582 | 2.869–2.894 [2.777–3.028] | 9.114–9.293 / 3.602–3.662 | 2.536–2.542 [2.433–2.651] |
| zero | 1.027–1.141 / 1.651–1.831 | 0.621–0.623 [0.617–0.711] | 1.353–1.437 / 2.118–2.254 | 0.637–0.639 [0.634–0.703] |
| infinity | 1.025–1.123 / 1.812–1.979 | 0.556–0.624 [0.555–0.686] | 1.350–1.431 / 2.121–2.248 | 0.636–0.637 [0.631–0.639] |
| quiet-NaN | 1.206–1.338 / 1.612–2.005 | 0.668–0.748 [0.665–0.765] | 1.575–1.609 / 2.165–2.213 | 0.726–0.728 [0.686–0.742] |
| signaling-NaN | 1.254–1.472 / 1.881–2.008 | 0.667–0.750 [0.665–0.984] | 1.577–1.743 / 2.167–2.354 | 0.727–0.728 [0.721–0.745] |

Ordinary, wide, subnormal and other exact-cube cases remain substantially slower
than host libm. Binary powers and special values are faster on the measured
host. Call/loop/checksum/timestamp work and first-exception amortization are
included. No overall, application, shared-library, vector, other-compiler or
cross-platform speed win is claimed. A dedicated Float kernel is a future
performance investigation; the wrapper supplies verified capability first.

## Native-long scaling validation

`gmath_scalbln` and `gmath_scalblnf` saturate the exponent in signed long
before the only int cast, then call the unchanged Double/Float kernels.
LONG_MIN/MAX never undergo negation, addition or premature narrowing. Both
return nearest/ties-even bits in every mode, exact finite/subnormal results
without new flags, deterministic signed infinity with OF/IX on overflow, and
UF/IX for inexact rounded zero/subnormal. Double retains before-round tininess;
Float retains after-round tininess. The rounded-minimum-normal witnesses
`(001fffffffffffff,-1)` and `(00ffffff,-1)` require UF/IX and IX respectively.
Canonical NaNs raise invalid only for signaling inputs. Signed zeros/infinities,
errno, mode and incoming flags are preserved. Full directed/libm errno semantics
are not promised. The derivation and saturation proof are in `design.md`.
No other libm implementation source was read or copied; own-project kernels
and mathematical bounds supply the implementation. Standard identities are
not claimed novel.

A read-only audit of 6,229 project-owned C/C++ source/header files found no
direct scalbln/scalblnf calls within its exclusions. This intentionally advances
broader standard coverage; consumers remain unmigrated. Classic real-function
name coverage is now 65/171: 33 Double, 32 Float and zero long double. Missing
24 Double + 25 Float means 49 Float/Double additions, or 106 including 57
long-double names. Complex adds another 66. Name counts do not establish full
behavioral parity and exclude fenv/macros/vendor extensions.

Final sequential full default GCC14.2/GCC16.2 `make test` commands return zero,
with persisted actual child statuses. Each main unit run has 218 tests in 30
binaries. Clang passes the same unit-only counts, and five focused ASan/UBSan
tests pass. The first GCC14 full attempt returned 2 because the pre-existing
atan2f fresh generator exceeded its unchanged 60-second limit under concurrent
validation. Its exact seed/count replay passed in 6.979 seconds under lighter
load; the serialized full rerun passed. No numerical mismatch, waived gate or
raised timeout is represented as success. An earlier GCC16 full run passed
before the final recording-control wiring; both current-tree full runs were
then repeated. Independent contract/proof, blind and follow-up reviews resolve
the implementation findings.

Valgrind 3.24 invoked all five focused tests and reported zero memory errors
and no leaks, but four exception-state tests failed, so this is not a passing
suite. Both corpus probes stop at their first flag mismatch; memory coverage
is partial. An independent plain C volatile minimum-normal multiplication,
without any gmath calls, produces the same zero bits but UF/IX natively and
no flags under Valgrind. This directly establishes an instrumentation limitation
for UF/IX; attributing every suite discrepancy to that model is an inference.
No production/test exception assertions were weakened. Compatibility with this
instrumenter remains a separate follow-up.

Independent field-decoded exact Fraction quantization and separately decoded
pinned MPFR agree on 48,558 Double and 18,082 Float raw input/exponent rows.
MPFR exponent clipping at 8,192 is independent of the implementation caps.
Common signed32-exponent subsets add portable numerical sets:

| Set | Hash | Rows |
| --- | --- | ---: |
| scalbln | `47ab6ee726681988` | 48,194 |
| scalblnf | `ef95ceda283f36cc` | 17,604 |

All 69 previous result sets and legacy `f5fa269eb60ee34f` over 292,711 rows
are unchanged. Five complete-file SHA256 gates and LF attributes protect all
new payloads even without the optional oracle. Pinned regeneration is
byte-identical. Fresh checks bind requested seed/count to every ordered input
pair, independently reconstruct widened rows and signaling-Float exclusions,
and run the real generic checker with only the two new corpora overlaid.
Three fresh samples and a larger 147,471 Double/116,689 Float raw sample pass;
the larger long64 probe checks 264,160 nearest results and 3,024,184 state
calls. Actual same-sized parse-valid target corruptions verify both unit
corpus-directory selections without renaming caller evidence.

Width-aware raw result/order and state result/order hashes are:

| Format / native long | Nearest hash / rows / skipped | State hash / calls |
| --- | --- | --- |
| Double / 32 | `47ab6ee726681988` / 48,194 / 364 | `6b19acdde5624b15` / 623,632 |
| Double / 64 | `d1266b38f3cc4b68` / 48,558 / 0 | `7ff3bc96257bad15` / 670,440 |
| Float / 32 | `243fedf2071a0191` / 17,718 / 364 | `b6038507f04a35c5` / 323,280 |
| Float / 64 | `8e36464ae1171755` / 18,082 / 0 | `ee4327d77e8838c5` / 369,840 |

Long32 skips only exponent words outside its native parameter range, after
validating row schema/order. Every eligible row runs all four modes and two
errno seeds; selected/nonfinite rows request all 32 incoming-flag subsets.
Actual flags can merge when raised. Per-call flags/errno/mode are checked
before hashing; hashes encode results/order, not hardware flag bits.

Six emulated targets agree on all 71 numerical sets in default/portable builds,
and 24 raw O0/O2/default/forced-Float-loop profiles agree on native long32/64
outputs and state. Each long64 profile checks 66,640 nearest results and
1,040,280 state calls; long32 checks 65,912 and 946,912. The larger raw sample
also passes O2/default on all six targets. Final i686 O0 callers have no
fldl/flds input loads. These are emulated probes, not physical-host/full
cross-target GoogleTest claims. Windows/LLP64, exhaustive input/environment
space and native32/application timing remain unrun.

Both native compilers detect all 64 source/state plant executions in C++ and
C17, requiring the other format to remain passing for format-specific defects.
Real short-narrowing defects detect on i686 and PowerPC32; int-to-long identity
variants pass as equivalent on those native-long32 targets. Thirty-two isolated
loader/value fixtures, five checksum corruptions, a valid recording process
and 12 output/process faults pass. Eight actual pinned numerical oracle faults
fail before publication; actual ignored-count/seed generator faults are caught
by complete-population verification. Recording-engine controls exercise both
wrapper dispatch commands, missing-family counterfactuals and optional/required
absence behavior even when numerical oracles skip; these are accounting,
not numerical oracle evidence. The unchanged five-file publisher's earlier
exception rollback/permission controls apply; publication is not crash-atomic.
Old runtime modules, including both scaling kernels, remain byte-identical.
Earlier expf/exp2f/atanf force-only deletion witness gaps remain unchanged.

Two predeclared paired benchmark runs per native compiler use eight discarded
paired warmups and 401 alternating pairs of 4,096 identical inputs across 11
ranges, two types and clean/preseeded UF/IX states: 44 cases per run. Integer
timestamps precede floating timing arithmetic; untimed host bit/class controls
and own exact batch-flag/errno/mode guards run separately. Host new flags,
exceptional errno and NaN payloads can differ. Both compiler contexts use the
same logical processor affinity, without CPU isolation or governor changes.
Compiler/library flags, target, linked host-libm identity and binary/source
hashes are retained with the measurements. The two runtime images may have
different host libraries; differences between contexts are not attributed
solely to compiler choice.

The following ranges enclose both entry states and both runs. Absolute columns
are independent min–max envelopes of median ns/call (gmath / host); ratio
columns enclose paired median gmath/host ratios and, in brackets, the envelope
of paired p10 through p90. Absolute envelope endpoints are not paired samples.

| API / range | GCC14 absolute ns (gmath / host) | GCC14 ratio [p10–p90] | GCC16 absolute ns (gmath / host) | GCC16 ratio [p10–p90] |
| --- | --- | --- | --- | --- |
| scalbln / normal | 2.632–5.067 / 3.762–6.627 | 0.670–0.764 [0.624–0.835] | 3.173–6.129 / 4.489–7.826 | 0.703–0.786 [0.589–0.846] |
| scalblnf / normal | 2.695–4.828 / 3.529–6.382 | 0.736–0.770 [0.708–0.815] | 2.578–5.021 / 4.631–8.369 | 0.556–0.604 [0.501–0.641] |
| scalbln / subnormal-input | 39.889–40.922 / 62.268–63.247 | 0.639–0.646 [0.623–0.678] | 39.116–44.810 / 60.125–69.349 | 0.649–0.653 [0.632–0.670] |
| scalblnf / subnormal-input | 6.836–7.667 / 63.187–70.048 | 0.108–0.111 [0.106–0.127] | 4.708–5.451 / 60.006–66.080 | 0.077–0.084 [0.076–0.092] |
| scalbln / exact-subnormal-result | 3.383–5.820 / 37.819–50.517 | 0.091–0.108 [0.076–0.122] | 3.369–3.480 / 39.474–41.366 | 0.085–0.086 [0.074–0.089] |
| scalblnf / exact-subnormal-result | 3.268–5.302 / 36.755–46.218 | 0.089–0.102 [0.077–0.116] | 3.261–3.490 / 36.873–39.924 | 0.088–0.089 [0.076–0.091] |
| scalbln / inexact-subnormal-result | 3.700–3.859 / 36.911–38.810 | 0.095–0.102 [0.082–0.123] | 3.430–3.510 / 39.324–41.613 | 0.083–0.089 [0.073–0.090] |
| scalblnf / inexact-subnormal-result | 3.963–4.411 / 37.719–41.193 | 0.100–0.107 [0.087–0.118] | 3.726–6.680 / 35.988–48.533 | 0.098–0.135 [0.088–0.155] |
| scalbln / rounded-normal | 3.759–3.770 / 37.819–38.783 | 0.096–0.098 [0.081–0.103] | 3.370–3.624 / 38.655–41.374 | 0.083–0.089 [0.077–0.130] |
| scalblnf / rounded-normal | 3.599–4.722 / 37.594–47.930 | 0.092–0.111 [0.082–0.133] | 3.285–3.644 / 36.016–39.856 | 0.089–0.095 [0.078–0.124] |
| scalbln / overflow | 2.909–3.622 / 3.430–3.725 | 0.848–0.996 [0.843–1.079] | 2.644–3.255 / 3.962–4.296 | 0.667–0.798 [0.665–0.901] |
| scalblnf / overflow | 3.172–3.363 / 3.447–3.635 | 0.922–0.931 [0.844–1.003] | 2.585–2.888 / 4.458–4.864 | 0.565–0.625 [0.562–0.824] |
| scalbln / long-max | 3.364–3.731 / 3.587–3.740 | 0.919–0.998 [0.845–1.031] | 3.343–3.621 / 3.917–4.081 | 0.832–0.892 [0.760–0.963] |
| scalblnf / long-max | 3.348–3.524 / 3.565–3.627 | 0.937–0.989 [0.920–1.079] | 2.715–3.051 / 4.341–4.581 | 0.625–0.687 [0.562–0.788] |
| scalbln / long-min | 3.531–3.628 / 4.367–4.610 | 0.768–0.814 [0.763–0.868] | 2.719–3.066 / 4.826–4.888 | 0.565–0.616 [0.554–0.662] |
| scalblnf / long-min | 3.074–5.355 / 4.306–6.258 | 0.706–0.780 [0.625–0.944] | 2.513–2.711 / 5.019–5.155 | 0.500–0.526 [0.451–0.557] |
| scalbln / zero-infinity | 2.759–4.211 / 1.894–2.611 | 1.440–1.615 [1.391–1.721] | 2.758–2.963 / 2.280–2.509 | 1.155–1.213 [1.152–1.341] |
| scalblnf / zero-infinity | 2.075–2.956 / 2.016–2.366 | 1.030–1.326 [0.997–1.402] | 2.387–2.569 / 2.528–2.771 | 0.885–0.977 [0.859–1.072] |
| scalbln / quiet-NaN | 2.762–4.177 / 2.312–2.987 | 1.214–1.387 [1.164–1.484] | 2.631–2.713 / 2.513–2.576 | 1.046–1.054 [0.997–1.103] |
| scalblnf / quiet-NaN | 2.208–3.079 / 1.808–2.289 | 1.217–1.324 [1.145–1.427] | 2.382–2.607 / 2.511–2.722 | 0.947–0.953 [0.898–1.055] |
| scalbln / signaling-NaN | 2.764–4.264 / 2.312–2.987 | 1.201–1.409 [1.164–1.479] | 2.715–2.900 / 2.637–2.714 | 1.008–1.098 [0.900–1.103] |
| scalblnf / signaling-NaN | 2.271–2.599 / 1.851–2.132 | 1.211–1.282 [1.182–1.446] | 2.319–2.506 / 2.577–2.711 | 0.878–0.926 [0.874–0.976] |

Normal/subnormal ranges improve on the measured host, while Double special
ranges and several GCC14 Float special ranges remain slower. Absolute times
vary substantially even with fixed affinity. Call/loop/checksum/timestamp work
and amortized first-exception costs are included. No overall, application,
physical cross-platform or general performance win is claimed. Forced-loop,
other-compiler and native-long32 timings remain unrun. Reproduce with
`make bench-long-scale`; correctness gates and standalone probe instructions
are in the design document.

## Float exponent conversion optimization

Only the Float finite normal exponent tail changes: an exact conversion and
unsigned whole-word zero mask replace the old exponent-zero branch. Strictly
negative subnormal exponents return immediately. The entire Double source
prefix and Float special dispatch match the API baseline byte-for-byte; no
other runtime module changes. The source mask does not guarantee branchless
machine code; GCC14 currently uses conditional integer movement. All 69
reference sets and legacy aggregate `f5fa269eb60ee34f` over 292,711 remain
unchanged.

Every possible finite exponent output is checked separately: 2,098 Double and
277 Float values, each reached by both signs of an exact-power input, four
modes, 32 requested incoming subsets and two errno seeds. Independent unsigned
integer encoding supplies the expected bits. This gives 1,216,000 logical
observations; optional actual-prior hooks make 2,432,000 physical calls,
resetting state and checking each against the targets. It enumerates the
conversion domain, not all raw inputs or complete hardware state space.
Domain result/order hashes are `f4c934bfef138325` and `717cc11f90d36325`.
Flags, mode and errno are asserted separately; requested subsets can merge.

Six emulated targets pass all 69 numeric sets default/portable, plus 24
O0/O2/default/forced-loop raw and finite-domain profiles with actual separately
compiled prior functions. Each raw profile retains 38,620 nearest records and
486,528 selected state records, now two calls per record. The domain adds the
1,216,000 logical observations per profile. Actual PPC32 repair deletion and
all-ones-mask controls detect negative zero at input one in the changed Float format,
at both optimization levels/default/loop (eight cases), with unchanged flags,
mode and errno. Native forced-negative-zero plants are distinct controls.
The final i686 O0 raw caller has no fldl/flds argument loads. These are emulated
probes, not physical hosts or full cross-target GoogleTest.

The native mutation suite grows from 70 to 76 source/state plants, each checked
by C++ and C17 with format-specific failure requirements. New plants cover mask
polarity, an all-zero mask and spurious zero-conversion inexact.
Default accounting calibration detects 11 metadata/output/status faults plus
an actual bounded direct-child timeout; identity-family/header compatibility
and rejected-family publication controls also pass. Recording processes do
not count as numerical oracle evidence. Optional native controls pass 31 cases
per GCC14/GCC16 compiler: three valid tools, individual-format wrong values,
NaN-bit changes, aliases and result-preserving flag/errno/mode corruption.
The selected corpus directory is forwarded to the raw controls.

Validation uses the declared API-baseline revision
`fad5c17ae0e9ffe8fed3f6540aacca6f30ed8d6f`, separately compiled with identical
compiler/library arguments, with only two public symbols renamed. Object,
compiler-driver and argument digests bind the chosen context, without
pretending to authenticate arbitrary source provenance. Changed object/flags/
compiler, missing baseline and a newer executable with invalid older object
are rejected; optional tools force relinking. The adjacent helper's default
identity/header bytes remain compatible. Default gates need no baseline or Git.

Independent mathematical/domain/recipe and blind reviews are resolved. Five
actual tool findings were patched: exact prior NaN comparison, selected-corpus
forwarding, isolated wrong-format and alias fixtures, and bits-preserving state
corruption calibration. No findings are deferred. No external libm source was
read or copied; own prior source is used solely for controlled comparisons.

Final full GCC14.2/GCC16.2 commands return zero, with persisted actual child
status and 213 main unit tests in 29 binaries each. Clang passes the same unit
set (unit-only); four focused ASan/UBSan tests pass. Host pinned regeneration
is byte-identical, and fresh independent references/checks pass. Optional
nested pinned oracles skip explicitly in the GCC16 image. All 76 source/state
plants pass on both compilers. Earlier expf/exp2f/atanf force-only deletion
witness gaps remain unchanged.

Earlier sign-bit-only and Double/Float candidates were rejected after measured
subnormal regressions, including a repeatable 40–60% Float cost. The final
Float-only whole-word mask was promoted after independent proof/admission
review and private archive-preserving measurements. Final measurements use the
promoted library, with a predeclared two runs per compiler after this phase's
validation jobs finished: eight discarded paired warmups, 401 alternating
pairs of 4,096 identical inputs per nine ranges, two formats and two entry
states. Integer timestamps, typed bit/state/errno guards and actual-prior
identity accompany absolute medians and paired ratio p10/median/p90. The normal
range samples binary exponents 0–19 for Double and 0–11 for Float; powers and
wide inputs supply broader finite coverage. No CPU/governor isolation is
claimed; frequency, code layout and linked caller context affect timings.

The table gives min–max paired medians across two runs and clean/UF-IX states.
Only Float changes. The unchanged Double source is a context control; its
ratios are not an optimization claim.

| Range | Float/prior GCC14 | Float/prior GCC16 | Double control/prior GCC14 | Double control/prior GCC16 |
| --- | ---: | ---: | ---: | ---: |
| Normal | 0.575–0.696 | 0.671–0.672 | 0.999–1.028 | 1.026–1.028 |
| Subnormal | 0.994–1.000 | 1.166–1.166 | 1.000–1.002 | 1.198–1.202 |
| Binary powers | 0.745–0.809 | 0.869–0.876 | 1.003–1.119 | 0.999–1.001 |
| Near one | 0.319–0.380 | 0.356–0.363 | 0.996–1.007 | 0.996–1.006 |
| Wide finite | 0.739–0.852 | 0.861–0.863 | 1.009–1.018 | 0.999–1.000 |
| Zero | 0.856–0.899 | 1.000–1.000 | 1.000–1.028 | 1.000–1.001 |
| Infinity | 0.999–1.000 | 1.000–1.001 | 0.850–0.857 | 0.833–0.835 |
| Quiet NaN | 0.833–0.926 | 0.999–1.000 | 0.853–0.858 | 0.833–0.835 |
| Signaling NaN | 0.984–1.000 | 0.997–1.001 | 0.857–0.908 | 0.999–0.999 |

Separately linked host-libm comparisons give:

| Range | Float/libm GCC14 | Float/libm GCC16 |
| --- | ---: | ---: |
| Normal | 0.858–1.077 | 0.601–0.603 |
| Subnormal | 0.780–0.819 | 0.583–0.584 |
| Binary powers | 0.859–1.112 | 0.601–0.602 |
| Near one | 0.859–1.026 | 0.601–0.602 |
| Wide finite | 0.859–1.020 | 0.601–0.602 |
| Zero | 1.144–1.267 | 0.800–0.800 |
| Infinity | 0.667–0.786 | 0.546–0.546 |
| Quiet NaN | 0.776–0.932 | 0.637–0.638 |
| Signaling NaN | 0.667–0.669 | 0.546–0.547 |

Normal Float absolute medians in actual-prior binaries span 1.116–2.272 ns
current versus 1.939–3.195 ns prior on GCC14, and 1.301–1.482 versus
1.938–2.189 ns on GCC16. Host-comparison binaries give 1.257–2.133 versus
1.465–1.951 ns on GCC14 and 1.117–1.119 versus 1.857–1.858 ns on GCC16.
Ratios are paired within each binary; absolute medians across binaries must
not be divided to infer additional gains. Call/loop/checksum/timestamp work
and amortized first-exception costs are included.

This supports substantial measured Float normal/near-one improvements with
a real GCC16 subnormal regression of about 16.6%. Unchanged Double controls
also drift by about 20% in some ranges, demonstrating context sensitivity;
that does not establish the Float slowdown is noise. The narrower increment
accepts this measured range tradeoff, with no application workload weights
or overall speed win established. Some GCC14 host-comparison cases remain
slower. Windows, exhaustive raw-input/environment space, physical cross-target
hosts, forced-loop timing and application performance remain unrun.

## Floating exponent validation

The two APIs bring classic real-function name coverage to 63/171: 32 Double,
31 Float and no long-double entries. Missing 25 Double + 26 Float = 51
float/double additions, or 108 including 57 long-double entries; complex adds
66 more. These are name counts, excluding fenv/macros/vendor extensions and
additional behavioral parity. A read-only 6,230-file source/header audit found
no project-owned logb/logbf production calls; broader coverage is intentional.
Consumers remain unmigrated.

Committed references contain 32,318 Double/6,302 Float raw inputs, including
every binade and subnormal leading-bit transition with neighboring values and
both signs. Raw integer-field rational decoding and independent pinned MPFR
conversion agree on exact exponents. All possible finite output exponents
occur in these strata; execution is not exhaustive over all raw inputs.
The new numeric sets are `logb e0aa81ad34f8834b` over 32,318 rows and
`logbf bb32234cb185f773` over 6,296 widened rows (Float signaling inputs are
excluded from generic widening). All 67 previous sets and legacy aggregate
`f5fa269eb60ee34f` over 292,711 results remain unchanged.

Raw result hashes are `e0aa81ad34f8834b` Double and `7ae1289a0939fb11` Float.
Selected all-mode result/order hashes are `5ca7e7db52126b65` over 399,656 calls
and `c405790601745025` over 86,872 calls. Actual flags, errno and mode are
compared separately before successful hash publication; digests do not encode
hardware flag states. Explicit finite boundaries, nonfinite cases and ordinal
sampling request all 32 incoming subsets, using actual raised flags when
hardware merges them. All rows run every mode and two errno seeds.

Five complete-file SHA256 checks and LF checkout attributes protect references,
with byte-identical pinned regeneration. Larger references check 130,318
Double/104,301 Float raw inputs and 2,958,480 selected state calls. Fresh
validation checks complete widened rows/exclusions, metadata, counts and paths,
and runs the real generic checker over all 69 sets with only the two fresh
corpora overlaid. Eight fresh widened corruptions detect; same-sized unit
selection and disposable empty-directory counterfactuals pass. The reused
publisher passes ten existing/absent exception-rollback controls across five
replacement positions; it is not crash-atomic.

Seventy default/forced-loop source/state plant executions pass both the C++
unit driver and standalone C17 executable. Shared defects must fail both
formats; format-specific defects must leave the other format passing. Controls
include quiet-only invalid, signaling-only payload preservation, flag-only
zero divide-by-zero loss, errno/mode/incoming-state changes and positive-zero
loss. An initially proposed '<' to '<=' minimum-normal mutation was equivalent
and correctly survived; the admitted threshold fault changes actual results.
Thirty-two native loader/value fixtures, ten complete-payload corruptions,
a valid recording process plus eight full output hash/count/order/path faults,
four schema controls, five actual oracle faults and four new numeric hash
omission/corruption controls detect. Two actual probe-header faults demonstrate
restoration after a late malformed row following executed calls. Both wrapper
commands' real family-dispatch omission is calibrated with a recording engine;
those controls are not numerical oracle evidence. Optional missing-engine mode
skips explicitly, while required absence fails without publishing outputs.

Six emulated targets match all 69 numeric sets in default/portable builds and
24 raw O0/O2/default/forced-loop profiles, checking 38,620 nearest records and
486,528 selected state calls each. Initial PPC32 directed-mode checks exposed
negative exponent-zero bits from software integer conversion. Explicit raw
positive-zero construction fixes that case before final passing profiles.
The i686 O0 caller has no fldl/flds argument loads. These are emulated probes,
not physical-host/full cross-target GoogleTest coverage. External suite runners
remain unchanged. Windows, exhaustive raw-input/state space and application
performance remain unrun.

Final recorded full GCC14.2/GCC16.2 commands return zero, with 212 unit tests
in 29 binaries each. Clang passes the same unit set (unit-only), and three
focused ASan/UBSan tests pass. Independent contract/proof, blind review and
follow-ups are resolved, with no findings deferred. Two initial outer command
sessions reported signal termination despite complete passing logs; confirmed
reruns persist the actual successful child return codes. No failed or ambiguous
invocation is counted as a passing final run. Earlier expf/exp2f/atanf force-only
deletion witness gaps remain unchanged.

Two final native x86-64/GCC14.2 runs use eight discarded alternating paired
warmups followed by 401 alternating pairs of 4,096 identical values per
format/range/state case. Integer timestamps, compiler/build identity, exact
bit/class guards, expected new flags and own errno preservation accompany
absolute median ns/call and paired ratio p10/median/p90. Host NaN payloads and
exceptional errno may differ. Median gmath/libm ratios across the two runs and
clean/UF-IX entry states are:

| Input range | Double | Float |
| --- | ---: | ---: |
| Ordinary normal | 1.283–1.371 | 1.399–1.414 |
| Subnormal | 0.601–0.603 | 0.667–0.668 |
| Binary powers | 1.128–1.130 | 1.141–1.152 |
| Near one | 2.408–2.440 | 2.689–2.708 |
| Wide finite | 1.125–1.128 | 1.027–1.159 |
| Zero | 0.998–1.001 | 0.857–0.858 |
| Infinity | 0.778–0.778 | 0.556–0.557 |
| Quiet NaN | 0.778–0.779 | 0.556–0.559 |
| Signaling NaN | 0.667–0.668 | 0.557–0.559 |

Ordinary normal absolute medians span 2.287–3.111 ns gmath versus 1.783–2.240 ns
libm for Double, 2.067–2.208 versus 1.463–1.562 ns for Float. These include
call/loop/checksum/timestamp work and amortize initial exception costs. Ordinary
and near-one inputs remain slower, despite measured subnormal/special gains.
Timings describe the native default builtin path; forced-loop/other-compiler/
other-platform timing and application workloads remain unrun. No overall
performance win is claimed. A later result-preserving zero-repair strategy may
address the measured branch overhead, but no unimplemented candidate is proven.

## Fraction split validation

The two APIs bring classic real-function name coverage to 61/171: 31 Double,
30 Float and no long-double entries. Missing 26 Double + 27 Float = 53
float/double additions, or 110 including 57 long-double entries; complex adds
66 more. These count names, excluding fenv/macros/vendor extensions and
additional behavioral parity. The prior read-only audit found no project-owned
modf/modff production calls; this advances broader coverage. Consumers remain
unmigrated.

Committed independent references contain 32,022 Double and 6,180 Float inputs.
Exact rational truncation and pinned MPFR independently agree on both outputs;
all comparisons require exact bits. Four new supplemental result sets preserve
every previous line and the legacy aggregate `f5fa269eb60ee34f` over 292,711:

| Result set | Hash | Rows |
| --- | --- | ---: |
| modf fraction | a15da59a64013194 | 32,022 |
| modf integral | a2eed88d4ae647d5 | 32,022 |
| modff fraction, widened | feea8ae7dd573424 | 6,174 |
| modff integral, widened | 3f7a8130f27b762b | 6,174 |

The Float widened sets exclude signaling inputs. Raw result-pair hashes are
`81bc8f432ad796cc` Double and `c12a535f7cf63fa7` Float; selected all-mode result/
order hashes are `8e022d9fe7fe7da5` over 778,704 calls and `f2e4bcb03b4bec25`
over 157,408 calls. Actual flags, errno and mode are asserted separately,
including present/NULL outputs. These hashes do not encode hardware flag bits.
A larger sample checks 130,022 Double/104,179 Float inputs and 5,883,984 selected
state calls; fresh samples check requested metadata/counts/path and generated
hashes, including equal-sized populations and unit selection. Mandatory seven
SHA256 checks, LF attributes and byte-identical pinned regeneration protect
complete payloads. Publication exception rollback covers all seven replacement
positions with existing/absent outputs and preserved permissions; no
crash-atomic claim.

All 32 source/state plants detect through the affected format's test while the
other format remains passing. Controls include omitted-output-only return/
flag defects, zero-errno and mixed incoming flags. Thirty native loader/value
fixtures cover both formats, including NUL, width and numeric-metadata errors;
fourteen checksum corruptions include parse-valid semantic output changes.
A valid recording process and eight full output hash/count/order/path defects,
four schema/omission controls and eight new supplemental hash omission/value
controls detect. Four actual oracle-source faults fail before publication.
Both new wrapper commands' real dispatch omission is calibrated with a recording
engine; those controls are not numerical oracle evidence. Optional absence
skips explicitly, while required absent-engine mode fails specifically.

Six emulated targets agree on all 67 numeric result sets in default/portable
builds and 24 raw O0/O2/default/portable profiles: 38,202 nearest records plus
936,112 selected state calls per profile. Direct raw memcpy preserves signaling
inputs on i686; the final O0 caller has no fldl/flds argument loads. An initial
probe exposed a value-return test helper quieting signaling input before flag
setup, then an assembly guard exposed remaining unrelated value-return sentinel
helpers. Both were removed before final passing profiles. These are emulated
probes, not physical-host/full cross-target GoogleTest results; Windows,
exhaustive input/state space and application timing remain unrun. External
suite runners are unchanged; standalone reproduction is in the design notes.

Full final GCC14.2/GCC16.2 default gates pass, with 209 unit tests in 28
binaries on GCC14/GCC16/Clang (Clang unit-only) and three focused ASan/UBSan
tests. Independent proof, blind review and follow-ups are resolved, with no
finding deferred. Build wiring and an old wrapper-dispatch mutation anchor
collision were corrected before final passing gates; the old calibrated anchor
is preserved. Initial full runs hit a 1 GiB resident cap, then final runs pass
under 2 GiB with reduced parallelism. These failed attempts are not reported
as numerical failures or passing runs. Earlier expf/exp2f/atanf force-only
deletion witness gaps remain unchanged.

Two final-build same-processor paired runs on native x86-64/GCC14.2 use 401
alternating pairs of 4,096 identical values, non-NULL integral outputs, clean/
UF-IX entry states, zero/nonzero errno and integer timestamps. Untimed guards
check both result bits against host libm. Compiler identity, build arguments,
absolute median ns/call and paired ratio p10/median/p90 are retained. Median
gmath/libm ratios across both runs and entry states are:

| Input range | Double | Float |
| --- | ---: | ---: |
| Mixed fractions | 0.949–1.000 | 0.998–1.001 |
| Below one | 0.750–0.751 | 0.750–0.775 |
| Integral binades | 0.998–1.087 | 0.638–0.779 |
| Subnormal | 0.750–0.883 | 0.754–0.942 |
| Wide finite | 1.099–1.162 | 1.119–1.153 |

Final mixed-fraction absolute medians are 1.437–1.785 ns gmath versus
1.499–1.784 ns libm for Double, 1.608–1.675 versus 1.608–1.672 ns for Float.
Earlier samples varied substantially, including slower mixed-fraction ratios;
these final-build runs follow completion of the heavy validation. Call/loop/
checksum/timestamp overhead is included. Common mixed inputs are near parity;
wide finite inputs remain slower. No overall/application/cross-platform win,
other-compiler timing or exhaustive performance claim is made.

## Adjacent direction optimization

This performance phase adds no API: classic real-function name coverage remains
59/171, with 55 Float/Double or 112 including long-double entries missing.
Twenty-one cohesive phases now supply 39 added APIs, three optimizations and
certificate maintenance. Consumers remain unmigrated.

Replace two signed-order key constructions with a branchless sign/magnitude
predicate and explicit-width magnitude masks. NaN/equality/zero behavior,
result bits, all exception classes and caller-state contracts are unchanged.
Same-sign larger magnitude moves outward; all other ordered cases move inward.
The no-wrap step `(x-1)+(outward<<1)` is valid after the existing dispatch.
Independent investigation/review verifies width and bounds. A simple branched
prototype did not improve common Float inputs and was not admitted; the
branchless form did. Existing tables and all other runtime modules are unchanged.

Full final GCC14.2/GCC16.2 default gates, 206 tests in 27 binaries on each of
GCC14/GCC16/Clang (Clang unit-only) and four focused ASan/UBSan tests pass.
All 36 direction/special/state plants and existing reference/loader/SHA/output/
oracle controls pass. New accounting/context/boundary/cancellation calibration
has 13 controls; optional native fixtures prove valid/wrong/aliased references
in all three tools (nine cases per compiler). Independent blind review and
follow-ups are resolved, including a compiler-identity bug: the invoked driver
name must be included even when clang/clang++ resolve to one executable.
An initial full-gate attempt rejected an unrecorded Make macro-flag variable;
inlining the constant definitions restored the stamp gate before final passing
full runs. No numerical failure or waived gate is hidden by that correction.

The actual prior public functions come from
`6d469e66690c0ce879e0b48a5768d5f477965c85`, separately compiled with each
current library compiler invocation/flags and only public symbols renamed.
Source/helper bytes are checked against Git. Object, library-argument and
compiler-driver/context digests accompany the declared revision in retained
results. Metadata binds supplied artifact/build bytes, not arbitrary source
provenance. Forced optional-tool relinking and an older-object/sidecar switch
control prevent stale configuration reuse; absent configuration and aliased
function pointers fail explicitly. A deliberately wrong native reference is
recognized as a result mismatch, and raw diagnostics identify current/prior.

Confirmed final native GCC14 scans match all 4,294,967,296 raw binary32 source
patterns toward both infinities: 8,589,934,592 paired result comparisons over 32
disjoint step-one intervals. Metadata accounts for every interval and result.
Case analysis reduces other ordered destinations to inward/outward selection;
finite-sign/magnitude, zero/equality and NaN-target cases remain separately
covered. The fast scan adds explicit boundary neighborhoods and seven target
classes under four modes: 1,836,688 evaluations, with overlap between strata
permitted. Result-only scans do not prove independent accuracy or exhaustive
exception/mode behavior. The raw hooks separately check current and actual
prior against pinned targets over 143,236 nearest records and 632,064 selected
all-mode/flag-subset/errno records per compiler (two physical calls per logical
record). These retain the existing normalized hashes; actual incoming flags,
errno and mode are asserted separately.

All 63 function hashes, all five adjacent-reference payload SHA256 values and
legacy aggregate `f5fa269eb60ee34f` over 292,711 results remain unchanged.
Six emulated targets match all 63 numeric sets default/portable and 24 O0/O2
raw profiles, including the unchanged adjacent raw/state hashes/counts. The
i686 O0 caller retains no fldl/flds argument loads. These are emulated probes,
not physical-host/full cross-target GoogleTest results. Windows, exhaustive
pair-space and exhaustive per-call flag/mode behavior remain unrun.

Two same-processor paired runs per compiler use 401 alternating pairs of 4,096
identical typed inputs across clean/UF-IX and zero/nonzero errno states.
Integer timestamps, untimed exact-bit/alias guards, baseline identities,
absolute medians and paired ratio p10/median/p90 are retained. Both compilers
ran on the same x86-64 host (GCC16 inside its build image); separate actual-prior
objects preserve each compiler's context. Median current/prior and current/libm
ratios across the two runs and entry states are:

| Input range | GCC14 Double/prior | GCC14 Float/prior | GCC16 Double/prior | GCC16 Float/prior |
| --- | ---: | ---: | ---: | ---: |
| Common normal | 0.343–0.356 | 0.513–0.575 | 0.435–0.499 | 0.403–0.445 |
| Equality | 1.000–1.001 | 0.993–0.999 | 0.998–1.005 | 0.953–0.999 |
| Subnormal inputs | 0.534–0.615 | 0.542–0.613 | 0.707–0.791 | 0.442–0.474 |
| Normal boundary | 0.447–0.606 | 0.498–0.538 | 0.554–0.589 | 0.601–0.609 |
| Overflow/inward | 0.493–0.519 | 0.552–0.587 | 0.570–0.596 | 0.561–0.577 |

Common current/libm medians are 0.358–0.372 Double and 0.674–0.741 Float on
GCC14, 0.317–0.332 Double and 0.530–0.566 Float on GCC16. Common current/prior
absolute medians span 1.577–1.843/4.395–4.950 ns Double and 1.882–3.344/
3.511–6.191 ns Float on GCC14, 3.818–4.266/8.576–9.428 ns Double and 2.577–4.874/
5.882–11.089 ns Float on GCC16. Absolute times vary substantially between runs,
so do not compare compiler speeds from these samples. Call/loop/checksum/
timestamp overhead and amortized first-exception costs are included. Equality
is approximately unchanged against prior. Range-specific gains address the
measured common Float overhead; no overall library/application/cross-platform
speed win is claimed. Host errno semantics differ where previously specified.

## Adjacent-value validation

This records the API-addition phase; the direction optimization above supersedes
its earlier timing figures.

The two APIs bring classic real-function name coverage to 59 of 171: 30 Double,
29 Float and no long-double entries. Missing 27 Double + 28 Float = 55 float/double
additions, or 112 including 57 long-double entries; complex arithmetic adds 66
more. These are name counts, excluding fenv/macros/vendor extensions and
additional behavioral parity. Twenty cohesive phases now add 39 APIs, two
optimizations and certificate maintenance. Consumers remain unmigrated.

Full default GCC14.2/GCC16.2 gates and 206 unit tests in 27 binaries pass, with
Clang unit-only coverage and four focused ASan/UBSan tests. Independent contract
investigation, blind review and follow-ups are resolved. Review strengthened
standalone parsing, independent fresh widening, immediate destinations,
zero-errno and all-subset state coverage. A residual embedded-NUL bypass in
the standalone probe was reproduced and fixed with byte-counted input; both
unit validation and SHA already rejected that corruption. No review finding
is deferred.

Committed raw references contain 125,378 Double and 17,858 Float pairs; 17,752
Float pairs remain after excluding signaling inputs for exact widening.
Fraction spacing and pinned directed MPFR agree on targets, with explicit
fixed boundary controls. A larger 173,378/65,858-pair sample and three fresh
128,378/20,858-pair samples pass values, independent widened-row consistency
and generated raw/state hashes. All five payloads have mandatory complete
SHA256/LF gates and byte-identical pinned regeneration. Fresh checks verify
metadata/populations/directory, including a disposable empty-directory
counterfactual; caller evidence is never renamed. The actual old-family
directory typo is detected with equal-sized fallback. Actual wrapper dispatch
omission is separately detected for both normal/fresh commands using a
recording engine. Optional nested-oracle absence skips explicitly; strict
required absence fails.

All 36 source/state plants detect, including conditional zero-errno writes and
mixed-flag clearing on both APIs. Fifty unit-loader rejection fixtures,
20 independent raw-loader negatives, seven widened-payload negatives, five
complete-file checksum corruptions, eight raw-output field corruptions,
seven pinned oracle faults and four supplemental hash omission/corruption
controls detect. Overflow and zero/subnormal UF deletion variants are real
flag-only controls: integer construction introduces no preceding FP flag.
Earlier expf/exp2f/atanf force-only deletion witness limits remain unchanged.

New supplemental sets are `nextafter beb51b91820d1a0c` over 125,378 results and
`nextafterf acbbbeef9ad7711f` over 17,752. All 61 previous hashes and legacy
aggregate `f5fa269eb60ee34f` over 292,711 results remain unchanged. Six emulated
targets agree on all 63 numeric sets in default/portable profiles. Raw O0/O2
profiles on i686, AArch64, s390x, PowerPC64, PowerPC32 and SPARC64 agree:

| API | Raw result/flag hash | Raw pairs | All-mode hash | State calls |
| --- | --- | ---: | --- | ---: |
| nextafter | `3c4a5af59878d4cc` | 125378 | `79a3304685a58bdd` | 424448 |
| nextafterf | `1b1f2fec1551d519` | 17858 | `b79be56e77366a25` | 207616 |

State calls request four modes, 32 incoming-flag subsets and both zero/nonzero
errno seeds on selected pairs, asserting actual incoming state separately
from the unseeded normalized-flag hash. The larger native probe checks 239,236
nearest results and 826,112 state calls. The i686 O0 raw caller contains no
x87 fldl/flds argument loads. These are emulated probes, not physical-host or
full cross-target GoogleTest coverage. Windows, exhaustive pair-space testing
and application timings remain unrun.

Two same-processor runs use 401 alternating pairs of 4,096 identical inputs,
clean/UF-IX states and zero/nonzero errno, integer timestamps, untimed host-bit
guards, absolute medians and paired ratio p10/median/p90. Call/loop/checksum/
timestamp overhead and amortized first-exception costs are included. Median
gmath/libm ratios across runs/entry states are:

| Input range | Double | Float |
| --- | ---: | ---: |
| Common normal | 0.949–0.990 | 1.247–1.424 |
| Equality | 0.701–0.776 | 0.876–0.877 |
| Subnormal inputs | 0.765–0.801 | 1.141–1.152 |
| Normal boundary | 0.779–0.783 | 1.033–1.059 |
| Overflow/inward | 0.608–0.631 | 0.980–1.013 |

Common absolute medians span 5.854–6.565 ns Double (host 6.042–6.735 ns) and
5.608–5.911 ns Float (host 4.229–4.613 ns). Earlier runs varied. Double samples
show some range-specific gains; common Float inputs remain slower. No overall,
application or cross-platform win is claimed, and host errno semantics differ
where specified. A later result-preserving sign/magnitude simplification may
address Float overhead; it is not implemented or measured here.

## Float decomposition/scaling validation

The four APIs bring classic real-function name coverage to 57 of 171: 29 Double
and 28 Float. Missing entries are 28 Double, 29 Float and 57 long double: 57
float/double additions, 114 including long double. Complex arithmetic would add
another 66 entries. Name coverage excludes fenv/macros/vendor extensions and
does not establish full behavioral compatibility. Across nineteen cohesive
phases, 37 APIs, two optimizations and certificate maintenance have been added;
consumers remain unmigrated.

Full GCC14.2/GCC16.2 default gates pass; 202 unit tests in 26 binaries pass on
GCC14/GCC16/Clang (Clang unit-only), plus three focused ASan/UBSan tests.
Independent contract investigation and blind review/follow-up are resolved.
The review tightened generator/loader population limits, bounded parsing,
fresh raw/state coverage, publication rollback, mutation coverage and source
formatting. No finding remains deferred from this phase.

Committed references contain 178,280 raw input/exponent rows, 178,156 widened
scaling rows and 4,196 decomposition/classification rows. Fraction and pinned
MPFR agree on numerical targets; exception classes derive from the stated
contract, with fixed tie/overflow/NaN controls. A larger
560,298-row sample and three fresh populations (178,235/178,289/178,222 rows)
pass values and their generated raw/state hashes. Pinned regeneration is
byte-identical; all five payloads have mandatory SHA256 gates and LF protection.
The loader independently certifies exact fractions, exponents, target rounding
cells and flags; 21 malformed/incorrect-reference fixtures reject. Fresh
selection verifies metadata, requested population and directory. An actual
old-family environment-variable typo is rejected even with equal-sized fallback;
a disposable empty-directory counterfactual checks ignored paths without
renaming caller evidence. Optional engine absence skips explicitly; required
absence fails. Individual publication write/replace failures and permission/
cleanup controls pass, together with rollback for each of five final replacement
failures against existing and absent destination sets. Publication is exception-
recoverable, not crash-atomic; SHA checks reject interrupted mixed generations.

All 72 native/default/forced-loop source/state plants detect, including separate
state violations in each API, special sentinels, ties and a real flag-only
rounded-normal IX witness `(00ffffff,-1)`. Five payload corruptions, four raw
output-field corruptions, four oracle faults and eight supplemental function
hash omission/corruption controls also detect. The earlier expf/exp2f/atanf
force-only deletion witness limits remain unchanged.

New supplemental result sets are:

| Function | Result hash | Rows |
| --- | --- | ---: |
| scalbnf | `27a1b98daffdda7a` |178156|
| ldexpf | `27a1b98daffdda7a` |178156|
| frexpf | `8bccabb7ed1f52ec` |4196|
| ilogbf | `0ef843f80e25384f` |4196|

All 57 prior function hashes and legacy aggregate `f5fa269eb60ee34f` over 292,711
results remain unchanged. Six emulated targets (i686, AArch64, s390x,
PowerPC64, PowerPC32 and SPARC64 Linux) match all 61 sets in default/portable
builds. Raw O0/O2 default/forced-loop probes match 891,400 nearest results plus
137,060 selected all-mode/incoming-state calls per configuration: nearest hash
`bc063b38a0fcf7d3`, all-mode hash `cb47fc4002f27725`. The larger native probe
checks 2,801,490 nearest results and 350,140 state calls. Existing width-aware
integer-rounding probes also pass on all six emulated targets. These are
emulated probes, not physical-host or full cross-target GoogleTest results.
Windows, exhaustive all-input scaling and application timings remain unrun.

Two same-processor benchmark runs use 401 alternating pairs of 4,096 identical
inputs per range/function/entry state. Both clean and preseeded UF/IX states are
checked outside timing; integer timestamps precede floating timing arithmetic;
untimed typed bit/exponent agreement with host nearest results is required.
Reported output includes absolute median ns/call and paired-ratio p10/median/p90.
For normal exact inputs, median gmath/libm ratios are 0.785–0.786 (scalbnf),
0.855–0.857 (ldexpf), 1.165–1.167 (frexpf) and 0.500–0.502 (ilogbf). Absolute
normal medians span 2.455–2.717 ns, 2.672–2.935 ns, 1.532–1.757 ns and 1.092–1.228 ns,
respectively. Subnormal-input ratios are approximately 0.053/0.058–0.059/0.050/
0.179–0.192; tiny rounded scaling 0.114–0.130 and rounded-minimum-normal
scaling 0.096–0.110. Overflow scaling ratios vary 0.751–0.930. Call/loop/checksum/
timestamp overhead is included; host errno/directed semantics differ where
explicitly documented. Earlier unpinned runs varied. These measurements show
range-specific gains and ordinary frexpf overhead, not an overall, application
or cross-platform performance win.

## Notes for the next numerical phase

Base logarithms now retain the precision reserve in `log_dd` with generated
split reciprocals. Their ordinary scalar-call paths remain slower than host
libm; direct base-specific tables remain a later optimization opportunity.

Exp2 now uses exact reduction by multiples of 1/128 and the existing table and
reconstruction polynomial, with explicit -1075/-1074/-1022/1024 boundary tests.
Future float elementary operations must use binary32 rounding and ulp spacing
in their reference data, not a binary64 corpus tolerance.

## Verification and remaining limits

The atanf specialization preserves every numerical contract while removing
fixed-abscissa operand/quadrant work. The binary atan2 function, shared kernel,
helpers and table are unchanged in source. Full GCC14.2/GCC16.2 default gates
pass, with 199 unit tests in 25 binaries on GCC14/GCC16/Clang (Clang unit-only),
five focused ASan/UBSan tests and resolved independent review follow-ups.
All 57 committed function hashes, legacy aggregate `f5fa269eb60ee34f` and
native-width integer-rounding probe contracts remain unchanged. Twenty unary
implementation/state plants and five reference checksum controls detect.
Moving the sign after narrowing is specifically caught by all-mode equality.
Deleting only the final normal IX force escaped the tested inputs because
other kernel/cast operations already raise IX. The production force remains;
a normal-path IX-loss mutation is detected, which does not establish that
narrow force-only deletion coverage.

Native GCC14 result-only scans cover every signed finite binary32 encoding:
4,278,190,080 inputs, including both zeros, under nearest in 32 disjoint
step-one intervals. They match both the unchanged current binary path and a
separately compiled actual prior public function. This proves compatibility
for those builds, not independent reference accuracy or exhaustive exception
behavior. Sampled all-mode checks compare bits, flags, errno and mode for
45,882 inputs with individual incoming exception seeds; the actual-prior
variant passes 1,284,696 paired observations. The 107,903-row independent
larger corpus also passes, with reported closed-cell error about 0.50000002
ULP; general correct rounding remains unclaimed. Pinned regeneration/fresh
checks preserve committed reference bytes.

Six emulated targets agree on all 57 numeric sets in default/portable builds,
and 24 O0/O2 default/portable raw probes retain nearest hash
`ba74d43d61e3eaf0` and all-mode hash `97c05e26310d4b1c` over 42 fixtures.
Each target additionally compares 65,280 signed encodings under all four
modes at O2 (261,120 input/mode evaluations). These are emulated probes, not full cross-target GoogleTest or
physical hosts. Windows and exhaustive directed-mode/exception validation
remain unrun. The comparison runner validates interval/count metadata, has
configurable timeouts distinct from mismatch failures, and cancels active
scans promptly on failure; deliberately wrong counts/intervals, later failures,
timeouts and child cleanup have been calibrated.

Two paired benchmark runs on the same allowed processor use the actual prior
module from `a606f32d9428e5d5b4f866a101f644f9374d7f21`, compiled with matching
library flags and public symbols renamed before linking beside the candidate.
This preserves the prior compiler context. The default benchmark separately
labels its old-wrapper-body/current-kernel baseline. Each run uses 401
alternating pairs of 4,096 inputs; every range is reused unchanged in clean
and preseeded UF/IX states, with untimed equality checks, integer timestamps,
median ns and ratio p10/p90. Relative times are:

| Input range | New / actual prior | New / host libm |
| --- | ---: | ---: |
| Common signed | 0.665–0.683 | 1.046–1.089 |
| Table | 0.667–0.669 | 1.125–1.126 |
| Direct | 0.620–0.654 | 0.877–0.912 |
| Tiny normal | 0.316–0.318 | 0.463–0.501 |
| Subnormal | 0.257–0.258 | 0.047 |
| Wide finite | 0.452–0.465 | 0.882–0.897 |

Ratios include call/loop/checksum/timestamp overhead. Unpinned runs showed
substantial subnormal timing variation, including much smaller gains. Common
and table ranges remain slower than host libm on these measurements; no
workload-wide or cross-platform speed win is claimed. This phase adds no API:
classic real-function name coverage remains 53 of 171, with 61 float/double
and 57 long-double entry points missing; behavioral parity is additional work.

The integer-rounding phase passes full final GCC14.2/GCC16.2 default gates,
198 unit tests in 25 binaries on GCC14/GCC16/Clang (Clang unit-only), and
four focused ASan/UBSan tests. Independent contract investigation and blind
review follow-ups are resolved. The new module is included in both legacy
mutation-harness object lists; initial incomplete-list failures were corrected
before the passing full runs. Thirteen native implementation/state plants,
four pinned oracle numerical faults, six payload checksum corruptions and
five actual probe-output field corruptions detect. Two signed32 post-rounding
range/sign defects detect on both i686 and powerpc32 emulation; LP64 default
runs skip those observationally equivalent mutations explicitly. Fresh guards
reject wrong metadata and ignored paths even with equal-sized fallback;
omission/corruption controls detect for all four new function hashes.

Committed full references contain 22,308 binary64 and 7,758 binary32 inputs,
each with exact signed32/signed64 answers and invalid classes. Six payloads,
including both native-width probe hashes, have mandatory complete-file SHA256
and LF protection. Pinned regeneration is byte-identical; three fresh samples
and a larger 224,060-input sample pass. The common valid signed32 subsets add
four portable result sets without folding native-width boundary differences
into a supposedly identical result hash:

| APIs | Common rows | Result hash |
| --- | ---: | --- |
| lround, llround | 12,886 each | `29062da116a95b78` |
| lroundf, llroundf | 5,792 each | `f55e957431a9f6ae` |

All 53 previous hashes and legacy aggregate `f5fa269eb60ee34f` remain unchanged.
Six emulated targets agree on all 57 sets in default/portable configurations.
Raw/full O0/O2 default/portable probes check 60,132 nearest public results and
51,408 selected all-mode/incoming-state calls per configuration. Native long32
uses nearest hash `f6b27ba135a01251`, all-mode hash `fc34d8bb72c277fd`;
long64 uses `11187661db241e79` and `8f0b8b6d02ea47e5`. The larger sample also
passes all six O2/default native-width probes, with 448,120 nearest results
and 313,992 selected-state calls each. These are emulated probes, not physical
hosts or full cross-target GoogleTest. Windows/LLP64 validation and native
32-bit timing remain unrun. Host pinned oracle controls pass; nested GCC16
optional controls skip explicitly, and required unavailable-oracle mode fails.

Two same-binary timing runs use 401 alternating pairs of 4,096 inputs per
range with clean and preseeded IX entry states. Every population first passes
untimed integer-result agreement, destination-bound and invalid checks.
The tool reports candidate/host median ns and paired ratio p10/p90. Across
both states/runs, common and half-tie double-input medians are about 1.14–1.22
of host libm, Float inputs 1.46–1.65; subnormal ranges are 0.75–0.87. Large
valid integral double inputs are 0.95–1.00, Float inputs about 1.41. Common
inputs use a small grid in [-4096,4096); these are controlled microbenchmarks,
not a project workload. Absolute timings vary between runs; call/loop/checksum
and timestamp overhead remain included. No overall/application speed win is
claimed. The initial capability phase favors exact deterministic contracts;
normal-range performance remains work to do.

The atanf phase passes full default GCC14.2/GCC16.2 gates and 194 unit tests
in 24 binaries on GCC14/GCC16/Clang (Clang's full gate set was not repeated).
Four focused ASan/UBSan tests pass. Independent numerical investigation and
blind review with two follow-ups are resolved. Seven wrapper/state plants
and five complete-payload checksum corruptions detect; publisher failure,
permissions and cleanup controls pass. Fresh selection rejects incorrect
metadata and ignored paths even with equal-sized fallback. Result-hash
omission/corruption controls also detect.

The committed 13,114-row corpus has SHA256
`9b5cf28ae9a2f394cad6d134ca3eaa227b454610434d73bc6c871c2435d05df6`.
Its result set 53 is `471e594171d32a6d`; all 52 previous function hashes and
legacy aggregate `f5fa269eb60ee34f` remain unchanged. A larger 107,903-row
sample and three fresh samples pass; the maximum conservative closed-cell
error is 0.50000002 ULP, under the 0.51 implementation regression cap.
General correct rounding remains unclaimed. Six emulated targets agree on
all 53 numeric sets in default/portable builds. Raw O0/O2 default/portable
probes agree on 42 fixtures, nearest hash `ba74d43d61e3eaf0` and all-mode
hash `97c05e26310d4b1c`; 1,176 calls separately assert flags, errno and mode
per configuration. These are emulated probes, not physical-host/full
cross-target GoogleTest claims. General directed accuracy remains unpromised.

Two successive same-binary benchmarks each use 401 alternating pairs of
4,096 inputs per range, with clean and preseeded UF/IX batch-entry controls.
Across those states/runs, median gmath/libm ratios are about 1.46–1.52 common,
1.68 table, 1.39–1.42 direct, 1.59–1.72 tiny normal, 0.18 subnormal and
1.99–2.09 wide finite. Integer timestamps and explicit entry-state checks
keep timing conversion from pre-raising IX. Entry-state controls amortize
first-exception costs across a batch; ratios include call/loop/checksum work.
The wrapper remains slower on most ranges; no overall or application speed
win is claimed. Unary specialization is a possible later optimization.

All four numerical budget certificates now reject optimized Python before
imports or proof work. `make check-budget-optimization` exercises -O, -OO and
PYTHONOPTIMIZE=1/2 on every certificate without requiring numerical dependencies,
then runs normal positive controls in the pinned image. The 16 negative probes
are mandatory; unavailable optional normal controls skip explicitly, and
required-oracle mode fails closed. This closes the earlier logf/log10f/hypotf
guard follow-up without changing runtime code, reference payloads or hashes.
Independent review also hardened required-script discovery, pre-import
rejection and image/version timeouts. Full GCC14.2/GCC16.2 default gates
pass, including 190 unit tests and all 52 committed result sets. The gate
itself passes under optimized Python; optional/required missing-image paths
and deliberately broken guards, imports, output and discovery are checked.
Normal pinned controls pass on the host and skip explicitly in the GCC16
image. No runtime change calls for new cross-target or performance claims.

The atan2f phase passes full default GCC14.2/GCC16.2 gates, 190 unit tests
on GCC14/GCC16/Clang and seven focused ASan/UBSan tests. Independent numerical
and blind reviews with follow-up are resolved. All 36 implementation/state
plants, 37 loader fixtures, four oracle faults, complete-payload/raw/output
hash corruptions, omitted entry and actual former-directory-typo checks pass.
The ordinary oracle gate verifies requested fresh metadata/population/path.
Its missing-directory probe leaves caller evidence untouched even on process
termination. The new certificate rejects optimized Python rather than printing
PASS with assertions disabled. Host pinned checks run; nested optional checks
skip explicitly in the GCC16 image. All 52 function result sets and the old
aggregate match on six emulated targets, with raw default/portable -O0/-O2
probes and 21,504 all-mode/incoming calls per run. The 229,222-row sample and
three fresh seeds pass; general all-input correct rounding, directed numerical
accuracy, physical-target timing and application performance remain unclaimed.

The hypotf phase passes full default GCC14.2/GCC16.2 gates, 183 unit tests
on GCC14/GCC16/Clang and seven focused ASan/UBSan tests. Independent numerical
and blind reviews with follow-up are resolved. Native mutation checks detect
42 implementation/state plants; forced-portable checks detect 31 and explicitly
skip 11 unavailable hardware plants. Both configurations pass 35 loader fixtures,
four oracle faults, strict target/reference integrity, raw/output hash and
actual former-directory-typo guards. Fresh metadata/population/path checks run
in the ordinary oracle gate too. The pinned certificate independently models
final flags and rejects five real-input flag-only deletions across all modes.
Host pinned checks run; optional nested oracles/certificates skip explicitly
in the GCC16 image. All 51 result sets and the old aggregate agree across six
emulated targets. Final 792-case raw probes pass default/portable at -O0/-O2;
22,176 calls per run separately assert all-mode/incoming state. Larger references
cover 229,568 pairs with strict nearest-target certificates and the same
0.50000003 conservative closed-cell bound. Physical-target timing, vector and
application performance remain unmeasured; directed libm semantics remain
outside this API's deterministic-nearest contract.

The log10f phase passes full default GCC14.2/GCC16.2 gates, 176 unit tests
on GCC14/GCC16/Clang and ten focused ASan/UBSan tests. Independent numerical
and blind reviews with follow-up are resolved. All 24 implementation/state
plants, 32 loader fixtures, four oracle faults, reference/raw/output hash
corruptions, omitted entry and actual former directory typo are detected.
The ordinary pinned-oracle gate now checks the source-linked numerical budget
and requested fresh metadata/population/path; staged coefficient/evaluation
drift and stale fresh metadata are rejected. Host pinned checks execute;
optional nested oracles/budget are explicitly skipped in the GCC16 image.
All 50 function result sets and the unchanged legacy aggregate agree on six
emulated targets; raw default/portable probes pass at -O0/-O2. The new raw
hash covers 778 nearest records, with 21,784 all-mode/incoming-state calls.
Four stratified fresh samples each supply 120 distinct inverse-midpoint
candidates and pass accuracy checks; committed data stays byte-identical.
These results do not claim all-input correct rounding, directed numerical
accuracy, physical-target coverage or an overall performance win.

The logf phase passes full default GCC14.2/GCC16.2 gates and 166 unit tests
on GCC14/GCC16/Clang, plus nine focused ASan/UBSan tests,
pinned reference regeneration, a 309,591-row direct-reference sample, and
independent review with follow-up. All 23 implementation/state plants, 28
loader fixtures, two parse-valid reference corruptions, four oracle faults,
raw/output hash corruptions, omitted-entry detection and the actual former
corpus-directory typo are detected on the host. Optional nested oracles are
explicitly skipped inside the GCC16 image and execute on the host. Fresh population and directory
selection are verified independently of row count. Six-target QEMU probes agree
on all 49 result sets; raw probes pass default/portable at -O0/-O2. The 668-row
raw logf hash covers nearest result/normalized flags; 18,704 calls separately
assert all-mode/incoming state. Native near-one scanning covers 524,288 calls.
These runs do not establish correctly rounded results for every input or
numerical accuracy in directed modes; physical-target and broader compatibility
coverage remain pending.

The expf phase passes full default GCC14.2/GCC16.2 gates and 157 unit tests
on GCC14/GCC16/Clang, plus nine focused ASan/UBSan tests. All 23 arithmetic/
state plants, 28 loader fixtures, two parse-valid reference corruptions, four
oracle faults and output/raw hash mutations are detected. Host pinned oracles
run; unavailable optional nested oracles are explicitly skipped in the GCC16
image. All 48 function result hashes agree on six emulated targets, with the
49-record raw expf probe passing default/portable -O0/-O2. Native all-mode
subnormal scanning covers 8,721,812 public/cast calls; deletion-only UF-force
sensitivity remains unverified and is not represented as public coverage.

The exp2f phase passes full default GCC14.2/GCC16.2 gates and 148 unit tests
on GCC14/GCC16/Clang, plus nine focused ASan/UBSan tests. All 23 arithmetic/
state plants, 28 loader fixtures, two parse-valid reference corruptions, four
oracle plants and output/raw hash mutations are detected. Optional nested
oracles are explicitly skipped inside the GCC16 image and executed on the host.
All 47 function hashes and the old aggregate agree on six emulated targets;
the 320-record raw exp2f probe also agrees at -O0/-O2, default/portable. A native
all-mode subnormal scan covers 6,815,648 public/cast calls; no force-only deletion
witness exists, so that narrow mutation claim remains explicitly unverified.

The wide-trig reduction phase passes full default `make test` gates on
GCC14.2 and GCC16.2, all 139 unit tests on GCC14/GCC16/Clang, and 14 focused
ASan/UBSan tests. All 34 implementation/branch/state plants, 66 loader fixtures,
three oracle mutations, three hash corruptions and three omissions are detected.
Pinned regeneration and fresh-reference checks execute on the host; optional
nested-oracle checks are explicitly skipped inside the GCC16 build image.
Independent numerical and blind reviews are resolved, including follow-up
review of the final dispatch and benchmark environment control.

The new exact APIs have independent committed reference corpora, fresh samples,
raw-bit NaN/zero/infinity tests, all four rounding modes, errno/exception-state
checks, mutation checks and supplemental result hashes. Existing hashes remain
unchanged. Build/test validation and independent reviews accompany each commit.

Math-only QEMU checks now match all 52 committed function hashes on i686,
AArch64, s390x, PowerPC64, PowerPC32 and SPARC64 Linux, with both default and
forced-portable square root. Raw binary32 special-value/exception probes also
pass on those emulated targets at both `-O0` and `-O2`. These are probe executions, not physical-host or full GoogleTest
results. Other targets and broader exception/state validation remain pending.

The suite's automatic cross-target scripts still compare only the legacy
aggregate. Integrating supplemental entries and raw probes into that pipeline
remains separate work while consumer/suite edits are deferred.

Scalar call benchmarks compare against host libm on identical input ranges.
Extrema are approximately tied on the measured host. Base logarithms have
mixed performance as described above. Remainder is faster in
some float/subnormal cases and slower in some double ranges; there is no claim
of an overall libm performance win. Compiler-inlined, shared-library, vector,
and application workloads still need separate measurements.

Standard C types and semantics also need an explicit compatibility boundary:
long double, complex arithmetic, full fenv/errno compatibility and FMA are not
covered by the current library. Existing `gmath_rint` deliberately uses ties to
even regardless of the host rounding mode.
