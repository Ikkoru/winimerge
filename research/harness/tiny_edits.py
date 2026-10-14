"""Tiny differences: how small a real change can each way of comparing still show?

    python3 tiny_edits.py [--jobs 4] [--out ../results/tiny_edits.csv]

Follow-up to the user's review: big edits are seen with every method, so this looks at the small ones.
Images: 4 synthetic (line art, flat colour, manga, UI text) and 4 real (the Pepper&Carrot cover, the Krita
anime banner, the lion photo, the terminal screenshot), copies made with Pillow's Lanczos at factors 2 and 4
(with dots of 1 to 6 px, edits from a quarter of a copy pixel to three copy pixels).

Scenarios (how the two files were saved):
  png        large lossless, small PNG
  jpg85      large lossless, small JPEG q85
  big90_png  large JPEG q90, small PNG (lossless small copy, high-quality lossy large file)

Edits: square dots of 1, 2, 4 and 6 large-image pixels, at full or half contrast against their
surroundings, on a flat or a busy spot, and a 1-px anti-aliased hairline (40 px) on a flat or busy spot.
Each edit is applied in one of two directions:
  in_small  the small copy was made from the edited picture (the large file lacks the change)
  in_large  the large file is the edited one (the small copy's source lacks the change: a detail the
            large file has and the small copy's source did not, like the dot in eye-check case c02)

Methods (the pair WinMerge would compare):
  small       matched shrink, compared at the copy's size (WinIMerge DOWN_MATCHED)
  rt_l3       both panes of `small` enlarged back with Lanczos3 (round trip)
  up_l3       the copy enlarged with Lanczos3 (UP_SMOOTH)
  up_cr       the copy enlarged with Catmull-Rom (8-bit)
  up_nn       the copy enlarged with nearest neighbour to the exact size
  up_nn_int   whole-number NN, centred (UP_NEAREST_INTEGER + centre alignment)
  up_l3usm    Lanczos3 + unsharp mask sigma 1 px, 50 %

Per edited pair and method: the edit's strongest 8x8 block against the 99th percentile of the unedited
twin's blocks (cnr; above 1 means WinMerge marks the edit at the threshold that leaves 1 % of the unedited
blocks marked), and the same on ꟻLIP's error map at 96 pixels per degree; for `small` also at 96/k ppd
(the small comparison zoomed k x, as when flipping it at the original's size).
"""
import argparse
import math
import os
from multiprocessing import Pool

import cv2
import numpy as np
import pandas as pd
from PIL import Image

import fi
import metrics as M
import resample as R
import study as S
from paths import RESULTS, TESTSET

IMAGES = [('large', 'synth_lineart'), ('large', 'synth_flatcolor'), ('large', 'synth_manga'), ('large', 'synth_text_ui'),
          ('large_real', 'real_peppercarrot_cover'), ('large_real', 'real_krita_anime_banner'),
          ('large_real', 'real_lion_appel'), ('large_real', 'real_kitty_screenshot')]
FACTORS = [2, 4]   # with dots of 1-6 px this covers edits from 1/4 to 3 pixels of the copy
SCENARIOS = ['png', 'jpg85', 'big90_png']
SHRINKER = 'pil_lanczos'
METHODS = ['small', 'rt_l3', 'up_l3', 'up_cr', 'up_nn', 'up_nn_int', 'up_l3usm']
FLIP_METHODS = ['small', 'rt_l3', 'up_l3', 'up_cr', 'up_nn']
EDITS = [(f'dot{d}_{c}_{p}', 'dot', d, c, p) for d in (1, 2, 4, 6) for c in ('full', 'half') for p in ('flat', 'busy')] + \
        [(f'hair_{p}', 'hair', 1, 'full', p) for p in ('flat', 'busy')]


def spot(img, fw, fh, salt, place):
    """Top-left corner of a fw x fh footprint on a 9x9 grid: the busiest (highest local std) or the
    flattest spot; a little jitter breaks ties."""
    H, W = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float32)
    rng = np.random.default_rng(salt)
    best, best_s = None, None
    for gy in np.linspace(0.08, 0.86, 9):
        for gx in np.linspace(0.08, 0.86, 9):
            x, y = int(gx * (W - fw)), int(gy * (H - fh))
            s = g[y:y + fh, x:x + fw].std() + rng.uniform(0, 0.5)
            if place == 'flat':
                s = -s
            if best_s is None or s > best_s:
                best, best_s = (x, y), s
    return best


