# Initial IEEE remainder division

The initial normalized division is replaced by comparison and conditional
subtraction. This changes no API, result or exception contract. Every other
runtime module/table and every reference payload remains byte-identical.
The operation is derived from integer bounds and own-project code, without
reading or copying another math implementation source. Standard arithmetic is
not claimed novel.

## Exact equivalence

Let H=2^p, with p=52 or 23. Both finite nonzero normalized significands satisfy
H<=mx,my<=2H-1, including normalized subnormals. Consequently integer mx/my is
zero or one, exactly `(mx>=my)`. Subtract my only in the latter case; it cannot
underflow. The replacement retains `mx=q*my+r`, with `0<=r<my`, and feeds
identical q/r into the unchanged chunk, early-zero, nearest/even, sign and
packing code. It adds no floating operations or shifts. Exceptional and
negative-gap paths remain unchanged. Integer comparison cannot change the
rounding mode, errno or floating exception flags.

Equality matters even though later reduction can repair some incorrect initial
states: changing >= to > at equal magnitudes and gap zero eventually obtains
the correct quotient but flips the exact-zero sign. Targeted signed-zero tests
and an actual source plant detect that defect. The old / and % were combined
by both measured native compilers; emitted divide sites fall from two to one,
not from three to one. Wide Double inputs still spend most time in the loop.

## Validation and scope

Final full GCC14.2/GCC16.2 commands return zero with actual child-status records:
233 main tests in 32 binaries each. Clang passes 233/32 unit-only, and nine focused
ASan/UBSan tests pass. GCC14 full began before review changes to test/benchmark
plumbing; current affected checks were rerun, and the later GCC16 full includes
them. A final strengthening of benchmark fault controls was rerun separately
on both compilers. Runtime source remained frozen throughout the full runs.

All 78 numerical sets and legacy `f5fa269eb60ee34f` over 292711 results remain
unchanged. Mandatory complete-file SHA256 gates and independent reference checks
still run;
there is no new numerical oracle or accuracy target. The four APIs retain
exact mode-independent remainder bits, signed abs(quotient)%128, signed zero,
canonical NaNs, invalid-only special/domain rules and preserved caller state.
Valid subnormal outputs add no flags. Full errno/long-double parity is unpromised.

A baseline builder obtains the actual prior module from own revision
`a54cfbacafa735c0bc7fd1a56af869b8877fa501`, checks the unchanged helper, compiles
with identical library arguments and renames only its four public symbols.
Metadata binds declared revision, actual object bytes, compiler-driver
invocation and library argument vector. This identifies caller-declared
provenance; it does not authenticate arbitrary externally supplied source.
Actual retained source/helper hashes match Git. Both current/prior public
functions are linked into the same probe/benchmark process.

Each raw profile checks 393972 nearest and 807504 selected corpus observations,
with two API calls per observation when hooks are enabled. Unchanged raw hashes
are `de2cafdcc5da3465`/`d982af8aeb4c9bfb`; ordered selected hashes are
`84af9b980627e8f5`/`9f841414af40b535`. Actual flags, errno and mode are asserted
inline; requested flag subsets can merge. The shared focused matrix adds 46
cases, 3312 calls per format (6624 logical observations, each paired), across
all four modes, signs and three API paths. These include normalized less/equal/
greater relations, normal/subnormal operands and negative/zero/chunk/large gaps.
Thus each complete paired raw profile makes 1208100 logical observations and
2416200 physical public API calls; this is not exhaustive pair/state coverage.

Six emulated targets agree on all 78 numeric sets default/portable. Twenty-four
raw O0/O2 default/forced-loop profiles compare the four affected APIs against
actual prior functions. Final i686 O0 caller has no fldl/flds argument loads. These are emulated probes, not physical
hosts/full cross-target GoogleTest. Three retained fresh corpora and the larger
149316/80008-pair independent corpus pass actual-prior value/state comparisons
on both native compilers. Larger probes add the focused matrix to 2023020 corpus
observations (4059288 physical calls total). New default host pinned/fresh checks
also pass; optional nested GCC16 numerical engines skip explicitly. No larger
cross-target run or exhaustive inputs/environments/Windows/application timing
is claimed.

Twenty-six shared source/state plants, including four initial-state defects,
detect in C17/C++ and both formats on both compilers default/forced-loop.
Two format-local defects leave the other format passing; the loop-only defect
is tested on its actual branch. The public driver has a valid recording-process
control and 11 identity/hash/count/path/process faults; accounting evidence is
separate from numerical references. Native optional C17 probe/benchmark controls
check actual prior
source defects in result bits, NaN payload, quotient bit3, partial invalid loss,
NULL-only errno and Float-only output. Benchmark failures require their intended
comparison layer: quotient bit3 preserves the host-guaranteed low three bits
and the sign of retained nonzero fragments, leaving original zeros unchanged
(q==8 may become zero). Partial invalid loss removes only sNaN invalid while other domain calls
still raise it, so mixed batch flags alone could hide the defect. Individually
seeded per-input checks detect it. Three metadata and two actual-invocation
identity faults reject. Actual Make controls verify selected older objects force
relinking, correct identity/path and rejection of wrong revision/flags/compiler.

