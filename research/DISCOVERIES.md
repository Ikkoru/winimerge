# Discoveries log: image upscaling, downscaling, filters and tools

A running log, newest sections appended at the end. Each entry says what was measured, on
what, and how sure it is. "Measured" = run in this session with the harness in
`research/harness/`; "Read" = read in source code or docs; "Inferred" = reasoning, not tested.

Session date: 2026-10-14. Machine: Linux x86-64 container, 4 cores, no GPU.

---

## 1. FreeImage (the library WinMerge/WinIMerge uses) — resampler behaviour

- **WinMerge's FreeImage fork (3.19.0, branch `winmerge`) resamples bit-identically to
  upstream FreeImage 3.18.0** (Ubuntu's `libfreeimage3`). Measured: all six filters
  (box, bilinear, B-spline, bicubic, Catmull-Rom, Lanczos3), up and down, 8-bit and float
  paths, 258,732 output values, zero differences. So anything learned with stock FreeImage
  applies to WinMerge.
- **Building the fork on Linux**: `make -f Makefile.gnu` builds, but the `.so` fails to load
  (`undefined symbol: TIFFHashSetNew`) because `Source/LibTIFF4/tif_hash_set.c` is missing from
  `Makefile.srcs`. Adding it fixes the build. (Read + measured.)
- **Geometry**: FreeImage uses the pixel-centre convention: destination pixel `u` samples source
  coordinate `(u + 0.5) / scale` with pixel `i` spanning `[i, i+1)`; kernel weights are cut at
  the image border and renormalised; when shrinking, the kernel is widened by 1/scale
  (antialiased). (Read in `Source/FreeImageToolkit/Resize.cpp`, `CWeightsTable`.)
- **A float reference implementation with the same convention reproduces FreeImage's float
  path exactly** (max |difference| 0.0000 for Lanczos3, Catmull-Rom, Mitchell, bilinear,
  B-spline, in both directions). Measured on synthetic line art, 480×640 → 1200×1600 and
  1200×1600 → 480×640.
- **FreeImage's 8-bit path rounds and clamps to 0..255 between its two separable passes**
  (the temporary image has the source's type). Error against the float path, synthetic line art
  enlarged 2.5×: Lanczos3 max 27 levels (mean 0.109), Catmull-Rom max 13 (0.077),
  Mitchell max 7 (0.064), bilinear max 1, B-spline max 1. Kernels with negative lobes overshoot
  at hard edges; the intermediate clips the overshoot, the second pass then spreads the
  clipped value. Non-negative kernels (bilinear, B-spline) only suffer rounding. Measured.
  The way around it: convert to `FIT_RGBAF` (`FreeImage_ConvertToRGBAF`), rescale, round once
  (WinIMerge's first version did; it no longer does, see the next point).
- **…but for comparing images the clipping does not matter, and the float path is expensive.**
  Lanczos3 enlargement on the 8-bit and the float path gave the same median thresholds (T_p99 differs
  by 0.02 on average, at most ±9, over 840 pairs) and the same edit visibility (79.7 % vs 80.1 %),
  while the float path took 2.4× as long (6 → 24 MP: 1.84 s vs 0.77 s) and 0.56 GB more memory, and
  can fail to allocate in a 32-bit build. So WinIMerge's UP_SMOOTH uses the 8-bit path. Measured
  (harness + an independent review's timing of the C++ code).
- **FreeImage's box filter at a whole-number enlargement is exactly nearest neighbour**
  (each output pixel gets weight 1 from one source pixel). At non-integer factors, output pixels
  whose centre falls exactly on a source-pixel boundary average two pixels (the box test is
  `|x| <= 0.5`). Measured (×2) + read.
- **Pass order**: when the output is wider than the input (enlarging), FreeImage filters
  vertically first, then horizontally ("yx"); when shrinking, horizontally first. (Read.)

## 2. Shrinking tools — geometry quirks

- **Pillow `Image.NEAREST` shrink at even factors (2×, 4×) shifts content by half a source
  pixel** (centroid shift 0.50 px after enlarging back). At odd factors (3×) it is centred.
  Area averaging (OpenCV `INTER_AREA`), Pillow BILINEAR/BICUBIC/LANCZOS, OpenCV `INTER_LINEAR`
  and libvips `resize` all keep features in place (≤ 0.04 px). Measured with Gaussian blobs at
  sub-pixel positions, factors 1.5–4.
- **Nearest-neighbour enlargement to a non-integer size misplaces features** by about a quarter
  of a small pixel on average (centroid error 0.20–0.26 px at 1.5× and 2.5×, 0.13 px at 3× for
  non-NN shrinkers, ~0.01 px at 2× and 4×). Each output pixel is placed up to half a source pixel
  off, and source pixels become 1 or 2 (or 2 or 3) output pixels wide. Measured.

## 3. Pillow, libvips, OpenCV and other shrinkers

- **Pillow's `resize()` (LANCZOS) rounds and clamps to 8 bits between its horizontal and vertical
  pass**, exactly like FreeImage's 8-bit path: Pillow vs. a float reference differs by up to 26–27
  levels on line art (mean 0.31), but Pillow vs. an emulation with a rounded 8-bit intermediate
  (horizontal first) differs by at most 1 level (fixed-point weights). **FreeImage's 8-bit Lanczos3
  shrink matches Pillow's within 1 level.** Consequence: to reproduce a Pillow-made small copy
  (common on Python-based sites), shrink the original with FreeImage's 8-bit path, not the float
  path. Measured, synthetic line art 1200×1600 → 480×640 and 533×711.
- How sites shrink, as far as documented (from the literature notes, `notes/literature.md`):
  Danbooru uses libvips thumbnail (shrink-on-load → box → Lanczos3) in sRGB without sharpening and
  saves JPEG q85; Discord's lilliput uses OpenCV `INTER_AREA`; Cloudflare/imgix sharpen only on
  request; Pixiv, Twitter/X, Imgur do not document their filter; no documented pipeline resizes in
  linear light by default.
- Enlargement defaults (literature notes): ImageMagick `-resize` Mitchell, libvips Catmull-Rom (or
  LBB), Pillow bicubic a = −0.5 (= Catmull-Rom), OpenCV bilinear (its cubic is a = −0.75), FFmpeg
  bicubic B = 0, C = 0.6, Chrome bilinear + mipmaps.

## 4. Tools and environment notes

- **jpeg-quantsmooth (jpegQS)** builds from `github.com/ilyakurdyukov/jpeg-quantsmooth` with plain
  `make` on Linux (needs libjpeg-turbo dev headers; uses OpenMP). It writes a JPEG with all
  quantisation tables set to 1, i.e. a near-lossless store of the smoothed result. On a flat-colour
  crop saved as JPEG q85, mean absolute error vs. the source fell from 2.36 to 2.16 (`-q 3`) and
  1.25 (`-q 6`). Measured.
- **libjxl's `butteraugli_main` and `ssimulacra2`** build in ~1.5 min on 4 cores:
  `cmake -G Ninja -DJPEGXL_ENABLE_DEVTOOLS=ON -DBUILD_TESTING=OFF ...; ninja butteraugli_main ssimulacra2`
  (run `./deps.sh` first for the submodules). Butteraugli takes ~2.8 s and SSIMULACRA2 ~0.9 s per
  2.4 MP pair; NVIDIA's `flip-evaluator` (pip) ~2.8 s on CPU. Controls (image vs itself) give 0, 0
  and 100.
- **skia-python** (pip) renders anti-aliased vector art headlessly but needs `libegl1 libgl1`
  installed.
- Headless Chrome taints a canvas with images loaded from `file://`, so `getImageData` fails on a
  local page; embedding images as data URIs avoids it (used for the eye-check page).

## 5. Comparing a copy with its original (details and tables in REPORT.md §4)

- **Enlarging the small copy can never remove most spurious differences on detailed content.** On the
  synthetic set (840 unedited pairs per candidate), every enlarger (nearest, bilinear, Mitchell,
  Catmull-Rom, Lanczos2/3/4, ± unsharp mask) leaves 34–48 % of 8×8 blocks marked at WinMerge's
  colour-distance threshold 16, and 5–35 % even at 64, the highest value in WinIMerge's menu (medians
  per enlarger, factor and codec). The lost
  detail is not in the copy. Measured.
- **Comparing at the smaller size (shrink the original to the copy's size) with the filter that best
  reproduces the copy removes them**: the threshold needed to leave ≤ 1 % of blocks marked is 2–5 for
  PNG copies and 42–60 for JPEG q85 copies, against 94–326 for the enlargers (WinIMerge's rule with
  its six candidates; 2–21 without the area-averaging candidate). Measured.
- **It also finds edits far more reliably**: with the threshold set where 1 % of unedited blocks are
  marked, 98 % of edits (text, lines, faint recolours, smudges, moved regions, a 3-px dot) stay visible,
  against 80 % with Lanczos3 enlargement, 76 % with NN to the exact size and 53 % with whole-number NN
  (1008 edited synthetic pairs). The hardest edit is a faint recolour (+18/−6/−18 RGB): 89 % vs 54 %. Knowing the true resampler
  would only add one point (99 %).
  Measured.
- **An unsharp mask after Lanczos3 helps a little and hurts a little.** Full grid (σ 0.5–1.5 px ×
  25–100 %, 420 pairs per setting): the threshold needed changes by −1.8 % (σ 0.5, 75–100 %) to +20 %
  (σ 1.5, 100 %); radius 1 px at 50 % (the brief's candidate) changes it by 0 %. Every setting finds
  1–3 points more edits (89 % → 91–92 %), and every setting marks more blocks on JPEG copies (up to +4
  points at threshold 16): it sharpens the JPEG noise and adds halos, which are differences too.
  Measured.
- **Real-pair spot check** (lion photo, copy made with Pillow bicubic at 1/2, PNG): every enlarger marks
  98 % of blocks at threshold 16; shrinking the original with FreeImage Catmull-Rom marks 0.0 % (PSNR
  56 dB), because Pillow's BICUBIC is Catmull-Rom (Keys a = −0.5) with the same antialiasing as
  FreeImage's minification.

## 6. Viewing conditions (the user's setup)

- **WinMerge declares no DPI awareness**: `Src/res/WinMerge.exe.manifest` has no `dpiAware` /
  `dpiAwareness` element and `Src/Merge.vcxproj` sets no `EnableDpiAwareness` (checked on master
  `ea828d5`; WinIMerge.exe's resources neither). An unaware process is bitmap-stretched by Windows on
  a 200 % display, so at WinMerge zoom 100 % one image pixel covers 2×2 device pixels **and is
  smoothed by the compositor** (not nearest neighbour). Fine differences are then attenuated, and
  the effective pixels-per-degree for image pixels is half the monitor's. Check in Task Manager
  (Details → column "DPI awareness") for `WinMergeU.exe`; to get 1:1 pixels, set
  Properties → Compatibility → Change high DPI settings → "Override high DPI scaling behavior:
  Application" (text and UI then render at 100 % size). Read, not tested on Windows.
- **Pixels per degree** for ꟻLIP, PPD = PPI × distance(in) × tan 1°, at the user's 80–90 cm:
  BenQ RD280U (28.2", 3840×2560, 163.7 PPI): 90–101 PPD (≈96 at 85 cm) for 1:1 pixels, ≈48 when
  each image pixel covers 2×2 device pixels (zoom 2× or a DPI-unaware stretch);
  HP Pavilion 23xw (23", 1920×1080, 95.8 PPI): 53–59 PPD; Packard Bell Maestro 226DX (assuming
  21.5"/22" 1920×1080, ≈100 PPI): ≈55–62 PPD. The study evaluates ꟻLIP at 96 and 48 PPD, which
  brackets all three monitors and the 2× case.

## 7. Reproducing a website's small copy (compare-at-the-smaller-size), continued

- **FreeImage's 8-bit path reproduces Pillow's antialiased shrinks almost bit-exactly at every factor
  tested (1.25–4)**: Pillow BICUBIC ↔ FreeImage Catmull-Rom, Pillow LANCZOS ↔ FreeImage Lanczos3,
  Pillow BILINEAR ↔ FreeImage bilinear. Largest per-pixel colour distance over all factors 2.24
  (WinMerge's distance is Euclidean over R, G, B, A: √5 = one channel off by 2 and one by 1, i.e. rounding), and exactly 0 for Catmull-Rom at 1.25, 2 and 4 on
  the flat-colour image. The float path is further off (T_p99 ≈ 3–8 instead of 0–1) because Pillow,
  like FreeImage's 8-bit path, rounds to 8 bits between its two passes. Measured (synthetic images, PNG
  copies). This is why WinIMerge's DOWN_MATCHED uses the 8-bit path.
- **OpenCV `INTER_AREA` (area averaging; Discord's resizer) is reproduced by FreeImage's box filter only
  at whole-number factors.** At 2× and 4× they agree to rounding (max distance 1.7); at 1.25, 1.5,
  2.5 and 3 they differ a lot (median T_p99 35–148 on synthetic PNG copies): FreeImage samples the box
  kernel at source-pixel centres, so each source pixel gets weight 0 or 1, while area averaging gives
  partly covered pixels fractional weights. None of FreeImage's filters reproduces area averaging at
  non-integer factors, so WinIMerge's DOWN_MATCHED got its own area resampler (`ResizeImageArea`, a
  sixth candidate, ≈50 lines): separable, fractional coverage weights, float accumulation, rounded
  once. It agrees with OpenCV's `INTER_AREA` to within 1 level (0.2 % of the values differ, by
  rounding) and equals the exact block average at whole-number factors. Measured.
- **JPEG compression biases filter matching towards softer filters.** A Pillow-BICUBIC copy saved as
  JPEG q90 (terminal screenshot, 2.5×) was best matched (lowest mean absolute difference) by FreeImage's
  Mitchell filter, not Catmull-Rom, because the JPEG quantisation removes the high frequencies that
  distinguish the two. The softer pick also gave the lower T_p99 (102 vs 116), so for comparison
  purposes the "wrong" pick is the better one. Measured (one pair; the study tables have the full set).
- **Selecting the filter by mean absolute difference is a near-optimal proxy for WinMerge's block
  outcome.** It finds the true filter whenever one of the five is it (126/126 Pillow-made PNG pairs),
  and judged by the outcome itself (the threshold that leaves ≤1 % of blocks marked) it is within 1
  level of the best of the five filters in 85 % of PNG pairs and 78 % of JPEG q85 pairs, with the same
  median (10.4 vs 10.4 PNG; 50.6 vs 50.2 JPEG). Against a fixed Catmull-Rom shrink it wins 67 % of
  pairs, ties 18 %, loses 15 %. Measured, 840 synthetic pairs.
- **Whole-number NN and Lanczos3 enlargement mark about the same share of 8×8 blocks** at every
  threshold WinMerge's menu offers (NN slightly fewer at low thresholds: it keeps flat areas exactly
  flat, while a smooth filter spreads each edge's error over more blocks), **but NN's differences are
  stronger** (threshold for ≤1 % blocks: 238 vs 207 at 2×, 321 vs 242 at 3×). For pixel art NN wins
  clearly (24 vs 82). Neither comes close to comparing at the smaller size. Measured.
- **JPEG noise does not get diluted at the small size.** With JPEG q85 copies, comparing at the small
  size marks as many blocks at thresholds 8–16 as enlarging does, but at threshold 64 it drops to
  ≤0.9 % while the enlargers stay at 7–35 %. Measured.

## 8. WinIMerge implementation notes (for whoever continues the PRs)

- **Copying a difference between panes of different scale**: the copy must take the pixels the source
  pane *shows* (its scaled image) and write them into every original pixel of the destination that the
  copied canvas pixel stands for (all original pixels whose centres fall inside it). Copying the
  source's *original* pixel instead leaves the difference in place after an UP_SMOOTH copy, and writing
  only one original pixel per canvas pixel into a shrunk image leaves a dotted pattern (1 pixel in 4 at
  2×). Both were found in self-review and fixed; unit tests cover them. When the destination is the
  smaller image, a difference can remain after copying, because the smaller image cannot hold the
  detail (inherent).
- **Selection rectangles in a scaled pane** convert their edges, not their corner pixels: an edge at
  canvas position e maps to the original boundary ceil(e / scale − 0.5), so a selection contains the
  original pixels whose centres lie inside it, for any scale.
- **Menu naming**: both WinIMerge's View menu and WinMerge's Image menu already have a
  "Vector Image Scaling" submenu (the render scale of SVG/EMF images), so the new option is labelled
  "Size Matching" in the menus while the API keeps `SetImageScalingMode()`.

## 9. JPEG decoding and timing

- **JPEG chroma upsampling hardly matters for the comparison.** Decoding 4:2:0 JPEG q85 copies with
  libjpeg-turbo's default smooth ("fancy") chroma upsampling instead of `djpeg -nosmooth` (replicated
  chroma) lowered the matched shrink's threshold from 42 to 40 and the share of blocks marked at 16 from
  49 % to 44 %; Lanczos3 enlargement was unchanged (249). The default is slightly better; JPEG noise
  dominates either way. Measured, 42 synthetic pairs (`harness/chroma_test.py`).
- **With JPEG copies the matched filter is often not the one that made the copy, and that is fine.**
  The pick is the true resampler in 99–100 % of PNG pairs but only 56–73 % of JPEG q85 pairs (JPEG
  removes the detail that tells the filters apart, so a softer filter often fits better); the outcome
  stays within one level of the best pick in 80 % of JPEG pairs. Measured.
- **Comparing at the small size is also much faster.** At 1000×1500 vs 4000×6000 (WinIMerge's C++ on
  Linux, one thread): a comparison at the large size takes ~1 s, at the small size 0.07 s; switching the
  matched shrink on costs 2.2 s once (six resamples of the original), an edit of the original 0.7 s.
  Measured (`tools/winimerge-linux-test/test_timing.cpp`, under load).
- **Image borders do not distort the numbers**: dropping the outermost ring of 8×8 blocks changed the
  threshold needed by at most 0.5 (matched shrink) and 1.7 (Lanczos3). Measured, 27 pairs.
