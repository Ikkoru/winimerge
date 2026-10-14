# WinIMerge / WinMerge image compare: how the code works (notes for future sessions)

Read on 2026-10-14 from WinMerge/winimerge `master` at `da639cd` (= Ikkoru/winimerge `master`) and
WinMerge/winmerge `master` at `ea828d5`. Line numbers drift; search for the names.

## Layers

| Layer | File | Role |
|---|---|---|
| Public interface | `src/WinIMergeLib/WinIMergeLib.h` | `IImgMergeWindow` (abstract, vtable ABI), `IImgToolWindow`, `WinIMerge_Create*` exports |
| Window | `src/WinIMergeLib/ImgMergeWindow.hpp` | `CImgMergeWindow : IImgMergeWindow` — panes, splitter, mouse/drag modes, forwards most calls to the buffer then `Invalidate()` |
| Pane | `src/WinIMergeLib/ImgWindow.hpp` | `CImgWindow` — one scrollable pane; draws the pane's diff image with zoom; centres the whole canvas in the pane when it is smaller than the window (`ConvertLPtoDP`) |
| Merge buffer | `src/WinIMergeLib/ImgMergeBuffer.hpp` | `CImgMergeBuffer : CImgDiffBuffer` — editing: CopyDiff, Resize, Paste, Delete, Undo/Redo, Save |
| Diff buffer | `src/WinIMergeLib/ImgDiffBuffer.hpp` | `CImgDiffBuffer` — loading, preprocessing, comparing, overlays, marking; platform-independent except `ImgConverter.hpp` |
| Image | `src/WinIMergeLib/image.hpp` | `Image` wraps `fipImageEx` (FreeImagePlus); `scanLine(y)` is top-down (FreeImage is bottom-up internally) |
| Tool window | `src/WinIMergeLib/ImgToolWindow.hpp` + `WinIMergeLib.rc` `IDD_DIALOGBAR` | the side panel with sliders, combos and the diff map; shared by WinIMerge.exe and WinMerge |
| App | `src/WinIMerge/WinIMerge.cpp/.rc` | the standalone WinIMerge.exe; menus in `WinIMerge.rc`, no persisted settings |
| CLI | `src/cidiff/cidiff.cpp` | writes `diff.png`; can build on non-Windows against the buffer only |

## Image pipeline inside `CImgDiffBuffer`

`m_imgOrig[pane]` (as loaded, any bpp) → `m_imgOrig32` (32-bit BGRA copy; edits happen here) →
`PreprocessImages()` → `m_imgPreprocessed` (what is compared; with insertion/deletion detection, ghost lines are
inserted here) → `CompareImages2()` → `m_diff` block map → `RefreshImages()` → `m_imgDiff[pane]` (the canvas each
pane displays: max size of all images, each image copied at its offset, overlays and marks drawn on it).

- `CompareImages()` = `PreprocessImages()` + `InitializeDiff()` + `CompareImages2()` + `MarkDiffIndex()` + `RefreshImages()`.
  It runs on **every** option change (threshold, block size, page, rotation, ...), so anything expensive in
  preprocessing must be cached.
- **Offsets**: `m_offset[pane]` (`Point<unsigned>`), normalised so the minimum is 0. `AddImageOffset()` (Adjust Offset
  drag, Shift+arrows) changes it; `CloseImages()` resets it. `GetMaxWidthHeight()` = max(preprocessed size + offset)
  is the canvas size. Pixels outside an image count as different (`diff = -1`).
- **Diff rule** (`CompareImages2`): a pixel differs if any of B, G, R, A differs (threshold 0) or if the Euclidean
  distance over B, G, R, A exceeds the threshold. A differing pixel marks its whole block (default 8×8).
  `MarkDiffIndex()` floods 8-connected marked blocks into regions; the status bar's "Diff" count is regions.
- **Rotation/flip** are not applied to the stored images: `TemporaryTransformation` applies them to `m_imgOrig32`
  for the duration of preprocessing or an edit and undoes them afterwards. Code inside such a scope sees the
  rotated image, so `GetImageWidth()` (which swaps width/height itself for 90/270°) is wrong there.
- **`ConvertToRealPos(pane, x, y)`** maps canvas coordinates to original-image coordinates (offset, ghost lines).
  It is the single place selections, status bar, copy/paste and CopyDiff use; a new transformation of the
  preprocessed images (like scaling) must be undone here.
- **Ghost lines** (`INSERTION_DELETION_DETECTION_*`): a line diff (xdiff in `Diff.hpp`) between rows (or columns,
  via transposed images) inserts empty rows so matching rows line up; `m_lineDiffInfos` holds the mapping.

## Editing (`CImgMergeBuffer`)

- Every edit pushes old/new bitmaps of one pane on `UndoRecords` and calls `CompareImages()`.
- `CopyDiffInternal()` copies a diff region pixel by pixel through `ConvertToRealPos()` of both panes; if the region
  extends past the destination image it first enlarges `m_imgOrig32[dst]` and lowers `m_offset[dst]`. With ghost
  lines and all offsets zero it also inserts/deletes rows.
