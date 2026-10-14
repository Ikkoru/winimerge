"""Perceptual metrics (heavy run): which candidate looks closest, and do the metrics agree?

    python3 heavy_analysis.py [--results /home/user/research/results]

Prints medians per candidate (ꟻLIP at 96 and 48 pixels per degree, Butteraugli max and 3-norm,
SSIMULACRA2, worst-tile SSIM, T_p99) and the mean Spearman rank correlation, within each pair, between
each metric and WinMerge's own outcome (T_p99).
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd

METRICS = [('T_p99', 'T_p99', False), ('flip_mean_ppd96', 'ꟻLIP mean @96', False), ('flip_p99_ppd96', 'ꟻLIP p99 @96', False),
           ('flip_mean_ppd48', 'ꟻLIP mean @48', False), ('ba_max', 'Butteraugli max', False), ('ba_p3', 'Butteraugli 3-norm', False),
           ('ssimu2', 'SSIMULACRA2', True), ('ssim_worst64', 'worst-tile SSIM', True)]
ORDER = ['nn_int_center', 'nn', 'sharp_bilinear', 'fi_bilinear', 'fi_mitchell', 'fi_catmullrom_f', 'fi_lanczos3', 'fi_lanczos3_f',
         'l3f_usm_r0.75_a0.5', 'l3f_usm_r1.0_a0.5', 'down_area', 'down_fi_catmullrom8', 'down_matched8', 'down_matched8a', 'down_oracle']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', default='/home/user/research/results')
    a = ap.parse_args()
    frames = []
    for f in sorted(glob.glob(os.path.join(a.results, 'heavy_*.csv'))):
        d = pd.read_csv(f, low_memory=False)
        d['set'] = 'real' if 'real' in f else 'synth'
        frames.append(d)
    d = pd.concat(frames).replace([np.inf, -np.inf], np.nan)
    d = d[d.edit == 'none']
    d['integer'] = d.factor.isin([2.0, 3.0, 4.0])
    for st in sorted(d.set.unique()):
        for integer in [True, False]:
            x = d[(d.set == st) & (d.integer == integer)]
            if x.empty:
                continue
            t = pd.DataFrame({lab: x.groupby('candidate')[m].median() for m, lab, _ in METRICS}).reindex([c for c in ORDER if c in set(x.candidate)])
            print(f'\n== {st}, {"whole-number factors" if integer else "factor 2.5"}: medians over {x.groupby(["image", "shrinker", "factor", "codec"]).ngroups} pairs')
            print(t.round(4).to_string())
    # within-pair rank agreement with T_p99, enlargers only (same canvas), and all candidates
    for scope, cands in [('enlargers', [c for c in ORDER if not c.startswith('down_')]), ('all', ORDER)]:
        rows = []
        for key, g in d[d.candidate.isin(cands)].groupby(['set', 'image', 'shrinker', 'factor', 'codec']):
            g = g.dropna(subset=['T_p99'])
            if len(g) < 4:
                continue
            r = {}
            for m, lab, higher_better in METRICS[1:]:
                v = g[m] if not higher_better else -g[m]
                if v.notna().sum() >= 4:
                    r[lab] = g['T_p99'].rank().corr(v.rank())
            rows.append(r)
        c = pd.DataFrame(rows).mean()
        print(f'\nMean within-pair Spearman correlation with T_p99 ({scope}):')
        print(c.round(3).to_string())


if __name__ == '__main__':
    main()
