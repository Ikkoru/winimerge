"""Build eye-check page 2 (after the user's first round): blind tiny-edit trials, a compression section
(which copy is cleaner?) and a filters-only section (PNG copies, no compression).

    python3 eyecheck2.py [--out ../eyecheck2]

Writes OUT/index.html (self-contained; opens from disk) and OUT/artifact.html (the same page without the
document skeleton, for publishing as a claude.ai artifact), plus OUT/truth.json.

Changes asked for after round 1:
- blind: each trial shows one pair through one method, labelled only "Trial n"; whether there is an
  edit, the method and the scale are hidden until "Show results". Every method gets the same mix of
  edits (a no-edit trial, a 1-px dot on a flat spot, a small dot or hairline on a busy spot, a larger
  half-contrast dot, a faint dot or hairline on a flat spot), each on a different picture, so finding an
  edit in one trial does not give away another.
- no view compares a picture with itself, and views that would show identical pixels are merged.
- Catmull-Rom sits next to Lanczos3; the filters-only section uses PNG copies only.
- compression: your centred whole-number NN view (crop at the picture's centre) next to the matched
  shrink, as saved and after jpegQS.
- WinMerge's own views: manual flip (space), XOR as WinMerge computes it (bitwise, per channel), and an
  overlay of the 8x8 blocks WinMerge would mark at a chosen threshold.
"""
import argparse
import base64
import hashlib
import io
import json
import math
import os

import cv2
import numpy as np
from PIL import Image

import compression_test as C
import fi
import metrics as M
import resample as R
import study as S
import tiny_edits as TE
from paths import ROOT, TESTSET

CROP = 192
REAL = lambda n: n.startswith('real_')


def load(name):
    folder = 'large_real' if REAL(name) else 'large'
    return np.asarray(Image.open(os.path.join(TESTSET, folder, f'{name}.png')).convert('RGB'))


class Store:
    """PNG crops as data URIs, de-duplicated by content."""
    def __init__(self):
        self.imgs = {}

    def put(self, arr):
        arr = np.ascontiguousarray(arr)
        key = hashlib.sha1(arr.tobytes() + str(arr.shape).encode()).hexdigest()[:12]
        if key not in self.imgs:
            buf = io.BytesIO()
            Image.fromarray(arr).save(buf, 'PNG', optimize=True)
            self.imgs[key] = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
        return key


def place_nn_int(Sm, W, H):
    U, _ = S.up_nn_int(Sm, W, H, 'center')
    return U


# ------------------------------------------------------------------ blind tiny-edit trials

BLIND_METHODS = ['small', 'rt_l3', 'up_l3', 'up_cr', 'up_nn_int']
METHOD_LABEL = {'small': 'Shrink the large file to the copy\'s size (DOWN_MATCHED), shown zoomed',
                'rt_l3': 'Round trip: both shrunk-and-matched, then enlarged with Lanczos3',
                'up_l3': 'Enlarge the copy with Lanczos3 (UP_SMOOTH)',
                'up_cr': 'Enlarge the copy with Catmull-Rom',
                'up_nn_int': 'Enlarge the copy with whole-number NN, centred'}
BUNDLES = [['none'], ['dot1_full_flat'], ['dot2_full_busy', 'hair_busy'], ['dot4_half_busy', 'dot6_half_busy'],
           ['dot2_half_flat', 'hair_flat']]
BLIND_IMAGES = ['synth_lineart', 'synth_manga', 'synth_flatcolor', 'synth_text_ui', 'synth_painterly',
                'real_peppercarrot_cover', 'real_peppercarrot_witches', 'real_krita_anime_banner', 'real_lion_appel',
                'real_kitty_screenshot', 'real_hokusai_hodogaya']
EDIT_SPEC = {e[0]: e for e in TE.EDITS}


def edit_spot_center(L, ename, salt):
    if ename == 'none':
        return None
    _, kind, size, contrast, place = EDIT_SPEC[ename]
    L1, mask = TE.make_edit(L, kind, size, contrast, place, salt)
    ys, xs = np.where(mask)
    return L1, mask, (int(round(xs.mean())), int(round(ys.mean())))


