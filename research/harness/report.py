"""Turn the study CSVs into markdown tables (results/tables.md) for REPORT.md.

    python3 report.py [--results /home/user/research/results]
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd

UP_ORDER = ['nn_int_center', 'nn_int_topleft', 'nn', 'sharp_bilinear', 'fi_bilinear', 'fi_bspline', 'fi_mitchell',
            'fi_catmullrom', 'fi_catmullrom_f', 'fi_lanczos3', 'fi_lanczos3_f', 'ref_lanczos2_f', 'ref_lanczos4_f',
            'l3f_usm_r0.75_a0.5', 'l3f_usm_r1.0_a0.5']
DOWN_ORDER = ['down_area', 'down_fi_box8', 'down_fi_box', 'down_fi_bilinear', 'down_fi_bilinear8', 'down_fi_bspline',
              'down_fi_bicubic', 'down_fi_bicubic8', 'down_fi_catmullrom', 'down_fi_catmullrom8', 'down_fi_lanczos3',
              'down_fi_lanczos38', 'down_matched', 'down_matched8', 'down_matched8a', 'down_oracle']
# the three WinIMerge modes as the harness reproduces them (bit-identical to the C++ code)
MODES = [('nn_int_center', 'UP_NEAREST_INTEGER (NN, whole-number factor)'),
         ('fi_lanczos3', 'UP_SMOOTH (Lanczos3)'),
         ('down_matched8a', 'DOWN_MATCHED (shrink, matched filter)')]
TASK = ['set', 'image', 'edit', 'shrinker', 'factor', 'codec']
LABEL = {
    'nn_int_center': 'NN, whole-number factor, centred', 'nn_int_topleft': 'NN, whole-number factor, top-left',
    'nn': 'NN to exact size', 'sharp_bilinear': 'NN whole-number, then bilinear to size',
    'fi_bilinear': 'Bilinear', 'fi_bspline': 'B-spline', 'fi_mitchell': 'Mitchell (FreeImage "bicubic")',
    'fi_catmullrom': 'Catmull-Rom (8-bit)', 'fi_catmullrom_f': 'Catmull-Rom (float)',
    'fi_lanczos3': 'Lanczos3 (8-bit)', 'fi_lanczos3_f': 'Lanczos3 (float)',
    'ref_lanczos2_f': 'Lanczos2 (float)', 'ref_lanczos4_f': 'Lanczos4 (float)',
    'l3f_usm_r0.75_a0.5': 'Lanczos3 float + USM r0.75 50%', 'l3f_usm_r1.0_a0.5': 'Lanczos3 float + USM r1.0 50%',
    'down_area': 'Shrink original: area (OpenCV)', 'down_fi_box8': 'Shrink original: FreeImage box (8-bit)',
    'down_fi_box': 'Shrink original: box', 'down_fi_bilinear': 'Shrink original: bilinear',
    'down_fi_bspline': 'Shrink original: B-spline', 'down_fi_bicubic': 'Shrink original: Mitchell',
    'down_fi_catmullrom': 'Shrink original: Catmull-Rom', 'down_fi_lanczos3': 'Shrink original: Lanczos3',
    'down_fi_bilinear8': 'Shrink original: bilinear (8-bit)', 'down_fi_bicubic8': 'Shrink original: Mitchell (8-bit)',
    'down_fi_catmullrom8': 'Shrink original: Catmull-Rom (8-bit)', 'down_fi_lanczos38': 'Shrink original: Lanczos3 (8-bit)',
    'down_matched': 'Shrink original: best-matching FreeImage filter (float, 6 filters)',
    'down_matched8': 'Shrink original: matched filter, 5 FreeImage filters (8-bit), without area averaging',
    'down_matched8a': 'Shrink original: WinIMerge DOWN_MATCHED (5 FreeImage filters + area averaging)',
    'down_oracle': 'Shrink original: the true kernel (oracle)',
}


def load(results, exp):
    frames = []
    for f in sorted(glob.glob(os.path.join(results, f'{exp}_*.csv'))):
        d = pd.read_csv(f, low_memory=False)
        d['set'] = 'real' if f.endswith('_real.csv') else 'synth'
        frames.append(d)
    if not frames:
        return None
    d = pd.concat(frames, ignore_index=True)
    d['factor'] = d['factor'].astype(float)
    d['integer'] = d['factor'].isin([2.0, 3.0, 4.0])
    return d.replace([np.inf, -np.inf], np.nan)


def md(df, floatfmt='{:.3g}'):
    df = df.copy()
    cols = [str(c) for c in df.columns]
    out = ['| ' + ' | '.join([df.index.name or ''] + cols) + ' |', '|' + '---|' * (len(cols) + 1)]
    for idx, row in df.iterrows():
        cells = []
        for v in row.values:
            if isinstance(v, (float, np.floating)):
                cells.append('' if np.isnan(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        out.append('| ' + ' | '.join([LABEL.get(idx, str(idx))] + cells) + ' |')
    return '\n'.join(out)


def order(df, names):
    return df.reindex([n for n in names if n in df.index])


def complete(d, cands):
    """Rows of the candidates in `cands`, restricted to the tasks that have all of them, so that
    every row of a table is computed on the same pairs."""
    present = [c for c in cands if c in set(d.candidate.unique())]
    sub = d[d.candidate.isin(present)]
    n = sub.groupby(TASK).candidate.transform('nunique')
    return sub[n == len(present)]


def ntasks(d):
    return d.groupby(TASK).ngroups


def spurious_tables(d, out):
    d = d[d.edit == 'none']
    for codec in ['png', 'jpg85']:
        dc = d[d.codec == codec]
        if dc.empty:
            continue
        for metric, title, fmt in [('share_T16', 'share of 8×8 blocks marked at threshold 16 (lower = cleaner)', '{:.1%}'),
                                   ('T_p99', 'colour-distance threshold that leaves ≤1 % of blocks marked (lower = closer)', '{:.0f}'),
                                   ('psnr', 'PSNR in dB (higher = closer)', '{:.1f}')]:
            for st in ['synth', 'real']:
                ds = dc[dc.set == st]
                if ds.empty:
                    continue
                du = complete(ds, UP_ORDER)
                up = order(du.groupby(['candidate', 'factor'])[metric].median().unstack(), UP_ORDER)
                out.append(f'\n#### Spurious differences, {st} images, small copy saved as {codec}: median {title}\n')
                out.append(f'Median over {du.image.nunique()} images × {du.shrinker.nunique()} shrinking kernels '
                           f'({ntasks(du)} pairs); enlarged to the original size.\n')
                out.append(md(up, fmt))
                dd = complete(ds, DOWN_ORDER)
                if not dd.empty and metric != 'psnr':
                    dn = order(dd.groupby(['candidate', 'factor'])[metric].median().unstack(), DOWN_ORDER)
                    out.append(f'\nThe same, comparing at the small size (the original shrunk instead of the copy enlarged; '
                               f'{ntasks(dd)} pairs):\n')
                    out.append(md(dn, fmt))
    # rank of each enlarger per task by T_p99 (lower better)
    du = d[d.candidate.isin(UP_ORDER) & ~d.candidate.isin(['nn_int_center', 'nn_int_topleft'])].copy()
    du['rank'] = du.groupby(['set', 'image', 'shrinker', 'factor', 'codec'])['T_p99'].rank(method='average')
    r = du.groupby(['candidate', 'set'])['rank'].mean().unstack()
    out.append('\n#### Mean rank by T_p99 among the enlargers (1 = closest), all factors and codecs\n')
    out.append(md(order(r, UP_ORDER), '{:.2f}'))


def matched_kernel_table(d, out):
    for cand, what in [('down_matched8a', 'WinIMerge rule: 5 FreeImage filters on the 8-bit path + area averaging'),
                       ('down_matched8', '5 FreeImage filters on the 8-bit path'), ('down_matched', 'float path, 6 filters')]:
        dm = d[(d.candidate == cand) & (d.edit == 'none')]
        if dm.empty:
            continue
        t = dm.groupby(['shrinker', 'matched_kernel']).size().unstack(fill_value=0)
        out.append(f'\n#### Which FreeImage filter best reproduces each shrinker ({what}; count of pairs, all factors and codecs)\n')
        t.index.name = 'shrinker'
        out.append(md(t, '{:.0f}'))


def modes_table(d, out):
    """The headline tables: the three WinIMerge modes on unedited pairs, by factor."""
    d = complete(d[d.edit == 'none'], [c for c, _ in MODES])
    if d.empty:
        return
    lab = dict(MODES)
    for metric, title, fmt in [('T_p99', 'colour-distance threshold needed to leave ≤1 % of 8×8 blocks marked (T_p99; lower = better)', '{:.0f}'),
                               ('share_T16', 'share of 8×8 blocks marked at threshold 16 (lower = better)', '{:.1%}')]:
        for st in ['synth', 'real']:
            ds = d[d.set == st]
            if ds.empty:
                continue
            t = ds.groupby(['candidate', 'codec', 'factor'])[metric].median().unstack()
            t = t.reindex([(c, k) for c, _ in MODES for k in ['png', 'jpg85'] if (c, k) in t.index])
            t.index = [f'{lab[c]}, copy {k}' for c, k in t.index]
            t.index.name = 'mode, small copy saved as'
            out.append(f'\n#### WinIMerge modes, {st} images: median {title}\n')
            out.append(f'{ds.image.nunique()} images × {ds.shrinker.nunique()} shrinking kernels ({ntasks(ds)} pairs per mode). '
                       'NN whole-number leaves part of the canvas uncovered at 1.25, 1.5 and 2.5, which WinMerge marks as different '
                       '(T_p99 infinite, shown empty).\n')
            out.append(md(t, fmt))


HEAVY_UP = ['nn_int_center', 'nn', 'sharp_bilinear', 'fi_bilinear', 'fi_mitchell', 'fi_catmullrom_f', 'fi_lanczos3',
            'fi_lanczos3_f', 'l3f_usm_r0.75_a0.5', 'l3f_usm_r1.0_a0.5']
HEAVY_DOWN = ['down_area', 'down_fi_catmullrom8', 'down_matched8', 'down_matched8a', 'down_oracle']
HEAVY_COLS = [('T_p99', 'T_p99', False), ('flip_mean_ppd96', 'ꟻLIP mean @96 ppd', False),
              ('flip_p99_ppd96', 'ꟻLIP p99 @96 ppd', False), ('flip_mean_ppd48', 'ꟻLIP mean @48 ppd (2× zoom)', False),
              ('flip_p99_ppd48', 'ꟻLIP p99 @48 ppd', False), ('ba_max', 'Butteraugli max', False),
              ('ba_p3', 'Butteraugli 3-norm', False), ('ssimu2', 'SSIMULACRA2', True),
              ('ssim_worst64', 'worst 64-px tile SSIM', True)]


def heavy_tables(d, out):
    d = d[d.edit == 'none']
    for st in ['synth', 'real']:
        for codec in ['png', 'jpg85']:
            ds = d[(d.set == st) & (d.codec == codec)]
            if ds.empty:
                continue
            for integer in [True, False]:
                di = ds[ds.integer == integer]
                cands = HEAVY_UP + HEAVY_DOWN if integer else [c for c in HEAVY_UP + HEAVY_DOWN if c != 'nn_int_center']
                di = complete(di, cands)
                if di.empty:
                    continue
                t = pd.DataFrame({lab: di.groupby('candidate')[c].median() for c, lab, _ in HEAVY_COLS})
                t = order(t, cands)
                out.append(f'\n#### Perceptual metrics, {st} images, {codec}, {"whole-number factors (2, 3)" if integer else "factor 2.5"}: medians over {ntasks(di)} pairs\n')
                out.append('ꟻLIP/Butteraugli/T_p99 lower = closer; SSIMULACRA2/SSIM higher = closer. Enlargers are compared with the '
                           'original at its size, the shrink rows at the copy\'s size. At 2.5 whole-number NN shows the copy at 80 % of '
                           'the original\'s size, so nothing lines up (left out).\n')
                out.append(md(t, '{:.4g}'))
    # mean rank of each enlarger by each metric, within each pair (whole-number factors: all enlargers)
    for st in ['synth', 'real']:
        ds = complete(d[(d.set == st) & d.integer], HEAVY_UP)
        if ds.empty:
            continue
        ranks = {}
        for c, lab, higher in HEAVY_COLS:
            v = -ds[c] if higher else ds[c]
            ranks[lab] = v.groupby([ds[k] for k in TASK]).rank(method='average').groupby(ds.candidate).mean()
        t = order(pd.DataFrame(ranks), HEAVY_UP)
        out.append(f'\n#### Mean rank of the enlargers by each measure ({st}, whole-number factors, PNG and JPEG q85; '
                   f'{ntasks(ds)} pairs; 1 = closest)\n')
        out.append(md(t, '{:.1f}'))
    # do the perceptual metrics agree with WinMerge's own outcome?
    for scope, cands in [('enlargers only', HEAVY_UP[1:]), ('all candidates incl. the shrink', HEAVY_UP[1:] + HEAVY_DOWN)]:
        rows = []
        for key, g in d[d.candidate.isin(cands)].groupby(TASK):
            g = g.dropna(subset=['T_p99'])
            if len(g) < 4:
                continue
            r = {'set': key[0]}
            for c, lab, higher in HEAVY_COLS[1:]:
                v = -g[c] if higher else g[c]
                if v.notna().sum() >= 4:
                    r[lab] = g['T_p99'].rank().corr(v.rank())
            rows.append(r)
        if not rows:
            continue
        t = pd.DataFrame(rows).groupby('set').mean().T
        t.index.name = 'measure'
        out.append(f'\n#### Agreement with WinMerge\'s outcome: mean within-pair Spearman correlation with T_p99 ({scope})\n')
        out.append(md(t, '{:.2f}'))


def edit_tables(d, out):
    d = d[d.edit != 'none']
    if d.empty:
        return
    short = ['nn_int_center', 'nn', 'fi_bilinear', 'fi_catmullrom_f', 'fi_lanczos3', 'l3f_usm_r1.0_a0.5',
             'down_area', 'down_fi_catmullrom8', 'down_matched8', 'down_matched8a', 'down_oracle']
    for st in ['synth', 'real']:
        ds = complete(d[d.set == st], UP_ORDER + DOWN_ORDER)
        if ds.empty:
            continue
        t = pd.DataFrame({
            'edit blocks found at 1 % false-alarm threshold': ds.groupby('candidate')['det_T1'].mean(),
            'edits visible at all (≥1 block)': ds.groupby('candidate')['any_T1'].mean(),
            'edits visible at 0.1 % threshold': ds.groupby('candidate')['any_T01'].mean(),
            'median unchanged blocks louder than the edit': ds.groupby('candidate')['outrank'].median(),
        })
        out.append(f'\n#### Can an edit still be seen? {st} images (means over {ds.image.nunique()} images × {ds.edit.nunique()} edits × '
                   f'factors × kernels × codecs; {ntasks(ds)} edited pairs)\n')
        out.append(md(order(t, UP_ORDER + DOWN_ORDER), '{:.3g}'))
        t2 = ds.groupby(['candidate', 'edit'])['any_T1'].mean().unstack()
        out.append(f'\nShare of edited pairs where the edit shows at the 1 % threshold, by edit ({st}):\n')
        out.append(md(order(t2, short), '{:.0%}'))
        t3 = ds.groupby(['candidate', 'factor'])['any_T1'].mean().unstack()
        out.append(f'\nThe same by factor ({st}):\n')
        out.append(md(order(t3, short), '{:.0%}'))
        t4 = ds.groupby(['candidate', 'codec'])['any_T1'].mean().unstack()
        out.append(f'\nThe same by codec of the copy ({st}):\n')
        out.append(md(order(t4, short), '{:.0%}'))


def usm_tables(d, out):
    if d is None:
        return
    for st in ['synth', 'real']:
        ds = d[d.set == st]
        if ds.empty:
            continue
        base = ds[ds.edit == 'none']
        rows = []
        for c in sorted(base.candidate.unique()):
            b = base[base.candidate == c]
            e = ds[(ds.edit != 'none') & (ds.candidate == c)]
            rows.append(dict(candidate=c, share_T16=b.share_T16.median(), T_p99=b.T_p99.median(), psnr=b.psnr.median(),
                             det=e.det_T1.mean() if not e.empty else np.nan, vis=e.any_T1.mean() if not e.empty else np.nan))
        t = pd.DataFrame(rows).set_index('candidate')
        t.columns = ['blocks marked @T16', 'T_p99', 'PSNR', 'edit blocks found', 'edits visible']
        out.append(f'\n#### Unsharp mask after Lanczos3/Catmull-Rom (float), {st} images: medians over images × kernels × '
                   f'factors 1.5/2/3 × png/jpg85 ({ntasks(base)} unedited pairs, {ntasks(ds[ds.edit != "none"])} edited)\n')
        out.append(md(t, '{:.3g}'))


CODECS = ['png', 'jpg95', 'jpg85', 'jpg85_444', 'jpg75', 'jpg60', 'webp90', 'webp75']
CODEC_CANDS = ['nn_int_center', 'fi_lanczos3', 'l3f_usm_r1.0_a0.5', 'down_area', 'down_fi_catmullrom8', 'down_matched8a',
               'down_oracle']


def codec_tables(d, out):
    if d is None:
        return
    d = d[d.edit == 'none']
    for st in ['synth', 'real']:
        ds = complete(d[d.set == st], CODEC_CANDS)
        if ds.empty:
            continue
        cols = [c for c in CODECS if c in set(ds.codec)]
        for metric, fmt in [('T_p99', '{:.0f}'), ('share_T16', '{:.1%}'), ('share_T64', '{:.1%}')]:
            t = ds.groupby(['candidate', 'codec'])[metric].median().unstack()[cols]
            out.append(f'\n#### Codec of the small copy, {st} images: median {metric} ({ntasks(ds) // len(cols)} pairs per codec; '
                       'factors 2 and 2.5, Pillow Lanczos and area copies)\n')
            out.append(md(order(t, CODEC_CANDS), fmt))
        dm = ds[ds.candidate == 'down_matched8a']
        g = dm.groupby('codec')
        t = pd.DataFrame({'T_p99 median': g.T_p99.median(), 'T_p99 75th pct': g.T_p99.quantile(0.75),
                          'T_p99 90th pct': g.T_p99.quantile(0.9), 'T_p99 max': g.T_p99.max(),
                          'blocks @T32': g.share_T32.median(), 'blocks @T64': g.share_T64.median(),
                          'pairs ≤1 % @T64': g.T_p99.apply(lambda v: (v <= 64).mean())}).reindex(cols)
        t.index.name = 'copy saved as'
        out.append(f'\n#### Threshold guidance for DOWN_MATCHED by codec ({st}): distribution of T_p99 over pairs\n')
        out.append(md(t, '{:.3g}'))


QS_CODECS = ['jpg85', 'jpg85_qs3', 'jpg85_qs6', 'jpg60', 'jpg60_qs3', 'jpg60_qs6']
QS_CANDS = ['nn', 'fi_lanczos3_f', 'l3f_usm_r1.0_a0.5', 'down_area', 'down_matched8a', 'down_oracle']


def jpegqs_tables(d, out):
    if d is None:
        return
    for st in ['synth', 'real']:
        ds = complete(d[d.set == st], QS_CANDS)
        if ds.empty:
            continue
        cols = [c for c in QS_CODECS if c in set(ds.codec)]
        base = ds[ds.edit == 'none']
        ed = ds[ds.edit != 'none']
        for metric, fmt, src, agg in [('T_p99', '{:.0f}', base, 'median'), ('share_T16', '{:.1%}', base, 'median'),
                                      ('share_T32', '{:.1%}', base, 'median'), ('psnr', '{:.1f}', base, 'median'),
                                      ('any_T1', '{:.0%}', ed, 'mean'), ('det_T1', '{:.0%}', ed, 'mean')]:
            if src.empty:
                continue
            t = src.groupby(['candidate', 'codec'])[metric].agg(agg).unstack()[cols]
            what = {'any_T1': 'share of edits visible at the 1 % threshold', 'det_T1': 'share of the edit\'s blocks marked'}.get(metric, f'median {metric}')
            out.append(f'\n#### jpegQS-restored copies, {st} images: {what} ({ntasks(src) // len(cols)} '
                       f'{"edited" if src is ed else "unedited"} pairs per codec)\n')
            out.append(md(order(t, QS_CANDS), fmt))


LIN_CANDS = ['fi_lanczos3_f', 'lin_lanczos3_f', 'fi_catmullrom_f', 'lin_catmullrom_f']
LABEL.update({'lin_lanczos3_f': 'Lanczos3 in linear light (float)', 'lin_catmullrom_f': 'Catmull-Rom in linear light (float)'})


def linear_tables(d, out):
    if d is None:
        return
    for st in ['synth', 'real']:
        ds = complete(d[d.set == st], LIN_CANDS)
        if ds.empty:
            continue
        base = ds[ds.edit == 'none']
        ed = ds[ds.edit != 'none']
        for metric, fmt, src, agg in [('T_p99', '{:.0f}', base, 'median'), ('share_T16', '{:.1%}', base, 'median'),
                                      ('any_T1', '{:.0%}', ed, 'mean')]:
            if src.empty:
                continue
            t = src.groupby(['candidate', 'shrinker'])[metric].agg(agg).unstack()
            what = 'share of edits visible at the 1 % threshold' if metric == 'any_T1' else f'median {metric}'
            out.append(f'\n#### Enlarging in linear light, {st} images: {what}, by how the copy was made '
                       f'({ntasks(src)} {"edited" if src is ed else "unedited"} pairs; PNG copies, factors 2, 2.5, 3)\n')
            out.append(md(order(t, LIN_CANDS), fmt))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', default='/home/user/research/results')
    a = ap.parse_args()
    out = ['# Result tables (generated by harness/report.py)\n']
    sp = load(a.results, 'spurious')
    if sp is not None:
        out.append('\n## Spurious differences (unedited pairs)\n')
        modes_table(sp, out)
        spurious_tables(sp, out)
        matched_kernel_table(sp, out)
    hv = load(a.results, 'heavy')
    if hv is not None:
        out.append('\n## Perceptual metrics\n')
        heavy_tables(hv, out)
    ed = load(a.results, 'edits')
    if ed is not None:
        out.append('\n## Edit detectability\n')
        edit_tables(ed, out)
    us = load(a.results, 'usm')
    if us is not None:
        out.append('\n## Unsharp-mask sweep\n')
        usm_tables(us, out)
    co = load(a.results, 'codec')
    if co is not None:
        out.append('\n## Codec of the small copy\n')
        codec_tables(co, out)
    qs = load(a.results, 'jpegqs')
    if qs is not None:
        out.append('\n## Restoring the small JPEG with jpegQS first\n')
        jpegqs_tables(qs, out)
    li = load(a.results, 'linear')
    if li is not None:
        out.append('\n## Enlarging in linear light\n')
        linear_tables(li, out)
    path = os.path.join(a.results, 'tables.md')
    open(path, 'w').write('\n'.join(out) + '\n')
    print('wrote', path, sum(len(x) for x in out), 'chars')


if __name__ == '__main__':
    main()
