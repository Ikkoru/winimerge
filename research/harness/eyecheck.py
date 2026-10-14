"""Build the eye-check page: flip between a large original and each candidate made from its small copy.

    python3 eyecheck.py --out /home/user/research/eyecheck [--cases cases.json]

Writes OUT/index.html (self-contained page, no network), OUT/img/*.png (crops) and OUT/cases.json.
Each case = one large original, one way the small copy was made (shrinker, factor, codec, optional
edit), and one crop window. Each candidate = one way WinIMerge could show the small copy at the
large size (or, for "shrink original", the original shrunk to the small size, shown enlarged with
nearest neighbour so its pixels stay visible).
"""
import argparse
import json
import math
import os

import cv2
import numpy as np
from PIL import Image

import edits as E
import fi
import resample as R
import study as S

CANDIDATES = [
    # id, label, function(L, S) -> image at large size
    ('nn_int', 'Nearest neighbour, whole-number factor (requested; WinIMerge UP_NEAREST_INTEGER)', lambda L, Sm: S.up_nn_int(Sm, L.shape[1], L.shape[0])[0]),
    ('nn', 'Nearest neighbour to exact size', lambda L, Sm: R.nn_exact(Sm, L.shape[1], L.shape[0])),
    ('lanczos3', 'Lanczos3, float path (WinIMerge UP_SMOOTH)', lambda L, Sm: fi.rescale(Sm, L.shape[1], L.shape[0], 'lanczos3', float_path=True)),
    ('lanczos3_usm', 'Lanczos3 + unsharp mask r1.0 50%', lambda L, Sm: R.unsharp(fi.rescale(Sm, L.shape[1], L.shape[0], 'lanczos3', float_path=True), 1.0, 0.5)),
    ('catmullrom', 'Catmull-Rom (float path)', lambda L, Sm: fi.rescale(Sm, L.shape[1], L.shape[0], 'catmullrom', float_path=True)),
    ('bilinear', 'Bilinear', lambda L, Sm: fi.rescale(Sm, L.shape[1], L.shape[0], 'bilinear')),
]
DOWN = [
    # shown at the small size, enlarged with nearest neighbour by the same factor for viewing
    ('down_box', 'Shrink the original instead (FreeImage box)', 'box'),
    ('down_matched', 'Shrink the original instead (WinIMerge DOWN_MATCHED)', None),
]

KERNEL_NAME = {'box': 'box', 'bilinear': 'bilinear', 'bicubic': 'Mitchell', 'catmullrom': 'Catmull-Rom', 'lanczos3': 'Lanczos3'}

DEFAULT_CASES = [
    dict(image='synth_flatcolor', shrinker='area', factor=2, codec='png', edit='none'),
    dict(image='synth_flatcolor', shrinker='pil_lanczos', factor=2.5, codec='jpg85', edit='none'),
    dict(image='synth_lineart', shrinker='pil_lanczos', factor=2.5, codec='png', edit='line'),
    dict(image='synth_manga', shrinker='vips', factor=3, codec='jpg85', edit='text_small'),
    dict(image='real_peppercarrot_witches', shrinker='pil_lanczos', factor=2.5, codec='jpg85', edit='none'),
    dict(image='real_peppercarrot_witches', shrinker='area', factor=3, codec='png', edit='recolor'),
    dict(image='real_peppercarrot_cover', shrinker='vips', factor=2, codec='jpg85', edit='text_small'),
    dict(image='real_hokusai_hodogaya', shrinker='pil_bicubic', factor=1.5, codec='png', edit='move'),
    dict(image='real_lion_appel', shrinker='pil_lanczos', factor=3, codec='jpg85', edit='smudge'),
    dict(image='real_kitty_screenshot', shrinker='pil_lanczos', factor=2, codec='png', edit='dot'),
]

IMG_DIRS = ['/home/user/research/testset/large', '/home/user/research/testset/large_real']
CROP = 256


def _find(name):
    for d in IMG_DIRS:
        p = os.path.join(d, name + '.png')
        if os.path.exists(p):
            return p
    raise FileNotFoundError(name)


