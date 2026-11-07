# Random stress test logs (2026-11-07)

`tools/winimerge-linux-test/fuzz/run.sh <tree> <mode> 400 7` on each tree, after upstream was merged into the
branches. Same seed everywhere, so the same operation sequences ran on every tree (the options a tree lacks are
skipped). The last lines of each log list the crash sites (function, `file:line`, last operation).

| Log | Tree | Mode | Crashes | Sites |
|---|---|---|---|---|
| `master-da639cd.txt` | old upstream master (the forks' `master`) | none | 125 | paste (`PasteImageInternal`), per-pixel copy, row-insertion copy, column delete, three-way horizontal |
| `master-10e78f7.txt` | upstream master | none | 46 | per-pixel copy, row-insertion copy (two statements), three-way horizontal |
| `fix-bounds-4b72dd6.txt` | `-fix-bounds` | none | 46 | the same as upstream master |
| `align-65fa6a8.txt` | `-align` | align | 40 | the same as upstream master |
| `scale-d703ec8.txt` | `-scale` | scale | 40 | per-pixel copy, row-insertion copy, three-way horizontal |
| `follow-15cadcb-both.txt` | `-follow` | both (alignment and scaling) | 33 | per-pixel copy, row-insertion copy, three-way horizontal |
| `follow-15cadcb-follow.txt` | `-follow` | follow (both plus Follow View) | 32 | the same as `both` |

Sites by statement (line numbers differ per tree): the per-pixel `memcpy` in `CopyDiffInternal()` (rotation
90°/270° with insertion/deletion detection), the row/column-insertion `memcpy` there (ghost lines, narrower
row), and `Make3WayLineDiff(..., compfunc02)` in `PreprocessImages()` (three panes, horizontal detection). No
branch adds a site; upstream's #41 removed the paste crash (and the column-delete one seen on `da639cd`).
Crash counts are per operation sequence and depend on which options a tree has, so compare sites, not counts.
