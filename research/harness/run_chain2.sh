#!/bin/bash
# Supplementary experiments (linear light, jpegQS restoration). Resumable.
cd "$(dirname "$0")"
ROOT=${RESEARCH_DIR:-$(cd .. && pwd)}   # the research folder (this script's parent folder)
# FREEIMAGE_LIB: optional, WinMerge's FreeImage fork as a .so (README); the system libfreeimage is used otherwise
export LIBJXL_TOOLS=${LIBJXL_TOOLS:-}   # folder with butteraugli_main and ssimulacra2 (README)
run() { local tag=$1 img=$2; shift 2; echo "=== $1 ($tag) $(date +%H:%M:%S)"; python3 -W ignore study.py run "$@" --images "$img" --tag "$tag" --jobs ${JOBS:-4} 2>&1 | grep --line-buffered -v Fontconfig; }
S=$ROOT/testset/large
R=$ROOT/testset/large_real
# add the compare-at-the-smaller-size rows that runs made before they existed (incl. down_matched8)
run synth $S spurious --down-only
run synth $S edits --down-only
run synth $S linear
run real $R linear
run synth $S jpegqs --only synth_flatcolor,synth_lineart,synth_manga,synth_painterly
run real $R jpegqs --only real_peppercarrot_cover,real_peppercarrot_witches,real_hokusai_hodogaya,real_lion_appel
echo "=== done $(date +%H:%M:%S)"
