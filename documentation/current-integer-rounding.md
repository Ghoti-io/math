# Current-mode integer conversion

`gmath_lrint`, `gmath_lrintf`, `gmath_llrint` and `gmath_llrintf` round exactly
using the current standard direction: nearest/ties-even, downward, upward or
toward zero. Native long is signed32 or signed64; long long is signed64. Valid
integral inputs add no flags. Valid nonintegral inputs add inexact only, including
subnormals and fractions rounded to zero. Every NaN, infinity or rounded result
outside the destination range returns destination MIN and adds invalid only.
Range checks precede new inexact. errno, current mode and incoming standard C
flags are preserved. Valid MIN and the invalid sentinel require a clean/check
of FE_INVALID to distinguish; incoming invalid cannot identify a new one.

These contracts follow the current-direction and valid-inexact requirements in
[C11 draft N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf),
sections 7.12.9.5 and F.10.6.5, with an explicit project choice of MIN for invalid
results and errno preservation. Full libm errno, long-double, unsupported modes
and arbitrary hardware override semantics remain outside scope. Existing
mode-independent rint and ties-away lround APIs are unchanged.

## Integer proof and mode observation

The new module decodes raw binary32/64 fields without widening signaling inputs.
Absolute encodings at or above 2^63 are invalid, except exact negative 2^63 for a
signed64 destination. Every admitted nonzero normal exponent is at most 62. Below
one, direction and sign select zero or signed one; nearest chooses zero at exactly
one half. Larger inputs extract unsigned magnitude and discarded fraction; nearest
uses the retained integer parity. Right shifts lie in 1..p and left shifts are at
most 62-p, where p is 52 or 23. Fractional rounding cannot exceed 2^p; integral
magnitudes stay below 2^63. Unsigned comparison against MAX+negative is safe.
MIN is formed as `-(int64_t)maximum-1`, avoiding negation or narrowing of 2^63.

Only after successful rounded range classification does a fractional input
force inexact with volatile 1+2^-54. The exact sum is unrepresentable but normal
in every standard mode, so it adds IX without UF/OF. Invalid cases never reach
that operation. Integer decoding and control reads otherwise perform no floating
arithmetic. Source/state fault controls include deletion of only that IX force;
actual C17/C++ force-only deletion witnesses retain zero result bits but lose
required IX at minimum-subnormal inputs in both formats. Earlier expf/exp2f/atanf/
cbrtf force-only witness gaps are unchanged.

The existing nearby mode reader is reused byte-for-byte. It observes native GNU
arithmetic controls on the six emulated hardware targets; explicit/other-port
standard queries can require platform fenv/libm. Coherent nontrapping standard C
controls are assumed. x86 numerical mode is MXCSR; the new test snapshot also
checks the x87 control word, including precision/masks. PPC checks binary controls,
not extended DFP; SPARC FSR stores may clear trap-type FTT status, which is not a
standard C exception flag or promised preservation field. Windows/RISC-V runtime
and numerical soft-float execution remain unrun.

## Independent references and checks

Exact rational targets use independently specified floor, ceiling, truncation
and nearest parity, then signed32/64 range tests. Pinned MPFR rint constructs the
input independently through IEEE struct decoding and runs in each actual mode;
it does not use the old ties-away rint_round. Raw rows contain both destination
widths and all modes. Generic hash subsets use nearest results valid in signed32,
so outputs widen exactly to Double on every supported long ABI. Invalid classes
come from explicit contracts, not host errno or sentinel choices.

The new standalone probe identifies its compiled native long width. Controllers
validate that identity before selecting signed32/64 manifests, rather than infer
an emulated target ABI from Python's host type. Every raw row checks both APIs
for its input format in all modes/two errno seeds; selected cases request all 32
incoming-flag subsets. Hardware requests can merge; actual incoming flags,
errno, mode and control snapshots are checked inline. Result/flag-class ordered
hashes are accounting, not an encoding of every hardware-state observation.

Complete-file SHA gates and LF attributes protect seven payloads. Complete fresh
population/widening reconstruction checks seed/count/path even when fallback
row counts match. The publisher stages first and rolls back ordinary replacement
failures, preserving permissions/cleanup; it is not crash-atomic. Interrupted
mixed generations fail the complete checksum gates. Recording-engine dispatch
controls test accounting, not numerical oracle correctness. Optional absent
engines skip explicitly; required mode fails, while mandatory bytes and recording
controls still run.

