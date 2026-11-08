# Explicit target contract validation

`make check-target-contracts TARGET_CONTRACT_ARGS='...'` runs the focused
portability gate. It is opt-in: ordinary builds, installation and native tests
do not require a cross compiler, target GoogleTest or an emulator. Run
`python3 tools/check-target-contracts.py --help` for the required tool paths.
The target runner uses a POSIX host and owned process groups for timeout cleanup.

Prepare the authenticated generated corpora and version header first:

```sh
make -j1 prepare-corpora libver-gen PREFIX=/path/to/private-prefix
python3 tools/check-target-contracts.py \
  --target i686 --cc i686-linux-gnu-gcc --cxx i686-linux-gnu-g++ \
  --ar i686-linux-gnu-ar --nm i686-linux-gnu-nm \
  --objdump i686-linux-gnu-objdump --readelf i686-linux-gnu-readelf \
  --runner 'qemu-i386 -L /usr/i686-linux-gnu' \
  --generated build/linux/release/generated \
  --gtest-include /path/to/target/include --gtest-lib /path/to/target/lib \
  --work /path/to/evidence
```

The i686 profile requires pointer32, long32 and native extended80, and explicitly
uses `-msse2 -mfpmath=sse`. The Windows profile requires pointer64, long32 and
native extended80. Supply MinGW64 compiler/binutils, matching target GoogleTest,
and a Wine wrapper through `--runner`. The wrapper must preserve stdout, stderr
and the real process exit status, and forward `--version` to its runtime;
configure an owned Wine prefix and matching
runtime DLLs before invoking the gate. Long-double clients use an 8 MiB Windows
stack. Compiler identity and runtime version are recorded independently.

Every production translation unit is compiled at C17/O2 with strict warnings,
`-ffp-contract=off` and `-fno-lto`. The legacy and integer/scaling clients link
the full static archive. Native long-double ABI clients link their separate
caller and individual production objects without LTO. The gate retains
commands, raw diagnostics, statuses, input byte/mode
identities, production/caller objects and complete legacy stdout. It reuses the
existing independently authenticated integer, scaling and long-double checkers.
The six current-integer GoogleTests must pass without skips, including the
signed32 rounded-boundary test. Real compiled numerical and errno defects must
fail their value/state assertions after the matching good control passes.

Linux uses the existing ELF object and caller ABI gates unchanged. Windows
additionally builds a DLL/import library and executes actual imported public
calls, retaining PE export/import and caller relocation evidence. This PE
certificate does not imply the SysV assembly wrapper or ELF CFI certificate.
Numerical comparisons and state requirements are shared across both profiles.
On i686, foundation/scaling/nine compiler C wrappers retain the existing
instruction/control partition, transfer coverage and external-call checks;
their full compiler-generated CFA is not proved. Eleven/seventeen retain the
existing explicit i386 wrapper and CFI assertions. Full PE unwind verification
is outside this gate.

These are bounded corpus and instrument checks. Emulator results do not establish
physical-machine execution, exhaustive correctness or transcendental accuracy in
every rounding mode. A timeout, crash, missing tool, missing row or setup error
fails the gate; none counts as successful fault detection. A successful
`status.json` is written only when every selected check completes.

Exception assertions cover exactly the five standard classes: invalid,
divide-by-zero, overflow, underflow and inexact. The long-scale corpus already
enumerates those five. Its fixture now observes their explicit union because
MinGW's `FE_ALL_EXCEPT` additionally exposes the x86 denormal-operand diagnostic.
The result bits, incoming standard flags, exact flag equality, errno and mode
assertions are unchanged. Compiled underflow-loss, inexact-loss and extra
divide-by-zero controls must still fail after a matching good control passes.
`probe-long-scale --diagnostics` records the wider CRT mask and observed bits
separately; preservation of architectural diagnostic flags is outside this
certificate.

The 2026-11-08 Linux i686 run used GCC/G++ 16.2.0 (Debian 16.2.0-3),
QEMU i386 11.1.2, explicit SSE2 arithmetic, pointer32/long32 and native80.
All 39 production translation units compiled
strictly. The full static client retained the 7319-byte legacy output with
SHA256 `0d972320da7b26f67e45263b52dae60056cc09947bd7342450d97d2fd18ad480`.
All four strict variants, native32 integer/scaling contracts, six current-integer
units without skips, compiled numerical/errno controls, and ten unchanged ELF
object/caller ABI gates passed.

The Windows x86-64 run used MinGW-w64 GCC/G++ `14-win32` and Wine 10.0
(Debian `10.0~repack-6`), with pointer64/long32/native80. The `win32` compiler
suffix describes its thread model; the executed target was x86-64. All 39
production translation units compiled strictly. The static arm passed the same
six current-integer units without skips, including the native-long32 boundary,
and the width-sensitive integer/scaling and compiled state-fault controls.
Static and DLL legacy clients both matched the complete 7319-byte stdout after
CRLF normalization. Real DLL imports, exports and PE caller relocations were
recorded alongside the native public calls below.

| Native80 family | i686 static | Windows static | Windows DLL |
| --- | ---: | ---: | ---: |
| Foundation | 2592 | 2592 | 2592 |
| Scaling | 5948 | 5948 | 5948 |
| Nine integer/arithmetic APIs | 15489 | 15489 | 15489 |
| Eleven roots/exponential/logarithmic APIs | 205 | 205 | 205 |
| Seventeen reference calls | 500 | 500 | 500 |
| Seventeen additional state calls | 831 | 831 | 831 |

Each seventeen state pass comprises 408 ordinary nonidentity, 63 special and
360 boundary calls across four supported control profiles, using
`--state-repetitions 24`. Eleven/seventeen used native-only selection. Each
foundation/scaling/nine checker invocation separately ran 10449/24500/77016
synthetic rows. The two static profiles also ran 84456 synthetic DD supplement
rows each. The i686 evidence includes authenticated counts, summaries and
separate objects. Each Windows seventeen arm additionally retains five
invocation JSON records containing 1332 rows, including its capability query.

The Windows long-scale diagnostic recorded CRT mask `0x3f`, standard mask
`0x3d`, and outgoing flags `0x32`/`0x30` respectively for the minimum subnormal
scaled by `LONG_MIN`; the zero result and errno 733 were correct. A matching
compiled good control passed, while compiled UF loss, IX loss and extra
divide-by-zero faults each failed the intended standard-flag assertion.

The Windows certificate covers MinGW-w64 native80 under Wine, with the PE
instrument limits stated above. It does not establish native Windows execution.
