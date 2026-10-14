"""The brief's suggestion 4 against 5: after the matched shrink, enlarge *both* images with the same filter
and compare at the original's size ("round trip"), or compare at the copy's size (WinIMerge DOWN_MATCHED)?
And do edits stand out for the eye (ꟻLIP), not only for WinMerge's threshold?

    python3 roundtrip_test.py [--jobs 2] [--out ../results/roundtrip_synth.csv]

Synthetic set; copies made with Pillow Lanczos and OpenCV area averaging at factors 2 and 3, saved as PNG
and JPEG q85; unedited and with four edits that are hard to see (small text, a thin line, a faint recolour,
the 3-px dot). Candidates, each a pair of panes:

  small         the original shrunk with WinIMerge's matched rule vs the copy, at the copy's size
  rt_lanczos3   both panes of `small` enlarged to the original's size with FreeImage Lanczos3 (8-bit path)
  rt_bilinear   the same with bilinear (no ringing)
  up_lanczos3   the copy enlarged with Lanczos3 vs the original (WinIMerge UP_SMOOTH)
  up_nn         the copy enlarged with nearest neighbour to the exact size vs the original

Per pair: WinMerge's outcome (T_p99, share of 8×8 blocks marked) and, for edited pairs, edit detection as in
study.py (threshold where 1 % of the unedited twin's blocks are marked). The same detection is run on the
ꟻLIP error map (max per 8×8 block) at 96 pixels per degree, and for `small` also at 96/k (the small
comparison zoomed k× to the original's size): does the edit's block stand out from the noise when flipping?
"""
import argparse
import math
import os
from multiprocessing import Pool

import cv2
import numpy as np
import pandas as pd
from PIL import Image

import edits as E
import fi
import metrics as M
import resample as R
import study as S
from paths import RESULTS, ROOT, TESTSET

IMAGES = ['synth_flatcolor', 'synth_lineart', 'synth_manga', 'synth_painterly', 'synth_text_ui', 'synth_pixelart',
          'synth_zoneplate']
EDITS = ['text_small', 'line', 'recolor', 'dot']


def flip_blocks(a, b, ppd):
    f, m = M.flip(a, b, ppd)
    return f['flip_mean'], M.block_reduce(m.astype(np.float32), 8, 'max')


def panes(L, D, Sm):
    """The two panes of every candidate and their size class, given the original L, its matched shrink D
    and the copy Sm."""
    H, W = L.shape[:2]
    up_l3 = fi.rescale(Sm, W, H, 'lanczos3')
    return {
        'small': (D, Sm, 'small'),
        'rt_lanczos3': (fi.rescale(D, W, H, 'lanczos3'), up_l3, 'large'),
        'rt_bilinear': (fi.rescale(D, W, H, 'bilinear'), fi.rescale(Sm, W, H, 'bilinear'), 'large'),
        'up_lanczos3': (L, up_l3, 'large'),
        'up_nn': (L, R.nn_exact(Sm, W, H), 'large'),
    }


def task(args):
    name, shrinker, factor, cod = args
    L0 = np.asarray(Image.open(os.path.join(TESTSET, 'large', f'{name}.png')).convert('RGB'))
    H, W = L0.shape[:2]
    w, h = R.small_size(W, H, factor)
    S0 = S.codec(R.SHRINKERS[shrinker](L0, w, h), cod)
    downs, k = S.down_strategies(L0, S0, shrinker)
    kern = k['down_matched8a']
    base = panes(L0, downs['down_matched8a'], S0)
    rows = []
    # unedited twin: block distances and ꟻLIP block maps, the baseline for every edit
    b_bm, b_fl, b_fl_zoom = {}, {}, {}
    for c, (A, B, size) in base.items():
        out, bm = M.cheap_panel(A, B)
        b_bm[c] = bm
        mean96, b_fl[c] = flip_blocks(A, B, 96)
        row = dict(image=name, edit='none', shrinker=shrinker, factor=factor, codec=cod, candidate=c, kernel=kern,
                   T_p99=out['T_p99'], share_T8=out['share_T8'], share_T16=out['share_T16'], share_T32=out['share_T32'],
                   share_T64=out['share_T64'], psnr=out['psnr'], flip_mean_ppd96=mean96)
        if c == 'small':
            row['flip_mean_zoomed'], b_fl_zoom[c] = flip_blocks(A, B, 96.0 / factor)
        rows.append(row)
    for e in EDITS:
        L1, mask = E.apply(e, L0)
        S1 = S.codec(R.SHRINKERS[shrinker](L1, w, h), cod)
        # the original against the edited copy; the matched filter is picked for this pair, as WinIMerge would
        downs1, _ = S.down_strategies(L0, S1, shrinker)
        ed = panes(L0, downs1['down_matched8a'], S1)
        ebL, gbL = S._edit_blocks(mask, int(math.ceil(3 * factor)) + 2)
        mask_s = cv2.resize(mask.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA) > 0
        ebS, gbS = S._edit_blocks(mask_s, 3)
        for c, (A, B, size) in ed.items():
            eb, gb = (ebS, gbS) if size == 'small' else (ebL, gbL)
            bm1 = M.block_max_distance(A, B)
            row = dict(image=name, edit=e, shrinker=shrinker, factor=factor, codec=cod, candidate=c, kernel=kern)
            row.update(S._detection(b_bm[c], bm1, eb, gb))
            _, fl1 = flip_blocks(A, B, 96)
            fd = S._detection(b_fl[c], fl1, eb, gb)
            row.update({'flip_' + k: v for k, v in fd.items() if k in ('det_T1', 'any_T1', 'det_T01', 'any_T01', 'outrank')})
            if c == 'small':
                _, flz = flip_blocks(A, B, 96.0 / factor)
                fz = S._detection(b_fl_zoom[c], flz, eb, gb)
                row.update({'flipzoom_' + k: v for k, v in fz.items() if k in ('det_T1', 'any_T1', 'outrank')})
            rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--out', default=os.path.join(RESULTS, 'roundtrip_synth.csv'))
    a = ap.parse_args()
    tasks = [(n, s, f, c) for n in IMAGES for s in ('pil_lanczos', 'area') for f in (2, 3) for c in ('png', 'jpg85')]
    with Pool(a.jobs) as pool:
        rows = [r for rr in pool.imap_unordered(task, tasks) for r in rr]
    df = pd.DataFrame(rows)
    df.to_csv(a.out, index=False)
    un = df[df.edit == 'none']
    print(un.groupby(['candidate', 'codec'])[['T_p99', 'share_T16', 'share_T64', 'flip_mean_ppd96', 'flip_mean_zoomed']].median().round(4))
    ed = df[df.edit != 'none']
    print(ed.groupby(['candidate', 'codec'])[['any_T1', 'det_T1', 'flip_any_T1', 'flip_det_T1', 'flipzoom_any_T1']].mean().round(3))
    print(ed.groupby(['candidate', 'edit'])[['any_T1', 'flip_any_T1']].mean().unstack().round(2))


if __name__ == '__main__':
    main()
