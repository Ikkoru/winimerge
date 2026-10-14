"""Compression damage: which copy is cleaner, is a smaller copy worth keeping, and what jpegQS can recover.

    python3 compression_test.py recover [--jobs 4]   # one-time vs multi-compressed JPEGs, before/after jpegQS
    python3 compression_test.py keep [--jobs 4]      # large lossy copy + small copy: is the small one worth keeping?

Masters: 4 synthetic and 5 real images (lossless). JPEGs are made with Pillow (libjpeg-turbo, 4:2:0) and
decoded the same way; jpegQS is jpeg-quantsmooth (`JPEGQS`, default `jpegqs` on PATH). The JPEG
histories (each ends with a save of the whole picture, so jpegQS sees that file):
  q95 q90 q85 q80 q70     saved once
  q75>q90                 saved at q75, then again at q90 (aligned block grid)
  q60>q90                 q60, then q90
  q80s>q90                q80 with the picture shifted by 3 px (block grid moved), then q90
  q85s>q85                q85 shifted by 4 px, then q85
  q90s>q90s>q90           three q90 saves, the first two shifted by 3 and 5 px (a twice-re-saved q90)

recover: every history against the master, as saved and after jpegQS -q 3 and -q 6 (PSNR, Butteraugli
3-norm, SSIMULACRA2, ꟻLIP at 96 ppd). Does a one-time q80 become better than a re-saved "q90" once both
are restored?

keep: the large file H is a JPEG with one of the histories; the small copy L (factor 2 or 3, Pillow
Lanczos from the master) is PNG, JPEG q95/q85/q75, a twice-saved q85, or a q85 thumbnail made from the
q90 upload. Ground truth at the small size: errH = distance(H shrunk, true small), errL = distance(L, true
small) (Butteraugli 3-norm; ꟻLIP at 96/k ppd), also after jpegQS. What the user can see: DOWN_MATCHED
(L against H shrunk, both at L's size) and the centred whole-number NN view (H at its size against L
enlarged k x with nearest neighbour), where the visible damage of each side is ꟻLIP(H, master) and
ꟻLIP(NN(L), NN(true small)) at 96 ppd.
"""
import argparse
import io
import os
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np
import pandas as pd
from PIL import Image

import fi
import metrics as M
import resample as R
import study as S
from paths import RESULTS, TESTSET

JPEGQS = os.environ.get('JPEGQS') or 'jpegqs'
IMAGES = [('large', 'synth_lineart'), ('large', 'synth_flatcolor'), ('large', 'synth_manga'), ('large', 'synth_painterly'),
          ('large_real', 'real_peppercarrot_cover'), ('large_real', 'real_peppercarrot_witches'),
          ('large_real', 'real_krita_anime_banner'), ('large_real', 'real_hokusai_hodogaya'), ('large_real', 'real_lion_appel')]
HISTORIES = {
    'q95': [(95, 0)], 'q90': [(90, 0)], 'q85': [(85, 0)], 'q80': [(80, 0)], 'q70': [(70, 0)],
    'q75>q90': [(75, 0), (90, 0)], 'q60>q90': [(60, 0), (90, 0)], 'q80s>q90': [(80, 3), (90, 0)],
    'q85s>q85': [(85, 4), (85, 0)], 'q90s>q90s>q90': [(90, 3), (90, 5), (90, 0)],
}
KEEP_H = ['q95', 'q90', 'q80', 'q70', 'q75>q90', 'q90s>q90s>q90']
KEEP_L = ['png', 'q95', 'q85', 'q75', 'q85s>q85', 'thumb_of_q90']
BORDER = 8   # left out of every measure (shifted saves leave the outermost pixels from an earlier save)


def load(folder, name):
    return np.asarray(Image.open(os.path.join(TESTSET, folder, f'{name}.png')).convert('RGB'))


def jpeg_bytes(img, q):
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, 'JPEG', quality=q, subsampling=2)
    return buf.getvalue()


def decode(b):
    return np.asarray(Image.open(io.BytesIO(b)).convert('RGB'))


def chain(img, steps):
    """Apply the saves in order; returns the decoded picture and the bytes of the last (whole-picture) JPEG."""
    cur, last = img, None
    for q, s in steps:
        if s:
            cur = cur.copy()
            cur[s:, s:] = decode(jpeg_bytes(np.ascontiguousarray(cur[s:, s:]), q))
            last = None
        else:
            last = jpeg_bytes(cur, q)
            cur = decode(last)
    return cur, last


def jpegqs(b, level):
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, 'a.jpg'), os.path.join(d, 'b.jpg')
        open(src, 'wb').write(b)
        subprocess.run([JPEGQS, '-q', str(level), '-i', '0', '-t', '1', src, dst], check=True, capture_output=True)
        return decode(open(dst, 'rb').read())


