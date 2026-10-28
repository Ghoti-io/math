# Current-mode nearby integer rounding

`gmath_nearbyint` and `gmath_nearbyintf` round to integral values of their own
floating type using the current standard rounding mode. Nearest uses ties to
even. Signed zeros, infinities and integral inputs retain their bits. NaNs
canonicalize to positive quiet NaN; only signaling inputs add invalid. All other
calls add no exception, including inexact. Caller errno, current mode and incoming
standard exception flags are preserved. Existing deterministic `gmath_rint` and
`gmath_rintf` are unchanged and deliberately have different mode semantics.

## Construction and scope

The implementation decodes raw IEEE fields. Magnitudes below one compare with
one half for nearest, or select signed zero/one from direction and sign. For
larger nonintegral inputs, clearing the low `cut` significand bits gives the
integer below the magnitude. The discarded field determines rounding; at an
exact half, the retained integer's low bit selects even. Adding one encoded
integer unit can carry at most to 2^52 or 2^23. Larger inputs are already integral.
All shifts are bounded by the format's significand width. Valid paths use only
integer arithmetic and bit copies, so they cannot produce floating inexact or
underflow from tiny arguments. Signaling NaNs explicitly raise invalid.

GNU-compatible native readers cover x86 SSE, AArch64, s390x, PowerPC32/64 and
SPARC. They read rounding controls rather than modify them. The contract assumes
coherent, nontrapping standard C environments. On x86 the selected arithmetic
control is MXCSR; manually desynchronizing x87 and SSE is not a portable current
mode. Instruction-specific overrides and unsupported rounding codes are outside
the contract. SPARC STFSR/STXFSR may clear FTT trap-type status, which is not a
standard C exception flag. No preservation of arbitrary trap diagnostics is
promised.

`GMATH_NEARBY_FENV_QUERY` and ports excluded by the native architecture/FP
predicates (including PPC/SPARC soft-float) use a real `fegetround`, with errno saved/restored around that query. This configuration may
require a platform fenv runtime, including libm. It does not silently substitute a
constant `FLT_ROUNDS`. Native clients are separately linked and executed without
libm; a separate platform-query client actually calls both APIs with its required
runtime. The RISC-V native reader is not implemented. Windows runtime validation remains
unperformed; compatible x86 compiler predicates may select the native reader.

## Independent checks

The reference generator constructs exact rational values and rounds using integer
floor, ceiling, truncation and nearest parity. Independently decoded pinned MPFR
`rint` outputs agree in all four modes. Special-value and exception classes follow
the explicit public contract rather than host NaN payload/errno choices. Neither
implementation source from MPFR nor another libm was consulted or copied.

The committed population includes all exponent binades, tiny/normal boundaries,
half-cell neighbors at every fractional cut with odd/even/carry cases, both signs,
and all single signaling-payload bits plus maximum payloads. An independent
coverage check examines the actual serialized input words; deleting an interior
half-cell input is detected. This is directed coverage, not an exhaustive raw
input or environment proof.

There are 34,102 Double and 7,042 Float raw rows. Generic nearest corpora exclude
signaling inputs before conversion: 33,997 and 6,990 rows respectively. All five
payloads have mandatory complete-file SHA256 gates and LF checkout attributes.
Publication stages files and rolls back ordinary replacement exceptions, including
permissions and cleanup; it is not crash-atomic. A mixed interrupted generation
fails the complete checksum gate.

Each raw run checks all rows in four modes and two errno seeds, with all 32
requested incoming-flag subsets on selected cases: 548,632 calls total. Hardware
can merge requested flag combinations; the actual captured incoming state is
compared. Result/order hashes do not encode all hardware state. Control snapshots
also compare x86 MXCSR controls, AArch64 FPCR, PPC binary controls (not extended
DFP fields), defined s390 FPC controls and SPARC rounding/mask/nonstandard fields.
C flags, errno and mode are checked separately. A real x86 FTZ mutation must fail
specifically at control preservation.

Raw nearest hashes are `90e8e7927fcf767e` and `c053c0b70289f232`; ordered all-mode
hashes are `cbeb7e3a86db14d9` and `262938d80919ee5d`. Generic hashes are
`181c93ddf14441bf` and `c75989a801b50444`. All 78 earlier function sets and legacy
aggregate `f5fa269eb60ee34f` over 292,711 rows remain unchanged.

## Reproduction

Run the normal `make test` with the project's private dependency prefix. The
focused default gates include `check-nearby`, `check-planted-nearby`,
`check-nearby-mode-plants`, `check-nearby-controls`, `check-nearby-link`,
`check-nearby-oracle` and `check-nearby-oracle-controls`. Optional missing pinned
engines skip explicitly; required mode fails. Mandatory payload checks run even
without an engine. Recording-engine dispatch controls test accounting, not
numerical oracle correctness.

For explicit platform-query coverage, select a separate build directory and add
`-DGMATH_NEARBY_FENV_QUERY` to library flags. The Makefile propagates this backend
choice to C++ tests. `tools/check-nearby-mode-plants.py` accepts compiler, runner,
work-directory and flag environment overrides for cross-target direction controls.
`tools/probe-nearby.c` provides a standalone C17 raw/state check;
`tools/check-nearby-controls.py --fresh DIR --seed SEED --count COUNT` checks the
complete requested population, widening, path and optional C++/numeric overlays.

Final sequential GCC14.2 and GCC16.2 full `make test` commands return zero,
with persisted actual child statuses. Main unit runs have 237 tests in 33
binaries; Clang passes the same counts unit-only. Four focused ASan/UBSan tests
pass. A final explicit-fenv build passes its targeted value/link/plant gates and
three unit tests, with the native-only SSE desynchronization test correctly
skipped. Its native-query mutation skips loudly; its FTZ control and errno-query
mutations still execute.

Initial full attempts failed on missing public aliases, legacy mutation-probe
object closures, and an old atan comparison link. Aliases/closures were repaired;
the last link replay passed unchanged, and its precise cause was not established.
None of those failed full invocations is called successful. The final complete
GCC14 run passes; a later file-overview comment correction was followed by a full
unit-only rebuild/rerun. The final GCC16 run includes that comment. Numerical
sources and payloads stayed frozen throughout confirmed final runs.

Seventeen shared source/state defects, two format-local old-rint aliases and
separate native-query, nonround-control and errno-query faults detect in C17 and
C++ with passing controls. Six actual architecture-direction defects detect in
both formats. There are 56 loader/value negatives, five complete payload
corruptions, eight process/output accounting faults, two actual half-cell
omissions, four actual numerical/version oracle faults and two ignored-request
faults. Six supplemental hash omission/hash/count controls detect. Publication
controls include two positives and ten replacement-failure rollbacks. Recording
wrapper controls execute both real command dispatches and optional/required
absence branches even without numerical engines; they are accounting evidence.
Host pinned regeneration is byte-identical. Nested GCC16 optional numerical
engines skip explicitly; mandatory references and recording controls still run.