Run the normal `make test` with a private dependency prefix. Focused gates include
`check-currentint`, `check-currentint-link`, `check-planted-currentint`,
`check-currentint-controls`, `check-currentint-oracle`,
`check-currentint-oracle-controls` and `check-currentint-bench-controls`.
A separate build with `-DGMATH_NEARBY_FENV_QUERY` selects the platform query.
Native no-libm and companion platform clients actually call all four APIs.

## Final validation and limits

Confirmed sequential full GCC14.2 and GCC16.2 `make test` commands return zero,
with actual child statuses persisted. Each main run invokes 242 tests in 34
binaries: 241 pass and the native32-long unit test skips explicitly on LP64.
Clang has the same counts unit-only. Five focused ASan/UBSan tests invoke four
passes and the same skip. Final explicit-query targeted gates and units pass.
The old nearby reader and every prior runtime module remain byte-identical.
All 80 old result sets and legacy `f5fa269eb60ee34f` over 292711 rows remain;
four additions bring the generic total to 84. New lrint/llrint hash
`472e8d420d2337c2` covers 17739 common-valid rows each; Float forms
`1d43cc9f8126755f` cover 4861 each. This portable subset does not replace the
width-specific invalid/range raw checks.

Committed raw populations have 34184 Double and 7042 Float rows. Each profile
checks 1145696 actual API/state calls, with nearest digests sampled from those
calls, not additional calls. The width-specific result/flag-class and ordered
hashes are listed in `tests/corpus/currentint-special.hash`. Actual hardware
state is asserted separately; requests can merge. The corpus covers every
exponent binade, half-cell parity/carry neighbors, signed32 range fractions,
signed64 exact neighbors, both signs and signaling payload classes, not exhaustive
raw/environment space.

Six emulated targets match all 84 generic sets default/portable and 24 raw
O0/O2 native/explicit-query profiles. Twelve native clients actually link/run
without libm. Native32 equality, narrowing and premature-IX defects detect on
both i686 and PowerPC32; the premature-IX defect fails Double while Float remains
passing, since representable Float destination32 boundaries are integral.
Signed64-long default runners skip equivalent/inapplicable native32 variants
explicitly. Real host-Python controllers successfully validate both compiled
native32 probes; restoring the former host64-width assumption fails on each.
The i686 O0 raw call body has no `fldl`/`flds` argument loads. These are emulated
probes, not physical-host/full cross-target GoogleTest coverage.

Three retained fresh 34184/7042-row populations pass complete seed/count/target/
widening/path, actual C++ selection and all 84-set overlays on both native
compilers. State-call totals are 1139248,1143216 and1138752. A larger 72184/45041-row
population passes both native contexts with 3335824 calls. Its long64 nearest
hashes are `cdb440b913a52625` and `ccb6629cf4ba5e91`; ordered hashes
`b5517f436bd55325` and `802ec724a624a5b5`. No larger cross-target run is claimed.

Eighteen shared source/state faults and four format/wide-range defects detect in
C17/C++, with native/explicit-query positive controls. Actual SSE and x87
nonround-control faults detect where supported, with honest elsewhere skips.
There are 70 loader/value negatives, seven payload checksum corruptions, nine
observed output/process faults, twelve actual generic hash/count/omission
controls, four numerical/version oracle faults and two ignored-request faults.
Publisher controls include two positives and fourteen replacement rollback
cases; no crash-atomicity claim. Recording wrapper dispatch/omission/absence
controls execute even when optional numerical engines skip. Host pinned
regeneration is byte-identical; nested GCC16 numerical engines skip explicitly.
Independent mathematical and blind source reviews/follow-ups resolve their
findings; final evidence reconciliation is recorded separately.

The first full GCC14 invocation was deliberately interrupted for review fixes,
with actual return -2; it is not passing. The subsequent complete frozen run
and complete GCC16 run pass. Earlier targeted failures found a wrong executable
name, an equivalent LP64 comparison mutant and unchecked unused signed32 columns;
these were corrected before confirmed full runs, without treating harness
failures as numerical defect detections or weakening existing gates.

