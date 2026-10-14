# Comparing images of different resolution in WinMerge: study report

*Session of 2026-10-14. Harness, data and page in this folder; findings log in `DISCOVERIES.md`.*

<!-- RESULTS-SUMMARY -->

## 1. The question

WinMerge's image compare (WinIMerge) compares pixel by pixel at each image's own size, so a
picture and its lower-resolution copy never line up. The user compares duplicates found by a
duplicate finder (anime-style illustrations, manga, some photos); the low-resolution copy usually
comes from a website's resizing, often JPEG-compressed. Two features were requested:

1. place the smaller image in the centre instead of the top-left, and
2. enlarge the smaller image by the largest whole-number factor with nearest neighbour (NN),

with the question whether a smooth filter (e.g. Lanczos3 + a light unsharp mask) would make a
better comparison, and which filter settings are best. The brief (`notes/brief.md`, the user's
methodology document) asks for the best stand-in for the larger image, so
that flipping between the two shows what was changed and not what resampling did, measured with
tools that predict what a person sees when flipping.

## 2. Short answer

<!-- SHORT-ANSWER -->

## 3. What was tested

### 3.1 Test material

17 large originals, used at their native resolution (no image was resampled to make it "large"):

| Set | Images | Size | Notes |
|---|---|---|---|
| Synthetic (`testset/synth`, made by `harness/synth.py`) | line art, flat-colour anime-style cel shading, painterly strokes, manga page with screentone, UI/text, pixel art (×8 NN), zone plate | 1200–1600 px | Rendered with skia at the final size (vector anti-aliasing, as a drawing program renders strokes). No licence restrictions. |
| Real (`testset/real`, sources in `testset/sources/MANIFEST.md`) | Pepper&Carrot cover and "Witches" (David Revoy, CC BY 4.0), Krita anime banner (CC BY-SA 4.0), Hokusai *Hodogaya* (Met, CC0), *The Starry Night* (PD), lion photo (CC0), astronaut (NASA, PD), coffee (CC0), Kenney pixel-art tiles (CC0), kitty terminal screenshot (GPL-3.0) | 512–1920 px wide; larger sources cropped at native resolution to ≤1600×1200 | Crops chosen automatically as the most detailed window (`testset/real/CROPS.json`). Several are JPEGs already (q≈87–100). No public-domain manga page with screentone was found on the reachable hosts; the synthetic manga page stands in. |

### 3.2 How the small copies were made

Unknown for real copies, so varied (`harness/resample.py`, `SHRINKERS`):

| Shrinker | What it stands for |
|---|---|
| `area` | OpenCV `INTER_AREA` (exact area averaging; Discord's lilliput) |
| `pil_bilinear` | Pillow BILINEAR (antialiased triangle) |
| `cv_linear` | OpenCV `INTER_LINEAR` without prefilter (aliases) |
| `pil_bicubic` | Pillow BICUBIC (Keys a = −0.5 = Catmull-Rom, antialiased) |
| `pil_lanczos` | Pillow LANCZOS (Lanczos3, antialiased) |
| `mitchell` | Mitchell–Netravali B = C = 1/3 (float reference implementation) |
| `lanczos_linear` | Lanczos3 in linear light |
| `lanczos_sharpened` | Pillow LANCZOS + unsharp mask σ 0.6, 60 % |
| `vips` | libvips `resize` (Lanczos3 with shrink/reduce) |
| `nearest` | Pillow NEAREST |

Factors 1.25, 1.5, 2, 2.5, 3, 4, with the small size rounded per axis (so the two axes' factors
differ slightly, as with real copies). Saved as PNG, JPEG q95/q85/q75/q60 at 4:2:0, q85 at 4:4:4,
WebP q90/q75 (Pillow/libjpeg-turbo, decoded with the same library).

### 3.3 Edits

Applied to the large image before shrinking, as a real variant would differ (`harness/edits.py`),
each placed automatically where the image has content: small text (20 px and 11 px), a 2-px line,
a 90-px recolour (+18/−6/−18 RGB), a black bar, a 96-px mosaic, a smudge (Gaussian σ 3), a
110-px region moved 2 px, and a 3-px dot (≈1 small pixel at 3×: the detection floor).

### 3.4 Candidates (how WinIMerge could show the pair)

Enlarging the small copy to the original's size (FreeImage, the library WinMerge ships; its
8-bit path and a float path):

