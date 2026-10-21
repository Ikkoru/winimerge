# Hand-off: where everything is and what to do next

Written at the end of the 2026-10-14 session for whoever continues (you or a local Claude session).
Nothing was posted upstream (WinMerge/winimerge, WinMerge/winmerge); everything lives in the Ikkoru forks.

## Branches and pull requests

| Repo (fork) | Branch | What | Draft PR |
|---|---|---|---|
| Ikkoru/winimerge | `claude/trusting-brown-3d75mh-align` | Image alignment (9 anchors, e.g. centre): library commit, WinIMerge.exe menu commit, undo/redo/paste placement commit | https://github.com/Ikkoru/winimerge/pull/1 |
| Ikkoru/winimerge | `claude/trusting-brown-3d75mh-scale` | Size matching (whole-number NN / Lanczos3 / shrink with matched filter): library commit, menu commit, area-averaging commit | https://github.com/Ikkoru/winimerge/pull/2 |
| Ikkoru/winimerge | `claude/trusting-brown-3d75mh-fix-bounds` | Bug fix on master: Delete/Paste outside the image (crash) | https://github.com/Ikkoru/winimerge/pull/3 |
| Ikkoru/winimerge | `claude/trusting-brown-3d75mh` | This research folder (`research/`), no code changes | – |
| Ikkoru/winmerge | `claude/trusting-brown-3d75mh-align` | Image > Image Alignment menu + `Settings/ImageAlignment` | https://github.com/Ikkoru/winmerge/pull/1 |
| Ikkoru/winmerge | `claude/trusting-brown-3d75mh-scale` | Image > Size Matching menu + `Settings/ImageScalingMode` | https://github.com/Ikkoru/winmerge/pull/2 |
| Ikkoru/winimerge | `claude/trusting-brown-3d75mh-combined` | **Testing only**: alignment + scaling merged, with the integration change | – |
| Ikkoru/winmerge | `claude/trusting-brown-3d75mh-combined` | **Testing only**: both WinMerge menus merged; matches a DLL built from the WinIMerge combined branch | – |

All branches are based on upstream `master` (WinIMerge `da639cd`, WinMerge `ea828d5`). The fork PRs are
review copies against the forks' own `master` (identical to upstream). Texts for the upstream PRs and an
optional comment for WinMerge issue #1916 are in `notes/upstream-drafts.md`.

The two WinIMerge branches are independent. Merged together they need the conflict resolution in
`tools/make_combined.sh` (both append to the same enum/interface/menu) plus one change: in
`ScaleImages()`, set `m_alignImagesPending = true` when a pane's scale differs from the previous value;
`tools/winimerge-linux-test/test_combined.cpp` tests the combination.

## What was verified, and what was not

- Verified on Linux: the diff/merge buffer (`ImgDiffBuffer.hpp`, `ImgMergeBuffer.hpp`) compiled with g++
  against FreeImage and unit-tested (`tools/winimerge-linux-test`: alignment 155 checks, scaling 158,
  combined 30, bounds fix 10, all also under AddressSanitizer); WinIMergeLib.cpp, WinIMerge.cpp and both
  .rc files compile with MinGW i686 (`tools/mingw-syntax-check.sh`, syntax only).
- An independent review (a separate agent) ran ~2,500 random edit sequences under AddressSanitizer on
  both branches: no new crash sites; with the options at their defaults, results are bit-identical to
  master. Its real findings were fixed (see the PR descriptions); its fuzzer is kept in
  `tools/winimerge-linux-test/fuzz/` (README there). A re-run on the
  final commits (400 sequences each on align, scale and master, same seed) hit only crash sites that master
  has too (the pre-existing bugs below).
- **Not verified**: an MSVC build, running WinIMerge.exe or WinMerge on Windows, and the WinMerge (MFC)
  changes at all beyond reading them.

## Before submitting upstream: build and try it on Windows

WinIMerge: open `WinIMerge.sln` in Visual Studio 2022 (or run `BuildBin.cmd x64`), build Release x64,
run `Build\x64\Release\WinIMerge\WinIMerge.exe`. Manual checklist:

1. Open a picture and a smaller copy of it (File > Open, or `WinIMerge.exe big.png small.png`).
2. View > Image Alignment > Center: the smaller image moves to the middle; Top Left restores today's view.
   Try a few anchors with Adjust Offset dragging and Shift+arrows (the nudge is kept on top).
3. View > Size Matching > Shrink to Smallest (Matched Filter): the larger image becomes the size of the
   smaller one; for a copy made by a resizer, almost nothing is marked (raise Ignore Color Difference to
   32–64 for JPEG copies). The status bar position should refer to the original pixels.
4. Enlarge by Whole Number: with a 2× or 3× copy the copy is enlarged with square pixels; with a 1.5×
   copy nothing changes (expected). Enlarge to Largest: smooth enlargement to the large size.
5. With a mode on: Copy to Right/Left on a difference (in the two smooth modes, copying *into* the
   resampled pane does nothing by design; copying out of it makes the difference disappear), Undo,
   rotate one image (Image > Rotate), toggle Insertion/Deletion Detection, zoom, Blink, Overlay modes,
   and save (the original, unscaled image must be saved). Switch back to None.
6. With alignment Center: copy a difference from the larger image's left margin into the smaller one
   (it grows to the left), then Undo and Redo: the image must stay where it was / where the copy left it.
   Paste an image from the clipboard into the centred image: it should appear on its top-left corner.
