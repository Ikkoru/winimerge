"""Tables for the follow-up experiments (tiny edits, pixel art, compression damage) -> results/tables_followup.md

    python3 followup_report.py [--results ../results]
"""
import argparse
import os

import numpy as np
import pandas as pd

import report as RP
from paths import RESULTS

TE_METHODS = ['small', 'rt_l3', 'up_l3', 'up_cr', 'up_l3usm', 'up_nn', 'up_nn_int']
TE_LABEL = {'small': 'shrink, matched (DOWN_MATCHED)', 'rt_l3': 'round trip (Lanczos3)', 'up_l3': 'enlarge, Lanczos3',
            'up_cr': 'enlarge, Catmull-Rom', 'up_l3usm': 'enlarge, Lanczos3 + USM', 'up_nn': 'enlarge, NN to exact size',
            'up_nn_int': 'enlarge, whole-number NN (centred)'}
FLIP_LABEL = {'small': 'shrink, 1:1', 'small_zoom': 'shrink, viewed zoomed k×', 'rt_l3': 'round trip (Lanczos3)',
              'up_l3': 'enlarge, Lanczos3', 'up_cr': 'enlarge, Catmull-Rom', 'up_nn': 'enlarge, NN to exact size'}
SCEN_LABEL = {'png': 'small PNG', 'jpg85': 'small JPEG q85', 'big90_png': 'large JPEG q90 + small PNG'}


def pct(x):
    return '' if pd.isna(x) else f'{100 * x:.0f} %'


def table(df, index_label=None):
    df = df.copy()
    cols = [str(c) for c in df.columns]
    out = ['| ' + ' | '.join([index_label or (df.index.name or '')] + cols) + ' |', '|' + '---|' * (len(cols) + 1)]
    for idx, row in df.iterrows():
        out.append('| ' + ' | '.join([str(idx)] + [str(v) for v in row.values]) + ' |')
    return '\n'.join(out)