def _crop_window(L, mask):
    H, W = L.shape[:2]
    c = min(CROP, W, H)
    if mask is not None and mask.any():
        ys, xs = np.where(mask)
        cy, cx = int(ys.mean()), int(xs.mean())
    else:
        g = cv2.cvtColor(L, cv2.COLOR_RGB2GRAY).astype(np.float32)
        mag = cv2.blur(np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0)) + np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1)), (c, c))
        cy, cx = np.unravel_index(np.argmax(mag), mag.shape)
    x0 = int(np.clip(cx - c // 2, 0, W - c))
    y0 = int(np.clip(cy - c // 2, 0, H - c))
    return x0, y0, c


def build(out, cases):
    os.makedirs(os.path.join(out, 'img'), exist_ok=True)
    meta = []
    for ci, case in enumerate(cases):
        L0 = np.asarray(Image.open(_find(case['image'])).convert('RGB'))
        H, W = L0.shape[:2]
        w, h = R.small_size(W, H, case['factor'])
        mask = None
        L1 = L0
        if case['edit'] != 'none':
            L1, mask = E.apply(case['edit'], L0)
        Sm = S.codec(R.SHRINKERS[case['shrinker']](L1, w, h), case['codec'])
        x0, y0, c = _crop_window(L0, mask)
        cid = f'c{ci:02d}'
        files = {}

        def save(key, img):
            fn = f'img/{cid}_{key}.png'
            Image.fromarray(img).save(os.path.join(out, fn), optimize=True)
            files[key] = fn
        save('original', L0[y0:y0 + c, x0:x0 + c])
        for key, label, fn in CANDIDATES:
            U = fn(L0, Sm)
            save(key, U[y0:y0 + c, x0:x0 + c])
        # compare at the small size: crop the corresponding small window, enlarge both by NN for display
        f = case['factor']
        sx0, sy0, sc = int(x0 / f), int(y0 / f), max(1, int(round(c / f)))
        k = max(1, int(round(f)))
        crop_s = lambda img: np.repeat(np.repeat(img[sy0:sy0 + sc, sx0:sx0 + sc], k, 0), k, 1)
        save('small_copy', crop_s(Sm))
        dl = {}
        for key, label, kern in DOWN:
            if kern is None:
                best, err = None, None
                for kk in S.MATCH8:
                    D = fi.rescale(L0, w, h, kk)
                    e = np.abs(D.astype(int) - Sm.astype(int)).mean()
                    if err is None or e < err:
                        best, err, bk = D, e, kk
                D = best
                label = f'{label}: {KERNEL_NAME.get(bk, bk)}'
            else:
                D = fi.rescale(L0, w, h, kern)
            dl[key] = label
            save(key, crop_s(D))
        meta.append(dict(id=cid, **case, size=[W, H], small=[w, h], crop=[x0, y0, c],
                         small_crop=[sx0, sy0, sc, k], files=files, down_labels=dl))
        print(cid, case)
    _write_page(out, meta)


def build_pairs(out, cases):
    """Eye-check page for real pairs (no known edit): crop where the two images differ most."""
    import compare_pairs as CP
    os.makedirs(os.path.join(out, 'img'), exist_ok=True)
    meta = []
    for ci, case in enumerate(cases):
        A, B = (CP.load(p) for p in case['pair'])
        L0, Sm = (A, B) if A.shape[0] * A.shape[1] >= B.shape[0] * B.shape[1] else (B, A)
        H, W = L0.shape[:2]
        h, w = Sm.shape[:2]
        U = fi.rescale(Sm, W, H, 'lanczos3', float_path=True)
        d = np.sqrt(((L0.astype(np.float32) - U.astype(np.float32)) ** 2).sum(axis=2))
        c = min(CROP, W, H)
        dm = cv2.blur(d, (c, c))
        cy, cx = np.unravel_index(np.argmax(dm), dm.shape)
        x0, y0 = int(np.clip(cx - c // 2, 0, W - c)), int(np.clip(cy - c // 2, 0, H - c))
        cid = f'p{ci:02d}'
        files = {}

        def save(key, img):
            fn = f'img/{cid}_{key}.png'
            Image.fromarray(img).save(os.path.join(out, fn), optimize=True)
            files[key] = fn
        save('original', L0[y0:y0 + c, x0:x0 + c])
        for key, label, fn in CANDIDATES:
            save(key, fn(L0, Sm)[y0:y0 + c, x0:x0 + c])
        f = W / w
        sx0, sy0, sc = int(x0 / f), int(y0 / f), max(1, int(round(c / f)))
        k = max(1, int(round(f)))
        crop_s = lambda img: np.repeat(np.repeat(img[sy0:sy0 + sc, sx0:sx0 + sc], k, 0), k, 1)
        save('small_copy', crop_s(Sm))
        dl = {}
        for key, label, kern in DOWN:
            if kern is None:
                best, err = None, None
                for kk in S.MATCH8:
                    D = fi.rescale(L0, w, h, kk)
                    e = np.abs(D.astype(int) - Sm.astype(int)).mean()
                    if err is None or e < err:
                        best, err, bk = D, e, kk
                D = best
                label = f'{label}: {KERNEL_NAME.get(bk, bk)}'
            else:
                D = fi.rescale(L0, w, h, kern)
            dl[key] = label
            save(key, crop_s(D))
        meta.append(dict(id=cid, image=os.path.basename(case['pair'][0]) + ' / ' + os.path.basename(case['pair'][1]),
                         shrinker='unknown', factor=round(f, 3), codec='as found', edit='unknown',
                         size=[W, H], small=[w, h], crop=[x0, y0, c], small_crop=[sx0, sy0, sc, k], files=files,
                         down_labels=dl))
        print(cid, meta[-1]['image'])
    _write_page(out, meta)


def _credits(meta):
    """Attribution for the real images shown (CC BY and GPL need it; the crops are adaptations)."""
    import html
    try:
        man = json.load(open(os.path.join(os.path.dirname(IMG_DIRS[1]), 'sources', 'MANIFEST.json')))
        crops = json.load(open(os.path.join(os.path.dirname(IMG_DIRS[1]), 'real', 'CROPS.json')))
    except (OSError, ValueError):
        return ''
    by_file = {e['file']: e for e in man['images']}
    lines = []
    for name in sorted({m['image'] for m in meta if str(m['image']).startswith('real_')}):
        src = crops.get(name + '.png', {}).get('source')
        e = by_file.get(src)
        if e:
            lines.append(f'<li>{html.escape(e["attribution"])} ({html.escape(e["license"])}). Cropped, resized and '
                         f'partly edited for this test.</li>')
    if not lines:
        return ''
    return ('<p>Image credits: synthetic images are generated by the study harness. Real images:</p><ul class="credits">'
            + ''.join(lines) + '</ul>')


def _write_page(out, meta):
    """Write OUT/index.html (standalone, opens from disk) and OUT/artifact.html (the same page without
    the document skeleton, for publishing as a claude.ai artifact). The crops are embedded as data
    URIs: one self-contained file, and the canvas is not tainted when the page is opened from disk
    (file:// images count as cross-origin for getImageData)."""
    import base64
    labels = {k: l for k, l, _ in CANDIDATES}
    labels.update({k: l for k, l, _ in DOWN})
    labels['small_copy'] = 'The small copy itself (enlarged with nearest neighbour)'
    with open(os.path.join(out, 'cases.json'), 'w') as fh:
        json.dump(dict(cases=meta, labels=labels), fh, indent=1)
    for m in meta:
        m['files'] = {k: 'data:image/png;base64,' + base64.b64encode(open(os.path.join(out, v), 'rb').read()).decode()
                      for k, v in m['files'].items()}
    body = PAGE_BODY.replace('/*CASES*/', json.dumps(dict(cases=meta, labels=labels))).replace('<!--CREDITS-->', _credits(meta))
    with open(os.path.join(out, 'index.html'), 'w') as fh:
        fh.write('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
                 '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                 + PAGE_HEAD + '</head><body>\n' + body + '</body></html>\n')
    with open(os.path.join(out, 'artifact.html'), 'w') as fh:
        fh.write(PAGE_HEAD + body)


PAGE_HEAD = r'''<title>Resampling Flip Check</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400&display=swap">
<style>
/* Layout: one working column; controls above a pixel stage, verdict buttons below. Neutrals lean slightly blue
   toward the accent; the stage is a mid grey in both themes so neither image's edges blend into it. */
:root {
  --bg: #f5f6f8; --fg: #16181d; --mut: #5d6370; --card: #ffffff; --line: #d6d9e0; --acc: #2a62c9; --stage: #7f8288;
  --sans: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #15171c; --fg: #eceef3; --mut: #a0a6b3; --card: #1f2229; --line: #353a45; --acc: #7aa2ff; --stage: #6c6f75; color-scheme: dark; } }
:root[data-theme="dark"] {
  --bg: #15171c; --fg: #eceef3; --mut: #a0a6b3; --card: #1f2229; --line: #353a45; --acc: #7aa2ff; --stage: #6c6f75; color-scheme: dark; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 14px/1.5 var(--sans); }
main { max-width: 1100px; margin: 0 auto; padding-block: 20px 32px;
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  display: flex; flex-direction: column; gap: 10px; }
h1 { font-size: 22px; font-weight: 600; margin: 0; text-wrap: balance; }
p { margin: 0; color: var(--mut); max-width: 68ch; }
.row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; min-width: 0; }
label { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; min-width: 0; max-width: 100%; }
select, button, textarea { font: inherit; padding: 6px 10px; border: 1px solid var(--line); border-radius: 6px;
  background: var(--card); color: var(--fg); max-width: 100%; }
select { min-width: 0; }
button { cursor: pointer; }
button:focus-visible, select:focus-visible { outline: 2px solid var(--acc); outline-offset: 2px; }
button.on { border-color: var(--acc); color: var(--acc); font-weight: 600; }
.stage { position: relative; overflow: auto; max-width: 100%; border: 1px solid var(--line); border-radius: 8px; background: var(--stage); }
.stage canvas { display: block; image-rendering: pixelated; }
.lbl, .legend, code { font-family: var(--mono); font-size: 12px; font-variant-numeric: tabular-nums; color: var(--mut); }
.group-title { font-size: 12px; letter-spacing: .04em; text-transform: uppercase; color: var(--mut); }
textarea { width: 100%; min-height: 120px; font-family: var(--mono); font-size: 12px; box-sizing: border-box; }
.credits { margin: 0; padding-left: 20px; color: var(--mut); font-size: 12px; max-width: 90ch; }
</style>
'''

PAGE_BODY = r'''<main>
<h1>Resampling flip check</h1>
<p>Each case is a large original and a smaller copy of it, made the way websites and libraries make them
(shrinker, factor and file format are listed under the picture). Pick how WinIMerge could show the copy, then flip
between it and the original. The modes marked WinIMerge are the ones in the pull request. "Shrink the original"
candidates are compared at the small size and shown enlarged with nearest neighbour.</p>
<div class="row"><label for="case">Case <select id="case"></select></label></div>
<div class="row"><label for="cand">Candidate <select id="cand"></select></label></div>
<div class="row" id="modes" aria-label="Flip mode"></div>
<div class="row" id="zooms" aria-label="Zoom"></div>
<div class="row"><span class="lbl" id="showing"></span></div>
<div class="stage"><canvas id="cv"></canvas></div>
<div class="row legend" id="info"></div>
<div class="row"><span class="group-title">Spurious differences</span>
 <button data-k="spur" data-v="none">none</button><button data-k="spur" data-v="few">a few</button><button data-k="spur" data-v="many">many</button></div>
<div class="row"><span class="group-title">Edit visible</span>
 <button data-k="edit" data-v="yes">yes</button><button data-k="edit" data-v="faint">faint</button><button data-k="edit" data-v="no">no</button><button data-k="edit" data-v="na">no edit</button></div>
<div class="row"><button id="copy">Copy marks as JSON</button><span class="lbl" id="count"></span></div>
<textarea id="out" hidden readonly aria-label="Marks as JSON"></textarea>
<p>Cross-fade uses WinIMerge's alpha-blend animation timing (fade 20 %, hold 30 %, fade back 20 %, hold 30 % of a
1-second cycle). Space flips by hand in Manual mode. Zoom uses nearest neighbour. Marks stay in this browser only.</p>
<!--CREDITS-->
</main>
<script>
const DATA = /*CASES*/;
const $ = id => document.getElementById(id);
const cv = $('cv'), ctx = cv.getContext('2d');
const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
let caseI = 0, cand = 'lanczos3', mode = reduce ? 'manual' : 'xfade', zoom = 2, manual = false, imgs = {}, t0 = performance.now();
const MODES = [['xfade','Cross-fade (WinMerge timing)'],['flip2','Hard flip 2 Hz'],['flip3','Hard flip 3 Hz'],['flip4','Hard flip 4 Hz'],['manual','Manual (space)'],['side','Side by side'],['diff','|difference| ×4']];
let marks = {}; try { marks = JSON.parse(localStorage.getItem('flipmarks') || '{}'); } catch (e) {}
function save() { try { localStorage.setItem('flipmarks', JSON.stringify(marks)); } catch (e) {} $('count').textContent = Object.keys(marks).length + ' marked'; }
DATA.cases.forEach((c, i) => { const o = document.createElement('option'); o.value = i;
  o.textContent = `${c.id}: ${c.image}, ${c.shrinker} 1/${c.factor}, ${c.codec}, edit: ${c.edit}`; $('case').appendChild(o); });
function fillCands() { const c = DATA.cases[caseI]; $('cand').innerHTML = '';
  Object.keys(c.files).filter(k => k !== 'original').forEach(k => { const o = document.createElement('option'); o.value = k;
    o.textContent = (c.down_labels && c.down_labels[k]) ? c.down_labels[k] : (DATA.labels[k] || k); if (k === cand) o.selected = true; $('cand').appendChild(o); });
  cand = $('cand').value; }
function btns(el, list, cur, set) { el.innerHTML = ''; list.forEach(([k, l]) => { const b = document.createElement('button'); b.textContent = l;
  if (k === cur) b.className = 'on'; b.setAttribute('aria-pressed', k === cur); b.onclick = () => { set(k); btns(el, list, k, set); }; el.appendChild(b); }); }
function load(src) { if (imgs[src]) return imgs[src]; const im = new Image(); im.src = src; imgs[src] = im; return im; }
function candLabel() { const c = DATA.cases[caseI]; return (c.down_labels && c.down_labels[cand]) || DATA.labels[cand] || cand; }
function refPair() { const c = DATA.cases[caseI]; const small = cand === 'small_copy' || cand.startsWith('down_');
  // compare-at-small candidates are shown against the small copy, both enlarged the same way
  return small ? [load(c.files['small_copy']), load(c.files[cand]), 'small copy', candLabel()]
               : [load(c.files['original']), load(c.files[cand]), 'original', candLabel()]; }
function alphaAt(t) { const T = 1000, x = t % T; if (x < 200) return x / 200; if (x < 500) return 1; if (x < 700) return 1 - (x - 500) / 200; return 0; }
function draw(now) {
  const [a, b, la, lb] = refPair(); if (!a.complete || !b.complete) { requestAnimationFrame(draw); return; }
  const w = a.naturalWidth, h = a.naturalHeight, side = mode === 'side';
  const W = (side ? 2 * w + 8 : w) * zoom, H = h * zoom;
  if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; }
  ctx.imageSmoothingEnabled = false;
  const t = now - t0; let which = 0, alpha = 0;
  if (mode === 'xfade') alpha = alphaAt(t);
  else if (mode.startsWith('flip')) { const hz = +mode.slice(4); which = Math.floor(t / (500 / hz)) % 2; }
  else if (mode === 'manual') which = manual ? 1 : 0;
  if (side) { ctx.clearRect(0, 0, W, H); ctx.drawImage(a, 0, 0, w * zoom, h * zoom); ctx.drawImage(b, (w + 8) * zoom, 0, w * zoom, h * zoom); $('showing').textContent = `left: ${la} | right: ${lb}`; }
  else if (mode === 'diff') { ctx.drawImage(a, 0, 0, w * zoom, h * zoom); const da = ctx.getImageData(0, 0, W, H);
    ctx.drawImage(b, 0, 0, w * zoom, h * zoom); const db = ctx.getImageData(0, 0, W, H);
    for (let i = 0; i < da.data.length; i += 4) for (let j = 0; j < 3; j++) db.data[i + j] = Math.min(255, 4 * Math.abs(da.data[i + j] - db.data[i + j]));
    ctx.putImageData(db, 0, 0); $('showing').textContent = '|' + la + ' − ' + lb + '| × 4'; }
  else if (mode === 'xfade') { ctx.globalAlpha = 1; ctx.drawImage(a, 0, 0, w * zoom, h * zoom); ctx.globalAlpha = alpha; ctx.drawImage(b, 0, 0, w * zoom, h * zoom); ctx.globalAlpha = 1;
    $('showing').textContent = `${la} → ${lb}: ${Math.round(alpha * 100)} %`; }
  else { ctx.drawImage(which ? b : a, 0, 0, w * zoom, h * zoom); $('showing').textContent = 'showing: ' + (which ? lb : la); }
  requestAnimationFrame(draw); }
function info() { const c = DATA.cases[caseI];
  $('info').innerHTML = `original ${c.size[0]}×${c.size[1]}, small copy ${c.small[0]}×${c.small[1]} (factor ${c.factor}, shrunk with <code>${c.shrinker}</code>, saved as <code>${c.codec}</code>), edit: <code>${c.edit}</code>; crop ${c.crop[2]} px at (${c.crop[0]}, ${c.crop[1]}).`;
  document.querySelectorAll('[data-k]').forEach(b => { const m = marks[c.id + '|' + cand] || {}; b.className = (m[b.dataset.k] === b.dataset.v) ? 'on' : ''; }); }
$('case').onchange = e => { caseI = +e.target.value; fillCands(); info(); };
$('cand').onchange = e => { cand = e.target.value; info(); };
document.querySelectorAll('[data-k]').forEach(b => b.onclick = () => { const k = DATA.cases[caseI].id + '|' + cand;
  marks[k] = Object.assign(marks[k] || {}, { [b.dataset.k]: b.dataset.v }); save(); info(); });
document.addEventListener('keydown', e => { if (e.code === 'Space' && e.target.tagName !== 'TEXTAREA' && e.target.tagName !== 'SELECT') { manual = !manual; e.preventDefault(); } });
$('copy').onclick = () => { const text = JSON.stringify(marks, null, 1); const out = $('out'); out.value = text; out.hidden = false;
  const done = ok => { $('copy').textContent = ok ? 'Copied' : 'Select the text below and copy it'; setTimeout(() => $('copy').textContent = 'Copy marks as JSON', 2500); };
  try { navigator.clipboard.writeText(text).then(() => done(true), () => { out.select(); done(false); }); } catch (e) { out.select(); done(false); } };
btns($('modes'), MODES, mode, k => { mode = k; t0 = performance.now(); });
btns($('zooms'), [[1,'1×'],[2,'2×'],[4,'4×']], zoom, k => { zoom = k; });
fillCands(); info(); save(); requestAnimationFrame(draw);
</script>
'''


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='/home/user/research/eyecheck')
    ap.add_argument('--cases', default='')
    a = ap.parse_args()
    cases = json.load(open(a.cases)) if a.cases else DEFAULT_CASES
    build(a.out, cases)
