#!/bin/bash
# Build and run the Linux unit tests for WinIMerge's diff/merge buffer.
# Usage: ./build.sh [winimerge-checkout] [test.cpp ...]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:-/home/user/winimerge}"; shift || true
TESTS=("$@"); [ ${#TESTS[@]} -eq 0 ] && TESTS=("$HERE"/test_*.cpp)
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
for f in Diff.hpp ImgDiffBuffer.hpp ImgMergeBuffer.hpp image.hpp; do
  cp "$SRC/src/WinIMergeLib/$f" "$BUILD/"
done
cp "$HERE/ImgConverter.hpp" "$HERE/testlib.hpp" "$BUILD/"
# Diff.hpp jumps over a reference initialization with goto, which MSVC accepts but GCC rejects.
# Harness-only rewrite (the shipped file is untouched): use a pointer declared without initializer.
sed -i -e 's/const Data& data = ((pass == 1) ? m_data1 : m_data2);/const Data* pdata_; pdata_ = ((pass == 1) ? \&m_data1 : \&m_data2);/' \
       -e 's/hav = data\.hash(cur);/hav = pdata_->hash(cur);/' -e 's/cur = data\.next(cur);/cur = pdata_->next(cur);/' "$BUILD/Diff.hpp"
grep -q "pdata_->next" "$BUILD/Diff.hpp" || { echo "Diff.hpp rewrite did not apply"; exit 2; }
rc=0
for t in "${TESTS[@]}"; do
  exe="$BUILD/$(basename "${t%.cpp}")"
  cp "$t" "$BUILD/"
  ${CXX:-g++} -std=c++17 -O1 -g -Wall -Wno-unused-variable -Wno-unused-function -Wno-sign-compare -Wno-write-strings \
      -Wno-unused-but-set-variable -Wno-parentheses -Wno-misleading-indentation -Wno-reorder -Wno-class-memaccess -w \
      -I"$BUILD" ${EXTRA_CXXFLAGS:-} -o "$exe" "$BUILD/$(basename "$t")" -lfreeimageplus -lfreeimage
  (cd "${OUTDIR:-$BUILD}" && "$exe" ${RUN_ARGS:-}) || rc=1
done
exit $rc
