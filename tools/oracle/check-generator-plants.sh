#!/bin/bash
# Shows that the corpus generator for the exact functions (gen_corpus_exact.py) fails on a planted defect in one of its
# two statements of each answer. Runs on the host, in the pinned oracle image; needs podman. Not part of make test.
cd "$(dirname "$0")/../.." || exit 2
W=build/gen-plants
mkdir -p "$W"
img=$(awk -F"\t" '$1=="mpfr"{print $2}' tools/oracle/containers/IMAGES)
run() {
  name=$1; old=$2; new=$3
  rm -f "$W"/gen.py
  python3 - "$old" "$new" "$W" <<'PY'
import sys
t=open('tools/oracle/gen_corpus_exact.py').read()
old,new=sys.argv[1].encode().decode('unicode_escape'),sys.argv[2].encode().decode('unicode_escape')
assert t.count(old)==1,(old,t.count(old))
open(sys.argv[3] + '/gen.py','w').write(t.replace(old,new))
PY
  [ -f "$W"/gen.py ] || { echo "HARNESS ERROR (the plant does not apply): $name"; return; }
  rm -rf "$W"/out
  if podman run --rm --userns=keep-id -v "$PWD:$PWD:z" -w "$PWD" $img python "$W"/gen.py --out "$W"/out --seed 1 --size fresh > "$W"/log.txt 2>&1; then
    echo "NOT CAUGHT: $name"
  else
    echo "caught: $name -> $(tail -1 "$W"/log.txt | cut -c1-110)"
  fi
}
run "sqrt: the integer root never rounds up" "        q += 1\n    r2 = float(Fraction(q) * Fraction(2) ** (drop - k))" "        q += 0\n    r2 = float(Fraction(q) * Fraction(2) ** (drop - k))"
run "sqrt: the integer root rounds up from a quarter" "if rem > half or" "if rem > half // 2 or"
run "floor: the rational path is ceil" "v = math.floor(fr)" "v = math.ceil(fr)"
run "round: the rational path rounds ties to even" "v = math.floor(abs(fr) + Fraction(1, 2)) * (1 if fr >= 0 else -1)" "v = round(fr)"
run "rint: the rational path rounds ties away" "if d > Fraction(1, 2) or (d == Fraction(1, 2) and f % 2 == 1):" "if d >= Fraction(1, 2):"
run "scalbn: the rational path rounds toward zero" "return sign * (a.numerator / a.denominator)" "return sign * float(a.numerator // a.denominator) if a > 1 else sign * (a.numerator / a.denominator) * (1 - 2.0 ** -53)"
run "frexp: the exact exponent is one off" "    f = fr / Fraction(2) ** e" "    e += 1\n    f = fr / Fraction(2) ** e"
run "ilogb: the check against Python is off by one" "if me - 1 != e:" "if me != e:"
run "zero sign: floor(-0) is +0 in the rules" "negative_zero = bool(sign) if fn != \"floor\" else (bool(sign) and mag == 0)" "negative_zero = False"