Independent mathematical and blind reviews are resolved, with no deferred
implementation findings. The false missing-tool-default finding was checked
against existing NM/OBJCOPY defaults and successful default builds. Initial
control-only compile/calibration failures were corrected before final passing
runs; none was counted as defect detection. Cross-image setup lacked Python,
so host orchestration invoked the compiler image by immutable image ID without
installing anything.

Valgrind was not rerun for this optimization. The previous failed eight-test
scope remains five passing/three fenv failures with partial memory coverage;
no passing or expanded Memcheck claim is made. The independent missing-invalid
instrumentation reproducer and earlier UF/IX limitation remain applicable
external evidence. No assertions were weakened. Earlier expf/exp2f/atanf/cbrtf
force-only IX deletion witness gaps remain unverified and unchanged.

## Reproduce the actual prior comparison

Default gates require no prior Git object. Optional comparisons require that
revision in the math checkout and nm/objcopy-compatible tools. With the ordinary
Linux release build directory (adapt paths if using another BUILD_DIR):

```sh
make build-ieee-remainder-baseline
make IEEE_REMAINDER_REFERENCE_OBJECT=build/linux/release/ieee-remainder-baseline/prior.o check-ieee-remainder-prior check-ieee-remainder-prior-controls
make IEEE_REMAINDER_REFERENCE_OBJECT=build/linux/release/ieee-remainder-baseline/prior.o bench-ieee-remainder-prior
make bench-ieee-remainder
```

`tools/check-ieee-remainder-prior.py --calibrate` runs accounting controls.
The public benchmark's `--validate-only` option runs input/value guards without
timings. Prior mode additionally checks every benchmark input separately through
all three API paths and clean/UF-IX+errno states before timing. The actual-prior
NULL path calls prior remquo with NULL; ordinary host comparison calls host
remainder, never standard remquo with NULL. Selected NM/OBJCOPY commands are
passed consistently to the builder and native controls. Forced optional-tool
relinking prevents stale object/metadata selections from silently persisting.

## Paired timing evidence

Two predeclared runs per compiler/runtime context and comparison produce 768
case records: eight ranges, six paths and two entry states, with 401 alternating
pairs of 4096 identical inputs after eight paired warmups. Integer timestamps
precede floating timing arithmetic. Untimed actual-prior checks verify exact
bits including NaNs, all seven quotient bits and individual state/errno/mode
for 393216 logical observations per run, before batch timing guards. Native
current/prior comparisons and host comparisons are separate measurements.

Ordinary actual-prior paired medians are 0.873–0.937 Double and 0.854–0.918 Float
across the three paths: measured call times fall about 6–15%. Float wide inputs
also improve, but Double wide medians are 1.002–1.004 (a measured 0.2–0.4% cost).
Some special ranges regress: GCC14 NaN/domain remainder reaches 1.164, with
absolute medians 3.760 ns versus 3.133 ns in that case. GCC16 special paired medians
reach 1.130. These observations are retained tradeoffs, not dismissed as noise;
there is no general nonregression claim. Current host ratios remain below one
for ordinary inputs but Double wide remquo still costs 4.103–4.181 times host.

Tables report envelopes over two runs and two entry states (four observations
per cell), not confidence bounds. Absolute columns are amortized median ns/call;
ratio columns are paired p10/median/p90 quantiles. Ratio of absolute medians need
not equal the median of per-pair ratios. Fixed logical affinity does not establish
CPU isolation or controlled governor. Call/loop/checksum/timestamp work and
amortized first exceptions are included. Compiler/library arguments, source,
archive, binary, actual prior object and runtime-libm hashes are retained with
the measurement evidence. There is no net workload/application/platform win
claim, and other compiler/platform timing remains unrun.

### GCC14 / actual-prior

