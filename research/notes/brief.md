# Comparing images of different resolution in WinMerge: research brief

For a research session that has no access to the user's PC. It collects what earlier work found, what WinMerge does today, suggested tools and methods, where each suggestion needs testing before it is trusted, and the holes in what is known. The result will become a WinMerge pull request.

## The question

WinMerge's image compare (WinIMerge) shows two images side by side, can overlay them (XOR, alpha blend, an animated cross-fade) and marks the blocks that differ. It compares pixel by pixel at each image's own size, so a picture and its lower-resolution copy do not line up. WinMerge issue #1916 (open since 2023, no replies) asks for this: scale the images to one size.

1. Which resampling, or chain of steps, makes the smaller image the best stand-in for the larger one, so that flipping between them shows what was changed and not what resampling did?
2. Which tools measure that closeness in a way that predicts what a person sees when flipping?

The user compares duplicates found by a duplicate finder: mostly digital illustrations (anime style: line art, flat colour, gradients, painterly shading), also manga pages with screentone, and some photos. A lower-resolution copy usually comes from a website's resizing, often JPEG-compressed after. Today JPEGs go through jpegQS (QuantSmooth) and are converted to PNG before WinMerge opens them, so WinMerge's JPEG decoder plays no part; the feature may therefore receive smoothed PNGs as well as raw files. For video the user already enlarges the lower-resolution side with FFmpeg's Lanczos and shows a difference blend.

**The criterion is the user's eye.** They flip, zoom in at whole-number factors with nearest-neighbour, and look. Metrics shortlist; the eye decides. They prefer a few well-made test images to many.

## What WinMerge does today

Read in the source on 2026-10-14: WinMerge/winimerge `src/WinIMergeLib/` at `da639cd`, and WinMerge/freeimage branch `winmerge`. Check against current master before relying on any of it.

