"""Spot check: can WinIMerge's matched shrink reproduce copies made by ImageMagick (6.9, Q16)?

    python3 im_spotcheck.py [--jobs 1] [--out ../results/im_spotcheck.csv]

ImageMagick is behind many websites' thumbnails (WordPress's Imagick editor, PHP/Ruby/Python wrappers).
Recipes (sRGB, as ImageMagick resizes by default):
  im_default    convert -resize WxH!                     (Lanczos when shrinking; 16-bit intermediate)
  im_catrom     -filter Catrom -resize WxH!
  wp_png        WordPress's thumbnail_image() (class-wp-image-editor-imagick.php, read 2026-10-14):
                Triangle filter with filter:support 2.0 (a tent twice as wide as bilinear's), PNG output
  wp_jpeg       the same for JPEG output: then unsharpMaskImage(0.25, 0.25, 8, 0.065), quality 82 (the
                default). (WordPress also point-samples to 5x the target first when the area ratio is
                below 0.111, i.e. beyond 3x per axis: not reached here.)
  im_linear     -colorspace RGB -resize WxH! -colorspace sRGB   (resized in linear light, as IM's docs advise)
Synthetic set, factors 2, 2.5, 3, PNG copies (wp_jpeg: JPEG). For each copy: the filter WinIMerge's rule picks, the
threshold needed (T_p99) for the matched shrink, for the best FreeImage filter alone, and for Lanczos3
enlargement.
"""
import argparse
import os
import subprocess
import tempfile
from multiprocessing import Pool

import numpy as np
import pandas as pd
from PIL import Image

import fi
import metrics as M
import resample as R
import study as S
from paths import RESULTS, ROOT, TESTSET

IMAGES = ['synth_flatcolor', 'synth_lineart', 'synth_manga', 'synth_painterly', 'synth_text_ui', 'synth_pixelart',
          'synth_zoneplate']
RECIPES = {
    'im_default': ['{size}'],
    'im_catrom': ['-filter', 'Catrom', '{size}'],
    'wp_png': ['-define', 'filter:support=2.0', '-filter', 'Triangle', '{size}'],
    'wp_jpeg': ['-define', 'filter:support=2.0', '-filter', 'Triangle', '{size}', '-unsharp', '0.25x0.25+8+0.065',
                '-quality', '82'],
    'im_linear': ['-colorspace', 'RGB', '{size}', '-colorspace', 'sRGB'],
}


def im_resize(src_path, w, h, recipe, td):
    jpeg = '-quality' in RECIPES[recipe]
    dst = os.path.join(td, recipe + ('.jpg' if jpeg else '.png'))
    cmd = [a for x in RECIPES[recipe] for a in (['-resize', f'{w}x{h}!'] if x == '{size}' else [x])]
    subprocess.run(['convert', src_path] + cmd + ['-depth', '8', ('' if jpeg else 'PNG24:') + dst],
                   check=True, capture_output=True)
    return np.asarray(Image.open(dst).convert('RGB'))   # JPEG decoded with Pillow (libjpeg-turbo), as everywhere


def task(args):
    name, f = args
    path = os.path.join(TESTSET, 'large', f'{name}.png')
    L = np.asarray(Image.open(path).convert('RGB'))
    H, W = L.shape[:2]
    w, h = R.small_size(W, H, f)
    rows = []
    with tempfile.TemporaryDirectory() as td:
        for recipe in RECIPES:
            Sm = im_resize(path, w, h, recipe, td)
            assert Sm.shape[:2] == (h, w), (Sm.shape, w, h)
            downs, k = S.down_strategies(L, Sm, 'area')   # the oracle slot is unused here
            row = dict(image=name, factor=f, recipe=recipe, picked=k['down_matched8a'])
            out, _ = M.cheap_panel(downs['down_matched8a'], Sm)
            row.update(T_p99_matched=out['T_p99'], share_T16_matched=out['share_T16'])
            best = min((M.cheap_panel(downs['down_fi_' + kk + '8'], Sm)[0]['T_p99'], kk)
                       for kk in S.MATCH8)
            row.update(T_p99_best_fi=best[0], best_fi=best[1])
            out, _ = M.cheap_panel(L, fi.rescale(Sm, W, H, 'lanczos3'))
            row.update(T_p99_lanczos3_up=out['T_p99'])
            rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--out', default=os.path.join(RESULTS, 'im_spotcheck.csv'))
    a = ap.parse_args()
    tasks = [(n, f) for n in IMAGES for f in (2, 2.5, 3)]
    with Pool(a.jobs) as pool:
        rows = [r for rr in pool.imap_unordered(task, tasks) for r in rr]
    df = pd.DataFrame(rows)
    df.to_csv(a.out, index=False)
    print(df.groupby('recipe')[['T_p99_matched', 'T_p99_best_fi', 'T_p99_lanczos3_up', 'share_T16_matched']].median().round(2))
    print(df.groupby(['recipe', 'picked']).size().unstack(fill_value=0))
    print(df.pivot_table(index='image', columns='recipe', values='T_p99_matched').round(1))


if __name__ == '__main__':
    main()
