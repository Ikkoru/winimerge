"""Was this JPEG saved more than once? A quick forensic check, to tell recoverable damage from unrecoverable.

    python3 jpeg_history.py FILE.jpg [FILE2.jpg ...]   # report on your own files
    python3 jpeg_history.py --test [--jobs 2]          # accuracy on the JPEG histories of compression_test.py

jpegQS can only undo the last save, and the file's quantisation tables only tell the last save's quality,
so a "q90" that was saved three times looks like a one-time q90 (REPORT section 10.3). Two classic traces of
an earlier save survive in the pixels:

  JPEG ghost    an earlier save at a lower quality on the same 8x8 grid: re-saving the picture at that
                quality changes it less than at the qualities around it, a dip in the re-save difference
                curve below the file's own quality (Farid 2009, "Exposing digital forgeries from JPEG
                ghosts").
  shifted grid  an earlier save whose grid did not line up with this file's (cropped or padded between
                saves): on that grid the DCT coefficients still cluster at multiples of the earlier
                quantisation step (Bianchi and Piva 2012, "Detection of nonaligned double JPEG compression
                based on integer periodicity maps"). Scored per grid offset as the strength of the
                periodicity, |mean(exp(2 pi i c / q))| * sqrt(n), over low frequencies and steps q 2..24.

What it cannot see: an earlier save at a quality as high as the last one on a shifted grid (the later
save's rounding hides the old steps), an earlier save at a higher quality than the last, and anything
before a resize. Pictures that are almost all pure black and white (clipped blocks) leave only the ghost
check. Pictures over 2 megapixels are checked on a central crop of that size (the grid kept). Measured
on 9 masters x 10 histories with `--test` (results/jpeg_history_test.csv).
"""
import argparse
import io
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image
from scipy.fft import dctn

STD_LUMA = np.array([16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56,
                     14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
                     49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99], np.float64)
FREQS = [(0, 1), (1, 0), (1, 1), (0, 2), (2, 0)]
STEPS = np.arange(2, 25)
GRID_MIN, GRID_RATIO = 12.0, 2.5   # a shifted grid: score >= 12 and >= 2.5x the median of the other offsets
GHOST_DEPTH = 0.10                 # a ghost: a dip at least 10 % below the curve 3 qualities either side
MIN_BLOCKS = 500
MAX_PIXELS = 2_000_000   # larger pictures are checked on a central crop of about this size (grid kept)


