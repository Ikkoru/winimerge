#!/bin/bash
# Real-image runs with a slightly trimmed grid (compute budget); see REPORT.md for the full grid on synthetic images.
cd "$(dirname "$0")"
ROOT=${RESEARCH_DIR:-$(cd .. && pwd)}   # the research folder (this script's parent folder)
# FREEIMAGE_LIB: optional, WinMerge's FreeImage fork as a .so (README); the system libfreeimage is used otherwise
export LIBJXL_TOOLS=${LIBJXL_TOOLS:-}   # folder with butteraugli_main and ssimulacra2 (README)
IMG=$ROOT/testset/large_real
run() { echo "=== $1 (real) $(date +%H:%M:%S)"; python3 -W ignore study.py run "$@" --images $IMG --tag real --jobs ${JOBS:-4} 2>&1 | grep --line-buffered -v Fontconfig; }
run spurious --shrinkers area,pil_bilinear,cv_linear,pil_bicubic,pil_lanczos,lanczos_linear,vips
run edits --factors 2,2.5,3
run heavy
run codec
run usm --only real_peppercarrot_cover,real_peppercarrot_witches,real_hokusai_hodogaya,real_lion_appel,real_kitty_screenshot
echo "=== done $(date +%H:%M:%S)"
