# Hand-off: where everything is and what to do next

Written at the end of the 2026-10-14 session for whoever continues (you or a local Claude session);
updated 2026-11-06 (upstream merged into every branch, Follow View added on the `-follow` branches) and
2026-11-07 (docs checked against the code and data, eye-check marks saved to your account, section
"Moving to a local session"). Nothing was posted upstream (WinMerge/winimerge, WinMerge/winmerge);
everything lives in the Ikkoru forks.

## Branches and pull requests

| Repo (fork) | Branch | What | Draft PR |
|---|---|---|---|
| Ikkoru/winimerge | `claude/trusting-brown-3d75mh-align` | Image alignment (9 anchors, e.g. centre): library commit, WinIMerge.exe menu commit, undo/redo/paste placement commit | https://github.com/Ikkoru/winimerge/pull/1 |
| Ikkoru/winimerge | `claude/trusting-brown-3d75mh-scale` | Size matching (whole-number NN / Lanczos3 / shrink with matched filter): library commit, menu commit, area-averaging commit | https://github.com/Ikkoru/winimerge/pull/2 |
| Ikkoru/winimerge | `claude/trusting-brown-3d75mh-fix-bounds` | Bug fix: Delete in a 90°/270° rotated, non-square image (heap overflow; still on upstream `master` after #41, which fixed the plain cases) | https://github.com/Ikkoru/winimerge/pull/3 |
| Ikkoru/winimerge | `claude/trusting-brown-3d75mh` | This research folder (`research/`), no code changes | – |
| Ikkoru/winmerge | `claude/trusting-brown-3d75mh-align` | Image > Image Alignment menu + `Settings/ImageAlignment` | https://github.com/Ikkoru/winmerge/pull/1 |
| Ikkoru/winmerge | `claude/trusting-brown-3d75mh-scale` | Image > Size Matching menu + `Settings/ImageScalingMode` | https://github.com/Ikkoru/winmerge/pull/2 |
| Ikkoru/winimerge | `claude/trusting-brown-3d75mh-follow` | Alignment + scaling merged (with the integration change and upstream), plus **Follow View (Scaled Images)**: a 10th alignment that lines up the content under the window's centre in every scaled pane, 0.5 s after scrolling, zoom or a resize stops | – (not opened yet) |
| Ikkoru/winmerge | `claude/trusting-brown-3d75mh-follow` | Both WinMerge menus merged, plus Image > Image Alignment > Follow View (Scaled Images); pairs with a DLL built from the WinIMerge `-follow` branch | – (not opened yet) |
| both | `claude/trusting-brown-3d75mh-combined` | Superseded by `-follow` (the same merge, made before upstream was merged in); kept for reference | – |

The branches started from upstream `master` (WinIMerge `da639cd`, WinMerge `ea828d5`). On 2026-11-06
upstream's newer `master` (WinIMerge `10e78f7`: FreeImage as a submodule, #41 paste/delete past the image,
#42 copy into the extended area; WinMerge `179a02a`, 108 commits from 2.16.59 on, translations, splitter
memory) was merged into every branch (merge commits, no rebase; conflicts in `PasteImage`,
`CopyDiffInternal` and `DeleteRectangle`, resolved and re-tested). The forks' own `master` is still at the
old commits, so the fork PRs' diffs also show upstream's changes until "Sync fork" is pressed on each
fork's GitHub page (nothing was pushed to `master`). The fork PRs are review copies. Texts for the upstream PRs and an
optional comment for WinMerge issue #1916 are in `notes/upstream-drafts.md`.

The two WinIMerge branches are independent. Merged together they need the conflict resolution in
`tools/make_combined.sh` (both append to the same enum/interface/menu) plus one change: in
`ScaleImages()`, set `m_alignImagesPending = true` when a pane's scale differs from the previous value;
`tools/winimerge-linux-test/test_combined.cpp` tests the combination.

## What was verified, and what was not

- Verified on Linux: the diff/merge buffer (`ImgDiffBuffer.hpp`, `ImgMergeBuffer.hpp`) compiled with g++
  against FreeImage and unit-tested (`tools/winimerge-linux-test`: alignment 155 checks, scaling 158,
  combined 30, bounds fix 10 + 3 (rotated image), copy into the extended area 6 + 7 (scaled panes),
  follow view 44, all under AddressSanitizer, all re-run on 2026-11-07 on the merged branches);
  WinIMergeLib.cpp, WinIMerge.cpp and both .rc files compile with MinGW i686
  (`tools/mingw-syntax-check.sh`, syntax only).