| API / range | Own ns/call | Reference ns/call | Ratio p10 | Ratio median | Ratio p90 |
| --- | ---: | ---: | ---: | ---: | ---: |
| remainder / normal | 9.867–10.998 | 10.974–12.567 | 0.856–0.880 | 0.873–0.904 | 0.896–0.943 |
| remquo / normal | 10.701–11.281 | 11.461–12.594 | 0.880–0.901 | 0.898–0.914 | 0.912–0.980 |
| remquo_null / normal | 10.348–11.002 | 11.859–12.482 | 0.857–0.866 | 0.873–0.881 | 0.891–0.899 |
| remainder / half-ties | 6.153–6.581 | 6.632–7.080 | 0.924–0.926 | 0.926–0.929 | 0.931–0.939 |
| remquo / half-ties | 6.303–6.858 | 6.793–7.226 | 0.926–0.927 | 0.928–0.930 | 0.930–1.040 |
| remquo_null / half-ties | 6.107–6.520 | 6.572–7.006 | 0.925–0.927 | 0.930 | 0.933–1.029 |
| remainder / quotient-wrap | 5.169–5.615 | 5.445–5.908 | 0.930–0.935 | 0.941–0.954 | 0.966–0.992 |
| remquo / quotient-wrap | 5.269–5.534 | 5.540–5.843 | 0.942–0.947 | 0.952–0.956 | 0.961–0.965 |
| remquo_null / quotient-wrap | 5.263–5.613 | 5.577–5.930 | 0.935–0.940 | 0.939–0.948 | 0.945–1.072 |
| remainder / subnormal | 18.009–19.164 | 19.409–20.585 | 0.904–0.917 | 0.923–0.931 | 0.945–0.949 |
| remquo / subnormal | 17.927–19.455 | 18.992–20.719 | 0.916–0.927 | 0.931–0.946 | 0.945–0.958 |
| remquo_null / subnormal | 18.139–19.267 | 19.795–20.992 | 0.898–0.904 | 0.915–0.920 | 0.928–0.943 |
| remainder / wide-gap | 678.098–678.229 | 676.002–676.241 | 1.002 | 1.003 | 1.004 |
| remquo / wide-gap | 677.771–677.844 | 675.838–675.932 | 1.002 | 1.003 | 1.004 |
| remquo_null / wide-gap | 677.972–683.421 | 675.625–681.509 | 0.988–1.002 | 1.003–1.004 | 1.005–1.019 |
| remainder / zero | 2.964–3.349 | 2.906–3.504 | 0.866–0.932 | 0.877–1.001 | 1.002–1.079 |
| remquo / zero | 2.755–3.016 | 2.676–2.875 | 0.950–1.026 | 1.029–1.030 | 1.083–1.086 |
| remquo_null / zero | 2.899–3.104 | 2.986–3.341 | 0.927–0.928 | 0.929–0.933 | 0.932–1.004 |
| remainder / infinite-divisor | 3.126–3.599 | 3.340–3.674 | 0.866–0.932 | 0.931–0.998 | 0.936–1.073 |
| remquo / infinite-divisor | 2.828–3.343 | 2.781–3.341 | 0.907–0.998 | 0.978–1.003 | 1.052–1.079 |
| remquo_null / infinite-divisor | 2.905–3.109 | 3.118–3.583 | 0.812–0.928 | 0.866–0.932 | 0.930–1.072 |
| remainder / NaN-domain | 3.422–3.760 | 3.133–3.733 | 0.887–1.160 | 0.930–1.164 | 0.967–1.401 |
| remquo / NaN-domain | 2.962–3.221 | 2.889–3.105 | 0.960–1.025 | 1.009–1.028 | 1.029–1.394 |
| remquo_null / NaN-domain | 3.118–3.580 | 3.070–3.474 | 0.899–1.015 | 0.953–1.019 | 1.077–1.151 |
| remainderf / normal | 11.086–11.640 | 12.645–13.658 | 0.837–0.856 | 0.854–0.877 | 0.871–0.896 |
| remquof / normal | 11.288–12.212 | 12.690–13.495 | 0.878–0.886 | 0.890–0.899 | 0.904–0.968 |
| remquof_null / normal | 11.245–12.351 | 12.767–13.718 | 0.866–0.884 | 0.881–0.903 | 0.894–0.962 |
| remainderf / half-ties | 6.428–7.005 | 6.933–7.574 | 0.923–0.927 | 0.925–0.929 | 0.927–0.940 |
| remquof / half-ties | 6.562–7.170 | 7.068–7.722 | 0.926–0.927 | 0.928–0.929 | 0.930–1.056 |
| remquof_null / half-ties | 6.357–6.938 | 6.870–7.507 | 0.923–0.926 | 0.925–0.927 | 0.927–0.966 |
| remainderf / quotient-wrap | 5.515–5.926 | 5.735–6.268 | 0.912–0.937 | 0.944–0.954 | 0.959–0.989 |
| remquof / quotient-wrap | 5.742–6.032 | 5.928–6.310 | 0.944 | 0.954–0.955 | 0.963–1.089 |
| remquof_null / quotient-wrap | 5.391–5.881 | 5.707–6.238 | 0.938–0.939 | 0.942–0.944 | 0.947–0.951 |
| remainderf / subnormal | 11.371–12.503 | 12.931–13.920 | 0.866–0.883 | 0.880–0.898 | 0.895–0.937 |
| remquof / subnormal | 11.978–12.945 | 12.921–13.985 | 0.906–0.916 | 0.920–0.927 | 0.936–0.994 |
| remquof_null / subnormal | 11.728–12.474 | 13.073–13.874 | 0.879–0.885 | 0.894–0.901 | 0.913–0.954 |
| remainderf / wide-gap | 27.039–28.562 | 28.893–30.815 | 0.902–0.913 | 0.927–0.938 | 0.953–0.964 |
| remquof / wide-gap | 27.715–28.897 | 29.356–30.818 | 0.926–0.930 | 0.938–0.942 | 0.949–0.953 |
| remquof_null / wide-gap | 26.898–28.190 | 28.665–30.338 | 0.913–0.918 | 0.930–0.938 | 0.946–0.957 |
| remainderf / zero | 2.988–3.526 | 3.041–3.863 | 0.865–0.931 | 0.927–0.936 | 0.936–1.078 |
| remquof / zero | 2.780–3.093 | 2.675–2.935 | 1.025 | 1.028–1.080 | 1.030–1.086 |
| remquof_null / zero | 2.898–3.103 | 2.986–3.142 | 0.927–0.928 | 0.932–1.037 | 1.002–1.042 |
| remainderf / infinite-divisor | 3.088–3.423 | 3.342–3.502 | 0.866–0.931 | 0.875–0.936 | 1.000–1.077 |
| remquof / infinite-divisor | 2.896–3.110 | 2.968–3.105 | 0.907–0.977 | 0.977–1.042 | 1.002–1.079 |
| remquof_null / infinite-divisor | 2.844–3.268 | 2.993–3.344 | 0.868–0.928 | 0.930–0.998 | 0.932–1.003 |
| remainderf / NaN-domain | 3.212–4.066 | 3.248–3.595 | 0.860–1.073 | 0.979–1.130 | 1.019–1.207 |
| remquof / NaN-domain | 2.931–3.177 | 2.905–3.125 | 0.986–1.009 | 1.016–1.017 | 1.025–1.166 |
| remquof_null / NaN-domain | 3.121–3.502 | 3.008–3.437 | 0.899–0.984 | 0.952–1.036 | 1.019–1.154 |

