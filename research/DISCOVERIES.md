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
  Fix inside WinIMerge: convert to `FIT_RGBAF` (`FreeImage_ConvertToRGBAF`), rescale, round once.
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

