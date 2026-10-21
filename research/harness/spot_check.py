"""Is an added dot more obvious at full resolution? How spot-like tiny edits look in each view.

    python3 spot_check.py [--jobs 4]   -> results/spot_check.csv

Follow-up to the user's note on c02: a dot is not the same kind of difference as compression noise or
softened edges, so at full resolution it might be obvious even where ꟻLIP's map has other differences as
strong (tiny_edits.py counts an edit as seen only if it outshines all but 1 % of the picture, whatever
their shape). Here each difference is scored by how *spot-like* it is: on ꟻLIP's error map (what
flickers, and how much, at the viewing distance), the strongest value inside a dot-sized window minus the
strongest value in eight windows of the same size on a ring around it. An isolated dot that appears or
vanishes scores high; a difference along an edge scores low (the ring continues the edge), and so does
texture (the ring holds more of it). A dot "stands out as a spot" when its score beats all but 1 % of the
unedited comparison's blocks, and the number of blocks scoring at least as high counts the other places
that look like an appearing or vanishing dot of that size (lost fine detail, compression specks).

Views: the large file against the copy enlarged with Lanczos3 or nearest neighbour to the exact size
(96 ppd), and the matched shrink against the copy viewed zoomed k x (96/k ppd), each with blocks covering
8 x 8 pixels of the original. Dots of 1-6 px in full or half contrast on a flat or busy spot, in either
file; pictures, sizes and saves as in tiny_edits.py.
"""
import argparse
import math
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

import cv2
import numpy as np
import pandas as pd
from PIL import Image
from scipy.ndimage import maximum_filter

import fi
import metrics as M
import resample as R
import study as S
import tiny_edits as TE
from paths import RESULTS, TESTSET

DOTS = [e for e in TE.EDITS if e[1] == 'dot']
VIEWS = ['up_l3', 'up_nn', 'small_zoom']


def spot_map(F, a):
    """Max of F in a (2a+1)^2 window minus the max of eight such windows on a ring around it (a gap of
    two pixels, so the dot's own blur on the map does not reach the ring)."""
    mx = maximum_filter(F, size=2 * a + 1, mode='nearest')
    d = 2 * a + 3
    H, W = F.shape
    pad = np.pad(mx, d, mode='edge')
    ring = np.zeros_like(F)
    for dy in (-d, 0, d):
        for dx in (-d, 0, d):
            if dy or dx:
                np.maximum(ring, pad[d + dy:d + dy + H, d + dx:d + dx + W], out=ring)
    return mx - ring


def half_width(size_px):
    return max(1, int(math.ceil(size_px / 2.0)))


def task(args):
    folder, name, f, scen = args
    L0 = np.asarray(Image.open(os.path.join(TESTSET, folder, f'{name}.png')).convert('RGB'))
    H, W = L0.shape[:2]
    w, h = R.small_size(W, H, f)
    small_codec = {'png': 'png', 'jpg85': 'jpg85', 'big90_png': 'png'}[scen]
    small_of = lambda img: S.codec(R.SHRINKERS[TE.SHRINKER](img, w, h), small_codec)
    large_of = lambda img: S.codec(img, 'jpg90') if scen == 'big90_png' else img
    enl = {'up_l3': lambda s: fi.rescale(s, W, H, 'lanczos3'), 'up_nn': lambda s: R.nn_exact(s, W, H)}
    A0, S0 = large_of(L0), small_of(L0)
    downs, kk = S.down_strategies(A0, S0, TE.SHRINKER)
    kernel, D0 = kk['down_matched8a'], downs['down_matched8a']
    up0 = {v: enl[v](S0) for v in enl}
    ppd = {'up_l3': 96.0, 'up_nn': 96.0, 'small_zoom': 96.0 / f}
    bsz = {'up_l3': 8, 'up_nn': 8, 'small_zoom': max(1, int(round(8 / f)))}
    base = {v: M.flip(A0, up0[v], 96)[1] for v in enl}
    base['small_zoom'] = M.flip(D0, S0, ppd['small_zoom'])[1]
    spot_cache = {}

    def base_spot(v, a):
        if (v, a) not in spot_cache:
            spot_cache[(v, a)] = M.block_reduce(spot_map(base[v], a), bsz[v], 'max')
        return spot_cache[(v, a)]

    rows = []
    for i, (ename, kind, size, contrast, place) in enumerate(DOTS):
        idx = TE.EDITS.index((ename, kind, size, contrast, place))
        L1, mask = TE.make_edit(L0, kind, size, contrast, place, salt=100 + idx)
        mask_s = cv2.resize(mask.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA) > 0
        for direction in ('in_small', 'in_large'):
            if direction == 'in_small':
                S1 = small_of(L1)
                pairs = {v: (A0, enl[v](S1)) for v in enl}
                pairs['small_zoom'] = (D0, S1)
            else:
                A1 = large_of(L1)
                pairs = {v: (A1, up0[v]) for v in enl}
                pairs['small_zoom'] = (TE.shrink_with(kernel, A1, w, h), S0)
            for v in VIEWS:
                small = v == 'small_zoom'
                msk = mask_s if small else mask
                dot_px = size / f if small else size
                a = half_width(dot_px)
                bs = bsz[v]
                # the edited map: ꟻLIP recomputed near the edit, the rest as in the unedited pair
                mg = 3 * a + 24
                y0, y1, x0, x1 = TE.crop_box(msk, mg + 16, msk.shape)
                y0, x0 = y0 // bs * bs, x0 // bs * bs
                Fm = base[v].copy()
                ra, rb = pairs[v]
                Fm[y0:y1, x0:x1] = M.flip(ra[y0:y1, x0:x1], rb[y0:y1, x0:x1], ppd[v])[1]
                cy0, cy1, cx0, cx1 = max(0, y0 - mg), min(Fm.shape[0], y1 + mg), max(0, x0 - mg), min(Fm.shape[1], x1 + mg)
                Sm = spot_map(Fm[cy0:cy1, cx0:cx1], a)
                near = cv2.dilate(msk.astype(np.uint8), np.ones((2 * a + 1, 2 * a + 1), np.uint8))[cy0:cy1, cx0:cx1] > 0
                s_edit = float(Sm[near].max())
                f_edit = float(Fm[cy0:cy1, cx0:cx1][near].max())
                # background: the unedited comparison's blocks away from the edit
                eb, gb = S._edit_blocks(msk, 2 * a + 4, bs)
                keep = ~(eb | gb)
                bS = base_spot(v, a)[keep]
                bF = M.block_reduce(base[v], bs, 'max')[keep]
                rows.append(dict(image=name, set='real' if name.startswith('real') else 'synth', factor=f, scenario=scen,
                                 edit=ename, size=size, rel=size / f, contrast=contrast, place=place, direction=direction,
                                 view=v, spot_edit=s_edit, spot_p99=float(np.percentile(bS, 99)),
                                 spot_rank=int((bS >= s_edit).sum()), flip_edit=f_edit,
                                 flip_p99=float(np.percentile(bF, 99)), flip_rank=int((bF >= f_edit).sum()),
                                 blocks=int(keep.sum())))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=4)
    a = ap.parse_args()
    out = os.path.join(RESULTS, 'spot_check.csv')
    tasks = [(fo, n, f, sc) for fo, n in TE.IMAGES for f in TE.FACTORS for sc in TE.SCENARIOS]
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


if __name__ == '__main__':
    main()
