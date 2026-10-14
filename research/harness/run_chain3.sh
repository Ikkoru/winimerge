#!/bin/bash
# All remaining experiments, most important first. Resumable: safe to re-run after a restart.
cd "$(dirname "$0")"
export FREEIMAGE_LIB=${FREEIMAGE_LIB:-/tmp/claude-0/-home-user/c93e777e-edee-5658-827e-7ebd2f76571d/scratchpad/lib/libfreeimage-3.19.0.so}
export LIBJXL_TOOLS=${LIBJXL_TOOLS:-/tmp/claude-0/-home-user/c93e777e-edee-5658-827e-7ebd2f76571d/scratchpad/ext/libjxl/build/tools}
run() { local tag=$1 img=$2; shift 2; echo "=== $* ($tag) $(date +%H:%M:%S)"; python3 -W ignore study.py run "$@" --images "$img" --tag "$tag" --jobs ${JOBS:-4} 2>&1 | grep --line-buffered -v Fontconfig; }
# wait for runs started by an earlier chain (they write the same CSVs)
while pgrep -f "study.py run" >/dev/null; do sleep 15; done
S=/home/user/research/testset/large
R=/home/user/research/testset/large_real
run synth $S spurious
run synth $S edits
run synth $S spurious --down-only
run synth $S edits --down-only
run real $R spurious --shrinkers area,pil_bilinear,cv_linear,pil_bicubic,pil_lanczos,lanczos_linear,vips
run synth $S usm
run real $R edits --factors 2,2.5,3
run synth $S heavy
run synth $S codec
run real $R heavy
run real $R usm --only real_peppercarrot_cover,real_peppercarrot_witches,real_hokusai_hodogaya,real_lion_appel,real_kitty_screenshot
run real $R codec
run synth $S linear
run real $R linear
run synth $S jpegqs --only synth_flatcolor,synth_lineart,synth_manga,synth_painterly
run real $R jpegqs --only real_peppercarrot_cover,real_peppercarrot_witches,real_hokusai_hodogaya,real_lion_appel
echo "=== done $(date +%H:%M:%S)"
