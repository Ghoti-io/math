# Error and gamma assurance

`make check-error-gamma PREFIX=...` exercises `erf`, `erfc`, `tgamma`, and
`lgamma` in Float, Double and native long double. The ordinary gate uses retained,
authenticated compact references and requires no container engine. It is also
part of the default test gates.

`make check-error-gamma-oracle PREFIX=...` requires the pinned MPFR instrument.
It checks the actual runtime version, independently inverts every selected
transition, and reproduces every retained reference byte. Missing instruments,
version mismatches and reference changes fail the gate; they never trigger
host-library substitution or reference repair.

The input recipes cover signed zeros and minimum subnormals, normal boundaries,
both sides of negative integer poles with alternating reflection signs,
recurrence neighborhoods at 64 and 1024, error-function switches at 4 and 16,
and tails around 128. Error-function saturation, erfc normal/zero transitions,
and positive tgamma overflow and negative tgamma normal/zero transitions come
from directed independent inversion, rather than runtime cutoff constants.
Lgamma has its own independently inverted positive overflow neighborhood;
its input recipe uses common power-of-two scaling to keep exact bisection
inputs within the instrument precision even on extended exponent ranges.
Normal-result transition recipes invert the midpoint with the actual
predecessor, and overflow recipes include the midpoint to the virtual next
value. Nominal threshold neighborhoods are retained separately. Erf saturation
is mirrored to negative inputs, and erfc saturation near 2 is independently
evaluated. Double-double saturation near 1 uses the actual remote-tail grid
down to 2^-1074 rather than a fixed 106-bit relative spacing.
Additional lgamma root neighbors use the authenticated root registry, selecting
both roots in intervals indexed by 4, 5, 7, 16, 32, 64 and 128. Representable
integer poles encountered while rounding a root bracket remain poles and are
excluded from its finite root-neighbor population. Positive lgamma cancellation
includes neighbors of 1 and 2. Double-double cases also retain remote low tails
of both signs around 1, 2 and negative poles.

The oracle uses MPFR 4.2.2 with gmpy2 2.3.2, mpmath 1.4.1 and Python 3.14.7.
Directed MPFR calculations use 4096 bits; independent mpmath cross-checks start
at 8192 bits and refine when needed. Compact outward enclosures retain 2304
bits. Logarithmic transition comparisons subtract opposite enclosure endpoints;
all projected input values are exact dyadics. Mathematical identities, domain
cases and pole cases use their exact specified answers. Finite seam answers
are calculated by the independent instrument. Far positive tgamma cases use
monotonicity and an exact factorial lower bound to establish overflow without
constructing enormous gamma values. For huge negative double-double inputs,
reflection and the minimum input lattice bound the tiny magnitude while
retaining its parity sign.

The raw long-double adapters exercise binary64, extended80, binary128 and
106-bit double-double layouts. These are four representation populations,
not four native ABIs. A separate production object and integer byte caller
exercise the actual native public functions without narrowing through Double.
Float and Double calls use their public entry points. State checks cover all
four rounding modes, all five incoming standard flag classes, supported
DAZ/FTZ profiles, errno, floating controls, and signgam where exposed. Ordinary
outputs must stay bitwise invariant across the tested states; exact specials
and result-boundary exception identities remain exact.

Numerical acceptance retains the published one-result/local-ULP scope. It
compares independent enclosures with the actual adjacent representable values,
including the varying double-double spacing. It neither requires equality to
host libm nor upgrades the contract to universal correct rounding. Rejecting
controls follow successful genuine calls and separately reject wrong values,
flags, controls, references and omitted populations. A compiled erfc cutoff
defect must fail its intended numerical assertion; compilation failures,
crashes, setup failures and timeouts do not count as detection.

## Measured population

A GCC 16.2.0 x86-64 run executed 1471 retained recipe rows, 245 additional native80 public calls and 6116 caller-state rows. All passed. All 20 rejecting controls each reached their intended assertion after a successful genuine control. No production violation was demonstrated; no historical answer or runtime implementation changed.

