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