Six emulated targets (i686, AArch64, s390x, PowerPC64, PowerPC32 and SPARC64) agree
on all 80 generic result sets in default and portable/query configurations.
Twenty-four raw profiles cover O0/O2 and native/explicit-query readers, each
checking 548,632 all-mode/state calls. Twelve native client profiles actually
link and run without libm. The initial cross controller stopped at optimized
PPC64 because it incorrectly demanded an undefined `fegetround` symbol; GCC can
inline the real standard query. Corrected accounting checks the actual backend
macro and forbids native external queries, permitting fallback inlining. The
complete rerun passes. Native/soft-float predicate preprocessing is checked for
PPC32/64 and SPARC; no soft-float numerical run is claimed. The final i686 O0 raw
call body contains no `fldl`/`flds` argument loads.

Three retained fresh populations of 34,102/7,042 raw rows pass complete
seed/count/population, widening, path, actual C++ selection and all-80-set numeric
overlays on both native compilers. Their state-call totals are 547,392, 549,376
and 547,392. A larger 72,102/45,041-row population passes the same native checks,
with 1,507,792 state calls. Larger raw result hashes are `34c901304bd12f79` and
`ac182de44aa3864e`, ordered hashes `dde288bfc078d05d` and `0030b17a2b4f91ed`.
No larger cross-target run was performed. These are emulated probes, not
physical-host or full cross-target GoogleTest coverage. Physical cross-target hosts, Windows/RISC-V runtime,
soft-float numerical execution, exhaustive raw/environment space and application
workload timing remain unrun. Prior failed partial Valgrind scopes and earlier
force-only IX mutation witness gaps are unchanged; no new passing Valgrind claim.


## Paired host timing

Two predeclared runs per compiler/runtime context retain all 576 case records:
nine ranges, both formats, four modes and clean/UF-IX entry states. Eight paired
warmups precede 401 alternating pairs of 4,096 identical inputs. Integer
timestamps, per-input exact bits/classes and flag/errno/mode guards are outside
timed batches. Host NaN payloads may differ; own canonical bits are checked.
There is no prior API baseline for this new capability.

The table's own/host columns are amortized median ns/call envelopes across the
two runs. Paired p10/median/p90 columns are also two-run envelopes, not a ratio
of separate median times. Timing includes calls, loops, checksums, timestamps
and amortized first-exception costs. Both contexts use logical CPU affinity 0;
this supplies no CPU isolation or governor-control claim. Compiler/runtime and
absolute-time differences must not be attributed solely to compiler choice.
All predeclared final records are retained; no timing retry replaces a result.

Ordinary own/host paired medians span 2.616–3.975 Double and 3.046–4.087 Float
in GCC14, and 2.251–3.985 / 2.240–3.317 in GCC16. Most other ranges also trail;
GCC16 signed-zero Float is near parity. This phase adds coverage, with a concrete
performance gap to address. There is no overall, application or platform speed
win, and no general nonregression claim.

Reproduce with `make bench-nearby`, optionally selecting a separate compiler
build directory. `bench-nearby --validate-only` is available on the built
binary to run untimed guards. Private final logs retain compiler versions,
flags, linked-runtime paths, binary hashes and source snapshots; the table below
contains every case envelope.

### GCC14 compiler/runtime context