def inner(a, k=1):
    b = max(1, int(BORDER // k))
    return np.ascontiguousarray(a[b:-b, b:-b])


def full_metrics(ref, test, prefix=''):
    r, t = inner(ref), inner(test)
    out = {'psnr': M.psnr(r, t)}
    out.update(M.butteraugli(r, t))
    out.update(M.ssimulacra2(r, t))
    f, _ = M.flip(r, t, 96)
    out['flip96'] = f['flip_mean']
    return {prefix + k: v for k, v in out.items()}


# ------------------------------------------------------------------ recover

def task_recover(args):
    folder, name = args
    Mst = load(folder, name)
    rows = []
    for hname, steps in HISTORIES.items():
        X, last = chain(Mst, steps)
        row = dict(image=name, set='real' if name.startswith('real') else 'synth', history=hname,
                   last_q=steps[-1][0], saves=len(steps))
        row.update(full_metrics(Mst, X, 'raw_'))
        for lv in (3, 6):
            Y = jpegqs(last, lv)
            row.update(full_metrics(Mst, Y, f'qs{lv}_'))
            row[f'qs{lv}_change'] = float(np.abs(Y.astype(np.int16) - X.astype(np.int16)).mean())
        rows.append(row)
    return rows


# ------------------------------------------------------------------ keep

def small_metrics(T, X, k, prefix):
    t, x = inner(T, k), inner(X, k)
    out = {}
    out.update({prefix + kk: v for kk, v in M.butteraugli(t, x).items()})
    f, _ = M.flip(t, x, 96.0 / k)
    out[prefix + 'flipz'] = f['flip_mean']
    return out


def task_keep(args):
    folder, name, k = args
    Mst = load(folder, name)
    H, W = Mst.shape[:2]
    w, h = R.small_size(W, H, k)
    shrink = lambda img: R.SHRINKERS['pil_lanczos'](img, w, h)
    T = shrink(Mst)
    # large copies (as saved and restored)
    Hs = {}
    for hn in KEEP_H:
        X, last = chain(Mst, HISTORIES[hn])
        Hs[hn] = X
        Hs[hn + '+qs6'] = jpegqs(last, 6)
    # small copies
    Ls = {'png': T}
    for q in (95, 85, 75):
        b = jpeg_bytes(T, q)
        Ls[f'q{q}'] = decode(b)
        Ls[f'q{q}+qs6'] = jpegqs(b, 6)
    X, last = chain(T, HISTORIES['q85s>q85'])
    Ls['q85s>q85'], Ls['q85s>q85+qs6'] = X, jpegqs(last, 6)
    b = jpeg_bytes(shrink(Hs['q90']), 85)
    Ls['thumb_of_q90'], Ls['thumb_of_q90+qs6'] = decode(b), jpegqs(b, 6)
    rows = []
    # per-copy ground truth and the visible damage in the centred whole-number NN view
    gt = {}
    kk = int(k) if float(k).is_integer() else int(np.floor(k))
    for hn, X in Hs.items():
        g = small_metrics(T, shrink(X), k, 'small_')
        f, _ = M.flip(inner(Mst), inner(X), 96)
        g['nnview_flip96'] = f['flip_mean']
        gt[('H', hn)] = g
    NT = R.nn_int(T, kk)
    for ln, X in Ls.items():
        g = small_metrics(T, X, k, 'small_')
        f, _ = M.flip(inner(NT), inner(R.nn_int(X, kk)), 96)
        g['nnview_flip96'] = f['flip_mean']
        gt[('L', ln)] = g
    for (side, cn), g in gt.items():
        rows.append(dict(kind='copy', image=name, factor=k, side=side, copy=cn, **g))
    # what DOWN_MATCHED shows for each pair (L against H shrunk with the matched filter). Its candidates
    # (FreeImage's five kernels on the 8-bit path, then exact area averaging) are made once per large copy;
    # the pick is study.down_strategies' rule: lowest mean absolute difference, the first kernel wins a tie,
    # area only when strictly better.
    cands = {hk: [(kn, fi.rescale(X, w, h, kn)) for kn in S.MATCH8] + [('area', R.SHRINKERS['area'](X, w, h))]
             for hk, X in Hs.items()}
    for hn in KEEP_H:
        for ln in KEEP_L:
            for restored in ('', '+qs6'):
                hk, lk = hn + restored, ln + (restored if ln != 'png' else '')
                Lx = Ls[lk].astype(np.int16)
                kern, D, best = None, None, None
                for kn, C in cands[hk]:
                    err = np.abs(C.astype(np.int16) - Lx).mean()
                    if best is None or err < best:
                        kern, D, best = kn, C, err
                out, _ = M.cheap_panel(D, Ls[lk])
                rows.append(dict(kind='pair', image=name, factor=k, H=hk, L=lk, restored=bool(restored),
                                 kernel=kern, T_p99=out['T_p99'], share_T4=out['share_T4'],
                                 share_T8=out['share_T8'], share_T16=out['share_T16'], share_T32=out['share_T32']))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('part', choices=['recover', 'keep'])
    ap.add_argument('--jobs', type=int, default=4)
    a = ap.parse_args()
    out = os.path.join(RESULTS, f'compression_{a.part}.csv')
    if a.part == 'recover':
        tasks, fn = [(fo, n) for fo, n in IMAGES], task_recover
        if os.path.exists(out):
            os.remove(out)
    else:
        tasks, fn = [(fo, n, k) for fo, n in IMAGES for k in (2, 3)], task_keep
        if os.path.exists(out):   # resumable: skip (image, factor) already written
            prev = pd.read_csv(out)
            done = set(zip(prev.image, prev.factor))
            tasks = [t for t in tasks if (t[1], t[2]) not in done]
    print(f'{len(tasks)} tasks to run', flush=True)
    # a worker that dies makes the pool raise instead of waiting forever; rows are written as tasks finish
    with ProcessPoolExecutor(a.jobs) as pool:
        futs = [pool.submit(fn, t) for t in tasks]
        for i, fu in enumerate(as_completed(futs)):
            df = pd.DataFrame(fu.result())
            df.to_csv(out, mode='a', header=not os.path.exists(out), index=False)
            print(f'{i + 1}/{len(tasks)}', flush=True)
    print('wrote', out, len(pd.read_csv(out)))


if __name__ == '__main__':
    main()