- **Comparison** (`CImgDiffBuffer::CompareImages2`, `ImgDiffBuffer.hpp`): both images at their own sizes, each at an integer offset (default 0, 0; the user can drag it). A pixel differs when any of B, G, R, A differs (colour distance threshold 0, the default), or when the Euclidean distance over B, G, R, A exceeds the threshold. A differing pixel marks its block (diff block size, default 8 px); any area outside either image counts as different. 8-connected marked blocks are the "differences" the status bar counts (`MarkDiffIndex`): regions, not pixels.
- **Overlays**: XOR; alpha blend (alpha 0.3); alpha-blend animation, which in each cycle (1000 ms by default) fades to the other image over 20 % of it, holds 30 %, fades back over 20 %, holds 30 % (`AlphaBlendImages2`); a blink of the difference marks (800 ms); vertical and horizontal wipes.
- **No scaling anywhere.** `Resize(pane, w, h)` (`ImgMergeBuffer.hpp`) changes the canvas size for editing; nothing resamples.
- **Pixels** are 32-bit BGRA, 8 bits per channel, decoded by FreeImage, or by WIC when "prefer WIC" is on (winimerge#38).
- **Where scaling could go** (a suggestion): `PreprocessImages()` already builds the `m_imgPreprocessed` images that comparison, overlays and blinking read, from the originals in `m_imgOrig32`. Scaling there leaves the originals, saving and editing alone; clicks and edits on a scaled pane would need their coordinates mapped, or editing turned off for it.
- **FreeImage's resampler** (`Source/FreeImageToolkit/Resize.cpp`, `Filters.h`): box (radius 0.5), bilinear (1), B-spline (2), bicubic as Mitchell–Netravali with B = C = 1/3 (2), Catmull-Rom (2), Lanczos3 (3). Separable, in two passes. **The intermediate image has the source's type, so for 8-bit images each pass rounds and clamps to 0–255**, which clips the overshoot that negative-lobe kernels produce at hard edges. Sample positions follow the pixel-centre convention (source centre = (u + 0.5) / scale); at the borders the kernel is cut and its weights renormalised. It also resamples float images (FIT_RGBF, FIT_RGBAF), with no 0–255 clamp between the passes.

## What earlier work found

Each item says what it was measured on. None of it answers the question above directly.

1. **Lanczos3 followed by a light unsharp mask** (radius 1 px, 40–60 %, threshold 0) beat plain Lanczos3 on small game icons shrunk by area averaging (by 1.25, 1.5 and 1.75) and enlarged back: SSIMULACRA2 44.5 against 42.2, 45.5 against 42.9, 33.1 against 28.6, and better on Butteraugli and PSNR. 100 % overshot and scored worse than none. Not repeated on illustrations or manga.
2. **Lanczos3 beat nearest-neighbour even at exactly ×2**, by the user's eye, on manga pages enlarged ×2 and ×2.276 on a 164 PPI monitor. Nearest is only right at whole-number factors; bilinear is soft.
3. **An 8-bit intermediate between the two passes of a separable Lanczos clipped its overshoot**: the maximum error on line art was 25–28 levels, and 1 after the intermediate moved to half-float; at exactly ×2 the mean error went from 0.122 to 0.003. FreeImage has such an intermediate (above).
4. **Coordinates held in 16-bit floats** made a GPU Lanczos drift half a pixel beyond 1024 px, while its self-test at 12 px passed. Test geometry at real sizes.
5. **A Lanczos round trip looked close only at small comparison sizes.** On four digital illustrations 2470–4000 px wide, copies shrunk to 50 % and 25 % and enlarged back to full size (Lanczos both ways, Pillow) ranked ahead of every version of the picture (the artist's variants, work-in-progress steps, synthetic edits) for a worst-block colour difference on 64 and 128 px thumbnails, a worst-tile SSIM, Butteraugli at 512 and 1024 px and SSIMULACRA2 at 512 px; a grey SSIM on 128 px thumbnails made with bilinear-then-halving put 499 versions ahead of them. Nothing was measured at full resolution, where the lost detail shows.
6. **Metrics on that set** (telling copies from versions, a different task from this one, but the same kind of judgement): Butteraugli's max-norm separated best (with a threshold at the farthest copy, 12–25 % copies aside, it let no version through at 512 px; an earlier synthetic test found a 3× gap between duplicates and edits at 1024 px); a worst-block colour difference on 64 px thumbnails came close, at a fraction of the cost; SSIMULACRA2 separated barely; perceptual hashes, image embeddings and the learned LPIPS and DISTS failed (LPIPS put 118–645 versions ahead of the farthest compressed or resized copy).
7. **Metric pitfalls met so far**: on a manga page, whole-image SSIMULACRA2 and Butteraugli and a worst-tile SSIM ranked two JPEG cleanups in opposite order, and the worst tile matched the spot a person had objected to. A mean called an error "invisible" that was 0 on flat blocks and plainly visible on saturated edges. RMSE rewarded low-amplitude speckle. `magick compare -metric SSIM` returns a similarity on some builds and a distance on others: compare a file with itself first. The pip `ssimulacra2` port disagreed with libjxl's tool (51.9 against 84.7 on a downscaled copy); a Rust port agreed. VMAF rewards sharpening without limit.
8. **Decoders differ legitimately**: the JPEG standard allows an approximate inverse DCT, so two programs can decode one file to different pixels, most on detailed, high-quality files. WinMerge's FreeImage once decoded about 1.5 levels off libjpeg (fixed since). Decode everything once, with one decoder, to PNG.
9. **jpegQS before resizing**, on the same illustrations: JPEG copies reduced to 50, 25 and 12 % at q45–q75 gained 2.4–5.0 SSIMULACRA2 points with `-q 6`, about twice the gain at full size (1.5–3.3 at q60); at q30, `-q 3` lost up to 3 points on two of the four; `-q 6` writes 4:2:0 input out as 4:4:4; it can only undo the last save. On manga, restore-then-resample was judged the right order: an enlargement enlarges the ringing around line art too.
10. **Downscaling without a prefilter aliases**: bilinear from 4000 to 256 px samples about 2 of every 15 pixels; area averaging brought re-saved and resized copies 3–50 times closer under AntiDupl's metric.

## Suggestions to test

Each is a hypothesis with a reason; none is measured for this purpose.

1. **Kernel**: Lanczos3 or Catmull-Rom for illustrations and photos, computed with a float intermediate; Mitchell where ringing shows; B-spline and bilinear blur; nearest only for pixel art at whole-number factors. Test FreeImage's own kernels in both its 8-bit and its float path, since FreeImage's is what would ship.
2. **A light unsharp mask after enlarging** (item 1): sweep 0–100 % at radius 0.5–1.5 px. Watch for halos and for sharpened JPEG noise, both of which flash when flipping.
3. **Restore before resampling** JPEG copies: jpegQS `-q 3` and `-q 6`, then enlarge. Inside WinMerge this would add an LGPL-2.1 library; measure the gain first, and remember the user may already pass smoothed PNGs.
4. **Match the round trip instead of guessing detail.** Shrink the larger image to the smaller one's size with the kernel that best reproduces the smaller image (try each candidate, keep the one with the lowest difference at the small size), then enlarge both with the same kernel. Both panes then carry the same resampling blur, and only content and compression differ. Prediction: far fewer spurious differences than enlarging the small one alone, at the cost of showing the large image softened, so perhaps an option ("compare at the smaller resolution"). Also measure how often the match picks the kernel that really made the copy, with and without JPEG.
5. **Compare at the smaller size**: the same shrink, with the difference computed at the small size and shown zoomed. Compare with 4.
6. **Colour**: resample in gamma-encoded sRGB, as most tools do, and in linear light; decode 4:2:0 JPEG chroma with and without libjpeg's smooth ("fancy") upsampling. Either can tint edges.
7. **Learned super-resolution** (Real-ESRGAN, waifu2x and the like) as an upper bound only. It invents detail, which in a diff tool is a false difference or hides a real one, and WinMerge would have to ship a neural runtime and model files.

## Test material

- **Images**: 6–10, covering anti-aliased black line art on white, a flat-colour anime-style illustration with gradients, painterly digital art with texture, a manga page with screentone, a photo, text and interface elements, pixel art, and a synthetic zone plate. Use material whose licence allows it (CC0 or public-domain art, renders made for the purpose). The user can share a few real pairs from their own collection if asked; no public set replaces those.
- **How the small copy was made**, unknown for real copies, so vary it: area (box); bilinear with and without a prefilter (Pillow prefilters; OpenCV's `INTER_LINEAR` and GPU texture sampling do not); bicubic with Keys a = −0.5 and −0.75, and Mitchell; Lanczos3; nearest. In sRGB and in linear light; some with a sharpen afterwards.
- **Factors**: 1.25, 1.5, 2, 2.5, 3, 4, and sizes that round (4000 → 1333, odd widths), where the two axes' factors differ slightly.
- **Saved as**: PNG; JPEG at q95, 85, 75 and 60, at 4:2:0 and 4:4:4; WebP at q75 and q90.
- **Edits**, made on the large image before shrinking, as a real variant would be: small text, a thin line removed, a small recolour, a black bar, a mosaic, a smudge, an element moved 1–2 px. Size some near one pixel of the small image: below that nothing can show them, and the write-up should say where that floor lies.

## Measuring

**Harness rules.** Decode each file once, with one decoder, to PNG; do the arithmetic in float; name the file, size, chroma and quality behind every number; run controls that must return zero (an image against itself, a lossless round trip) before trusting anything else; leave out a 3–4 px border or report it separately, since libraries treat edges differently; check the geometry (pixel-centre convention, a separate scale per axis) on a synthetic grid before any metric run.

**The panel**, for how close the enlarged copy is to the large image:

| Tool | What it tells | Caveats |
|---|---|---|
| ꟻLIP (NVIDIA; `pip install flip-evaluator`, Python 3.10+) | Built to predict what a viewer notices when alternating between two images: a per-pixel error map, its mean and percentiles | Not used in this work before: check it against the user's eye first. Its pixels-per-degree setting must match how the user views (below) |
| Butteraugli (libjxl's `butteraugli_main`) | Max-norm: the worst visible spot, what catches the eye when flipping. 3-norm: overall. A distance map | Slow at full size: about 1 s per pair at 1024 px on one thread (google/butteraugli) |
| WinMerge's own outcome | Share of 8 × 8 blocks marked, and regions counted, at colour distance thresholds from 0 to about 50 | What the user will actually see; cheap to reproduce from `CompareImages2` |
| SSIMULACRA2 (libjxl's `ssimulacra2`) | One overall perceptual score | Tuned on compression artefacts; says nothing about where |
| Worst-tile SSIM, worst-block colour difference | The locality whole-image scores lack | Report the tile or block size |
| PSNR, SSIM | Comparability with super-resolution papers | Reward blur |
| LPIPS, DISTS | Only to rank learned upscalers, if tested | They reward plausible texture over the right pixels: the wrong reward for a diff tool |

**Edits must still show.** For each edited pair: at the threshold that marks at most about 1 % of the unedited twin's blocks, what share of the edit's blocks is marked. Or rank every block of every pair by its local error and count the unedited blocks that outrank the faintest edit.

**The eye check.** One HTML page that flips each pair, both as a hard flip at 2–4 Hz and with WinMerge's cross-fade timing, with nearest-neighbour zoom at 1×, 2× and 4×, for the top 3–5 candidates on 4–6 images. The user marks which show spurious differences and which hide an edit.

**Viewing condition for ꟻLIP.** The user's monitor is 164 PPI, with Windows at 200 % scaling. Pixels per degree = PPI × distance in inches × tan 1°: about 68–79 at 60–70 cm, for one image pixel per screen pixel, and half that if WinMerge at zoom 100 % draws each image pixel as 2 × 2 screen pixels on a 200 % display. Ask the user for the distance, and check how WinMerge draws at 100 % on such a display.

## Implementation check

Check the recommended chain in the code that would ship: FreeImage's resampler, both at 8 bits and through a float image. Windows' own scalers (WIC's `IWICBitmapScaler`: nearest-neighbour, linear, cubic, Fant, high-quality cubic; Direct2D's interpolation modes) need Windows: the user can run a harness. Time a typical pair (for example 1000 × 1500 enlarged to 4000 × 6000), with and without caching, since WinIMerge compares again on every option change.

## What to deliver

- The recommended default (kernel, intermediate precision, sharpening, JPEG restoration, colour space) and the options worth offering, each with its evidence, plus a one-paragraph answer the user can act on.
- Tables for every candidate × content × shrinking kernel × codec, and the eye-check page.
- The harness, able to run again on the user's own pairs: inputs from a folder, nothing fetched from the network.
- A sketch of the WinIMerge change: where scaling goes, option names, what happens to editing and saving, three-way compare.
- What was not tested, and why.

## Holes in this brief

- No measurement yet answers the question at full resolution. The only enlargement measurements are game icons at small factors, Lanczos round trips judged on thumbnails, and the user's eye on manga.
- Real copies come from unknown website pipelines (kernel, sharpening, colour conversion, chroma), which synthetic copies may not cover. Only the user has real pairs.
- The user's viewing distance, and whether WinMerge draws 1:1 on a 200 % display, are unknown.
- The WinMerge facts above were read once, on one day; FreeImage's behaviour was read, not run.
- Windows' own scalers cannot be tested off Windows.
- If one copy is also cropped, scaling cannot align it; that needs feature matching (ORB and AKAZE aligned every crop in the duplicate-finder study, at 512 px), which WinMerge does not have. Out of scope unless it falls out cheaply.
- Colour management (ICC profiles), alpha, animated images and 16-bit sources are not covered.
- Whether WinMerge's maintainers want this, and with which dependency, is unknown: issue #1916 has no reply.

## Sources

- WinMerge issue #1916: https://github.com/WinMerge/winmerge/issues/1916
- WinIMerge: https://github.com/WinMerge/winimerge (`src/WinIMergeLib/ImgDiffBuffer.hpp`, `ImgMergeBuffer.hpp`, `WinIMergeLib.h`)
- WinMerge's FreeImage fork: https://github.com/WinMerge/freeimage, branch `winmerge` (`Source/FreeImageToolkit/Resize.cpp`, `Filters.h`)
- ꟻLIP: https://github.com/NVlabs/flip
- libjxl, whose tools include `butteraugli_main` and `ssimulacra2`: https://github.com/libjxl/libjxl
- jpeg-quantsmooth: https://github.com/ilyakurdyukov/jpeg-quantsmooth
- The user's GPU Lanczos3, with a half-float intermediate and a JavaScript reference to test against: https://github.com/Ikkoru/crisp-images
- The duplicate-finder study behind items 5, 6, 9 and 10: https://github.com/Ikkoru/AntiDupl, branch `claude/inspiring-wright-e741yy`, `plan/02-comparison-modes.md`; `plan/07-settings-study.md` and its tools in `plan/tools/` once the user has pushed them.