| Bits | Range | Mode | Entry | Own ns | Host ns | Ratio p10 | Ratio median | Ratio p90 |
|---|---|---|---|---:|---:|---:|---:|---:|
| 64 | normal | nearest | clean | 6.599–9.354 | 1.850–2.431 | 3.454–3.599 | 3.570–3.886 | 3.661–4.269 |
| 64 | normal | nearest | UF/IX | 6.386–10.039 | 1.854–2.528 | 3.376–3.663 | 3.452–3.975 | 3.934–4.423 |
| 64 | normal | down | clean | 5.306–8.120 | 1.819–2.520 | 2.740–2.964 | 2.850–3.224 | 3.265–3.536 |
| 64 | normal | down | UF/IX | 5.146–7.602 | 1.849–2.505 | 2.760–2.854 | 2.784–3.054 | 2.821–3.324 |
| 64 | normal | up | clean | 5.640–8.849 | 1.805–2.551 | 3.059–3.200 | 3.108–3.452 | 3.278–3.779 |
| 64 | normal | up | UF/IX | 5.760–9.122 | 1.895–2.617 | 3.007–3.200 | 3.039–3.510 | 3.155–3.810 |
| 64 | normal | zero | clean | 4.821–7.411 | 1.833–2.535 | 2.579–2.714 | 2.616–2.926 | 2.676–3.142 |
| 64 | normal | zero | UF/IX | 4.838–7.682 | 1.849–2.646 | 2.581–2.707 | 2.618–2.899 | 2.650–3.187 |
| 64 | half-ties | nearest | clean | 5.007–7.765 | 1.896–2.618 | 2.620–2.762 | 2.641–2.946 | 2.661–3.351 |
| 64 | half-ties | nearest | UF/IX | 5.005–7.818 | 1.869–2.568 | 2.614–2.802 | 2.638–3.003 | 2.692–3.418 |
| 64 | half-ties | down | clean | 5.790–8.800 | 1.851–2.538 | 2.931–3.240 | 3.084–3.464 | 3.549–3.819 |
| 64 | half-ties | down | UF/IX | 5.606–9.331 | 1.811–2.677 | 2.999–3.234 | 3.075–3.507 | 3.567–3.870 |
| 64 | half-ties | up | clean | 5.975–9.689 | 1.869–2.690 | 3.094–3.383 | 3.206–3.600 | 3.427–3.892 |
| 64 | half-ties | up | UF/IX | 5.682–9.337 | 1.806–2.581 | 3.102–3.371 | 3.149–3.610 | 3.660–3.942 |
| 64 | half-ties | zero | clean | 4.361–6.860 | 1.853–2.594 | 2.339–2.446 | 2.355–2.659 | 2.380–2.884 |
| 64 | half-ties | zero | UF/IX | 4.354–6.880 | 1.847–2.607 | 2.337–2.449 | 2.356–2.639 | 2.374–2.867 |
| 64 | tiny-normal | nearest | clean | 3.927–5.996 | 1.808–2.570 | 2.120–2.134 | 2.166–2.306 | 2.236–2.572 |
| 64 | tiny-normal | nearest | UF/IX | 4.005–5.958 | 1.849–2.513 | 2.137–2.144 | 2.168–2.331 | 2.527–2.907 |
| 64 | tiny-normal | down | clean | 5.815–9.051 | 1.849–2.543 | 3.108–3.335 | 3.148–3.541 | 3.660–3.781 |
| 64 | tiny-normal | down | UF/IX | 5.980–8.891 | 1.893–2.497 | 3.130–3.241 | 3.177–3.510 | 3.236–3.824 |
| 64 | tiny-normal | up | clean | 3.547–5.972 | 1.850–2.709 | 1.886–2.056 | 1.918–2.194 | 1.942–2.373 |
| 64 | tiny-normal | up | UF/IX | 3.537–5.671 | 1.843–2.573 | 1.903–2.008 | 1.918–2.188 | 1.938–2.389 |
| 64 | tiny-normal | zero | clean | 3.522–5.572 | 1.801–2.581 | 1.926–1.938 | 1.956–2.133 | 1.989–2.355 |
| 64 | tiny-normal | zero | UF/IX | 3.625–5.715 | 1.853–2.647 | 1.922–2.016 | 1.957–2.132 | 2.278–2.353 |
| 64 | subnormal | nearest | clean | 4.115–6.249 | 1.900–2.658 | 2.151–2.154 | 2.165–2.331 | 2.179–2.589 |
| 64 | subnormal | nearest | UF/IX | 4.006–6.069 | 1.848–2.617 | 2.138–2.148 | 2.170–2.307 | 2.518–2.520 |
| 64 | subnormal | down | clean | 5.950–9.257 | 1.852–2.583 | 3.110–3.308 | 3.223–3.567 | 3.685–3.850 |
| 64 | subnormal | down | UF/IX | 5.777–9.325 | 1.800–2.589 | 3.129–3.363 | 3.203–3.575 | 3.724–3.839 |
| 64 | subnormal | up | clean | 3.583–5.797 | 1.873–2.616 | 1.906–2.057 | 1.919–2.218 | 1.936–2.423 |
| 64 | subnormal | up | UF/IX | 3.643–5.721 | 1.896–2.579 | 1.906–2.059 | 1.924–2.209 | 2.238–2.439 |
| 64 | subnormal | zero | clean | 3.615–5.673 | 1.849–2.612 | 1.941–1.997 | 1.956–2.172 | 1.975–2.369 |
| 64 | subnormal | zero | UF/IX | 3.523–5.927 | 1.801–2.699 | 1.942–2.014 | 1.959–2.180 | 2.276–2.396 |
| 64 | large-integral | nearest | clean | 2.385–4.598 | 1.851–2.772 | 1.267–1.530 | 1.290–1.646 | 1.497–1.805 |
| 64 | large-integral | nearest | UF/IX | 2.391–4.472 | 1.853–2.766 | 1.284–1.550 | 1.289–1.626 | 1.311–1.779 |
| 64 | large-integral | down | clean | 2.447–4.371 | 1.899–2.694 | 1.281–1.482 | 1.289–1.614 | 1.299–1.728 |
| 64 | large-integral | down | UF/IX | 2.382–4.394 | 1.852–2.703 | 1.278–1.495 | 1.287–1.635 | 1.304–1.772 |
| 64 | large-integral | up | clean | 2.395–4.343 | 1.857–2.640 | 1.274–1.512 | 1.288–1.631 | 1.315–1.772 |
| 64 | large-integral | up | UF/IX | 2.393–4.388 | 1.856–2.659 | 1.280–1.469 | 1.287–1.639 | 1.305–1.787 |
| 64 | large-integral | zero | clean | 2.382–4.441 | 1.849–2.671 | 1.128–1.492 | 1.289–1.631 | 1.502–1.785 |
| 64 | large-integral | zero | UF/IX | 2.379–4.502 | 1.849–2.696 | 1.278–1.531 | 1.287–1.667 | 1.299–1.811 |
| 64 | signed-zero | nearest | clean | 2.443–4.121 | 1.899–2.667 | 1.146–1.438 | 1.286–1.574 | 1.295–1.729 |
| 64 | signed-zero | nearest | UF/IX | 2.380–4.409 | 1.849–2.784 | 1.275–1.475 | 1.287–1.581 | 1.297–1.638 |
| 64 | signed-zero | down | clean | 2.318–4.120 | 1.802–2.675 | 1.130–1.446 | 1.285–1.549 | 1.494–1.672 |
| 64 | signed-zero | down | UF/IX | 2.321–4.323 | 1.843–2.745 | 1.147–1.466 | 1.286–1.578 | 1.301–1.702 |
| 64 | signed-zero | up | clean | 2.319–3.987 | 1.803–2.552 | 1.211–1.377 | 1.285–1.574 | 1.294–1.707 |
| 64 | signed-zero | up | UF/IX | 2.322–4.094 | 1.804–2.605 | 1.276–1.424 | 1.287–1.563 | 1.299–1.719 |
| 64 | signed-zero | zero | clean | 2.334–4.362 | 1.845–2.777 | 1.127–1.458 | 1.285–1.578 | 1.375–1.712 |
| 64 | signed-zero | zero | UF/IX | 2.373–4.094 | 1.847–2.625 | 1.143–1.463 | 1.285–1.569 | 1.406–1.689 |
| 64 | infinity | nearest | clean | 2.319–4.531 | 1.801–2.787 | 1.281–1.510 | 1.288–1.616 | 1.300–1.755 |
| 64 | infinity | nearest | UF/IX | 2.377–4.299 | 1.847–2.594 | 1.272–1.503 | 1.287–1.645 | 1.485–1.784 |
| 64 | infinity | down | clean | 2.441–4.407 | 1.895–2.667 | 1.282–1.483 | 1.288–1.632 | 1.297–1.800 |
| 64 | infinity | down | UF/IX | 2.329–4.303 | 1.800–2.609 | 1.283–1.527 | 1.301–1.652 | 1.502–1.804 |
| 64 | infinity | up | clean | 2.320–4.547 | 1.801–2.721 | 1.280–1.529 | 1.288–1.648 | 1.298–1.800 |
| 64 | infinity | up | UF/IX | 2.323–4.524 | 1.801–2.762 | 1.277–1.560 | 1.292–1.640 | 1.499–1.799 |
| 64 | infinity | zero | clean | 2.378–4.201 | 1.848–2.490 | 1.281–1.433 | 1.287–1.665 | 1.295–1.893 |
| 64 | infinity | zero | UF/IX | 2.319–4.379 | 1.798–2.442 | 1.277–1.551 | 1.290–1.792 | 1.499–1.988 |
| 64 | qNaN | nearest | clean | 2.643–4.143 | 1.849–2.506 | 1.251–1.548 | 1.429–1.648 | 1.668–1.768 |
| 64 | qNaN | nearest | UF/IX | 2.425–4.380 | 1.852–2.647 | 1.282–1.591 | 1.297–1.672 | 1.441–1.759 |
| 64 | qNaN | down | clean | 2.392–4.542 | 1.849–2.681 | 1.252–1.618 | 1.288–1.704 | 1.663–1.822 |
| 64 | qNaN | down | UF/IX | 2.498–4.029 | 1.878–2.526 | 1.282–1.477 | 1.296–1.609 | 1.437–1.724 |
| 64 | qNaN | up | clean | 2.641–2.870 | 1.848–2.016 | 1.400–1.414 | 1.428–1.429 | 1.435–1.448 |
| 64 | qNaN | up | UF/IX | 2.578–2.639 | 1.808–1.849 | 1.288–1.382 | 1.425–1.428 | 1.434–1.499 |
| 64 | qNaN | zero | clean | 2.644–2.712 | 1.851–1.898 | 1.293–1.379 | 1.428 | 1.440–1.448 |
| 64 | qNaN | zero | UF/IX | 2.576–2.583 | 1.805–1.807 | 1.292–1.406 | 1.427–1.430 | 1.441–1.444 |
| 64 | sNaN | nearest | clean | 2.718–2.787 | 1.918–1.952 | 1.287–1.294 | 1.428 | 1.439–1.444 |
| 64 | sNaN | nearest | UF/IX | 2.578–2.713 | 1.851–1.900 | 1.289–1.416 | 1.428–1.429 | 1.437–1.501 |
| 64 | sNaN | down | clean | 2.448–2.717 | 1.900–1.901 | 1.284–1.291 | 1.290–1.429 | 1.429–1.441 |
| 64 | sNaN | down | UF/IX | 2.640–2.712 | 1.845–1.898 | 1.287–1.420 | 1.428–1.431 | 1.435–1.450 |
| 64 | sNaN | up | clean | 2.402–2.441 | 1.849–1.894 | 1.282–1.284 | 1.289–1.293 | 1.422–1.438 |
| 64 | sNaN | up | UF/IX | 2.584–2.641 | 1.847–1.893 | 1.279–1.287 | 1.413–1.429 | 1.435–1.660 |
| 64 | sNaN | zero | clean | 2.396–2.526 | 1.850–1.949 | 1.284–1.285 | 1.291–1.293 | 1.427–1.434 |
| 64 | sNaN | zero | UF/IX | 2.639–2.663 | 1.845–1.893 | 1.292 | 1.427–1.430 | 1.442–1.446 |
| 32 | normal | nearest | clean | 6.392–6.773 | 1.629–1.631 | 3.894–4.049 | 3.928–4.087 | 4.110–4.190 |
| 32 | normal | nearest | UF/IX | 6.184–6.658 | 1.585–1.630 | 3.860–4.020 | 3.908–4.061 | 3.989–4.119 |
| 32 | normal | down | clean | 5.132–5.476 | 1.590–1.674 | 3.182–3.240 | 3.220–3.287 | 3.301–3.360 |
| 32 | normal | down | UF/IX | 4.936–4.990 | 1.583–1.594 | 3.061–3.063 | 3.087–3.160 | 3.116–3.191 |
| 32 | normal | up | clean | 5.531–5.667 | 1.631–1.675 | 3.334–3.358 | 3.379–3.391 | 3.581–3.599 |
| 32 | normal | up | UF/IX | 5.470–5.525 | 1.629 | 3.331–3.355 | 3.364–3.387 | 3.396–3.421 |
| 32 | normal | zero | clean | 4.961–5.136 | 1.629–1.694 | 3.013–3.032 | 3.046–3.052 | 3.059–3.313 |
| 32 | normal | zero | UF/IX | 4.874–4.973 | 1.588–1.631 | 3.017–3.022 | 3.050 | 3.068–3.071 |
| 32 | half-ties | nearest | clean | 4.999–5.013 | 1.630–1.631 | 3.044–3.053 | 3.068–3.074 | 3.083–3.092 |
| 32 | half-ties | nearest | UF/IX | 4.873–5.138 | 1.589–1.669 | 3.043–3.057 | 3.068–3.074 | 3.090–3.096 |
| 32 | half-ties | down | clean | 5.878–6.045 | 1.613–1.674 | 3.578–3.582 | 3.611–3.631 | 3.770–3.785 |
| 32 | half-ties | down | UF/IX | 5.726–5.869 | 1.589–1.632 | 3.554–3.569 | 3.586–3.606 | 3.623–3.638 |
| 32 | half-ties | up | clean | 6.161–6.313 | 1.670–1.675 | 3.670–3.722 | 3.757–3.772 | 3.787–3.873 |
| 32 | half-ties | up | UF/IX | 5.700–6.111 | 1.551–1.674 | 3.622 | 3.655–3.663 | 3.703–3.749 |
| 32 | half-ties | zero | clean | 4.474–4.592 | 1.630–1.677 | 2.730–2.733 | 2.739–2.747 | 2.749–2.760 |
| 32 | half-ties | zero | UF/IX | 4.352–4.468 | 1.590–1.629 | 2.721–2.723 | 2.738–2.743 | 2.753–2.762 |
| 32 | tiny-normal | nearest | clean | 4.115–4.116 | 1.630–1.631 | 2.499–2.500 | 2.525 | 2.550–2.561 |
| 32 | tiny-normal | nearest | UF/IX | 4.108–4.222 | 1.624–1.669 | 2.508–2.512 | 2.526 | 2.543–2.550 |
| 32 | tiny-normal | down | clean | 5.936–6.050 | 1.631–1.670 | 3.601–3.613 | 3.647–3.678 | 3.710–3.716 |
| 32 | tiny-normal | down | UF/IX | 5.808–5.862 | 1.585–1.629 | 3.555–3.599 | 3.602–3.659 | 3.671–3.697 |
| 32 | tiny-normal | up | clean | 3.278–3.738 | 1.440–1.674 | 2.204–2.216 | 2.234 | 2.253–2.320 |
| 32 | tiny-normal | up | UF/IX | 3.548–3.560 | 1.588–1.596 | 2.212–2.220 | 2.233–2.234 | 2.249–2.260 |
| 32 | tiny-normal | zero | clean | 3.438–3.815 | 1.513–1.675 | 2.259–2.264 | 2.277 | 2.286 |
| 32 | tiny-normal | zero | UF/IX | 3.617–3.819 | 1.588–1.679 | 2.259–2.271 | 2.278–2.280 | 2.288–2.420 |
| 32 | subnormal | nearest | clean | 4.114–4.221 | 1.631–1.672 | 2.506–2.509 | 2.521–2.523 | 2.531–2.539 |
| 32 | subnormal | nearest | UF/IX | 4.110–4.111 | 1.630 | 2.510–2.511 | 2.520–2.522 | 2.529–2.533 |
| 32 | subnormal | down | clean | 5.906–5.913 | 1.625–1.633 | 3.540–3.604 | 3.615–3.647 | 3.704–3.798 |
| 32 | subnormal | down | UF/IX | 5.630–5.859 | 1.579–1.613 | 3.542–3.598 | 3.612–3.644 | 3.648–4.033 |
| 32 | subnormal | up | clean | 3.542–3.614 | 1.585–1.614 | 2.225–2.228 | 2.235 | 2.243–2.258 |
| 32 | subnormal | up | UF/IX | 3.542–3.549 | 1.586–1.592 | 2.218–2.222 | 2.232 | 2.244–2.249 |
| 32 | subnormal | zero | clean | 3.611–3.712 | 1.586–1.632 | 2.263–2.265 | 2.274–2.277 | 2.288–2.300 |
| 32 | subnormal | zero | UF/IX | 3.523–3.524 | 1.547 | 2.269 | 2.278–2.280 | 2.288–2.290 |
| 32 | large-integral | nearest | clean | 2.381–2.449 | 1.586–1.631 | 1.493–1.496 | 1.501–1.503 | 1.506–1.528 |
| 32 | large-integral | nearest | UF/IX | 2.323–2.382 | 1.546–1.584 | 1.496–1.499 | 1.503–1.504 | 1.509–1.511 |
| 32 | large-integral | down | clean | 2.448 | 1.629 | 1.494–1.497 | 1.502–1.503 | 1.509–1.512 |
| 32 | large-integral | down | UF/IX | 2.380–2.384 | 1.586–1.589 | 1.494–1.497 | 1.498–1.503 | 1.503–1.509 |
| 32 | large-integral | up | clean | 2.381–2.451 | 1.586–1.635 | 1.489–1.495 | 1.500–1.502 | 1.505–1.543 |
| 32 | large-integral | up | UF/IX | 2.378–2.448 | 1.581–1.632 | 1.494–1.497 | 1.500–1.501 | 1.507–1.509 |
| 32 | large-integral | zero | clean | 2.349–2.446 | 1.560–1.631 | 1.491–1.494 | 1.500–1.503 | 1.506–1.519 |
| 32 | large-integral | zero | UF/IX | 2.383–2.385 | 1.589 | 1.493–1.496 | 1.500–1.501 | 1.507 |
| 32 | signed-zero | nearest | clean | 2.173–2.230 | 1.629–1.673 | 1.325–1.328 | 1.333–1.334 | 1.342–1.359 |
| 32 | signed-zero | nearest | UF/IX | 2.117–2.174 | 1.587–1.630 | 1.327–1.329 | 1.334 | 1.340–1.341 |
| 32 | signed-zero | down | clean | 2.119–2.130 | 1.587–1.597 | 1.323–1.325 | 1.334–1.336 | 1.360–1.423 |
| 32 | signed-zero | down | UF/IX | 2.117–2.118 | 1.585–1.591 | 1.328–1.330 | 1.333–1.336 | 1.340 |
| 32 | signed-zero | up | clean | 2.117–2.175 | 1.592–1.633 | 1.321–1.328 | 1.331–1.334 | 1.344–1.405 |
| 32 | signed-zero | up | UF/IX | 2.117–2.118 | 1.584–1.587 | 1.327–1.331 | 1.334–1.336 | 1.340–1.341 |
| 32 | signed-zero | zero | clean | 2.116–2.121 | 1.587–1.589 | 1.324–1.328 | 1.333–1.336 | 1.339–1.346 |
| 32 | signed-zero | zero | UF/IX | 2.115–2.178 | 1.588–1.635 | 1.328–1.329 | 1.332–1.334 | 1.338–1.339 |
| 32 | infinity | nearest | clean | 2.448–2.518 | 1.629–1.674 | 1.496–1.499 | 1.503–1.504 | 1.510–1.513 |
| 32 | infinity | nearest | UF/IX | 2.382–4.796 | 1.585–1.602 | 1.497–1.501 | 1.503–2.999 | 1.509–3.079 |
| 32 | infinity | down | clean | 2.383–2.720 | 1.563–1.587 | 1.496–1.498 | 1.502–1.517 | 1.514–3.057 |
| 32 | infinity | down | UF/IX | 2.322–2.381 | 1.546–1.587 | 1.495–1.496 | 1.500–1.502 | 1.507–1.508 |
| 32 | infinity | up | clean | 2.335–2.387 | 1.550–1.590 | 1.492–1.495 | 1.501–1.502 | 1.512–1.518 |
| 32 | infinity | up | UF/IX | 2.324–2.516 | 1.546–1.676 | 1.495–1.498 | 1.501–1.503 | 1.508–1.509 |
| 32 | infinity | zero | clean | 2.389–2.451 | 1.592–1.631 | 1.493–1.496 | 1.502–1.503 | 1.516 |
| 32 | infinity | zero | UF/IX | 2.378–2.385 | 1.581–1.586 | 1.495–1.499 | 1.502–1.503 | 1.508–1.509 |
| 32 | qNaN | nearest | clean | 2.321–2.322 | 1.548–1.551 | 1.485–1.492 | 1.498–1.500 | 1.503–1.523 |
| 32 | qNaN | nearest | UF/IX | 2.321–2.441 | 1.548–1.628 | 1.491–1.494 | 1.500–1.501 | 1.506–1.509 |
| 32 | qNaN | down | clean | 2.321–2.446 | 1.550–1.630 | 1.493–1.494 | 1.498–1.500 | 1.502–1.507 |
| 32 | qNaN | down | UF/IX | 2.380 | 1.587 | 1.493–1.495 | 1.500 | 1.505–1.509 |
| 32 | qNaN | up | clean | 2.379–2.384 | 1.587–1.590 | 1.488–1.494 | 1.499–1.500 | 1.504–1.537 |
| 32 | qNaN | up | UF/IX | 2.322–2.380 | 1.550–1.587 | 1.492–1.495 | 1.500 | 1.506–1.507 |
| 32 | qNaN | zero | clean | 2.381–2.382 | 1.588 | 1.492–1.494 | 1.500–1.501 | 1.506–1.522 |
| 32 | qNaN | zero | UF/IX | 2.336–2.377 | 1.560–1.585 | 1.486–1.491 | 1.499–1.501 | 1.506–1.519 |
| 32 | sNaN | nearest | clean | 2.392–2.439 | 1.591–1.627 | 1.490–1.494 | 1.498–1.501 | 1.503–1.521 |
| 32 | sNaN | nearest | UF/IX | 2.382–2.511 | 1.589–1.676 | 1.492–1.494 | 1.499–1.500 | 1.507–1.510 |
| 32 | sNaN | down | clean | 2.444–2.502 | 1.630–1.660 | 1.487–1.494 | 1.499–1.500 | 1.505–1.528 |
| 32 | sNaN | down | UF/IX | 2.381–2.382 | 1.589 | 1.491–1.494 | 1.498–1.499 | 1.505–1.508 |
| 32 | sNaN | up | clean | 2.508–2.514 | 1.672–1.677 | 1.486–1.491 | 1.498–1.499 | 1.505–1.767 |
| 32 | sNaN | up | UF/IX | 2.379–2.508 | 1.587–1.669 | 1.491–1.495 | 1.500–1.502 | 1.507–1.509 |
| 32 | sNaN | zero | clean | 2.389–2.514 | 1.592–1.675 | 1.488–1.490 | 1.501 | 1.511–1.514 |
| 32 | sNaN | zero | UF/IX | 2.383–2.468 | 1.588–1.648 | 1.488–1.496 | 1.499–1.501 | 1.505–1.514 |

