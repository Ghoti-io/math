# Binary64 unary arctangent

`gmath_atan` adds the binary64 unary entry point with independent numerical
references, explicit caller-state checks and compact container-free test data.
The accuracy and platform limits below are part of its contract.

`gmath_atan(x)` uses the existing own-project binary64 `gmath_atan2(x,1)` only
for `2^-30 <= |x| < 2^54`. The unary change leaves the existing binary kernel, table and arithmetic
helpers unchanged. A separate x87 reader correction supports no-SSE mode
queries without libm; production library links remain free of libm. General nearest accuracy inherits the old kernel's one-ULP contract;
its roughly 0.55-ULP error budget is measured, not a complete mathematical
proof of its fitted polynomial and floating evaluation. No new global bound,
general correct rounding or directed numerical accuracy is claimed.

The principal range and signed-zero/infinity definitions come from
[WG14 N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf),
7.12.4.3 and F.10.1.3. Canonical NaNs, explicit signaling invalid, errno
preservation and the following mode-independent guards are project choices.
NaNs are dispatched from raw bits before arithmetic: canonical positive quiet
NaN, with invalid only for signaling inputs. Both signed zeros retain bits
without new flags. Every valid nonzero input requires inexact; underflow is
required exactly for subnormal inputs. Caller errno/mode/incoming standard
flags survive; production code never changes controls. Full libm errno and
long-double semantics are not promised.

For `0 < |x| < 2^-30`, `0 < |x-atan(x)| < |x|^3/3`, safely below the nearest
midpoint distance even on the predecessor side of a power of two. Return the
input bits in every standard mode. All subnormal inputs therefore round to
themselves and need UF/IX; minimum normal rounds to minimum normal and needs IX
only under the chosen after-rounding tininess policy.

For `|x| >= 2^54`, `0 < pi/2-atan(|x|) < 2^-54`. The existing nearest pi/2 high
constant lies below pi/2 by about `6.123e-17`, greater than `2^-54`, and its
upper midpoint lies above true pi/2. The entire tail is thus in that nearest
constant's cell. Return nearest signed pi/2 and require IX, including infinity.
This avoids the old general binary kernel's potentially tiny reciprocal for
huge inputs. Independent directed constant checks certify this cell.

On the remaining interval the binary kernel has `v=1` below one and `u=1`
above one, so its computed quotient cannot exceed one in any mode. The table
index is consequently within rows 0..64; directed selection changes numerical
error but does not access another row. Bounded intermediates avoid incidental
UF/OF. The source-linked guard/index/flag certificate is separate from
the unproved general fitted-kernel accuracy budget.

Four initial literal tests pass 5,632 calls across four modes, 32 requested
incoming subsets and two errno seeds. Actual incoming flags are captured because
requests can merge. Tests cover zeros/NaNs, tiny and minimum-normal boundaries,
large finite/infinite inputs and representative general values. These are
initial native checks, not independent reference accuracy, full compiler/cross
coverage or exhaustive environment evidence. The first test link lacked its
own GoogleTest main and failed; the corrected test binary passes. That failed
invocation is not a numerical failure or a passing test run.


The first independent directed MPFR1200/mpmath1240 generation contains 28,382
raw and 28,278 generic rows. MPFR decodes inputs through `struct`; mpmath uses
separate exact integer decoding. Both agree on binary64 nearest targets and
binary32 signed true-ULP error cells. Below `2^-104`, an analytic predecessor-
binade bound certifies signed error rounding to zero; finite precision alone
is not treated as proof that atan(x)=x. The conservative unit correction and
independent input decoding were applied before byte-identical regeneration.

The population sweeps all finite exponent fields, subnormal leading bits, both
signs, guard/table seams, reciprocal centers, signaling payloads and random
words. Decimal sine/cosine Taylor inverse-cell selection agrees at two
precisions and is cross-checked with mpmath tangent. This selection agreement
is not a rigorous interval proof. Its first inverse stratum is linear and
covers the eight input binades -38 through -31; it does not cover all seventy
binades down to the stratum's lower endpoint. Ordinary input exponent coverage
comes from the separate exponent sweep.

Three mandatory complete-file SHA256/LF gates protect two independent reference
payloads and one explicitly observed compatibility manifest. The nearest raw
hash is `281c70e9008ebb61`, ordered implementation digest `f2dc44556cd9a171`;
28,382 nearest observations plus 464,640 selected all-mode/state calls pass.
General directed values are checked for normal sign/class and state, then
hashed as observed behavior; those digests do not prove directed accuracy.
Nearest calls separately check independent closed error cells against a 0.60
sampled regression guard. The maximum conservative observed cell error is
0.532239005 ULP; 26 generic results differ from correctly rounded targets.
These facts support the explicit limitation on correct rounding.

