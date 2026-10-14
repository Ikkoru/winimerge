# Drafts for upstream (WinMerge/winimerge and WinMerge/winmerge)

Nothing here has been posted anywhere. The branches live in the Ikkoru forks; the fork PRs are
review copies. To submit upstream, open a PR from the fork branch to `WinMerge/<repo>:master`
(GitHub's "Contribute → Open pull request" on the branch page) and paste the matching text.

## Recommended order

1. WinIMerge: alignment PR (small, self-contained) — branch `Ikkoru/winimerge:claude/trusting-brown-3d75mh-align`.
2. WinIMerge: scaling PR — branch `Ikkoru/winimerge:claude/trusting-brown-3d75mh-scale`. Independent of 1;
   whichever lands second needs a trivial rebase (both append to the interface and the View menu), plus one line:
   `m_alignImagesPending = true;` in `SetImageScalingMode()` so the alignment follows the new sizes
   (tested together: `research/tools/winimerge-linux-test/test_combined.cpp`).
3. WinMerge: the two small integration PRs (options + Image menu), after the maintainer has released a
   WinIMerge build with the new methods (WinMerge downloads WinIMergeLib.dll from releases; calling a method the
   loaded DLL lacks would crash). In the user's earlier contribution (winimerge#39 + winmerge#3593) the maintainer
   handled the release and the submodule bump himself.

Why PRs rather than an issue first: the maintainer merges focused PRs quickly and adjusts details himself
(winimerge#39 → #40 reworked the splitter API the next day). A PR with the core in the library, the UI as a
separate small commit, and an explicit "happy to move the setting" lets him place the setting wherever he likes
without a round-trip. WinMerge issue #1916 (open, no maintainer reply) can be referenced from the scaling PR.

---

## 1. WinIMerge PR: alignment

**Title:** Add an option to align images of different sizes (e.g. center the smaller image)

(Body: identical to Ikkoru/winimerge#1, minus the fork links: https://github.com/Ikkoru/winimerge/pull/1)

## 2. WinIMerge PR: scaling

<!-- SCALING-PR -->

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
