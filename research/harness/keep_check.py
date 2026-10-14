"""Is the smaller copy worth keeping next to the larger one? Run on your own pairs (offline).

    python3 keep_check.py LARGE SMALL [--jpegqs]
    python3 keep_check.py FOLDER [--pairs pairs.csv] [--jpegqs] [--jobs 2]

Pairs in a folder are found as in compare_pairs.py (FOLDER/pairs.csv with columns a,b, or files sharing the
name before the first dot). For each pair:

  * what each file is: lossless (PNG, BMP, lossless WebP...), JPEG with the quality of its last save, or
    other lossy; for JPEGs whether an earlier save left traces (jpeg_history.py), and for lossless files
    whether they carry the 8x8 grid of an earlier JPEG save (a PNG made from a JPEG is not clean);
  * the larger file shrunk to the smaller one's size with WinIMerge's matched filter (DOWN_MATCHED), and
    how far that is from the smaller file: Butteraugli (max and 3-norm, at the small size) and the share
    of 8x8 blocks WinMerge marks at thresholds 8 and 16;
  * with --jpegqs, the same after restoring every JPEG with jpegQS -q 6 (how the copies look restored).

When the smaller file is lossless and clean, that distance is the larger file's compression damage that
survives at the smaller size (plus a little resampling mismatch), so it answers the question directly:
below the visibility threshold the small copy adds nothing you could see; above it, the small copy is the
cleaner picture at its size. When both are lossy the distance is the two damages together and cannot say
which side carries them; the study (REPORT section 10.3) found the larger file, shrunk, cleaner than a
lossy small copy in most cases, so the verdict says how this pair compares with those, and you judge
by flipping the two at the small size (DOWN_MATCHED, zoomed k x), restored.

Writes FOLDER/keep_results.csv (or prints only, for a single pair).
"""
import argparse
import csv
import io
import os
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image, ImageOps

import fi
import jpeg_history as JH
import metrics as M
import resample as R
import study as S
from compare_pairs import find_pairs

JPEGQS = os.environ.get('JPEGQS') or 'jpegqs'
VISIBLE_MAX = 1.0    # Butteraugli max-norm: about 1 is "just noticeable" (libjxl's convention)
BORDER = 0.2         # within 0.2 of it: borderline, look yourself


def file_kind(path):
    with Image.open(path) as im:
        fmt = im.format
        if fmt == 'JPEG':
            return 'jpeg'
        if fmt == 'WEBP':
            return 'lossless' if b'VP8L' in open(path, 'rb').read() else 'lossy'
        if fmt == 'TIFF' and str(im.info.get('compression', '')).lower() in ('jpeg', 'tiff_jpeg'):
            return 'jpeg-in-tiff'
        if fmt in ('PNG', 'BMP', 'TIFF', 'PPM', 'TGA', 'QOI'):
            return 'lossless'
        if fmt == 'GIF':
            return 'palette'
        return 'other'


def load(path):
    with Image.open(path) as im:
        return np.asarray(ImageOps.exif_transpose(im).convert('RGB'))


def jpegqs(path):
    with tempfile.TemporaryDirectory() as d:
        dst = os.path.join(d, 'b.jpg')
        subprocess.run([JPEGQS, '-q', '6', '-i', '0', '-t', '1', path, dst], check=True, capture_output=True)
        with Image.open(dst) as im:
            return np.asarray(ImageOps.exif_transpose(im).convert('RGB'))


def jpeg_traces(rgb):
    """Grid periodicity of a lossless picture: a strong 8x8 lattice means it was a JPEG once."""
    x = rgb.astype(np.float64)
    x = JH.central(x)
    S_, Q, n = JH.grid_scores(0.299 * x[..., 0] + 0.587 * x[..., 1] + 0.114 * x[..., 2])
    if n < JH.MIN_BLOCKS:
        return None
    med = float(np.median(S_.ravel()))
    oy, ox = np.unravel_index(S_.argmax(), S_.shape)
    return (int(ox), int(oy), int(Q[oy, ox]), float(S_.max())) if S_.max() >= max(JH.GRID_MIN, JH.GRID_RATIO * med) else None


def describe(path, rgb):
    kind = file_kind(path)
    d = {'kind': kind, 'quality': None, 'history': '', 'sampling': ''}
    if kind == 'jpeg':
        r = JH.analyse(open(path, 'rb').read())
        d['quality'] = r['last_q']
        try:
            from PIL import JpegImagePlugin
            with Image.open(path) as im:
                d['sampling'] = {0: '4:4:4', 1: '4:2:2', 2: '4:2:0'}.get(JpegImagePlugin.get_sampling(im), '')
        except Exception:
            pass
        d['history'] = '' if not (r['ghost'] or r['grids']) else JH.verdict(r)
    elif kind == 'lossless':
        t = jpeg_traces(rgb)
        if t:
            d['history'] = f'carries the 8x8 grid of an earlier JPEG save (offset x+{t[0]} y+{t[1]}, step {t[2]}): not clean'
    return d


def matched_shrink(Hx, Lx):
    h, w = Lx.shape[:2]
    best = None
    for k in S.MATCH8 + ['area']:
        D = R.SHRINKERS['area'](Hx, w, h) if k == 'area' else fi.rescale(Hx, w, h, k)
        err = np.abs(D.astype(np.int16) - Lx.astype(np.int16)).mean()
        if best is None or err < best[0]:
            best = (err, k, D)
    return best[1], best[2]