Valgrind 3.24 invokes all five focused tests and exits 1: four fenv assertion
failures and one native32-only skip. It reports zero memory errors/leaks, but
both corpus probes stop at the first fractional input, so Memcheck coverage is
partial. A plain volatile 1+2^-54 and 0/0 program without gmath returns identical
native/instrumented bits while native IX/IV become no flags under instrumentation.
This directly establishes missing flags for those operations; attribution of
every harness failure remains inference. No assertions were weakened and this
is not a passing Valgrind suite. Earlier failed partial scopes and unrelated
force-only IX witness gaps remain unchanged.

Windows/LLP64 runtime, numerical soft-float, physical cross-target hosts,
exhaustive input/environment space and application workload timing are unrun.
Consumer migration and edits to other libraries remain deferred.

## Predeclared paired timing

Two final runs per compiler/runtime context retain all 1408 case records: four
APIs, eleven ranges, four modes and two entry states. Eight paired warmups
precede 401 alternating pairs of 4096 identical inputs. Integer timestamps,
untimed per-input own flags/errno/mode and valid host-result guards are used;
each timed checksum equals its untimed checked checksum. Invalid own MIN is
checked, but host invalid sentinels/errno/extra flags are not compared as a
parity promise. Untimed host nearby rounding supplies a rounded-range benchmark
classifier, not an independent numerical oracle. Reduced-workload checksum,
disabled-checksum and finite-range-classifier counterfactuals calibrate guards;
those runs are accounting evidence, not final performance measurements.

The review expanded missing wide/overflow/boundary workloads before any final
measurement. No selected timing retry replaces a final result. Both contexts
use one fixed logical CPU affinity, without CPU isolation or governor control.
Absolute times include call/switch/loop/checksum/timestamp work and amortized
first exceptions. Compiler/runtime differences must not be attributed solely
to the compiler. No overall, application or cross-platform win is claimed.

Ordinary own/host paired medians are 7.868–10.530 for lrint, 9.335–13.865 for
llrint, 8.822–11.965 for lrintf and 7.819–10.731 for llrintf in GCC14. GCC16 spans
6.901–9.129,9.164–12.314,7.805–10.805 and7.081–9.765 respectively. The other
ranges also trail on this measured host. This is an exact portable coverage
baseline with a substantial performance gap, motivating a separately proved
native-conversion investigation; it does not meet the overall performance goal.

[Machine-readable timing records](current-integer-timings.json) preserve every
mode/state/run case, target long width and compiler/build identities. Private
reproduction records additionally bind actual compiler/library flags and source,
archive, binary and linked-runtime identities. `make bench-currentint` reproduces
the public harness; the built program accepts `--validate-only` for untimed
guards. Aggregated tables below show minimum-to-maximum envelopes across both
runs, four modes and two entry states for each API/range. Each ratio column is
an envelope of the original paired quantile, not a mixed-workload quantile or a
ratio of separately aggregated absolute medians.

### GCC14 compiler/runtime context

