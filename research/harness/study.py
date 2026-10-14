"""Experiment runner: shrink -> (codec) -> enlarge with each candidate -> compare with the original.

    python3 study.py run EXP --images DIR [--jobs 4] [--out results/] [--limit-images a,b]
    python3 study.py list

EXP is one of the keys of EXPERIMENTS below. Results are appended to <out>/<EXP>.csv, one row per
(image, edit, shrinker, factor, codec, candidate). Everything is computed in memory from the
large originals in --images (PNG/JPEG/WebP files, decoded once with Pillow), so the harness can be
re-run on the user's own pairs folder (see compare_pairs.py for real pairs).
"""
import argparse
import csv
import io
import math
import os
import sys
import time
from multiprocessing import Pool

import cv2
import numpy as np
from PIL import Image

import edits as E
import fi
import metrics as M
import resample as R

# ------------------------------------------------------------------ candidates (enlargers)


def _place(img, W, H, align='center'):
    """Put a smaller image on a W x H canvas (as WinIMerge would with the alignment option)."""
    h, w = img.shape[:2]
    out = np.zeros((H, W, 3), np.uint8)
    valid = np.zeros((H, W), bool)
    ox, oy = ((W - w) // 2, (H - h) // 2) if align == 'center' else (0, 0)
    out[oy:oy + h, ox:ox + w] = img
    valid[oy:oy + h, ox:ox + w] = True
    return out, valid


def up_nn_int(S, W, H, align='center'):
    k = R.int_factor((S.shape[1], S.shape[0]), (W, H))
    U = R.nn_int(S, k)
    if U.shape[:2] == (H, W):
        return U, None
    return _place(U, W, H, align)


def up_sharp_bilinear(S, W, H):
    k = R.int_factor((S.shape[1], S.shape[0]), (W, H))
    return fi.rescale(R.nn_int(S, k), W, H, 'bilinear'), None


def _usm(base, r, a):
    return lambda S, W, H: (R.unsharp(base(S, W, H)[0], r, a), None)


UPSCALERS = {
    'nn_int_center': lambda S, W, H: up_nn_int(S, W, H, 'center'),
    'nn_int_topleft': lambda S, W, H: up_nn_int(S, W, H, 'topleft'),
    'nn': lambda S, W, H: (R.nn_exact(S, W, H), None),
    'sharp_bilinear': up_sharp_bilinear,
    'fi_bilinear': lambda S, W, H: (fi.rescale(S, W, H, 'bilinear'), None),
    'fi_bspline': lambda S, W, H: (fi.rescale(S, W, H, 'bspline'), None),
    'fi_mitchell': lambda S, W, H: (fi.rescale(S, W, H, 'bicubic'), None),
    'fi_catmullrom': lambda S, W, H: (fi.rescale(S, W, H, 'catmullrom'), None),
    'fi_lanczos3': lambda S, W, H: (fi.rescale(S, W, H, 'lanczos3'), None),
    'fi_catmullrom_f': lambda S, W, H: (fi.rescale(S, W, H, 'catmullrom', float_path=True), None),
    'fi_lanczos3_f': lambda S, W, H: (fi.rescale(S, W, H, 'lanczos3', float_path=True), None),
    'ref_lanczos2_f': lambda S, W, H: (R.resize(S, W, H, 'lanczos2'), None),
    'ref_lanczos4_f': lambda S, W, H: (R.resize(S, W, H, 'lanczos4'), None),
}
def _linear(kernel):
    # resample in linear light (sRGB decoded to linear, resampled in float, encoded back)
    return lambda S, W, H: (R.linear_to_srgb(R.resize_float(R.srgb_to_linear(S), W, H, kernel)), None)


UPSCALERS['lin_lanczos3_f'] = _linear('lanczos3')
UPSCALERS['lin_catmullrom_f'] = _linear('catmullrom')
BASE_L3F = UPSCALERS['fi_lanczos3_f']
BASE_CRF = UPSCALERS['fi_catmullrom_f']
USM_GRID = [(r, a) for r in (0.5, 0.75, 1.0, 1.5) for a in (0.25, 0.5, 0.75, 1.0)]
for _r, _a in USM_GRID:
    UPSCALERS[f'l3f_usm_r{_r}_a{_a}'] = _usm(BASE_L3F, _r, _a)
for _r, _a in [(0.75, 0.5), (1.0, 0.5)]:
    UPSCALERS[f'crf_usm_r{_r}_a{_a}'] = _usm(BASE_CRF, _r, _a)

MAIN = ['nn_int_center', 'nn_int_topleft', 'nn', 'sharp_bilinear', 'fi_bilinear', 'fi_bspline', 'fi_mitchell',
        'fi_catmullrom', 'fi_lanczos3', 'fi_catmullrom_f', 'fi_lanczos3_f', 'ref_lanczos2_f', 'ref_lanczos4_f',
        'l3f_usm_r1.0_a0.5', 'l3f_usm_r0.75_a0.5']
HEAVY = ['nn_int_center', 'nn', 'sharp_bilinear', 'fi_bilinear', 'fi_mitchell', 'fi_lanczos3', 'fi_lanczos3_f',
         'fi_catmullrom_f', 'l3f_usm_r1.0_a0.5', 'l3f_usm_r0.75_a0.5']
EDIT_CANDS = ['nn_int_center', 'nn', 'sharp_bilinear', 'fi_bilinear', 'fi_mitchell', 'fi_catmullrom_f', 'fi_lanczos3',
              'fi_lanczos3_f', 'ref_lanczos4_f', 'l3f_usm_r1.0_a0.5', 'l3f_usm_r0.75_a0.5']
USM_SET = ['fi_lanczos3_f', 'fi_catmullrom_f'] + [f'l3f_usm_r{r}_a{a}' for r, a in USM_GRID] + \
          ['crf_usm_r0.75_a0.5', 'crf_usm_r1.0_a0.5']

# "compare at the smaller size": shrink the large original instead of enlarging the copy
FI_DOWN = ['box', 'bilinear', 'bspline', 'bicubic', 'catmullrom', 'lanczos3']


def down_strategies(L, S, true_shrinker):
    h, w = S.shape[:2]
    out = {'down_area': R.SHRINKERS['area'](L, w, h),
           'down_oracle': R.SHRINKERS[true_shrinker](L, w, h)}
    best, best_err, best_k = None, None, None
    for k in FI_DOWN:
        D = fi.rescale(L, w, h, k, float_path=True)
        out['down_fi_' + k] = D
        err = np.abs(D.astype(np.int16) - S.astype(np.int16)).mean()
        if best_err is None or err < best_err:
            best, best_err, best_k = D, err, k
    out['down_fi_box8'] = fi.rescale(L, w, h, 'box')  # FreeImage's 8-bit path (as fipImage::rescale)
    for k in ('bilinear', 'bicubic', 'catmullrom', 'lanczos3'):
        # 8-bit path: rounds/clamps between passes like Pillow does, so it mimics Pillow-made copies
        out['down_fi_' + k + '8'] = fi.rescale(L, w, h, k)
    out['down_matched'] = best
    # the rule WinIMerge's IMAGE_SCALING_DOWN_MATCHED uses (ResizeImageMatching): FreeImage's 8-bit
    # path, five kernels in this order, lowest mean absolute difference (first one wins a tie)
    best8, best8_err, best8_k = None, None, None
    for k in MATCH8:
        D = out['down_fi_' + k + '8']
        err = np.abs(D.astype(np.int16) - S.astype(np.int16)).mean()
        if best8_err is None or err < best8_err:
            best8, best8_err, best8_k = D, err, k
    out['down_matched8'] = best8
    # with WinIMerge's exact area-averaging candidate as well (ResizeImageArea; OpenCV's INTER_AREA stands
    # in for it here: they agree to within 1 level, in 0.2 % of the values)
    best8a, best8a_k = best8, best8_k
    area = out['down_area']
    err = np.abs(area.astype(np.int16) - S.astype(np.int16)).mean()
    if err < best8_err:
        best8a, best8a_k = area, 'area'
    out['down_matched8a'] = best8a
    return out, {'down_matched': best_k, 'down_matched8': best8_k, 'down_matched8a': best8a_k}


MATCH8 = ['box', 'bilinear', 'bicubic', 'catmullrom', 'lanczos3']
DOWN_NAMES = ['down_area', 'down_oracle'] + ['down_fi_' + k for k in FI_DOWN] + ['down_fi_box8'] + \
             ['down_fi_' + k + '8' for k in ('bilinear', 'bicubic', 'catmullrom', 'lanczos3')] + ['down_matched', 'down_matched8', 'down_matched8a']

# ------------------------------------------------------------------ codecs


JPEGQS = os.environ.get('JPEGQS', '/tmp/claude-0/-home-user/c93e777e-edee-5658-827e-7ebd2f76571d/scratchpad/ext/jpeg-quantsmooth/jpegqs')


def codec(img, name):
    if name == 'png':
        return img
    if '_qs' in name:  # e.g. jpg85_qs6: JPEG q85 4:2:0, then restored with jpegQS -q 6
        import subprocess, tempfile
        base, qs = name.split('_qs')
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, 'a.jpg'), os.path.join(d, 'b.jpg')
            Image.fromarray(img).save(src, 'JPEG', quality=int(base[3:5]), subsampling=2)
            subprocess.run([JPEGQS, '-q', qs, '-i', '0', '-t', '1', src, dst], check=True, capture_output=True)
            return np.asarray(Image.open(dst).convert('RGB'))
    buf = io.BytesIO()
    pil = Image.fromarray(img)
    if name.startswith('jpg'):
        q = int(name[3:5])
        sub = 0 if name.endswith('_444') else 2
        pil.save(buf, 'JPEG', quality=q, subsampling=sub)
    elif name.startswith('webp'):
        pil.save(buf, 'WEBP', quality=int(name[4:6]), method=4)
    buf.seek(0)
    return np.asarray(Image.open(buf).convert('RGB'))

