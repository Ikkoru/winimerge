"""Charts for REPORT.md (PNG, light background) from the study CSVs.

    python3 charts.py [--results /home/user/research/results] [--out /home/user/research/charts]

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

SURFACE, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df'
SLOTS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
MODES = [('nn_int_center', 'Enlarge, whole-number NN'),
         ('fi_lanczos3_f', 'Enlarge, Lanczos3'),
         ('down_matched8', 'Shrink, matched filter')]
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', default='/home/user/research/results')
    ap.add_argument('--out', default='/home/user/research/charts')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    sp = report.load(a.results, 'spurious')
    if sp is not None:
        print(modes_chart(sp, a.out))
        print(modes_chart(sp, a.out, 'share_T16', 'blocks marked at threshold 16 (%)', 'modes_share16.png', pct=True))
    ed = report.load(a.results, 'edits')
    if ed is not None:
        print(edits_chart(ed, a.out))


if __name__ == '__main__':
    main()
