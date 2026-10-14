"""Charts for REPORT.md (PNG, light background) from the study CSVs.

    python3 charts.py [--results ../results] [--out ../charts]

Colours: the dataviz reference palette, categorical slots in fixed order (slot 1 = first mode, ...),
so a mode keeps its colour in every chart.
"""
import argparse
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import report
from paths import RESULTS, ROOT, TESTSET  # noqa: E402

SURFACE, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df'
SLOTS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
MODES = [('nn_int_center', 'Enlarge, whole-number NN'),
         ('fi_lanczos3', 'Enlarge, Lanczos3'),
         ('down_matched8a', 'Shrink, matched filter')]
COLOR = {c: SLOTS[i] for i, (c, _) in enumerate(MODES)}
FACTORS = [1.25, 1.5, 2.0, 2.5, 3.0, 4.0]


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis='y', color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def modes_chart(sp, out, metric='T_p99', ylabel='threshold needed (T_p99)', fname='modes_tp99.png', pct=False):
    d = report.complete(sp[sp.edit == 'none'], [c for c, _ in MODES])
    sets = [s for s in ['synth', 'real'] if (d.set == s).any()]
    codecs = ['png', 'jpg85']
    fig, axes = plt.subplots(len(sets), 2, figsize=(9, 3.4 * len(sets)), sharey=True, squeeze=False)
    fig.patch.set_facecolor(SURFACE)
    for i, st in enumerate(sets):
        for j, cod in enumerate(codecs):
            ax = axes[i][j]
            style(ax)
            x = d[(d.set == st) & (d.codec == cod)]
            for c, lab in MODES:
                y = x[x.candidate == c].groupby('factor')[metric].median().reindex(FACTORS)
                if pct:
                    y = y * 100
                ok = np.isfinite(y.values)
                ax.plot(np.array(FACTORS)[ok], y.values[ok], color=COLOR[c], linewidth=2,
                        marker='o', markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.5, label=lab,
                        linestyle='-' if c != 'nn_int_center' else 'none')
                if c == 'nn_int_center':   # whole-number factors only: dots joined by a thin dashed line
                    ax.plot(np.array(FACTORS)[ok], y.values[ok], color=COLOR[c], linewidth=1, linestyle=':')
            if metric == 'T_p99':   # the highest threshold WinIMerge's menu offers
                ax.axhline(64, color=INK2, linewidth=1, linestyle=(0, (4, 3)), zorder=1)
                ax.text(4.12, 64, 'menu max 64', fontsize=8, color=INK2, ha='right', va='bottom')
            ax.set_xticks(FACTORS)
            ax.set_xticklabels(['1.25', '1.5', '2', '2.5', '3', '4'])
            ax.set_xlim(1.1, 4.15)
            name = {'png': 'copy saved as PNG', 'jpg85': 'copy saved as JPEG q85'}[cod]
            ax.set_title(f'{"Synthetic" if st == "synth" else "Real"} images, {name}', fontsize=10, color=INK, loc='left')
            if j == 0:
                ax.set_ylabel(ylabel, fontsize=9, color=INK2)
            if i == len(sets) - 1:
                ax.set_xlabel('size factor between original and copy', fontsize=9, color=INK2)
    h, l = axes[0][0].get_legend_handles_labels()
    keep = [k for k, t in enumerate(l) if t]
    fig.legend([h[k] for k in keep], [l[k] for k in keep], loc='upper center', ncol=3, frameon=False, fontsize=9,
               labelcolor=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    path = os.path.join(out, fname)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


def edits_chart(ed, out):
    d = ed[ed.edit != 'none']
    cands = MODES + [('nn', 'Enlarge, NN to exact size'), ('down_oracle', 'Shrink, true filter (upper bound)')]
    rows = []
    for st in ['synth', 'real']:
        x = report.complete(d[d.set == st], [c for c, _ in cands])
        if x.empty:
            continue
        for c, lab in cands:
            y = x[x.candidate == c]
            rows.append((st, c, lab, y.any_T1.mean() * 100, y.det_T1.mean() * 100))
    if not rows:
        return None
    t = pd.DataFrame(rows, columns=['set', 'cand', 'label', 'visible', 'found'])
    sets = list(dict.fromkeys(t.set))
    fig, axes = plt.subplots(1, len(sets), figsize=(max(7.0, 4.8 * len(sets)), 3.4), sharey=True, squeeze=False)
    fig.patch.set_facecolor(SURFACE)
    colors = [SLOTS[0], SLOTS[1], SLOTS[2], '#9a9993', '#c3c2b7']
    for i, st in enumerate(sets):
        ax = axes[0][i]
        style(ax)
        ax.grid(axis='y', visible=False)
        ax.grid(axis='x', color=GRID, linewidth=0.8)
        x = t[t.set == st].reset_index(drop=True)
        ypos = np.arange(len(x))[::-1]
        ax.barh(ypos, x.visible, color=colors[:len(x)], height=0.62, edgecolor=SURFACE, linewidth=2)
        for yy, v in zip(ypos, x.visible):
            ax.text(v + 1.5, yy, f'{v:.0f}%', va='center', fontsize=9, color=INK)
        ax.set_yticks(ypos)
        ax.set_yticklabels(x.label, fontsize=9, color=INK)
        ax.set_xlim(0, 110)
        ax.set_xticks([0, 25, 50, 75, 100])
        ax.set_title(f'{"Synthetic" if st == "synth" else "Real"} images', fontsize=10, color=INK, loc='left')
        ax.set_xlabel('edited pairs where the edit shows (%)', fontsize=9, color=INK2)
    fig.suptitle('Is the edit still visible? (threshold set so that 1 % of unedited blocks are marked)',
                 fontsize=10, color=INK, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    path = os.path.join(out, 'edits_visible.png')
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


RANK_CANDS = [('nn_int_center', 'NN, whole-number factor'), ('nn', 'NN to exact size'),
              ('sharp_bilinear', 'NN whole-number, then bilinear'), ('fi_bilinear', 'Bilinear'),
              ('fi_mitchell', 'Mitchell'), ('fi_catmullrom_f', 'Catmull-Rom'), ('fi_lanczos3', 'Lanczos3 (UP_SMOOTH)'),
              ('l3f_usm_r1.0_a0.5', 'Lanczos3 + unsharp σ1 50 %')]
RANK_MEASURES = [('T_p99', 'WinMerge threshold needed (T_p99)', False, 'o'),
                 ('flip_mean_ppd96', 'ꟻLIP mean, 96 ppd', False, 's'),
                 ('flip_mean_ppd48', 'ꟻLIP mean, 48 ppd', False, 'D'),
                 ('ba_p3', 'Butteraugli 3-norm', False, '^'),
                 ('ssimu2', 'SSIMULACRA2', True, 'v')]


def ranks_chart(hv, out):
    """Mean rank of each enlarger by each measure, within each unedited pair at whole-number factors."""
    d = hv[(hv.edit == 'none') & hv.integer]
    sets = [st for st in ['synth', 'real'] if (d.set == st).any()]
    if not sets:
        return None
    fig, axes = plt.subplots(1, len(sets), figsize=(max(7.5, 5.0 * len(sets) + 2.0), 4.6), sharey=True, squeeze=False)
    fig.patch.set_facecolor(SURFACE)
    names = [c for c, _ in RANK_CANDS]
    for i, st in enumerate(sets):
        ax = axes[0][i]
        style(ax)
        ax.grid(axis='y', visible=False)
        ax.grid(axis='x', color=GRID, linewidth=0.8)
        x = report.complete(d[d.set == st], names)
        keys = [x[k] for k in report.TASK]
        ypos = np.arange(len(names))[::-1]
        for j, (m, lab, higher, marker) in enumerate(RANK_MEASURES):
            v = -x[m] if higher else x[m]
            r = v.groupby(keys).rank(method='average').groupby(x.candidate).mean().reindex(names)
            off = (j - (len(RANK_MEASURES) - 1) / 2) * 0.13
            ax.scatter(r.values, ypos + off, s=46, marker=marker, color=SLOTS[j], edgecolor=SURFACE, linewidth=1.2,
                       label=lab, zorder=3)
        ax.set_yticks(ypos)
        ax.set_yticklabels([lab for _, lab in RANK_CANDS], fontsize=9, color=INK)
        ax.set_xlim(0.5, len(names) + 0.5)
        ax.set_xticks(range(1, len(names) + 1))
        ax.set_xlabel('mean rank within each pair (1 = closest to the original)', fontsize=9, color=INK2)
        ax.set_title(f'{"Synthetic" if st == "synth" else "Real"} images, 2× and 3× ({report.ntasks(x)} pairs)',
                     fontsize=10, color=INK, loc='left')
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=3, frameon=False, fontsize=8.5, labelcolor=INK,
               bbox_to_anchor=(0.5, 0.0))
    fig.suptitle('Which enlarger is closest? It depends on the measure, and on the picture',
                 fontsize=10, color=INK, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0.12, 1, 0.95))
    path = os.path.join(out, 'enlargers_by_measure.png')
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


