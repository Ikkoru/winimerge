"""ctypes wrapper around FreeImage's resampler (FreeImage_Rescale), the code WinMerge ships.

Set FREEIMAGE_LIB to WinMerge's fork built as a shared library (see harness/README.md);
falls back to the system libfreeimage.so.3 (upstream 3.18, same Resize.cpp).

Images are numpy uint8 arrays (H, W, 3) RGB or (H, W, 4) RGBA, top row first.
"""
import ctypes as C
import os
import numpy as np

_LIB_CANDIDATES = [os.environ.get('FREEIMAGE_LIB', ''), 'libfreeimage.so.3', 'libfreeimage.so']
_fi = None
for _p in _LIB_CANDIDATES:
    if not _p:
        continue
    try:
        _fi = C.CDLL(_p)
        LIB_PATH = _p
        break
    except OSError:
        pass
if _fi is None:
    raise ImportError('FreeImage shared library not found; set FREEIMAGE_LIB')

FILTERS = {'box': 0, 'bicubic': 1, 'bilinear': 2, 'bspline': 3, 'catmullrom': 4, 'lanczos3': 5}
FIT_BITMAP, FIT_RGBAF = 1, 12

_fi.FreeImage_Initialise.argtypes = [C.c_int]
_fi.FreeImage_GetVersion.restype = C.c_char_p
_fi.FreeImage_AllocateT.restype = C.c_void_p
_fi.FreeImage_AllocateT.argtypes = [C.c_int, C.c_int, C.c_int, C.c_int, C.c_uint, C.c_uint, C.c_uint]
_fi.FreeImage_GetScanLine.restype = C.c_void_p
_fi.FreeImage_GetScanLine.argtypes = [C.c_void_p, C.c_int]
_fi.FreeImage_GetWidth.restype = C.c_uint
_fi.FreeImage_GetWidth.argtypes = [C.c_void_p]
_fi.FreeImage_GetHeight.restype = C.c_uint
_fi.FreeImage_GetHeight.argtypes = [C.c_void_p]
_fi.FreeImage_GetBPP.restype = C.c_uint
_fi.FreeImage_GetBPP.argtypes = [C.c_void_p]
_fi.FreeImage_GetImageType.restype = C.c_int
_fi.FreeImage_GetImageType.argtypes = [C.c_void_p]
_fi.FreeImage_Rescale.restype = C.c_void_p
_fi.FreeImage_Rescale.argtypes = [C.c_void_p, C.c_int, C.c_int, C.c_int]
_fi.FreeImage_ConvertToRGBAF.restype = C.c_void_p
_fi.FreeImage_ConvertToRGBAF.argtypes = [C.c_void_p]
_fi.FreeImage_Unload.argtypes = [C.c_void_p]
_fi.FreeImage_Initialise(0)
VERSION = _fi.FreeImage_GetVersion().decode()


def _to_dib32(img):
    """numpy RGB(A) uint8 top-down -> FIBITMAP 32bpp BGRA bottom-up (as WinIMerge holds images)."""
    h, w = img.shape[:2]
    if img.shape[2] == 3:
        img = np.dstack([img, np.full((h, w), 255, np.uint8)])
    bgra = np.ascontiguousarray(img[:, :, [2, 1, 0, 3]])
    dib = _fi.FreeImage_AllocateT(FIT_BITMAP, w, h, 32, 0x00FF0000, 0x0000FF00, 0x000000FF)
    for y in range(h):
        C.memmove(_fi.FreeImage_GetScanLine(dib, h - 1 - y), bgra[y].ctypes.data, w * 4)
    return dib


def _from_dib32(dib):
    w, h = _fi.FreeImage_GetWidth(dib), _fi.FreeImage_GetHeight(dib)
    assert _fi.FreeImage_GetBPP(dib) == 32 and _fi.FreeImage_GetImageType(dib) == FIT_BITMAP
    out = np.empty((h, w, 4), np.uint8)
    for y in range(h):
        C.memmove(out[y].ctypes.data, _fi.FreeImage_GetScanLine(dib, h - 1 - y), w * 4)
    return out[:, :, [2, 1, 0, 3]]


def _from_dibf(dib):
    w, h = _fi.FreeImage_GetWidth(dib), _fi.FreeImage_GetHeight(dib)
    assert _fi.FreeImage_GetImageType(dib) == FIT_RGBAF
    out = np.empty((h, w, 4), np.float32)
    for y in range(h):
        C.memmove(out[y].ctypes.data, _fi.FreeImage_GetScanLine(dib, h - 1 - y), w * 16)
    return out  # RGBA order, 0..1


def rescale(img, width, height, filt='lanczos3', float_path=False, return_float=False):
    """Resize like WinIMerge would with FreeImage_Rescale.

    float_path=False: 32-bit BGRA FIT_BITMAP; FreeImage rounds and clamps to 8 bits between passes.
    float_path=True: convert to FIT_RGBAF first (no clamping between passes), then round/clamp once.
    Returns uint8 RGB(A) like the input (or float32 0..255 if return_float and float_path).
    """
    nch = img.shape[2]
    src = _to_dib32(img)
    try:
        if float_path:
            f = _fi.FreeImage_ConvertToRGBAF(src)
            try:
                r = _fi.FreeImage_Rescale(f, width, height, FILTERS[filt])
                out = _from_dibf(r) * 255.0
                _fi.FreeImage_Unload(r)
            finally:
                _fi.FreeImage_Unload(f)
            if return_float:
                return out[:, :, :nch]
            out = np.clip(np.floor(out + 0.5), 0, 255).astype(np.uint8)
        else:
            r = _fi.FreeImage_Rescale(src, width, height, FILTERS[filt])
            out = _from_dib32(r)
            _fi.FreeImage_Unload(r)
    finally:
        _fi.FreeImage_Unload(src)
    return out[:, :, :nch]


if __name__ == '__main__':
    print('FreeImage', VERSION, 'from', LIB_PATH)
    a = (np.random.default_rng(0).random((5, 7, 3)) * 255).astype(np.uint8)
    for k in FILTERS:
        b = rescale(a, 14, 10, k)
        c = rescale(a, 14, 10, k, float_path=True)
        print(k, b.shape, int(np.abs(b.astype(int) - c).max()))
    # box at integer upscale must equal nearest neighbour
    nn = np.repeat(np.repeat(a, 2, 0), 2, 1)
    print('box x2 == NN:', np.array_equal(rescale(a, 14, 10, 'box'), nn))
