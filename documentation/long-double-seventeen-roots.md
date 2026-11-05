# Lgamma root, input-grid, and cancellation certificates

The compact registry contains directed reference output, rather than runtime
constants. Its fixed SHA, canonical schema, exact rational checks, population
checks, and rejecting controls make normal offline use fail closed. The required
pinned MPFR/mpmath regeneration establishes the numerical truth of those
references. MPFR uses 4096 bits with exact dyadic inputs; the independent
mpmath check uses 8192 bits and an absolute padding of 2^-5800*max(1,|value|).
The higher independent precision allows for the smallest pole distance
(about 2^-1684) and cancellation in nearzero lgamma values. The directed MPFR
bounds establish signs; the independent approximate check corroborates them.
Pins do not authenticate arbitrary modifications of checker source.
No reference computation supplies a runtime approximation.

## Relevant roots and the input grid

On each interval between negative integer poles, recurrence gives

    (log|Gamma(x)|)'' = psi'(x+n) + sum_{j=0}^{n-1} 1/(x+j)^2 > 0,

where x+n>0 and psi'(y)=sum_{j>=0}1/(y+j)^2>0. The function tends to positive
infinity at either pole. At the half-integer in(-3,-2),
|Gamma(-5/2)|^2=64*pi/225<64*(22/7)/225<1. Each subsequent negative
half-integer divides its predecessor's gamma magnitude by a number greater
than one. Strict convexity therefore gives exactly two roots in every
(-n,1-n), n=3..256: one on each side of its half-integer. This accounts for
508 relevant roots and proves uniqueness of each indexed bracket.

For 0<y<1, the defining positive gamma integral gives
Gamma(y)>integral_0^1(1-t)t^(y-1)dt=1/[y(y+1)]. Consequently |Gamma(y-1)|>2
and |Gamma(y-2)|>16/9, using y(1-y)<=1/4 and
(y+1)(2-y)=2+y(1-y)<=9/4. Thus the first two negative pole intervals have no
roots and log magnitude greater than 1/2: e<3<(16/9)^2<4.

Every supported input in[-256,-2] or[1/2,3] lies on the 2^-1074 lattice. Binary
formats have much coarser spacing there; DD components are exact binary64
values. The registry proposes each root as a normalized 1152-bit dyadic
**distance from its pole**, then uses directed MPFR signs at both adjacent
endpoints. Both x endpoints lie strictly inside one 2^-1074 lattice cell.
The two surrounding lattice values have directed nonzero lgamma enclosures;
an integer pole is recorded explicitly instead of assigned a finite value.
The pole-distance times n! (left) or(n-1)! (right) also lies strictly between
1/2 and 2, independently tying each bracket's scale to its index.

Convexity makes lgamma monotone on the two outer sides of its roots. Between
the roots, its greatest negative values occur at the ends of any closed
subinterval. Thus the finite lattice values nearest each root bound the
smallest nonzero absolute lgamma value throughout that pole interval. The
registry also checks 1+-2^-1074 and 2+-2^-1074, using positive strict convexity
and the exact positive roots 1,2. For 0<x<=1/2 the integral bound gives
Gamma(x)>4/3, hence logGamma(x)>1/4 because(4/3)^4>3>e. For x>=3,
Gamma(x)>=2: psi(2)=1-gamma_E>0,0<gamma_E<1, and psi' is positive.

There are real lgamma zeros arbitrarily far negative. Their exclusion from
supported **inputs** is a separate grid argument, not a claim about all reals.
For a representable noninteger x<=-256, distance d to an integer is at least
2^-1074. Concavity of sine gives |sin(pi*x)|>=2d. Reflection and monotonicity
of positive gamma give

    |Gamma(x)| <= pi*2^1073/256! < 2^-608.

The last inequality is checked with exact integers and pi<4. Therefore such
inputs are bounded far away from a zero of log magnitude. Combining these
arguments with all 863 finite nearest-grid references, including four positive
references proves the stored global bound |lgamma(x)|>2^-1076 for every finite
nonzero ordinary result. Poles and the exact 1,2 identities dispatch separately.

## Scope and rounding-width units

The **absolute** width certificate below applies only to the bounded
cancellation region: negative[-256,-2] excluding poles, and positive[1/2,3].
It does not assert an absolute error bound for lgamma of an enormous argument.
Outside this region the zero exclusions above and normalized relative-width
and output-range checks apply; the runtime still checks actual output neighbors.

Let u=2^-4352. A normalized mantissa has magnitude between 1 and 2, apart from
a narrow interval crossing a power of two. Directed normalization introduces
at most two endpoint units; we budget four. For positive intervals with
relative widths A*u and B*u, a product or quotient has width at most
(A+B+8)*u, and a positive sum has width at most (max(A,B)+8)*u.
The omitted quadratic terms fit in one unit throughout the following induction:
all coefficients stay below 2^64, so A*B*u^2<=2^128*u^2<u. Exact small-integer
multiplication precedes normalization and has the same four-unit allowance.
Signed addition instead uses the absolute width of the operand sum plus four
units at the largest operand exponent, so cancellation never silently changes
an absolute error into a relative one.

All input dyadics in this region have at most 1085 significant bit positions.
Conversion, integer recurrence shifts, and y-1/2 are therefore exact. The lower
endpoint guard requires y>=1024. At most 1024 shifts give y<1026. Each product
factor is positive, so the product's relative width is at most 1024*8*u=8192u.
Its binary exponent is smaller than 1024*11<2^14. These are multiplicative
relative bounds; they do not compound as an exponential interval dependency.