The committed payload SHA256 is `4b2830f68a3b59be5c42defe6ad40f9176eb51979137e1a4e2bc79eb03497353`. Required pinned regeneration reproduced it exactly. Four raw layouts and one actual native ABI were exercised.

Reference classes: 9 edge, 320 exact-special, 6 far-overflow-proof, 1065 finite, 69 overflow, 2 tiny-range-proof. Ordinary finite errors below exclude exact specials and range-proof cases.

| Population | erf rows | erfc rows | tgamma rows | lgamma rows |
| --- | ---: | ---: | ---: | ---: |
| Float binary32 | 44 | 53 | 73 | 69 |
| Double binary64 | 44 | 53 | 73 | 71 |
| raw long-double binary64 | 44 | 53 | 73 | 71 |
| raw extended80 | 45 | 54 | 74 | 72 |
| raw binary128 | 44 | 53 | 73 | 71 |
| raw double-double | 51 | 54 | 76 | 83 |

Seam recipes retain their declared region identifiers; coincident nominal and rounded seams intentionally repeat the same encoding under separate tags. Other recipes remove duplicate operation/input encodings. Region tags distinguish input populations, while every output enclosure is independently regenerated.

| Region | Float32 | Double64 | raw64 | raw80 | raw128 | DD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| erf-dd-saturation | 0 | 0 | 0 | 0 | 0 | 6 |
| erf-saturation | 9 | 9 | 9 | 9 | 9 | 9 |
| erfc-negative-saturation | 3 | 3 | 3 | 3 | 3 | 3 |
| erfc-normal | 3 | 3 | 3 | 3 | 3 | 3 |
| erfc-rounded-normal | 3 | 3 | 3 | 3 | 3 | 3 |
| erfc-zero | 3 | 3 | 3 | 3 | 3 | 3 |
| gamma-normal | 6 | 6 | 6 | 6 | 6 | 6 |
| gamma-overflow | 3 | 3 | 3 | 3 | 3 | 3 |
| gamma-rounded-normal | 6 | 6 | 6 | 6 | 6 | 6 |
| gamma-rounded-overflow | 3 | 3 | 3 | 3 | 3 | 3 |
| gamma-zero | 6 | 6 | 6 | 6 | 6 | 6 |
| huge-negative-remote | 0 | 0 | 0 | 0 | 0 | 4 |
| huge-positive-range | 2 | 2 | 2 | 2 | 2 | 2 |
| infinity | 8 | 8 | 8 | 8 | 8 | 8 |
| input-normal | 12 | 12 | 12 | 12 | 12 | 12 |
| lgamma-rounded-overflow | 3 | 3 | 3 | 3 | 3 | 3 |
| malformed | 0 | 0 | 0 | 4 | 0 | 4 |
| minimum-subnormal | 4 | 4 | 4 | 4 | 4 | 4 |
| negative-minimum-subnormal | 4 | 4 | 4 | 4 | 4 | 4 |
| negative-root | 17 | 19 | 19 | 19 | 19 | 28 |
| negative-zero | 4 | 4 | 4 | 4 | 4 | 4 |
| one | 4 | 4 | 4 | 4 | 4 | 4 |
| ordinary | 4 | 4 | 4 | 4 | 4 | 4 |
| pole | 48 | 48 | 48 | 48 | 48 | 48 |
| quiet-nan | 8 | 8 | 8 | 8 | 8 | 8 |
| recurrence | 16 | 16 | 16 | 16 | 16 | 16 |
| reflection | 4 | 4 | 4 | 4 | 4 | 4 |
| signaling-nan | 8 | 8 | 8 | 8 | 8 | 8 |
| switch | 36 | 36 | 36 | 36 | 36 | 36 |
| tiny-reciprocal | 4 | 4 | 4 | 4 | 4 | 4 |
| two | 4 | 4 | 4 | 4 | 4 | 4 |
| zero | 4 | 4 | 4 | 4 | 4 | 4 |

