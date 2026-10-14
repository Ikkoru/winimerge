#!/bin/bash
# Real-image runs with a slightly trimmed grid (compute budget); see REPORT.md for the full grid on synthetic images.
cd "$(dirname "$0")"
export FREEIMAGE_LIB=${FREEIMAGE_LIB:-/tmp/claude-0/-home-user/c93e777e-edee-5658-827e-7ebd2f76571d/scratchpad/lib/libfreeimage-3.19.0.so}
export LIBJXL_TOOLS=${LIBJXL_TOOLS:-/tmp/claude-0/-home-user/c93e777e-edee-5658-827e-7ebd2f76571d/scratchpad/ext/libjxl/build/tools}
IMG=/home/user/research/testset/large_real
run() { echo "=== $1 (real) $(date +%H:%M:%S)"; python3 -W ignore study.py run "$@" --images $IMG --tag real --jobs ${JOBS:-4} 2>&1 | grep --line-buffered -v Fontconfig; }
run spurious --shrinkers area,pil_bilinear,cv_linear,pil_bicubic,pil_lanczos,lanczos_linear,vips
run edits --factors 2,2.5,3
run heavy
run codec
run usm --only real_peppercarrot_cover,real_peppercarrot_witches,real_hokusai_hodogaya,real_lion_appel,real_kitty_screenshot
echo "=== done $(date +%H:%M:%S)"