| API | Range | Own ns/call | Host ns/call | Paired p10 | Paired median | Paired p90 |
|---|---|---:|---:|---:|---:|---:|
| lrint | normal | 6.103–8.554 | 0.756–0.819 | 7.424–10.388 | 7.868–10.530 | 8.019–11.334 |
| lrint | half-ties | 6.917–7.812 | 0.738–0.868 | 8.078–9.018 | 8.473–9.195 | 8.702–90.670 |
| lrint | subnormal | 5.247–6.217 | 0.792–0.867 | 5.785–7.216 | 6.192–7.453 | 6.362–7.888 |
| lrint | large-integral | 5.665–8.304 | 0.775–1.553 | 4.387–7.159 | 5.285–7.324 | 6.878–7.504 |
| lrint | zero | 1.772–2.208 | 0.774–0.966 | 1.889–2.283 | 2.263–2.289 | 2.292–2.343 |
| lrint | infinity | 1.858–2.156 | 0.776–0.872 | 2.259–2.392 | 2.394–2.533 | 2.400–2.726 |
| lrint | qNaN | 1.897–2.150 | 0.792–0.870 | 2.327–2.391 | 2.394–2.527 | 2.400–2.566 |
| lrint | sNaN | 1.899–2.250 | 0.792–0.937 | 2.316–2.392 | 2.394–2.422 | 2.400–2.604 |
| lrint | wide-integral | 4.760–5.916 | 0.774–0.964 | 4.075–6.194 | 6.133–6.290 | 6.220–6.478 |
| lrint | finite-overflow | 1.936–2.091 | 0.793–0.853 | 2.349–2.411 | 2.411–2.528 | 2.430–2.624 |
| lrint | boundary32 | 5.916–7.939 | 0.792–0.829 | 7.101–9.485 | 7.279–9.779 | 7.396–9.975 |
| llrint | normal | 6.290–8.547 | 0.601–0.702 | 8.849–12.452 | 9.335–13.865 | 9.681–14.418 |
| llrint | half-ties | 6.780–7.402 | 0.613–0.689 | 9.729–11.327 | 10.076–11.801 | 10.429–12.186 |
| llrint | subnormal | 4.897–6.205 | 0.583–0.719 | 5.565–9.711 | 8.022–9.885 | 8.213–10.073 |
| llrint | large-integral | 5.774–6.108 | 0.602–0.674 | 6.950–8.851 | 8.867–9.713 | 9.903–10.138 |
| llrint | zero | 1.529–1.638 | 0.601–0.702 | 2.201–2.324 | 2.327–2.607 | 2.608–2.649 |
| llrint | infinity | 1.641–1.754 | 0.614–0.704 | 2.484–2.789 | 2.492–2.793 | 2.496–2.858 |
| llrint | qNaN | 1.541–2.063 | 0.587–0.728 | 2.432–2.789 | 2.492–2.794 | 2.791–2.991 |
| llrint | sNaN | 1.606–1.796 | 0.612–0.720 | 2.437–2.789 | 2.489–2.795 | 2.789–2.827 |
| llrint | wide-integral | 6.119–6.498 | 0.600–0.658 | 9.029–9.647 | 9.509–10.642 | 10.625–10.920 |
| llrint | finite-overflow | 1.514–2.137 | 0.583–0.750 | 2.539–2.763 | 2.545–2.855 | 2.846–3.090 |
| llrint | boundary32 | 5.961–7.397 | 0.599–0.689 | 8.676–10.815 | 8.751–12.261 | 8.846–12.640 |
| lrintf | normal | 6.274–8.450 | 0.681–0.728 | 8.751–11.819 | 8.822–11.965 | 8.922–12.502 |
| lrintf | half-ties | 6.787–7.546 | 0.680–0.728 | 8.643–10.356 | 9.863–10.485 | 10.024–10.651 |
| lrintf | subnormal | 5.486–6.033 | 0.681–0.715 | 6.443–8.506 | 7.964–8.653 | 8.100–8.948 |
| lrintf | large-integral | 6.052–6.439 | 0.659–0.697 | 8.576–9.041 | 9.135–9.211 | 9.297–10.196 |
| lrintf | zero | 1.475–1.794 | 0.599–0.729 | 2.378–2.457 | 2.460–2.462 | 2.465–2.505 |
| lrintf | infinity | 1.578–1.834 | 0.627–0.729 | 2.452–2.514 | 2.517–2.518 | 2.521–2.576 |
| lrintf | qNaN | 1.712–1.797 | 0.680–0.713 | 2.452–2.513 | 2.517–2.521 | 2.522–2.644 |
| lrintf | sNaN | 1.679–1.797 | 0.667–0.714 | 2.463–2.514 | 2.517–2.519 | 2.522–2.554 |
| lrintf | wide-integral | 5.986–6.448 | 0.652–0.711 | 8.821–9.049 | 9.099–9.250 | 9.221–9.427 |
| lrintf | finite-overflow | 1.715–2.021 | 0.680–0.731 | 2.468–2.557 | 2.515–2.832 | 2.521–3.056 |
| lrintf | boundary32 | 5.663–6.344 | 0.612–0.696 | 8.783–9.038 | 9.088–9.279 | 9.259–9.782 |
| llrintf | normal | 6.364–8.779 | 0.760–0.831 | 7.650–10.576 | 7.819–10.731 | 8.075–11.223 |
| llrintf | half-ties | 6.824–7.355 | 0.794–0.832 | 7.959–8.665 | 8.249–8.880 | 8.530–9.250 |
| llrintf | subnormal | 5.708–6.271 | 0.794–0.832 | 6.909–7.426 | 7.051–7.634 | 7.179–8.003 |
| llrintf | large-integral | 5.989–6.612 | 0.776–0.833 | 7.428–7.646 | 7.662–8.022 | 7.844–8.402 |
| llrintf | zero | 1.748–1.914 | 0.776–0.850 | 2.212–2.253 | 2.252–2.282 | 2.256–2.288 |
| llrintf | infinity | 1.855–2.030 | 0.775–0.848 | 2.341–2.388 | 2.391–2.394 | 2.396–2.533 |
| llrintf | qNaN | 1.705–2.036 | 0.700–0.850 | 2.349–2.387 | 2.391–2.395 | 2.396–2.540 |
| llrintf | sNaN | 1.856–2.031 | 0.776–0.831 | 2.327–2.390 | 2.391–2.525 | 2.396–2.537 |
| llrintf | wide-integral | 5.974–6.667 | 0.777–0.846 | 7.455–7.621 | 7.652–7.996 | 7.797–8.225 |
| llrintf | finite-overflow | 1.912–2.056 | 0.794–0.850 | 2.293–2.400 | 2.400–2.523 | 2.409–2.625 |
| llrintf | boundary32 | 5.971–6.403 | 0.761–0.810 | 7.513–7.960 | 7.679–8.235 | 7.963–8.515 |