| Candidate | Description |
|---|---|
| `nn_int_center` / `nn_int_topleft` | NN by the largest whole-number factor (the requested feature), centred or top-left; the rest of the canvas is "missing" and counts as different, as in WinMerge |
| `nn` | NN to the exact size (uneven pixel widths at non-integer factors) |
| `sharp_bilinear` | NN by the whole-number factor, then bilinear to the exact size (CSS `image-rendering: pixelated` style) |
| `fi_bilinear`, `fi_bspline`, `fi_mitchell` | FreeImage filters |
| `fi_catmullrom`, `fi_lanczos3` | FreeImage, 8-bit intermediate (clips overshoot) |
| `fi_catmullrom_f`, `fi_lanczos3_f` | the same in float (`FreeImage_ConvertToRGBAF` first) |
| `ref_lanczos2_f`, `ref_lanczos4_f` | float reference implementation |
| `l3f_usm_rR_aA`, `crf_usm_…` | Lanczos3/Catmull-Rom float + unsharp mask, σ R ∈ {0.5, 0.75, 1, 1.5} px, amount A ∈ {25, 50, 75, 100} %, threshold 0 |
| `lin_lanczos3_f`, `lin_catmullrom_f` | resampled in linear light |

Comparing at the smaller size instead (shrinking the original to the copy's size):

| Candidate | Description |
|---|---|
| `down_area` | OpenCV area averaging |
| `down_fi_<k>` / `down_fi_<k>8` | FreeImage filter k (box, bilinear, B-spline, Mitchell, Catmull-Rom, Lanczos3), float / 8-bit path |
| `down_matched8` | **WinIMerge's `IMAGE_SCALING_DOWN_MATCHED`**: FreeImage's box, bilinear, Mitchell, Catmull-Rom and Lanczos3 on the 8-bit path; the one with the lowest mean absolute difference to the copy, chosen per pair |
| `down_matched` | the same choice among six filters (B-spline too) on the float path (an earlier variant; kept for comparison) |
| `down_oracle` | the shrinker that really made the copy (an upper bound) |

### 3.5 Measures

For every pair, against the large original (or, for `down_*`, the copy against the shrunk original):

- **WinMerge's own outcome**: the share of 8×8 blocks it marks (colour distance > T over R, G, B)
  at T = 0, 2, 4, 8, 16, 32, 64; regions (8-connected); and **T_p99**, the threshold that leaves
  at most 1 % of blocks marked. T_p99 is the single most practical number: the colour-distance
  setting a user would need before the diff stops being yellow everywhere.
- PSNR; worst-8×8-block mean colour distance; SSIM (global and worst 64-px tile).
- On a subset: **ꟻLIP** (NVIDIA; models flipping between two images) at 96 pixels per degree
  (the user's BenQ RD280U at 85 cm, 1:1 pixels) and 48 (2× zoom, or a DPI-unaware 200 % stretch),
  **Butteraugli** max and 3-norm, **SSIMULACRA2** (libjxl tools).
- **Edit detectability**: blocks touched by the edit (in the large image) vs. all other blocks
  (a guard ring of 3·factor+2 px around the edit is excluded). At the threshold that leaves 1 %
  (0.1 %) of blocks marked in the unedited twin pair, the share of edit blocks still marked, and
  whether any edit block is marked at all ("edit visible"); plus the number of unedited blocks
  louder than the edit's strongest block.

### 3.6 Controls and geometry checks (run first)

- Every metric returns "identical" for an image against itself (block distance 0, PSNR ∞,
  ꟻLIP 0, Butteraugli 0, SSIMULACRA2 100) — `harness/metrics.py` self-test.
- The float reference resampler reproduces FreeImage's float path exactly (max |Δ| 0.0000, five
  kernels, both directions); WinMerge's FreeImage fork resamples bit-identically to FreeImage 3.18.
- Centroids of Gaussian blobs at sub-pixel positions stay within 0.04 px through every
  antialiased shrinker and a FreeImage enlargement (pixel-centre convention everywhere), except
  Pillow NEAREST at even factors (0.5 px shift) and NN enlargement at non-integer factors.
- The WinIMerge implementation (C++) produces bit-identical output to the harness for all three
  scaling modes (Linux unit tests with the real `ImgDiffBuffer.hpp`).

<!-- RESULTS -->


## 5. Is anything other than nearest neighbour a flawed comparison?

Partly right, but the measurements turn the argument around.

**What whole-number NN does well.** Every pixel it shows is a pixel of the copy, unchanged, and
nothing is invented. That is the right view when looking *at the copy* (pixel art, checking its
compression artefacts, counting pixels), and when the copy was itself made by whole-number NN the
comparison becomes exact (no differences at all; unit-tested).

**What it does to the comparison.** WinMerge compares what is shown with the original, pixel by
pixel. The original has its edges at full resolution; the NN-enlarged copy has the same edges as
k×k staircases. So every edge in the picture differs, by up to its full contrast, and NN needs a
*higher* threshold than any smooth filter before the diff stops being yellow everywhere (section 4).
NN avoids inventing values, but it does not avoid differences: it adds them. At factors that are not
whole numbers it also leaves part of the canvas uncovered (below 2× it does nothing at all; at 2.5×
it enlarges 2× and leaves a 20 % border), and NN to the exact size makes pixels unevenly wide and
moves features by up to half a copy pixel (`DISCOVERIES.md` §2).

**What a smooth filter does.** It estimates in-between values. The estimate is wrong exactly where the
copy lost detail, but it is closer to the original than a staircase, so fewer and weaker differences
remain. Lanczos3 is the closest of the common filters by every measure used here. Still, on detailed
images about a third of all 8×8 blocks stay marked at threshold 16 whatever enlarger is used: the
detail is not in the copy, so no filter can bring it back, and an enlarged comparison can never be
clean.

**Lanczos3 + unsharp mask.** Measured over radius 0.5–1.5 px and amount 25–100 % (threshold 0): see
section 4. Sharpening moves the enlarged copy towards the original's edge contrast but also amplifies
ringing and JPEG artefacts; it does not make edits easier to find, so it is not worth a mode.

**The honest comparison is at the smaller size.** Shrink the original the way the copy was made.
Then both images went through the same resampling, and what remains is what really differs: edits
and compression noise. That is WinIMerge's `IMAGE_SCALING_DOWN_MATCHED`. The cost is that
differences smaller than one pixel of the copy cannot be seen, but the copy cannot show them anyway.

## 6. Recommendations

For the WinIMerge/WinMerge feature (implemented in the PR branches, see `notes/upstream-drafts.md`):

1. Offer **Shrink to Smallest (Matched Filter)** as the mode for resized copies, **Enlarge by Whole
   Number (Nearest Neighbor)** for pixel art and for inspecting the copy, and **Enlarge to Largest
   (Lanczos)** for viewing a small copy next to the original at the same size. Keep **None** as the
   default (today's behaviour).
2. Match the filter on FreeImage's 8-bit path (what Pillow and most libraries do), choose by the
   lowest mean absolute difference, and enlarge on the float path (no clipped overshoot).
3. No unsharp-mask option.
4. Image alignment **Center** is the useful companion when sizes still differ (crops, letterboxing,
   or a factor where whole-number NN leaves a border).

For comparing duplicates by eye (your use):

- Use *Shrink to Smallest*; it is the only mode where a clean pair looks clean.
- Set the colour-distance threshold (WinMerge: Image > Ignore Color Difference) according to how the
  copy was saved: see the threshold table in section 4. With a lossless copy a low threshold works;
  with JPEG copies the compression noise sets the floor.
- Make sure WinMerge is not bitmap-stretched by Windows (section 7), and zoom in (200 % or more) on the
  small comparison: at the copy's resolution one pixel is small on a 4K screen.

## 7. Viewing conditions

`DISCOVERIES.md` §6 has the details. In short: WinMerge declares no DPI awareness, so on a 200 %
display Windows stretches it with smoothing and one image pixel covers 2×2 device pixels; fine
differences are then attenuated. ꟻLIP was run at 96 pixels per degree (BenQ RD280U at 85 cm, 1:1
pixels) and 48 (2× stretch or zoom); the HP 23xw (≈53–59) and the Packard Bell Maestro 226DX (≈55–62)
fall between. The ranking of the candidates was the same at both (section 4).

## 8. The WinIMerge implementation in brief

- Scaling happens in `CImgDiffBuffer::PreprocessImages()` (inside the temporary rotation/flip), so the
  comparison, overlays, blinking, insertion/deletion detection and the diff map see equal-size images
  without other changes; the originals are untouched and saving, undo and edits act on them.
- Scaled images are cached (key: hash of the source and of the reference image, target size, mode),
  because `CompareImages()` runs again on every option change.
- `ConvertToRealPos()` maps a canvas pixel to the original pixel it came from; selection edges map so
  that a selection holds the original pixels whose centres lie inside it; `CopyDiff()` copies the pixels
  a scaled pane shows into every original pixel of the destination they stand for.
- The C++ output is bit-identical to this harness for all three modes (unit test + `harness/fi.py`).

## 9. What was not tested

- Copies made by Windows' own scalers (WIC Fant and high-quality cubic, Direct2D, GDI+), browsers
  (canvas `drawImage`), Photoshop ("Bicubic Sharper"), GIMP (NoHalo/LoHalo) or Paint.NET
  (supersampling): not available on Linux. WIC Fant and Paint.NET supersampling are area-averaging-like,
  which FreeImage cannot reproduce at non-integer factors (`DISCOVERIES.md` §7).
- Copies that were also cropped, padded, rotated, colour-converted (ICC profiles, gamma), resized twice
  or recompressed several times; factors above 4; very small thumbnails.
- Learned super-resolution (waifu2x, Real-ESRGAN) as an enlarger: it invents plausible detail, which is
  the opposite of what a diff needs.
- A real manga page with screentone (no freely licensed one was reachable; the synthetic page stands in).
- Your own pairs: the harness runs on them offline (`harness/compare_pairs.py`, section 10).
- The eye-check page was built and checked to work, but no person has looked through it yet; ꟻLIP,
  Butteraugli and SSIMULACRA2 stand in for the eye.
- The WinIMerge/WinMerge changes were compiled with MinGW and unit-tested on Linux, not built with MSVC
  or run on Windows.

## 10. Reproducing and running it on your own pairs

See `harness/README.md`. In short (Linux or WSL, Python 3 with numpy, opencv-python, pillow, scipy,
skia-python, flip-evaluator; FreeImage 3.18 via `FREEIMAGE_LIB`; libjxl tools for Butteraugli and
SSIMULACRA2 via `LIBJXL_TOOLS`):

```
python3 harness/compare_pairs.py FOLDER [--heavy] [--eyecheck OUTDIR]   # your own pairs
python3 harness/study.py run spurious --images testset/large --tag synth  # the study (resumable)
python3 harness/report.py && python3 harness/charts.py                    # tables and charts
python3 harness/eyecheck.py --out eyecheck                                # the flip page
```