### GCC14 / host

NULL rows use host remainder as the reference.

| API / range | Own ns/call | Reference ns/call | Ratio p10 | Ratio median | Ratio p90 |
| --- | ---: | ---: | ---: | ---: | ---: |
| remainder / normal | 10.524–10.644 | 14.349–14.397 | 0.724–0.732 | 0.732–0.737 | 0.745–0.792 |
| remquo / normal | 11.171–11.573 | 18.200–19.034 | 0.575–0.603 | 0.598–0.618 | 0.617–0.660 |
| remquo_null / normal | 10.522–10.809 | 14.190–14.661 | 0.717–0.744 | 0.726–0.754 | 0.734–0.802 |
| remainder / half-ties | 6.174–6.297 | 25.942–26.478 | 0.235–0.237 | 0.238 | 0.240–0.245 |
| remquo / half-ties | 7.025–7.199 | 7.116–7.456 | 0.943–0.965 | 0.963–0.984 | 0.973–1.083 |
| remquo_null / half-ties | 6.111–6.279 | 25.941–26.482 | 0.233–0.235 | 0.236 | 0.238–0.243 |
| remainder / quotient-wrap | 5.527–5.667 | 7.192–7.353 | 0.762–0.764 | 0.766–0.782 | 0.791–0.806 |
| remquo / quotient-wrap | 5.835–6.032 | 7.116–7.315 | 0.794–0.820 | 0.822–0.830 | 0.830–0.950 |
| remquo_null / quotient-wrap | 5.618–5.744 | 7.194–7.355 | 0.763 | 0.766–0.799 | 0.794–0.930 |
| remainder / subnormal | 16.503–16.959 | 195.384–199.036 | 0.083–0.084 | 0.085 | 0.086–0.087 |
| remquo / subnormal | 18.623–20.106 | 74.362–80.441 | 0.240–0.244 | 0.248–0.252 | 0.259–0.272 |
| remquo_null / subnormal | 16.699–20.703 | 199.225–221.012 | 0.082–0.091 | 0.084–0.093 | 0.085–0.097 |
| remainder / wide-gap | 698.167–705.335 | 619.121–628.077 | 1.081–1.101 | 1.114–1.119 | 1.144–1.153 |
| remquo / wide-gap | 694.330–698.631 | 166.439–167.427 | 4.044–4.089 | 4.133–4.181 | 4.269–4.301 |
| remquo_null / wide-gap | 690.469–699.637 | 616.539–620.423 | 1.097–1.100 | 1.115–1.119 | 1.143–1.154 |
| remainder / zero | 2.667–2.812 | 19.861–19.875 | 0.131–0.136 | 0.132–0.142 | 0.142–0.146 |
| remquo / zero | 2.814–3.703 | 6.369–6.626 | 0.423–0.437 | 0.425–0.595 | 0.427–0.617 |
| remquo_null / zero | 2.611–2.716 | 19.861–19.872 | 0.129–0.131 | 0.131–0.132 | 0.132–0.142 |
| remainder / infinite-divisor | 2.811–3.005 | 19.929–20.236 | 0.131–0.141 | 0.141–0.144 | 0.151–0.161 |
| remquo / infinite-divisor | 2.965–3.105 | 4.162–4.769 | 0.624–0.706 | 0.640–0.713 | 0.684–0.719 |
| remquo_null / infinite-divisor | 2.616–2.812 | 19.927–19.933 | 0.131 | 0.132–0.141 | 0.141–0.152 |
| remainder / NaN-domain | 2.707–3.021 | 78.526–78.553 | 0.033–0.034 | 0.034–0.039 | 0.039–0.042 |
| remquo / NaN-domain | 2.896–3.584 | 2.031–2.516 | 1.346–1.422 | 1.353–1.438 | 1.441–1.469 |
| remquo_null / NaN-domain | 2.668–2.786 | 78.529–78.768 | 0.032–0.033 | 0.034–0.036 | 0.037 |
| remainderf / normal | 11.013–11.069 | 14.455–14.613 | 0.752–0.758 | 0.758–0.767 | 0.766–0.831 |
| remquof / normal | 11.109–11.363 | 16.955–18.586 | 0.603–0.633 | 0.617–0.678 | 0.623–0.694 |
| remquof_null / normal | 10.503–10.562 | 14.465–14.505 | 0.720–0.722 | 0.727–0.729 | 0.734–0.776 |
| remainderf / half-ties | 6.155–6.278 | 25.825–26.354 | 0.235–0.236 | 0.238 | 0.239–0.240 |
| remquof / half-ties | 6.853–7.006 | 7.010–7.225 | 0.961–0.992 | 0.969–0.996 | 0.973–1.002 |
| remquof_null / half-ties | 6.097–6.154 | 25.905–26.351 | 0.229–0.234 | 0.235–0.236 | 0.237–0.239 |
| remainderf / quotient-wrap | 5.502–5.620 | 6.976–7.193 | 0.760–0.764 | 0.766–0.789 | 0.788–0.865 |
| remquof / quotient-wrap | 5.746–5.898 | 6.845–7.187 | 0.798–0.834 | 0.810–0.842 | 0.820–0.850 |
| remquof_null / quotient-wrap | 5.476–5.758 | 6.976–7.193 | 0.761–0.785 | 0.766–0.801 | 0.789–0.827 |
| remainderf / subnormal | 10.791–10.848 | 191.474–192.090 | 0.055–0.056 | 0.056 | 0.057–0.060 |
| remquof / subnormal | 10.774–11.109 | 70.779–72.496 | 0.149–0.150 | 0.151–0.152 | 0.155–0.161 |
| remquof_null / subnormal | 10.211–10.533 | 191.805–192.109 | 0.052–0.053 | 0.053–0.054 | 0.054–0.057 |
| remainderf / wide-gap | 25.334–25.457 | 207.898–209.526 | 0.120 | 0.121–0.122 | 0.125 |
| remquof / wide-gap | 27.315–27.874 | 111.348–114.341 | 0.241–0.243 | 0.243–0.246 | 0.248–0.250 |
| remquof_null / wide-gap | 25.976–26.048 | 208.014–208.770 | 0.123 | 0.125 | 0.128 |
| remainderf / zero | 2.805–2.811 | 19.679–19.918 | 0.131–0.141 | 0.141–0.143 | 0.143 |
| remquof / zero | 2.756–2.839 | 6.616–6.925 | 0.403–0.409 | 0.408–0.424 | 0.431–0.438 |
| remquof_null / zero | 2.608–2.611 | 19.676–19.682 | 0.130–0.132 | 0.133 | 0.133–0.135 |
| remainderf / infinite-divisor | 2.812–3.007 | 20.315–20.604 | 0.129–0.138 | 0.139–0.146 | 0.146–0.157 |
| remquof / infinite-divisor | 2.969–3.152 | 4.688–5.021 | 0.586–0.638 | 0.604–0.670 | 0.623–0.703 |
| remquof_null / infinite-divisor | 2.615–2.811 | 20.287–20.611 | 0.127–0.128 | 0.129–0.138 | 0.139–0.175 |
| remainderf / NaN-domain | 2.950–3.084 | 78.564–78.611 | 0.033–0.034 | 0.038–0.039 | 0.039 |
| remquof / NaN-domain | 2.863–3.907 | 2.179–3.042 | 1.280–1.285 | 1.284–1.325 | 1.288–1.780 |
| remquof_null / NaN-domain | 2.698–2.846 | 78.571–78.816 | 0.032–0.033 | 0.034–0.036 | 0.037 |