The generic set is `atan ec6946b8a9e1891b / 28278`. Initial native checks preserve
all 86 previous sets and the legacy aggregate. Five focused tests pass 498,654
calls including the literal fixtures. Bounded C/C++ loaders reject malformed
metadata/word shapes, NUL/partial/oversized/nonregular files and unsorted inputs;
metadata uses checked integer accumulation. Mandatory host checks reconstruct
complete requested populations and generic rows. The first pinned regeneration,
fresh-path/empty-directory unit and all-87-set numeric overlay gate passes.
The later validation section records completed compiler and cross-target checks.

The source-linked guard certificate checks tiny/large cells, directed pi/2
constants, unary index endpoints and necessary finite-range conditions, binding
the reviewed wrapper/kernel/table fingerprints. It expressly does not prove the
general fitted approximation/evaluation budget or formally verify C/compiler
execution. Its initial pinned positive passes, along with all 24 optimized-
Python rejection probes and six normal pinned certificate controls. A later
compile-time IEEE binary64 assertion only changes applicability declarations;
the current certificate/regeneration/fresh recipe rerun passes. Those initial checks preceded the completed cross, focused sanitizer, final
performance and failed Valgrind scopes recorded below.


Initial source/state calibration detects 21 runtime defects plus the supported
native SSE control defect through both C17 and C++ callers, with a passing
unplanted control. The force-only IX defect preserves bits at input
`0010000000000000` while losing IX in both callers. This family's narrow witness
is verified; earlier expf/exp2f/atanf/cbrtf witness gaps remain unchanged.
Caller calibration now covers 14 C17/C++ passing configurations and ten real
restoration defects, including failure after actual calls and late malformed
input. Loader/value, mandatory checksum and process/accounting faults reject;
the numerical-cell counterfactual disables the accuracy helper and demonstrates
that the same parse-valid bad target then escapes. Fresh-directory controls
exercise a former-family environment-variable typo with an equal-sized fallback.
These accounting controls are distinct from independent oracle evidence.

Six actual oracle/pin defects, two ignored generator requests, five mathematical
certificate defects and three applicability defects reject. Publication has two
passing controls and eight ordinary-exception rollback controls; it is not
crash-atomic. The first precision-fault controller used the wrong diagnostic;
its corrected intended-layer check passes. Recording engines calibrate dispatch
and absence behavior only.

The scalar benchmark selects repeated corpus members and independently checks
all 45,056 emitted input/target/error-cell records before timing. It reports
source and used-input counts, so the short special-value workloads are explicit.
Nearest-only timing uses integer timestamps, alternating identical input batches,
checked result hashes and per-input state checks. Reduced benchmark controls
and all final measurements are complete; the later tables retain their absolute
times and paired quantiles. Raw timing records remain outside source history.
Completed cross probes and the remaining combined acceptance gate are described
in the validation section below.

The timed result checksum performs eight serialized FNV byte steps per call.
Its cost is included in every absolute time and ratio, along with loop and
indirect-call overhead; fast-path ratios can consequently be pulled toward one.
Paired integer samples are retained privately before sorting. They are not
committed benchmark output. Sign-interleaved selection includes both signs in
every range, and a reciprocal range covers `4 <= |x| < 2^54`.

## Production linking

The production shared object is linked by the C compiler with no host libm
or C++ runtime in its link flags. The Linux production-link gate checks real
shared/example commands, package link metadata, dynamic dependencies and bare C
static/shared clients. Explicit unused `-lm` in a production command rejects
even if the linker would drop it. Actual forbidden-dependency shared fixtures
exercise the ELF check. Test-only oracle comparisons and platform fenv checks
use separate test flags. Explicit query configurations on unsupported ports
retain their documented platform fenv requirement.


## Compact reference storage

Only the 2,000 literal seeded answers and the small observed compatibility
manifest are committed. The two full grid files are ignored caches. Native
preparation reconstructs their deterministic rows using Decimal half-angle
reduction, an alternating series and Machin's pi identity, while reusing every
literal seeded answer. Both entire files must match the original independently
MPFR/mpmath-certified SHA256 anchors before publication. This reconstruction
is an encoding/storage mechanism, not a new rigorous approximation bound.

Three Decimal precisions (130, 170 and 210 digits) reproduce all pinned bytes.
Controls require the literal seed rows to be used, verify cold/warm/partially
missing caches, preserve valid file permissions and timestamps, and reject
seed corruption, existing cache corruption and a wrong reconstructed result.
A corrupt existing file is never silently repaired. Publication creates only
missing files and is individually atomic, not a multi-file transaction. Tests
continue checking and naming each input without a container. Pinned oracle
regeneration remains independent of this native preparation. Direct corpus
probes require preparation first; a cross environment without Python can use
the cache prepared before copying the tree. Dependency-free `libver-gen` and
SDK-only builds do not prepare test data.

