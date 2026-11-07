#!/bin/bash
# Merge the alignment and scaling branches in a scratch worktree, resolve the add/add conflicts,
# add the one integration line, then run the MinGW syntax check and the Linux unit tests.
# The -follow branch already contains this merge (dd3c64f, made with this script after upstream was merged
# into both branches); rerun it after changing either branch. WINIMERGE_DIR = your winimerge clone.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=${WINIMERGE_DIR:-/home/user/winimerge}
WT=${WT:-${TMPDIR:-/tmp}/wim-combined}
cd $REPO
git worktree remove --force $WT 2>/dev/null || true
git branch -D trial-combined 2>/dev/null || true
git worktree add -f -b trial-combined $WT claude/trusting-brown-3d75mh-align >/dev/null
cd $WT
git merge --no-edit claude/trusting-brown-3d75mh-scale >/dev/null 2>&1 || true
TOOLS=$HERE python3 - <<'PY'
import os, subprocess, sys
sys.path.insert(0, os.environ['TOOLS'])
from eolsafe_replace import replace_once as R
files = subprocess.run(['git','diff','--name-only','--diff-filter=U'],capture_output=True,text=True).stdout.split()
for f in files:
    data = open(f,'rb').read(); eol = b'\r\n' if b'\r\n' in data else b'\n'
    out=[]; state=None; ours=[]; theirs=[]
    for l in data.split(eol):
        if l.startswith(b'<<<<<<< '): state='o'; ours=[]; theirs=[]; continue
        if l.startswith(b'=======') and state=='o': state='t'; continue
        if l.startswith(b'>>>>>>> ') and state=='t': out+=ours+theirs; state=None; continue
        (ours if state=='o' else theirs if state=='t' else out).append(l)
    open(f,'wb').write(eol.join(out))
for f in ['src/WinIMergeLib/ImgDiffBuffer.hpp', 'src/WinIMergeLib/WinIMergeLib.h']:
    R(f, "IMAGE_ALIGNMENT_BOTTOM_RIGHT\n\tenum IMAGE_SCALING_MODE {", "IMAGE_ALIGNMENT_BOTTOM_RIGHT\n\t};\n\tenum IMAGE_SCALING_MODE {")
R('src/WinIMergeLib/ImgMergeWindow.hpp', "(alignment));\n\tIMAGE_SCALING_MODE GetImageScalingMode() const override", "(alignment));\n\t\tUpdateScrollBars();\n\t\tInvalidate();\n\t}\n\n\tIMAGE_SCALING_MODE GetImageScalingMode() const override")
# a pane whose scale changes (mode change, or an edit that changes its size) is aligned again
R('src/WinIMergeLib/ImgDiffBuffer.hpp', "\t\t\tscaled.scaleX = (w > 0) ? static_cast<double>(tw) / w : 1.0;\n\t\t\tscaled.scaleY = (h > 0) ? static_cast<double>(th) / h : 1.0;\n",
  "\t\t\tconst double scaleX = (w > 0) ? static_cast<double>(tw) / w : 1.0;\n\t\t\tconst double scaleY = (h > 0) ? static_cast<double>(th) / h : 1.0;\n\t\t\tif (scaleX != scaled.scaleX || scaleY != scaled.scaleY)\n\t\t\t\tm_alignImagesPending = true;\n\t\t\tscaled.scaleX = scaleX;\n\t\t\tscaled.scaleY = scaleY;\n")
R('src/WinIMerge/WinIMerge.cpp', "(wmId - ID_VIEW_ALIGNMENT_TOP_LEFT));\n\t\tcase ID_VIEW_SCALING_NONE:", "(wmId - ID_VIEW_ALIGNMENT_TOP_LEFT));\n\t\t\tbreak;\n\t\tcase ID_VIEW_SCALING_NONE:")
R('src/WinIMerge/WinIMerge.rc', 'ID_VIEW_ALIGNMENT_BOTTOM_RIGHT\n        POPUP "Size Mat&ching"', 'ID_VIEW_ALIGNMENT_BOTTOM_RIGHT\n        END\n        POPUP "Size Mat&ching"')
PY
! grep -rn "^<<<<<<<\|^>>>>>>>" src/ || { echo "unresolved conflicts"; exit 1; }
git add -A src && git -c user.name=Claude -c user.email=noreply@anthropic.com commit -q -m "Merge image alignment and image scaling (for testing both together)

Resolves the add/add conflicts (both branches append to the same enum,
interface and View menu) and adds the one integration change: a pane
whose scale changes is aligned again (ScaleImages sets
m_alignImagesPending).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011DaoEzRioXAZckz9AW1kyX" && echo "merged: $(git log --oneline -1)"
$HERE/mingw-syntax-check.sh $WT | tail -1
cd $HERE/winimerge-linux-test
for t in test_alignment.cpp test_scaling.cpp test_combined.cpp; do mkdir -p ${TMPDIR:-/tmp}/scaletest; OUTDIR=${TMPDIR:-/tmp}/scaletest ./build.sh $WT $t 2>&1 | tail -1; done