# ------------------------------------------------------------------ experiments

ALL_SHRINKERS = ['area', 'pil_bilinear', 'cv_linear', 'pil_bicubic', 'pil_lanczos', 'mitchell', 'lanczos_linear',
                 'lanczos_sharpened', 'vips', 'nearest']
ALL_EDITS = list(E.EDITS)

EXPERIMENTS = {
    # spurious differences between an image and its own enlarged small copy
    'spurious': dict(edits=['none'], shrinkers=ALL_SHRINKERS, factors=[1.25, 1.5, 2, 2.5, 3, 4],
                     codecs=['png', 'jpg85'], candidates=MAIN, down=True, heavy=False),
    # how the codec of the small copy changes things
    'codec': dict(edits=['none'], shrinkers=['pil_lanczos', 'area'], factors=[2, 2.5],
                  codecs=['png', 'jpg95', 'jpg85', 'jpg75', 'jpg60', 'jpg85_444', 'webp90', 'webp75'],
                  candidates=MAIN, down=True, heavy=False),
    # can a real edit still be seen? (edited small copy vs original, with unedited twin as baseline)
    'edits': dict(edits=ALL_EDITS, shrinkers=['area', 'pil_lanczos'], factors=[2, 2.5, 3, 4],
                  codecs=['png', 'jpg85'], candidates=EDIT_CANDS, down=True, heavy=False),
    # unsharp-mask sweep
    'usm': dict(edits=['none', 'text_small', 'line', 'dot', 'move'], shrinkers=['area', 'pil_lanczos'],
                factors=[1.5, 2, 3], codecs=['png', 'jpg85'], candidates=USM_SET, down=False, heavy=False),
    # resampling in linear light instead of gamma-encoded sRGB
    'linear': dict(edits=['none', 'text_small', 'line'], shrinkers=['pil_lanczos', 'lanczos_linear', 'area'], factors=[2, 2.5, 3],
                   codecs=['png'], candidates=['fi_lanczos3_f', 'lin_lanczos3_f', 'fi_catmullrom_f', 'lin_catmullrom_f'],
                   down=False, heavy=False),
    # restoring the small JPEG with jpegQS before comparing
    'jpegqs': dict(edits=['none', 'text_small', 'line'], shrinkers=['pil_lanczos', 'area'], factors=[2, 2.5, 3],
                   codecs=['jpg85', 'jpg85_qs3', 'jpg85_qs6', 'jpg60', 'jpg60_qs3', 'jpg60_qs6'],
                   candidates=['nn', 'fi_lanczos3_f', 'l3f_usm_r1.0_a0.5'], down=True, heavy=False),
    # perceptual metrics on a subset
    'heavy': dict(edits=['none'], shrinkers=['area', 'pil_lanczos'], factors=[2, 2.5, 3],
                  codecs=['png', 'jpg85'], candidates=HEAVY, down=True, heavy=True),
}

