#!/bin/bash
# Randomized stress test of WinIMerge's merge buffer under AddressSanitizer/UBSan.
# Usage: ./run.sh <winimerge-checkout> <none|align|scale|both> [iterations=400] [seed=7] [extra g++ flags...]
#   none  = master (or any tree without the new options); align/scale/both enable the new options' ops.
# The same seed runs the same operation sequence on every tree, so crash sites can be compared between trees.
# Prints a summary of crash sites (function, file:line, last operation) at the end.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$1"; WHAT="$2"; ITER="${3:-400}"; SEED="${4:-7}"; shift 2; shift $(( $# > 2 ? 2 : $# ))
case "$WHAT" in none) DEFS=();; align) DEFS=(-DHAS_ALIGN);; scale) DEFS=(-DHAS_SCALE);;
  both) DEFS=(-DHAS_ALIGN -DHAS_SCALE);; *) echo "second argument: none, align, scale or both"; exit 2;; esac
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
for f in Diff.hpp ImgDiffBuffer.hpp ImgMergeBuffer.hpp image.hpp; do cp "$SRC/src/WinIMergeLib/$f" "$BUILD/"; done
cp "$HERE/../ImgConverter.hpp" "$HERE/../testlib.hpp" "$HERE/fuzz.cpp" "$BUILD/"
# same harness-only Diff.hpp rewrite as ../build.sh (GCC rejects a goto over a reference initialization)
sed -i -e 's/const Data& data = ((pass == 1) ? m_data1 : m_data2);/const Data* pdata_; pdata_ = ((pass == 1) ? \&m_data1 : \&m_data2);/' \
       -e 's/hav = data\.hash(cur);/hav = pdata_->hash(cur);/' -e 's/cur = data\.next(cur);/cur = pdata_->next(cur);/' "$BUILD/Diff.hpp"
grep -q "pdata_->next" "$BUILD/Diff.hpp" || { echo "Diff.hpp rewrite did not apply"; exit 2; }
${CXX:-g++} -std=c++17 -O1 -g -w -fsanitize=address,undefined -fno-omit-frame-pointer -I"$BUILD" "${DEFS[@]}" "$@" \
    -o "$BUILD/fuzz" "$BUILD/fuzz.cpp" -lfreeimageplus -lfreeimage
cp "$BUILD/fuzz" "${OUTDIR:-.}/fuzz_${WHAT}"      # kept for minimize.py
OUT="${OUTDIR:-.}/fuzz_${WHAT}_${SEED}.txt"
FUZZ_LOGDIR="$BUILD" ASAN_OPTIONS=detect_leaks=0 "$BUILD/fuzz" "$ITER" "$SEED" > "$OUT" 2>&1 || true
tail -1 "$OUT"
python3 "$HERE/classify.py" "$OUT"
echo "full output: $OUT"
