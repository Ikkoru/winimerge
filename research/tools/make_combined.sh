#!/bin/bash
# Merge the alignment and scaling branches in a scratch worktree, resolve the add/add conflicts,
# add the one integration line, then run the MinGW syntax check and the Linux unit tests.
set -e
REPO=/home/user/winimerge
WT=${WT:-/tmp/claude-0/-home-user/c93e777e-edee-5658-827e-7ebd2f76571d/scratchpad/wim-combined}
cd $REPO
git worktree remove --force $WT 2>/dev/null || true
git branch -D trial-combined 2>/dev/null || true
git worktree add -f -b trial-combined $WT claude/trusting-brown-3d75mh-align >/dev/null
cd $WT
git merge --no-edit claude/trusting-brown-3d75mh-scale >/dev/null 2>&1 || true
python3 - <<'PY'
import subprocess, sys
sys.path.insert(0, '/home/user/research/tools')
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
R('src/WinIMergeLib/ImgMergeWindow.hpp', "(alignment));\n\tIMAGE_SCALING_MODE GetImageScalingMode() const override", "(alignment));\n\t\tInvalidate();\n\t}\n\n\tIMAGE_SCALING_MODE GetImageScalingMode() const override")
R('src/WinIMerge/WinIMerge.cpp', "(wmId - ID_VIEW_ALIGNMENT_TOP_LEFT));\n\t\tcase ID_VIEW_SCALING_NONE:", "(wmId - ID_VIEW_ALIGNMENT_TOP_LEFT));\n\t\t\tbreak;\n\t\tcase ID_VIEW_SCALING_NONE:")
R('src/WinIMerge/WinIMerge.rc', 'ID_VIEW_ALIGNMENT_BOTTOM_RIGHT\n        POPUP "Size Mat&ching"', 'ID_VIEW_ALIGNMENT_BOTTOM_RIGHT\n        END\n        POPUP "Size Mat&ching"')
R('src/WinIMergeLib/ImgDiffBuffer.hpp', "\t\tm_imageScalingMode = mode;\n\t\tCompareImages();", "\t\tm_imageScalingMode = mode;\n\t\tm_alignImagesPending = true;\n\t\tCompareImages();")
PY
! grep -rn "^<<<<<<<\|^>>>>>>>" src/ || { echo "unresolved conflicts"; exit 1; }
git add -A src && git -c user.name=Claude -c user.email=noreply@anthropic.com commit -q -m "Merge image alignment and image scaling" && echo "merged: $(git log --oneline -1)"
/home/user/research/tools/mingw-syntax-check.sh $WT | tail -1
cd /home/user/research/tools/winimerge-linux-test
for t in test_alignment.cpp test_scaling.cpp test_combined.cpp; do OUTDIR=/tmp/claude-0/-home-user/c93e777e-edee-5658-827e-7ebd2f76571d/scratchpad/scaletest ./build.sh $WT $t 2>&1 | tail -1; done
