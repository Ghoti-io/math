# Final native real long-double functions

The seventeen-family module implements `sinl`, `cosl`, `tanl`, `asinl`, `acosl`,
`atanl`, `atan2l`, `sinhl`, `coshl`, `tanhl`, `asinhl`, `acoshl`, `atanhl`,
`erfl`, `erfcl`, `tgammal`, and `lgammal`. The raw adapters decode binary64,
extended80, binary128, and IBM double-double without a binary64 bridge.
Double-double values remain exact component sums; final certification uses
actual population neighbors, including their variable spacing.

Numerical decisions use integer operations. Outward normalized intervals have
4352 fractional significand bits and an explicit signed exponent. This permits
intermediate exponent ranges beyond the output layout, including gamma's
logarithm and full-range hyperbolic arguments. Logarithms use the rational
atanh series, exponentials use ln2 reduction and Taylor expansion, roots use
restoring integer square roots, and inverse angles use eight half-angle
reductions followed by an alternating series. Each composition carries internal
enclosures rather than rounded public results.

## Full-range trigonometric reduction

The preparation tool derives pi from Machin's identity using rational
alternating-series bounds. It authenticates every bit of a 75008-bit floor of
2/pi, a 4352-bit pi enclosure, and normalized rational Bernoulli coefficients.
No external math implementation supplies constants or runtime algorithms.

A reduced rational p/q is certified with D=2^32879, D<q<2^32900, and
|pi-p/q|<1/(2Dq), checked against both outward Machin endpoints. Every supported
finite value is A*2^-16494. For nonzero |k|<2^16385, the rational r=2x/k has
reduced denominator b<=D and differs from p/q. Consequently
|pi-r|>=1/(bq)-1/(2Dq)>=1/(2bq), so
|x-k*pi/2|>=2^-16496/q>2^-49396. Odd-k nearest-quadrant midpoints similarly
satisfy |x-k*pi/4|>=2^-16495/q>2^-49395, using r=4x/k. The k=0 case uses the
original exact input. These bounds establish both residual and pole-side signs.

The complete significand product with floor(2/pi) is retained before quadrant
subtraction and normalization. Its absolute omitted error is below 2^-58624,
leaving over 9200 relative bits even at the smallest allowed nonzero residual.
Sine/cosine alternating-series tails use the next term, so tiny arguments
retain relative precision instead of receiving an absolute truncation radius.

## Error and gamma functions

The small-error path uses the positive expansion for exp(x*x)*erf(x), retaining
the exponential as an internal interval. The tail path uses independent even
and odd convergents of Laplace's positive continued fraction. Reflection keeps
sin(pi*x) reduction exact on the input grid. Gamma uses positive recurrence to
y>=1024 and 512 rational Stirling coefficients, with a Stieltjes remainder bound.
Lgamma returns log(abs(gamma)) and does not modify signgam or another global.

Signed-zero and infinite identities are exact. Domain errors add IV; poles add
DZ. Ordinary finite gamma/error calls add IX, including factorials, except the
explicit gamma(1), gamma(2), lgamma(1), and lgamma(2) identities. Tiny rounded
results add UF/IX; range overflow adds OF/IX. Incoming flags, errno, and controls
are preserved. Native80 wrappers retain arguments as bytes until classification
and use one final memory load for the ABI return.

## Verification

The compact pinned corpus, state/public-wrapper checks, rejecting controls,
and required independent preflight are described in
[the reference and gate contracts](long-double-seventeen-corpus.md).
The negative-root registry, input-grid exclusions, and bounded cancellation
width derivation are described in
[the lgamma proof](long-double-seventeen-roots.md).
Default tests are container-free; independent regeneration is explicit and
fails closed. Native80 ABI checks cover argument/result slots, external calls,
control writes, floating instructions, and unwind rows. Raw adapters cover all
four layouts; native ABI coverage is recorded separately by each target run.
