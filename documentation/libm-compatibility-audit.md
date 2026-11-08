# Float/Double libm compatibility audit

Audited implementation: `dc0204f737c8bdc9ee846ea5418ec185937d023e`.
All 57 tracked classic real-function names exist in both precisions. This
inventory excludes long double, complex functions, classification/comparison
macros, type-generic dispatch, newer extension families and vendor extensions.
Having 114 entry points does not establish interchangeable behavior.

The most important substitution risks are current-mode rounding, error
reporting and observable floating-point state. Canonical NaNs and bounded
nearest-mode approximations are deliberate project choices. No runtime,
header, corpus, gate or consumer was changed by this audit.

## Project-standard disposition

The owner clarified that correctness means self-consistency with the published,
deterministic specifications, rather than emulating version-dependent libm
behavior. Fixed ties-to-even rint, preserved errno, canonical NaNs, ignored nan
tags, no signgam side effect and fixed-nearest paths therefore remain intentional
contracts. They are substitution considerations, not open implementation defects.
No compatibility adapter or default semantic change is authorized by that goal.

The concrete atan2 intermediate-underflow finding is corrected, including
the separate classifier multiplication that can underflow for two subnormal
inputs. Stale no-FMA/unimplemented-function prose is corrected, and broad
sqrt/determinism wording is qualified by the existing nearest-mode scope. The
historical comparisons below remain observations of the audited revision.

## Correction verification

The correction preserves all 122 numerical result sets and legacy aggregate.
Focused GCC16, Clang19 and ASan/UBSan checks pass 14 Elementary tests, including
all four modes and all 32 incoming-flag subsets. Four compiled defects establish
that incidental classifier/reflected underflow, lost direct underflow and lost
reflected inexact are caught at intended assertions. Independent nearest cutoff
encodings and direct signed zero/subnormal encodings supplement scale-invariance
checks. An exact-rational instrument validates 11,112 actual C ratio comparisons
and the stored reflected-constant tail/midpoint margins.

The original default full run stopped at one old adjacency-dependent mutation
anchor after the classifier was inserted. That attempt remains failed, with its
full log/status and verified record archive preserved. The repair anchors the
infinite-x branch itself. A verified resumption establishes identical code/data,
relocations and symbol sections for all 75 production/main-test objects across
both frozen trees after removing only debug metadata/build IDs. All other
mutation tasks have identical AST, all 58 literal source anchors are valid,
the repaired mutant fails the required quadrant assertion, and the unmodified
Elementary control passes. The 68 completed default gates are retained; the
interrupted aggregate is accounted for by its complete prior task record plus
the corrected item. All 39 later default gates and all main binaries then pass:
41 binaries, 285 tests, 284 passes and one expected native32-long skip. This is
composite verification, not a relabeling of the failed initial command.

No runtime/test/Make code changes occur after that verified tree; final edits
only record these results in Markdown. Initial, resumed and focused build trees
were reclaimed after archive CRC/tar-inventory verification. The prior unrun
platform and failed instrumentation scopes below remain unchanged.

## Evidence and interpretation

The fixed catalog covers all 114 entry points: twelve cases, four standard
rounding modes and two incoming-flag states, giving **10,944 paired cases**.
Cases are signed zero, 0.5, -1, 2, minimum subnormal, maximum finite, both
infinities, quiet/signaling NaNs with payloads, and 1.5. Binary functions
normally receive a second argument of 2; copysign uses -1, and negative-base
pow uses exponent 0.5. FMA's third argument is -1; scaling uses exponent -1
or 2048. Nexttoward receives native long-double `1 + 2^-63`; nan receives
valid tag `"123"`. The catalog is intentionally small, not a random accuracy
campaign or a comprehensive binary-operand cross product.

