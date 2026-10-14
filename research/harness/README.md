# The study harness

Python code that makes the test pairs, runs every candidate way of showing them in WinIMerge, and
measures the result. Everything runs offline once the tools and images are in place. Tested on
Linux x86-64 (Ubuntu, Python 3.13); WSL should work the same.

## Setup

```sh
pip install numpy pandas matplotlib pillow opencv-python-headless scipy scikit-image skia-python flip-evaluator
sudo apt install libegl1 libgl1          # skia-python needs them, even headless
sudo apt install libfreeimage3           # FreeImage 3.18: resamples bit-identically to WinMerge's fork
```

Optional, for exactness or the extra metrics (each is picked up through an environment variable):

| What | Why | How |
|---|---|---|
| WinMerge's FreeImage fork as a `.so` (`FREEIMAGE_LIB`) | the exact library WinMerge ships (3.18 gives identical resampling, so this is only a check) | `git clone https://github.com/WinMerge/freeimage`; add `Source/LibTIFF4/tif_hash_set.c` to `Makefile.srcs` (otherwise the `.so` fails with `undefined symbol: TIFFHashSetNew`); `make -f Makefile.gnu` |
| libjxl's `butteraugli_main` and `ssimulacra2` (`LIBJXL_TOOLS` = their folder) | Butteraugli and SSIMULACRA2 columns (the `heavy` experiment) | `git clone https://github.com/libjxl/libjxl && cd libjxl && ./deps.sh && cmake -B build -G Ninja -DJPEGXL_ENABLE_DEVTOOLS=ON -DBUILD_TESTING=OFF && ninja -C build butteraugli_main ssimulacra2` (≈1.5 min on 4 cores) |
| jpeg-quantsmooth (`JPEGQS` = the `jpegqs` binary, or `jpegqs` on PATH) | the `jpegqs` experiment and `compression_test.py` | `git clone https://github.com/ilyakurdyukov/jpeg-quantsmooth && make` (needs libjpeg-turbo headers; it builds with `-march=native`, so rebuild it on a different CPU: an old build stops with "Illegal instruction") |

Without `LIBJXL_TOOLS` and `flip-evaluator` the cheap metrics (WinMerge's block outcome, PSNR, SSIM)
still work.

## Test images

```sh
python3 harness/synth.py testset/synth            # the 7 synthetic originals (deterministic)
# real originals: download the files listed in testset/sources/MANIFEST.md into testset/sources
# (the SHA-256 of each file is in MANIFEST.json), then cut the same windows as the study:
python3 harness/make_real_crops.py                # writes testset/real/*.png and testset/large_real links
mkdir -p testset/large && ln -s ../synth/*.png testset/large/
```

## Files

| File | What it does |
|---|---|
| `fi.py` | ctypes wrapper for `FreeImage_Rescale`, 8-bit path (as WinIMerge without float) and float path (`FreeImage_ConvertToRGBAF` first, as WinIMerge's UP_SMOOTH) |
| `resample.py` | the shrinkers that make the small copies (Pillow, OpenCV, libvips-like, Mitchell, linear light, sharpened), the float reference resampler, NN, unsharp mask |
| `synth.py` | synthetic originals rendered with skia at their final size |
| `edits.py` | the edits applied to the original before shrinking (text, line, recolour, bar, mosaic, smudge, move, dot) |
| `metrics.py` | WinMerge's block outcome (8×8 blocks, colour distance > T, any pixel), T_p99, PSNR, SSIM, ꟻLIP, Butteraugli, SSIMULACRA2 |
| `study.py` | the experiments (`python3 study.py list`), resumable runner writing `results/<exp>_<tag>.csv`; `--down-only` adds missing compare-at-the-smaller-size rows to an existing CSV |
| `report.py` | `results/tables.md` from the CSVs (each table compares candidates on the same pairs) |
| `charts.py` | `charts/*.png` |
| `eyecheck.py` | the flip page (`eyecheck/index.html`, self-contained) |
| `compare_pairs.py` | the same measurements on your own image pairs |
| `make_real_crops.py` | recreates the real-image crops from the sources |
| `heavy_analysis.py` | perceptual metrics (heavy run): medians per candidate and how well each metric agrees with WinMerge's outcome |
| `chroma_test.py` | JPEG 4:2:0 chroma upsampling (libjpeg's smooth default vs replicated) |
| `roundtrip_test.py` | the brief's suggestion 4 (matched shrink, then enlarge both panes) vs comparing at the small size, with edit detection on ꟻLIP maps too |
| `im_spotcheck.py` | copies made by ImageMagick (default, Catmull-Rom, WordPress's thumbnail recipe, linear light): does the matched shrink reproduce them? |
| `run_chain3.sh`, `run_chain4.sh` | every `study.py` experiment, in order (resumable); chain 3 first, then chain 4 |
| `tiny_edits.py` | follow-up: tiny edits (1–6 px dots, hairlines; flat or busy spot; in either file) under three save scenarios, incl. a lossless small copy with a lossy large file |
| `pixelart_test.py` | follow-up: pixel art at two sizes (NN zooms, smooth or point-sampled thumbnails) with logical-pixel edits |
| `compression_test.py` | follow-up: `recover` (one-time vs re-saved JPEGs before/after jpegQS) and `keep` (is a smaller copy worth keeping next to a lossy large file?) |
| `eyecheck2.py` | eye-check page, round 2 (blind trials, compression cases, filters on PNG copies) |
| `blocksize_check.py` | follow-up: the round trip against the shrink with the same block area (WinMerge's Diff Block Size) |
| `cr_vs_l3.py` | follow-up: Catmull-Rom against Lanczos3 as the enlarger, by the models of the eye (PNG copies) |
| `jpeg_history.py` | was a JPEG saved more than once? (ghost and shifted-grid checks); `--test` measures it on known histories; also usable on your files |
| `keep_check.py` | **for your pairs**: is the smaller copy worth keeping next to the larger one? (lossless or JPEG, earlier saves, the larger file's damage at the smaller size; `--jpegqs` compares restored copies too) |
| `followup_report.py` | `results/tables_followup.md` from the follow-up CSVs |

## Running

```sh
cd harness
python3 study.py run spurious --images ../testset/large --tag synth --jobs 4   # one experiment
./run_chain3.sh && ./run_chain4.sh                                             # everything (many hours)
python3 roundtrip_test.py; python3 im_spotcheck.py; python3 chroma_test.py     # the side experiments
python3 tiny_edits.py; python3 pixelart_test.py                            # follow-up round
python3 compression_test.py recover; python3 compression_test.py keep
python3 blocksize_check.py; python3 cr_vs_l3.py; python3 jpeg_history.py --test
python3 followup_report.py && python3 eyecheck2.py                          # tables and page 2
python3 keep_check.py LARGE.jpg SMALL.png --jpegqs                         # keep both? (your own files)
python3 jpeg_history.py FILE.jpg                                           # saved more than once?
python3 report.py && python3 charts.py && python3 eyecheck.py --out ../eyecheck
python3 compare_pairs.py /path/to/my/pairs --heavy --eyecheck /path/to/out    # your own pairs
```

## Checks that the harness is right

- `python3 metrics.py` runs the self-test: every metric reports "identical" for an image against itself.
- The float reference resampler reproduces FreeImage's float path exactly; FreeImage's 8-bit path
  matches Pillow's resize within 1–2 levels (`DISCOVERIES.md` §1, §3, §7).
- `tools/winimerge-linux-test` builds WinIMerge's real `ImgDiffBuffer.hpp` on Linux and checks that its
  scaled images are bit-identical to `fi.py`'s.