# ------------------------------------------------------------------ worker

_CACHE = {}


def _load(path):
    if path not in _CACHE:
        _CACHE.clear()
        _CACHE[path] = np.asarray(Image.open(path).convert('RGB'))
    return _CACHE[path]


def _edit_blocks(mask, guard_px, block=8):
    eb = M.block_reduce(mask.astype(np.float32), block, 'max') > 0
    if guard_px > 0:
        k = 2 * guard_px + 1
        dil = cv2.dilate(mask.astype(np.uint8), np.ones((k, k), np.uint8))
        gb = (M.block_reduce(dil.astype(np.float32), block, 'max') > 0) & ~eb
    else:
        gb = np.zeros_like(eb)
    return eb, gb


def _detection(bm0, bm1, eb, gb):
    nb = ~(eb | gb)
    if eb.sum() == 0 or nb.sum() == 0:
        return {}
    base = bm0[nb]
    t1, t01 = np.percentile(base, 99), np.percentile(base, 99.9)
    e = bm1[eb]
    peak = float(e.max())
    return {'det_T1': float((e > t1).mean()), 'det_T01': float((e > t01).mean()),
            'T1': float(t1), 'T01': float(t01), 'edit_peak': peak,
            'outrank': int((bm1[nb] >= peak).sum()), 'edit_blocks': int(eb.sum()),
            'any_T1': int((e > t1).any()), 'any_T01': int((e > t01).any())}


