#!/bin/bash
# Add the down_matched8a rows (matched shrink with the area-averaging candidate) to runs made before it existed.
cd "$(dirname "$0")"
ROOT=${RESEARCH_DIR:-$(cd .. && pwd)}   # the research folder (this script's parent folder)
# FREEIMAGE_LIB: optional, WinMerge's FreeImage fork as a .so (README); the system libfreeimage is used otherwise
fill() { local tag=$1 img=$2; shift 2; echo "=== fill $* ($tag) $(date +%H:%M:%S)"; python3 -W ignore study.py run "$@" --images "$img" --tag "$tag" --jobs ${JOBS:-2} --down-only 2>&1 | grep --line-buffered -v Fontconfig; }
S=$ROOT/testset/large
R=$ROOT/testset/large_real
fill synth $S spurious
fill synth $S edits
# the real spurious run was started before the area candidate existed: wait until it is finished
while pgrep -f "study.py run spurious --shrinkers" >/dev/null; do sleep 15; done
fill real $R spurious --shrinkers area,pil_bilinear,cv_linear,pil_bicubic,pil_lanczos,lanczos_linear,vips
echo "=== done $(date +%H:%M:%S)"