def make_edit(img, kind, size, contrast, place, salt):
    fw, fh = (24, 24) if kind == 'dot' else (48, 24)
    x, y = spot(img, fw, fh, salt, place)
    m = img[y:y + fh, x:x + fw].reshape(-1, 3).astype(np.float64).mean(axis=0)
    lum = 0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]
    full = np.array((20, 20, 20) if lum > 128 else (240, 240, 240), np.float64)
    col = full if contrast == 'full' else (m + full) / 2
    col = tuple(int(v) for v in np.round(col))
    out = img.copy()
    if kind == 'dot':
        # normally at (10, 10) in the footprint; if pixels there already have the dot's colour (dark text on a
        # light spot in the UI picture), the nearest place in the footprint where the dot changes every pixel
        oy, ox = 10, 10
        if (img[y + oy:y + oy + size, x + ox:x + ox + size] == col).all(axis=2).any():
            cands = sorted(((a, b) for a in range(2, fh - size - 1) for b in range(2, fw - size - 1)),
                           key=lambda p: (abs(p[0] - 10) + abs(p[1] - 10), p))
            for a, b in cands:
                if not (img[y + a:y + a + size, x + b:x + b + size] == col).all(axis=2).any():
                    oy, ox = a, b
                    break
        out[y + oy:y + oy + size, x + ox:x + ox + size] = col
    else:
        cv2.line(out, (x + 4, y + 8), (x + 44, y + 14), col, 1, lineType=cv2.LINE_AA)
    return out, np.any(out != img, axis=2)


def shrink_with(kernel, img, w, h):
    """Shrink as WinIMerge's DOWN_MATCHED does once it has picked `kernel` (OpenCV's INTER_AREA stands in
    for WinIMerge's area resampler: they agree to within 1 level)."""
    if kernel == 'area':
        return cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    return fi.rescale(img, w, h, kernel)


def enlargers(Sm, W, H):
    return {
        'up_l3': (fi.rescale(Sm, W, H, 'lanczos3'), None),
        'up_cr': (fi.rescale(Sm, W, H, 'catmullrom'), None),
        'up_nn': (R.nn_exact(Sm, W, H), None),
        'up_nn_int': S.up_nn_int(Sm, W, H, 'center'),
        'up_l3usm': (R.unsharp(fi.rescale(Sm, W, H, 'lanczos3'), 1.0, 0.5), None),
    }


def pairs(A, Sm, D, ups, W, H, up_d=None):
    """(reference, test, valid) per method for large file A, small copy Sm, A shrunk D, enlargements of Sm."""
    p = {'small': (D, Sm, None),
         'rt_l3': (up_d if up_d is not None else fi.rescale(D, W, H, 'lanczos3'), ups['up_l3'][0], None)}
    for k in ('up_l3', 'up_cr', 'up_nn', 'up_nn_int', 'up_l3usm'):
        p[k] = (A, ups[k][0], ups[k][1])
    return p


def flip_map(a, b, ppd):
    _, m = M.flip(a, b, ppd)
    return M.block_reduce(m.astype(np.float32), 8, 'max')


