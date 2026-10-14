# Literature and prior art: centring and upscaling in WinIMerge image compare

Compiled 2026-10-14 for the WinIMerge feature "centre the smaller image" / "upscale the smaller image to (about) the larger one's size".

**Reading key**

- **[doc]**: documented. I read it directly in official docs or in the project's own source code, which is mostly GitHub-hosted and was read in full.
- **†**: documented, but I could read it only through web-search summaries. The fetch tool reached only github.com, raw.githubusercontent.com, npm and PyPI; imagemagick.org, arxiv.org, docs.opencv.org, learn.microsoft.com, Adobe, Scooter Software and similar hosts failed DNS. Wording marked † may be paraphrased, so check the original before quoting it in a PR.
- **Inference:** my reasoning; no source states it.
- **Computed:** my own small numeric check, with the method given inline. All step-overshoot figures use the same setup:
  - a 1-D ideal step 0→1, upscaled with centre convention (output pixel *i* samples source position (*i*+0.5)/*s* − 0.5);
  - kernel weights normalised to sum to 1;
  - no clipping;
  - values in % of the step height; undershoot is symmetric.

---

## Key takeaways for the WinIMerge feature

1. **Nearest neighbour (NN) is not "the only honest choice" anywhere I looked.**
   - ImageMagick documents NN (`-sample`) as the mode where "no new colors will be added".
   - The CSS Images spec warns that at non-integer ratios NN makes "lines that were the same thickness … a pixel thinner or thicker". It therefore defines `pixelated` as NN to the nearest integer multiple, then smooth scaling for the rest. [doc]
2. **Site-made copies are rarely an integer fraction of the original.** Examples: Danbooru's 850 px sample [doc], Pixiv's 1200 px "master" (community notes), Twitter's 4096 px cap †.
   - So NN-to-match draws every low-res pixel as a flat block that is alternately ⌊s⌋ and ⌈s⌉ screen pixels wide.
   - Edges snap to the low-res grid, up to ±½ low-res pixel away from where an interpolating reconstruction puts them.
   - In a flip test this flickers along all line art. *Inference.*
3. **A fixed linear interpolator adds no information, but negative lobes overshoot.** Bilinear, cubic and Lanczos output only weighted sums of stored samples. *Computed* overshoot on a hard step at 2×:

   | Kernel | Overshoot |
   |---|---|
   | bilinear | 0 % |
   | Mitchell | 2.3 % |
   | Catmull-Rom | 7.0 % |
   | Lanczos3 | 10.3 % |
   | Keys a = −0.75 | 10.6 % |
   | Lanczos3 + USM (σ = 1 px, 50 %) | 17.7 % |
4. **Sharpening is enhancement, not reconstruction.**
   - Video-quality practice separates the two: Netflix ships VMAF "No Enhancement Gain" (NEG) models for codec comparison, because enhancement inflates the score. [doc]
   - At threshold 0, USM also amplifies JPEG ringing, blocking and grain. AMD's CAS header: "CAS will amplify grain". [doc]
   - I found **no study** showing that post-USM improves full-reference fidelity (PSNR, SSIM, SSIMULACRA2, Butteraugli) for upscaled JPEG copies. This is an open question for the harness.
5. **Answer to the user's question** (*inference* from 1–4): offer two honest modes, and treat Lanczos3 + USM as a "make it look sharper" preset that biases the diff.
   - **"Pixels"**: NN. Exact at integer ratios; for non-integer ratios, optionally the CSS two-step (NN to the nearest integer multiple, then smooth).
   - **"Smooth"**: a clamped interpolating kernel with no post-sharpening. Catmull-Rom is what libvips uses for all upsizing and is Pillow's BICUBIC. LBB is better still: a locally bounded Catmull-Rom whose output stays within the range of nearby inputs, so it makes no halos (libvips, GEGL/GIMP NoHalo) [doc].
6. **Enlargement defaults in the wild** [doc]. The filter Beyond Compare's "Auto Scale" uses is undocumented.

   | Tool | Default for enlargement |
   |---|---|
   | ImageMagick `-resize` | Mitchell |
   | ImageMagick `-distort Resize` | EWA Robidoux |
   | libvips | Catmull-Rom |
   | Pillow | bicubic a = −0.5 |
   | OpenCV | bilinear (its cubic is a = −0.75) |
   | FFmpeg | bicubic B = 0, C = 0.6 |
   | mpv | Lanczos (`ewa_lanczossharp` in the high-quality profile) |
   | Chrome | bilinear + mipmaps; Mitchell only for "high"-quality upscales |
   | Cloudflare | bicubic, or ESRGAN when asked |
   | FreeImage (already linked by WinIMerge) | offers Box, Bilinear, B-spline, Mitchell, Catmull-Rom, Lanczos3, all clamped |
7. **How sites downscale is mostly undocumented.**
   - Danbooru (open source): libvips thumbnail (shrink-on-load → box → Lanczos3) in sRGB, no sharpening, JPEG q85 (WebP q75 for 720 px). [doc]
   - Discord's lilliput: OpenCV `INTER_AREA`. [doc]
   - Cloudflare and imgix sharpen only on request; Cloudflare recommends `sharpen=1` "for downscaled images". [doc]
   - Pixiv, Twitter/X and Imgur do not document their filter.
   - No documented pipeline resizes in linear light by default.
8. **Geometry matters as much as the kernel.**
   - Upscale with centre convention and per-axis factors W/w and H/h, which is how libvips, Pillow, OpenCV and FreeImage map pixels [doc].
   - A naive corner-aligned mapping (src = dst/s) shifts content by 0.5·(1 − 1/s) source px, i.e. 0.5·(s − 1) output px (≈0.7 px at s = 2.41), and lights up every edge. This is the same displacement libvips adds as `idx = 0.5 * (1.0 - 1.0 / hscale)`. *Inference.*
   - If the aspect ratios differ by more than rounding, use one uniform factor plus centring.
9. **How other diff tools handle different sizes:**

   | Tool | Behaviour |
   |---|---|
   | ImageMagick `compare`, odiff, jest-image-snapshot | top-left alignment [doc] |
   | Kaleidoscope | centred until 6.4; corner/edge anchors in 6.4; X/Y offset and automatic alignment in 6.6 † |
   | Beyond Compare | "Auto Scale" enlarges the smaller image; draggable "Difference Offset" † |
   | Resemble.js | `scaleToSameSize()` [doc] |
   | pixelmatch, DiffImg, Butteraugli, SSIMULACRA2 | reject mismatched sizes |

   None documents its scaling filter.
10. **Flip perception.**
    - NVIDIA ꟻLIP models an observer alternating two images. It needs pixels per degree: PPD = *d*·(resX/width)·π/180; the default is 67 PPD (0.7 m from a 0.7 m-wide 4K screen) [doc]. At WinIMerge zoom *k*, image PPD = monitor PPD/*k* (*inference*).
    - SSIMULACRA2's top band (90) means "not noticeable … in a flicker test". [doc]
    - Butteraugli is tuned only near threshold. [doc]
    - All three require equal sizes, so they inherit our upscaler. The VMAF FAQ's practice is to upsample the low-res input to the reference size; its example uses bicubic. [doc]
11. **Perception–distortion trade-off** (Blau and Michaeli 2018) †: outputs that look more "real" must have higher distortion.
    - Learned upscalers invent detail and do not belong in a diff tool: waifu2x, Real-ESRGAN anime models, Cloudflare `upscale=generate` (ESRGAN).
    - USM is a mild step in the same direction. *Inference.*
12. **WinMerge prior art.**
    - #1916 (2023, open, labelled, no comment) asks for exactly this: "size everything to fit the first image compared".
    - In WinIMerge #26 (2021), sdottaka wrote: "Unfortunately, WinMerge doesn't have the ability to scale an image to fit an image in another pane."
    - #2371 asks for per-image X/Y offsets. WinIMerge already has an `ADJUST_OFFSET` dragging mode and `AddImageOffset()`.
    - The maintainer usually questions the need, merges focused PRs within a day, then generalises or gates them behind an option himself.
13. **Expected pitfalls in the diff.**
    - JPEG decoder differences: WinIMerge #37 led to the "prefer WIC" option in 2.16.59.
    - Nearly every pixel of a resampled pane differs slightly. The Color Distance threshold (Euclidean RGBA) needs a sane value whenever scaling is on; sdottaka has suggested about 16 for rendering drift (#1391).
    - Screentone will produce moiré-level differences whatever the kernel. *Inference.*

---

## 1. Resampling kernels for enlargement

### 1.1 The vocabulary: blur, ringing, aliasing/anisotropy

- **Mitchell and Netravali, "Reconstruction Filters in Computer Graphics" (SIGGRAPH 1988)** †
  - The paper studies the two-parameter cubic family (B, C).
  - Setup: "nine expert observers", "over 500 samples".
  - "In viewing many reconstructions with filters in this family, ringing, anisotropy, and blurring are the dominant behaviors."
  - Disclaimer: "It would not be credible to suggest that a single ideal parameter pair can be deduced from subjective testing … simply to draw approximate boundaries between regions of differing behavior."
  - The recommended family is the dashed line **B + 2C = 1**, "and especially B = C = 1/3 as a satisfactory compromise" (Wikipedia wording; the region chart is the paper's Fig. 13).
  - Sources: [ACM DL](https://dl.acm.org/doi/10.1145/54852.378514), [PDF mirror](http://mentallandscape.com/Papers_siggraph88.pdf).
- **The ImageMagick source carries the same table** [doc] ([resize.c](https://github.com/ImageMagick/ImageMagick/blob/main/MagickCore/resize.c)):

  | Name | B | C | ImageMagick comment |
  |---|---|---|---|
  | Mitchell-Netravali | 1/3 | 1/3 | "Balanced" cubic spline filter |
  | Catmull-Rom | 0 | 1/2 | "Interpolatory and exact on linears" |
  | Spline | 1 | 0 | "B-Spline Gaussian approximation" |
  | Hermite | 0 | 0 | — |

  Its `filter:c` option is described as the "Keys alpha" value.
- **Computed: what B + 2C = 1 buys.** I checked the moments of the BC kernel numerically.
  - Every BC cubic reproduces constants.
  - Only the kernels with **B + 2C = 1** reproduce linear ramps exactly (first moment = 0). This includes B-spline, Mitchell, Catmull-Rom and GIMP's (0.5, 0.25).
  - Catmull-Rom additionally reproduces quadratics.
  - Keys a = −0.75 (B = 0, C = 0.75) and FFmpeg's default (0, 0.6) are off the line. A linear ramp gets a periodic ripple of at most ≈0.05 px (a = −0.75) or ≈0.02 px (C = 0.6), which is negligible for gradients.
  - k(0) = 1 − B/3. Mitchell therefore has k(0) = 8/9 and k(1) = 1/18: it is **not interpolating** and softens even at 1:1. The B-spline (k(0) = 2/3) is much blurrier.
- **Keys, "Cubic convolution interpolation for digital image processing"**, IEEE TASSP 29(6):1153–1160, 1981 †. With a = −1/2 the interpolant reaches third-order accuracy (error ∝ h³). That is Catmull-Rom. [IEEE](https://ieeexplore.ieee.org/document/1163711)
- **Thévenaz, Blu and Unser, "Interpolation revisited"**, IEEE TMI 19(7):739–758, 2000 †. "Contrary to the common belief, those that perform best are not interpolating" (prefiltered B-spline / MOMS "generalized interpolation"). [EPFL project page](https://bigwww.epfl.ch/research/projects/interpol.html)
- **Duchon, "Lanczos filtering in one and two dimensions"**, J. Applied Meteorology 18:1016–1022, 1979 † is the usual origin citation for Lanczos. [Wikipedia](https://en.wikipedia.org/wiki/Lanczos_resampling)

### 1.2 Kernel catalogue

Overshoot is computed per the reading key (ideal step, centre convention, no clipping). LBB's 0 % is by construction (locally bounded). For the EWA filters I did not compute a 1-D figure (n/c). "Non-integer" is s = 2.41.

| Kernel | Definition / parameters (source) | Radius | Interp.? | 2× | 3× | Non-integer |
|---|---|---|---|---|---|---|
| Nearest / point | box of width 1 | 0.5 | yes | 0 | 0 | 0 |
| Bilinear / triangle | 1 − \|x\| | 1 | yes | 0 | 0 | 0 |
| Hermite | BC(0,0) (IM, mpv) | 1 (IM) | yes | 0 | 0 | 0 |
| B-spline | BC(1,0) | 2 | no | 0 | 0 | 0 |
| GEGL/GIMP "Cubic" | BC(0.5, 0.25) [doc] | 2 | no | 1.0 | 1.5 | — |
| Robidoux (IM EWA default; here as 1-D) | BC(0.3782, 0.3109) [doc] | 2 | no | 1.7 | 2.7 | 3.0 |
| Mitchell–Netravali | BC(1/3, 1/3) | 2 | no | 2.3 | 3.3 | 3.5 |
| RobidouxSharp | BC(0.2620, 0.3690) [doc] | 2 | no | 3.4 | 4.2 | 4.3 |
| Catmull-Rom = Keys a = −½ | BC(0, ½) | 2 | yes | 7.0 | 7.4 | 7.3 |
| FFmpeg "bicubic" default | BC(0, 0.6) [doc] | 2 | yes | 8.4 | 8.9 | — |
| Keys a = −¾ | BC(0, ¾) (OpenCV `A = -0.75f`) [doc] | 2 | yes | 10.6 | 11.1 | — |
| Lanczos2 | sinc(x)·sinc(x/2) | 2 | yes | 8.4 | 8.4 | — |
| Lanczos3 | sinc(x)·sinc(x/3) | 3 | yes | 10.3 | 11.5 | 11.7 |
| Lanczos4 | sinc(x)·sinc(x/4) | 4 | yes | 11.2 | 12.4 | — |
| Spline36 (Panorama Tools) | piecewise cubic, 36 taps in 2-D [doc] | 3 | yes | 9.5 | 10.5 | — |
| Magic Kernel Sharp 2013 | Costella; piecewise quadratic [doc] | 2.5 | no (k(0) = 17/16, k(2) = −1/32) | 13.3 | 14.2 | — |
| Magic Kernel Sharp 2021 | Costella [doc] | 4.5 | nearly (k(0) = 577/576, k(4) = 1/576) | 7.9 | 11.7 | — |
| LBB (Locally Bounded Bicubic) | Catmull-Rom with limiters [doc] | 2 | yes | 0 | 0 | 0 |
| EWA Jinc/Lanczos (polar) | jinc-windowed jinc, radius = 3rd jinc zero 3.2383 [doc] | 3.24 | — | n/c | n/c | n/c |

Notes per kernel:

- **Nearest / box / area at magnification.**
  - ImageMagick `-sample`: "When magnifying, pixels are replicated in blocks … The key feature of the -sample is that no new colors will be added to the resulting image" [doc] ([options](https://github.com/ImageMagick/Website/blob/main/docs/command-line-options/index.html), live: imagemagick.org/script/command-line-options.php#sample).
  - `-scale` is "pixel block averaging and pixel replication" (box) [doc].
  - Pillow `BOX`: "For upscaling, this is equivalent to Resampling.NEAREST" [doc].
  - OpenCV `INTER_AREA`: "when the image is zoomed, it is similar to the INTER_NEAREST method" [doc].
  - FFmpeg `area` is the odd one out: "Area averaging. Equivalent to bilinear for upscaling." [doc]
- **Hermite.** mpv: "support of radius 1.0, making it very fast … but prone to blocking. This is the default for `--dscale`." [doc]
- **Mitchell.** mpv: "Provides a balanced compromise of all scaling artifacts." [doc] Skia's `SkCubicResampler::Mitchell()` is commented "Historic default for kHigh_SkFilterQuality" [doc].
- **Catmull-Rom.** mpv: "sharper than `mitchell`, but prone to ringing" [doc]. It is libvips's "bicubic (catmull-rom) interpolator" [doc].
- **Lanczos.** ImageMagick: "The Lanczos filter is a special 3-lobed Sinc-windowed Sinc filter (promoted to Jinc-windowed Jinc for cylindrical (Elliptical Weighted Average) use)." [doc] Lanczos is zero at non-zero integers (interpolating) but its weights do not sum exactly to 1. The implementations I read (Pillow, FreeImage, libvips) normalise them.
- **EWA / Jinc (cylindrical).**
  - ImageMagick `-distort Resize` uses EWA. "Default cylindrical filter is a Cubic Keys filter": Robidoux, "the Keys cubic filter defined by B=(228 - 108 sqrt(2))/199" [doc] ([resample.c](https://github.com/ImageMagick/ImageMagick/blob/main/MagickCore/resample.c)).
  - LanczosSharp uses blur 0.9812505644269356 and Lanczos2Sharp blur 0.9549963639785485, chosen for "'No-Op' Vertical and Horizontal Line Preservation" [doc].
  - mpv `ewa_lanczossharp` (blur 0.98125058372237073562493) is the high-quality-profile default. `ewa_lanczos4sharpest` uses blur 0.8845 with anti-ringing 0.8 [doc] ([libplacebo filters.c](https://github.com/haasn/libplacebo/blob/master/src/filters.c)).
  - EWA comes from Greene & Heckbert and Heckbert's 1989 thesis, *Fundamentals of Texture Mapping and Image Warping*, UCB/CSD-89-516 † ([Berkeley](https://www2.eecs.berkeley.edu/Pubs/TechRpts/1989/5504.html)).
  - Robidoux's ImageMagick notes present EWA LanczosSharp as an all-round filter: "slightly blurry, with no jaggies to speak of and only mild halos" † ([IM usage/nicolas](https://legacy.imagemagick.org/Usage/filter/nicolas/)).
- **Magic Kernel Sharp** (John Costella).
  - Pillow source [doc]: MKS2013 is k(x) = 17/16 − 7/4·x² for |x| < ½, (1 − x)(7/4 − x) for |x| < 3/2, and −1/8·(x − 5/2)² for |x| < 5/2.
  - Implementations:
    - Pillow 13.0.0 (`Resampling.MKS2013/MKS2021`; on `main` only — the latest release is 12.3.0) [doc]
    - libvips `VIPS_KERNEL_MKS2013/2021` [doc]
    - ImageMagick `MagicKernelSharp2013/2021` [doc]
  - Costella says Facebook has used it since 2013 and Instagram since 2015 †. Note that it embeds a sharpening step: in the table it overshoots more than Lanczos3 at 2× when used as an upsampler.
  - Pillow PR #8811 claims "reduced moiré patterning on downsampling, reduced blockiness on upscaling" (preliminary, no numbers) [doc] ([PR](https://github.com/python-pillow/Pillow/pull/8811), [Costella](https://johncostella.com/magic/) †).
- **Spline16/36/64.** libpano13 (Panorama Tools) `panorama.h` [doc, mirror]: `_spline16 … // Cubic Spline fitting 16 nearest pixels`, `_spline36 … 36 nearest pixels`. libplacebo has the exact polynomials [doc].
- **LBB / NoHalo / LoHalo** (Robidoux et al.).
  - libvips [lbb.cpp](https://github.com/libvips/libvips/blob/master/libvips/resample/lbb.cpp) [doc]: "LBB (Locally Bounded Bicubic) is a high quality nonlinear variant of Catmull-Rom. Images resampled with LBB have much smaller halos … the resampled values are contained within the range of nearby input values." Also: "When the limiters are inactive, LBB gives the same result as Catmull-Rom."
  - GEGL NoHalo = LBB-Nohalo upsampler + clamped EWA "teepee" for downsampling. LoHalo = "sigmoidized tensor filtering with the Mitchell-Netravali Keys cubic filter used as an upsampler" + EWA Robidoux for downsampling [doc] ([gegl-sampler-nohalo.c](https://github.com/GNOME/gegl/blob/master/gegl/buffer/gegl-sampler-nohalo.c), [lohalo.c](https://github.com/GNOME/gegl/blob/master/gegl/buffer/gegl-sampler-lohalo.c)).
  - *Inference:* LBB is the most "diff-honest" smooth kernel I found. It is interpolating, equals Catmull-Rom in smooth areas, and never creates values outside the local min/max, so it can show no halo that is not in the data.
- **mpv anti-ringing and sigmoid options** [doc] ([options.rst](https://github.com/mpv-player/mpv/blob/master/DOCS/man/options.rst)).
  - `--scale-antiring`: "tries to eliminate ringing"; default 0.0; the high-quality profile uses 0.6.
  - `--sigmoid-upscaling` is enabled by default: "use a sigmoidal color transform to avoid emphasizing ringing artifacts".
  - `--linear-upscaling` is "not usually recommended"; `--linear-downscaling` is enabled by default.

### 1.3 When overshoot is clipped

Every 8-bit implementation I read clamps the final value to 0..255 [doc]:

- Pillow: `_clip8` lookup ([Resample.c](https://github.com/python-pillow/Pillow/blob/main/src/libImaging/Resample.c)).
- FreeImage: `CLAMP<int>(…, 0, 0xFF)` ([Resize.cpp](https://github.com/WinMerge/freeimage/blob/winmerge/Source/FreeImageToolkit/Resize.cpp)).
- libvips: `VIPS_CLIP(0, …, max_value)` for integer formats ([templates.h](https://github.com/libvips/libvips/blob/master/libvips/resample/templates.h)).

ImageMagick behaves differently [doc]. `HorizontalFilter`/`VerticalFilter` in resize.c write every pass through `ClampToQuantum()`. That function clamps to 0..QuantumRange in non-HDRI builds and is a no-op with `MAGICKCORE_HDRI_SUPPORT` (MagickCore/quantum.h). So non-HDRI builds also clip between the two separable passes, which is why Robidoux advises against sharp tensor Lanczos "unless you use an HDRI build" †.

*Inference for this content:*
- Anime line art usually sits on pure white paper (255) with near-black lines (≈0). The overshoot beyond those extremes is clipped away.
- Halos therefore show mainly where lines cross mid-tone fills, gradients or screentone. There they appear as light or dark rims of 7–12 % of the local step (≈18–30 levels on a 255 step) for Catmull-Rom/Lanczos3, and more with USM.

### 1.4 Integer scaling and pixel art

CSS Images 3, `image-rendering` [doc] ([spec source](https://github.com/w3c/csswg-drafts/blob/main/css-images-3/Overview.bs), live: w3.org/TR/css-images-3/#the-image-rendering):

- `pixelated`: "For each axis independently, first determine the integer multiple of its natural size that puts it closest to the target size … Scale it to this integer-multiple-size using nearest neighbor, then scale it the rest of the way to the target size as for 'smooth'."
- Note on `crisp-edges`: "If the new size is not an integer multiple of the original size, the nearest neighbor algorithm can introduce significant 'aliasing' bugs; lines that were the same thickness in the original image might be a pixel thinner or thicker in the scaled image depending on where they appear."
- `smooth`: "scaling algorithms that 'smooth' colors are acceptable, such as bilinear interpolation."

WinIMerge's own zoom is NN-style, so it already shows the stored samples at integer zoom [doc]:
- `fipWinImage::drawEx` calls `SetStretchBltMode(hDC, COLORONCOLOR)` + `StretchDIBits` ([fipWinImage.cpp](https://github.com/WinMerge/freeimage/blob/winmerge/Wrapper/FreeImagePlus/src/fipWinImage.cpp)).
- GDI defines COLORONCOLOR as: "Deletes the pixels. This mode deletes all eliminated lines of pixels without trying to preserve their information." ([SetStretchBltMode](https://github.com/MicrosoftDocs/sdk-api/blob/docs/sdk-api-src/content/wingdi/nf-wingdi-setstretchbltmode.md)).

*Inference:* the "Pixels" mode should hand integer-ratio cases to plain replication. Non-integer ratios need either the CSS two-step or an explicit "nearest integer factor + centre" fallback.

### 1.5 Linear light vs gamma space

- libvips `thumbnail`: "Shrinking is normally done in sRGB colourspace. Set @linear to shrink in linear light … tricks like JPEG shrink-on-load cannot be used in linear space." [doc]
- AMD CAS: "This filter does not function well on sRGB or gamma 2.2 non-linear data." [doc]
- Eric Brasseur's "Gamma error in picture scaling" page is the classic demonstration that most tools downscale in gamma space † ([discussion](https://bugs.kde.org/show_bug.cgi?id=228934)).
- *Inference:* the copies we compare were almost certainly downscaled in sRGB (libvips and Pillow defaults). For upscaling, sRGB-space interpolation is the norm (mpv recommends against linear upscaling), so WinIMerge can resample in sRGB.

---

## 2. What popular tools and sites use by default

### 2.1 Libraries and applications

**Photoshop** † ([Adobe: Resampling options](https://helpx.adobe.com/photoshop/desktop/crop-resize-transform/resize-adjust-resolution/resampling-options.html))
- Image Size "Resample" options:
  - **Automatic** (default): "Chooses the best method automatically, depending on whether the image is being enlarged or reduced."
  - **Preserve Details 2.0** for enlarging: "Maintains sharp edges and fine detail with reduced artifacts", with a *Reduce Noise* slider.
  - **Preserve Details (enlargement)**: "earlier version of the Preserve Details 2.0 algorithm".
  - **Bicubic Smoother (enlargement)**, **Bicubic Sharper (reduction)**, **Bicubic (smooth gradients)**, **Nearest Neighbor (hard edges)**, **Bilinear**.
- Undocumented: which method Automatic picks for enlargement, and the kernels behind Smoother and Sharper. Community answers say the "Bicubic Automatic" preference picks Smoother when enlarging and Sharper when reducing † ([community](https://community.adobe.com/t5/photoshop-ecosystem-discussions/how-to-change-image-interpolation-setting-default-from-quot-bicubic-quot-to-quot-nearest-neighbor/m-p/15127057/highlight/true)).

**GIMP / GEGL** [doc]
- The default interpolation is **Cubic** (`GIMP_INTERPOLATION_CUBIC` in [gimpcoreconfig.c](https://github.com/GNOME/gimp/blob/master/app/config/gimpcoreconfig.c)). The choices are None, Linear, Cubic, NoHalo, LoHalo.
- GEGL's cubic sampler forces B = 0.5, C = 0.5·(1 − B) = 0.25. Its comment reads "0.0 = sharp, but with anomaly of issue #167 / 1.0 = fuzzy cubic, without anomaly / 0.5 is a compromise against issue #145" ([gegl-sampler-cubic.c](https://github.com/GNOME/gegl/blob/master/gegl/buffer/gegl-sampler-cubic.c)).
- GIMP docs †: "Use the NoHalo method when you downscale an image to less than a half of the original size and the LoHalo method when you do not reduce the size much" ([Transform tools](https://docs.gimp.org/en/gimp-tools-transform.html)). A docs page quotes Robidoux: LoHalo suits text, pixel art, noisy or compressed images; NoHalo suits noise-free, slightly blurry ones †.

**ImageMagick** [doc]
- `-filter` default: "If you do not select a filter with this option, the filter defaults to Mitchell for a colormapped image, an image with a matte channel, or if the image is enlarged. Otherwise the filter default to Lanczos."
  - Code: Lanczos, unless 1:1 (→ Point), or PseudoClass, alpha, or `x_factor*y_factor > 1.0` (→ Mitchell).
- `-distort Resize` uses EWA with Robidoux.
- Expert defines:
  - `-define filter:blur=factor`: "Use > 1.0 for blurry or < 1.0 for sharp".
  - `filter:lobes=count`, `filter:support=radius`, `filter:window`, `filter:sigma` (default 0.5).
  - `filter:b` / `filter:c`: "If only one of the values are defined, the other is set so as to generate a 'Cubic-Keys' filter."
- `-unsharp {radius}x{sigma}+gain+threshold` defaults: radius 0 (auto), sigma 1.0, gain 1.0, threshold 0.05 (fraction of QuantumRange).
- Sources: [options page source](https://github.com/ImageMagick/Website/blob/main/docs/command-line-options/index.html), [resize.c](https://github.com/ImageMagick/ImageMagick/blob/main/MagickCore/resize.c).

**libvips** [doc] ([resize.c](https://github.com/libvips/libvips/blob/master/libvips/resample/resize.c), [thumbnail.c](https://github.com/libvips/libvips/blob/master/libvips/resample/thumbnail.c))
- `vips_resize`: kernel default LANCZOS3, gap default 2.0. "Downsizing is done with centre convention."
- Upsizing: "When upsizing (@scale > 1), the operation uses [method@Image.affine] with a [class@Interpolate] selected depending on @kernel. It will use … "bicubic" for [enum@Vips.Kernel.CUBIC] and above. It adds a 0.5 pixel displacement to the input pixels to get centre convention scaling."
  - So even with the default Lanczos3 kernel, **upsizing is Catmull-Rom**: libvips's "bicubic" interpolator is Catmull-Rom.
- "This operation does not premultiply alpha."
- Kernels: NEAREST, LINEAR, CUBIC (Catmull-Rom), MITCHELL, LANCZOS2, LANCZOS3, MKS2013, MKS2021.
- `vips_thumbnail`: "Shrinking is done in three stages: using any shrink-on-load features available in the image load library, using a block shrink, and using a lanczos3 shrink. At least the final 200% is done with lanczos3."
  - It runs in sRGB unless `linear` is set.
  - For JPEG, shrink-on-load is libjpeg's DCT-domain 1/2, 1/4, 1/8 scaling (*inference* from libjpeg).

**Pillow** [doc] ([Image.py](https://github.com/python-pillow/Pillow/blob/main/src/PIL/Image.py), [concepts.rst](https://github.com/python-pillow/Pillow/blob/main/docs/handbook/concepts.rst), [Resample.c](https://github.com/python-pillow/Pillow/blob/main/src/libImaging/Resample.c))
- `resize`: "If the image has mode "1" or "P", it is always set to Resampling.NEAREST. Otherwise, the default filter is Resampling.BICUBIC." Before 7.0.0 the default was NEAREST ([7.0.0 notes](https://github.com/python-pillow/Pillow/blob/main/docs/releasenotes/7.0.0.rst)).
- `thumbnail`: defaults to BICUBIC with `reducing_gap=2.0` and uses `draft()` for JPEG. On `reducing_gap`: "With reducing_gap greater or equal to 3.0, the result is indistinguishable from fair resampling in most cases."
- Kernels: BICUBIC is Keys `a = -0.5`; LANCZOS is 3-lobe; support is widened only when downscaling (`filterscale = max(1, scale)`); 8-bit output is clipped.
- The docs' "Filters comparison table" rates upscaling quality as follows:

  | Filter | Upscaling quality |
  |---|---|
  | NEAREST, BOX, HAMMING | — |
  | BILINEAR | ⭐ |
  | BICUBIC | ⭐⭐⭐ |
  | LANCZOS | ⭐⭐⭐⭐ |
  | MKS2013 | ⭐⭐⭐⭐ |
  | MKS2021 | ⭐⭐⭐⭐⭐ |

**OpenCV** [doc] ([imgproc.hpp](https://github.com/opencv/opencv/blob/5.x/modules/imgproc/include/opencv2/imgproc.hpp), [resize.cpp](https://github.com/opencv/opencv/blob/5.x/modules/imgproc/src/resize.cpp))
- `resize(..., interpolation = INTER_LINEAR)` is the default.
- "To shrink an image, it will generally look best with INTER_AREA interpolation, whereas to enlarge an image, it will generally look best with INTER_CUBIC (slow) or INTER_LINEAR (faster but still looks OK)."
- `INTER_CUBIC` uses `A = -0.75f`; `INTER_LANCZOS4` is "Lanczos interpolation over 8x8 neighborhood".
- Nearest neighbour:
  - `INTER_NEAREST` maps destination x to `cvFloor(x*ifx)` (ifx = source/destination), with no half-pixel offset. At integer magnifications this is still plain replication.
  - `INTER_NEAREST_EXACT`: "This will produce same results as the nearest neighbor method in PIL, scikit-image or Matlab".
- *Inference:* `INTER_LINEAR` reads a 2×2 neighbourhood whatever the scale, so it aliases when shrinking by more than 2×. That is why the docs point to `INTER_AREA`.

**Browsers**
- **Chrome/Blink** [doc]
  - `GetDefaultInterpolationQuality()` returns `kInterpolationMedium` ([graphics_context_types.cc](https://github.com/chromium/chromium/blob/main/third_party/blink/renderer/platform/graphics/graphics_context_types.cc)).
  - In `PaintFlags::FilterQualityToSkSamplingOptions` ([paint_flags.cc](https://github.com/chromium/chromium/blob/main/cc/paint/paint_flags.cc)):
    - Medium = bilinear + mipmaps.
    - High = Catmull-Rom (default op) or `SkCubicResampler::Mitchell()` when the operation is an upscale.
  - I did not verify which CSS values map to "High".
- **CSS** `image-rendering`: `smooth`, `high-quality`, `pixelated`, `crisp-edges` (§1.4).
- **Firefox** [doc]: decode-time downscaling ("DownscalingFilter performs Lanczos downscaling") uses `ResizeMethod::LANCZOS3` ([DownscalingFilter.h](https://github.com/mozilla-firefox/firefox/blob/main/image/DownscalingFilter.h)). I did not verify its upscaling path.

**Windows WIC, Direct2D and GDI** [doc] ([WIC enum](https://learn.microsoft.com/en-us/windows/win32/api/wincodec/ne-wincodec-wicbitmapinterpolationmode), [D2D1_INTERPOLATION_MODE](https://learn.microsoft.com/en-us/windows/win32/api/d2d1_1/ne-d2d1_1-d2d1_interpolation_mode), [Scale effect](https://learn.microsoft.com/en-us/windows/win32/direct2d/high-quality-scale); read via the MicrosoftDocs GitHub sources)
- `IWICBitmapScaler` takes a `WICBitmapInterpolationMode`:
  - **NearestNeighbor**: "The output pixel is assigned the value of the pixel that the point falls within."
  - **Linear**: "weighted average of the nearest four pixels in a 2x2 grid".
  - **Cubic**: "nearest sixteen pixels in a 4x4 grid".
  - **Fant**: "weighted average of the all the pixels that map to the new pixel". Its upscaling behaviour is undocumented.
  - **HighQualityCubic**: "much denser sampling kernel than regular cubic. The kernel is resized in response to the scale factor, making it suitable for downscaling by factors greater than 2." Windows 10 and later.
  - None of the kernels' parameters are documented.
- Direct2D `D2D1_INTERPOLATION_MODE`: NEAREST_NEIGHBOR, LINEAR, CUBIC ("16 sample cubic kernel"), MULTI_SAMPLE_LINEAR, ANISOTROPIC, HIGH_QUALITY_CUBIC ("variable size high quality cubic kernel to perform a pre-downscale … Then uses the cubic interpolation mode").
- The Direct2D **Scale effect** defaults to `D2D1_SCALE_INTERPOLATION_MODE_LINEAR` and has a `SHARPNESS` property (0–1, high-quality cubic only).
- `D2D1_BITMAP_INTERPOLATION_MODE` has only NEAREST_NEIGHBOR and LINEAR.
- GDI `HALFTONE` is "the average color over the destination block … approximates the color of the source pixels".

**FFmpeg swscale** [doc] ([scaler.texi](https://github.com/FFmpeg/FFmpeg/blob/master/doc/scaler.texi), [utils.c](https://github.com/FFmpeg/FFmpeg/blob/master/libswscale/utils.c))
- The new `scaler` option defaults to `auto`, which falls back to `sws_flags`, whose default is `bicubic`.
- bicubic: "2-tap cubic BC-spline (AKA Mitchell-Netravali spline). The B and C parameters can be configured by setting param0 and param1, defaulting to 0.0 and 0.6 respectively."
- lanczos: "The number of filter taps can be configured by setting param0, defaulting to 3."
- Other flags: `area` ("Equivalent to bilinear for upscaling"), `neighbor`, `spline`, `accurate_rnd`, `full_chroma_int`.
- The `scale` filter's own `flags` default is empty, so it gets the swscale default.

**FreeImage** (WinMerge fork; already a WinIMerge dependency) [doc] ([FreeImage.h](https://github.com/WinMerge/freeimage/blob/winmerge/Source/FreeImage.h), [Filters.h](https://github.com/WinMerge/freeimage/blob/winmerge/Source/FreeImageToolkit/Filters.h))
- `FreeImage_Rescale(dib, w, h, filter)` offers:
  - `FILTER_BOX`
  - `FILTER_BICUBIC`: "Mitchell & Netravali's two-param cubic filter", b = c = 1/3 by default
  - `FILTER_BILINEAR`
  - `FILTER_BSPLINE`
  - `FILTER_CATMULLROM`
  - `FILTER_LANCZOS3`
- It uses centre convention (`dCenter = u/dScale + 0.5/dScale`), widens support when shrinking, and clamps.
- *Inference:* WinIMerge could use this with no new dependency. It has no LBB and no alpha premultiplication, so transparent edges can fringe (libvips warns the same about its own resize).

### 2.2 Image hosts and art sites

| Site | Downscale path | Sharpening | Linear light | Status |
|---|---|---|---|---|
| **Danbooru** | libvips `thumbnail_image(..., size: :force)` with sRGB import/export profiles | none in code | no (thumbnail default) | [doc] source |
| **Discord** | media proxy via lilliput (2017 blog: Python + pillow-simd replaced by Go); lilliput uses OpenCV `INTER_AREA` | none in code | no | lilliput [doc]; production use † |
| **Cloudflare Images** | kernel undocumented; upscale `interpolate` = bicubic or `generate` = ESRGAN | `sharpen` 0–10, default 0, "recommended value for downscaled images is 1" | undocumented | [doc] docs source |
| **imgix** | kernel undocumented | `sharp` default 0 (0–100); `usm` default 0 (−100..100); `usmrad` default 2.5 | undocumented | [doc] param registry |
| **Pixiv** | undocumented | unknown | unknown | community reverse-engineering |
| **Twitter/X** | undocumented | unknown | unknown | press coverage † |
| **Imgur** | undocumented | unknown | unknown | old API docs via forum † |
| **Facebook / Instagram** | Magic Kernel Sharp (sharpening built into the kernel) | yes (in kernel) | † | Costella † |

- **Danbooru** detail ([image.rb](https://github.com/danbooru/danbooru/blob/master/app/logical/media_file/image.rb), [media_asset.rb](https://github.com/danbooru/danbooru/blob/master/app/models/media_asset.rb)):
  - Variants: 180×180 and 360×360 JPEG q85; 720×720 WebP q75 (`preset: :drawing`); sample 850 px wide JPEG q85 for images wider than `large_image_width` (default 850, in `config/danbooru_default_config.rb`); full JPEG q85 for WebP/AVIF sources.
  - jpegsave flags: `trellis_quant`, `overshoot_deringing`, `quant_table: 3`.
  - Alpha is flattened onto white.
- **Discord** sources: [blog](https://discord.com/blog/how-discord-resizes-150-million-images-every-day-with-go-and-c) †, [opencv.go](https://github.com/discord/lilliput/blob/master/opencv.go). Current production use is not verified.
- **Cloudflare** sources: [sharpen](https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/partials/images/sharpen.mdx), [upscale](https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/partials/images/upscale.mdx). Also `quality` default 85 and `fit` default `scale-down`.
- **imgix**: also `q` default 75 and `fit` default `clip` ([parameters.json](https://github.com/imgix/imgix-url-params/blob/master/dist/parameters.json)).
- **Pixiv**: `img-master/…_master1200.jpg` and `_square1200.jpg`, plus WebP variants. Size prefixes such as `/c/600x1200_90`, `/c/768x1200_80` and `w1200_q80` suggest per-variant JPEG quality ([community notes](https://github.com/kepstin/Fix-pixiv-thumbnails/blob/master/thumbnail_urls.md)).
- **Twitter/X**: since Dec 2019, web-uploaded JPEGs within limits are not re-encoded; before that they were transcoded at quality 85. Images over 4096 px are still transcoded, and thumbnails are recompressed ([TechRadar](https://www.techradar.com/news/twitter-will-no-longer-downgrade-the-quality-of-your-jpegs-in-tweets) †).
- **Imgur** thumbnail suffixes: s (90 square), b (160 square), t (160), m (320), l (640), h (1024) ([Vogons quote of the old API docs](https://www.vogons.org/viewtopic.php?p=505907) †).
- **Facebook / Instagram**: "Facebook has used Magic Kernel Sharp to resize images since 2013" †.

*Inference for the user's duplicates:* most low-res copies will be a windowed-sinc or area downscale in sRGB, then JPEG q75–90 (4:2:0 likely), with no extra sharpening, except Facebook/Instagram (MKS includes sharpening) and any site that opts in. Their resize factors are arbitrary, not integer.

---

## 3. Sharpening after enlargement

- **Unsharp mask.** out = x + amount·(x − G_σ ∗ x), applied only where |x − G_σ ∗ x| exceeds the threshold. Parameter semantics differ by tool:
  - GIMP/GEGL `gegl:unsharp-mask` [doc] ([unsharp-mask.c](https://github.com/GNOME/gegl/blob/master/operations/common/unsharp-mask.c)): "Radius" is "Expressed as standard deviation, in pixels" (default 3.0); "Amount" default 0.5; "Threshold" default 0.0.
    - The user's "radius 1 px, 40–60 %, threshold 0" therefore means σ = 1, amount 0.4–0.6, threshold 0 in GIMP terms.
  - ImageMagick `-unsharp` takes sigma explicitly (default 1.0) plus gain and threshold (§2.1).
  - Photoshop: Amount %, Radius px, Threshold levels. Adobe does not document how Radius maps to σ (unverified). A common rule is "radius 0.5–2 px, amount 50–150 %" ([Wikipedia](https://en.wikipedia.org/wiki/Unsharp_masking) †).
- **Computed: halo size.** Peak overshoot after USM (σ = 1 px, amount 0.5, threshold 0) applied to a step that was first upscaled 2× with:

  | Upscaler | Peak overshoot after USM |
  |---|---|
  | NN | 15.0 % |
  | bilinear | 5.3 % |
  | B-spline | 1.5 % |
  | Mitchell | 8.1 % |
  | Catmull-Rom | 13.7 % |
  | Lanczos2 | 15.7 % |
  | Lanczos3 | 17.7 % |
  | Keys −0.75 | 18.4 % |
  | MKS2013 | 21.1 % |

  - On a 255-level step, Lanczos3 + USM is ±45 levels before clipping. The halo is about 2–3 σ wide on each side.
  - With threshold 0, every JPEG ringing ripple and 8×8 block edge in the low-res copy (*inference*) is boosted in proportion.
- **AMD FidelityFX CAS (Contrast Adaptive Sharpening)** [doc] ([ffx_cas.h](https://github.com/GPUOpen-Effects/FidelityFX-CAS/blob/master/ffx-cas/ffx_cas.h), [README](https://github.com/GPUOpen-Effects/FidelityFX-CAS)):
  - "CAS enchances sharpness and local high-frequency contrast, and with or without added upsampling."
  - "The filter kernel adapts to local contrast (adjusting the negative lobe strength of the filter kernel)."
  - It uses a 3×3 window and a "Sharpness tuning knob (0.0 to 1.0)".
  - Scaling support goes up to "4x area".
  - "It is likely better to reduce the amount of film grain which happens before CAS (as CAS will amplify grain)."
  - "This is designed to be a linear filter. Running CAS on perceptual inputs will yield over-sharpening."
- **Halo perception.** Trentacoste, Mantiuk, Heidrich et al., "Unsharp Masking, Countershading and Halos: Enhancements or Artifacts?" (Eurographics 2012, CGF 31(2)) † found that acceptability depends on the halo's width and amplitude with a U-shaped characteristic. "Wrong parameters, or different viewing conditions can result in objectionable halo artifacts" ([PDF](https://www.cl.cam.ac.uk/~rkm38/pdfs/trentacoste12countershading.pdf)).
  - *Inference:* WinIMerge users zoom 2–8×, which makes a 1-px-σ halo span many screen pixels, i.e. the "objectionable" width range.
- **Metrics vs sharpening.**
  - VMAF: "VMAF can capture the visual gain from image enhancement operations … in codec evaluation, it is often desirable to measure the gain achievable from compression without taking into account the gain from image enhancement". Hence the `neg` models [doc] ([models_v0.md](https://github.com/Netflix/vmaf/blob/master/resource/doc/models_v0.md)).
  - Siniukov et al., "Hacking VMAF and VMAF NEG" (arXiv 2107.04510, 2021) †: tuned preprocessing raised VMAF by up to 218.8 % and VMAF NEG by up to 23.6 %, while subjective quality stayed the same or dropped.
  - Zvezdakova et al. 2019 (arXiv 1907.04807) † showed the same with colour and contrast changes.
  - Krasula et al., "Quality Assessment of Sharpened Images: Challenges, Methodology, and Objective Metrics" (IEEE TIP 26(3):1496–1508, 2017) † treats sharpening as post-processing that can raise perceived quality above the reference. I could not read its result tables.
  - RAISR (Romano, Isidoro, Milanfar; arXiv 1606.01299, IEEE TCI 2017) † applies learned filters to a "cheap" upscale, chosen "to minimize the Euclidean distance" to ground truth. It needs a census-transform blending step to avoid artefacts.
    - *Inference:* sharpening improves fidelity when it is fitted to the actual degradation. Generic USM is not.
  - **Gap:** I found no published PSNR/SSIM/SSIMULACRA2/Butteraugli comparison of "bicubic or Lanczos alone" vs "the same + USM" on downscaled-and-JPEG'd images.
    - *Inference:* USM can only partly restore frequencies below the low-res Nyquist. It cannot recover anything above it, and it boosts quantisation noise. Expect small or negative fidelity gains on JPEG'd anime art and possibly small gains on clean photos.
    - SSIMULACRA2 has an explicit ringing map ("distorted has edges where original is smooth") [doc], so it should penalise USM halos.
    - Recommended harness test: kernels {NN, bilinear, Catmull-Rom, LBB, Lanczos3} × {no USM, USM σ = 1 at 0.4/0.6} × {clean, JPEG q85} × {line art, screentone, gradient, photo}. Measure ꟻLIP at the user's PPD, SSIMULACRA2, Butteraugli 3-norm and max, and PSNR.

---

## 4. Perceptual metrics for "flip" comparison

### 4.1 NVIDIA ꟻLIP

- **Paper.** P. Andersson, J. Nilsson, T. Akenine-Möller, M. Oskarsson, K. Åström, M. D. Fairchild, "ꟻLIP: A Difference Evaluator for Alternating Images", *Proc. ACM Comput. Graph. Interact. Tech.* 3(2), 15:1–15:23, 2020, doi:10.1145/3406183 [doc] ([LDRFLIP.txt](https://github.com/NVlabs/flip/blob/main/misc/LDRFLIP.txt)). HDR-FLIP followed in 2021.
- **What it models** †: "a map that approximates the difference perceived by humans when alternating between two images". The authors' motivation is that flipping reveals differences "much more distinctly than showing them side by side" ([Lund portal](https://portal.research.lu.se/en/publications/flip-a-difference-evaluator-for-alternating-images/)).
- **Pipeline**, read in [FLIP.h](https://github.com/NVlabs/flip/blob/main/src/cpp/FLIP.h) [doc]:
  - **Colour:** sRGB → linear → XYZ → YCxCz, then spatial filtering by contrast-sensitivity functions whose size depends on PPD. Back to linear RGB (clamped) → CIELab; Hunt adjustment (`0.01 * L * chroma`); **HyAB** distance; then a non-linear remap (`gqc = 0.7`, `gpc = 0.4`, `gpt = 0.95`).
  - **Features:** edge (1st-derivative) and point (2nd-derivative) magnitudes of a Gaussian (`gw = 0.082`), differenced and raised to `gqf = 0.5`.
  - **Final:** `errorFLIP = pow(colorDiff, 1 - featureDiff)`. Output is a per-pixel map in [0,1] plus mean, weighted median, quartiles and a weighted histogram.
- **PPD (pixels per degree).**
  - `calculatePPD(dist, resolutionX, monitorWidth) = dist * (resolutionX / monitorWidth) * (π/180)`; the default is `calculatePPD(0.7, 3840, 0.7)` ≈ **67.02** [doc].
  - CLI ([commandline.h](https://github.com/NVlabs/flip/blob/main/src/cpp/tool/commandline.h)) [doc]:
    - `--pixels-per-degree` / `-ppd`: "Observer's number of pixels per degree of visual angle. Default corresponds to viewing the images at 0.7 meters from a 0.7 meter wide 4K display".
    - `--viewing-conditions` / `-vc MONITOR-DISTANCE MONITOR-WIDTH MONITOR-WIDTH-PIXELS`, i.e. metres, metres, pixels.
  - **Pitfall:** the Python API's `"vc"` list is ordered *[distance m, width px, width m]*, a different order from the C++ CLI ([nanobindFLIP.cpp](https://github.com/NVlabs/flip/blob/main/src/nanobindFLIP.cpp)) [doc].
  - From PPI and distance (small-angle): **PPD ≈ distance_in × PPI × π/180**, with PPI = √(w² + h²)/diagonal_in.
  - Computed examples:

    | Display | Distance | PPI | PPD at 1× | 2× zoom | 4× zoom |
    |---|---|---|---|---|---|
    | 24″ 1920×1080 | 60 cm | 91.8 | 37.8 | 18.9 | 9.5 |
    | 27″ 2560×1440 | 60 cm | 108.8 | 44.9 | 22.4 | 11.2 |
    | 27″ 3840×2160 | 60 cm | 163.2 | 67.3 | 33.6 | 16.8 |
    | 15.6″ 1920×1080 laptop | 50 cm | 141.2 | 48.5 | 24.3 | 12.1 |

  - At WinIMerge zoom *k*, one image pixel spans *k* screen pixels, so pass **PPD/k** when evaluating the image at native resolution. *Inference*, following directly from the definition.
- **Implementation note.** "We have several different implementations of FLIP (Python, PyTorch, C++, and CUDA) … There may still be differences." This is due to float order, FMA and separable filters ([precision.md](https://github.com/NVlabs/flip/blob/main/misc/precision.md)) [doc].
- *Inference:* ꟻLIP's feature pipeline responds to edge and point structure. NN staircases and USM halos both add edge energy that the original lacks, so both should score as visible flip differences. This is a testable prediction for the harness.

### 4.2 Butteraugli

- README [doc] ([google/butteraugli](https://github.com/google/butteraugli)):
  - "reliable in the domain of barely noticeable differences".
  - "We don't know how well butteraugli performs with major deformations -- we have mostly tuned it within a small range of quality, roughly corresponding to jpeg qualities 90 to 95."
  - It outputs a scalar plus a spatial diff map.
- **Max-norm vs p-norm.**
  - The classic scalar is the maximum of the diffmap, i.e. the worst local spot: `ButteraugliScoreFromDiffmap()` returns `std::max` over all pixels in both google/butteraugli and libjxl [doc] ([libjxl butteraugli.cc](https://github.com/libjxl/libjxl/blob/main/lib/jxl/butteraugli/butteraugli.cc)).
  - libjxl's `butteraugli_main` prints that value, then `"%g-norm"` with default `p = 3` (`--pnorm`) ([butteraugli_main.cc](https://github.com/libjxl/libjxl/blob/main/tools/butteraugli_main.cc)) [doc].
  - *Inference:* max-norm suits "is there any visible difference anywhere"; p-norm suits "how different overall".
- **Scale** [doc]: `ButteraugliFuzzyClass` "Returns 2.0 for a perfect match, and 1.0 for 'ok', 0.0 for bad". cjxl's `--distance` is "Target visual distance in JND units … 1.0 = visually lossless".
- **Requirements** [doc]:
  - Images must be the same size ("Width mismatch").
  - "Butteraugli does not work as intended if the caller does not perform gamma correction" (original API).
  - *Inference:* a 2–4× downscale plus upscale is far outside its calibrated range, so only the heatmap and relative ranking are meaningful there.

### 4.3 SSIMULACRA 2

- README [doc] ([cloudinary/ssimulacra2](https://github.com/cloudinary/ssimulacra2)). Score bands:

  | Score | Meaning |
  |---|---|
  | 90 | "Distortion not noticeable by an average observer in a **flicker test** at 1:1 from a normal viewing distance" |
  | 85 | not noticeable in an in-place comparison |
  | 80 | not noticeable side-by-side |
  | 70 | high quality |
  | 50 | medium |
  | 30 | low |
  | 10 | very low |
  | negative | extremely low quality |

- Method: XYB colour space; an SSIM map, a "blockiness/ringing" map and a "smoothing/blur" map; 6 scales; "Downscaling is done in linear color"; 1-norm and 4-norm; 108 weighted features.
- Requirements: the libjxl tool requires equal sizes ("Image size mismatch.") and at least 8×8 pixels ([ssimulacra2_main.cc](https://github.com/libjxl/libjxl/blob/main/tools/ssimulacra2_main.cc)) [doc].
- Port drift: the Rust and numpy ports differ from libjxl by about 0.1–0.3 points (float32 recursive Gaussian, border handling) † ([write-up](https://github.com/NevermindNilas/frame_analytics)).

### 4.4 The perception–distortion trade-off

- Blau & Michaeli, "The Perception-Distortion Tradeoff", CVPR 2018 (arXiv 1711.06077) †:
  - "distortion and perceptual quality are at odds with each other".
  - As mean distortion falls, the optimal probability of telling outputs from real images "must increase (indicating worse perceptual quality)". This holds "for any distortion measure".
  - GANs "provide a principled way to approach the perception-distortion bound".
  - [CVF](https://openaccess.thecvf.com/content_cvpr_2018/html/Blau_The_Perception-Distortion_Tradeoff_CVPR_2018_paper.html)
- *Inference for a diff tool:* the diff should show what is missing, so we want the low-distortion end, whose outputs look somewhat blurry but invent nothing. That rules out:
  - perceptual or generative upscalers: [waifu2x](https://github.com/nagadomi/waifu2x) ("Image Super-Resolution for Anime-style art"), [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) `RealESRGAN_x4plus_anime_6B`, Cloudflare `upscale=generate`;
  - and, to a lesser degree, fixed sharpening.
- A fixed linear kernel has a known, content-independent transfer function, so its artefacts are predictable (and avoidable with LBB). A GAN's are not.

### 4.5 Known metric pitfalls

- **Ports and implementations disagree:** see ꟻLIP's precision note, the SSIMULACRA2 ports above, and SSIM itself.
  - Venkataramanan et al., "A Hitchhiker's Guide to Structural Similarity" (IEEE Access 2021, arXiv 2101.06354) †: public SSIM/MS-SSIM implementations "differ in efficiency and performance".
  - VMAF's SSIM "includes an empirical downsampling process … The other implementations, such as the SSIM filter in FFmpeg, does not include this step" [doc] ([faq.md](https://github.com/Netflix/vmaf/blob/master/resource/doc/faq.md)).
  - Nilsson & Akenine-Möller, "Understanding SSIM" (arXiv 2006.13846) †: SSIM's input colour space is undefined and it can give unexpected results on simple cases.
- **VMAF rewards sharpening:** see §3 (NEG models; the hacking papers).
- **Resolution and viewing-distance assumptions** (VMAF FAQ) [doc]:
  - The default model assumes 1080p at 3H, "angular resolution of 60 pixels/degree".
  - Scoring a 480p pair natively is "going to hide a lot of artifacts". The right way is to "upsample the 480 video to 1080, and calculate the VMAF at 1080, together with its 1080 source".
  - Example: `scale=1920x1080:flags=bicubic`; the Python harness default is `DEFAULT_RESAMPLING_TYPE = 'bicubic'`.
  - This is the closest documented precedent for "upscale the smaller to the larger, then compare".
- **Decoder differences** create false diffs before any resampling. WinIMerge #37: FreeImage's JPEG decode differs from libjpeg/WIC (mean abs diff ≈1.1, concentrated on edges). See §6.

---

## 5. How other image-diff tools handle images of different sizes

| Tool | Default placement | Scaling | Manual offset / alignment | Status |
|---|---|---|---|---|
| **Beyond Compare 4/5** (Picture Compare) | top-left; "Reset Difference Offset" returns the offset to (0,0) | **Auto Scale**: "Pick Auto Scale to automatically enlarge the smaller image to match the scale of the larger one"; command reference: "Forces pictures to have same height or width"; filter undocumented | drag in the difference pane to move the right image's top-left; arrow keys nudge 1 px, Ctrl+arrow further; also Tolerance mode and Blend mode | † |
| **Kaleidoscope** (macOS) | "Until now, images of different sizes always aligned to the center" (pre-6.4) | no scale-to-match found; zoom options Fixed / Adaptive / Fit to View | 6.4: anchor to any corner or edge; 6.6: X/Y offset and automatic AI alignment ("2D and 3D" methods, Apple Vision); 7.0.1 can switch AI alignment off | † |
| **Araxis Merge** | not documented | not documented | — | † |
| **DiffImg** | — (refuses) | — | — | † |
| **ImageMagick `compare`** | page offset, typically top-left; "the smaller image is aligned with the larger one. The extra areas in the smaller image are treated as virtual pixels"; `-define compare:virtual-pixels=false` compares only real pixels | none | `-subimage-search` "returns the best match offset" plus a similarity map | [doc] |
| **Resemble.js** | pads both to the max size at top-left; reports `isSameDimensions`, `dimensionDifference` | `.scaleToSameSize()`: "Scale second image to dimensions of the first one" via canvas `drawImage` (browser/canvas default smoothing; filter not specified) | — | [doc] |
| **pixelmatch** | — (refuses) | — | — | [doc] |
| **odiff** | top-left overlap compared; overflow pixels counted as diff | none | `--fail-on-layout` / `failOnLayoutDiff` returns `reason: "layout-diff"` (exit 21) | [doc] |
| **jest-image-snapshot** | `allowSizeMismatch` (default `false`); when allowed, both are padded to the max size at (0,0) and the extension filled with black, alpha 64 | none | — | [doc] |
| **BackstopJS** | `requireSameDimensions` (default `true`) | — | — | [doc] |
| **Python `diffimg`** | — | "the 2nd image will be resized to match the first" via Pillow `im2.resize(...)` with the default filter, so BICUBIC on Pillow ≥ 7 and NEAREST before | — | [doc] |
| **Applitools Eyes** | not found (match levels Strict/Layout/Exact only) | — | — | † |
| **Photoshop** (Difference blend) | Shift-drag of a layer into a document of different pixel size centres it | Auto-Align Layers: Auto, Perspective, Collage (rotation/scale), Cylindrical, Reposition (translation only) | manual nudge with the Difference blend mode | † |
| **GIMP** | layers sit at their offsets, typically (0,0); alignment is manual | — | — | † |
| **GitHub** image diff | modes: 2-up (shows "the actual dimension change"), Swipe, Onion skin | alignment of mismatched sizes not documented | — | [doc] |

Details and sources:

- **Beyond Compare**: [How to compare (v5)](https://www.scootersoftware.com/v5help/pix_how_to_compare.html), [commands](https://scootersoftware.com/v4help/commandspix.html).
  - Tolerance colours: gray = match, blue = unimportant, red = important.
  - The BC4 changelog says Auto Scale, Blend Toggle and Difference Offset are no longer stored with session defaults.
  - A staff forum answer says zoom uses nearest neighbour and they are "not aware of anywhere where they do filtered scaling" ([forum](https://forum.scootersoftware.com/forum/beyond-compare-4-discussion/general/82417-image-compare-ability-to-disable-bilinear-filtering)).
- **Kaleidoscope**: [release notes](https://cloud.kaleidoscope.app/support/release-notes), [6.6 blog](https://blog.kaleidoscope.app/2026/02/26/kaleidoscope-6-6-ai-powered-alignment-for-screenshots-and-photos/).
- **Araxis Merge**: the ImageComparison API counts "inserted and removed pixels (resulting from different image sizes)" as one change each ([API](https://www.araxis.com/merge/documentation-windows/api-image-comparison-object.en)). Zoom steps are 1×–32×.
- **DiffImg**: "take two images with the same size as input" ([fork](https://github.com/lingo/diffimg-xbee)).
- **ImageMagick `compare`**: `-dissimilarity-threshold` default 0.2; FFTW speeds up the subimage search; "The default metric is NCC" ([compare docs source](https://github.com/ImageMagick/Website/blob/main/docs/compare/index.html)).
- **Resemble.js**: [README](https://github.com/rsmbl/Resemble.js), [resemble.js](https://github.com/rsmbl/Resemble.js/blob/master/resemble.js).
- **pixelmatch**: "Note: all three images need to have the same dimensions". It throws "Image sizes do not match." ([index.js](https://github.com/mapbox/pixelmatch/blob/main/index.js)).
- **odiff**: "Supports comparison of images with different layouts" ([README](https://github.com/dmtrKovalenko/odiff), [diff.zig](https://github.com/dmtrKovalenko/odiff/blob/main/src/diff.zig)).
- **jest-image-snapshot**: [diff-snapshot.js](https://github.com/americanexpress/jest-image-snapshot/blob/main/src/diff-snapshot.js); README via npm.
- **BackstopJS**: README via npm ([repo](https://github.com/garris/BackstopJS)).
- **Python `diffimg`**: [diffimg](https://github.com/nicolashahn/diffimg).
- **Photoshop**: [Auto-align image layers](https://helpx.adobe.com/photoshop/desktop/create-manage-layers/create-layer-compositions/align-image-layers.html); Shift-drag behaviour from an Adobe Community answer.
- **GitHub**: [docs source](https://github.com/github/docs/blob/main/content/repositories/working-with-files/using-files/working-with-non-code-files.md).

*Inference — pattern:*
- Pixel-diff libraries default to top-left: correct for screenshots and crops, and trivially defined.
- Interactive tools add an offset control (BC, Kaleidoscope, and WinIMerge's existing *Adjust offset* mode).
- Centring was Kaleidoscope's default for years.
- Scaling exists (BC Auto Scale, Resemble.js, Python diffimg), but no tool documents its filter.
- So WinIMerge stating its kernel explicitly, and offering NN vs smooth, would be ahead of the prior art rather than behind it.

---

## 6. WinMerge / WinIMerge prior art

**Direct requests**
- **WinMerge #1916**, "Allow scaling when comparing too images of different resolution". SlySkFP, opened 2023-06-26, **open**, labels `enhancement` and `image compare/merge`; no comments, no linked PR ([issue](https://github.com/WinMerge/winmerge/issues/1916)). Body, verbatim:
  > "I often compared images which are the same but at different resolution (testing different compression)."
  > "But if the images are of diffrent resolution they don't overlap properly."
  > "It be nice to have a check box to size everything to fit the first image compared, possibly with some different options"
  > "but for my need images always have the same ratio, just different reolsution."

  sdottaka only added the labels.
- **WinIMerge #26**, "Compare image of different dimension". jindili, 2021-01-21, **open**, `enhancement`; transferred from WinMerge on 2022-01-15. It asks about comparing an original with a 2× or 3× upscaled copy. sdottaka's reply: "Unfortunately, WinMerge doesn't have the ability to scale an image to fit an image in another pane." ([issue](https://github.com/WinMerge/winimerge/issues/26))

**Related requests**
- **WinMerge #2371**, "Image Comparison : one pane not several". meteorquake, 2024-07-04, open. It asks for single-pane cycling and says "a per-image X Y offset option would be good". sdottaka: "Wouldn't it be better to use IrfanView or FastStone Image Viewer which supports Slideshow?" ([issue](https://github.com/WinMerge/winmerge/issues/2371))
- **WinMerge #323**, "Auto-zoom option" (fit to window). 2020, open, no comments ([issue](https://github.com/WinMerge/winmerge/issues/323)).
- **WinMerge #1596**, image comparison slider. 2022, open. sdottaka: "WinMerge has a similar feature." It points to the existing wipe modes; WinIMerge PR #33 (Mar 2026) sped up WipeEffect ([issue](https://github.com/WinMerge/winmerge/issues/1596)).
- **WinMerge #1391**: identical files flagged as different. Here sdottaka suggests a Color Distance Threshold "around 16" as a workaround for slight colour differences from Windows PDF rendering ([issue](https://github.com/WinMerge/winmerge/issues/1391)).
- **WinMerge #2282** (detail-presence colouring) and **#1784** (binary pre-check in folder compare): open, labelled only.

**Decoder fidelity**
- **WinIMerge #37** (Ikkoru, 2026-08-11, open): "Image compare decodes JPEGs differently from every other viewer, causing false differences" ([issue](https://github.com/WinMerge/winimerge/issues/37)).
- sdottaka: "I tried loading the image with FreeImage's JPEG_ACCURATE option, but it did not resolve the difference." Also: "The image is displayed identically when decoded with Windows Imaging Component (WIC)."
- He added "prefer WIC" in WinIMerge PR #38 ("planned to be available in WinMerge 2.16.59 and later"); the option is `Settings/ImagePreferWICDecoder`.

**How the maintainer handles feature PRs**
- The clearest recent case is #3591, "Remember the image compare splitter position" (Ikkoru, 2026-08-29) ([issue](https://github.com/WinMerge/winmerge/issues/3591)):
  - sdottaka first probed the need: "I was wondering if what you really want might be a single-pane view rather than persistent splitter position." He also raised a reset: "we would also need a way to restore the default 50:50 split."
  - He merged WinIMerge PR #39 and WinMerge PR #3593 as-is the next day with "Thank you!" and no formal review ([#39](https://github.com/WinMerge/winimerge/pull/39), [#3593](https://github.com/WinMerge/winmerge/pull/3593)).
  - He then generalised it himself. WinIMerge PR #40 (2026-09-04) switched the API to `GetSplitterRatio()/SetSplitterRatios()/ResetSplitterRatios()`, with a Copilot "lite" review ([#40](https://github.com/WinMerge/winimerge/pull/40)).
  - He stated: "I plan to make the splitter position persistent only when Window → Keep Splitter Position is checked."
- Other issues show fast, terse fixes with commit references (#3368 Blink state; #3382 WebP regression), and he asks for use cases and samples before acting.
- *Inference:* a focused, well-described WinIMerge PR plus a thin WinMerge PR, with the behaviour behind an explicit option and a clear default, matches what he merges. Expect him to adjust naming or menus afterwards, and to ask whether the need is really "alignment" or "scaling".

**Existing WinIMerge mechanisms to build on** [doc] ([WinIMergeLib.h](https://github.com/WinMerge/winimerge/blob/master/src/WinIMergeLib/WinIMergeLib.h), [ImgDiffBuffer.hpp](https://github.com/WinMerge/winimerge/blob/master/src/WinIMergeLib/ImgDiffBuffer.hpp))
- `DRAGGING_MODE { NONE, MOVE, ADJUST_OFFSET, VERTICAL_WIPE, HORIZONTAL_WIPE, RECTANGLE_SELECT, … }`, `AddImageOffset(pane, dx, dy)` and `GetImageOffset(pane)`.
- `INSERTION_DELETION_DETECTION_{NONE, VERTICAL, HORIZONTAL}` (added around 2.16.3).
- `OVERLAY_{NONE, XOR, ALPHABLEND, ALPHABLEND_ANIM}`.
- The diff grid spans the max width/height, and blocks outside either image are marked different.
- The colour test is squared Euclidean RGBA distance against `m_colorDistanceThreshold`.
- Options already persisted include `Settings/ImageDiffBlockSize`, `ImageColorDistanceThreshold`, `ImageOverlayMode`, `ImageDraggingMode`, `ImageZoom`, `ImageVectorImageZoomRatio`, `ImageSplitterRatios` and `ImagePreferWICDecoder` ([OptionsDef.h](https://github.com/WinMerge/winmerge/blob/master/Src/OptionsDef.h)).
- Context only: the local WinIMerge checkout at /home/user/winimerge, branch `claude/trusting-brown-3d75mh-align`, already holds work-in-progress commits "Add an option to align images of different sizes" and "WinIMerge: add View > Image Alignment menu". It uses a 3×3 anchor (left/centre/right × top/middle/bottom) applied on top of user offsets.

**Search coverage.** I searched WinMerge issues for image + size/different, align, resize, scale, resolution, center, offset, zoom, overlay, and the `image compare/merge` label (24 issues), all WinIMerge issues (9) and PRs (20), and WinMerge discussions for "image". I found no other request or PR for centring or scaling.

---

## Sources

Papers and primary references:
- https://dl.acm.org/doi/10.1145/54852.378514 — Mitchell & Netravali 1988, "Reconstruction Filters in Computer Graphics" † (PDF mirror: http://mentallandscape.com/Papers_siggraph88.pdf)
- https://ieeexplore.ieee.org/document/1163711 — Keys 1981, cubic convolution interpolation †
- https://bigwww.epfl.ch/research/projects/interpol.html — Thévenaz, Blu, Unser 2000, "Interpolation revisited" †
- https://en.wikipedia.org/wiki/Lanczos_resampling — Lanczos resampling; Duchon 1979 citation †
- https://www2.eecs.berkeley.edu/Pubs/TechRpts/1989/5504.html — Heckbert 1989, texture mapping and image warping (EWA) †
- https://johncostella.com/magic/ — Costella, Magic Kernel Sharp, and Facebook/Instagram use †
- https://github.com/NVlabs/flip — ꟻLIP code; `misc/LDRFLIP.txt` (citation), `src/cpp/FLIP.h`, `src/cpp/tool/commandline.h`, `misc/precision.md`, `src/nanobindFLIP.cpp`
- https://portal.research.lu.se/en/publications/flip-a-difference-evaluator-for-alternating-images/ — ꟻLIP paper record and abstract †
- https://openaccess.thecvf.com/content_cvpr_2018/html/Blau_The_Perception-Distortion_Tradeoff_CVPR_2018_paper.html — Blau & Michaeli 2018 †
- https://arxiv.org/abs/2107.04510 — Siniukov et al. 2021, "Hacking VMAF and VMAF NEG" †
- https://arxiv.org/pdf/1907.04807 — Zvezdakova et al. 2019, "Hacking VMAF with Video Color and Contrast Distortion" †
- https://hal.science/hal-01633838v1 — Krasula et al. 2017, quality assessment of sharpened images †
- https://www.cl.cam.ac.uk/~rkm38/pdfs/trentacoste12countershading.pdf — Trentacoste et al. 2012, unsharp masking, countershading and halos †
- https://arxiv.org/abs/1606.01299 — Romano, Isidoro, Milanfar, RAISR †
- https://arxiv.org/abs/2006.13846 — Nilsson & Akenine-Möller 2020, "Understanding SSIM" †
- https://arxiv.org/abs/2101.06354 — Venkataramanan et al. 2021, "A Hitchhiker's Guide to Structural Similarity" †

Libraries, applications and specifications (read in source unless marked †):
- https://github.com/ImageMagick/ImageMagick/blob/main/MagickCore/resize.c — filter table, B/C values, default-filter logic, Robidoux/LanczosSharp notes
- https://github.com/ImageMagick/ImageMagick/blob/main/MagickCore/resample.c — EWA default (Robidoux)
- https://github.com/ImageMagick/ImageMagick/blob/main/MagickCore/quantum.h — `ClampToQuantum` (clamps in non-HDRI builds only)
- https://github.com/ImageMagick/Website/blob/main/docs/command-line-options/index.html — `-filter`, `-define filter:*`, `-sample`, `-scale`, `-unsharp` docs
- https://github.com/ImageMagick/Website/blob/main/docs/compare/index.html — `compare`: size handling, `-subimage-search`, virtual pixels
- https://legacy.imagemagick.org/Usage/filter/nicolas/ — Robidoux's resampling recommendations †
- https://github.com/libvips/libvips/blob/master/libvips/resample/resize.c — `vips_resize`: kernels, centre convention, Catmull-Rom upsizing
- https://github.com/libvips/libvips/blob/master/libvips/resample/thumbnail.c — `vips_thumbnail`: stages, sRGB vs `linear`
- https://github.com/libvips/libvips/blob/master/libvips/resample/lbb.cpp — LBB (locally bounded Catmull-Rom)
- https://github.com/libvips/libvips/blob/master/libvips/resample/templates.h — kernel definitions (Catmull-Rom, Mitchell, MKS), clipping
- https://github.com/python-pillow/Pillow/blob/main/src/libImaging/Resample.c — Pillow kernels (a = −0.5, Lanczos3, MKS), support scaling, clipping
- https://github.com/python-pillow/Pillow/blob/main/src/PIL/Image.py — `resize`/`thumbnail` defaults, `reducing_gap`
- https://github.com/python-pillow/Pillow/blob/main/docs/handbook/concepts.rst — filter descriptions and comparison table
- https://github.com/python-pillow/Pillow/blob/main/docs/releasenotes/7.0.0.rst — default filter changed to BICUBIC
- https://github.com/python-pillow/Pillow/blob/main/docs/releasenotes/13.0.0.rst — MKS2013/MKS2021 added (unreleased; latest PyPI release is 12.3.0)
- https://github.com/python-pillow/Pillow/pull/8811 — Magic Kernel Sharp PR discussion
- https://github.com/opencv/opencv/blob/5.x/modules/imgproc/include/opencv2/imgproc.hpp — `InterpolationFlags`, `resize` guidance
- https://github.com/opencv/opencv/blob/5.x/modules/imgproc/src/resize.cpp — cubic `A = -0.75`, NN mapping
- https://github.com/FFmpeg/FFmpeg/blob/master/doc/scaler.texi — swscale `scaler`/`sws_flags`, bicubic B/C and Lanczos defaults
- https://github.com/FFmpeg/FFmpeg/blob/master/libswscale/utils.c — B = 0, C = 0.6 defaults in code
- https://github.com/WinMerge/freeimage/blob/winmerge/Source/FreeImage.h — `FREE_IMAGE_FILTER` enum
- https://github.com/WinMerge/freeimage/blob/winmerge/Source/FreeImageToolkit/Filters.h — FreeImage filter classes (Mitchell b = c = 1/3)
- https://github.com/WinMerge/freeimage/blob/winmerge/Source/FreeImageToolkit/Resize.cpp — centre convention, clamping
- https://github.com/WinMerge/freeimage/blob/winmerge/Wrapper/FreeImagePlus/src/fipWinImage.cpp — `drawEx` uses COLORONCOLOR (WinIMerge zoom)
- https://github.com/GNOME/gimp/blob/master/app/config/gimpcoreconfig.c — GIMP default interpolation is Cubic
- https://github.com/GNOME/gegl/blob/master/gegl/buffer/gegl-sampler-cubic.c — GEGL cubic B = 0.5, C = 0.25
- https://github.com/GNOME/gegl/blob/master/gegl/buffer/gegl-sampler-nohalo.c — NoHalo description
- https://github.com/GNOME/gegl/blob/master/gegl/buffer/gegl-sampler-lohalo.c — LoHalo description
- https://github.com/GNOME/gegl/blob/master/operations/common/unsharp-mask.c — GIMP/GEGL unsharp-mask parameters and defaults
- https://docs.gimp.org/en/gimp-tools-transform.html — GIMP NoHalo/LoHalo usage advice †
- https://helpx.adobe.com/photoshop/desktop/crop-resize-transform/resize-adjust-resolution/resampling-options.html — Photoshop resampling options †
- https://helpx.adobe.com/photoshop/desktop/create-manage-layers/create-layer-compositions/align-image-layers.html — Photoshop Auto-Align Layers †
- https://github.com/mpv-player/mpv/blob/master/DOCS/man/options.rst — mpv scale filters, anti-ringing, sigmoid and linear options
- https://github.com/haasn/libplacebo/blob/master/src/filters.c — EWA blur constants, Spline16/36/64, Robidoux
- https://github.com/lianhaidong/libpano13/blob/master/panorama.h — Panorama Tools spline16/36 definitions (mirror)
- https://github.com/google/skia/blob/main/include/core/SkSamplingOptions.h — `SkCubicResampler` Mitchell/CatmullRom
- https://github.com/chromium/chromium/blob/main/cc/paint/paint_flags.cc — Chrome filter-quality → sampling mapping
- https://github.com/chromium/chromium/blob/main/third_party/blink/renderer/platform/graphics/graphics_context_types.cc — Blink default interpolation quality (Medium)
- https://github.com/mozilla-firefox/firefox/blob/main/image/DownscalingFilter.h — Firefox Lanczos3 decode-time downscaling
- https://github.com/w3c/csswg-drafts/blob/main/css-images-3/Overview.bs — CSS `image-rendering` definitions (`pixelated` two-step, `crisp-edges` warning)
- https://learn.microsoft.com/en-us/windows/win32/api/wincodec/ne-wincodec-wicbitmapinterpolationmode — WIC interpolation modes (read via MicrosoftDocs/sdk-api source)
- https://learn.microsoft.com/en-us/windows/win32/api/d2d1_1/ne-d2d1_1-d2d1_interpolation_mode — Direct2D interpolation modes (read via sdk-api source)
- https://learn.microsoft.com/en-us/windows/win32/api/d2d1/ne-d2d1-d2d1_bitmap_interpolation_mode — `D2D1_BITMAP_INTERPOLATION_MODE` (read via sdk-api source)
- https://learn.microsoft.com/en-us/windows/win32/direct2d/high-quality-scale — Direct2D Scale effect (read via MicrosoftDocs/win32 source)
- https://learn.microsoft.com/en-us/windows/win32/api/wingdi/nf-wingdi-setstretchbltmode — GDI stretch modes (read via sdk-api source)
- https://github.com/GPUOpen-Effects/FidelityFX-CAS/blob/master/ffx-cas/ffx_cas.h — AMD CAS design notes

Metrics:
- https://github.com/google/butteraugli — Butteraugli README and API (fuzzy classes, gamma requirement)
- https://github.com/libjxl/libjxl/blob/main/tools/butteraugli_main.cc — max-norm and 3-norm output, size check
- https://github.com/libjxl/libjxl/blob/main/lib/jxl/butteraugli/butteraugli.cc — score = diffmap maximum
- https://github.com/libjxl/libjxl/blob/main/tools/cjxl_main.cc — distance in "JND units"
- https://github.com/libjxl/libjxl/blob/main/tools/ssimulacra2_main.cc — size requirements
- https://github.com/cloudinary/ssimulacra2 — SSIMULACRA2 score bands (incl. flicker test) and method
- https://github.com/NevermindNilas/frame_analytics — SSIMULACRA2 port-discrepancy write-up †
- https://github.com/Netflix/vmaf/blob/master/resource/doc/faq.md — VMAF viewing assumptions; upsample the distorted input to the reference size
- https://github.com/Netflix/vmaf/blob/master/resource/doc/models_v0.md — VMAF NEG (no enhancement gain)
- https://github.com/Netflix/vmaf/blob/master/python/vmaf/core/asset.py — `DEFAULT_RESAMPLING_TYPE = 'bicubic'`

Image-diff tools:
- https://www.scootersoftware.com/v5help/pix_how_to_compare.html — Beyond Compare Picture Compare (Auto Scale, Difference Offset) †
- https://scootersoftware.com/v4help/commandspix.html — Beyond Compare picture commands †
- https://forum.scootersoftware.com/forum/beyond-compare-4-discussion/general/82417-image-compare-ability-to-disable-bilinear-filtering — staff on NN zoom and no filtered scaling †
- https://cloud.kaleidoscope.app/support/release-notes — Kaleidoscope alignment history (6.4, 6.6, 7.0.1) †
- https://blog.kaleidoscope.app/2026/02/26/kaleidoscope-6-6-ai-powered-alignment-for-screenshots-and-photos/ — Kaleidoscope automatic alignment †
- https://www.araxis.com/merge/documentation-windows/api-image-comparison-object.en — Araxis: inserted/removed pixels from size differences †
- https://github.com/lingo/diffimg-xbee — DiffImg requires same-size inputs †
- https://github.com/rsmbl/Resemble.js — `scaleToSameSize`, top-left padding (README and `resemble.js`)
- https://github.com/mapbox/pixelmatch — same-size requirement
- https://github.com/dmtrKovalenko/odiff — different-layout handling, `--fail-on-layout`
- https://github.com/americanexpress/jest-image-snapshot/blob/main/src/diff-snapshot.js — `allowSizeMismatch` padding behaviour
- https://github.com/garris/BackstopJS — `requireSameDimensions` (README via npm registry)
- https://github.com/nicolashahn/diffimg — Python diffimg resizes the second image with Pillow
- https://github.com/github/docs/blob/main/content/repositories/working-with-files/using-files/working-with-non-code-files.md — GitHub image diff modes

Sites and services:
- https://github.com/danbooru/danbooru/blob/master/app/logical/media_file/image.rb — Danbooru resize via libvips thumbnail; JPEG/WebP settings
- https://github.com/danbooru/danbooru/blob/master/app/models/media_asset.rb — Danbooru variants and qualities
- https://github.com/danbooru/danbooru/blob/master/config/danbooru_default_config.rb — `large_image_width` default 850
- https://github.com/discord/lilliput/blob/master/opencv.go — lilliput resize uses `INTER_AREA`
- https://discord.com/blog/how-discord-resizes-150-million-images-every-day-with-go-and-c — Discord media proxy history †
- https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/partials/images/sharpen.mdx — Cloudflare `sharpen` (default 0, recommend 1 for downscaled)
- https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/partials/images/upscale.mdx — Cloudflare `upscale` (bicubic or ESRGAN)
- https://github.com/imgix/imgix-url-params/blob/master/dist/parameters.json — imgix `sharp`/`usm`/`usmrad`/`q` defaults
- https://github.com/kepstin/Fix-pixiv-thumbnails/blob/master/thumbnail_urls.md — Pixiv thumbnail URL variants (community)
- https://www.techradar.com/news/twitter-will-no-longer-downgrade-the-quality-of-your-jpegs-in-tweets — Twitter 2019 JPEG change †
- https://www.vogons.org/viewtopic.php?p=505907 — Imgur thumbnail suffixes (quoting the old API docs) †
- https://github.com/nagadomi/waifu2x — anime-art super-resolution (generative upscaling example)
- https://github.com/xinntao/Real-ESRGAN — Real-ESRGAN, incl. anime models

WinMerge / WinIMerge:
- https://github.com/WinMerge/winmerge/issues/1916 — scaling request (open)
- https://github.com/WinMerge/winimerge/issues/26 — "Compare image of different dimension"; maintainer reply
- https://github.com/WinMerge/winmerge/issues/2371 — single pane and per-image X/Y offset request
- https://github.com/WinMerge/winmerge/issues/323 — auto-zoom request
- https://github.com/WinMerge/winmerge/issues/1596 — slider/wipe request
- https://github.com/WinMerge/winmerge/issues/1391 — CD threshold ≈16 suggestion
- https://github.com/WinMerge/winmerge/issues/2282 — detail-presence colouring request
- https://github.com/WinMerge/winmerge/issues/1784 — binary pre-check request
- https://github.com/WinMerge/winimerge/issues/37 — JPEG decode differences; WIC preference
- https://github.com/WinMerge/winmerge/issues/3591 — splitter feature; maintainer review pattern
- https://github.com/WinMerge/winimerge/pull/39 — contributor PR merged as-is
- https://github.com/WinMerge/winimerge/pull/40 — maintainer follow-up generalisation
- https://github.com/WinMerge/winmerge/pull/3593 — WinMerge side PR
- https://github.com/WinMerge/winmerge/issues/3368 — Blink-state fix (response pattern)
- https://github.com/WinMerge/winmerge/issues/3382 — WebP regression fix (response pattern)
- https://github.com/WinMerge/winimerge/blob/master/src/WinIMergeLib/WinIMergeLib.h — offset, dragging, overlay and detection APIs
- https://github.com/WinMerge/winimerge/blob/master/src/WinIMergeLib/ImgDiffBuffer.hpp — diff over the max size, colour-distance test
- https://github.com/WinMerge/winmerge/blob/master/Src/OptionsDef.h — persisted image options
