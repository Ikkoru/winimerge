"""Is the round trip's small edge over the matched shrink only WinMerge's block size?

    python3 blocksize_check.py [--jobs 1]   -> results/blocksize_check.csv

WinMerge marks 8x8 blocks of the images it compares. In the matched-shrink view (DOWN_MATCHED) a block
covers 8k x 8k pixels of the original; in the round trip (both panes enlarged back with Lanczos3) it
covers 8 x 8. WinMerge's "Diff Block Size" menu (1-32) can make the shrink's blocks as fine, so this
compares the two views at the same block area: the shrink with blocks of 8 and of 8/k, the round trip
with blocks of 8 and of 8k. The same for ꟻLIP's map (the shrink viewed zoomed k x, 96/k ppd; the round
trip at 96 ppd). Edits, images and saves as in tiny_edits.py (a subset: 4 images, lossy saves only,
where the two differ).
"""
import argparse
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

import cv2
import numpy as np
import pandas as pd
from PIL import Image

import fi
import metrics as M
import resample as R
import study as S
import tiny_edits as TE
from paths import RESULTS, TESTSET

IMAGES = [('large', 'synth_lineart'), ('large', 'synth_manga'),
          ('large_real', 'real_peppercarrot_cover'), ('large_real', 'real_lion_appel')]
FACTORS = [2, 4]
SCENARIOS = ['jpg85', 'big90_png']


def detect(bm0, bm1, eb, gb):
    d = S._detection(bm0, bm1, eb, gb)
    return (d['any_T1'], (d['edit_peak'] + 1.0) / (d['T1'] + 1.0)) if d else (np.nan, np.nan)


def task(args):
    folder, name, f, scen = args
    L0 = np.asarray(Image.open(os.path.join(TESTSET, folder, f'{name}.png')).convert('RGB'))
    H, W = L0.shape[:2]
    w, h = R.small_size(W, H, f)
    small_codec = {'jpg85': 'jpg85', 'big90_png': 'png'}[scen]
    small_of = lambda img: S.codec(R.SHRINKERS[TE.SHRINKER](img, w, h), small_codec)
    large_of = lambda img: S.codec(img, 'jpg90') if scen == 'big90_png' else img
    up = lambda img: fi.rescale(img, W, H, 'lanczos3')
    upb = lambda img: fi.rescale(img, W, H, 'bilinear')
    A0, S0 = large_of(L0), small_of(L0)
    downs, kk = S.down_strategies(A0, S0, TE.SHRINKER)
    kernel, D0 = kk['down_matched8a'], downs['down_matched8a']
    uS0, uD0, bS0, bD0 = up(S0), up(D0), upb(S0), upb(D0)
    fine, coarse = max(1, int(8 // f)), int(8 * f)
    views = [('small', 8), ('small', fine), ('rt', 8), ('rt', coarse), ('rtbl', 8), ('rtbl', coarse)]
    base_d = {'small': M.color_distance(D0, S0), 'rt': M.color_distance(uD0, uS0), 'rtbl': M.color_distance(bD0, bS0)}
    base_f = {'small': M.flip(D0, S0, 96.0 / f)[1], 'rt': M.flip(uD0, uS0, 96)[1], 'rtbl': M.flip(bD0, bS0, 96)[1]}
    rows = []
    for i, (ename, kind, size, contrast, place) in enumerate(TE.EDITS):
        L1, mask = TE.make_edit(L0, kind, size, contrast, place, salt=100 + i)
        mask_s = cv2.resize(mask.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA) > 0
        for direction in ('in_small', 'in_large'):
            if direction == 'in_small':
                S1, D1 = small_of(L1), D0
                uS1, uD1, bS1, bD1 = up(S1), uD0, upb(S1), bD0
            else:
                S1, D1 = S0, TE.shrink_with(kernel, large_of(L1), w, h)
                uS1, uD1, bS1, bD1 = uS0, up(D1), bS0, upb(D1)
            ed_d = {'small': M.color_distance(D1, S1), 'rt': M.color_distance(uD1, uS1), 'rtbl': M.color_distance(bD1, bS1)}
            # ꟻLIP of the edited pair only near the edit (the rest equals the unedited map)
            ed_f = {}
            for v, (a, b, msk, ppd, mg) in {'small': (D1, S1, mask_s, 96.0 / f, 32), 'rt': (uD1, uS1, mask, 96, 64),
                                            'rtbl': (bD1, bS1, mask, 96, 64)}.items():
                y0, y1, x0, x1 = TE.crop_box(msk, mg, msk.shape)
                y0, x0 = y0 // coarse * coarse, x0 // coarse * coarse
                m = base_f[v].copy()
                m[y0:y1, x0:x1] = M.flip(a[y0:y1, x0:x1], b[y0:y1, x0:x1], ppd)[1]
                ed_f[v] = m
            for v, bs in views:
                small = v == 'small'
                msk = mask_s if small else mask
                guard = 3 if small else int(math.ceil(3 * f)) + 2
                eb, gb = S._edit_blocks(msk, guard, bs)
                vis, cnr = detect(M.block_reduce(base_d[v], bs), M.block_reduce(ed_d[v], bs), eb, gb)
                eye, ecnr = detect(M.block_reduce(base_f[v], bs), M.block_reduce(ed_f[v], bs), eb, gb)
                content = bs * (f if small else 1)   # block side in pixels of the original
                rows.append(dict(image=name, factor=f, scenario=scen, edit=ename, size=size, contrast=contrast,
                                 place=place, direction=direction, view=v, block=bs, block_orig_px=content,
                                 granularity='coarse' if content > 8 else 'fine', visible=vis, cnr=cnr,
                                 eye=eye, eye_cnr=ecnr))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=1)
    a = ap.parse_args()
    out = os.path.join(RESULTS, 'blocksize_check.csv')
    tasks = [(fo, n, f, sc) for fo, n in IMAGES for f in FACTORS for sc in SCENARIOS]
    if os.path.exists(out):
        prev = pd.read_csv(out)
        done = set(zip(prev.image, prev.factor, prev.scenario))
        tasks = [t for t in tasks if (t[1], t[2], t[3]) not in done]
    print(f'{len(tasks)} tasks to run', flush=True)
    with ProcessPoolExecutor(a.jobs) as pool:
        futs = [pool.submit(task, t) for t in tasks]
        for i, fu in enumerate(as_completed(futs)):
            pd.DataFrame(fu.result()).to_csv(out, mode='a', header=not os.path.exists(out), index=False)
            print(f'{i + 1}/{len(tasks)}', flush=True)
    d = pd.read_csv(out)
    print(d.pivot_table(index=['scenario', 'view'], columns='granularity', values=['visible', 'eye'], aggfunc='mean').round(2))


if __name__ == '__main__':
    main()