For log, normalized m is in[1,2] with a possible narrow straddle. The map
(m-1)/(m+1) has bounded derivative, giving width at most 4*delta+8u from
relative input width delta. Its magnitude is at most 1/3+2^-4000 and its square
is below 1/8. In the 1400-term atanh recurrence, term-width propagation contracts
by at least 1/8; each product and small division contributes at most two fixed
endpoint units. A bound 2*w_t+8u covers every term. Summing and doubling all
1400 terms, adding symmetric analytic-tail units, adding e*ln2 with |e|<2^14,
and normalizing gives the deliberately rounded bound

    width(log(a)) <= 2^16*relative_width(a) + 2^20*u.

The geometric analytic tail is below one fixed unit; the new immutable ln2
interval has width u and is derived from a guarded positive rational series.
This bound also covers a normalized input straddling a power of two.

For sin(pi*f),0<f<=1/2, the argument has relative width at most 16u (including pi normalization). Its square
has relative width at most 40u. Through 512 Taylor terms, a term's relative
width is at most (16+512*(40+16))*u<2^15u. The absolute-term sum divided by the
sine is below 4: use sinh(t)<2t and sin(t)>=2t/pi on 0<t<=pi/2. Directed sum
rounding adds less than 2^14u relatively, so 2^20u safely bounds the sine's
relative width, including its next-term remainder. Termination occurs before
512 terms: at n=512,4^n/(2n+1)!<2^-6528, using the factorial blocks
513..1024,257..512,129..256. This is well below the 4400-bit stopping test.
Log then turns this relative sine width into an absolute bound without a 1/f
factor; the sine's binary exponent has magnitude at most 1075 on this grid.

For the 512 Stirling terms, the reciprocal starts with relative width<=4u;
the inverse square and each subsequent power add at most 24u per step.
Every coefficient has magnitude greater than 2^-11 (checked from exact
Bernoulli rationals), so its fixed-point enclosure has relative width below
2^12u. Term relative widths are below 2^16u. The positive absolute term sum is
below 2^-12, since the first term is 1/(12y) and subsequent ratios are below 1/16.
A 2^20*u allowance covers all arithmetic in the sum, including tail packing.
Binet's integral gives the remainder directly:

    logGamma(y) - (y-1/2)log(y) +y - log(2*pi)/2
      = 2 integral_0^infinity arctan(t/y)/(exp(2*pi*t)-1) dt.

The finite geometric identity for 1/(1+z*z), integrated from 0 to z, gives an
alternating arctan remainder with the sign of the next term and magnitude no
greater than that term, for every z>=0. Integrating this positive bound in
Binet's formula establishes the Stieltjes bound. The ratio of consecutive
absolute Stirling coefficients is
(2k)(2k-1)*zeta(2k+2)/(4*pi*pi*zeta(2k)); zeta decreases and pi>3. At k<=512
and y>=1024 the term ratio is below 1/32. The implementation encloses the next
remainder conservatively by the last retained term divided by 16. The exact generator
checks this at y=1024 and proves that its magnitude is below 2^-4190.

The following integer coefficients implement those bounds in the generator:

| Contribution | Coefficient multiplying u |
| --- | --- |
| Main (y-1/2)log(y)-y | 2^11*2^20 +2^20 |
| Log of positive recurrence product | 2^16*8192 +2^20 |
| Half log(2*pi) | 2^22 |
| Stirling arithmetic | 2^20 |
| Reflection log(sine) | 2^16*2^20 +2^20 |
| Reflection log(pi) | 2^16*4 +2^20 |
| Remaining directed sums | 2^20 |

The sum is below 2^40, hence below the retained conservative 2^64*u budget.
The main-expression bound uses y<2^11, log(y)<7, and operand magnitudes below
2^15; the generator verifies exp(7)>1026 with a finite positive rational sum.
With the Stieltjes width included, exact rational checking gives total width
below 2^-4100 in the stated region. The root/grid lower bound 2^-1076 therefore
leaves a relative width below 2^-3024. A DD population gap is at least 2^-2098
relative to a finite value (minimum component quantum 2^-1074, maximum magnitude
below 2^1024), leaving 926 bits of reserve. Single formats have coarser relative
spacing. This is a one-local-ULP enclosure argument, not global correct rounding.

## Error-tail continuants

The forward positive continuants use T[-1]=1,T[0]=2x,U[-1]=0,U[0]=1 and
T[n]=2x*T[n-1]+2n*T[n-2], U[n]=2x*U[n-1]+2n*U[n-2]. Their reciprocal
fraction is 2U[n]/T[n]. Positive recurrences avoid cancellation and accumulate
at most 16u relative width per step; the two final divisions add their endpoint
rounding. Only two full divisions are needed for depths 2048 and 2049.

At x=16, exact integer arithmetic proves their gap is
2049!*2^2050/(T[2049]*T[2048])<2^-2614. Positive denominator polynomials make
this absolute gap decrease for x>=16. On 16<=x<128, the reciprocal fraction is
at least 1/(x+1/(2x))>1/129, giving relative analytic width below 2^-2606.
Forward arithmetic adds less than 2^17u, far below that width. Saturation and
underflow cases at larger x dispatch separately.