7. Three-way compare with three sizes.

WinMerge: run `DownloadDeps.cmd`, then replace the downloaded `Build\x64\Release\WinIMerge\WinIMergeLib.dll`
with the one built from the WinIMerge branch (WinIMerge's build writes it to the same relative path,
`Build\x64\Release\WinIMerge\WinIMergeLib.dll`). To try both features at once, build the two
`claude/trusting-brown-3d75mh-combined` branches together (their interface methods are in the same
order; a DLL and a WinMerge built from different branch pairs would call the wrong methods). Build WinMerge (`WinMerge.sln`, Release x64), then check Image > Image Alignment /
Size Matching, that the choice is remembered after restarting, and that the menus show the radio mark.

## Upstream order (see notes/upstream-drafts.md for the texts)

1. WinIMerge alignment PR and scaling PR (either order; the second needs the trivial rebase above).
2. After the maintainer publishes a WinIMerge release with the new methods: the two WinMerge PRs
   (they call methods a pre-release DLL does not have, which would crash).
3. New menu strings go through the translation files (the maintainer usually regenerates them).

## Possible follow-ups (measured, not implemented)

- ~~Round trip~~ (REPORT §4.12): dropped after the follow-up (§10.1). Its gain was WinMerge's block
  size; the matched shrink with Diff Block Size 8/k does as well.
- **Alignment that follows the view centre** (your idea, estimated, not implemented): for whole-number
  NN at a factor like 2.5× (the copy shown at 80 %), place each smaller image so that the content under
  the middle of the window lines up in every pane, re-aligning 0.5 s after scrolling, wheel, zoom or a
  resize stops. The offset is t × (W − w), with t the window centre's position across the largest image
  (0 at the left edge, 1 at the right): the existing Left/Center/Right anchors are t = 0, ½, 1, so it is a
  continuous version of `AlignImages()`. Needs a 10th alignment choice, a one-shot timer (WinIMerge
  already uses timers for blinking) restarted from `ChildWnd_OnHVScroll()` and zoom/resize, and a
  re-comparison when it fires: ~0.1 s for 2-megapixel pictures, 1–2 s for 24 megapixels (single thread,
  measured with `test_timing.cpp` under load), nothing while scrolling. About 100 lines in the library
  plus a menu item per app; the offset math can be unit-tested on Linux, the feel needs Windows. Open
  questions: jump after the pause or slide while scrolling (marks recomputed at the pause); pause it
  during next/previous-difference navigation; also offer it with Size Matching None.
- **A point-sampling candidate for the matched shrink** (REPORT §10.2): thumbnails made with nearest
  neighbour (Pillow NEAREST) are reproduced by no current candidate; point sampling at the common phases
  would make pixel-art thumbnails exact.
- **Linear-light candidate for the matched shrink** (REPORT §4.11): copies resized in linear light are the
  matched shrink's main failure (threshold ~70–80); a Lanczos3 candidate resampled between two gamma
  conversions (FreeImage's float path) would reproduce them exactly. Only worth it if such copies are
  common in your collection.
- **A threshold above 64**: JPEG q60 copies need ~80–95; WinMerge's menu stops at 64, but the option
  (`Settings/ImageColorDistanceThreshold`, × 1000) accepts up to 442. A "96" or "128" menu item, or a
  free value on the options page, would be a small separate WinMerge PR.

## Pre-existing upstream bugs found (not fixed in these PRs)

1. Copying a difference that lies right of or below a smaller image enlarges it, but the new columns/rows
   stay empty on the first click (`CopyDiffInternal()` checks positions against the old preprocessed size).
2. Undo after a copy that enlarged an image to the left/top restored the bitmap but not `m_offset`
   (fixed in the alignment PR's third commit).
3. Delete/Paste outside the image (crash): fixed in the bug-fix PR #3.
4. Crashes found by the random test, not fixed: rotation 90°/270° + insertion/deletion detection +
   CopyDiff (`ConvertToRealPos()` uses the rotation-aware `GetImageWidth()/GetImageHeight()` on the
   already rotated image); row insertion with ghost lines copying `dst.width()*4` bytes from a narrower
   row; three-way compare with horizontal insertion/deletion detection (`compfunc02` compares rows by
   column index).

## Research

`README.md` (index), `REPORT.md` (the study), `DISCOVERIES.md` (findings log), `harness/README.md` (how to
rebuild the tools and rerun everything, including on your own image pairs), `eyecheck/index.html`
(flip page, works offline; also published privately at https://claude.ai/artifact/6VCaQkq5egCxeAi9tqepCp).
The experiments ran through `harness/run_chain3.sh` and `harness/run_chain4.sh` (logs in `results/`); every
run is resumable, so rerunning a chain only fills in what is missing. Side experiments: `roundtrip_test.py`,
`im_spotcheck.py`, `chroma_test.py`. Follow-up round by comparison goal (REPORT §10): `tiny_edits.py`,
`blocksize_check.py`, `cr_vs_l3.py`, `pixelart_test.py`, `compression_test.py`, `jpeg_history.py`
(`results/tables_followup.md`), the round-2 flip page `eyecheck2/index.html` (published privately at
https://claude.ai/artifact/AZuXdaiba6Qw86YBqfJtyn), and two tools for your own files: `keep_check.py`
(keep the smaller copy too?) and `jpeg_history.py FILE.jpg` (saved before at a lower quality?).