### GCC16 / actual-prior

| API / range | Own ns/call | Reference ns/call | Ratio p10 | Ratio median | Ratio p90 |
| --- | ---: | ---: | ---: | ---: | ---: |
| remainder / normal | 10.850–11.276 | 11.834–12.309 | 0.898–0.908 | 0.916–0.922 | 0.932–0.942 |
| remquo / normal | 10.967–11.324 | 11.771–12.195 | 0.917–0.926 | 0.925–0.937 | 0.937–0.946 |
| remquo_null / normal | 11.161–11.479 | 12.443–12.601 | 0.886–0.902 | 0.899–0.916 | 0.911–0.927 |
| remainder / half-ties | 6.759–7.013 | 6.953–7.125 | 0.965–0.967 | 0.972–0.974 | 0.976–0.990 |
| remquo / half-ties | 6.905–6.924 | 7.220–7.227 | 0.953–0.957 | 0.956–0.959 | 0.958–0.960 |
| remquo_null / half-ties | 6.775–6.864 | 6.986–7.144 | 0.952–0.955 | 0.958–0.968 | 0.970–0.995 |
| remainder / quotient-wrap | 5.892–6.190 | 6.103–6.294 | 0.891–0.961 | 0.959–0.990 | 1.000–1.057 |
| remquo / quotient-wrap | 5.804–5.843 | 6.033–6.082 | 0.953–0.958 | 0.958–0.962 | 0.964–0.968 |
| remquo_null / quotient-wrap | 6.009–6.132 | 5.990–6.076 | 0.932–0.963 | 0.989–1.020 | 1.033–1.068 |
| remainder / subnormal | 18.975–19.217 | 20.453–21.022 | 0.898–0.914 | 0.907–0.932 | 0.921–0.945 |
| remquo / subnormal | 19.053–19.366 | 20.440–20.947 | 0.910–0.923 | 0.924–0.933 | 0.933–0.941 |
| remquo_null / subnormal | 19.149–19.357 | 20.615–21.111 | 0.900–0.921 | 0.914–0.934 | 0.923–0.952 |
| remainder / wide-gap | 677.797–677.837 | 675.764–675.828 | 1.002 | 1.003 | 1.004 |
| remquo / wide-gap | 677.519–677.774 | 675.857–675.973 | 0.988–1.002 | 1.002–1.003 | 1.003–1.015 |
| remquo_null / wide-gap | 677.762–677.896 | 675.542–675.711 | 0.993–1.002 | 1.003 | 1.004–1.017 |
| remainder / zero | 3.342–3.631 | 3.203–3.758 | 0.881–0.939 | 1.001–1.130 | 1.069–1.156 |
| remquo / zero | 2.625–3.192 | 2.725–2.989 | 0.803–0.999 | 0.997–1.075 | 1.002–1.166 |
| remquo_null / zero | 3.059–3.346 | 3.116–3.346 | 0.752–0.874 | 0.932–1.003 | 1.137–1.232 |
| remainder / infinite-divisor | 3.272–3.787 | 3.126–3.675 | 0.877–0.998 | 1.004–1.065 | 1.069–1.156 |
| remquo / infinite-divisor | 2.737–3.118 | 2.683–2.987 | 0.856–0.996 | 0.926–1.076 | 1.001–1.166 |
| remquo_null / infinite-divisor | 2.969–3.564 | 3.058–3.342 | 0.825–0.931 | 0.930–1.060 | 1.073–1.211 |
| remainder / NaN-domain | 3.017–3.301 | 3.236–3.716 | 0.793–0.872 | 0.898–0.942 | 0.946–1.059 |
| remquo / NaN-domain | 2.655–2.972 | 2.856–2.970 | 0.848–0.894 | 0.916–1.017 | 0.939–1.037 |
| remquo_null / NaN-domain | 2.949–3.139 | 3.140–3.406 | 0.772–0.914 | 0.911–0.999 | 0.984–1.075 |
| remainderf / normal | 11.359–11.408 | 12.547–12.654 | 0.878–0.887 | 0.897–0.907 | 0.919–0.924 |
| remquof / normal | 11.343–11.573 | 12.381–12.702 | 0.898–0.909 | 0.905–0.918 | 0.914–0.927 |
| remquof_null / normal | 11.402–11.598 | 12.605–12.751 | 0.891–0.897 | 0.905–0.911 | 0.922–0.927 |
| remainderf / half-ties | 6.856–7.021 | 7.096–7.120 | 0.961–0.964 | 0.973–0.987 | 1.000–1.028 |
| remquof / half-ties | 6.757–6.904 | 7.062–7.237 | 0.952–0.955 | 0.954–0.957 | 0.956–0.959 |
| remquof_null / half-ties | 6.770–6.812 | 6.976–6.989 | 0.952–0.953 | 0.955–0.959 | 0.980–0.996 |
| remainderf / quotient-wrap | 5.875–6.298 | 6.014–6.415 | 0.884–0.969 | 0.961–1.024 | 1.034–1.061 |
| remquof / quotient-wrap | 5.775–5.805 | 6.028–6.036 | 0.954–0.956 | 0.959–0.962 | 0.964–0.969 |
| remquof_null / quotient-wrap | 6.000–6.070 | 6.058–6.166 | 0.922–0.933 | 0.986–0.990 | 1.020–1.051 |
| remainderf / subnormal | 11.735–11.916 | 12.845–13.062 | 0.894–0.900 | 0.910–0.915 | 0.927–0.932 |
| remquof / subnormal | 11.883–12.040 | 13.271–13.367 | 0.880–0.888 | 0.895–0.901 | 0.907–0.913 |
| remquof_null / subnormal | 11.587–11.861 | 12.979–13.381 | 0.869–0.878 | 0.884–0.891 | 0.898–0.903 |
| remainderf / wide-gap | 28.754–28.865 | 29.698–29.791 | 0.953–0.958 | 0.966–0.970 | 0.979–0.986 |
| remquof / wide-gap | 27.947–28.090 | 29.804–29.885 | 0.924–0.928 | 0.935–0.941 | 0.950–0.955 |
| remquof_null / wide-gap | 27.882–27.952 | 29.715–29.818 | 0.923–0.926 | 0.937–0.939 | 0.948–0.954 |
| remainderf / zero | 3.086–3.583 | 3.138–3.704 | 0.832–0.931 | 0.882–1.110 | 1.003–1.156 |
| remquof / zero | 2.624–3.117 | 2.750–3.049 | 0.802–0.856 | 0.994–1.001 | 1.001–1.166 |
| remquof_null / zero | 3.052–3.417 | 3.057–3.323 | 0.857–0.998 | 0.877–1.060 | 1.142–1.216 |
| remainderf / infinite-divisor | 3.198–3.624 | 3.190–3.632 | 0.865–0.869 | 0.884–1.115 | 1.002–1.199 |
| remquof / infinite-divisor | 2.684–3.050 | 2.695–2.883 | 0.855–0.922 | 0.996–1.073 | 1.166–1.167 |
| remquof_null / infinite-divisor | 3.055–3.624 | 3.118–3.268 | 0.860–0.876 | 0.936–1.063 | 1.079–1.216 |
| remainderf / NaN-domain | 3.099–3.549 | 3.151–3.385 | 0.911–0.948 | 0.984–1.076 | 1.001–1.096 |
| remquof / NaN-domain | 2.653–2.768 | 2.803–3.062 | 0.862–0.907 | 0.866–0.966 | 0.933–1.021 |
| remquof_null / NaN-domain | 3.134–3.215 | 3.151–3.415 | 0.877–0.962 | 0.948–1.088 | 0.985–1.094 |

