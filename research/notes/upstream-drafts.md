# Drafts for upstream (WinMerge/winimerge and WinMerge/winmerge)

Nothing here has been posted anywhere. The branches live in the Ikkoru forks; the fork PRs are
review copies. To submit upstream, open a PR from the fork branch to `WinMerge/<repo>:master`
(GitHub's "Contribute → Open pull request" on the branch page) and paste the matching text.

## Recommended order

0. WinIMerge: the bug-fix PR (`claude/trusting-brown-3d75mh-fix-bounds`): two clamps, fixes a crash on master.
1. WinIMerge: alignment PR (small, self-contained) — branch `Ikkoru/winimerge:claude/trusting-brown-3d75mh-align`.
2. WinIMerge: scaling PR — branch `Ikkoru/winimerge:claude/trusting-brown-3d75mh-scale`. Independent of 1;
   whichever lands second needs a trivial rebase (both append to the interface and the View menu), plus one
   change so the alignment follows a pane whose scale changes: in `ScaleImages()`, set
   `m_alignImagesPending = true` when a pane's `scaleX`/`scaleY` differs from the previous value
   (tested together: `research/tools/winimerge-linux-test/test_combined.cpp`, 30 checks).
3. WinMerge: the two small integration PRs (options + Image menu), after the maintainer has released a
   WinIMerge build with the new methods (WinMerge downloads WinIMergeLib.dll from releases; calling a method the
   loaded DLL lacks would crash). In the user's earlier contribution (winimerge#39 + winmerge#3593) the maintainer
   handled the release and the submodule bump themselves.

Why PRs rather than an issue first: the maintainer merges focused PRs quickly and adjusts details themselves
(winimerge#39 → #40 reworked the splitter API the next day). A PR with the core in the library, the UI as a
separate small commit, and an explicit "happy to move the setting" lets them place the setting wherever they like
without a round-trip. WinMerge issue #1916 (open, no maintainer reply) can be referenced from the scaling PR.

---

## 1. WinIMerge PR: alignment

**Title:** Add an option to align images of different sizes (e.g. center the smaller image)

(Body: identical to the fork PR https://github.com/Ikkoru/winimerge/pull/1.)

## 2. WinIMerge PR: scaling

**Title:** Add an option to scale images of different sizes for comparison

**Body** (the fork PR https://github.com/Ikkoru/winimerge/pull/2 with upstream references; replace #NN
with the real numbers, and the research link if the branch moves):

> ## Summary
>
> When one image is a resized copy of the other (a thumbnail, a re-upload, a downscaled export), WinIMerge compares the copy with the top-left part of the original at its own size, so almost everything is marked as different (WinMerge/winmerge#1916, #26). This adds `IImgMergeWindow::SetImageScalingMode()`, which scales the images to a common size before they are compared:
>
> ```cpp
> enum IMAGE_SCALING_MODE {
>     IMAGE_SCALING_NONE = 0,            // as today
>     IMAGE_SCALING_UP_NEAREST_INTEGER,  // enlarge smaller images by the largest whole-number factor that fits (nearest neighbour)
>     IMAGE_SCALING_UP_SMOOTH,           // enlarge smaller images to the largest image's size (Lanczos3)
>     IMAGE_SCALING_DOWN_MATCHED,        // shrink larger images to the smallest image's size, with the filter that reproduces it best
> };
> virtual IMAGE_SCALING_MODE GetImageScalingMode() const = 0;
> virtual void SetImageScalingMode(IMAGE_SCALING_MODE mode) = 0;
> ```
>
> The originals are not changed: scaling happens in `PreprocessImages()`, like rotation and flipping, and saving, undo and edits work on the original pixels.
>
> ## Which mode does what (measured)
>
> I measured the three modes on synthetic originals (line art, cel shading, painterly strokes, manga screentone, UI text, pixel art, a zone plate), with smaller copies made the way websites and libraries make them (Pillow bilinear/bicubic/Lanczos, libvips, OpenCV area and linear, Mitchell, Lanczos in linear light, sharpened, nearest), at factors 1.25 to 4, saved as PNG and as JPEG. Results on real illustrations, paintings, photos and screenshots are in the report linked below.
>
> The number below is the colour-distance threshold a user would have to set before at most 1 % of the 8×8 blocks are marked on an **unedited** pair (median of 70 pairs per cell, synthetic set; lower is better; for scale, WinIMerge's threshold menu goes up to 64):
>
> | copy saved as | mode | 1.25× | 1.5× | 2× | 2.5× | 3× | 4× |
> |---|---|---|---|---|---|---|---|
> | PNG | enlarge, whole-number NN | – | – | 238 | – | 321 | 314 |
> | PNG | enlarge, Lanczos3 | 94 | 139 | 207 | 261 | 242 | 253 |
> | PNG | **shrink, matched filter** | **3** | **4** | **2** | **5** | **3** | **4** |
> | JPEG q85 | enlarge, whole-number NN | – | – | 248 | – | 326 | 317 |
> | JPEG q85 | enlarge, Lanczos3 | 98 | 142 | 216 | 265 | 252 | 257 |
> | JPEG q85 | **shrink, matched filter** | **45** | **46** | **42** | **52** | **53** | **60** |
>
> (– : whole-number NN does nothing below 2×, and at 2.5× it enlarges by 2, so the copy covers 80 % of the original's size, does not line up with it, and the uncovered part is marked as different.)
>
> At the menu's highest threshold, 64, shrinking leaves at most 0.4 % of the blocks marked even with JPEG copies (with PNG copies, 0 % already at 16); the enlargers leave 8–35 % (and NN 70–83 % at the factors where it does not fill the canvas).
>
> Real changes stay visible: on 1008 edited pairs (small text, a thin line, a faint recolour, a smudge, a moved region, a 3-px dot, ...; factors 2–4; PNG and JPEG), with the threshold set where 1 % of the unedited blocks are marked, the edit is still marked in **98 %** of pairs when shrinking (99 % if the true resampler were known), 80 % with Lanczos3 and 53 % with whole-number NN. On 1080 edited pairs of real pictures: 96 % when shrinking (100 % with PNG copies), 94 % with Lanczos3, 51 % with whole-number NN; with JPEG copies the smooth modes find about as many edits, but shrinking marks much more of each one (71 % of its blocks against 51 %).
>
> - **Shrinking to the smaller size is the useful mode for resized copies.** The original then goes through the same resampling as the copy, so what remains is real changes and compression noise. Copies made by Pillow's bilinear, bicubic or Lanczos resize and by OpenCV's `INTER_AREA` are reproduced exactly (threshold 0 for PNG copies), Mitchell-made ones to within rounding, ImageMagick's (WordPress thumbnails included) to within a level or two, and libvips ones closely (median 14). Copies resized in linear light, sharpened afterwards, or shrunk without antialiasing (nearest neighbour, OpenCV's `INTER_LINEAR`) cannot be reproduced exactly, but still compare far better than any enlargement.
> - **Enlarging cannot remove most differences on detailed images**, whatever the filter, because the detail lost in the copy is not there to restore. Of the common filters, Lanczos3 (and Lanczos4) need the lowest threshold; an unsharp mask after it moved the numbers by only a few percent either way, so I left it out.
> - **Whole-number nearest neighbour** keeps every pixel of the copy exact, which is right for pixel art and for looking at the copy itself. As a comparison it marks about as many blocks as Lanczos3 at whole-number factors, but its differences are stronger (each edge becomes a staircase), it does nothing below 2×, and at factors such as 2.5× it enlarges by 2, so the copy stays smaller than the original (80 %) and the two line up only at the anchor point.
> - **Perceptual metrics** (ꟻLIP, Butteraugli, SSIMULACRA2) agree that shrinking is by far the closest. Between the two enlargers it depends on the picture: at 2×, ꟻLIP (built to predict what a viewer notices when flipping between two images) rates the nearest-neighbour enlargement closer to the original than Lanczos3 for line art, flat colour, manga and text (89 % of the synthetic pairs, 65 % of the real ones), while for paintings and photos, at 3×, and by WinMerge's own threshold and the share of edits found, Lanczos3 comes out ahead. So both enlargers have a use: NN for looking at a 2× copy of line art or pixel art, Lanczos3 otherwise (though for finding differences, shrinking is far better than either).
>
> The full study (method, test images, harness, all tables, and a page for flipping between the candidates by eye) is here: https://github.com/Ikkoru/winimerge/tree/claude/trusting-brown-3d75mh/research (`REPORT.md`).
>
> ## How it works
>
> - `ScaleImages()` runs in `PreprocessImages()` inside the temporary rotation/flip, so the comparison, overlays, blinking, insertion/deletion detection and the diff map see equal-size images without further changes.
> - Sizes: whole-number NN enlarges by k = min(Wmax / w, Hmax / h), rounded down, when k ≥ 2 (so it does nothing below 2×, and at e.g. 2.5× the enlarged copy stays smaller than the original). The other two modes scale uniformly and, when the aspect ratios differ only by the rounding of a resized copy (≤ 1 source pixel), snap to the reference size so that both edges line up.
> - All resampling uses FreeImage's 8-bit path. For DOWN_MATCHED that is deliberate: it is what Pillow and most libraries do, so FreeImage reproduces their shrinks to within rounding. For UP_SMOOTH a float path (no clipping of the Lanczos overshoot between the two passes) made no measurable difference to the comparison but took 2.4× as long and much more memory, so it is not used.
> - DOWN_MATCHED tries FreeImage's box, bilinear, Mitchell ("bicubic"), Catmull-Rom and Lanczos3 filters and, in the third commit, exact area averaging, and keeps the one with the lowest mean absolute difference from the smallest image. That pick is within one level of the best of them (judged by the comparison outcome itself) in 88 % of PNG pairs and 80 % of JPEG pairs. The choice describes how the copy was made, so it is made once per image pair and size and kept after edits of either image: matching costs a few seconds for a 24-megapixel image, once; an edit then costs one resample.
> - Scaled images are cached (keyed by a hash of the source image, the target size and the mode), because `CompareImages()` runs again on every option change.
> - `ConvertToRealPos()` maps canvas positions to original pixels, so the status bar refers to the original image; selection edges map so that a selection holds the original pixels whose centres lie inside it.
> - `CopyDiff()` copies the pixels the source pane *shows* into the original pixels of the destination they stand for, so the difference disappears (e.g. from an enlarged copy into the original, or from a shrunk original into the copy). It does not copy *into* a pane that is shown through a smoothing filter (UP_SMOOTH, DOWN_MATCHED): the copied pixels would be resampled together with their neighbours again, so the difference would grow instead of disappear. A scaled image is not enlarged by `CopyDiff()`, and the insertion/deletion row handling is skipped while any image is scaled.
> - `IMAGE_SCALING_NONE` (the default) keeps today's behaviour exactly; the new methods are appended to `IImgMergeWindow`, so the existing vtable order is unchanged.
>
> ## UI
>
> The library change is the first commit. The second commit adds a **View > Size Matching** radio submenu to WinIMerge.exe as an example (not "Image Scaling", to avoid confusion with Vector Image Scaling just below it). For WinMerge there is a matching PR that adds **Image > Size Matching** and saves `Settings/ImageScalingMode`: WinMerge/winmerge#NN. If you prefer other names, fewer modes, or the option on the Options page, I'm happy to change it.
>
> This is independent of #NN (alignment). Whichever is merged second needs a trivial rebase (both append to the interface and the View menu), plus one change so that the alignment follows a pane whose scale changes (a mode change, or an edit that changes the scale): in `ScaleImages()`, set `m_alignImagesPending = true` when a pane's `scaleX`/`scaleY` differs from the previous value. Tested together (30 checks).
>
> ## Testing
>
> - Unit tests on Linux (the diff buffer built against FreeImage, with a stub for `ImgConverter.hpp`): 158 checks covering the sizes and factor rules, snapping, the cache and its invalidation, DOWN_MATCHED finding each filter exactly (area averaging included), the filter being kept after edits, copying differences between scaled panes (only in the directions allowed, difference gone afterwards), undo, rotation, insertion/deletion detection, selection mapping, and the default path unchanged.
> - An independent review ran ~2,500 random edit sequences (2/3 panes, every mode, ghost lines, rotation/flip, offsets, CopyDiff/All/3Way, Undo/Redo, Resize, Delete, Paste) under AddressSanitizer: no new crash sites, and with the option at its default the results are bit-identical to `master`. Its findings (re-matching on every edit, copies into smoothed panes, the float path's cost, scroll bars) are fixed here; a re-run on these final commits (400 sequences, same seed as on `master`) hit only the crash sites `master` has too, all pre-existing (listed in #NN, the alignment PR; the Delete/Paste one is fixed in #NN).
> - The scaled images of all three modes are bit-identical to the Python harness used for the measurements (WinMerge's FreeImage fork and FreeImage 3.18 resample identically); the area resampler agrees with OpenCV's `INTER_AREA` to within one level.
> - WinIMergeLib.cpp, WinIMerge.cpp and both .rc files compile with MinGW (i686, `-fsyntax-only` + windres).
> - **Not yet built with MSVC or run on Windows.**
>
> ## Known limitations
>
> - Dragging or pasting a selection in a scaled pane previews it at its original size; the result lands in the right place.
> - In the two smooth modes, differences can be copied out of the resampled pane but not into it; the copy commands stay enabled and do nothing in that direction. With whole-number NN, copying into the enlarged copy works but cannot carry the original's detail.
> - The status bar shows the original pixel's position but the colour of the shown (resampled) pixel.

## 2b. WinIMerge PR: bug fix (Delete/Paste outside the image)

**Title:** Keep Delete and Paste inside the image

(Body: identical to the fork PR https://github.com/Ikkoru/winimerge/pull/3. Independent of the two
feature PRs; worth submitting first, since alignment and scaling make the crash easier to hit.)

## 3. WinMerge PR: alignment

**Title:** Add Image > Image Alignment to align images of different sizes

**Body:**

> Adds an **Image > Image Alignment** submenu (nine anchor points; Top Left is the current behaviour) and saves
> the choice as `Settings/ImageAlignment` with the other image compare options.
>
> Depends on WinMerge/winimerge#NN (`IImgMergeWindow::SetImageAlignment()`), so it needs a WinIMerge release
> with that change and the usual `DownloadDeps.cmd` / `Externals/winimerge` / `versions.txt` bump before it
> can be merged. `Src/WinIMergeLib.h` is updated to match. The new menu strings still need to go through the
> translation files.
>
> If you would rather offer only Top Left / Center, or put it on the Options > Compare > Image page instead of
> the menu, I'm happy to change it.

## 4. WinMerge PR: scaling

**Title:** Add Image > Size Matching to compare images of different sizes

**Body:**

> Adds an **Image > Size Matching** submenu for `IImgMergeWindow::SetImageScalingMode()`: None (the
> current behaviour), Enlarge by Whole Number (Nearest Neighbor), Enlarge to Largest (Lanczos) and
> Shrink to Smallest (Matched Filter). The choice is saved as `Settings/ImageScalingMode` with the other
> image compare options. It is not called "Image Scaling" because of the Vector Image Scaling submenu
> below it.
>
> Depends on WinMerge/winimerge#NN, so it needs a WinIMerge release with that change and the usual
> `DownloadDeps.cmd` / `Externals/winimerge` / `versions.txt` bump before it can be merged.
> `Src/WinIMergeLib.h` is updated to match. The new menu strings still need to go through the
> translation files.
>
> This is what #1916 asks for. With Shrink to Smallest, a copy made by a website's or a library's
> resizer compares as (almost) identical to its original, and real edits remain visible; the WinIMerge
> PR has the measurements. If you would rather offer fewer modes, or put the option on the
> Options > Compare > Image page, I'm happy to change it.

## 5. Optional comment for WinMerge issue #1916

> Hi! I've opened WinMerge/winimerge#NN, which adds this as an option (and WinMerge/winmerge#NN for the
> menu): the images can be compared after enlarging the smaller one (by a whole-number factor with
> nearest neighbour, or to the larger size with Lanczos3) or after shrinking the larger one to the
> smaller size with the resampling filter that reproduces the smaller image best. For copies at a
> different resolution, the last one works best: a resized copy then compares as (almost) identical,
> and real changes remain visible. It scales to the largest or smallest image rather than to the first
> one, so the result does not depend on the order of the files.