def tiny(results, out):
    p = os.path.join(results, 'tiny_edits.csv')
    if not os.path.exists(p):
        return
    d = pd.read_csv(p)
    d['rel'] = d['size'] / d['factor']
    out.append('\n## Tiny edits (`harness/tiny_edits.py`)\n')
    out.append(f'{d.image.nunique()} images × factors {", ".join(str(int(f)) for f in sorted(d.factor.unique()))} × 3 save scenarios × {d.edit.nunique()} edits × 2 directions '
               f'({len(d[d.method == "small"])} edited pairs per method). "Visible" = WinMerge marks at least one of the edit\'s '
               'blocks at the threshold that leaves 1 % of the unedited twin\'s blocks marked; "eye" = the edit\'s block stands '
               'out in ꟻLIP\'s map at 96 ppd the same way (for the shrink: viewed zoomed k×).\n')
    for scen in ['png', 'jpg85', 'big90_png']:
        x = d[d.scenario == scen]
        t = x.pivot_table(index='method', columns='direction', values='any_T1', aggfunc='mean').reindex(TE_METHODS)
        e = x.pivot_table(index='method', columns='direction', values='flip_any', aggfunc='mean').reindex(TE_METHODS)
        ez = x[x.method == 'small'].groupby('direction')['flipzoom_any'].mean()
        tt = pd.DataFrame({'visible, edit in the small copy': t.get('in_small'), 'visible, edit in the large file': t.get('in_large'),
                           'eye, edit in the small copy': e.get('in_small'), 'eye, edit in the large file': e.get('in_large')})
        tt.loc['small_zoom'] = [np.nan, np.nan, ez.get('in_small'), ez.get('in_large')]
        tt = tt.reindex(['small', 'small_zoom'] + TE_METHODS[1:]).map(pct)
        tt.index = [TE_LABEL.get(m, 'shrink, viewed zoomed k×') for m in tt.index]
        out.append(f'\n### {SCEN_LABEL[scen]}: share of edited pairs where the edit shows\n')
        out.append(table(tt, 'method'))
    # by edit size relative to the copy's pixel
    d['relc'] = pd.cut(d.rel, [0, 0.34, 0.6, 1.1, 2.1, 10], labels=['≤ 1/3 px', '½ px', '1 px', '1½–2 px', '3 px'])
    for scen in ['png', 'jpg85', 'big90_png']:
        x = d[(d.scenario == scen) & (d.kind == 'dot')]
        t = x.pivot_table(index='method', columns='relc', values='any_T1', aggfunc='mean', observed=True).reindex(TE_METHODS)
        e = x[x.method.isin(FLIP_LABEL)].pivot_table(index='method', columns='relc', values='flip_any', aggfunc='mean', observed=True)
        ez = x[x.method == 'small'].groupby('relc', observed=True)['flipzoom_any'].mean()
        e.loc['small_zoom'] = ez
        t.index = ['visible: ' + TE_LABEL[m] for m in t.index]
        e = e.reindex([m for m in FLIP_LABEL])
        e.index = ['eye: ' + FLIP_LABEL[m] for m in e.index]
        out.append(f'\n### {SCEN_LABEL[scen]}: dots by size relative to one pixel of the copy (both directions)\n')
        out.append(table(pd.concat([t, e]).map(pct), 'method'))
    for scen in ['png', 'jpg85', 'big90_png']:
        x = d[d.scenario == scen]
        t = x.pivot_table(index='method', columns=['contrast', 'place'], values='any_T1', aggfunc='mean').reindex(TE_METHODS).map(pct)
        t.columns = [f'{c} contrast, {p} spot' for c, p in t.columns]
        t.index = [TE_LABEL[m] for m in t.index]
        out.append(f'\n### {SCEN_LABEL[scen]}: by contrast and placement\n')
        out.append(table(t, 'method'))
    # absolute strength in the eye model: the edit's ꟻLIP peak (median) by size, against the unedited 99th percentile
    for scen in ['png', 'jpg85', 'big90_png']:
        x = d[(d.scenario == scen) & (d.kind == 'dot')]
        rows = {}
        for m, col, tcol, lab in [('small', 'flip_peak', 'flip_T1', 'shrink, 1:1'), ('small', 'flipzoom_peak', 'flipzoom_T1', 'shrink, zoomed k×'),
                                  ('rt_l3', 'flip_peak', 'flip_T1', 'round trip'), ('up_l3', 'flip_peak', 'flip_T1', 'enlarge, Lanczos3'),
                                  ('up_cr', 'flip_peak', 'flip_T1', 'enlarge, Catmull-Rom'), ('up_nn', 'flip_peak', 'flip_T1', 'enlarge, NN to exact size')]:
            y = x[x.method == m]
            r = y.groupby('relc', observed=True)[col].median().map(lambda v: f'{v:.2f}')
            r['unedited 99th pct'] = f'{y[tcol].median():.2f}'
            rows[lab] = r
        t = pd.DataFrame(rows).T
        out.append(f'\n### {SCEN_LABEL[scen]}: how strongly the dot shows to the eye (ꟻLIP peak at the dot, median; 0 = no difference, 1 = black against white) and the level the unedited comparison already reaches in 1 % of its blocks\n')
        out.append(table(t, 'view'))
    # edit strength relative to the noise (median over pairs)
    t = d.pivot_table(index='method', columns='scenario', values='cnr', aggfunc='median').reindex(TE_METHODS)[['png', 'jpg85', 'big90_png']]
    t = t.map(lambda v: f'{v:.2f}')
    t.index = [TE_LABEL[m] for m in t.index]
    out.append('\n### Strongest edit block relative to the unedited 99th percentile (median; above 1 = marked)\n')
    out.append(table(t, 'method'))
    # Catmull-Rom against Lanczos3, pair by pair
    a = d[d.method == 'up_cr'].set_index(['image', 'factor', 'scenario', 'edit', 'direction'])
    b = d[d.method == 'up_l3'].set_index(['image', 'factor', 'scenario', 'edit', 'direction'])
    j = a.join(b, lsuffix='_cr', rsuffix='_l3', how='inner')
    better = (j.cnr_cr > j.cnr_l3 * 1.02).mean()
    worse = (j.cnr_cr < j.cnr_l3 / 1.02).mean()
    out.append(f'\nCatmull-Rom against Lanczos3, same pairs: the edit stands out more with Catmull-Rom in {pct(better)}, '
               f'with Lanczos3 in {pct(worse)}, the same (±2 %) in {pct(1 - better - worse)}; visible {pct(j.any_T1_cr.mean())} vs '
               f'{pct(j.any_T1_l3.mean())}; eye {pct(j.flip_any_cr.mean())} vs {pct(j.flip_any_l3.mean())}.\n')