## Measured finite error upper bounds

Each number is an outward upper bound in the actual result’s local ULP: distance toward each enclosure endpoint is divided by that direction’s immediate representable gap. Decimal presentation rounds upward to six places; exact rational bounds and complete input/output records are retained by the checker. These are measurements of this finite population, not global bounds or a correct-rounding proof.

| Population / operation | Maximum ULP upper bound | Witness input high:low (hex) | Witness region |
| --- | ---: | --- | --- |
| Float binary32 / erf | 0.500000 | `00000000407ad445:0000000000000000` | erf-saturation-0 |
| Float binary32 / erfc | 0.500000 | `00000000c07547cb:0000000000000000` | erfc-negative-saturation-0 |
| Float binary32 / tgamma | 0.499526 | `00000000c21ffe32:0000000000000000` | gamma-zero-sign0-0 |
| Float binary32 / lgamma | 0.494685 | `00000000c1f7ffff:0000000000000000` | pole-31-1 |
| Double binary64 / erf | 0.500000 | `4017afb48dc96627:0000000000000000` | erf-saturation-0 |
| Double binary64 / erfc | 0.500000 | `c017744f8f74e94a:0000000000000000` | erfc-negative-saturation-0 |
| Double binary64 / tgamma | 0.500000 | `c0665ffd05edca00:0000000000000000` | gamma-zero-sign1-0 |
| Double binary64 / lgamma | 0.485225 | `c02fffffffffffe6:0000000000000000` | negative-root-16-left-0 |
| raw long-double binary64 / erf | 0.500000 | `4017afb48dc96627:0000000000000000` | erf-saturation-0 |
| raw long-double binary64 / erfc | 0.500000 | `c017744f8f74e94a:0000000000000000` | erfc-negative-saturation-0 |
| raw long-double binary64 / tgamma | 0.500000 | `c0665ffd05edca00:0000000000000000` | gamma-zero-sign1-0 |
| raw long-double binary64 / lgamma | 0.485225 | `c02fffffffffffe6:0000000000000000` | negative-root-16-left-0 |
| raw extended80 / erf | 0.500000 | `0000000000004001:d0d8e9797c8fb413` | erf-saturation-0 |
| raw extended80 / erfc | 0.500000 | `000000000000c001:cf29205aa2682c91` | erfc-negative-saturation-0 |
| raw extended80 / tgamma | 0.500000 | `000000000000c009:dc3ffff9a465074a` | gamma-zero-sign0-0 |
| raw extended80 / lgamma | 0.486281 | `000000000000c001:c00b592c4be4676c` | negative-root-7-right-1 |
| raw binary128 / erf | 0.602865 | `0000ffffffffffff:ffffffffffffffff` | input-normal--1-1 |
| raw binary128 / erfc | 0.963269 | `4005aa24c0cb6e41:49d010bec1719977` | erfc-normal--1 |
| raw binary128 / tgamma | 0.983805 | `c009b6ffffeb8bff:9be98e5cd1b61365` | gamma-normal-sign0-0 |
| raw binary128 / lgamma | 0.497826 | `0000000000000000:0000000000000001` | minimum-subnormal |
| raw double-double / erf | 0.500000 | `403b39dc41e48bfc:3cdeae17c7980f14` | erf-dd-saturation-0 |
| raw double-double / erfc | 0.500000 | `c03b39dc41e48bfc:bcdeae17c7980f14` | erfc-negative-saturation-0 |
| raw double-double / tgamma | 0.500000 | `c0665ffd05edca00:3cfb96776300a2fe` | gamma-zero-sign1-0 |
| raw double-double / lgamma | 0.480284 | `c05fc00000000000:939c9b4c7476cc64` | negative-root-128-right-1 |

Only the native80 public ABI was executed by this measurement. Raw binary64, binary128 and double-double adapter results do not establish those native calling conventions. Coverage is bounded and selected; it does not exhaust all inputs, roots, caller states or representable range transitions. No host libm output supplied an acceptance value.