CODEC_ORDER = [('png', 'PNG'), ('jpg95', 'JPEG q95'), ('jpg85_444', 'JPEG q85 4:4:4'), ('jpg85', 'JPEG q85'),
               ('jpg75', 'JPEG q75'), ('jpg60', 'JPEG q60'), ('webp90', 'WebP q90'), ('webp75', 'WebP q75')]


def codec_chart(co, out):
    """Threshold the matched shrink needs, by how the copy was saved (median and 25th–90th percentile)."""
    d = report.complete(co[co.edit == 'none'], ['down_matched8a', 'fi_lanczos3'])
    sets = [st for st in ['synth', 'real'] if (d.set == st).any()]
    if not sets:
        return None
    fig, axes = plt.subplots(1, len(sets), figsize=(max(7.5, 5.4 * len(sets)), 4.2), sharey=True, squeeze=False)
    fig.patch.set_facecolor(SURFACE)
    for i, st in enumerate(sets):
        ax = axes[0][i]
        style(ax)
        x = d[d.set == st]
        codecs = [(c, lab) for c, lab in CODEC_ORDER if (x.codec == c).any()]
        xpos = np.arange(len(codecs))
        for c, color, lab, dx in [('down_matched8a', SLOTS[2], 'Shrink, matched filter', -0.12),
                                  ('fi_lanczos3', SLOTS[1], 'Enlarge, Lanczos3', 0.12)]:
            g = x[x.candidate == c].groupby('codec').T_p99
            med = g.median().reindex([k for k, _ in codecs])
            lo = g.quantile(0.25).reindex(med.index)
            hi = g.quantile(0.9).reindex(med.index)
            ax.vlines(xpos + dx, lo, hi, color=color, linewidth=2, alpha=0.55)
            ax.scatter(xpos + dx, med, s=48, color=color, edgecolor=SURFACE, linewidth=1.2, zorder=3, label=lab)
            if c == 'down_matched8a':
                for xx, v in zip(xpos + dx, med.values):
                    ax.text(xx - 0.1, v, f'{v:.0f}', ha='right', va='center', fontsize=8, color=INK)
        ax.axhline(64, color=INK2, linewidth=1, linestyle='--')
        ax.text(len(codecs) - 0.5, 66, 'highest menu value (64)', ha='right', va='bottom', fontsize=8, color=INK2)
        ax.set_xticks(xpos)
        ax.set_xticklabels([lab for _, lab in codecs], fontsize=8.5, color=INK, rotation=30, ha='right')
        ax.set_ylabel('threshold needed (T_p99)', fontsize=9, color=INK2)
        ax.set_title(f'{"Synthetic" if st == "synth" else "Real"} images', fontsize=10, color=INK, loc='left')
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper left', bbox_to_anchor=(0.01, 0.9), ncol=2, frameon=False, fontsize=8.5,
               labelcolor=INK)
    fig.suptitle('Threshold needed before ≤ 1 % of blocks are marked, by how the copy was saved\n'
                 '(dot: median; line: 25th to 90th percentile of the pairs)', fontsize=10, color=INK, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    path = os.path.join(out, 'codec_threshold.png')
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', default=RESULTS)
    ap.add_argument('--out', default=os.path.join(ROOT, 'charts'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    sp = report.load(a.results, 'spurious')
    if sp is not None:
        print(modes_chart(sp, a.out))
        print(modes_chart(sp, a.out, 'share_T16', 'blocks marked at threshold 16 (%)', 'modes_share16.png', pct=True))
    ed = report.load(a.results, 'edits')
    if ed is not None:
        print(edits_chart(ed, a.out))
    hv = report.load(a.results, 'heavy')
    if hv is not None:
        print(ranks_chart(hv, a.out))
    co = report.load(a.results, 'codec')
    if co is not None:
        print(codec_chart(co, a.out))


if __name__ == '__main__':
    main()
