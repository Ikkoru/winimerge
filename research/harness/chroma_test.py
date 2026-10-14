"""Does libjpeg's chroma upsampling ("fancy", the default, vs -nosmooth) change the comparison?

    python3 chroma_test.py [--jobs 2]

For each synthetic image, shrinker and factor, the small copy is saved as JPEG q85 4:2:0 (Pillow) and
decoded twice with libjpeg-turbo's djpeg: with its default smooth chroma upsampling and with
-nosmooth (replicated chroma). Both are compared with the original: matched shrink (WinIMerge
DOWN_MATCHED rule) and Lanczos3 enlargement. Writes results/chroma_synth.csv.
"""
import argparse
import io
import os
import subprocess
import tempfile
from multiprocessing import Pool

import numpy as np
from PIL import Image

import fi
import metrics as M
import resample as R
import study as S

IMAGES = ['synth_flatcolor', 'synth_lineart', 'synth_manga', 'synth_painterly', 'synth_text_ui', 'synth_pixelart', 'synth_zoneplate']


def djpeg(path, smooth):
    out = subprocess.run(['djpeg', '-ppm'] + ([] if smooth else ['-nosmooth']) + [path], capture_output=True, check=True).stdout
    return np.asarray(Image.open(io.BytesIO(out)).convert('RGB'))


def task(args):
    name, shr, f = args
    L = np.asarray(Image.open(f'/home/user/research/testset/large/{name}.png').convert('RGB'))
    H, W = L.shape[:2]
    w, h = R.small_size(W, H, f)
    Sm = R.SHRINKERS[shr](L, w, h)
    rows = []
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'c.jpg')
        Image.fromarray(Sm).save(p, quality=85, subsampling=2)
        for smooth in (True, False):
            D = djpeg(p, smooth)
            downs, k = S.down_strategies(L, D, shr)
            for cand, A, B in [('down_matched8a', downs['down_matched8a'], D),
                               ('fi_lanczos3', L, fi.rescale(D, W, H, 'lanczos3'))]:
                out, _ = M.cheap_panel(A, B)
                rows.append(dict(image=name, shrinker=shr, factor=f, upsampling='fancy' if smooth else 'replicate',
                                 candidate=cand, matched_kernel=k['down_matched8a'] if cand == 'down_matched8a' else '',
                                 T_p99=out['T_p99'], share_T16=out['share_T16'], share_T64=out['share_T64'], psnr=out.get('psnr')))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jobs', type=int, default=2)
    a = ap.parse_args()
    tasks = [(n, s, f) for n in IMAGES for s in ('pil_lanczos', 'area') for f in (2, 2.5, 3)]
    with Pool(a.jobs) as pool:
        rows = [r for rr in pool.map(task, tasks) for r in rr]
    import pandas as pd
    df = pd.DataFrame(rows)
    df.to_csv('/home/user/research/results/chroma_synth.csv', index=False)
    print(df.groupby(['candidate', 'upsampling'])[['T_p99', 'share_T16', 'share_T64', 'psnr']].median().round(3))
    piv = df.pivot_table(index=['image', 'shrinker', 'factor', 'candidate'], columns='upsampling', values='T_p99')
    print('pairs where fancy upsampling needs a lower threshold:',
          (piv.fancy < piv.replicate - 0.5).groupby(level='candidate').mean().round(2).to_dict())


if __name__ == '__main__':
    main()
