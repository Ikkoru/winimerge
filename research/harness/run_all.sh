#!/bin/bash
# Run every experiment on the images in $IMAGES (default testset/large), tagging the CSVs with $1.
# Usage: ./run_all.sh TAG [--only name1,name2] [experiments...]
set -u
cd "$(dirname "$0")"
ROOT=${RESEARCH_DIR:-$(cd .. && pwd)}   # the research folder (this script's parent folder)
TAG="$1"; shift
ONLY=""
if [ "${1:-}" = "--only" ]; then ONLY="--only $2"; shift 2; fi
EXPS=("$@"); [ ${#EXPS[@]} -eq 0 ] && EXPS=(spurious edits codec usm heavy)
: "${LIBJXL_TOOLS:=}"
export FREEIMAGE_LIB LIBJXL_TOOLS
for e in "${EXPS[@]}"; do
  echo "=== $e ($TAG) $(date +%H:%M:%S)"
  python3 -W ignore study.py run "$e" --images "${IMAGES:-$ROOT/testset/large}" --tag "$TAG" $ONLY --jobs "${JOBS:-4}" 2>&1 | grep --line-buffered -v Fontconfig
done
echo "=== done $(date +%H:%M:%S)"