def run_task(task):
    path, edit, shrinker, factor, cod, cands, do_down, heavy, *rest = task
    skip = rest[0] if rest else frozenset()   # down rows already in the CSV (--down-only)
    name = os.path.splitext(os.path.basename(path))[0]
    t0 = time.time()
    L0 = _load(path)
    H, W = L0.shape[:2]
    w, h = R.small_size(W, H, factor)
    S0 = codec(R.SHRINKERS[shrinker](L0, w, h), cod)
    rows = []
    base = dict(image=name, edit=edit, shrinker=shrinker, factor=factor, codec=cod, W=W, H=H, w=w, h=h)
    if edit != 'none':
        L1, mask = E.apply(edit, L0)
        S1 = codec(R.SHRINKERS[shrinker](L1, w, h), cod)
        eb, gb = _edit_blocks(mask, int(math.ceil(3 * factor)) + 2)
        # edit footprint at the small size, for the compare-at-small strategies
        mask_s = cv2.resize(mask.astype(np.float32), (w, h), interpolation=cv2.INTER_AREA) > 0
        ebs, gbs = _edit_blocks(mask_s, 3)
        base['edit_px'] = int(mask.sum())
    for c in cands:
        U0, valid = UPSCALERS[c](S0, W, H)
        row = dict(base, candidate=c)
        if edit == 'none':
            out, bm0 = M.cheap_panel(L0, U0, valid, ssim=heavy)
            row.update(out)
            if heavy:
                if valid is not None:   # whole-number NN that does not fill the canvas: compare the overlap
                    ys, xs = np.where(valid)
                    sl = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
                    row.update(M.heavy_panel(L0[sl], U0[sl]))
                    row['heavy_on_overlap'] = 1
                else:
                    row.update(M.heavy_panel(L0, U0))
        else:
            bm0 = M.block_max_distance(L0, U0, valid)
            U1, valid1 = UPSCALERS[c](S1, W, H)
            bm1 = M.block_max_distance(L0, U1, valid1)
            row.update(_detection(bm0, bm1, eb, gb))
        rows.append(row)
    if do_down:
        downs0, k0 = down_strategies(L0, S0, shrinker)
        if edit != 'none':
            downs1, _ = down_strategies(L0, S1, shrinker)  # the original shrunk; compared with the edited copy
        for dname, D in downs0.items():
            if dname in skip:
                continue
            row = dict(base, candidate=dname, matched_kernel=k0.get(dname, ''))
            if edit == 'none':
                out, _ = M.cheap_panel(D, S0, ssim=heavy)
                row.update(out)
                if heavy:
                    row.update(M.heavy_panel(D, S0, ppds=(96, 48)))
            else:
                bm0 = M.block_max_distance(D, S0)
                bm1 = M.block_max_distance(downs1[dname], S1)
                row.update(_detection(bm0, bm1, ebs, gbs))
            rows.append(row)
    for r in rows:
        r['secs'] = round(time.time() - t0, 2)
    return rows