## Completed validation and limitations

Focused GCC14 and GCC16 gates and the five unit tests pass. The complete
Clang unit-only run has 255 tests in 36 binaries: 254 pass and one older
native32-only case skips. All five focused ASan/UBSan tests pass (498,654 calls).
The earlier full GCC14 run predates production-link changes; those changes
have their own verified full baseline runs. The default combined acceptance gate is `make test`; its compiler and actual
result are recorded with the implementation commit. Independent mathematical,
blind, follow-up and final evidence reviews close the reported findings.

Six emulated targets agree on all 87 numerical sets in default/portable
configurations and 24 O0/O2 raw-state profiles (11,832,528 observations).
Twelve bare no-libm clients link and run. Extra portable defines do not select
a distinct unary kernel. The i686 O0 caller has no floating argument loads;
this does not establish general x87 numerical ABI behavior. Three new fresh
populations and a larger 46,382-row population pass complete targets, population,
unit/path/empty-directory and 87-set overlays on both native compilers.
No larger cross-target, physical-target, Windows/LLP64, Darwin, RISC-V,
exhaustive environment or application-timing result is claimed.

Valgrind 3.24 invokes all five tests and fails all five (make exit 2, test exit 1).
The corpus stops at its second row, so that scope is partial. Its 4,609 reported
mismatches have equal result bits, errno and mode but different exception flags,
including missing IV/IX/UF. It reports zero memory errors and no leaks; this does
not make the failed partial run passing. Prior plain-arithmetic reproductions
establish missing instrumented flags independently; attributing every mismatch
to that limitation is an inference. No assertions are weakened.

## Paired host baseline

All 88 predeclared records are retained: two runs per compiler, eleven ranges
and two incoming states. Each uses eight warmups, 401 alternating pairs and
4,096 identical inputs. The required runner independently certifies all 45,056
emitted reference cells before timing. Raw integer timestamps, per-run statuses,
binary/archive/compiler and loader context are retained outside source history;
only these Markdown envelopes are committed. This provenance is not arbitrary
source authentication. Fixed logical affinity is not CPU isolation or governor
control. Eight serialized checksum byte steps per call, loop/call overhead and
first-exception amortization are included. This is a new-API baseline with no
speed admission threshold, and implies no general or application speed win.

Each cell is the minimum–maximum across both retained runs. Paired ratio
quantiles are calculated from per-pair ratios, not ratios of separate aggregate
medians. Values below one favor this library; ordinary paths are slower than
host libm in these runs.

### GCC14

| Range | Incoming | Own ns/call | Host ns/call | Paired P10 | Paired median | Paired P90 |
|---|---|---:|---:|---:|---:|---:|
| ordinary | clean | 46.868–48.269 | 26.145–26.964 | 1.753–1.765 | 1.791–1.791 | 1.828–1.838 |
| ordinary | UF/IX | 46.747–48.456 | 26.109–27.051 | 1.756–1.757 | 1.791–1.793 | 1.821–1.828 |
| direct | clean | 38.891–41.017 | 21.523–22.439 | 1.786–1.798 | 1.822–1.824 | 1.880–1.880 |
| direct | UF/IX | 39.535–40.562 | 21.651–22.385 | 1.769–1.792 | 1.818–1.822 | 1.880–1.881 |
| table | clean | 46.575–46.651 | 22.394–22.413 | 2.054–2.066 | 2.080–2.081 | 2.110–2.114 |
| table | UF/IX | 43.548–46.676 | 20.929–22.418 | 2.043–2.063 | 2.080–2.081 | 2.120–2.125 |
| tiny-normal | clean | 17.294–17.297 | 18.022–18.068 | 0.954–0.955 | 0.962–0.962 | 0.967–0.967 |
| tiny-normal | UF/IX | 17.295–17.314 | 18.028–18.075 | 0.955–0.955 | 0.962–0.962 | 0.967–0.967 |
| subnormal | clean | 124.943–129.308 | 128.214–132.777 | 0.953–0.956 | 0.972–0.974 | 0.988–0.992 |
| subnormal | UF/IX | 124.692–125.186 | 128.081–128.372 | 0.948–0.949 | 0.972–0.974 | 0.993–1.002 |
| wide | clean | 17.314–17.856 | 17.722–18.078 | 0.968–0.974 | 0.977–0.979 | 0.984–0.985 |
| wide | UF/IX | 17.301–17.379 | 17.623–17.887 | 0.968–0.971 | 0.977–0.978 | 0.985–0.986 |
| zero | clean | 17.236–17.247 | 17.497–17.604 | 0.978–0.978 | 0.980–0.982 | 0.986–0.987 |
| zero | UF/IX | 17.237–17.239 | 17.494–17.504 | 0.977–0.979 | 0.980–0.985 | 0.986–0.987 |
| infinity | clean | 16.714–17.305 | 17.170–17.780 | 0.971–0.972 | 0.973–0.973 | 0.975–0.976 |
| infinity | UF/IX | 16.708–16.720 | 17.168–17.180 | 0.965–0.972 | 0.973–0.974 | 0.975–0.978 |
| qNaN | clean | 12.576–17.279 | 12.484–17.312 | 0.980–0.996 | 1.001–1.001 | 1.011–1.029 |
| qNaN | UF/IX | 16.211–16.775 | 16.169–16.732 | 1.001–1.002 | 1.003–1.003 | 1.004–1.016 |
| sNaN | clean | 16.124–16.686 | 16.163–16.727 | 0.996–0.996 | 0.998–0.998 | 0.998–1.000 |
| sNaN | UF/IX | 15.057–17.277 | 15.154–17.317 | 0.978–0.996 | 0.998–0.998 | 0.998–1.015 |
| reciprocal | clean | 35.360–38.789 | 24.228–26.528 | 1.435–1.443 | 1.458–1.460 | 1.484–1.497 |
| reciprocal | UF/IX | 36.285–38.930 | 24.853–26.582 | 1.445–1.445 | 1.459–1.464 | 1.477–1.492 |

