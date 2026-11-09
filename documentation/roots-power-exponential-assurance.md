# Roots, power and exponential assurance

This follow-up starts from revision `3a0c800b4c137027c76505c42a4623eb55189bb0`
and audits 21 already verified entry points. Existing implementation,
reference, proof, compiler, sanitizer and ABI evidence remains applicable within
its original source and target scope. Fourteen entry points need no new focused
checks; seven receive bounded caller-state or verifier checks. The historical
[verification ledger](libm-progress.md) remains unchanged.

| Operation | Float | Double | Long double |
| --- | --- | --- | --- |
| `sqrt` | Reuse basic-operation references, exact rounding and special/state tests | Reuse exact root, special-value and state evidence | Reuse exact midpoint certificates, literal cells and native ABI evidence |
| `cbrt` | Reuse certified references, exact cases and force-flag checks | Reuse certified references, exact cases and state/defect controls | Reuse exact cube certificates, literal cells and native ABI evidence |
| `hypot` | Reuse exact midpoint-square certificates and special/state tests | Reuse corpus/accuracy checks; add ordered Inf/sNaN and qNaN/sNaN pairs | Reuse exact midpoint and finite-overflow certificates, state and native ABI evidence |
| `pow` | Reuse remaining-function references and special/state tests | Reuse corpus/accuracy checks; add sNaN with both zero signs, one/sNaN and ordered qNaN/sNaN pairs | Reuse interval proof/reference cells; strengthen boundary policy and add fractional-exponent transition state checks |
| `exp` | Reuse references, special/state and force-flag checks | Reuse corpus/accuracy checks; add slow subnormal, far-range and sNaN caller-state paths | Reuse interval proof/reference cells; strengthen boundary policy and add transition state checks |
| `exp2` | Reuse references, integer-power and force-flag checks | Reuse nearest corpus and exact integer powers; add slow subnormal, far-range and sNaN caller-state paths | Reuse exact powers, literal cells, state and native ABI evidence |
| `expm1` | Reuse compensated-series references and special/state tests | Reuse compensated-series references and special/state tests | Reuse interval proof/reference cells; strengthen boundary policy and add transition state checks |

The existing [Float/Double compatibility audit](libm-compatibility-audit.md)
already exercises all 114 entry points in four modes with two flag states,
including errno, mode, incoming divide-by-zero and signgam. Its ordinary binary
arguments do not cover the paired dispatch combinations added here.

The new Double checks cover four rounding modes, supported nontrapping control
profiles and clear/combined standard exception seeds. They preserve errno,
controls, rounding mode and actual incoming flags. Paired results retain the
published identity, infinity and canonical NaN bits without adding a new invalid
exception precedence rule. Slow `exp(-740)` and `exp2(-1074.5)` calls exercise
subnormal scaling; far-range and signaling-NaN calls exercise other exits.
Slow unary fixtures also assert their documented required and allowed standard
exceptions, including underflow/inexact, overflow/inexact and signaling invalid.
Accuracy references apply to the default IEEE nearest environment with hardware
flushing disabled. Nondefault rounding, precision and flush profiles check
preservation and the stated exception policy; they make no directed-accuracy or
gradual-underflow result-bit claim. Paired dispatch bits keep their separate
special-value policy.

The long-double checker requires canonical nonexact output encodings and tests
both signed outer boundaries. A missing finite neighbor denotes the virtual
endpoint beyond the finite maximum. For double-double this endpoint is the
exact finite limit plus its actual last gap, 2^917; no fixed 106-bit relative
spacing is assumed. Finite transcendental outputs retain the actual-neighbor
one-ULP policy described in [the long-double contract](long-double.md#roots-exponentials-logarithms-and-power).

Transition states reuse the authenticated 184 supplemental cells; no reference
answer or pin changes. A bounded subset covers each exp/expm1 and base-two pow
transition's adjacent inputs. Each selected cell covers every mode/precision
and mode/flush pair, with clear flags and all five standard flags together.
Twelve paired profiles per seed avoid the full mode/precision/flush product. Required fresh flags remain
checked in unseeded calls, with actual entry masks retained for seeded calls.
Raw binary64, extended80, binary128 and double-double calls are representation
checks. Native extended80 calls separately execute the public ABI; other native
ABIs retain their previously recorded evidence and are not newly executed here.

To reproduce the public checks after installing dependencies into a private
prefix, use the existing Make targets and unit executables from the repository
root (the paths below are the default Linux release build):

```sh
prefix=/path/to/private/prefix
make -j1 build/linux/release/apps/testElementary build/linux/release/apps/testExp2 PREFIX="$prefix"
build/linux/release/apps/testElementary
build/linux/release/apps/testExp2
make -j1 check-long-double-eleven check-long-double-eleven-controls PREFIX="$prefix"
```

The two new unit cases can also be selected with
`--gtest_filter=Elementary.PairedDispatchAndSlowExpPreserveCallerState` and
`--gtest_filter=Exp2.SlowRangeAndSignalingPathsPreserveCallerState` respectively.
Both long-double targets are existing default test gates. Their state/control
results are generated under `build/linux/release/long-double-eleven-controls/`:
`transition-states.json` retains the selected rows, profile grid, counts, output
and three calibrated state faults; `boundary-policy-status.json` retains eleven
boundary-policy rejections. The authenticated supplemental reference remains
`tests/corpus/long-double-eleven.boundaries.json`; no pin or answer changes.

The latest targeted GCC 16.2.0 x86-64 checks passed 15 Elementary tests, nine
Exp2 tests and 3,240 transition calls: 648 each for raw binary64, raw extended80,
raw binary128, raw double-double and actual native extended80. The two added
Double tests execute 960 calls across three supported control profiles. This
run covers the reviewed unit/shared-fixture and transition changes only.

Earlier successful focused stages are reused for unchanged checker/runtime
paths: two long-double unit tests, 826 raw and 205 native80 pinned cells,
8,394 existing state rows, 96 exact hypot range states, 44 fresh certificate
cells and 1,485 exact primitive calibrations. Eleven public boundary-policy
controls reject noncanonical DD/infinity encodings, wrong sums and both signed
virtual outer-limit violations after good controls. These composite results
do not describe one new full-suite execution. The historical compiler,
sanitizer, independent-reference/proof and non-native ABI evidence remains
limited to its recorded source and target context.

Separate earlier private calibration used four genuine Double wrapper controls
and sixteen compiled errno/mode/flag/control defects against that fixture
version. Ten before/after witnesses showed former acceptance and strengthened
rejection of noncanonical outputs or out-of-envelope finite maxima. These
retained witnesses are supplementary evidence; their private harnesses are not
reproduced by the public default gates above. Setup/link failures remain failed
attempts and contribute no fault-detection claim.

No production violation was demonstrated. Runtime sources, public headers,
references, hashes, published numerical policies and historical verification
remain unchanged. These bounded checks do not assert exhaustive correctness or
newly executed non-native ABIs.