def central(a, max_px=MAX_PIXELS, align=16):
    """A central crop of at most max_px pixels whose corner sits on a multiple of 16 (keeps the 8x8 grid
    and the 16x16 chroma blocks where they were)."""
    H, W = a.shape[:2]
    if H * W <= max_px:
        return a
    s = (max_px / (H * W)) ** 0.5
    h, w = max(align, int(H * s) // align * align), max(align, int(W * s) // align * align)
    y0, x0 = (H - h) // 2 // align * align, (W - w) // 2 // align * align
    return a[y0:y0 + h, x0:x0 + w]


def table_quality(qt):
    """The IJG (libjpeg) quality whose scaled standard luminance table is closest to this one."""
    t = np.asarray(qt, np.float64)
    best = None
    for q in range(1, 101):
        s = 5000.0 / q if q < 50 else 200.0 - 2 * q
        ref = np.clip(np.floor((STD_LUMA * s + 50) / 100), 1, 255)
        err = min(np.abs(np.sort(ref) - np.sort(t)).mean(), np.abs(ref - t).mean())
        if best is None or err < best[1]:
            best = (q, err)
    return best


def decoded_y(data):
    """The luma plane as the decoder produced it (no colour conversion and back)."""
    im = Image.open(io.BytesIO(data))
    im.draft('YCbCr', im.size)
    a = np.asarray(im)
    return (a[..., 0] if a.ndim == 3 else a).astype(np.float64)


def grid_scores(y):
    """Periodicity score and the step that gives it, for each of the 64 grid offsets."""
    H, W = y.shape
    S, Q, n = np.zeros((8, 8)), np.zeros((8, 8), int), 0
    for oy in range(8):
        for ox in range(8):
            h, w = (H - oy) // 8 * 8, (W - ox) // 8 * 8
            b = y[oy:oy + h, ox:ox + w].reshape(h // 8, 8, w // 8, 8).transpose(0, 2, 1, 3).reshape(-1, 8, 8)
            # textured blocks that the decoder did not clip at 0 or 255 (clipping breaks the lattice)
            b = b[(b.std(axis=(1, 2)) > 2) & (b.min(axis=(1, 2)) > 2) & (b.max(axis=(1, 2)) < 253)]
            if (oy, ox) == (0, 0):
                n = len(b)
            if len(b) < MIN_BLOCKS:
                continue
            c = dctn(b - 128.0, axes=(1, 2), norm='ortho')
            for u, v in FREQS:
                x = c[:, u, v]
                x = x[np.abs(x) > 0.75]
                if len(x) < MIN_BLOCKS:
                    continue
                P = np.abs(np.exp(2j * np.pi * x[None, :] / STEPS[:, None]).mean(axis=1)) * np.sqrt(len(x))
                if P.max() > S[oy, ox]:
                    S[oy, ox], Q[oy, ox] = P.max(), STEPS[P.argmax()]
    return S, Q, n


def shifted_grids(S, Q):
    other = np.delete(S.ravel(), 0)
    med = float(np.median(other))
    hits = [(ox, oy, float(S[oy, ox]), int(Q[oy, ox])) for oy in range(8) for ox in range(8)
            if (oy, ox) != (0, 0) and S[oy, ox] >= max(GRID_MIN, GRID_RATIO * med)]
    return sorted(hits, key=lambda h: -h[2]), med


def ghost_curve(data, qs):
    im = Image.open(io.BytesIO(data))
    rgb = central(np.asarray(im.convert('RGB')))
    y = central(decoded_y(data))
    sub = 2
    try:
        from PIL import JpegImagePlugin
        s = JpegImagePlugin.get_sampling(im)
        sub = 2 if s == -1 else s
    except Exception:
        pass
    d = {}
    for q in qs:
        buf = io.BytesIO()
        Image.fromarray(rgb).save(buf, 'JPEG', quality=q, subsampling=sub)
        d[q] = float(((y - decoded_y(buf.getvalue())) ** 2).mean())   # the crop re-saved: same size as y
    return d


def ghost_dips(d, last_q):
    dips = []
    for q in sorted(d):
        if q > last_q - 4 or (q - 3) not in d or (q + 3) not in d:
            continue
        around = 0.5 * (d[q - 3] + d[q + 3])
        depth = 1.0 - d[q] / around if around > 0 else 0.0
        if depth >= GHOST_DEPTH and d[q] <= min(d.get(q - 1, np.inf), d.get(q + 1, np.inf)):
            dips.append((q, float(depth)))
    return sorted(dips, key=lambda t: -t[1])


def analyse(data):
    im = Image.open(io.BytesIO(data))
    qt = getattr(im, 'quantization', None) or {}
    last_q, fit = table_quality(qt[0]) if 0 in qt else (None, None)
    S, Q, nblocks = grid_scores(central(decoded_y(data)))
    usable = nblocks >= MIN_BLOCKS
    grids, med = shifted_grids(S, Q) if usable else ([], 0.0)
    lq = last_q or 95
    dips = ghost_dips(ghost_curve(data, range(30, min(100, lq + 3) + 1)), lq)
    return dict(last_q=last_q, table_fit=fit, grid_usable=usable, grid_blocks=nblocks, grids=grids, grid_median=med,
                grid_00=(float(S[0, 0]), int(Q[0, 0])), ghost=dips)


def verdict(r):
    notes = []
    if r['ghost']:
        # the lowest dip is the earlier save; a second, shallower dip a few qualities higher is an alias
        notes.append(f"an earlier save on the same grid at about q{min(q for q, _ in r['ghost'])}")
    if r['grids']:
        notes.append('an earlier save on a shifted grid (offset ' +
                     ', '.join(f'x+{ox} y+{oy}, step {q}, score {s:.0f}' for ox, oy, s, q in r['grids'][:2]) + ')')
    if notes:
        return 'saved more than once: ' + '; '.join(notes)
    tail = '' if r['grid_usable'] else ' (shifted-grid check not possible: the picture is mostly pure black/white)'
    return 'no trace of an earlier save' + tail


# ------------------------------------------------------------------ test on known histories

def _test_one(args):
    import compression_test as C
    folder, name = args
    Mst = C.load(folder, name)
    rows = []
    for hname, steps in C.HISTORIES.items():
        _, last = C.chain(Mst, steps)
        r = analyse(last)
        shift = sorted({s % 8 for _, s in steps if s})
        rows.append(dict(image=name, history=hname, saves=len(steps), last_q=r['last_q'], grid_usable=r['grid_usable'],
                         shift_truth=str(shift), grids=str([(g[0], g[1], g[3]) for g in r['grids'][:3]]),
                         grid_top=r['grids'][0][2] if r['grids'] else 0.0, grid_median=r['grid_median'],
                         shift_found=any(g[0] == g[1] and g[0] in shift for g in r['grids']),
                         ghost=str([q for q, _ in r['ghost'][:2]]), ghost_depth=r['ghost'][0][1] if r['ghost'] else 0.0,
                         first_q=steps[0][0] if len(steps) > 1 else None, flagged=bool(r['grids'] or r['ghost'])))
    return rows


def test(jobs):
    import pandas as pd
    import compression_test as C
    from paths import RESULTS
    with ProcessPoolExecutor(jobs) as pool:
        rows = [r for rr in pool.map(_test_one, C.IMAGES) for r in rr]
    d = pd.DataFrame(rows)
    out = os.path.join(RESULTS, 'jpeg_history_test.csv')
    d.to_csv(out, index=False)
    print(d.groupby('history', sort=False)[['flagged', 'shift_found', 'grid_usable']].mean().round(2))
    print(d[['image', 'history', 'last_q', 'grids', 'ghost', 'flagged']].to_string())
    print('wrote', out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='*')
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--jobs', type=int, default=2)
    a = ap.parse_args()
    if a.test:
        test(a.jobs)
        return 0
    if not a.files:
        ap.error('give JPEG files, or --test')
    for f in a.files:
        r = analyse(open(f, 'rb').read())
        q = f'about q{r["last_q"]}' if r['last_q'] else 'unknown quality'
        print(f'{f}: last save {q}; {verdict(r)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