def distances(Hx, Lx, k):
    kern, D = matched_shrink(Hx, Lx)
    out, _ = M.cheap_panel(D, Lx)
    ba = M.butteraugli(Lx, D)
    f, _ = M.flip(Lx, D, 96.0 / k)
    return dict(kernel=kern, ba_max=ba['ba_max'], ba_p3=ba['ba_p3'], flip_zoomed=f['flip_mean'],
                share_T8=out['share_T8'], share_T16=out['share_T16'], T_p99=out['T_p99'])


def verdict(r):
    lk, hk = r['small_kind'], r['large_kind']
    lclean = lk == 'lossless' and not r['small_history']
    m = r['ba_max']
    level = 'none' if m < VISIBLE_MAX - BORDER else 'borderline' if m <= VISIBLE_MAX + BORDER else 'visible'
    if r['aspect_mismatch'] > 0.01:
        return 'the two pictures do not have the same proportions (cropped?): not comparable this way'
    if hk == 'lossless' and not r['large_history']:
        return 'the larger file is lossless: it holds everything the small copy does; keep the larger file only'
    if lclean:
        if level == 'none':
            return ('the small copy adds nothing visible at its size: the larger file shrunk is within the visibility '
                    'threshold of it; keeping the larger file is enough')
        if level == 'borderline':
            return ('borderline: the larger file\'s damage that survives at the small size is near the visibility threshold; '
                    'flip the two in WinMerge (Shrink to Smallest, zoomed) and decide by eye')
        return ('the small copy is visibly cleaner at its size: the larger file\'s compression damage survives the shrink; '
                'keep both if you will look at the picture at the small size')
    if level == 'none':
        return 'the two agree at the small size within the visibility threshold: the small copy adds nothing visible'
    return ('both copies are lossy and differ at the small size; usually the larger file shrunk is the cleaner one '
            '(REPORT 10.3), so flip the two at the small size, zoomed in, after restoring both with jpegQS')


def run_pair(args):
    folder, a, b, restore = args
    pa, pb = (os.path.join(folder, a), os.path.join(folder, b)) if folder else (a, b)
    A, B = load(pa), load(pb)
    if A.shape[0] * A.shape[1] < B.shape[0] * B.shape[1]:
        A, B, pa, pb = B, A, pb, pa
    k = A.shape[1] / B.shape[1]
    r = dict(large=os.path.basename(pa), small=os.path.basename(pb), large_size=f'{A.shape[1]}x{A.shape[0]}',
             small_size=f'{B.shape[1]}x{B.shape[0]}', factor=round(k, 3),
             aspect_mismatch=abs(A.shape[1] / A.shape[0] - B.shape[1] / B.shape[0]) / (A.shape[1] / A.shape[0]))
    dl, ds = describe(pa, A), describe(pb, B)
    r.update(large_kind=dl['kind'], large_quality=dl['quality'], large_history=dl['history'], large_sampling=dl['sampling'],
             small_kind=ds['kind'], small_quality=ds['quality'], small_history=ds['history'], small_sampling=ds['sampling'])
    r.update(distances(A, B, k))
    if restore and 'jpeg' in (dl['kind'], ds['kind']):
        A2 = jpegqs(pa) if dl['kind'] == 'jpeg' else A
        B2 = jpegqs(pb) if ds['kind'] == 'jpeg' else B
        r.update({'restored_' + kk: v for kk, v in distances(A2, B2, k).items()})
    r['verdict'] = verdict(r)
    return r


def show(r):
    q = lambda kind, ql, sm: kind + (f' q{ql}' if ql else '') + (f' {sm}' if sm else '')
    print(f"{r['large']} ({r['large_size']}, {q(r['large_kind'], r['large_quality'], r['large_sampling'])}) and "
          f"{r['small']} ({r['small_size']}, {q(r['small_kind'], r['small_quality'], r['small_sampling'])}), factor {r['factor']}")
    for side in ('large', 'small'):
        if r[side + '_history']:
            print(f'  {side} file: {r[side + "_history"]}')
    print(f"  at the small size (matched filter: {r['kernel']}): Butteraugli max {r['ba_max']:.2f}, 3-norm {r['ba_p3']:.2f}; "
          f"WinMerge marks {100 * r['share_T8']:.1f} % of blocks at threshold 8, {100 * r['share_T16']:.1f} % at 16")
    if 'restored_ba_max' in r:
        print(f"  restored with jpegQS: Butteraugli max {r['restored_ba_max']:.2f}, 3-norm {r['restored_ba_p3']:.2f}")
    print(f"  -> {r['verdict']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+', help='LARGE SMALL, or a FOLDER')
    ap.add_argument('--pairs', default='')
    ap.add_argument('--jpegqs', action='store_true', help='also compare after restoring the JPEGs with jpegQS -q 6')
    ap.add_argument('--jobs', type=int, default=2)
    a = ap.parse_args()
    if len(a.paths) == 2 and all(os.path.isfile(p) for p in a.paths):
        show(run_pair(('', a.paths[0], a.paths[1], a.jpegqs)))
        return
    folder = a.paths[0]
    pairs = find_pairs(folder, a.pairs or os.path.join(folder, 'pairs.csv'))
    with ProcessPoolExecutor(a.jobs) as pool:
        rows = list(pool.map(run_pair, [(folder, x, y, a.jpegqs) for x, y in pairs]))
    for r in rows:
        show(r)
    if rows:
        out = os.path.join(folder, 'keep_results.csv')
        keys = sorted({k for r in rows for k in r})
        with open(out, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        print('wrote', out)


if __name__ == '__main__':
    main()