def blind_trials(store, seed=2026):
    rng = np.random.default_rng(seed)
    trials = []
    combos = [(m, b) for b in range(len(BUNDLES)) for m in BLIND_METHODS]
    images = list(rng.permutation(BLIND_IMAGES))
    for i, (method, b) in enumerate(combos):
        name = images[i % len(images)]
        f = int(rng.choice([2, 3, 4]))
        scen = str(rng.choice(['png', 'jpg85', 'big90_png']))
        ename = str(rng.choice(BUNDLES[b]))
        direction = str(rng.choice(['in_small', 'in_large']))
        L0 = load(name)
        H, W = L0.shape[:2]
        w, h = R.small_size(W, H, f)
        small_codec = {'png': 'png', 'jpg85': 'jpg85', 'big90_png': 'png'}[scen]
        small_of = lambda img: S.codec(R.SHRINKERS['pil_lanczos'](img, w, h), small_codec)
        large_of = lambda img: S.codec(img, 'jpg90') if scen == 'big90_png' else img
        salt = 500 + i
        if ename == 'none':
            # crop where an edit of this kind would go, so a crop position gives nothing away
            ref = str(rng.choice([e for bb in BUNDLES[1:] for e in bb]))
            _, _, (cx, cy) = edit_spot_center(L0, ref, salt)
            L1 = L0
        else:
            L1, mask, (cx, cy) = edit_spot_center(L0, ename, salt)
        A = large_of(L1 if direction == 'in_large' else L0)
        Sm = small_of(L1 if direction == 'in_small' else L0)
        downs, kk = S.down_strategies(A, Sm, 'pil_lanczos')
        D = downs['down_matched8a']
        off_x, off_y = int(rng.integers(48, 145)), int(rng.integers(48, 145))
        x0 = int(np.clip((cx - off_x) // 12 * 12, 0, (W - CROP) // 12 * 12))
        y0 = int(np.clip((cy - off_y) // 12 * 12, 0, (H - CROP) // 12 * 12))
        if method == 'small':
            s0x, s0y, sc = x0 // f, y0 // f, CROP // f
            a, b_ = D[s0y:s0y + sc, s0x:s0x + sc], Sm[s0y:s0y + sc, s0x:s0x + sc]
            scale = f
        else:
            if method == 'rt_l3':
                full_a, full_b = fi.rescale(D, W, H, 'lanczos3'), fi.rescale(Sm, W, H, 'lanczos3')
            elif method == 'up_l3':
                full_a, full_b = A, fi.rescale(Sm, W, H, 'lanczos3')
            elif method == 'up_cr':
                full_a, full_b = A, fi.rescale(Sm, W, H, 'catmullrom')
            else:
                full_a, full_b = A, place_nn_int(Sm, W, H)
            a, b_ = full_a[y0:y0 + CROP, x0:x0 + CROP], full_b[y0:y0 + CROP, x0:x0 + CROP]
            scale = 1
        trials.append(dict(a=store.put(a), b=store.put(b_), scale=scale,
                           truth=dict(method=method, method_label=METHOD_LABEL[method], edit=ename,
                                      present=ename != 'none', x=cx - x0, y=cy - y0, image=name, factor=f,
                                      scenario=scen, direction=direction, kernel=kk['down_matched8a'])))
    order = rng.permutation(len(trials))
    trials = [trials[j] for j in order]
    for n, t in enumerate(trials):
        t['id'] = f't{n + 1:02d}'
    return trials


# ------------------------------------------------------------------ compression cases

COMP_CASES = [
    ('synth_painterly', 2, 'q90', 'png'), ('real_lion_appel', 2, 'q70', 'png'),
    ('real_peppercarrot_cover', 3, 'q90s>q90s>q90', 'png'), ('real_krita_anime_banner', 2.5, 'q90', 'q85'),
    ('synth_manga', 2, 'q80', 'q95'), ('real_hokusai_hodogaya', 3, 'q75>q90', 'q85'),
    ('real_peppercarrot_witches', 2.5, 'q95', 'thumb_of_q90'), ('synth_lineart', 2, 'q90s>q90s>q90', 'q75'),
]


def comp_cases(store):
    out = []
    for i, (name, f, hist, lname) in enumerate(COMP_CASES):
        Mst = load(name)
        H, W = Mst.shape[:2]
        w, h = R.small_size(W, H, f)
        shrink = lambda img: R.SHRINKERS['pil_lanczos'](img, w, h)
        T = shrink(Mst)
        Hx, hlast = C.chain(Mst, C.HISTORIES[hist])
        Hq = C.jpegqs(hlast, 6)
        if lname == 'png':
            Lx, Lq = T, T
        elif lname == 'thumb_of_q90':
            hb = C.jpeg_bytes(shrink(C.chain(Mst, C.HISTORIES['q90'])[0]), 85)
            Lx, Lq = C.decode(hb), C.jpegqs(hb, 6)
        else:
            lb = C.jpeg_bytes(T, int(lname[1:]))
            Lx, Lq = C.decode(lb), C.jpegqs(lb, 6)
        k = int(math.floor(f))
        x0, y0 = (W - CROP) // 2 // 12 * 12, (H - CROP) // 2 // 12 * 12
        views = []
        for tag, Hv, Lv in (('', Hx, Lx), ('_qs', Hq, Lq)):
            NN = place_nn_int(Lv, W, H)
            views.append(dict(key='nn_center' + tag, a=store.put(Hv[y0:y0 + CROP, x0:x0 + CROP]),
                              b=store.put(NN[y0:y0 + CROP, x0:x0 + CROP]), scale=1,
                              label='Whole-number NN ×%d, centred' % k + (' (both restored with jpegQS)' if tag else '')))
            downs, kk = S.down_strategies(Hv, Lv, 'pil_lanczos')
            D = downs['down_matched8a']
            sc = int(round(CROP / f))
            s0x, s0y = (w - sc) // 2, (h - sc) // 2
            views.append(dict(key='small' + tag, a=store.put(D[s0y:s0y + sc, s0x:s0x + sc]),
                              b=store.put(Lv[s0y:s0y + sc, s0x:s0x + sc]), scale=int(math.ceil(f)),
                              label='Large file shrunk to the copy\'s size (matched), shown zoomed'
                                    + (' (both restored with jpegQS)' if tag else '')))
        # ground truth at the copy's size: Butteraugli 3-norm of each side against the true small image
        def err(X):
            b = M.butteraugli(C.inner(T, f), C.inner(X, f))
            return b['ba_p3'], b['ba_max']
        el, es, elq, esq = err(shrink(Hx)), err(Lx), err(shrink(Hq)), err(Lq)
        truth = dict(image=name, factor=f, large=hist, small=lname,
                     err_large=el[0], err_small=es[0], err_large_qs=elq[0], err_small_qs=esq[0],
                     max_large=el[1], max_small=es[1], max_large_qs=elq[1], max_small_qs=esq[1],
                     err_large_full=M.butteraugli(C.inner(Mst), C.inner(Hx))['ba_p3'])
        out.append(dict(id=f'c{i + 1}', views=views, truth=truth))
    return out


# ------------------------------------------------------------------ filters only (PNG copies)

FILTER_CASES = [('synth_lineart', 'pil_lanczos', 2), ('synth_manga', 'area', 2.5), ('real_krita_anime_banner', 'pil_lanczos', 3),
                ('real_peppercarrot_cover', 'vips', 2), ('real_lion_appel', 'pil_bicubic', 2.5), ('real_kitty_screenshot', 'pil_lanczos', 3)]
FILTER_VIEWS = [('nn_int', 'Nearest neighbour, whole-number factor'), ('nn', 'Nearest neighbour to the exact size'),
                ('bilinear', 'Bilinear'), ('catmullrom', 'Catmull-Rom'), ('lanczos3', 'Lanczos3 (UP_SMOOTH)'),
                ('lanczos3_usm', 'Lanczos3 + unsharp mask σ1 px 50 %'), ('small', 'Shrink the large file instead (DOWN_MATCHED), zoomed'),
                ('rt_l3', 'Round trip (shrink matched, then both enlarged with Lanczos3)')]


def busy_window(L, size=CROP):
    g = cv2.cvtColor(L, cv2.COLOR_RGB2GRAY).astype(np.float32)
    H, W = g.shape
    best, bs = (0, 0), -1
    for y in range(0, H - size, 36):
        for x in range(0, W - size, 36):
            s = g[y:y + size, x:x + size].std()
            if s > bs:
                best, bs = (x, y), s
    return best[0] // 12 * 12, best[1] // 12 * 12


def filter_cases(store):
    out = []
    for i, (name, shr, f) in enumerate(FILTER_CASES):
        L = load(name)
        H, W = L.shape[:2]
        w, h = R.small_size(W, H, f)
        Sm = R.SHRINKERS[shr](L, w, h)
        x0, y0 = busy_window(L)
        crop = lambda X: X[y0:y0 + CROP, x0:x0 + CROP]
        downs, kk = S.down_strategies(L, Sm, shr)
        D = downs['down_matched8a']
        full = {'nn': R.nn_exact(Sm, W, H), 'bilinear': fi.rescale(Sm, W, H, 'bilinear'),
                'catmullrom': fi.rescale(Sm, W, H, 'catmullrom'), 'lanczos3': fi.rescale(Sm, W, H, 'lanczos3'),
                'lanczos3_usm': R.unsharp(fi.rescale(Sm, W, H, 'lanczos3', float_path=True), 1.0, 0.5)}
        if float(f).is_integer():
            full['nn_int'] = place_nn_int(Sm, W, H)
        views, seen = [], {}
        for key, label in FILTER_VIEWS:
            if key == 'small':
                sc = int(round(CROP / f))
                s0x, s0y = int(round(x0 / f)), int(round(y0 / f))
                a, b_, scale = D[s0y:s0y + sc, s0x:s0x + sc], Sm[s0y:s0y + sc, s0x:s0x + sc], int(math.ceil(f))
            elif key == 'rt_l3':
                a, b_, scale = crop(fi.rescale(D, W, H, 'lanczos3')), crop(full['lanczos3']), 1
            elif key in full:
                a, b_, scale = crop(L), crop(full[key]), 1
            else:
                continue
            ka, kb = store.put(a), store.put(b_)
            if (ka, kb) in seen:   # identical pixels to an earlier view: merge the labels
                seen[(ka, kb)]['label'] += ' = ' + label
                continue
            v = dict(key=key, a=ka, b=kb, scale=scale, label=label)
            seen[(ka, kb)] = v
            views.append(v)
        out.append(dict(id=f'f{i + 1}', desc=f'{name}, copy made with {shr} at 1/{f}, PNG', views=views,
                        kernel=kk['down_matched8a']))
    return out


def credits(names):
    import html
    try:
        man = json.load(open(os.path.join(TESTSET, 'sources', 'MANIFEST.json')))
        crops = json.load(open(os.path.join(TESTSET, 'real', 'CROPS.json')))
    except (OSError, ValueError):
        return ''
    by_file = {e['file']: e for e in man['images']}
    lines = []
    for name in sorted(n for n in names if REAL(n)):
        e = by_file.get(crops.get(name + '.png', {}).get('source'))
        if e:
            lines.append(f'<li>{html.escape(e["attribution"])} ({html.escape(e["license"])}). Cropped, resized, '
                         'recompressed and partly edited for this test.</li>')
    return ('<p>Synthetic pictures are generated by the study harness. Real pictures:</p><ul>' + ''.join(lines) + '</ul>'
            if lines else '')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, 'eyecheck2'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    store = Store()
    trials = blind_trials(store)
    comp = comp_cases(store)
    filt = filter_cases(store)
    data = dict(imgs=store.imgs, trials=[{k: v for k, v in t.items()} for t in trials], comp=comp, filt=filt)
    names = {t['truth']['image'] for t in trials} | {c['truth']['image'] for c in comp} | {n for n, _, _ in FILTER_CASES}
    page = PAGE.replace('/*DATA*/', json.dumps(data)).replace('<!--CREDITS-->', credits(names))
    with open(os.path.join(a.out, 'artifact.html'), 'w') as fh:
        fh.write(page)
    with open(os.path.join(a.out, 'index.html'), 'w') as fh:
        fh.write('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                 '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                 '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}'
                 'body{margin:0;font:14px system-ui,sans-serif}[hidden]{display:none!important}</style>\n'
                 + page.replace('<meta name="claude:viewport-fit-sides" content="cover">', '') + '\n</html>\n')
    truth = dict(trials=[dict(id=t['id'], **t['truth']) for t in trials], comp=[dict(id=c['id'], **c['truth']) for c in comp])
    json.dump(truth, open(os.path.join(a.out, 'truth.json'), 'w'), indent=1)
    size = os.path.getsize(os.path.join(a.out, 'artifact.html'))
    print('wrote', a.out, f'{size / 1e6:.1f} MB,', len(store.imgs), 'images')


PAGE = r'''<title>Flip Check, Round 2</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700&family=Source+Sans+3:wght@400;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: a lab bench. Controls on top, one large neutral-grey stage for the pair, marks and notes below. */
:root {
  --paper: #f3f4f1; --ink: #1d2124; --quiet: #5b6366; --rule: #d3d7d2; --raised: #ffffff;
  --stage: #808080;             /* neutral 50 % grey: the surround must not bias the grey levels */
  --accent: #1d6a73; --accent-ink: #ffffff; --wm-mark: rgba(255, 210, 0, 0.45); --hit: #2f7d32; --miss: #b23b2e;
  --f-display: "Bricolage Grotesque", "Segoe UI", system-ui, sans-serif;
  --f-body: "Source Sans 3", "Segoe UI", system-ui, sans-serif;
  --f-mono: "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --paper: #16191b; --ink: #e5e8e4; --quiet: #9aa4a6; --rule: #2d3336; --raised: #1f2427;
  --accent: #66b3bc; --accent-ink: #0d1416; --hit: #7cc47f; --miss: #f08a7c; color-scheme: dark } }
:root[data-theme="dark"] {
  --paper: #16191b; --ink: #e5e8e4; --quiet: #9aa4a6; --rule: #2d3336; --raised: #1f2427;
  --accent: #66b3bc; --accent-ink: #0d1416; --hit: #7cc47f; --miss: #f08a7c; color-scheme: dark }
body { background: var(--paper); color: var(--ink); font: 16px/1.5 var(--f-body); }
main { max-width: 1100px; margin: 0 auto; padding-block: 20px 48px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: grid; gap: 18px; }
h1 { font: 700 clamp(1.6rem, 3.4vw, 2.3rem)/1.1 var(--f-display); margin: 0; text-wrap: balance; letter-spacing: -0.01em; }
h2 { font: 600 1.15rem/1.3 var(--f-display); margin: 0; }
p { margin: 0; max-width: 68ch; }
.lede { color: var(--quiet); }
nav.tabs { display: flex; flex-wrap: wrap; gap: 6px; border-bottom: 1px solid var(--rule); padding-bottom: 8px; }
button { font: 500 0.92rem/1.2 var(--f-body); color: var(--ink); background: var(--raised); border: 1px solid var(--rule);
  border-radius: 6px; padding: 7px 11px; cursor: pointer; }
button:hover { border-color: var(--accent); }
button:focus-visible, select:focus-visible, canvas:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
button.on, button[aria-pressed="true"] { background: var(--accent); color: var(--accent-ink); border-color: var(--accent); }
select { font: 0.95rem var(--f-body); padding: 6px 8px; border-radius: 6px; border: 1px solid var(--rule); background: var(--raised); color: var(--ink); max-width: 100%; min-width: 0; flex: 0 1 auto; }
.group { min-width: 0; max-width: 100%; }
.bar { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; }
.group { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.lbl { font: 500 0.75rem/1 var(--f-mono); letter-spacing: 0.06em; text-transform: uppercase; color: var(--quiet); }
.stage { background: var(--stage); border-radius: 8px; padding: 14px; overflow: auto; min-height: 240px; }
canvas { image-rendering: pixelated; display: block; margin: 0 auto; cursor: crosshair; max-width: none; }
main > * { min-width: 0; }
.marks > button { justify-self: start; }
.showing { font: 0.85rem var(--f-mono); color: var(--quiet); min-height: 1.3em; }
.marks { display: grid; gap: 10px; }
.note { font-size: 0.92rem; color: var(--quiet); }
code, .mono { font-family: var(--f-mono); font-size: 0.86em; }
table { border-collapse: collapse; font-size: 0.92rem; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--rule); vertical-align: top; }
th { font: 600 0.78rem var(--f-mono); letter-spacing: 0.04em; text-transform: uppercase; color: var(--quiet); }
.scroll { overflow-x: auto; }
.ok { color: var(--hit); font-weight: 600; } .bad { color: var(--miss); font-weight: 600; }
textarea { width: 100%; min-height: 6em; font: 0.8rem var(--f-mono); background: var(--raised); color: var(--ink); border: 1px solid var(--rule); border-radius: 6px; }
details summary { cursor: pointer; font-weight: 600; }
footer { font-size: 0.85rem; color: var(--quiet); display: grid; gap: 6px; }
footer ul { margin: 0; padding-left: 1.2em; }
</style>
<main>
<header style="display:grid;gap:8px">
  <h1>Flip Check, Round 2</h1>
  <p class="lede">Three tests from your review: spotting tiny edits without knowing the method, judging which copy carries more compression damage, and the filters alone on lossless copies. Space flips in manual mode, as in WinMerge.</p>
</header>
<nav class="tabs" aria-label="Sections">
  <button id="tab-blind" data-sec="blind">1 · Tiny edits (blind)</button>
  <button id="tab-comp" data-sec="comp">2 · Which copy is cleaner?</button>
  <button id="tab-filt" data-sec="filt">3 · Filters only (PNG copies)</button>
</nav>
<section id="intro" class="note"></section>
<div class="bar">
  <div class="group" id="nav"></div>
  <div class="group" id="views"></div>
</div>
<div class="bar">
  <span class="lbl">View</span><div class="group" id="modes"></div>
</div>
<div class="bar">
  <span class="lbl">Zoom</span><div class="group" id="zooms"></div>
  <span class="lbl">WinMerge marks</span><div class="group" id="thr"></div>
  <span class="lbl">Block size</span><div class="group" id="bsz"></div>
</div>
<div class="showing" id="showing" aria-live="polite"></div>
<div class="stage"><canvas id="cv" tabindex="0" aria-label="Image pair"></canvas></div>
<div class="marks" id="marks"></div>
<div id="results"></div>
<details><summary>Your marks (copy to send back)</summary>
  <div class="group" style="margin-top:8px"><button id="copy">Copy marks</button><span class="note" id="copied"></span></div>
  <textarea id="out" readonly aria-label="Marks as JSON"></textarea>
</details>
<footer>
  <p>Zoom uses nearest neighbour. On your BenQ RD280U at 85 cm one screen pixel is about 1/96 of a degree, so 2× zoom shows 48 image pixels per degree. Cross-fade uses WinMerge's timing (fade 20 %, hold 30 %, back 20 %, hold 30 % of a second). XOR is computed as WinMerge does it: each colour channel bitwise, so a 1-level step from 127 to 128 lights up fully. Marks shade the blocks WinMerge marks at the chosen colour-distance threshold and Diff Block Size (8 is WinMerge's default; when comparing at the smaller size, 8/k pixels, e.g. 4 for a half-size copy, give marks as fine as 8 pixels of the original). Marks are kept in this browser only.</p>
  <!--CREDITS-->
</footer>
</main>
<script>
const DATA = /*DATA*/;
const $ = id => document.getElementById(id);
const cv = $('cv'), ctx = cv.getContext('2d');
const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const MODES = [['manual', 'Manual (space)'], ['xor', 'XOR (WinMerge)'], ['diff', '|difference| × 4'], ['side', 'Side by side'],
  ['flip2', 'Flip 2 Hz'], ['flip4', 'Flip 4 Hz'], ['xfade', 'Cross-fade']];
const THRS = [['off', 'off'], ['0', '0'], ['2', '2'], ['4', '4'], ['8', '8'], ['16', '16'], ['32', '32'], ['64', '64']];
let st = { sec: 'blind', ti: 0, ci: 0, cv: 0, fi: 0, fv: 0, mode: 'manual', zoom: window.innerWidth < 560 ? 1 : 2, thr: 'off', bs: 8, showB: false };
let marks = {};
try { marks = JSON.parse(localStorage.getItem('flip2marks') || '{}'); } catch (e) { marks = {}; }
try { const s = JSON.parse(localStorage.getItem('flip2state') || 'null'); if (s) Object.assign(st, s, { showB: false }); } catch (e) {}
function persist() { try { localStorage.setItem('flip2marks', JSON.stringify(marks)); localStorage.setItem('flip2state', JSON.stringify(st)); } catch (e) {}
  $('out').value = JSON.stringify(marks, null, 1); }
const cache = {};
function img(key) { if (cache[key]) return cache[key]; const im = new Image(); const rec = { im, data: null };
  im.onload = () => { const c = document.createElement('canvas'); c.width = im.naturalWidth; c.height = im.naturalHeight;
    const x = c.getContext('2d'); x.drawImage(im, 0, 0); rec.data = x.getImageData(0, 0, c.width, c.height); draw(); };
  im.src = DATA.imgs[key]; cache[key] = rec; return rec; }
function cur() {
  if (st.sec === 'blind') { const t = DATA.trials[st.ti]; return { a: t.a, b: t.b, scale: t.scale, la: 'reference', lb: 'copy', key: t.id }; }
  if (st.sec === 'comp') { const c = DATA.comp[st.ci], v = c.views[st.cv]; return { a: v.a, b: v.b, scale: v.scale, la: 'large file', lb: 'small copy', key: c.id + '|' + v.key, label: v.label }; }
  const c = DATA.filt[st.fi], v = c.views[st.fv]; return { a: v.a, b: v.b, scale: v.scale, la: 'reference', lb: 'from the small copy', key: c.id + '|' + v.key, label: v.label }; }
function btns(el, list, curv, set) { el.innerHTML = ''; list.forEach(([k, l]) => { const b = document.createElement('button'); b.textContent = l;
  b.setAttribute('aria-pressed', String(k === curv)); b.onclick = () => { set(k); render(); }; el.appendChild(b); }); }
const t0 = performance.now();
function alphaAt(t) { const x = t % 1000; if (x < 200) return x / 200; if (x < 500) return 1; if (x < 700) return 1 - (x - 500) / 200; return 0; }
function blockMarks(A, B, thr, bs) { const w = A.width, h = A.height, out = [];
  for (let by = 0; by < h; by += bs) for (let bx = 0; bx < w; bx += bs) { let m = 0;
    for (let y = by; y < Math.min(by + bs, h); y++) for (let x = bx; x < Math.min(bx + bs, w); x++) { const i = (y * w + x) * 4;
      const d = (A.data[i] - B.data[i]) ** 2 + (A.data[i + 1] - B.data[i + 1]) ** 2 + (A.data[i + 2] - B.data[i + 2]) ** 2; if (d > m) m = d; }
    if (Math.sqrt(m) > thr) out.push([bx, by]); }
  return out; }
function draw(now) {
  const c = cur(), A = img(c.a), B = img(c.b);
  if (!A.data || !B.data) return;
  const w = A.data.width, h = A.data.height, s = c.scale * st.zoom, side = st.mode === 'side';
  const W = (side ? 2 * w + 4 : w) * s, H = h * s;
  if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
  ctx.imageSmoothingEnabled = false;
  const t = (now || performance.now()) - t0;
  let showB = st.showB, alpha = null, text;
  if (st.mode === 'flip2' || st.mode === 'flip4') { const hz = st.mode === 'flip2' ? 2 : 4; showB = Math.floor(t / (500 / hz)) % 2 === 1; }
  if (st.mode === 'xfade') alpha = reduce ? (st.showB ? 1 : 0) : alphaAt(t);
  if (st.mode === 'xor' || st.mode === 'diff') {
    const o = new ImageData(w, h);
    for (let i = 0; i < o.data.length; i += 4) { for (let j = 0; j < 3; j++) { const p = A.data.data[i + j], q = B.data.data[i + j];
      o.data[i + j] = st.mode === 'xor' ? (p ^ q) : Math.min(255, 4 * Math.abs(p - q)); } o.data[i + 3] = 255; }
    const tmp = document.createElement('canvas'); tmp.width = w; tmp.height = h; tmp.getContext('2d').putImageData(o, 0, 0);
    ctx.drawImage(tmp, 0, 0, w * s, h * s);
    text = (st.mode === 'xor' ? 'XOR' : '|difference| × 4') + ` of ${c.la} and ${c.lb}`;
  } else if (side) { ctx.fillStyle = '#808080'; ctx.fillRect(0, 0, W, H); ctx.drawImage(A.im, 0, 0, w * s, h * s); ctx.drawImage(B.im, (w + 4) * s, 0, w * s, h * s); text = `left: ${c.la} · right: ${c.lb}`; }
  else if (alpha !== null) { ctx.globalAlpha = 1; ctx.drawImage(A.im, 0, 0, w * s, h * s); ctx.globalAlpha = alpha; ctx.drawImage(B.im, 0, 0, w * s, h * s); ctx.globalAlpha = 1; text = `${c.la} → ${c.lb}: ${Math.round(alpha * 100)} %`; }
  else { ctx.drawImage((showB ? B : A).im, 0, 0, w * s, h * s); text = 'showing: ' + (showB ? c.lb : c.la); }
  if (st.thr !== 'off' && !side) { ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--wm-mark').trim() || 'rgba(255,210,0,.45)';
    blockMarks(A.data, B.data, +st.thr, st.bs).forEach(([x, y]) => ctx.fillRect(x * s, y * s, st.bs * s, st.bs * s)); text += ` · marks at threshold ${st.thr}, blocks of ${st.bs}`; }
  if (st.sec === 'blind') { const m = marks[c.key]; if (m && m.x != null) { ctx.strokeStyle = '#ff2fd6'; ctx.lineWidth = 2;
    const px = m.x / c.scale * s, py = m.y / c.scale * s; ctx.beginPath(); ctx.arc(px, py, 10, 0, 7); ctx.moveTo(px - 16, py); ctx.lineTo(px + 16, py); ctx.moveTo(px, py - 16); ctx.lineTo(px, py + 16); ctx.stroke(); } }
  $('showing').textContent = text;
  if (st.mode.startsWith('flip') || (st.mode === 'xfade' && !reduce)) requestAnimationFrame(draw);
}
function noteUse(k) { if (st.sec !== 'blind') return; const key = DATA.trials[st.ti].id; const m = marks[key] = marks[key] || {};
  m.used = m.used || []; if (!m.used.includes(k)) m.used.push(k); persist(); }
function markBtns(container, title, key, field, opts) {
  const row = document.createElement('div'); row.className = 'group'; const l = document.createElement('span'); l.className = 'lbl'; l.textContent = title; row.appendChild(l);
  opts.forEach(([v, t]) => { const b = document.createElement('button'); b.textContent = t; const m = marks[key] || {};
    b.setAttribute('aria-pressed', String(m[field] === v)); b.onclick = () => { marks[key] = Object.assign(marks[key] || {}, { [field]: v, t: Date.now() }); persist(); render(); }; row.appendChild(b); });
  container.appendChild(row); }
function intro() {
  const t = { blind: `Each trial is a reference and a copy compared one way, with or without one tiny edit somewhere in the crop. The method, the scale and whether there is an edit are hidden. Flip, decide, and if you see an edit click on it (a magenta cross marks your click). Each method gets the same mix of edits, on different pictures, so finding one edit tells you nothing about the next trial. Results appear when you ask for them.`,
    comp: `The large file and the small copy come from the same master; both may be lossy, with known save histories. Which one carries more compression damage at the copy's size (the size where a small copy has to earn its keep)? Judge in the matched-shrink view, zoomed, and in your centred whole-number NN view, as saved and after jpegQS. Your answer is kept per view, so answer the as-saved and the restored views separately: the restored answer is the one for deciding what to keep (you would keep the copies restored), the as-saved one says how the files arrived. The NN view shows each file's damage at its own resolution, which can point the other way. The truth (each side's damage at the copy's size, as saved and restored) appears when you ask for it. ← → step through the views and keep the side you are looking at.`,
    filt: `Lossless (PNG) copies, so only resampling differs. Each view shows the reference and the same small copy prepared one way; Catmull-Rom sits next to Lanczos3. Views that would show identical pixels are merged into one entry. Switching views (buttons or ← →) keeps the side you are looking at, so you can show "from the small copy" and step through the methods.` };
  $('intro').textContent = t[st.sec]; }
function render() {
  ['blind', 'comp', 'filt'].forEach(s => $('tab-' + s).setAttribute('aria-pressed', String(s === st.sec)));
  intro(); $('results').innerHTML = '';
  const nav = $('nav'), views = $('views'); nav.innerHTML = ''; views.innerHTML = '';
  const mk = $('marks'); mk.innerHTML = '';
  if (st.sec === 'blind') {
    const n = DATA.trials.length, t = DATA.trials[st.ti];
    const prev = document.createElement('button'); prev.textContent = '← Previous'; prev.disabled = st.ti === 0; prev.onclick = () => { st.ti--; st.showB = false; render(); };
    const lab = document.createElement('span'); lab.className = 'mono'; lab.textContent = `Trial ${st.ti + 1} of ${n}`;
    const next = document.createElement('button'); next.textContent = 'Next →'; next.disabled = st.ti === n - 1; next.onclick = () => { st.ti++; st.showB = false; render(); };
    nav.append(prev, lab, next);
    markBtns(mk, 'Edit?', t.id, 'edit', [['yes', 'yes, I see one'], ['unsure', 'not sure'], ['no', 'no edit']]);
    const m = marks[t.id] || {}; const p = document.createElement('p'); p.className = 'note';
    p.textContent = m.x != null ? `Clicked at (${Math.round(m.x)}, ${Math.round(m.y)}). Click again to move it.` : 'Click on the edit if you see one.'; mk.appendChild(p);
    const done = DATA.trials.filter(t => (marks[t.id] || {}).edit).length;
    const res = document.createElement('button'); res.textContent = `Show results (${done} of ${n} marked)`; res.onclick = showBlindResults; mk.appendChild(res);
  } else if (st.sec === 'comp') {
    const sel = document.createElement('select'); sel.id = 'compSel'; sel.setAttribute('aria-label', 'Case');
    DATA.comp.forEach((c, i) => { const o = document.createElement('option'); o.value = i; o.textContent = `Case ${i + 1}`; if (i === st.ci) o.selected = true; sel.appendChild(o); });
    sel.onchange = () => { st.ci = +sel.value; st.cv = 0; render(); }; nav.appendChild(sel);
    const c = DATA.comp[st.ci]; btns(views, c.views.map((v, i) => [i, v.label]), st.cv, k => { st.cv = k; });
    const v = c.views[st.cv];
    markBtns(mk, 'More damage in', c.id + '|' + v.key, 'worse', [['large', 'the large file'], ['same', 'about the same'], ['small', 'the small copy']]);
    const res = document.createElement('button'); res.textContent = 'Show the measured answer'; res.onclick = showCompResults; mk.appendChild(res);
  } else {
    const sel = document.createElement('select'); sel.id = 'filtSel'; sel.setAttribute('aria-label', 'Case');
    DATA.filt.forEach((c, i) => { const o = document.createElement('option'); o.value = i; o.textContent = c.desc; if (i === st.fi) o.selected = true; sel.appendChild(o); });
    sel.onchange = () => { st.fi = +sel.value; st.fv = 0; render(); }; nav.appendChild(sel);
    const c = DATA.filt[st.fi]; btns(views, c.views.map((v, i) => [i, v.label]), st.fv, k => { st.fv = k; });
    markBtns(mk, 'Spurious differences', c.id + '|' + c.views[st.fv].key, 'spur', [['none', 'none'], ['tiny', 'tiny'], ['clear', 'clear'], ['strong', 'strong']]);
  }
  btns($('modes'), MODES, st.mode, k => { st.mode = k; st.showB = false; noteUse(k); });
  btns($('zooms'), [[1, '1×'], [2, '2×'], [3, '3×'], [4, '4×']], st.zoom, k => { st.zoom = k; });
  btns($('thr'), THRS, st.thr, k => { st.thr = k; if (k !== 'off') noteUse('marks'); });
  btns($('bsz'), [[1, '1'], [2, '2'], [4, '4'], [8, '8'], [16, '16']], st.bs, k => { st.bs = k; });
  persist(); draw();
}
function showBlindResults() {
  const by = {}; const rows = [];
  DATA.trials.forEach(t => { const m = marks[t.id] || {}; const tr = TRUTH.trials[t.id];
    const said = m.edit || '—'; let verdict;
    if (tr.present) { const near = m.x != null && Math.hypot(m.x - tr.x, m.y - tr.y) <= 16;
      verdict = said === 'yes' ? (m.x == null ? 'hit (no click)' : near ? 'hit' : 'yes, wrong place') : 'missed'; }
    else verdict = said === 'yes' ? 'false alarm' : said === 'no' ? 'correct: no edit' : 'unsure';
    const b = by[tr.method] = by[tr.method] || { n: 0, edits: 0, hits: 0, fa: 0, label: tr.method_label }; b.n++;
    if (tr.present) { b.edits++; if (verdict.startsWith('hit')) b.hits++; } else if (verdict === 'false alarm') b.fa++;
    rows.push(`<tr><td>${t.id}</td><td>${tr.method_label}</td><td>${tr.present ? tr.edit : 'no edit'}</td><td>${tr.image}, 1/${tr.factor}, ${tr.scenario}, ${tr.direction}</td><td>${said}${(m.used || []).length ? ' · used ' + m.used.join(', ') : ''}</td><td class="${verdict.startsWith('hit') || verdict.startsWith('correct') ? 'ok' : verdict === 'unsure' ? '' : 'bad'}">${verdict}</td></tr>`); });
  const sum = Object.values(by).map(b => `<tr><td>${b.label}</td><td>${b.hits} of ${b.edits}</td><td>${b.fa}</td></tr>`).join('');
  $('results').innerHTML = `<h2>Results</h2><div class="scroll"><table><tr><th>Method</th><th>Edits found</th><th>False alarms</th></tr>${sum}</table></div>
    <div class="scroll"><table><tr><th>Trial</th><th>Method</th><th>Edit</th><th>Pair</th><th>Your mark</th><th>Verdict</th></tr>${rows.join('')}</table></div>`; }
function showCompResults() { const c = DATA.comp[st.ci], tr = TRUTH.comp[c.id];
  const side = (a, b) => a < b * 0.9 ? 'the large file is cleaner' : b < a * 0.9 ? 'the small copy is cleaner' : 'about the same';
  $('results').innerHTML = `<h2>Case ${st.ci + 1}: measured</h2><div class="scroll"><table>
   <tr><th></th><th>Large file</th><th>Small copy</th><th>Verdict at the copy's size</th></tr>
   <tr><td>How saved</td><td class="mono">${tr.large}</td><td class="mono">${tr.small}</td><td>${tr.image}, factor ${tr.factor}</td></tr>
   <tr><td>Damage at the copy's size, as saved: overall · worst spot</td><td>${tr.err_large.toFixed(2)} · ${tr.max_large.toFixed(2)}</td><td>${tr.err_small.toFixed(2)} · ${tr.max_small.toFixed(2)}</td><td>${side(tr.max_large, tr.max_small)}</td></tr>
   <tr><td>After jpegQS: overall · worst spot</td><td>${tr.err_large_qs.toFixed(2)} · ${tr.max_large_qs.toFixed(2)}</td><td>${tr.err_small_qs.toFixed(2)} · ${tr.max_small_qs.toFixed(2)}</td><td>${side(tr.max_large_qs, tr.max_small_qs)}</td></tr>
   <tr><td>Large file's damage at its own size (overall)</td><td>${tr.err_large_full.toFixed(2)}</td><td></td><td></td></tr></table></div>
   <p class="note">Damage is Butteraugli against the master (shrunk to the copy's size with Pillow's Lanczos): "overall" is its 3-norm, "worst spot" its max-norm, where about 1 is just noticeable; 0 is identical. The verdict uses the worst spot, as REPORT 10.3 does.</p>
   <p class="note">Your answers: ${c.views.map(v => `${v.label}: <b>${(marks[c.id + '|' + v.key] || {}).worse || '–'}</b>`).join('; ')}.</p>`; }
const TRUTH = { trials: {}, comp: {} };
DATA.trials.forEach(t => { TRUTH.trials[t.id] = t.truth; delete t.truth; });
DATA.comp.forEach(c => { TRUTH.comp[c.id] = c.truth; delete c.truth; });
['blind', 'comp', 'filt'].forEach(s => $('tab-' + s).onclick = () => { st.sec = s; st.showB = false; render(); });
cv.addEventListener('click', e => { if (st.sec !== 'blind') return; const r = cv.getBoundingClientRect(); const c = cur();
  const k = c.scale * st.zoom, sx = cv.width / r.width, sy = cv.height / r.height;
  const x = (e.clientX - r.left) * sx / st.zoom, y = (e.clientY - r.top) * sy / st.zoom;
  const key = DATA.trials[st.ti].id; marks[key] = Object.assign(marks[key] || {}, { x: x, y: y }); persist(); render(); });
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;
  if (e.code === 'Space') { e.preventDefault(); if (st.mode === 'manual' || st.mode === 'xfade') { st.showB = !st.showB; draw(); } }
  if (e.key === 'ArrowRight' && st.sec === 'blind' && st.ti < DATA.trials.length - 1) { st.ti++; st.showB = false; render(); }
  if (e.key === 'ArrowLeft' && st.sec === 'blind' && st.ti > 0) { st.ti--; st.showB = false; render(); }
  if ((e.key === 'ArrowRight' || e.key === 'ArrowLeft') && st.sec !== 'blind') {
    const step = e.key === 'ArrowRight' ? 1 : -1;
    if (st.sec === 'comp') { const n = DATA.comp[st.ci].views.length; st.cv = (st.cv + step + n) % n; }
    else { const n = DATA.filt[st.fi].views.length; st.fv = (st.fv + step + n) % n; }
    e.preventDefault(); render(); } });
$('copy').onclick = () => { const v = $('out').value; const done = () => { $('copied').textContent = 'Copied.'; };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(v).then(done, () => { $('out').select(); $('copied').textContent = 'Select-all is on; press Ctrl+C.'; });
  else { $('out').select(); $('copied').textContent = 'Select-all is on; press Ctrl+C.'; } };
render();
</script>'''


if __name__ == '__main__':
    main()