- **Pre-existing issues found** (reproduced on unmodified master with the Linux harness, not fixed):
  1. Copying a difference to the right of / below a smaller image enlarges it but leaves the new area empty:
     the copy loop checks against the old `m_imgPreprocessed` size.
  2. Undo of a copy that enlarged an image to the left/top restores the bitmap but not `m_offset`.
  3. The ghost-line branches of `ConvertToRealPos()` compare with `GetImageWidth/Height()`, which is wrong inside a
     `TemporaryTransformation` scope for 90/270° rotation (CopyDiff runs inside one).
  4. In horizontal insertion/deletion detection, the 3-way comparison lambda `compfunc02` compares *rows* of the
     untransposed images using column indices.

## Resampling available in the code that ships

FreeImage (WinMerge fork, branch `winmerge`, 3.19 — resamples bit-identically to upstream 3.18):
`FreeImage_Rescale(dib, w, h, FILTER_BOX | FILTER_BILINEAR | FILTER_BSPLINE | FILTER_BICUBIC (Mitchell 1/3,1/3) |
FILTER_CATMULLROM | FILTER_LANCZOS3)`, wrapped by `fipImage::rescale()`. 8-bit images keep an 8-bit intermediate
between the two passes (clips overshoot). Convert with `FreeImage_ConvertToRGBAF()` first for a float path. Box at a
whole-number enlargement is exact nearest neighbour.

## WinMerge side

- WinMerge does **not** build WinIMerge from source by default: `DownloadDeps.cmd` downloads release zips of
  WinIMergeLib.dll (`https://github.com/WinMerge/winimerge/releases/download/vX.Y.Z/...`). `Externals/winimerge` is a
  submodule (for reference/builds), and `Src/WinIMergeLib.h` is a **copy** of the interface that `Src/ImgMergeFrm.h`
  includes. A new interface method therefore needs: a WinIMerge release, `DownloadDeps.cmd` + `Externals/versions.txt`
  + submodule bump (maintainer), and the copy updated. Calling a method the loaded DLL does not have crashes (vtable).
- Options: `Src/OptionsDef.h` (`OPT_CMP_IMG_*` → `Settings/Image*` registry values), defaults/ranges in
  `Src/OptionsInit.cpp`, applied in `CImgMergeFrame::LoadOptions()`, written in `SaveOptions()`.
- The Image menu in the menu bar and the image view's popup are the same resource, `IDR_POPUP_IMGMERGEVIEW` in
  `Src/Merge.rc` (loaded by `MainFrm.cpp`). Handlers: `ON_COMMAND_RANGE`/`ON_UPDATE_COMMAND_UI_RANGE` in
  `Src/ImgMergeFrm.cpp`, each `OnImgX()` sets the value and calls `SaveOptions()`.
- Options dialog page for images: `Src/PropCompareImage.cpp` (file patterns, folder-compare image compare, prefer WIC,
  OCR result type) with its dialog in `Merge.rc`.
- Folder compare uses a windowless `IImgMergeWindow` (`Src/CompareEngines/ImageCompare.cpp`) and only sets the color
  distance threshold and the WIC preference; it does not see view options such as alignment or scaling.
- Translations: new menu strings must reach `Translations/WinMerge/English.pot` and the `.po` files; the maintainer
  regenerates them with scripts (Windows), which rewrites the line references in every `.po`.
- Upstream history shows the maintainer (Takashi Sawanaka, sdottaka) merging contributor PRs quickly and then
  adjusting the API themselves (e.g. the splitter position API, winimerge #39 → #40).

## Building and testing without Windows (this session's tools)

- `research/tools/winimerge-linux-test/build.sh <winimerge-checkout> [test.cpp]`: compiles the real
  `ImgDiffBuffer.hpp`/`ImgMergeBuffer.hpp`/`image.hpp`/`Diff.hpp` with a stub `ImgConverter.hpp` against system
  FreeImage (`apt install libfreeimage-dev libfreeimageplus-dev`) and runs the tests. `TestBuffer::SetImages()` feeds
  in-memory images (FreeImage's wide-char loading is Windows-only).
- `research/tools/mingw-syntax-check.sh <winimerge-checkout>`: compiles WinIMergeLib.cpp, WinIMerge.cpp, cidiff.cpp
  and both `.rc` files with MinGW i686 (`-fsyntax-only`, windres) after mechanical MSVC-ism fixups in a temp copy.
  Does not cover `_WIN64`-only code (WIC/PDF/SVG/OCR) or linking. See `research/tools/MINGW-CHECK.md`.
- WinIMerge's GitHub Actions CI builds with MSBuild on `windows-latest` on push/PR to `master`, but Actions are not
  enabled on the Ikkoru fork (no workflows registered), so fork PRs get no Windows build.
