#!/bin/bash
# Remaining experiments, ordered by the brief's priorities. Resumable: safe to re-run after a restart.
cd "$(dirname "$0")"
ROOT=${RESEARCH_DIR:-$(cd .. && pwd)}   # the research folder (this script's parent folder)
# FREEIMAGE_LIB: optional, WinMerge's FreeImage fork as a .so (README); the system libfreeimage is used otherwise
export LIBJXL_TOOLS=${LIBJXL_TOOLS:-}   # folder with butteraugli_main and ssimulacra2 (README)
run() { local tag=$1 img=$2; shift 2; echo "=== $* ($tag) $(date +%H:%M:%S)"; python3 -W ignore study.py run "$@" --images "$img" --tag "$tag" --jobs ${JOBS:-4} 2>&1 | grep --line-buffered -v Fontconfig; }
# wait for runs started by an earlier chain (they write the same CSVs); match the python processes only
while pgrep -f "^python3 -W ignore study.py run" >/dev/null; do sleep 15; done
S=$ROOT/testset/large
R=$ROOT/testset/large_real
run synth $S usm
run synth $S heavy
run synth $S jpegqs --only synth_flatcolor,synth_lineart,synth_manga,synth_painterly
run synth $S codec
run real $R edits --factors 2,2.5,3
run real $R usm --only real_peppercarrot_cover,real_peppercarrot_witches,real_hokusai_hodogaya,real_lion_appel,real_kitty_screenshot
run synth $S linear
run real $R jpegqs --only real_peppercarrot_cover,real_peppercarrot_witches,real_hokusai_hodogaya,real_lion_appel
run real $R heavy
run real $R codec
run real $R linear
echo "=== done $(date +%H:%M:%S)"
