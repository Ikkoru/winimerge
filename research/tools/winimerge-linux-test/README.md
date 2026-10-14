# Linux unit tests for WinIMerge's diff/merge buffer

WinIMerge's comparison and editing logic lives in header-only C++ (`ImgDiffBuffer.hpp`,
`ImgMergeBuffer.hpp`, `image.hpp`, `Diff.hpp`) that only needs FreeImage, so it builds on Linux with
g++. `ImgConverter.hpp` here is a stub for the Windows-only renderer (PDF/SVG/EMF/WIC). Nothing in the
checkout is modified: `build.sh` copies the headers to a temporary folder (and works around one
`goto` that GCC rejects in `Diff.hpp`).

```sh
sudo apt install libfreeimage-dev libfreeimageplus-dev g++
./build.sh /path/to/winimerge test_scaling.cpp           # one test against a checkout
./build.sh /path/to/winimerge                            # every test_*.cpp
EXTRA_CXXFLAGS="-fsanitize=address,undefined" ./build.sh /path/to/winimerge test_bounds.cpp
OUTDIR=/some/dir ./build.sh ...                          # where tests that write files put them
```

| Test | Needs a checkout of | What it covers |
|---|---|---|
| `test_alignment.cpp` | `claude/trusting-brown-3d75mh-align` | all nine anchors, crossed sizes, odd differences, three panes, manual offsets, rotation, insertion/deletion detection, a growing CopyDiff, Undo/Redo and re-alignment after it, invalid values, defaults equal to master (155 checks) |
| `test_alignment_undo3.cpp` | the align branch | three panes, growing copies to both sides, Undo/Redo in different orders, CopyDiff3Way (28 checks) |
| `test_scaling.cpp` | `claude/trusting-brown-3d75mh-scale` | sizes and factor rules, snapping, caching, DOWN_MATCHED finding each filter (area averaging included), the filter kept after edits, copying between scaled panes, selection mapping, undo, rotation, insertion/deletion detection; also writes the scaled panes for the harness's bit-identity check when `large.png`/`small.png` are in `OUTDIR` (158 checks) |
| `test_combined.cpp` | a tree with both features (`tools/make_combined.sh`, or the `-combined` branch) | alignment following scale changes (30 checks) |
| `test_bounds.cpp` | `claude/trusting-brown-3d75mh-fix-bounds` (crashes on master) | Delete and Paste rectangles that reach past the image (10 checks; run with AddressSanitizer) |
| `test_timing.cpp` | the scale branch | timing of the modes at 1000×1500 vs 4000×6000 (build with `EXTRA_CXXFLAGS=-O2`) |

## Random stress test (`fuzz/`)

`fuzz/fuzz.cpp` drives `CImgMergeBuffer` like the UI with random operation sequences (2 or 3 panes of
random, derived or rescaled images; every option incl. the new ones; ghost lines, rotation/flip, offsets,
CopyDiff/All/3Way, Undo/Redo, Resize, select+Delete, Paste, position mapping), each sequence in a child
process under AddressSanitizer/UBSan. The same seed runs the same sequence on every tree, so the crash
sites of a branch can be compared with `master`'s:

```sh
fuzz/run.sh /path/to/master-checkout none 400 7     # baseline
fuzz/run.sh /path/to/align-checkout  align 400 7
fuzz/run.sh /path/to/scale-checkout  scale 400 7
fuzz/run.sh /path/to/combined-tree   both  400 7
```

It ends with one line per crash site (function, `file:line`, last operation). On the final branch tips
(2026-10-14) all three trees hit only sites `master` has too: `PasteImageInternal` (fixed by the
fix-bounds branch), the per-pixel and row-insertion `memcpy` in `CopyDiffInternal`, and
`Make3WayLineDiff(..., compfunc02)` (see HANDOFF.md, pre-existing bugs). Options: `-DUI_RECTS` passes
the unclamped rectangles the UI computes to Delete/Copy, `-DSAFE_PASTE` avoids the known paste crash,
`-DNO_GHOST` leaves insertion/deletion detection off; `DIGEST=1` prints a digest of the final state per
sequence (for checking that a branch with its options at their defaults behaves exactly like `master`).
`fuzz/minimize.py fuzz_<what> <seed> <iteration>` (the binary `run.sh` leaves next to its output) drops
the steps that are not needed for a crash.