### GCC16 compiler/runtime context

| API | Range | Own ns/call | Host ns/call | Paired p10 | Paired median | Paired p90 |
|---|---|---:|---:|---:|---:|---:|
| lrint | normal | 6.224–9.063 | 0.885–0.990 | 6.565–8.953 | 6.901–9.129 | 7.047–9.532 |
| lrint | half-ties | 6.764–7.632 | 0.885–0.944 | 7.220–7.864 | 7.471–8.087 | 7.591–8.271 |
| lrint | subnormal | 4.873–5.847 | 0.867–0.945 | 5.434–6.202 | 5.532–6.325 | 5.635–6.608 |
| lrint | large-integral | 5.640–5.918 | 0.884–0.924 | 6.155–6.324 | 6.354–6.467 | 6.460–6.717 |
| lrint | zero | 1.718–2.258 | 0.865–1.289 | 1.616–1.984 | 1.916–1.988 | 1.991–2.045 |
| lrint | infinity | 1.760–1.881 | 0.866–0.944 | 1.976–2.028 | 2.030–2.033 | 2.036–2.060 |
| lrint | qNaN | 1.797–2.213 | 0.884–1.069 | 1.732–2.029 | 2.029–2.033 | 2.035–2.538 |
| lrint | sNaN | 1.755–1.966 | 0.864–0.968 | 1.876–2.028 | 1.989–2.033 | 2.034–2.161 |
| lrint | wide-integral | 4.938–5.251 | 0.867–0.924 | 5.379–5.646 | 5.560–5.733 | 5.657–5.845 |
| lrint | finite-overflow | 1.836–1.964 | 0.883–0.945 | 2.023–2.074 | 2.077–2.080 | 2.082–2.273 |
| lrint | boundary32 | 5.066–7.551 | 0.784–0.969 | 5.848–8.180 | 6.050–8.493 | 6.207–69.054 |
| llrint | normal | 6.277–8.501 | 0.679–0.714 | 8.754–11.798 | 9.164–12.314 | 9.268–12.964 |
| llrint | half-ties | 6.131–7.599 | 0.581–0.734 | 9.313–10.275 | 9.735–10.472 | 9.856–131.981 |
| llrint | subnormal | 5.287–6.192 | 0.665–0.698 | 7.401–8.618 | 7.928–9.094 | 8.079–9.298 |
| llrint | large-integral | 5.500–5.741 | 0.652–0.681 | 8.013–8.289 | 8.293–8.460 | 8.435–8.681 |
| llrint | zero | 1.502–1.640 | 0.650–0.711 | 2.238–2.305 | 2.307–2.309 | 2.312–2.357 |
| llrint | infinity | 1.550–1.729 | 0.651–0.726 | 2.249–2.377 | 2.378–2.381 | 2.384–2.454 |
| llrint | qNaN | 1.549–1.692 | 0.651–0.711 | 2.314–2.377 | 2.380–2.384 | 2.384–2.430 |
| llrint | sNaN | 1.584–1.692 | 0.666–0.711 | 2.258–2.376 | 2.379–2.381 | 2.384–2.441 |
| llrint | wide-integral | 5.943–6.289 | 0.651–0.685 | 8.544–9.015 | 9.008–9.146 | 9.223–9.417 |
| llrint | finite-overflow | 1.614–1.721 | 0.665–0.709 | 2.366–2.422 | 2.424–2.427 | 2.429–2.464 |
| llrint | boundary32 | 5.644–7.530 | 0.665–0.714 | 8.234–10.683 | 8.408–11.015 | 8.585–11.500 |
| lrintf | normal | 6.166–8.604 | 0.778–0.811 | 7.646–10.594 | 7.805–10.805 | 7.957–11.041 |
| lrintf | half-ties | 6.649–7.321 | 0.730–0.852 | 8.183–8.954 | 8.459–9.085 | 8.597–72.377 |
| lrintf | subnormal | 4.836–6.060 | 0.686–0.871 | 6.726–7.367 | 6.901–7.513 | 6.997–175.631 |
| lrintf | large-integral | 6.002–6.451 | 0.760–0.830 | 7.574–7.771 | 7.775–7.940 | 7.928–8.147 |
| lrintf | zero | 1.608–1.759 | 0.760–0.831 | 2.078–2.113 | 2.115–2.117 | 2.119–2.153 |
| lrintf | infinity | 1.655–1.806 | 0.760–0.830 | 2.135–2.173 | 2.176–2.178 | 2.180–2.201 |
| lrintf | qNaN | 1.670–1.848 | 0.771–0.848 | 2.126–2.173 | 2.176–2.179 | 2.180–2.209 |
| lrintf | sNaN | 1.657–3.901 | 0.761–1.830 | 1.857–2.173 | 2.054–2.181 | 2.180–2.503 |
| lrintf | wide-integral | 6.058–10.283 | 0.760–2.061 | 4.771–7.857 | 4.965–7.980 | 5.245–8.138 |
| lrintf | finite-overflow | 1.677–1.910 | 0.746–0.848 | 2.245–2.246 | 2.249–2.252 | 2.253–2.261 |
| lrintf | boundary32 | 6.006–6.262 | 0.760–0.794 | 7.651–7.883 | 7.782–7.987 | 7.999–8.188 |
| llrintf | normal | 6.547–9.145 | 0.904–0.947 | 6.936–9.639 | 7.081–9.765 | 7.196–10.030 |
| llrintf | half-ties | 7.006–7.564 | 0.905–0.946 | 7.512–8.113 | 7.652–8.244 | 7.744–8.392 |
| llrintf | subnormal | 5.117–6.010 | 0.813–0.969 | 5.943–6.440 | 6.045–6.536 | 6.309–61.619 |
| llrintf | large-integral | 5.683–7.044 | 0.782–1.042 | 5.976–6.764 | 6.787–7.176 | 7.213–94.090 |
| llrintf | zero | 1.757–1.991 | 0.885–1.009 | 1.771–1.990 | 1.984–1.996 | 1.997–2.040 |
| llrintf | infinity | 1.803–1.971 | 0.886–0.969 | 1.972–2.031 | 2.034–2.040 | 2.039–2.080 |
| llrintf | qNaN | 1.813–1.930 | 0.886–0.948 | 1.971–2.031 | 2.035–2.036 | 2.039–2.082 |
| llrintf | sNaN | 1.763–1.976 | 0.866–0.971 | 1.938–2.031 | 2.034–2.037 | 2.038–2.092 |
| llrintf | wide-integral | 5.881–6.538 | 0.868–0.958 | 5.511–6.725 | 6.753–6.857 | 6.820–7.190 |
| llrintf | finite-overflow | 1.868–1.958 | 0.905–0.948 | 2.034–2.062 | 2.065–2.069 | 2.069–2.692 |
| llrintf | boundary32 | 6.004–6.584 | 0.886–0.946 | 5.371–6.717 | 6.754–6.840 | 6.874–7.404 |