- An independent review (a separate agent) ran ~2,500 random edit sequences under AddressSanitizer on
  both branches: no new crash sites; with the options at their defaults, results are bit-identical to
  master. Its real findings were fixed (see the PR descriptions); its fuzzer is kept in
  `tools/winimerge-linux-test/fuzz/` (README there). A re-run on the
  final commits (400 sequences each on align, scale and master, same seed) hit only crash sites that master
  has too (the pre-existing bugs below). Re-run on the merged trees, and on `-follow` with Follow View
  operations added (`fuzz/run.sh <tree> follow`, 400 sequences, seed 7, 2026-11-07): every branch hits only
  statements upstream `master` (`10e78f7`) crashes on too (the per-pixel and row/column-insertion `memcpy` in
  `CopyDiffInternal`, and the three-way horizontal `Make3WayLineDiff`, reported as `PreprocessImages`);
  logs and a table in `results/fuzz/`.
- **Not verified**: an MSVC build, running WinIMerge.exe or WinMerge on Windows, and the WinMerge (MFC)
  changes at all beyond reading them.

## Before submitting upstream: build and try it on Windows

WinIMerge: since upstream made FreeImage a submodule, run `git submodule update --init` once after
checking out a branch. Open `WinIMerge.sln` in Visual Studio 2022 (or run `BuildBin.cmd x64`), build Release x64,
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
8. `-follow` branch: Enlarge by Whole Number with a 2.5× copy (shown at 2×, so 80 % of the large size),
   View > Image Alignment > Follow View. Scroll to a corner and stop: after half a second the smaller image
   jumps so that the content in the middle of the window matches; the marks follow. Zoom and resize the
   window: the same. Next/Previous Difference must not re-align afterwards (the timer is stopped there).
   With None or a whole ratio (nothing smaller than the canvas) it behaves like Center. Shift+arrow nudges
   stay on top.

WinMerge: run `DownloadDeps.cmd`, then replace the downloaded `Build\x64\Release\WinIMerge\WinIMergeLib.dll`
with the one built from the WinIMerge branch (WinIMerge's build writes it to the same relative path,
`Build\x64\Release\WinIMerge\WinIMergeLib.dll`). To try both features at once, build the two
`claude/trusting-brown-3d75mh-follow` branches together (their interface methods are in the same
order; a DLL and a WinMerge built from different branch pairs would call the wrong methods). Build WinMerge (`WinMerge.sln`, Release x64), then check Image > Image Alignment /
Size Matching, that the choice is remembered after restarting, and that the menus show the radio mark.

## Upstream order (see notes/upstream-drafts.md for the texts)