### GCC16

| Range | Incoming | Own ns/call | Host ns/call | Paired P10 | Paired median | Paired P90 |
|---|---|---:|---:|---:|---:|---:|
| ordinary | clean | 33.942–35.178 | 23.657–24.513 | 1.430–1.431 | 1.435–1.436 | 1.441–1.441 |
| ordinary | UF/IX | 35.119–35.165 | 24.458–24.499 | 1.408–1.431 | 1.435–1.436 | 1.451–1.456 |
| direct | clean | 30.381–30.393 | 20.333–20.339 | 1.488–1.489 | 1.494–1.494 | 1.499–1.522 |
| direct | UF/IX | 28.333–30.432 | 18.979–20.368 | 1.488–1.489 | 1.494–1.494 | 1.503–1.519 |
| table | clean | 32.847–33.951 | 21.708–24.729 | 1.310–1.554 | 1.330–1.564 | 1.354–1.595 |
| table | UF/IX | 34.881–35.170 | 22.435–26.445 | 1.285–1.557 | 1.328–1.564 | 1.338–1.572 |
| tiny-normal | clean | 16.650–17.888 | 17.188–18.471 | 0.964–0.966 | 0.968–0.969 | 0.970–0.971 |
| tiny-normal | UF/IX | 14.675–17.888 | 15.584–18.584 | 0.956–0.960 | 0.962–0.962 | 0.964–0.966 |
| subnormal | clean | 115.771–124.585 | 120.107–128.984 | 0.940–0.948 | 0.962–0.965 | 0.982–0.989 |
| subnormal | UF/IX | 117.037–124.031 | 121.844–129.069 | 0.942–0.945 | 0.960–0.964 | 0.979–0.981 |
| wide | clean | 16.636–17.248 | 17.162–17.813 | 0.967–0.967 | 0.969–0.969 | 0.971–0.971 |
| wide | UF/IX | 16.088–17.862 | 16.779–18.089 | 0.957–0.958 | 0.959–0.960 | 0.961–0.967 |
| zero | clean | 16.178–17.970 | 16.758–18.585 | 0.964–0.964 | 0.966–0.966 | 0.969–0.969 |
| zero | UF/IX | 16.731–17.969 | 17.298–18.579 | 0.963–0.963 | 0.966–0.966 | 0.969–0.969 |
| infinity | clean | 16.635–17.249 | 17.474–18.260 | 0.943–0.944 | 0.947–0.947 | 0.953–0.955 |
| infinity | UF/IX | 16.083–17.869 | 16.894–18.775 | 0.944–0.947 | 0.951–0.951 | 0.954–0.957 |
| qNaN | clean | 17.279–17.906 | 17.203–17.824 | 1.003–1.003 | 1.004–1.005 | 1.006–1.006 |
| qNaN | UF/IX | 17.278–17.278 | 17.194–17.199 | 1.004–1.004 | 1.005–1.005 | 1.005–1.007 |
| sNaN | clean | 17.244–17.872 | 17.202–17.837 | 1.001–1.001 | 1.002–1.003 | 1.004–1.005 |
| sNaN | UF/IX | 17.268–17.869 | 17.205–17.835 | 1.001–1.002 | 1.002–1.003 | 1.004–1.006 |
| reciprocal | clean | 30.790–30.805 | 26.590–26.623 | 1.146–1.148 | 1.155–1.156 | 1.178–1.186 |
| reciprocal | UF/IX | 29.682–29.741 | 25.659–25.795 | 1.146–1.147 | 1.155–1.156 | 1.168–1.180 |