def build_tasks(exp, image_paths):
    cfg = EXPERIMENTS[exp]
    tasks = []
    for p in image_paths:
        for e in cfg['edits']:
            for s in cfg['shrinkers']:
                for f in cfg['factors']:
                    for c in cfg['codecs']:
                        tasks.append((p, e, s, f, c, cfg['candidates'], cfg['down'], cfg['heavy']))
    return tasks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run', 'list'])
    ap.add_argument('exp', nargs='?')
    ap.add_argument('--images', default='/home/user/research/testset/large')
    ap.add_argument('--out', default='/home/user/research/results')
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--only', default='', help='comma-separated image names to include')
    ap.add_argument('--tag', default='', help='suffix for the output CSV name')
    ap.add_argument('--down-only', action='store_true',
                    help='only add the compare-at-the-smaller-size rows missing from an existing CSV')
    for k in ('shrinkers', 'factors', 'codecs', 'edits', 'candidates'):
        ap.add_argument('--' + k, default='', help=f'comma-separated override of the experiment\'s {k}')
    args = ap.parse_args()
    if args.cmd == 'list':
        for k, v in EXPERIMENTS.items():
            print(k, {kk: (len(vv) if isinstance(vv, list) else vv) for kk, vv in v.items()})
        return
    paths = sorted(os.path.join(args.images, f) for f in os.listdir(args.images)
                   if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')))
    if args.only:
        keep = set(args.only.split(','))
        paths = [p for p in paths if os.path.splitext(os.path.basename(p))[0] in keep]
    for k in ('shrinkers', 'factors', 'codecs', 'edits', 'candidates'):
        v = getattr(args, k)
        if v:
            EXPERIMENTS[args.exp][k] = [float(x) for x in v.split(',')] if k == 'factors' else v.split(',')
    tasks = build_tasks(args.exp, paths)
    os.makedirs(args.out, exist_ok=True)
    out_csv = os.path.join(args.out, f'{args.exp}{"_" + args.tag if args.tag else ""}.csv')
    header = FIELDS_ORDER
    done = set()
    if args.down_only and not (os.path.exists(out_csv) and os.path.getsize(out_csv) > 0):
        raise SystemExit(f'--down-only needs an existing {out_csv}')
    if os.path.exists(out_csv) and os.path.getsize(out_csv) > 0:
        # resume: keep complete rows, drop a half-written last line, skip tasks already done
        with open(out_csv, newline='') as fh:
            lines = list(csv.reader(fh))
        header, body = lines[0], [l for l in lines[1:] if len(l) == len(lines[0])]
        key_idx = [header.index(k) for k in ('image', 'edit', 'shrinker', 'factor', 'codec')]
        counts = {}
        for l in body:
            k = tuple(l[i] for i in key_idx)
            counts[k] = counts.get(k, 0) + 1
        expected = len(EXPERIMENTS[args.exp]['candidates']) + (3 if EXPERIMENTS[args.exp]['down'] else 0)  # tasks run before the down_fi_* rows were added have 3 down rows
        done = {k for k, n in counts.items() if n >= expected}
        if args.down_only:
            # keep every complete row; a task needs work when one of the down rows is missing
            ci = header.index('candidate')
            present = {}
            for l in body:
                present.setdefault(tuple(l[i] for i in key_idx), set()).add(l[ci])
            norm0 = lambda k: (k[0], k[1], k[2], str(float(k[3])), k[4])
            present = {norm0(k): frozenset(v) & frozenset(DOWN_NAMES) for k, v in present.items()}
            def key0(t):
                return (os.path.splitext(os.path.basename(t[0]))[0], t[1], t[2], str(float(t[3])), t[4])
            tasks = [t[:5] + ([], True, t[7], present.get(key0(t), frozenset())) for t in tasks
                     if key0(t) in present and not present[key0(t)] >= frozenset(DOWN_NAMES)]
            done = set()
        else:
            body = [l for l in body if tuple(l[i] for i in key_idx) in done]
        with open(out_csv, 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(header)
            w.writerows(body)
    def key(t):
        return (os.path.splitext(os.path.basename(t[0]))[0], t[1], t[2], repr(float(t[3])) if False else str(t[3]), t[4])
    norm = lambda k: (k[0], k[1], k[2], str(float(k[3])), k[4])
    done_norm = {norm(k) for k in done}
    tasks = [t for t in tasks if norm(key(t)) not in done_norm]
    print(f'{args.exp}: {len(tasks)} tasks to run on {len(paths)} images ({len(done)} already done) -> {out_csv}', flush=True)
    n, t0 = 0, time.time()
    new_file = not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0
    with open(out_csv, 'a', newline='') as fh, Pool(args.jobs) as pool:
        writer = csv.DictWriter(fh, fieldnames=header, extrasaction='ignore', restval='')
        if new_file:
            writer.writeheader()
        for rows in pool.imap_unordered(run_task, tasks, chunksize=1):
            n += 1
            writer.writerows(rows)
            fh.flush()
            if n % 20 == 0 or n == len(tasks):
                el = time.time() - t0
                print(f'  {n}/{len(tasks)} tasks, {el / 60:.1f} min elapsed, ~{el / n * (len(tasks) - n) / 60:.1f} min left', flush=True)


FIELDS_ORDER = ['image', 'edit', 'shrinker', 'factor', 'codec', 'candidate', 'W', 'H', 'w', 'h', 'edit_px', 'matched_kernel',
                'share_T0', 'share_T2', 'share_T4', 'share_T8', 'share_T16', 'share_T32', 'share_T64',
                'regions_T8', 'regions_T16', 'regions_T32', 'T_p99', 'T_p999', 'T_max', 'blockmax_median',
                'psnr', 'worst_block_mean', 'ssim', 'ssim_worst64',
                'flip_mean_ppd96', 'flip_p95_ppd96', 'flip_p99_ppd96', 'flip_max_ppd96',
                'flip_mean_ppd48', 'flip_p95_ppd48', 'flip_p99_ppd48', 'flip_max_ppd48',
                'ba_max', 'ba_p3', 'ssimu2', 'heavy_on_overlap',
                'det_T1', 'det_T01', 'any_T1', 'any_T01', 'T1', 'T01', 'edit_peak', 'outrank', 'edit_blocks', 'secs']

if __name__ == '__main__':
    main()