0. WinIMerge bug fix (rotated Delete, still open upstream after #41; text updated in fork PR #3).
1. WinIMerge alignment PR and scaling PR (either order; the second needs the trivial rebase above).
1b. Follow View, after both are in (it needs scaling to have anything to follow and extends the alignment
   enum): commit `15cadcb` of `-follow` (the rest of that branch is the two features merged), and in WinMerge
   `02af0c2` (text in `notes/upstream-drafts.md` 2c and 4b).
2. After the maintainer publishes a WinIMerge release with the new methods: the two WinMerge PRs
   (they call methods a pre-release DLL does not have, which would crash).
3. New menu strings go through the translation files (the maintainer usually regenerates them).

## Possible follow-ups (measured, not implemented)

- ~~Round trip~~ (REPORT §4.12): dropped after the follow-up (§10.1). Its gain was WinMerge's block
  size; the matched shrink with Diff Block Size 8/k does as well.
- ~~Alignment that follows the view centre~~: implemented as Follow View on the `-follow` branches
  (2026-11-06), with your three answers: it jumps into place after 0.5 s without scrolling, zooming or
  resizing (a slide would rebuild the canvas-sized composite every frame, ~0.5 s each at 24 megapixels;
  the re-comparison at the jump takes ~0.1 s at 2 megapixels and 1–2 s at 24), next/previous-difference
  navigation does not trigger it, and it acts only on scaled panes (with Size Matching None the panes
  stay centred). The offset is t × (canvas size − image size), t = the window centre's position across the
  canvas (Left/Center/Right are t = 0, ½, 1). REPORT §8; the feel still needs trying on Windows.
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

## Pre-existing upstream bugs found (status as of 2026-11-07)

1. Copying a difference that lies right of or below a smaller image enlarges it, but the new columns/rows
   stay empty on the first click (`CopyDiffInternal()` checks positions against the old preprocessed size).
   Fixed upstream by #42; the scale branch combines it with its scaled-position check, so a scaled pane is
   never extended (`test_copy_extend.cpp`, `test_copy_extend_scaled.cpp`).
2. Undo after a copy that enlarged an image to the left/top restored the bitmap but not `m_offset`
   (fixed in the alignment PR's third commit).
3. Delete/Paste outside the image (crash): upstream #41 fixed the plain cases; Delete in a 90°/270°
   rotated non-square image still overflows upstream (the clamp runs before the rotation), fixed in PR #3.
4. Crashes found by the random test, not fixed: rotation 90°/270° + insertion/deletion detection +
   CopyDiff (`ConvertToRealPos()` uses the rotation-aware `GetImageWidth()/GetImageHeight()` on the
   already rotated image); row insertion with ghost lines copying `dst.width()*4` bytes from a narrower
   row; three-way compare with horizontal insertion/deletion detection (`compfunc02` compares rows by
   column index).

## Moving to a local session

Everything that matters is pushed; the cloud container (with its build outputs and worktrees) is not
needed. To continue on your PC:

1. **Code**: clone the forks and check out the branches above. Add the upstream remotes for later merges
   (`git remote add upstream https://github.com/WinMerge/winimerge.git`, same for winmerge). In WinIMerge,
   run `git submodule update --init` (FreeImage is a submodule since upstream `10e78f7`).
2. **Research folder**: either unzip `winmerge-image-scaling-research.zip`, or check out branch
   `claude/trusting-brown-3d75mh` of Ikkoru/winimerge and use its `research/` folder. In the git copy the
   CSVs are gzip-compressed and images and binaries are left out: run `gunzip research/results/*.csv.gz`
   (the scripts read plain `.csv`), then follow `harness/README.md` (Python packages, FreeImage, optional
   libjxl and jpegQS builds; `harness/synth.py` and `make_real_crops.py` recreate the test images).
3. **Tools** (`tools/`): set `WINIMERGE_DIR` to your winimerge clone for `mingw-syntax-check.sh`,
   `make_combined.sh` and `winimerge-linux-test/build.sh` (they default to this container's
   `/home/user/winimerge`); `sync_research.py` takes `RESEARCH_REPO` (a checkout of the research branch) and
   `make_zip.sh` an output path. The Linux unit tests and the MinGW check need Linux or WSL.
4. **Your eye-check marks** live in two places:
   - in the browser where you made them (its local storage for that page; no other program or session can
     read it), and
   - from now on also in your Claude account: both pages (round 1
     https://claude.ai/artifact/6VCaQkq5egCxeAi9tqepCp, round 2
     https://claude.ai/artifact/AZuXdaiba6Qw86YBqfJtyn) save the marks to the page's own storage when they
     are open on claude.ai or in the Claude app, and on first opening they copy over the marks already in
     that browser. **Open each page once in the same browser (or the Claude app's built-in browser) where
     you marked**; the line above "Your marks" then says "saved … in your Claude account (N entries)".
   - A Claude session signed in to the same claude.ai account and offering the Artifact tools (cloud
     sessions do; Claude Code on your PC does when signed in with that account) reads them with the
     `ArtifactData` tool: `action: "get"`, the page's URL, `collection: "marks"`, `doc_id: "round2"` (round 2)
     or `"round1"` (round 1). The document holds `marks` (by trial or case and view: `edit`/`x`/`y`/`used`
     for blind trials, `worse` for "which copy is cleaner", `spur` for filters), `entries` and `updated`.
     The truth for round 2 is in `eyecheck2/truth.json` (by trial id and case id).
   - Fallback, if a session has no Artifact tools: the "Copy marks" button gives the same JSON to paste
     into the chat.
5. **Things only you can do**: press "Sync fork" on both forks' GitHub pages (so the PR diffs show only our
   changes), build and try the branches on Windows (checklist above), finish and send round 2 of the eye
   check, and decide when to open the `-follow` PRs and when to submit upstream.

**Decisions so far** (so a new session does not reopen them): nothing is posted upstream yet, and the fork
PRs are drafts that you discuss here rather than on GitHub; no new PRs without asking; branches use the prefix
`claude/trusting-brown-3d75mh`; the round trip is dropped; no unsharp-mask or jpegQS option in WinMerge;
Follow View jumps (no slide), pauses during difference navigation, and acts on scaled panes only; for
choosing which copy to keep, judge restored copies at the smaller size (`keep_check.py`).

## Research

`README.md` (index), `REPORT.md` (the study), `DISCOVERIES.md` (findings log), `harness/README.md` (how to
rebuild the tools and rerun everything, including on your own image pairs), `eyecheck/index.html`
(flip page, works offline; also published privately at https://claude.ai/artifact/6VCaQkq5egCxeAi9tqepCp).
The experiments ran through `harness/run_chain3.sh` and `harness/run_chain4.sh` (logs in `results/`); every
run is resumable, so rerunning a chain only fills in what is missing. Side experiments: `roundtrip_test.py`,
`im_spotcheck.py`, `chroma_test.py`. Follow-up round by comparison goal (REPORT §10): `tiny_edits.py`,
`blocksize_check.py`, `spot_check.py`, `cr_vs_l3.py`, `pixelart_test.py`, `compression_test.py`,
`jpeg_history.py` (`results/tables_followup.md`), the round-2 flip page `eyecheck2/index.html` (published privately at
https://claude.ai/artifact/AZuXdaiba6Qw86YBqfJtyn), and two tools for your own files: `keep_check.py`
(keep the smaller copy too?) and `jpeg_history.py FILE.jpg` (saved before at a lower quality?). The random
stress test's logs per branch are in `results/fuzz/`.
