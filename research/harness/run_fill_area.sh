#!/bin/bash
# Add the down_matched8a rows (matched shrink with the area-averaging candidate) to runs made before it existed.
cd "$(dirname "$0")"
export FREEIMAGE_LIB=${FREEIMAGE_LIB:-/tmp/claude-0/-home-user/c93e777e-edee-5658-827e-7ebd2f76571d/scratchpad/lib/libfreeimage-3.19.0.so}
fill() { local tag=$1 img=$2; shift 2; echo "=== fill $* ($tag) $(date +%H:%M:%S)"; python3 -W ignore study.py run "$@" --images "$img" --tag "$tag" --jobs ${JOBS:-2} --down-only 2>&1 | grep --line-buffered -v Fontconfig; }
S=/home/user/research/testset/large
R=/home/user/research/testset/large_real
fill synth $S spurious
fill synth $S edits
# the real spurious run was started before the area candidate existed: wait until it is finished
while pgrep -f "study.py run spurious --shrinkers" >/dev/null; do sleep 15; done
fill real $R spurious --shrinkers area,pil_bilinear,cv_linear,pil_bicubic,pil_lanczos,lanczos_linear,vips
echo "=== done $(date +%H:%M:%S)"