def pixel(results, out):
    p = os.path.join(results, 'pixelart.csv')
    if not os.path.exists(p):
        return
    d = pd.read_csv(p)
    out.append('\n## Pixel art (`harness/pixelart_test.py`)\n')
    order = ['nn8_4', 'nn8_2', 'nn8_3', 'nn6_4', 'lz8_2', 'lz8_2.5', 'lz8_3', 'lz8_3j', 'bl8_2.5', 'pt8_2.5', 'pt8_3']
    meth = ['small', 'rt_l3', 'up_nn', 'up_nn_int', 'up_l3', 'up_cr']
    u = d[d.edit == 'none']
    t = u.pivot_table(index='scenario', columns='method', values='T_p99', aggfunc='median').reindex(order)[meth]
    out.append('\n### Unedited pairs: threshold needed (T_p99, median of 3 pictures; inf = parts never line up)\n')
    out.append(table(t.map(lambda v: f'{v:.0f}' if np.isfinite(v) else 'inf'), 'how the two copies relate'))
    e = d[d.edit != 'none']
    t = e.pivot_table(index='scenario', columns='method', values='any_T1', aggfunc='mean').reindex(order)[meth].map(pct)
    out.append('\n### Edits visible (one logical pixel, a 2×2 block, a subtle 6×6 recolour; both directions)\n')
    out.append(table(t, 'how the two copies relate'))


def comp(results, out):
    p = os.path.join(results, 'compression_recover.csv')
    if os.path.exists(p):
        d = pd.read_csv(p)
        out.append('\n## jpegQS recoverability (`harness/compression_test.py recover`)\n')
        cols = []
        for pre in ('raw_', 'qs3_', 'qs6_'):
            for m in ('psnr', 'ba_p3', 'ssimu2', 'flip96'):
                cols.append(pre + m)
        t = d.groupby('history')[cols].median()
        order = ['q95', 'q90', 'q85', 'q80', 'q70', 'q75>q90', 'q60>q90', 'q80s>q90', 'q85s>q85', 'q90s>q90s>q90']
        t = t.reindex([o for o in order if o in t.index])
        show = pd.DataFrame({'PSNR as saved': t.raw_psnr.map('{:.1f}'.format), 'PSNR jpegQS -q6': t.qs6_psnr.map('{:.1f}'.format),
                             'Butteraugli as saved': t.raw_ba_p3.map('{:.2f}'.format), 'Butteraugli -q6': t.qs6_ba_p3.map('{:.2f}'.format),
                             'SSIMULACRA2 as saved': t.raw_ssimu2.map('{:.1f}'.format), 'SSIMULACRA2 -q6': t.qs6_ssimu2.map('{:.1f}'.format),
                             'ꟻLIP as saved': t.raw_flip96.map('{:.4f}'.format), 'ꟻLIP -q6': t.qs6_flip96.map('{:.4f}'.format)})
        out.append(f'Medians over {d.image.nunique()} masters; Butteraugli 3-norm and ꟻLIP lower is better, PSNR and SSIMULACRA2 higher.\n')
        out.append(table(show, 'JPEG history'))
        # one-time q80 vs re-saved q90, pair by pair
        for a, b in [('q80', 'q90s>q90s>q90'), ('q80', 'q75>q90'), ('q85', 'q90s>q90s>q90'), ('q70', 'q60>q90')]:
            pa, pb = d[d.history == a].set_index('image'), d[d.history == b].set_index('image')
            lines = []
            for m, hb in (('psnr', True), ('ba_p3', False), ('ssimu2', True), ('flip96', False)):
                for pre in ('raw_', 'qs6_'):
                    va, vb = pa[pre + m], pb[pre + m]
                    win = (va > vb) if hb else (va < vb)
                    lines.append(f'{m} {pre[:-1]}: {a} better in {int(win.sum())}/{len(win)}')
            out.append(f'\n{a} against {b}: ' + '; '.join(lines) + '.\n')
    p = os.path.join(results, 'compression_keep.csv')
    if os.path.exists(p):
        keep(pd.read_csv(p), out)


