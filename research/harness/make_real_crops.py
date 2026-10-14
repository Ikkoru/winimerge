"""Recreate testset/real/*.png (and the testset/large_real links) from the downloaded sources.

    python3 make_real_crops.py [--sources testset/sources] [--out testset/real]

The sources are listed, with URLs and SHA-256, in testset/sources/MANIFEST.md / MANIFEST.json.
testset/real/CROPS.json says which window of each source was used: the most detailed window of at
most 1600x1200, cut at the source's native resolution (nothing is resampled).
"""
import argparse
import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sources', default=os.path.join(ROOT, 'testset', 'sources'))
    ap.add_argument('--out', default=os.path.join(ROOT, 'testset', 'real'))
    ap.add_argument('--check', action='store_true', help='compare with the existing files instead of writing')
    a = ap.parse_args()
    crops = json.load(open(os.path.join(a.out, 'CROPS.json')))
    links = os.path.join(ROOT, 'testset', 'large_real')
    os.makedirs(links, exist_ok=True)
    for name, c in crops.items():
        im = Image.open(os.path.join(a.sources, c['source']))
        im = im.convert('RGBA').convert('RGB') if im.mode in ('RGBA', 'LA', 'P', 'PA') else im.convert('RGB')
        out = im.crop(tuple(c['crop_xyxy']))
        assert list(out.size) == list(c['size']), (name, out.size, c['size'])
        path = os.path.join(a.out, name)
        if a.check:
            old = np.asarray(Image.open(path).convert('RGB'))
            same = old.shape == np.asarray(out).shape and np.array_equal(old, np.asarray(out))
            print(f'{name}: {"identical" if same else "DIFFERENT"}')
            continue
        out.save(path, optimize=True)
        link = os.path.join(links, name)
        if not os.path.lexists(link):
            os.symlink(os.path.join('..', 'real', name), link)
        print('wrote', path)


if __name__ == '__main__':
    main()