def crop_box(mask, margin, shape):
    ys, xs = np.where(mask)
    H, W = shape
    y0 = max(0, (ys.min() - margin) // 8 * 8)
    x0 = max(0, (xs.min() - margin) // 8 * 8)
    y1 = min(H, ys.max() + margin)
    x1 = min(W, xs.max() + margin)
    return y0, y1, x0, x1


def task(args):
    folder, name, f, scen = args
    L0 = np.asarray(Image.open(os.path.join(TESTSET, folder, f'{name}.png')).convert('RGB'))
    H, W = L0.shape[:2]
    w, h = R.small_size(W, H, f)
    small_codec = {'png': 'png', 'jpg85': 'jpg85', 'big90_png': 'png'}[scen]

    def small_of(img):
        return S.codec(R.SHRINKERS[SHRINKER](img, w, h), small_codec)

    def large_of(img):
        return S.codec(img, 'jpg90') if scen == 'big90_png' else img

    A0, S0 = large_of(L0), small_of(L0)
    downs, kk = S.down_strategies(A0, S0, SHRINKER)
    kernel = kk['down_matched8a']
    D0 = downs['down_matched8a']
    ups0 = enlargers(S0, W, H)
    upD0 = fi.rescale(D0, W, H, 'lanczos3')
    base = pairs(A0, S0, D0, ups0, W, H, upD0)
    bm0 = {m: M.block_max_distance(*base[m]) for m in METHODS}
    fl0, flT = {}, {}
    for m in FLIP_METHODS:
        fl0[m] = flip_map(base[m][0], base[m][1], 96)
        flT[m] = float(np.percentile(fl0[m], 99))
    fl0['small_zoom'] = flip_map(base['small'][0], base['small'][1], 96.0 / f)
    flT['small_zoom'] = float(np.percentile(fl0['small_zoom'], 99))
    rows = []
    for i, (ename, kind, size, contrast, place) in enumerate(EDITS):
        L1, mask = make_edit(L0, kind, size, contrast, place, salt=100 + i)
        mask_s = cv2.resize(mask.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA) > 0
        ebL, gbL = S._edit_blocks(mask, int(math.ceil(3 * f)) + 2)
        ebS, gbS = S._edit_blocks(mask_s, 3)
        for direction in ('in_small', 'in_large'):
            if direction == 'in_small':
                A1, S1, D1 = A0, small_of(L1), D0
                ups1 = enlargers(S1, W, H)
                ed = pairs(A1, S1, D1, ups1, W, H, upD0)
            else:
                A1, S1 = large_of(L1), S0
                D1 = shrink_with(kernel, A1, w, h)
                ed = pairs(A1, S1, D1, ups0, W, H, None)
            for m in METHODS:
                small = m == 'small'
                eb, gb = (ebS, gbS) if small else (ebL, gbL)
                bm1 = M.block_max_distance(*ed[m])
                d = S._detection(bm0[m], bm1, eb, gb)
                row = dict(image=name, set='real' if name.startswith('real') else 'synth', factor=f, scenario=scen,
                           kernel=kernel, edit=ename, kind=kind, size=size, contrast=contrast, place=place,
                           direction=direction, method=m, edit_px=int(mask.sum()))
                if d:
                    row.update(any_T1=d['any_T1'], det_T1=d['det_T1'], T1=d['T1'], edit_peak=d['edit_peak'],
                               cnr=(d['edit_peak'] + 1.0) / (d['T1'] + 1.0), outrank=d['outrank'])
                for fm, ppd in ([(m, 96)] if m in FLIP_METHODS else []) + ([('small_zoom', 96.0 / f)] if small else []):
                    msk = mask_s if small else mask
                    y0, y1, x0, x1 = crop_box(msk, 32 if small else 64, msk.shape)
                    fm1 = flip_map(ed[m][0][y0:y1, x0:x1], ed[m][1][y0:y1, x0:x1], ppd)
                    ebc = eb[y0 // 8:y0 // 8 + fm1.shape[0], x0 // 8:x0 // 8 + fm1.shape[1]]
                    if ebc.any():
                        peak = float(fm1[ebc].max())
                        pre = 'flip_' if fm == m else 'flipzoom_'
                        row.update({pre + 'peak': peak, pre + 'T1': flT[fm], pre + 'any': int(peak > flT[fm]),
                                    pre + 'cnr': peak / max(flT[fm], 1e-6)})
                rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--out', default=os.path.join(RESULTS, 'tiny_edits.csv'))
    a = ap.parse_args()
    tasks = [(fo, n, f, sc) for fo, n in IMAGES for f in FACTORS for sc in SCENARIOS]
    done = set()
    if os.path.exists(a.out):   # resumable: skip (image, factor, scenario) already in the CSV
        prev = pd.read_csv(a.out)
        done = set(zip(prev.image, prev.factor, prev.scenario))
    todo = [t for t in tasks if (t[1], t[2], t[3]) not in done]
    print(f'{len(todo)} of {len(tasks)} tasks to run', flush=True)
    with Pool(a.jobs) as pool:
        for i, rr in enumerate(pool.imap_unordered(task, todo)):
            df = pd.DataFrame(rr)
            df.to_csv(a.out, mode='a', header=not os.path.exists(a.out), index=False)
            print(f'{i + 1}/{len(todo)} tasks', flush=True)
    df = pd.read_csv(a.out)
    print(df.groupby(['scenario', 'direction', 'method'])['any_T1'].mean().unstack().round(2))


if __name__ == '__main__':
    main()
