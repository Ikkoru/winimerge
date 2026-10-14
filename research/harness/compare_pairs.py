"""Run the comparison on your own image pairs (offline, nothing fetched from the network).

    python3 compare_pairs.py FOLDER [--pairs pairs.csv] [--heavy] [--eyecheck OUTDIR] [--jobs 4]

FOLDER holds the images. Pairs come from FOLDER/pairs.csv (two columns, header `a,b`, file names
relative to FOLDER); without it, files are paired by name: `<stem>.<anything>` files that share the
same <stem> before the first dot form a pair (e.g. `cat.orig.png` + `cat.copy.jpg`).

For every pair, the larger image is the reference L and the smaller one the copy S. Each candidate
either enlarges S to L's size or (the down_* strategies) shrinks L to S's size, and the result is
compared with the other image: WinMerge's block outcome at thresholds 0..64 (share of 8x8 blocks
marked), the threshold that leaves at most 1 % of blocks marked (T_p99), PSNR and, with --heavy,
FLIP (96 and 48 pixels per degree), Butteraugli and SSIMULACRA2.

Unlike the synthetic study, nobody knows how the copy was made or whether it was edited, so the
numbers say how *close* each strategy makes the pair, not whether a difference is real. Use the
eye-check page (--eyecheck) to look at the strongest differences.

Writes FOLDER/compare_results.csv and prints a short summary per pair.
"""
import argparse
import csv
import json
import os
import sys
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageOps

import fi
import metrics as M
import resample as R
import study as S

CANDS = ['nn_int_center', 'nn', 'fi_bilinear', 'fi_mitchell', 'fi_catmullrom_f', 'fi_lanczos3', 'l3f_usm_r1.0_a0.5']


def load(path):
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)  # WinIMerge applies the EXIF orientation too
    return np.asarray(im.convert('RGB'))


def find_pairs(folder, pairs_csv):
    if pairs_csv and os.path.exists(pairs_csv):
        with open(pairs_csv, newline='') as fh:
            return [(r['a'], r['b']) for r in csv.DictReader(fh)]
    groups = {}
    for f in sorted(os.listdir(folder)):
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff')):
            groups.setdefault(f.split('.')[0], []).append(f)
    return [tuple(v[:2]) for v in groups.values() if len(v) >= 2]


def run_pair(args):
    folder, a, b, heavy = args
    A, B = load(os.path.join(folder, a)), load(os.path.join(folder, b))
    if A.shape[0] * A.shape[1] >= B.shape[0] * B.shape[1]:
        L, Sm, ln, sn = A, B, a, b
    else:
        L, Sm, ln, sn = B, A, b, a
    H, W = L.shape[:2]
    h, w = Sm.shape[:2]
    rows = []
    base = dict(large=ln, small=sn, W=W, H=H, w=w, h=h, factor_x=round(W / w, 4), factor_y=round(H / h, 4))
    aspect_ok = abs(W / w - H / h) <= max(W / w, H / h) * 2.0 / min(w, h) + 1e-9
    base['aspect_matches'] = int(aspect_ok)
    for c in CANDS:
        U, valid = S.UPSCALERS[c](Sm, W, H)
        out, _ = M.cheap_panel(L, U, valid)
        row = dict(base, candidate=c, **out)
        if heavy and valid is None:
            row.update(M.heavy_panel(L, U))
        rows.append(row)
    downs, k = S.down_strategies(L, Sm, 'area')
    for dname in ['down_area', 'down_fi_box8', 'down_fi_bicubic8', 'down_fi_catmullrom8', 'down_fi_lanczos38', 'down_matched8a']:
        D = downs[dname]
        out, _ = M.cheap_panel(D, Sm)
        row = dict(base, candidate=dname, matched_kernel=k.get(dname, ''), **out)
        if heavy:
            row.update(M.heavy_panel(D, Sm))
        rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('folder')
    ap.add_argument('--pairs', default='')
    ap.add_argument('--heavy', action='store_true')
    ap.add_argument('--eyecheck', default='')
    ap.add_argument('--jobs', type=int, default=4)
    a = ap.parse_args()
    pairs = find_pairs(a.folder, a.pairs or os.path.join(a.folder, 'pairs.csv'))
    if not pairs:
        sys.exit('no pairs found')
    print(f'{len(pairs)} pairs')
    with Pool(a.jobs) as pool:
        results = pool.map(run_pair, [(a.folder, x, y, a.heavy) for x, y in pairs])
    rows = [r for rr in results for r in rr]
    fields = list(dict.fromkeys(k for r in rows for k in r))
    out_csv = os.path.join(a.folder, 'compare_results.csv')
    with open(out_csv, 'w', newline='') as fh:
        wr = csv.DictWriter(fh, fieldnames=fields, restval='')
        wr.writeheader()
        wr.writerows(rows)
    for rr in results:
        r0 = rr[0]
        print(f"\n{r0['large']} ({r0['W']}x{r0['H']}) vs {r0['small']} ({r0['w']}x{r0['h']}), factor {r0['factor_x']}"
              f"{'' if r0['aspect_matches'] else '  [aspect ratios differ: crop or padding?]'}")
        for r in sorted(rr, key=lambda r: r['T_p99']):
            print(f"  {r['candidate']:22s} blocks marked @T16 {r['share_T16']:6.1%}  T_p99 {r['T_p99']:6.1f}"
                  + (f"  PSNR {r['psnr']:5.1f}" if 'psnr' in r else '')
                  + (f"  kernel={r['matched_kernel']}" if r.get('matched_kernel') else ''))
    print('\nwrote', out_csv)
    if a.eyecheck:
        import eyecheck
        cases = []
        for x, y in pairs:
            cases.append(dict(pair=(os.path.join(a.folder, x), os.path.join(a.folder, y))))
        eyecheck.build_pairs(a.eyecheck, cases)


if __name__ == '__main__':
    main()