H_ORDER = ['q95', 'q90', 'q80', 'q70', 'q90s>q90s>q90', 'q75>q90']
H_LABEL = {'q95': 'q95 once', 'q90': 'q90 once', 'q80': 'q80 once', 'q70': 'q70 once',
           'q90s>q90s>q90': 'q90 saved 3 times (grid shifted)', 'q75>q90': 'q75, then q90'}
L_ORDER = ['png', 'q95', 'q85', 'q75', 'q85s>q85', 'thumb_of_q90']
L_LABEL = {'png': 'PNG', 'q95': 'JPEG q95', 'q85': 'JPEG q85', 'q75': 'JPEG q75', 'q85s>q85': 'JPEG q85 saved twice (shifted)',
           'thumb_of_q90': 'JPEG q85 thumbnail of the q90 upload'}
VISIBLE = 1.0   # Butteraugli max-norm at the copy's size


def keep(d, out):
    out.append('\n## Is a smaller copy worth keeping? (`harness/compression_test.py keep`)\n')
    c = d[d.kind == 'copy'].copy()
    n_m = c.image.nunique()
    out.append(f'{n_m} masters × factors 2 and 3. Damage = Butteraugli against the true small image (the master shrunk with '
               'Pillow Lanczos), at the small copy\'s size: the large file shrunk the same way, the small copy as it is. '
               f'Max-norm ≥ {VISIBLE:g} counts as visible (libjxl\'s "just noticeable"). "+jpegQS" = restored with jpegQS -q 6.\n')
    c['base'] = c['copy'].str.replace('+qs6', '', regex=False)
    c['restored'] = c['copy'].str.endswith('+qs6')
    # A. large file's damage that survives at the small size
    hh = c[c.side == 'H']
    rows = {}
    for hn in H_ORDER:
        x, y = hh[(hh.base == hn) & ~hh.restored], hh[(hh.base == hn) & hh.restored]
        if x.empty:
            continue
        r = {}
        for f in sorted(x.factor.unique()):
            xf, yf = x[x.factor == f], y[y.factor == f]
            r[f'{f:g}×: Butteraugli max, as saved → +jpegQS'] = f'{xf.small_ba_max.median():.2f} → {yf.small_ba_max.median():.2f}'
            r[f'{f:g}×: visible, as saved / +jpegQS'] = f'{int((xf.small_ba_max >= VISIBLE).sum())} / {int((yf.small_ba_max >= VISIBLE).sum())} of {len(xf)}'
        rows[H_LABEL[hn]] = r
    out.append('\n### The large file\'s compression damage that survives at the small size (what a lossless small copy would add)\n')
    out.append(table(pd.DataFrame(rows).T, 'large file'))
    # B. lossy small copies at their own size
    ll = c[c.side == 'L']
    rows = {}
    for ln in L_ORDER:
        x, y = ll[(ll.base == ln) & ~ll.restored], ll[(ll.base == ln) & ll.restored]
        if x.empty:
            continue
        r = {}
        for f in sorted(x.factor.unique()):
            xf, yf = x[x.factor == f], y[y.factor == f]
            r[f'{f:g}×: Butteraugli max, as saved → +jpegQS'] = (f'{xf.small_ba_max.median():.2f} → {yf.small_ba_max.median():.2f}'
                                                                 if not yf.empty else f'{xf.small_ba_max.median():.2f}')
        rows[L_LABEL[ln]] = r
    out.append('\n### The small copy\'s own damage at its size\n')
    out.append(table(pd.DataFrame(rows).T, 'small copy'))
    # C. which is cleaner at the small size, and does the centred NN view agree?
    cc = c.set_index(['image', 'factor', 'side', 'copy'])
    pairs = d[d.kind == 'pair']
    rows = []
    for (img, f, H, L, rest), g in pairs.groupby(['image', 'factor', 'H', 'L', 'restored']):
        try:
            eh, el = cc.loc[(img, f, 'H', H)], cc.loc[(img, f, 'L', L)]
        except KeyError:
            continue
        def side(a, b, tol=0.1):
            return 'large' if a < b * (1 - tol) else 'small' if b < a * (1 - tol) else 'same'
        rows.append(dict(image=img, factor=f, H=H.replace('+qs6', ''), L=L.replace('+qs6', ''), restored=rest,
                         truth=side(eh.small_ba_max, el.small_ba_max), truth_p3=side(eh.small_ba_p3, el.small_ba_p3),
                         nnview=side(eh.nnview_flip96, el.nnview_flip96), zoomed=side(eh.small_flipz, el.small_flipz),
                         visible_h=eh.small_ba_max >= VISIBLE, visible_l=el.small_ba_max >= VISIBLE,
                         T_p99=g.T_p99.iloc[0], share_T8=g.share_T8.iloc[0], share_T16=g.share_T16.iloc[0]))
    v = pd.DataFrame(rows)
    if v.empty:
        return
    lossy = v[v.L != 'png']
    for rest, lab in ((False, 'as saved'), (True, 'both restored with jpegQS')):
        x = lossy[lossy.restored == rest]
        t = x.pivot_table(index='H', columns='L', values='truth',
                          aggfunc=lambda s: f'{int((s == "large").sum())} · {int((s == "same").sum())} · {int((s == "small").sum())}')
        t = t.reindex([h for h in H_ORDER if h in t.index])[[l for l in L_ORDER if l in t.columns]]
        t.index = [H_LABEL[h] for h in t.index]
        t.columns = [L_LABEL[l] for l in t.columns]
        out.append(f'\n### Lossy small copy, {lab}: which is cleaner at the small size (large file · within 10 % · small copy; counts over masters and factors)\n')
        out.append(table(t, 'large file \\ small copy'))
    for rest, lab in ((False, 'as saved'), (True, 'restored')):
        x = lossy[lossy.restored == rest]
        out.append(f'\nLossy pairs {lab}: the centred whole-number NN view (ꟻLIP of each side at 96 ppd against its own pristine version) '
                   f'picks the same cleaner side as the small-size truth in {pct((x.nnview == x.truth).mean())} of {len(x)} cases; '
                   f'the small comparison viewed zoomed k× (ꟻLIP at 96/k ppd) in {pct((x.zoomed == x.truth).mean())}; '
                   f'Butteraugli 3-norm agrees with the max-norm verdict in {pct((x.truth_p3 == x.truth).mean())}. '
                   f'The NN view calls the small copy cleaner in {pct((x.nnview == "small").mean())}, the truth in {pct((x.truth == "small").mean())}.\n')
    # D. lossless small copy: does WinMerge's marking tell visible damage?
    x = v[(v.L == 'png') & ~v.restored]
    if not x.empty:
        rows = {}
        for thr in (0.005, 0.01, 0.02, 0.05):
            pred = x.share_T8 > thr
            rows[f'more than {100 * thr:g} % of blocks marked at threshold 8'] = {
                'agrees with "visible"': pct((pred == x.visible_h).mean()),
                'misses visible damage': int((~pred & x.visible_h).sum()), 'false alarms': int((pred & ~x.visible_h).sum())}
        for thr in (0.005, 0.01, 0.02, 0.05):
            pred = x.share_T16 > thr
            rows[f'more than {100 * thr:g} % of blocks marked at threshold 16'] = {
                'agrees with "visible"': pct((pred == x.visible_h).mean()),
                'misses visible damage': int((~pred & x.visible_h).sum()), 'false alarms': int((pred & ~x.visible_h).sum())}
        out.append(f'\n### Lossless small copy: can WinMerge\'s marks in DOWN_MATCHED tell whether the large file\'s damage is visible at the small size? ({len(x)} pairs, {int(x.visible_h.sum())} visible)\n')
        out.append(table(pd.DataFrame(rows).T, 'rule'))
        t = x.pivot_table(index='H', columns='factor', values='share_T8', aggfunc='median').reindex([h for h in H_ORDER if h in set(x.H)])
        t.index = [H_LABEL[h] for h in t.index]
        out.append('\n### Lossless small copy: share of blocks DOWN_MATCHED marks at threshold 8 (median)\n')
        out.append(table(t.map(pct), 'large file'))


