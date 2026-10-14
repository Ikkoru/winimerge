"""Metrics for "how close is the enlarged copy to the large original".

Cheap metrics (numpy/OpenCV): WinMerge's own block outcome, PSNR, worst-block colour
difference, worst-tile SSIM. Expensive ones (subprocess / C++): FLIP, Butteraugli, SSIMULACRA2.
All inputs are uint8 RGB arrays of identical shape; an optional `valid` mask (H, W) marks pixels
that exist in both images (pixels outside count as different, as in WinMerge).
"""
import os
import subprocess
import tempfile

import cv2
import numpy as np

LIBJXL_TOOLS = os.environ.get('LIBJXL_TOOLS', '')
THRESHOLDS = (0, 2, 4, 8, 16, 32, 64)


def color_distance(a, b):
    """Euclidean RGB distance per pixel in 0..255 units (WinMerge's colour distance; alpha equal)."""
    d = a.astype(np.int32) - b.astype(np.int32)
    return np.sqrt((d * d).sum(axis=2).astype(np.float32))


def block_reduce(m, block=8, how='max'):
    h, w = m.shape
    nby, nbx = -(-h // block), -(-w // block)
    pad = np.full((nby * block, nbx * block), np.nan, np.float32)
    pad[:h, :w] = m
    r = pad.reshape(nby, block, nbx, block)
    return np.nanmax(r, axis=(1, 3)) if how == 'max' else np.nanmean(r, axis=(1, 3))


def block_max_distance(a, b, valid=None, block=8):
    d = color_distance(a, b)
    if valid is not None:
        d = np.where(valid, d, np.inf).astype(np.float32)
    return block_reduce(d, block, 'max')


def block_outcome(bm, thresholds=THRESHOLDS):
    """Share of blocks WinMerge marks (distance > T) and number of 8-connected regions, per T."""
    out = {}
    n = bm.size
    for t in thresholds:
        marked = bm > t
        out[f'share_T{t}'] = float(marked.sum()) / n
        if t in (8, 16, 32):
            k, _ = cv2.connectedComponents(marked.astype(np.uint8), connectivity=8)
            out[f'regions_T{t}'] = int(k - 1)
    # thresholds that would leave at most 1 % / 0.1 % of blocks marked (inf: missing area, never clean)
    capped = np.where(np.isfinite(bm), bm, 1e9)
    for key, q in (('T_p99', 99), ('T_p999', 99.9), ('blockmax_median', 50)):
        v = float(np.percentile(capped, q))
        out[key] = float('inf') if v >= 1e9 else v
    out['T_max'] = float(bm.max())
    return out


def psnr(a, b):
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return float('inf') if mse == 0 else 10 * np.log10(255.0 ** 2 / mse)


def worst_block_mean(a, b, block=8):
    return float(np.nanmax(block_reduce(color_distance(a, b), block, 'mean')))


def ssim_map(a, b):
    from skimage.metrics import structural_similarity
    ga = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    gb = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    s, m = structural_similarity(ga, gb, data_range=255, full=True, gaussian_weights=True, sigma=1.5,
                                 use_sample_covariance=False)
    return float(s), m


def ssim_worst_tile(a, b, tile=64):
    s, m = ssim_map(a, b)
    t = block_reduce(m.astype(np.float32), tile, 'mean')
    return s, float(np.nanmin(t))


def cheap_panel(ref, test, valid=None, prefix='', ssim=False):
    bm = block_max_distance(ref, test, valid)
    out = {prefix + k: v for k, v in block_outcome(bm).items()}
    if valid is None:
        out[prefix + 'psnr'] = psnr(ref, test)
        out[prefix + 'worst_block_mean'] = worst_block_mean(ref, test)
        if ssim:
            s, w = ssim_worst_tile(ref, test)
            out[prefix + 'ssim'] = s
            out[prefix + 'ssim_worst64'] = w
    return out, bm


# ------------------------------------------------------------------ expensive metrics

def flip(ref, test, ppd):
    import flip_evaluator as fl
    r = ref.astype(np.float32) / 255.0
    t = test.astype(np.float32) / 255.0
    m, mean, _ = fl.evaluate(r, t, 'LDR', inputsRGB=True, applyMagma=False, parameters={'ppd': float(ppd)})
    m = m[..., 0] if m.ndim == 3 else m
    return {'flip_mean': float(mean), 'flip_p95': float(np.percentile(m, 95)),
            'flip_p99': float(np.percentile(m, 99)), 'flip_max': float(m.max())}, m


def _write_png(path, arr):
    cv2.imwrite(path, cv2.cvtColor(arr, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_PNG_COMPRESSION, 1])


def butteraugli(ref, test):
    tool = os.path.join(LIBJXL_TOOLS, 'butteraugli_main')
    with tempfile.TemporaryDirectory() as d:
        pa, pb = os.path.join(d, 'a.png'), os.path.join(d, 'b.png')
        _write_png(pa, ref)
        _write_png(pb, test)
        r = subprocess.run([tool, pa, pb, '--pnorm', '3'], capture_output=True, text=True, timeout=600)
    lines = [l for l in r.stdout.strip().splitlines() if l.strip()]
    mx = float(lines[0])
    pn = float(lines[1].split(':')[1])
    return {'ba_max': mx, 'ba_p3': pn}


def ssimulacra2(ref, test):
    tool = os.path.join(LIBJXL_TOOLS, 'ssimulacra2')
    with tempfile.TemporaryDirectory() as d:
        pa, pb = os.path.join(d, 'a.png'), os.path.join(d, 'b.png')
        _write_png(pa, ref)
        _write_png(pb, test)
        r = subprocess.run([tool, pa, pb], capture_output=True, text=True, timeout=600)
    return {'ssimu2': float(r.stdout.strip().splitlines()[-1])}


def heavy_panel(ref, test, ppds=(96, 48)):
    out = {}
    for p in ppds:
        f, _ = flip(ref, test, p)
        out.update({f'{k}_ppd{p}': v for k, v in f.items()})
    out.update(butteraugli(ref, test))
    out.update(ssimulacra2(ref, test))
    return out


def self_test():
    """Controls that must return 'identical' before any other number is trusted."""
    rng = np.random.default_rng(0)
    a = (rng.random((256, 320, 3)) * 255).astype(np.uint8)
    bm = block_max_distance(a, a)
    assert bm.max() == 0, 'block distance of an image with itself must be 0'
    assert psnr(a, a) == float('inf')
    h = heavy_panel(a, a, ppds=(96,))
    assert h['flip_mean_ppd96'] == 0.0, h
    assert h['ba_max'] < 1e-6, h
    assert h['ssimu2'] > 99.9, h
    s, w = ssim_worst_tile(a, a)
    assert abs(s - 1) < 1e-9 and abs(w - 1) < 1e-6
    return h


if __name__ == '__main__':
    print('self test (image vs itself):', self_test())