The production archive was compiled with GCC 16.2.0 and its existing O2 flags.
An O0 GCC caller and an O2 Clang 19.1.7 caller, both using volatile function
pointers, `-fno-builtin`, `-frounding-math` and disabled contraction, produced
byte-identical CSV against that same archive. The comparison host was
x86-64 glibc 2.41, 64-bit long and native binary80 long double. This is not a
second production-compiler or non-native ABI test. The caller clears flags,
optionally seeds divide-by-zero, and sets errno and signgam sentinels before
each individual call. No external math implementation source was consulted.

Across this catalog, project calls preserved errno, the active mode, incoming
seeded flags and the signgam sentinel. This does not check every control bit
or every incoming flag combination; earlier family tests cover their declared
broader state scopes. The CSV checker rejects omitted/duplicate rows, malformed
words and altered project state; actual negative controls exercised each.

| Observation axis | Unequal paired rows |
|---|---:|
| Returned raw encoding/integer | 2,832 |
| Auxiliary output | 96 |
| Exception flags | 258 |
| errno | 1,250 |
| signgam | 192 |

These axes overlap. They are **not failure counts or compatibility percentages**.
NaN sign/payload choices explain many differences; error-path outputs can be
implementation-defined or unspecified. In nearest mode, 24 rows had unequal
finite floating results, representing twelve input/precision cases repeated
with both flag seeds. The observed differences were one adjacent encoding,
across cbrt, log1p, asinh, acosh, atanh, sinh and erfc. Host output alone cannot
identify the more accurate answer. Existing independent oracle evidence, not
host-bit equality, remains the numerical acceptance basis.

CSV SHA256, identical for both callers:
`0f3ed872b7ecf8b4e7d2addf56a5039cf37da7942b3797279ce5c27b2155a566`.
Raw records and build/status evidence remain in the ignored local audit evidence
directory; the public artifact records the reproducible method and conclusions.

## Prioritized differences

| Priority | Finding and concrete witness | Disposition / consumer impact |
|---|---|---|
| 1 | Under downward rounding, rint(1.5) returns 2 with no added flags; host returns 1 with inexact. Both precisions differ. | Deliberate existing contract, incompatible with current-mode C rint. Address before generic substitution. Nearbyint and lrint/llrint already supply current-mode operations; nearbyint suppresses inexact and is not a complete rint replacement. |
| 1 | Double atan2(DBL_MAX, 2) returns normal nearest pi/2 but adds UF/IX; this host adds neither. | Reproduced intermediate-underflow issue, not a new numerical failure. `atan2.c` computes the tiny reciprocal ratio before reflecting to pi/2. Track a focused fenv fix preserving result bits; the broad Annex-F wording in its header does not disclose this behavior. |
| 2 | Upward scalbn(minsub, -1) returns zero; host returns minsub. Ldexp and scalbln share this policy. Fdim and Float hypot also have fixed-nearest contracts. | Deliberate result-bit differences, not failed preservation: leaving the caller's mode unchanged is distinct from computing in that mode. Directed-mode consumers need a compatibility implementation, not a claim based on nearest tests. |
| 2 | log(-1) returns canonical NaN with IV and preserves errno=123; host sets EDOM. Pole/range cases likewise differ. | Deliberate errno policy. Error-checking callers need explicit handling or an adapter. Do not infer failure from a stale errno value after a project call. |
| 2 | copysign(qNaN(payload), -1) returns positive canonical NaN; host returns negative payload NaN. With sNaN, project also raises IV while host copies its bits without IV. | Canonicalization is intentional, but NaN sign copying is a concrete C copysign compatibility gap. A payload-blind comparison would hide this distinction. |
| 3 | fabs(sNaN) quiets/canonicalizes and raises IV; host retains signaling payload bits without IV. Nan("123") ignores the tag while host encodes it. | Deliberate representation/state choices. Tag interpretation and NaN payloads are not a portable host-bit-equality requirement; code using payload tags still needs a migration decision. |
| 3 | lgamma(0.5) leaves signgam=12345; host sets +1. | Deliberate no-global-side-effect policy. GNU/POSIX-style callers reconstructing gamma's sign from signgam cannot substitute directly. No new sign-output API is introduced here. |
| 3 | ilogb(NaN) returns INT_MAX; this host returns INT_MIN. Remquo sets its auxiliary output to zero on invalid/NaN cases while this host leaves the sentinel. | Platform/invalid-path conventions, not established numerical defects. Use project sentinel macros. Do not compare unspecified error-path auxiliary output or demand identical higher quotient bits. |
| 3 | acos(0) and asin(-1) add IX while this host does not; tgamma(2) is exact without new flags here while host adds IX. | Host exception equality is not the project's family policy. Resolve requirements per function rather than clearing flags or weakening existing tests. |