def blocksize(results, out):
    p = os.path.join(results, 'blocksize_check.csv')
    if not os.path.exists(p):
        return
    d = pd.read_csv(p)
    out.append('\n## Round trip against the shrink with the same block area (`harness/blocksize_check.py`)\n')
    out.append(f'{d.image.nunique()} images × factors 2, 4 × lossy saves × {d.edit.nunique()} edits × 2 directions. "Coarse" = WinMerge\'s '
               'blocks cover 8k × 8k pixels of the original (the shrink with block size 8, the round trip with 8k); "fine" = 8 × 8 '
               '(the shrink with block size 8/k, the round trip with 8). Eye: ꟻLIP, the shrink viewed zoomed k×.\n')
    lab = {('small', 'coarse'): 'shrink, block size 8', ('small', 'fine'): 'shrink, block size 8/k (4 at 2×, 2 at 4×)',
           ('rt', 'fine'): 'round trip (Lanczos3), block size 8', ('rt', 'coarse'): 'round trip (Lanczos3), block size 8k',
           ('rtbl', 'fine'): 'round trip (bilinear), block size 8', ('rtbl', 'coarse'): 'round trip (bilinear), block size 8k'}
    rows = {}
    for (v, g), name in lab.items():
        x = d[(d.view == v) & (d.granularity == g)]
        if x.empty:
            continue
        r = {}
        for scen, sl in (('jpg85', 'small JPEG q85'), ('big90_png', 'large JPEG q90 + small PNG')):
            y = x[x.scenario == scen]
            r[f'visible, {sl}'] = pct(y.visible.mean())
            r[f'eye, {sl}'] = pct(y.eye.mean())
            sub = y[y['size'] / y.factor <= 0.5]
            r[f'visible, {sl}, dots ≤ ½ px'] = pct(sub.visible.mean())
        rows[name] = r
    out.append(table(pd.DataFrame(rows).T, 'view'))


