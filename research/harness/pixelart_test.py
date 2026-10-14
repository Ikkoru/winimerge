"""Pixel art: edits and variants when both files are pixel art at different sizes.

    python3 pixelart_test.py [--jobs 4] [--out ../results/pixelart.csv]

Three native pixel-art images (two procedural scenes from synth.pixelart, 200x150 logical pixels, and a
200x150 crop of Kenney's city tiles), each shown at two sizes:
  nn8_4, nn8_2      large x8 NN, small x4 / x2 NN (whole-number ratio 2 or 4)
  nn8_3, nn6_4      large x8 / x6 NN, small x3 / x4 NN (ratio 2.67 or 1.5: both NN zooms, not a whole number)
  lz8_2, lz8_2.5, lz8_3   large x8 NN, small shrunk with Pillow Lanczos (a site's thumbnail), PNG
  lz8_3j            the same at 1/3, saved as JPEG q85
  bl8_2.5           small shrunk with Pillow bilinear, PNG
  pt8_2.5, pt8_3    small shrunk with Pillow NEAREST (point sampling), PNG
Edits are made on the native image (one logical pixel to a contrasting palette colour or a subtle shift,
a 2x2 block, a subtle 6x6 recolour), in the small copy's source (in_small) or in the large file (in_large).
Methods: small (matched shrink), rt_l3 (round trip), up_nn_int (whole-number NN, centred), up_nn (NN to
the exact size), up_l3 (Lanczos3), up_cr (Catmull-Rom).
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
import synth
from paths import RESULTS, TESTSET

SCENARIOS = {  # name: (large NN zoom, how the small copy is made, its argument)
    'nn8_4': (8, 'nn', 4), 'nn8_2': (8, 'nn', 2), 'nn8_3': (8, 'nn', 3), 'nn6_4': (6, 'nn', 4),
    'lz8_2': (8, 'pil_lanczos', 2), 'lz8_2.5': (8, 'pil_lanczos', 2.5), 'lz8_3': (8, 'pil_lanczos', 3),
    'lz8_3j': (8, 'pil_lanczos_jpg85', 3), 'bl8_2.5': (8, 'pil_bilinear', 2.5),
    'pt8_2.5': (8, 'nearest', 2.5), 'pt8_3': (8, 'nearest', 3),
}
METHODS = ['small', 'rt_l3', 'up_nn_int', 'up_nn', 'up_l3', 'up_cr']
EDITS = ['px_strong_busy', 'px_strong_flat', 'px_subtle_busy', 'px_subtle_flat', 'blk2_strong_busy', 'region6_subtle']


def natives():
    out = {}
    for seed in (6, 9):
        out[f'px_seed{seed}'] = synth.pixelart(seed=seed)[::8, ::8].copy()
    k = np.asarray(Image.open(os.path.join(TESTSET, 'real', 'real_kenney_city_tiles.png')).convert('RGB'))
    g = cv2.cvtColor(k, cv2.COLOR_RGB2GRAY).astype(np.float32)
    best, bs = (0, 0), -1
    for y in range(0, k.shape[0] - 150, 10):
        for x in range(0, k.shape[1] - 200, 10):
            s = g[y:y + 150, x:x + 200].std()
            if s > bs:
                best, bs = (x, y), s
    x, y = best
    out['kenney'] = k[y:y + 150, x:x + 200].copy()
    return out


def nn(img, k):
    return np.repeat(np.repeat(img, k, 0), k, 1)


def native_spot(N, place, salt):
    g = cv2.cvtColor(N, cv2.COLOR_RGB2GRAY).astype(np.float32)
    rng = np.random.default_rng(salt)
    H, W = g.shape
    best, bs = None, None
    for y in range(8, H - 14, 3):
        for x in range(8, W - 14, 3):
            s = g[y - 2:y + 4, x - 2:x + 4].std() + rng.uniform(0, 0.3)
            s = -s if place == 'flat' else s
            if bs is None or s > bs:
                best, bs = (x, y), s
    return best


def edit_native(N, name, salt):
    out = N.astype(np.int32).copy()
    place = 'flat' if name.endswith('flat') else 'busy'
    x, y = native_spot(N, place, salt)
    pal = np.unique(N.reshape(-1, 3), axis=0).astype(np.int32)
    def contrast(c):
        return pal[np.argmax(((pal - c) ** 2).sum(axis=1))]
    if name.startswith('px_strong'):
        out[y, x] = contrast(out[y, x])
    elif name.startswith('px_subtle'):
        out[y, x] += (16, 8, -12)
    elif name.startswith('blk2'):
        out[y:y + 2, x:x + 2] = contrast(out[y, x])
    else:
        out[y:y + 6, x:x + 6] += (10, 0, -10)
    out = np.clip(out, 0, 255).astype(np.uint8)
    return out, np.any(out != N, axis=2)


def make_pair(Nimg, scen):
    kL, how, arg = SCENARIOS[scen]
    L = nn(Nimg, kL)
    H, W = L.shape[:2]
    if how == 'nn':
        Sm = nn(Nimg, arg)
    else:
        w, h = R.small_size(W, H, arg)
        if how == 'pil_lanczos_jpg85':
            Sm = S.codec(R.SHRINKERS['pil_lanczos'](L, w, h), 'jpg85')
        elif how == 'nearest':
            Sm = np.asarray(Image.fromarray(L).resize((w, h), Image.NEAREST))
        else:
            Sm = R.SHRINKERS[how](L, w, h)
    return L, Sm


def method_pairs(L, Sm, D, upD=None):
    H, W = L.shape[:2]
    U_int, valid = S.up_nn_int(Sm, W, H, 'center')
    up_l3 = fi.rescale(Sm, W, H, 'lanczos3')
    return {'small': (D, Sm, None), 'rt_l3': (upD if upD is not None else fi.rescale(D, W, H, 'lanczos3'), up_l3, None),
            'up_nn_int': (L, U_int, valid), 'up_nn': (L, R.nn_exact(Sm, W, H), None),
            'up_l3': (L, up_l3, None), 'up_cr': (L, fi.rescale(Sm, W, H, 'catmullrom'), None)}


def task(args):
    nname, scen = args
    Nimg = natives()[nname]
    L0, S0 = make_pair(Nimg, scen)
    H, W = L0.shape[:2]
    h, w = S0.shape[:2]
    kL = SCENARIOS[scen][0]
    downs, kk = S.down_strategies(L0, S0, 'area')
    kernel = kk['down_matched8a']
    D0 = downs['down_matched8a']
    base = method_pairs(L0, S0, D0)
    bm0 = {m: M.block_max_distance(*base[m]) for m in METHODS}
    rows = []
    for m in METHODS:
        out = M.block_outcome(bm0[m])
        rows.append(dict(native=nname, scenario=scen, factor=W / w, kernel=kernel, edit='none', direction='',
                         method=m, T_p99=out['T_p99'], share_T8=out['share_T8'], share_T16=out['share_T16']))
    for i, e in enumerate(EDITS):
        N1, nmask = edit_native(Nimg, e, salt=10 + i)
        maskL = nn(nmask.astype(np.uint8), kL).astype(bool)
        mask_s = cv2.resize(maskL.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA) > 0
        ebL, gbL = S._edit_blocks(maskL, int(math.ceil(3 * W / w)) + 2)
        ebS, gbS = S._edit_blocks(mask_s, 3)
        L1, S1 = make_pair(N1, scen)
        for direction in ('in_small', 'in_large'):
            if direction == 'in_small':
                ed = method_pairs(L0, S1, D0, base['rt_l3'][0])
            else:
                D1 = cv2.resize(L1, (w, h), interpolation=cv2.INTER_AREA) if kernel == 'area' else fi.rescale(L1, w, h, kernel)
                ed = method_pairs(L1, S0, D1)
            for m in METHODS:
                eb, gb = (ebS, gbS) if m == 'small' else (ebL, gbL)
                d = S._detection(bm0[m], M.block_max_distance(*ed[m]), eb, gb)
                row = dict(native=nname, scenario=scen, factor=W / w, kernel=kernel, edit=e, direction=direction, method=m)
                if d:
                    row.update(any_T1=d['any_T1'], det_T1=d['det_T1'], T1=d['T1'], edit_peak=d['edit_peak'],
                               cnr=(d['edit_peak'] + 1.0) / (d['T1'] + 1.0))
                rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--out', default=os.path.join(RESULTS, 'pixelart.csv'))
    a = ap.parse_args()
    tasks = [(n, s) for n in natives() for s in SCENARIOS]
    with Pool(a.jobs) as pool:
        rows = [r for rr in pool.imap_unordered(task, tasks) for r in rr]
    df = pd.DataFrame(rows)
    df.to_csv(a.out, index=False)
    u = df[df.edit == 'none']
    print(u.pivot_table(index='scenario', columns='method', values='T_p99', aggfunc='median').round(1))
    e = df[df.edit != 'none']
    print(e.pivot_table(index='scenario', columns='method', values='any_T1', aggfunc='mean').round(2))


if __name__ == '__main__':
    main()