C11 draft N1570 specifies current-direction rint via nearbyint in §7.12.9.4,
with Annex F.10.6.4 requiring inexact for changed values. Copysign's NaN result
has y's sign (§7.12.11.1). Its error-reporting model is conditional on
math_errhandling (§7.12.1), and permits alternative ilogb NaN sentinels
(§7.12). These distinctions matter when classifying a mismatch as a contract
choice, permitted implementation difference or C-compatibility gap.
See [N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf).
GNU's documented lgamma signgam side effect is a separate compatibility surface;
see [the GNU C Library manual](https://sourceware.org/glibc/manual/latest/html_node/Special-Functions.html).

## Family disposition

Every listed name includes its Float counterpart. “Nearest” below is a
per-function contract, not proof of universal correct rounding.

| Family / names | Audit disposition |
|---|---|
| Basic value operations: sqrt, floor, ceil, trunc, round, fabs, copysign | Ordinary exact operations are a strong migration starting point. Sqrt's public accuracy scope assumes nearest; hardware and portable directed behavior must not be conflated. NaN sign/payload and signaling behavior require explicit handling. |
| Integral rounding: rint, nearbyint, lrint, llrint, lround, llround | Rint is the main value-semantics gap. Nearbyint and current-mode integer conversions have reviewed four-mode contracts. Invalid conversion sentinels and errno are project-defined. |
| Scaling/decomposition: scalbn, scalbln, ldexp, frexp, modf, logb, ilogb | Decomposition and valid exponent values have exact contracts. Scaling fixes nearest bits; Double/Float tininess policies differ at rounded boundaries. Special exponent sentinels and error reporting differ from some hosts. |
| Remainders: fmod, remainder, remquo | Exact finite remainder contracts cover all modes. Preserve quotient low-bit guarantees rather than host-specific full integers; invalid paths and NaNs have project conventions. |
| Adjacent/extrema: nextafter, nexttoward, fdim, fmin, fmax | Adjacent-value selection is exact; nexttoward needs native ABI validation per format. Fdim is fixed-nearest. Signed-zero extrema ordering and signaling-NaN precedence are explicit project policies. The catalog does not cover every NaN operand ordering. |
| Circular/inverse: sin, cos, tan, asin, acos, atan, atan2 | Nearest accuracy targets, canonical NaNs and family-specific exceptions; no general directed accuracy claim. The Double atan2 reflected tiny-ratio exception is an actionable follow-up. |
| Exponential/logarithmic/power: exp, exp2, log, log2, log10, log1p, expm1, pow, cbrt, hypot | Nearest targets plus documented exact special cases. Directed tails, errno and IX witnesses vary; Double/Float signaling-identity precedence can differ. Universal correct rounding and all-mode equivalence remain unproven. |
| Hyperbolic/inverse: sinh, cosh, tanh, asinh, acosh, atanh | Nearest targets; deliberate fixed-result tiny/saturation paths, preserved errno and explicit pole/domain flags. Directed compatibility requires additional work. |
| Error/gamma/constructors/FMA: erf, erfc, tgamma, lgamma, nan, fma | Error/gamma nearest targets are measured, not globally proved. Lgamma does not publish signgam. Nan ignores tags. Integer FMA rounds once in all four modes; its exact contract is stronger than the ordinary transcendental targets. |

## Current consumers and recommended order

A read-only lexical scan examined 879 C/C++ source/header files under src/include
in shape-geometry, shape-cpu, shape-scene, vector, model, audio, image, color and
font. It found no direct rint/copysign call, rounding-mode setter/query or signgam
use after comment removal. This is a selected-source scan, not whole-program
proof: wrappers, generated code, indirect calls and external consumers remain.
Errno use in model parsers is associated with string conversion and must not be
misclassified as a math-call dependency.

Shape code already uses gmath_sqrt/atan2 and other earlier functions. For example,
shape-geometry's path arc code and shape-cpu's gradient renderer call gmath_atan2.
Consequently “no consumers migrated” is too broad: migration of the newly added
families remains pending, while earlier gmath integration already exists.
Nothing in this audit edits or validates those applications end to end.

Accepted follow-up after the owner's clarification:

1. Correct the demonstrated atan2 incidental-underflow paths, preserving the
   existing numerical corpus/hash contracts and genuine final tiny behavior.
2. Retain intentional deterministic contracts; reconcile stale documentation
   rather than adding adapters to imitate a particular host's policies.
3. Make future consumer migrations against those explicit numerical/state
   contracts. The audit's selected-source scan is not end-to-end validation.
4. Keep unrun numerical/platform work and known instrument limitations explicit.
   The 57 long-double names remain outside this Float/Double consistency fix.

## Verification still open

The later [four-function force checks](four-force-flags.md) add independent,
explicitly calibrated call-site coverage for the masked expf/exp2f UF/IX and
atanf/cbrtf IX forces. They preserve natural public checks separately; the
historical absence of a natural deletion witness is not relabeled as one.

The existing family oracle/state/defect evidence remains relevant; this audit
adds representative host comparisons, not a replacement accuracy certificate.
The earlier partial Valgrind fenv scopes remain failed, despite zero reported
memory errors in those scopes. Older expf/exp2f/atanf/cbrtf force-only inexact
witness coverage remains unverified; this catalog does not close it. See the
historical records in [libm-progress.md](libm-progress.md).

Non-native nexttoward format decoders have synthetic coverage, but native
binary64/binary128/IBM double-double ABI execution is not established by this
binary80 host run. Trapping environments, independent hardware control-word
settings, exhaustive operands, additional libm implementations and end-to-end
consumer migrations were not exercised here. The full implementation suite's
expected native32-long and optional unavailable-instrument skips remain explicit.

## Reproduce

The probe is a GNU/Linux host-comparison utility, not a default test gate.
It uses glibc signgam and assumes the project's supported Float/Double layouts.
Set PREFIX to an existing private dependency installation, then run in math:

```sh
make -j1 BUILD=libm-compat-audit PREFIX="$PREFIX" build/linux/libm-compat-audit/apps/libghoti.io-math-0.a
cc -std=c17 -O0 -Wall -Wextra -Werror -fno-builtin -frounding-math -ffp-contract=off \
  -Iinclude -Ibuild/linux/libm-compat-audit/generated tools/audit-libm-compat.c \
  build/linux/libm-compat-audit/apps/libghoti.io-math-0.a \
  -L"$PREFIX/lib/ghoti.io" -Wl,-rpath,"$PREFIX/lib/ghoti.io" -lghoti.io-cutil-0 -lm \
  -o build/linux/libm-compat-audit/probe
build/linux/libm-compat-audit/probe > build/linux/libm-compat-audit/results.csv
python3 tools/audit-libm-compat.py build/linux/libm-compat-audit/results.csv
```

The actual audit used one capped CPU, a 1536 MiB kernel limit, a named container
with an independent deadline and finally cleanup. The first build invocation
used an incorrect platform-prefixed BUILD value and failed before comparison;
that failure is retained. The corrected build and both callers exited zero.
No full suite was repeated for this audit: runtime, headers, corpora and Make
rules are unchanged from the completed 108-gate/284-test implementation run.