def crl3(results, out):
    p = os.path.join(results, 'cr_vs_l3.csv')
    if not os.path.exists(p):
        return
    d = pd.read_csv(p)
    out.append('\n## Catmull-Rom against Lanczos3 as the enlarger, lossless copies (`harness/cr_vs_l3.py`)\n')
    out.append(f'{d.image.nunique()} pictures × factors {", ".join(str(f) for f in sorted(d.factor.unique()))}; PNG copies made with Pillow '
               'Lanczos, enlarged back with FreeImage (8-bit, as WinIMerge). Lower is closer to the original except SSIMULACRA2. '
               '"CR closer" = share of pairs where Catmull-Rom is closer than Lanczos3 by that measure.\n')
    meas = [('flip96', 'ꟻLIP @96', False), ('flip48', 'ꟻLIP @48', False), ('ba_p3', 'Butteraugli 3-norm', False),
            ('ba_max', 'Butteraugli max', False), ('ssimu2', 'SSIMULACRA2', True), ('T_p99', 'WinMerge T_p99', False),
            ('overshoot_mean', 'overshoot (levels)', False)]
    a = d[d.enlarger == 'catmullrom'].set_index(['image', 'factor'])
    b = d[d.enlarger == 'lanczos3'].set_index(['image', 'factor'])
    j = a.join(b, lsuffix='_cr', rsuffix='_l3', how='inner')
    j['set'] = j['set_cr']
    rows = {}
    for grp, sel in (('synthetic', j[j.set == 'synth']), ('real', j[j.set == 'real']), ('all', j)):
        for m, lab, hb in meas:
            cr, l3 = sel[m + '_cr'], sel[m + '_l3']
            win = (cr > l3) if hb else (cr < l3)
            rows.setdefault(lab, {})[f'{grp}: Lanczos3 / Catmull-Rom'] = f'{l3.median():.3g} / {cr.median():.3g}'
            rows[lab][f'{grp}: CR closer'] = pct(win.mean())
    out.append(table(pd.DataFrame(rows).T, 'measure (median)'))
    t = j.groupby('factor').apply(lambda s: pd.Series({'ꟻLIP @96 CR closer': pct((s.flip96_cr < s.flip96_l3).mean()),
                                                         'Butteraugli 3-norm CR closer': pct((s.ba_p3_cr < s.ba_p3_l3).mean()),
                                                         'SSIMULACRA2 CR closer': pct((s.ssimu2_cr > s.ssimu2_l3).mean())}))
    out.append('\n### By factor\n')
    out.append(table(t, 'factor'))
    t = j.groupby(level='image').apply(lambda s: pd.Series({'ꟻLIP @96 CR closer': pct((s.flip96_cr < s.flip96_l3).mean()),
                                                              'Butteraugli 3-norm CR closer': pct((s.ba_p3_cr < s.ba_p3_l3).mean()),
                                                              'overshoot L3 / CR': f'{s.overshoot_mean_l3.mean():.2f} / {s.overshoot_mean_cr.mean():.2f}'}))
    out.append('\n### By picture (over the factors)\n')
    out.append(table(t, 'picture'))


