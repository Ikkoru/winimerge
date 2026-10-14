"""Catmull-Rom against Lanczos3 as the enlarger, by the models of the eye (lossless copies only).

    python3 cr_vs_l3.py [--jobs 1]   -> results/cr_vs_l3.csv

The user felt Catmull-Rom looked a little better than Lanczos3 when flipping. Section 4.10 measured
Lanczos3, bilinear and nearest neighbour with ꟻLIP, Butteraugli and SSIMULACRA2 but not Catmull-Rom.
Here both enlarge the same PNG copies (Pillow Lanczos, factors 2, 2.5, 3, 4) of 5 synthetic and 9 real
pictures back to the original's size with FreeImage's 8-bit path (as WinIMerge would), and each
enlargement is compared with the original: ꟻLIP at 96 and 48 ppd, Butteraugli (3-norm and max),
SSIMULACRA2, WinMerge's T_p99, and the overshoot (ringing) each filter adds next to hard edges.
"""
import argparse
import os
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
from PIL import Image

import fi
import metrics as M
import resample as R
from paths import RESULTS, TESTSET

IMAGES = [('large', n) for n in ('synth_lineart', 'synth_flatcolor', 'synth_manga', 'synth_text_ui', 'synth_painterly')] + \
         [('large_real', n) for n in ('real_peppercarrot_cover', 'real_peppercarrot_witches', 'real_krita_anime_banner',
                                      'real_kitty_screenshot', 'real_hokusai_hodogaya', 'real_vangogh_starry_night',
                                      'real_lion_appel', 'real_astronaut', 'real_coffee')]
FACTORS = [2, 2.5, 3, 4]
ENLARGERS = {'lanczos3': 'lanczos3', 'catmullrom': 'catmullrom'}


def overshoot(orig, up):
    """Mean overshoot beyond the local range of the original (3x3), in levels: halo/ringing added."""
    import cv2
    k = np.ones((3, 3), np.uint8)
    lo = cv2.erode(orig, k).astype(np.int16)
    hi = cv2.dilate(orig, k).astype(np.int16)
    u = up.astype(np.int16)
    over = np.maximum(u - hi, 0) + np.maximum(lo - u, 0)
    return float(over.mean()), float(np.percentile(over.max(axis=2), 99.9))


def task(args):
    folder, name, f = args
    L0 = np.asarray(Image.open(os.path.join(TESTSET, folder, f'{name}.png')).convert('RGB'))
    H, W = L0.shape[:2]
    w, h = R.small_size(W, H, f)
    S0 = R.SHRINKERS['pil_lanczos'](L0, w, h)
    rows = []
    for en, k in ENLARGERS.items():
        U = fi.rescale(S0, W, H, k)
        row = dict(image=name, set='real' if name.startswith('real') else 'synth', factor=f, enlarger=en)
        for ppd in (96, 48):
            row[f'flip{ppd}'] = M.flip(L0, U, ppd)[0]['flip_mean']
        row.update(M.butteraugli(L0, U))
        row.update(M.ssimulacra2(L0, U))
        out, _ = M.cheap_panel(L0, U)
        row['T_p99'], row['share_T16'] = out['T_p99'], out['share_T16']
        row['overshoot_mean'], row['overshoot_p999'] = overshoot(L0, U)
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=1)
    a = ap.parse_args()
    out = os.path.join(RESULTS, 'cr_vs_l3.csv')
    tasks = [(fo, n, f) for fo, n in IMAGES for f in FACTORS]
    if os.path.exists(out):
        prev = pd.read_csv(out)
        done = set(zip(prev.image, prev.factor))
        tasks = [t for t in tasks if (t[1], t[2]) not in done]
    print(f'{len(tasks)} tasks to run', flush=True)
    with ProcessPoolExecutor(a.jobs) as pool:
        futs = [pool.submit(task, t) for t in tasks]
        for i, fu in enumerate(as_completed(futs)):
            pd.DataFrame(fu.result()).to_csv(out, mode='a', header=not os.path.exists(out), index=False)
            print(f'{i + 1}/{len(tasks)}', flush=True)


if __name__ == '__main__':
    main()
