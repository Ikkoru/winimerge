#!/bin/bash
# Resumable chain of all experiments (synthetic, then real images). Safe to re-run after a restart.
cd "$(dirname "$0")"
export FREEIMAGE_LIB=${FREEIMAGE_LIB:-/tmp/claude-0/-home-user/c93e777e-edee-5658-827e-7ebd2f76571d/scratchpad/lib/libfreeimage-3.19.0.so}
export LIBJXL_TOOLS=${LIBJXL_TOOLS:-/tmp/claude-0/-home-user/c93e777e-edee-5658-827e-7ebd2f76571d/scratchpad/ext/libjxl/build/tools}
run() { local tag=$1 img=$2; shift 2; echo "=== $1 ($tag) $(date +%H:%M:%S)"; python3 -W ignore study.py run "$@" --images "$img" --tag "$tag" --jobs ${JOBS:-4} 2>&1 | grep --line-buffered -v Fontconfig; }
S=/home/user/research/testset/large
R=/home/user/research/testset/large_real
run synth $S spurious
run synth $S edits
run synth $S heavy
run real $R spurious --shrinkers area,pil_bilinear,cv_linear,pil_bicubic,pil_lanczos,lanczos_linear,vips
run real $R edits --factors 2,2.5,3
run real $R heavy
run synth $S usm
run real $R usm --only real_peppercarrot_cover,real_peppercarrot_witches,real_hokusai_hodogaya,real_lion_appel,real_kitty_screenshot
run synth $S codec
run real $R codec
echo "=== done $(date +%H:%M:%S)"