### GCC16 / host

NULL rows use host remainder as the reference.

| API / range | Own ns/call | Reference ns/call | Ratio p10 | Ratio median | Ratio p90 |
| --- | ---: | ---: | ---: | ---: | ---: |
| remainder / normal | 9.988–10.081 | 13.487–13.769 | 0.716–0.732 | 0.725–0.742 | 0.729–0.754 |
| remquo / normal | 10.689–10.911 | 18.230–18.481 | 0.560–0.573 | 0.584–0.593 | 0.601–0.623 |
| remquo_null / normal | 10.086–10.501 | 13.819–14.061 | 0.712–0.747 | 0.720–0.758 | 0.726–0.770 |
| remainder / half-ties | 6.344–6.482 | 25.321–25.742 | 0.245–0.246 | 0.250–0.252 | 0.258–0.261 |
| remquo / half-ties | 6.770–6.920 | 7.498–7.750 | 0.875–0.902 | 0.890–0.919 | 0.908–0.925 |
| remquo_null / half-ties | 6.270–6.342 | 25.738–25.746 | 0.242–0.243 | 0.245–0.246 | 0.247–0.254 |
| remainder / quotient-wrap | 5.881–5.901 | 6.829–6.977 | 0.808–0.837 | 0.838–0.863 | 0.865–0.868 |
| remquo / quotient-wrap | 5.683–5.840 | 7.403–7.727 | 0.729–0.765 | 0.757–0.781 | 0.780–0.790 |
| remquo_null / quotient-wrap | 5.762–5.897 | 6.827–6.893 | 0.790–0.857 | 0.832–0.862 | 0.863–0.866 |
| remainder / subnormal | 16.207–16.615 | 194.374–194.662 | 0.082–0.083 | 0.083–0.085 | 0.085–0.087 |
| remquo / subnormal | 18.501–18.886 | 75.011–75.386 | 0.238–0.241 | 0.246–0.249 | 0.258–0.260 |
| remquo_null / subnormal | 16.035–16.837 | 194.503–194.642 | 0.081–0.085 | 0.082–0.087 | 0.085–0.088 |
| remainder / wide-gap | 684.513–707.483 | 615.689–621.371 | 0.959–1.101 | 1.106–1.114 | 1.142–1.148 |
| remquo / wide-gap | 684.921–685.531 | 166.826–167.071 | 4.024–4.038 | 4.103–4.110 | 4.217–4.238 |
| remquo_null / wide-gap | 686.132–691.005 | 616.071–616.619 | 1.099–1.100 | 1.114–1.117 | 1.146–1.152 |
| remainder / zero | 2.893–3.083 | 19.652–19.680 | 0.133–0.152 | 0.151–0.153 | 0.153–0.174 |
| remquo / zero | 2.681–2.842 | 6.439–6.804 | 0.388–0.404 | 0.392–0.429 | 0.455–0.476 |
| remquo_null / zero | 2.700–3.205 | 19.665–19.675 | 0.122–0.143 | 0.141–0.163 | 0.143–0.173 |
| remainder / infinite-divisor | 2.894–3.215 | 19.738–19.747 | 0.132–0.150 | 0.149–0.163 | 0.153–0.173 |
| remquo / infinite-divisor | 2.739–3.037 | 4.981–5.264 | 0.507–0.525 | 0.516–0.609 | 0.536–0.634 |
| remquo_null / infinite-divisor | 2.705–3.084 | 19.732–19.740 | 0.122–0.140 | 0.140–0.155 | 0.143–0.173 |
| remainder / NaN-domain | 2.843–3.040 | 78.367–78.372 | 0.033–0.038 | 0.036–0.039 | 0.039–0.041 |
| remquo / NaN-domain | 2.724–3.316 | 2.401–3.013 | 1.034–1.080 | 1.085–1.173 | 1.137–1.252 |
| remquo_null / NaN-domain | 2.610–2.794 | 78.366–78.375 | 0.030–0.033 | 0.033–0.036 | 0.036–0.038 |
| remainderf / normal | 10.547–10.706 | 14.327–14.513 | 0.725–0.732 | 0.735–0.740 | 0.744–0.750 |
| remquof / normal | 10.810–11.042 | 17.039–17.679 | 0.595–0.638 | 0.609–0.648 | 0.618–0.654 |
| remquof_null / normal | 10.442–10.983 | 14.214–14.303 | 0.724–0.757 | 0.731–0.766 | 0.740–0.774 |
| remainderf / half-ties | 6.403–6.434 | 25.931–25.935 | 0.241–0.243 | 0.248 | 0.252–0.253 |
| remquof / half-ties | 6.759–7.055 | 7.348–7.867 | 0.885–0.913 | 0.893–0.920 | 0.900–0.929 |
| remquof_null / half-ties | 6.252–6.282 | 25.928–25.934 | 0.237–0.240 | 0.241–0.242 | 0.248–0.252 |
| remainderf / quotient-wrap | 5.879–6.016 | 6.829–7.131 | 0.788–0.841 | 0.852–0.863 | 0.866–0.867 |
| remquof / quotient-wrap | 5.808–5.820 | 7.184–7.270 | 0.767–0.806 | 0.806–0.814 | 0.812–0.819 |
| remquof_null / quotient-wrap | 5.748–5.986 | 6.827–6.976 | 0.783–0.810 | 0.826–0.862 | 0.863–0.866 |
| remainderf / subnormal | 9.863–9.940 | 191.353–191.533 | 0.050–0.051 | 0.051–0.052 | 0.053 |
| remquof / subnormal | 10.948–11.147 | 72.625–73.124 | 0.147–0.149 | 0.151–0.152 | 0.157–0.160 |
| remquof_null / subnormal | 9.853–9.904 | 191.436–191.537 | 0.050–0.051 | 0.051–0.052 | 0.053–0.054 |
| remainderf / wide-gap | 26.090–26.135 | 207.676–208.163 | 0.124 | 0.126 | 0.128–0.129 |
| remquof / wide-gap | 28.208–28.335 | 114.054–114.407 | 0.244–0.245 | 0.247 | 0.251–0.253 |
| remquof_null / wide-gap | 25.987–26.124 | 207.412–208.190 | 0.123–0.124 | 0.125–0.126 | 0.128 |
| remainderf / zero | 2.893–3.278 | 19.766–19.803 | 0.131–0.147 | 0.150–0.170 | 0.153–0.173 |
| remquof / zero | 2.674–2.942 | 6.916–7.158 | 0.365–0.372 | 0.372–0.424 | 0.398–0.480 |
| remquof_null / zero | 2.705–2.865 | 19.529–19.781 | 0.122–0.141 | 0.141–0.142 | 0.142–0.172 |
| remainderf / infinite-divisor | 2.865–3.277 | 20.386–20.402 | 0.128–0.147 | 0.138–0.164 | 0.148–0.167 |
| remquof / infinite-divisor | 2.740–3.093 | 4.105–4.438 | 0.617–0.651 | 0.655–0.688 | 0.679–0.773 |
| remquof_null / infinite-divisor | 2.807–3.036 | 20.330–20.379 | 0.126–0.137 | 0.138–0.146 | 0.157–0.167 |
| remainderf / NaN-domain | 2.798–2.942 | 78.492–78.516 | 0.035 | 0.036–0.038 | 0.038–0.041 |
| remquof / NaN-domain | 2.666–2.979 | 2.457–2.938 | 0.989–0.998 | 0.992–1.080 | 1.079–1.139 |
| remquof_null / NaN-domain | 2.688–2.703 | 78.465–78.513 | 0.031–0.033 | 0.034–0.036 | 0.036–0.038 |
