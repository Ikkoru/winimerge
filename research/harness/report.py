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


def heavy_tables(d, out):
    d = d[d.edit == 'none']
    cols = [('flip_mean_ppd96', 'ꟻLIP mean @96 ppd', '{:.4f}'), ('flip_p99_ppd96', 'ꟻLIP p99 @96 ppd', '{:.3f}'),
            ('flip_mean_ppd48', 'ꟻLIP mean @48 ppd (2× zoom)', '{:.4f}'), ('ba_max', 'Butteraugli max', '{:.2f}'),
            ('ba_p3', 'Butteraugli 3-norm', '{:.3f}'), ('ssimu2', 'SSIMULACRA2', '{:.1f}'), ('ssim_worst64', 'worst 64-px tile SSIM', '{:.3f}')]
    for st in ['synth', 'real']:
        for codec in ['png', 'jpg85']:
            ds = d[(d.set == st) & (d.codec == codec)]
            if ds.empty:
                continue
            for integer in [True, False]:
                di = ds[ds.integer == integer]
                if di.empty:
                    continue
                t = pd.DataFrame({lab: di.groupby('candidate')[c].median() for c, lab, _ in cols})
                t = order(t, UP_ORDER)
                out.append(f'\n#### Perceptual metrics, {st} images, {codec}, {"whole-number factors (2, 3)" if integer else "factor 2.5"}: medians\n')
                out.append(f'{di.image.nunique()} images × {di.shrinker.nunique()} kernels. ꟻLIP/Butteraugli lower = closer; SSIMULACRA2/SSIM higher = closer. NN-whole-number at 2.5 is measured on the overlap only.\n')
                lines = md(t, '{:.4g}')
                out.append(lines)


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
    base = d[d.edit == 'none']
    rows = []
    for c in sorted(base.candidate.unique()):
        b = base[base.candidate == c]
        e = d[(d.edit != 'none') & (d.candidate == c)]
        rows.append(dict(candidate=c, share_T16=b.share_T16.median(), T_p99=b.T_p99.median(), psnr=b.psnr.median(),
                         det=e.det_T1.mean() if not e.empty else np.nan, vis=e.any_T1.mean() if not e.empty else np.nan))
    t = pd.DataFrame(rows).set_index('candidate')
    t.columns = ['blocks marked @T16', 'T_p99', 'PSNR', 'edit blocks found', 'edits visible']
    out.append('\n#### Unsharp mask after Lanczos3/Catmull-Rom (float), medians over images × kernels × factors 1.5/2/3 × png/jpg85\n')
    out.append(md(t, '{:.3g}'))


def codec_tables(d, out):
    if d is None:
        return
    for metric, fmt in [('T_p99', '{:.0f}'), ('psnr', '{:.1f}')]:
        t = d.groupby(['candidate', 'codec'])[metric].median().unstack()
        t = t[[c for c in ['png', 'jpg95', 'jpg85', 'jpg85_444', 'jpg75', 'jpg60', 'webp90', 'webp75'] if c in t.columns]]
        out.append(f'\n#### Effect of the small copy\'s codec: median {metric}\n')
        out.append(md(order(t, UP_ORDER + DOWN_ORDER), fmt))


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
    path = os.path.join(a.results, 'tables.md')
    open(path, 'w').write('\n'.join(out) + '\n')
    print('wrote', path, sum(len(x) for x in out), 'chars')


if __name__ == '__main__':
    main()