def jhist(results, out):
    p = os.path.join(results, 'jpeg_history_test.csv')
    if not os.path.exists(p):
        return
    d = pd.read_csv(p)
    out.append('\n## Can a re-saved JPEG be recognised? (`harness/jpeg_history.py --test`)\n')
    out.append(f'{d.image.nunique()} masters × {d.history.nunique()} histories. "Flagged" = the ghost or the shifted-grid check finds an '
               'earlier save. On a one-time save a flag is a false alarm unless the master itself came from a JPEG: the q95 flags are '
               'the lion and Hokusai masters, crops of q≈90 JPEGs, found at their crop offsets (x+2, and x+5 y+1). The grid check '
               'needs textured blocks the decoder did not clip, which pure black-and-white art (the line art, the manga page) lacks.\n')
    order = ['q95', 'q90', 'q85', 'q80', 'q70', 'q75>q90', 'q60>q90', 'q80s>q90', 'q85s>q85', 'q90s>q90s>q90']
    t = d.groupby('history').agg(saves=('saves', 'first'), flagged=('flagged', 'mean'),
                                 ghost=('ghost', lambda s: pct((s != '[]').mean())),
                                 grid=('grids', lambda s: pct((s != '[]').mean())),
                                 grid_check_possible=('grid_usable', 'mean')).reindex([o for o in order if o in set(d.history)])
    t['flagged'] = t.flagged.map(pct)
    t['grid_check_possible'] = t.grid_check_possible.map(pct)
    t.columns = ['saves', 'flagged as saved more than once', 'by the ghost check', 'by the shifted-grid check', 'grid check possible']
    out.append(table(t, 'JPEG history'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', default=RESULTS)
    a = ap.parse_args()
    out = ['# Follow-up tables (generated by harness/followup_report.py)\n']
    tiny(a.results, out)
    blocksize(a.results, out)
    crl3(a.results, out)
    pixel(a.results, out)
    comp(a.results, out)
    jhist(a.results, out)
    path = os.path.join(a.results, 'tables_followup.md')
    open(path, 'w').write('\n'.join(out) + '\n')
    print('wrote', path)


if __name__ == '__main__':
    main()
