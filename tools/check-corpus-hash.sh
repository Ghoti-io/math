#!/bin/sh
#
# Fail unless the corpus hash a probe prints is the committed one.
#
# Usage: check-corpus-hash.sh PROBE CORPUS_DIR HASH_FILE
#
# PROBE is tools/corpus-hash.c built for this host (or a planted variant);
# HASH_FILE is tests/corpus/trig.hash, whose `hash` and `count` lines are the
# committed values over all eight functions, and whose `fn NAME HASH COUNT`
# lines are the value of each function alone.  The probe must print
# math.trig.hash and math.trig.count and a math.NAME.hash and math.NAME.count
# for each function; every one must equal the committed value.  No value may be
# empty, so a probe that crashed, or a hash file that was emptied, fails rather
# than comparing nothing with nothing.
probe="${1:?usage: check-corpus-hash.sh PROBE CORPUS_DIR HASH_FILE}"
dir="${2:?usage: check-corpus-hash.sh PROBE CORPUS_DIR HASH_FILE}"
file="${3:?usage: check-corpus-hash.sh PROBE CORPUS_DIR HASH_FILE}"

got="$("$probe" "$dir")" || { printf 'check-corpus-hash: the probe failed\n' >&2; exit 1; }
got_hash=$(printf '%s\n' "$got" | awk '$1=="math.trig.hash"{print $2}')
got_count=$(printf '%s\n' "$got" | awk '$1=="math.trig.count"{print $2}')
want_hash=$(awk '$1=="hash"{print $2}' "$file" 2>/dev/null)
want_count=$(awk '$1=="count"{print $2}' "$file" 2>/dev/null)
if [ -z "$want_hash" ] || [ -z "$want_count" ] || [ -z "$got_hash" ] || [ -z "$got_count" ]; then
  printf 'check-corpus-hash: nothing to compare (probe %s/%s, committed %s/%s in %s)\n' \
    "$got_hash" "$got_count" "$want_hash" "$want_count" "$file" >&2
  exit 1
fi
if [ "$got_hash" != "$want_hash" ] || [ "$got_count" != "$want_count" ]; then
  printf 'check-corpus-hash: FAIL: %s over %s results, committed %s over %s\n' \
    "$got_hash" "$got_count" "$want_hash" "$want_count" >&2
  exit 1
fi
# Check both directions. Iterating only emitted names would silently ignore a
# committed supplemental function if its entry disappeared from the probe.
got_names=$(printf '%s\n' "$got" | awk -F'[. ]' '$1=="math" && $3=="hash" && $2!="trig"{print $2}' | sort)
want_names=$(awk '$1=="fn"{print $2}' "$file" | sort)
if [ -z "$want_names" ] || [ "$got_names" != "$want_names" ]; then
  printf 'check-corpus-hash: FAIL: per-function name lists differ\nprobe:\n%s\ncommitted:\n%s\n' \
    "$got_names" "$want_names" >&2
  exit 1
fi
bad=0
n=0
for name in $(printf '%s\n' "$got" | awk -F'[. ]' '$1=="math" && $3=="hash" && $2!="trig"{print $2}'); do
  g_hash=$(printf '%s\n' "$got" | awk -v k="math.$name.hash" '$1==k{print $2}')
  g_count=$(printf '%s\n' "$got" | awk -v k="math.$name.count" '$1==k{print $2}')
  w_hash=$(awk -v k="$name" '$1=="fn" && $2==k{print $3}' "$file")
  w_count=$(awk -v k="$name" '$1=="fn" && $2==k{print $4}' "$file")
  n=$((n + 1))
  if [ -z "$w_hash" ] || [ -z "$w_count" ] || [ "$g_hash" != "$w_hash" ] || [ "$g_count" != "$w_count" ]; then
    printf 'check-corpus-hash: FAIL: %s: %s over %s results, committed %s over %s\n' \
      "$name" "$g_hash" "$g_count" "$w_hash" "$w_count" >&2
    bad=1
  fi
done
if [ "$bad" -ne 0 ] || [ "$n" -eq 0 ]; then
  printf 'check-corpus-hash: FAIL: per-function values (%s functions) do not match\n' "$n" >&2
  exit 1
fi
printf 'check-corpus-hash: %s over %s results (%s functions), as committed\n' "$got_hash" "$got_count" "$n"