### GCC16 compiler/runtime context

| Bits | Range | Mode | Entry | Own ns | Host ns | Ratio p10 | Ratio median | Ratio p90 |
|---|---|---|---|---:|---:|---:|---:|---:|
| 64 | normal | nearest | clean | 6.890–11.034 | 2.083–2.750 | 3.235–3.825 | 3.295–3.985 | 3.365–4.260 |
| 64 | normal | nearest | UF/IX | 6.937–10.783 | 2.112–2.703 | 3.219–3.770 | 3.282–3.984 | 3.427–4.234 |
| 64 | normal | down | clean | 5.902–9.276 | 2.133–2.778 | 2.664–3.158 | 2.752–3.337 | 2.854–3.581 |
| 64 | normal | down | UF/IX | 5.588–9.192 | 2.170–2.759 | 2.552–3.113 | 2.580–3.312 | 2.608–3.608 |
| 64 | normal | up | clean | 5.363–8.608 | 2.174–2.759 | 2.435–2.915 | 2.466–3.103 | 2.518–3.402 |
| 64 | normal | up | UF/IX | 5.289–8.662 | 2.174–2.737 | 2.408–2.920 | 2.433–3.145 | 2.497–3.418 |
| 64 | normal | zero | clean | 4.786–7.551 | 2.115–2.800 | 2.238–2.525 | 2.262–2.691 | 2.366–2.835 |
| 64 | normal | zero | UF/IX | 4.750–7.481 | 2.113–2.764 | 2.226–2.535 | 2.251–2.688 | 2.300–2.807 |
| 64 | half-ties | nearest | clean | 4.889–7.823 | 2.117–2.776 | 2.291–2.699 | 2.311–2.822 | 2.331–2.966 |
| 64 | half-ties | nearest | UF/IX | 4.758–7.646 | 2.058–2.698 | 2.298–2.664 | 2.312–2.801 | 2.324–2.951 |
| 64 | half-ties | down | clean | 5.886–9.097 | 2.170–2.732 | 2.689–3.111 | 2.725–3.309 | 2.778–3.522 |
| 64 | half-ties | down | UF/IX | 5.536–5.910 | 2.110–2.229 | 2.616–2.647 | 2.650–2.678 | 2.686–3.250 |
| 64 | half-ties | up | clean | 5.842–5.872 | 2.106–2.112 | 2.700–2.740 | 2.768–2.836 | 2.800–2.904 |
| 64 | half-ties | up | UF/IX | 5.603–5.667 | 2.055–2.085 | 2.690–2.703 | 2.721–2.726 | 2.765–2.772 |
| 64 | half-ties | zero | clean | 4.331–4.447 | 2.112–2.174 | 2.019–2.038 | 2.047–2.049 | 2.061–2.187 |
| 64 | half-ties | zero | UF/IX | 4.216–4.232 | 2.059–2.069 | 2.025–2.035 | 2.043–2.048 | 2.061–2.063 |
| 64 | tiny-normal | nearest | clean | 3.914–4.186 | 2.060–2.220 | 1.867–1.881 | 1.892–1.894 | 1.916–1.919 |
| 64 | tiny-normal | nearest | UF/IX | 3.800–3.966 | 2.011–2.093 | 1.858–1.880 | 1.891–1.893 | 1.901–1.941 |
| 64 | tiny-normal | down | clean | 5.487–5.755 | 2.033–2.115 | 2.671–2.681 | 2.705–2.729 | 2.737–2.822 |
| 64 | tiny-normal | down | UF/IX | 5.563–5.900 | 2.060–2.169 | 2.665–2.685 | 2.698–2.727 | 2.778–3.043 |
| 64 | tiny-normal | up | clean | 3.465–3.850 | 2.063–2.291 | 1.664–1.669 | 1.680–1.681 | 1.691–1.693 |
| 64 | tiny-normal | up | UF/IX | 3.455–3.557 | 2.059–2.120 | 1.660–1.671 | 1.678–1.680 | 1.691–1.715 |
| 64 | tiny-normal | zero | clean | 3.624–3.626 | 2.116–2.119 | 1.694–1.705 | 1.713–1.714 | 1.722–1.847 |
| 64 | tiny-normal | zero | UF/IX | 3.524–3.530 | 2.062–2.063 | 1.690–1.703 | 1.711–1.712 | 1.723–1.729 |
| 64 | subnormal | nearest | clean | 4.000–4.099 | 2.116–2.158 | 1.869–1.875 | 1.891 | 1.907–1.932 |
| 64 | subnormal | nearest | UF/IX | 3.900–4.223 | 2.064–2.235 | 1.869–1.884 | 1.891–1.892 | 1.900–1.926 |
| 64 | subnormal | down | clean | 6.049–6.194 | 2.171–2.234 | 2.735–2.764 | 2.769–2.791 | 2.831–2.850 |
| 64 | subnormal | down | UF/IX | 5.648–5.854 | 2.042–2.114 | 2.718–2.741 | 2.758–2.767 | 2.807–2.822 |
| 64 | subnormal | up | clean | 3.569–3.643 | 2.117–2.170 | 1.668–1.674 | 1.679–1.683 | 1.688–1.693 |
| 64 | subnormal | up | UF/IX | 3.457–3.552 | 2.053–2.117 | 1.662–1.669 | 1.678–1.682 | 1.694–1.699 |
| 64 | subnormal | zero | clean | 3.620–3.624 | 2.113–2.115 | 1.694–1.704 | 1.714 | 1.728–1.735 |
| 64 | subnormal | zero | UF/IX | 3.465–3.533 | 2.017–2.065 | 1.701–1.705 | 1.711–1.713 | 1.722–1.727 |
| 64 | large-integral | nearest | clean | 2.382–2.507 | 2.114–2.222 | 1.114–1.121 | 1.126–1.127 | 1.139–1.150 |
| 64 | large-integral | nearest | UF/IX | 2.381–2.515 | 2.114–2.235 | 1.114–1.119 | 1.126–1.128 | 1.142–1.161 |
| 64 | large-integral | down | clean | 2.380–2.387 | 2.114–2.119 | 1.118–1.122 | 1.125–1.126 | 1.134–1.136 |
| 64 | large-integral | down | UF/IX | 2.323–2.379 | 2.066–2.112 | 1.113–1.119 | 1.126–1.127 | 1.189–1.243 |
| 64 | large-integral | up | clean | 2.324–2.383 | 2.064–2.120 | 1.119–1.123 | 1.125–1.126 | 1.133 |
| 64 | large-integral | up | UF/IX | 2.394–2.447 | 2.119–2.174 | 1.112–1.121 | 1.126–1.127 | 1.149 |
| 64 | large-integral | zero | clean | 2.323–2.380 | 2.064–2.114 | 1.119–1.121 | 1.125–1.126 | 1.135–1.138 |
| 64 | large-integral | zero | UF/IX | 2.321–2.415 | 2.064–2.126 | 1.116–1.118 | 1.124–1.126 | 1.131–1.295 |
| 64 | signed-zero | nearest | clean | 2.373–2.576 | 2.115–2.296 | 0.998–0.999 | 1.118–1.120 | 1.127–1.133 |
| 64 | signed-zero | nearest | UF/IX | 2.312–2.372 | 2.061–2.117 | 0.998 | 1.085–1.120 | 1.129 |
| 64 | signed-zero | down | clean | 2.373–2.504 | 2.116–2.232 | 0.998 | 1.117–1.121 | 1.128–1.261 |
| 64 | signed-zero | down | UF/IX | 2.312–2.319 | 2.062–2.112 | 0.997–1.111 | 1.110–1.125 | 1.128–1.134 |
| 64 | signed-zero | up | clean | 2.247–2.315 | 2.065–2.288 | 0.996–0.997 | 1.074–1.114 | 1.133–1.138 |
| 64 | signed-zero | up | UF/IX | 2.255–2.505 | 2.067–2.229 | 0.997–0.998 | 1.068–1.122 | 1.129–1.133 |
| 64 | signed-zero | zero | clean | 2.288–2.511 | 2.119–2.236 | 0.997–1.015 | 1.071–1.125 | 1.127–1.133 |
| 64 | signed-zero | zero | UF/IX | 2.259–2.261 | 2.061–2.107 | 0.997–0.999 | 1.114–1.124 | 1.129–1.130 |
| 64 | infinity | nearest | clean | 2.286–2.338 | 2.033–2.073 | 1.117–1.120 | 1.126–1.127 | 1.136–1.143 |
| 64 | infinity | nearest | UF/IX | 2.319–2.513 | 2.060–2.230 | 1.121–1.122 | 1.126–1.127 | 1.131–1.134 |
| 64 | infinity | down | clean | 2.349–2.516 | 2.080–2.237 | 1.115 | 1.125 | 1.142–1.147 |
| 64 | infinity | down | UF/IX | 2.323 | 2.064–2.066 | 1.119–1.122 | 1.125–1.126 | 1.132–1.133 |
| 64 | infinity | up | clean | 2.265–2.379 | 2.012–2.114 | 1.105–1.117 | 1.126 | 1.135–1.162 |
| 64 | infinity | up | UF/IX | 2.258–2.322 | 2.006–2.064 | 1.110–1.119 | 1.125–1.126 | 1.134–1.155 |
| 64 | infinity | zero | clean | 2.151–2.415 | 1.911–2.127 | 1.100–1.117 | 1.125–1.127 | 1.145–1.149 |
| 64 | infinity | zero | UF/IX | 2.330–2.448 | 2.071–2.177 | 1.110–1.119 | 1.125–1.127 | 1.137–1.302 |
| 64 | qNaN | nearest | clean | 2.440–2.639 | 1.960–2.114 | 1.128–1.240 | 1.249 | 1.257–1.327 |
| 64 | qNaN | nearest | UF/IX | 2.572–2.643 | 2.113–2.117 | 1.123–1.124 | 1.240–1.248 | 1.252–1.371 |
| 64 | qNaN | down | clean | 2.571–2.711 | 2.056–2.173 | 1.129–1.234 | 1.247–1.249 | 1.254–1.262 |
| 64 | qNaN | down | UF/IX | 2.568–2.637 | 2.062–2.116 | 1.121–1.123 | 1.226–1.240 | 1.255–1.261 |
| 64 | qNaN | up | clean | 2.639–2.713 | 2.113–2.173 | 1.133–1.241 | 1.248–1.249 | 1.258–1.259 |
| 64 | qNaN | up | UF/IX | 2.505–2.640 | 2.013–2.163 | 1.121–1.122 | 1.242–1.243 | 1.255–1.258 |
| 64 | qNaN | zero | clean | 2.576–2.577 | 2.062–2.071 | 1.214–1.229 | 1.248–1.251 | 1.254–1.273 |
| 64 | qNaN | zero | UF/IX | 2.571–2.636 | 2.079–2.115 | 1.121–1.122 | 1.238–1.241 | 1.255–1.256 |
| 64 | sNaN | nearest | clean | 2.413–2.425 | 2.172–2.174 | 1.106 | 1.112–1.114 | 1.125–1.126 |
| 64 | sNaN | nearest | UF/IX | 2.359–2.382 | 2.113–2.122 | 1.107–1.109 | 1.119–1.122 | 1.129–1.133 |
| 64 | sNaN | down | clean | 2.353–4.771 | 2.114–2.620 | 1.107–1.117 | 1.113–1.804 | 1.126–1.968 |
| 64 | sNaN | down | UF/IX | 2.348–2.595 | 2.113–2.307 | 1.106–1.109 | 1.116–1.128 | 1.133–1.851 |
| 64 | sNaN | up | clean | 2.352–3.380 | 2.114–2.438 | 1.108 | 1.113–1.395 | 1.119–1.899 |
| 64 | sNaN | up | UF/IX | 2.314–2.624 | 2.065–2.359 | 1.100–1.108 | 1.113–1.125 | 1.137–1.829 |
| 64 | sNaN | zero | clean | 2.418–2.554 | 2.173–2.296 | 1.100–1.107 | 1.113–1.114 | 1.133–1.188 |
| 64 | sNaN | zero | UF/IX | 2.346–2.514 | 2.112–2.236 | 1.107–1.108 | 1.113–1.122 | 1.127–1.138 |
| 32 | normal | nearest | clean | 6.950–7.272 | 2.109–2.229 | 3.213–3.273 | 3.248–3.317 | 3.305–3.423 |
| 32 | normal | nearest | UF/IX | 6.878–7.249 | 2.112–2.230 | 3.210–3.218 | 3.240–3.260 | 3.283–3.312 |
| 32 | normal | down | clean | 5.314–5.804 | 2.059–2.231 | 2.536–2.564 | 2.578–2.603 | 2.647–2.696 |
| 32 | normal | down | UF/IX | 5.392–5.572 | 2.166–2.227 | 2.437–2.492 | 2.488–2.512 | 2.544–2.565 |
| 32 | normal | up | clean | 5.233–5.250 | 2.170–2.234 | 2.289–2.392 | 2.302–2.418 | 2.467–2.481 |
| 32 | normal | up | UF/IX | 4.906–5.075 | 2.062–2.213 | 2.272–2.357 | 2.298–2.377 | 2.333–2.399 |
| 32 | normal | zero | clean | 4.870–5.007 | 2.167–2.232 | 2.228–2.235 | 2.242–2.247 | 2.259–2.269 |
| 32 | normal | zero | UF/IX | 4.627–4.987 | 2.061–2.230 | 2.226–2.231 | 2.240–2.244 | 2.268–2.284 |
| 32 | half-ties | nearest | clean | 4.879–5.013 | 2.114–2.175 | 2.294–2.299 | 2.309–2.310 | 2.337–2.351 |
| 32 | half-ties | nearest | UF/IX | 4.775–5.028 | 2.074–2.176 | 2.301 | 2.310–2.313 | 2.320–2.328 |
| 32 | half-ties | down | clean | 6.132–6.269 | 2.182–2.254 | 2.732–2.753 | 2.759–2.784 | 2.794–2.824 |
| 32 | half-ties | down | UF/IX | 5.802–5.884 | 2.114–2.170 | 2.689–2.728 | 2.715–2.747 | 2.735–2.795 |
| 32 | half-ties | up | clean | 5.668–5.751 | 2.066–2.115 | 2.685–2.699 | 2.715–2.733 | 2.758–2.890 |
| 32 | half-ties | up | UF/IX | 5.629–5.633 | 2.064–2.065 | 2.675–2.688 | 2.704–2.717 | 2.749–2.752 |
| 32 | half-ties | zero | clean | 4.310–4.314 | 2.115 | 2.028–2.030 | 2.039–2.041 | 2.054–2.060 |
| 32 | half-ties | zero | UF/IX | 4.190–4.309 | 2.054–2.112 | 2.026–2.030 | 2.041–2.042 | 2.057–2.075 |
| 32 | tiny-normal | nearest | clean | 3.999–4.001 | 2.114–2.115 | 1.886 | 1.892 | 1.897 |
| 32 | tiny-normal | nearest | UF/IX | 3.819–4.002 | 2.015–2.117 | 1.878–1.880 | 1.892 | 1.909–1.911 |
| 32 | tiny-normal | down | clean | 5.898–5.940 | 2.114–2.169 | 2.719–2.748 | 2.758–2.788 | 2.813–2.864 |
| 32 | tiny-normal | down | UF/IX | 5.633–5.761 | 2.061–2.076 | 2.647–2.744 | 2.717–2.791 | 2.801–2.835 |
| 32 | tiny-normal | up | clean | 3.482–3.544 | 2.071–2.112 | 1.672 | 1.678 | 1.685 |
| 32 | tiny-normal | up | UF/IX | 3.458–3.468 | 2.057–2.060 | 1.669–1.672 | 1.681–1.682 | 1.690–1.695 |
| 32 | tiny-normal | zero | clean | 3.530–3.616 | 2.061–2.110 | 1.703–1.704 | 1.712–1.713 | 1.720–1.723 |
| 32 | tiny-normal | zero | UF/IX | 3.526–3.556 | 2.059–2.089 | 1.707 | 1.712–1.715 | 1.718–1.723 |
| 32 | subnormal | nearest | clean | 3.998–4.000 | 2.114–2.115 | 1.881 | 1.891–1.892 | 1.903–1.906 |
| 32 | subnormal | nearest | UF/IX | 3.897–3.949 | 2.058–2.082 | 1.874–1.881 | 1.893–1.895 | 1.909–2.055 |
| 32 | subnormal | down | clean | 5.923–6.106 | 2.135–2.234 | 2.639–2.705 | 2.733–2.749 | 2.797–2.872 |
| 32 | subnormal | down | UF/IX | 5.849–6.264 | 2.173–2.292 | 2.642–2.709 | 2.696–2.745 | 2.757–2.800 |
| 32 | subnormal | up | clean | 3.540–3.552 | 2.111–2.114 | 1.672–1.673 | 1.678–1.680 | 1.685–1.688 |
| 32 | subnormal | up | UF/IX | 3.484–3.743 | 2.078–2.231 | 1.669–1.672 | 1.677–1.681 | 1.690–1.692 |
| 32 | subnormal | zero | clean | 3.715–3.928 | 2.167–2.291 | 1.702–1.706 | 1.713 | 1.724–1.727 |
| 32 | subnormal | zero | UF/IX | 3.531–3.623 | 2.064–2.117 | 1.706 | 1.711–1.712 | 1.717–1.718 |
| 32 | large-integral | nearest | clean | 2.325–2.445 | 2.064–2.169 | 1.119–1.121 | 1.127–1.128 | 1.140–1.148 |
| 32 | large-integral | nearest | UF/IX | 2.443–2.448 | 2.166–2.171 | 1.122–1.123 | 1.127 | 1.131–1.133 |
| 32 | large-integral | down | clean | 2.445–2.448 | 2.169–2.172 | 1.119–1.124 | 1.127 | 1.131–1.135 |
| 32 | large-integral | down | UF/IX | 2.319–2.449 | 2.059–2.174 | 1.121–1.123 | 1.127 | 1.135 |
| 32 | large-integral | up | clean | 2.323–2.511 | 2.061–2.229 | 1.118–1.124 | 1.127 | 1.131–1.137 |
| 32 | large-integral | up | UF/IX | 2.266–2.544 | 2.012–2.238 | 1.121–1.124 | 1.127–1.128 | 1.136–1.138 |
| 32 | large-integral | zero | clean | 2.381–2.382 | 2.112–2.113 | 1.122 | 1.127 | 1.135 |
| 32 | large-integral | zero | UF/IX | 2.265–2.326 | 2.010–2.063 | 1.116–1.123 | 1.127–1.128 | 1.138–1.145 |
| 32 | signed-zero | nearest | clean | 2.115–2.235 | 2.115–2.234 | 0.994–0.997 | 1.000 | 1.003–1.009 |
| 32 | signed-zero | nearest | UF/IX | 2.011–2.115 | 2.010–2.117 | 0.938–0.968 | 0.998–1.001 | 1.010–1.097 |
| 32 | signed-zero | down | clean | 2.025–2.116 | 2.018–2.116 | 0.940–0.997 | 0.999–1.000 | 1.003–1.007 |
| 32 | signed-zero | down | UF/IX | 2.015–2.114 | 2.014–2.114 | 0.939–0.996 | 1.000–1.001 | 1.021–1.061 |
| 32 | signed-zero | up | clean | 2.063–2.115 | 2.062–2.114 | 0.997 | 1.000–1.001 | 1.004–1.005 |
| 32 | signed-zero | up | UF/IX | 1.962–2.063 | 1.959–2.080 | 0.939–0.995 | 1.000–1.001 | 1.012–1.152 |
| 32 | signed-zero | zero | clean | 2.111–2.173 | 2.111–2.172 | 0.995–0.996 | 1.000 | 1.003–1.004 |
| 32 | signed-zero | zero | UF/IX | 2.083–2.116 | 2.066–2.136 | 0.939–0.996 | 1.000–1.001 | 1.037–1.105 |
| 32 | infinity | nearest | clean | 2.385 | 2.115–2.118 | 1.123 | 1.126–1.127 | 1.132 |
| 32 | infinity | nearest | UF/IX | 2.267–2.449 | 2.013–2.174 | 1.116–1.119 | 1.128 | 1.201–1.236 |
| 32 | infinity | down | clean | 2.378–2.513 | 2.110–2.231 | 1.119–1.124 | 1.127 | 1.130–1.138 |
| 32 | infinity | down | UF/IX | 2.319–2.447 | 2.055–2.170 | 1.121–1.123 | 1.128–1.129 | 1.133–1.295 |
| 32 | infinity | up | clean | 2.381–2.515 | 2.112–2.232 | 1.122–1.124 | 1.127 | 1.131–1.211 |
| 32 | infinity | up | UF/IX | 2.260–2.264 | 2.005–2.006 | 1.122–1.125 | 1.127–1.128 | 1.132–1.142 |
| 32 | infinity | zero | clean | 2.323–2.444 | 2.062–2.167 | 1.121–1.123 | 1.127–1.128 | 1.132–1.138 |
| 32 | infinity | zero | UF/IX | 2.316–2.322 | 2.054–2.060 | 1.123 | 1.126–1.127 | 1.132–1.133 |
| 32 | qNaN | nearest | clean | 2.302–2.375 | 2.061–2.110 | 1.112–1.118 | 1.117–1.125 | 1.133–1.201 |
| 32 | qNaN | nearest | UF/IX | 2.300–2.334 | 2.059–2.070 | 1.112–1.118 | 1.118–1.126 | 1.126–1.133 |
| 32 | qNaN | down | clean | 2.306–2.440 | 2.063–2.174 | 1.108–1.112 | 1.119–1.122 | 1.138–1.300 |
| 32 | qNaN | down | UF/IX | 2.318–2.375 | 2.063–2.112 | 1.114–1.115 | 1.120–1.124 | 1.127–1.130 |
| 32 | qNaN | up | clean | 2.314–2.366 | 2.062–2.111 | 1.111–1.112 | 1.123 | 1.128–1.304 |
| 32 | qNaN | up | UF/IX | 2.321–2.382 | 2.063–2.119 | 1.113 | 1.122–1.124 | 1.130 |
| 32 | qNaN | zero | clean | 2.359–2.515 | 2.111–2.245 | 1.112 | 1.121–1.124 | 1.130–1.354 |
| 32 | qNaN | zero | UF/IX | 2.319–2.434 | 2.064–2.172 | 1.112–1.114 | 1.119–1.122 | 1.126–1.131 |
| 32 | sNaN | nearest | clean | 2.347–2.413 | 2.111–2.167 | 1.108 | 1.112–1.114 | 1.119–1.331 |
| 32 | sNaN | nearest | UF/IX | 2.291–2.481 | 2.063–2.231 | 1.104–1.105 | 1.111–1.115 | 1.122–1.509 |
| 32 | sNaN | down | clean | 2.413–2.485 | 2.173–2.234 | 1.106–1.107 | 1.111–1.113 | 1.115–1.158 |
| 32 | sNaN | down | UF/IX | 2.351–2.478 | 2.115–2.226 | 1.100–1.105 | 1.112–1.114 | 1.121–1.330 |
| 32 | sNaN | up | clean | 2.293–2.482 | 2.062–2.231 | 1.106–1.108 | 1.112–1.113 | 1.119–1.124 |
| 32 | sNaN | up | UF/IX | 2.356–2.403 | 2.119–2.126 | 1.104–1.108 | 1.112–1.113 | 1.122–1.135 |
| 32 | sNaN | zero | clean | 2.293–2.480 | 2.063–2.232 | 1.105–1.107 | 1.112–1.113 | 1.116–1.220 |
| 32 | sNaN | zero | UF/IX | 2.291–2.480 | 2.060–2.228 | 1.107–1.110 | 1.112–1.113 | 1.118–1.121 |
