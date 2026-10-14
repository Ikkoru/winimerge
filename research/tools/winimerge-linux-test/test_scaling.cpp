// Unit tests for the image scaling option (CImgDiffBuffer::SetImageScalingMode).
// Build/run: ./build.sh /home/user/winimerge test_scaling.cpp
#include "testlib.hpp"
#include <cmath>

static const unsigned RED = 0xffff0000, BLUE = 0xff0000ff, WHITE = 0xffffffff, BLACK = 0xff000000;

static Image Solid(int w, int h, unsigned c) { return MakeImage(w, h, [c](int, int) { return c; }); }
static unsigned Pattern(int x, int y) { return 0xff000000u | ((x * 37 + y * 11) & 0xff) << 16 | ((x * 7 ^ y * 13) & 0xff) << 8 | ((x + y) * 5 & 0xff); }
static Image Patterned(int w, int h) { return MakeImage(w, h, Pattern); }
static Image NearestUp(const Image& src, int k)
{
	return MakeImage(src.width() * k, src.height() * k, [&](int x, int y) {
		const unsigned char *p = src.scanLine(y / k) + (x / k) * 4;
		return (unsigned)p[0] | (unsigned)p[1] << 8 | (unsigned)p[2] << 16 | (unsigned)p[3] << 24; });
}

class ScaleTestBuffer : public TestBuffer
{
public:
	void CorruptCache(int pane) { m_scaledImage[pane].image.scanLine(0)[0] ^= 0xff; }
	static Image Shrink(const Image& src, unsigned w, unsigned h, FREE_IMAGE_FILTER f) { Image out; ResizeImage(src, out, w, h, f); return out; }
	int MatchedFilter(int pane) const { return m_scaledImage[pane].filter; }
	std::uint64_t ScaledKey(int pane) const { return m_scaledImage[pane].key; }
	const Image& Orig(int pane) const { return m_imgOrig32[pane]; }
	const Image& Shown(int pane) const { return m_scaledImage[pane].image; }
	static Image ShrinkArea(const Image& src, unsigned w, unsigned h) { Image out; ResizeImageArea(src, out, w, h); return out; }
	double ScaleX(int pane) { double sx, sy; GetImageScale(pane, sx, sy); return sx; }
	double ScaleY(int pane) { double sx, sy; GetImageScale(pane, sx, sy); return sy; }
	unsigned PixelAt(int pane, int x, int y) { RGBQUAD c = GetPixelColor(pane, x, y); return (unsigned)c.rgbBlue | c.rgbGreen << 8 | c.rgbRed << 16 | (unsigned)c.rgbReserved << 24; }
	unsigned OrigAt(int pane, int x, int y) { const unsigned char *p = m_imgOrig32[pane].scanLine(y) + x * 4; return (unsigned)p[0] | p[1] << 8 | p[2] << 16 | (unsigned)p[3] << 24; }
	int CountOrig(int pane, unsigned c) { int n = 0; for (unsigned y = 0; y < m_imgOrig32[pane].height(); ++y) for (unsigned x = 0; x < m_imgOrig32[pane].width(); ++x) n += OrigAt(pane, x, y) == c; return n; }
};

static void TestDefaultUnchanged()
{
	ScaleTestBuffer b;
	Image imgs[2] = { Solid(300, 200, RED), Solid(100, 100, RED) };
	b.SetImages(2, imgs);
	b.CompareImages();
	CHECK_EQ(b.PreW(1), 100); CHECK_EQ(b.PreH(1), 100);
	CHECK_EQ(b.ScaleX(1), 1.0);
	CHECK_EQ(b.GetDiffCount(), 1);
}

static void TestNearestIntegerSizes()
{
	ScaleTestBuffer b;
	Image imgs[2] = { Solid(300, 200, RED), Patterned(100, 100) };
	b.SetImages(2, imgs);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_NEAREST_INTEGER);
	CHECK_EQ(b.PreW(0), 300); CHECK_EQ(b.PreH(0), 200);
	CHECK_EQ(b.PreW(1), 200); CHECK_EQ(b.PreH(1), 200);       // k = min(300/100, 200/100) = 2
	CHECK_EQ(b.GetImageWidth(1), 100);                           // the original is untouched
	CHECK_EQ(b.ScaleX(1), 2.0); CHECK_EQ(b.ScaleY(1), 2.0);
	CHECK_EQ(b.CanvasW(), 300); CHECK_EQ(b.CanvasH(), 200);
	// every scaled pixel is an exact copy of the original pixel it came from
	bool exact = true;
	for (int y = 0; y < 200; ++y)
		for (int x = 0; x < 200; ++x)
			if (b.PixelAt(1, x, y) != Pattern(x / 2, y / 2))
				exact = false;
	CHECK(exact);
	int rx, ry;
	CHECK(b.ConvertToRealPos(1, 21, 41, rx, ry)); CHECK_EQ(rx, 10); CHECK_EQ(ry, 20);
	CHECK(b.ConvertToRealPos(1, 199, 199, rx, ry)); CHECK_EQ(rx, 99); CHECK_EQ(ry, 99);
	CHECK(!b.ConvertToRealPos(1, 250, 50, rx, ry)); CHECK_EQ(rx, 99);
	// image that does not fit a whole-number factor stays as is
	Image imgs2[2] = { Solid(150, 150, RED), Solid(100, 100, RED) };
	b.SetImages(2, imgs2);
	b.CompareImages();
	CHECK_EQ(b.PreW(1), 100); CHECK_EQ(b.ScaleX(1), 1.0);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_NONE);
	CHECK_EQ(b.PreW(1), 100);
}

static void TestNearestIntegerExactMatch()
{
	// the large image is an exact x3 nearest-neighbour enlargement: no differences once scaled
	Image small = Patterned(80, 60);
	ScaleTestBuffer b;
	Image imgs[2] = { NearestUp(small, 3), small };
	b.SetImages(2, imgs);
	b.CompareImages();
	CHECK(b.GetDiffCount() > 0);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_NEAREST_INTEGER);
	CHECK_EQ(b.GetDiffCount(), 0);
	// and the same with the panes swapped and three panes
	Image imgs3[3] = { small, NearestUp(small, 3), NearestUp(small, 3) };
	b.SetImages(3, imgs3);
	b.CompareImages();
	CHECK_EQ(b.GetDiffCount(), 0);
	CHECK_EQ(b.PreW(0), 240);
}

static void TestSmoothSnapsRoundedSizes()
{
	ScaleTestBuffer b;
	// 400x300 shrunk to a third and rounded: 133x100 (factors 3.0075 and 3.0)
	Image imgs[2] = { Patterned(400, 300), Patterned(133, 100) };
	b.SetImages(2, imgs);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_SMOOTH);
	CHECK_EQ(b.PreW(1), 400); CHECK_EQ(b.PreH(1), 300);         // snapped to the large size
	CHECK(b.ScaleX(1) > 3.0 && b.ScaleX(1) < 3.01); CHECK_EQ(b.ScaleY(1), 3.0);
	int rx, ry;
	CHECK(b.ConvertToRealPos(1, 399, 299, rx, ry)); CHECK_EQ(rx, 132); CHECK_EQ(ry, 99);
	CHECK(b.ConvertToRealPos(1, 0, 0, rx, ry)); CHECK_EQ(rx, 0); CHECK_EQ(ry, 0);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);
	CHECK_EQ(b.PreW(0), 133); CHECK_EQ(b.PreH(0), 100);
	CHECK_EQ(b.PreW(1), 133);
	CHECK(b.ConvertToRealPos(0, 132, 99, rx, ry)); CHECK_EQ(rx, 398); CHECK_EQ(ry, 298);
	// a crop (aspect ratio differs) is scaled uniformly, not stretched
	Image imgs2[2] = { Patterned(400, 300), Patterned(100, 100) };
	b.SetImages(2, imgs2);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_SMOOTH);
	b.CompareImages();
	CHECK_EQ(b.PreW(1), 300); CHECK_EQ(b.PreH(1), 300);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);
	CHECK_EQ(b.PreW(0), 133); CHECK_EQ(b.PreH(0), 100);          // touches the 100x100 box in height
}

static void TestCacheReuseAndInvalidate()
{
	ScaleTestBuffer b;
	Image imgs[2] = { Patterned(400, 300), Patterned(133, 100) };
	b.SetImages(2, imgs);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_SMOOTH);
	const unsigned good = b.PixelAt(1, 0, 0);
	b.CorruptCache(1);                               // flip the cached scaled pixel (0,0)
	b.SetColorDistanceThreshold(10.0);               // compares again: the cached image is reused...
	CHECK(b.PixelAt(1, 0, 0) != good);
	b.SetDiffBlockSize(4);
	CHECK(b.PixelAt(1, 0, 0) != good);
	b.DeleteRectangle(1, 100, 80, 110, 90);          // ...until the original changes
	CHECK_EQ(b.PixelAt(1, 0, 0), good);
	b.CorruptCache(1);
	b.Undo();                                        // undo restores the original: resampled again
	CHECK_EQ(b.PixelAt(1, 0, 0), good);
	b.CorruptCache(1);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_NEAREST_INTEGER);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_SMOOTH);
	CHECK_EQ(b.PixelAt(1, 0, 0), good);              // another filter in between: resampled again
}

static void TestEditingScaledPane()
{
	ScaleTestBuffer b;
	Image small = Solid(100, 100, BLUE);
	Image large = MakeImage(200, 200, [](int x, int y) { return (x >= 40 && x < 80 && y >= 40 && y < 80) ? RED : BLUE; });
	Image imgs[2] = { large, small };
	b.SetImages(2, imgs);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_NEAREST_INTEGER);
	CHECK_EQ(b.GetDiffCount(), 1);
	b.CopyDiff(0, 0, 1);                            // copy the red square into the small image
	CHECK_EQ(b.GetImageWidth(1), 100);              // not resized
	CHECK_EQ(b.GetDiffCount(), 0);
	RGBQUAD c = b.GetOriginalImage(1)->pixel(25, 25);
	(void)c;
	Image *orig = nullptr; (void)orig;
	// the original pixel (25,25) of the small image is now red
	int rx, ry;
	CHECK(b.ConvertToRealPos(1, 50, 50, rx, ry)); CHECK_EQ(rx, 25);
	CHECK_EQ(b.PixelAt(1, 50, 50), RED);
	b.Undo();
	CHECK_EQ(b.GetDiffCount(), 1);
	// copying the other way enlarges nothing and does not crash
	b.CopyDiff(0, 1, 0);
	CHECK_EQ(b.GetDiffCount(), 0);
	CHECK_EQ(b.GetImageWidth(0), 200);
}

static void TestInsertionDeletionWithScaling()
{
	ScaleTestBuffer b;
	Image small = MakeImage(60, 40, [](int x, int y) { return (y % 6 < 3) ? RED : BLUE; });
	Image imgs[2] = { NearestUp(small, 2), small };
	b.SetImages(2, imgs);
	b.SetInsertionDeletionDetectionMode(CImgDiffBuffer::INSERTION_DELETION_DETECTION_VERTICAL);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_NEAREST_INTEGER);
	CHECK_EQ(b.PreH(0), b.PreH(1));
	CHECK_EQ(b.GetDiffCount(), 0);
	int rx, ry;
	CHECK(b.ConvertToRealPos(1, 119, 79, rx, ry)); CHECK_EQ(rx, 59); CHECK_EQ(ry, 39);
	b.SetInsertionDeletionDetectionMode(CImgDiffBuffer::INSERTION_DELETION_DETECTION_HORIZONTAL);
	CHECK_EQ(b.PreW(0), b.PreW(1));
	CHECK_EQ(b.GetDiffCount(), 0);
	b.CopyDiffAll(0, 1);                            // nothing to copy, must not crash
	CHECK(true);
}

static void TestRotationWithScaling()
{
	ScaleTestBuffer b;
	Image imgs[2] = { Patterned(200, 400), Patterned(100, 50) };
	b.SetImages(2, imgs);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_NEAREST_INTEGER);
	CHECK_EQ(b.PreW(1), 200); CHECK_EQ(b.PreH(1), 100);         // k = min(2, 8) = 2
	b.SetRotation(1, 90.f);                                       // now 50x100: k = 4
	CHECK_EQ(b.PreW(1), 200); CHECK_EQ(b.PreH(1), 400);
	int rx, ry;
	CHECK(b.ConvertToRealPos(1, 199, 399, rx, ry)); CHECK_EQ(rx, 49); CHECK_EQ(ry, 99);
}

static Image Smooth(int w, int h)
{
	// smooth content with some edges, so that the filters give clearly different results
	return MakeImage(w, h, [](int x, int y) {
		const double v = 128 + 60 * std::sin(x * 0.05) * std::cos(y * 0.07) + ((x / 37 + y / 23) % 2 ? 50 : -50);
		const int c = static_cast<int>(std::min(255.0, std::max(0.0, v)));
		return 0xff000000u | (unsigned)c << 16 | (unsigned)(255 - c) << 8 | (unsigned)((c * 3) & 0xff); });
}

static void TestMatchedShrink()
{
	// the copy was made with one of FreeImage's filters (8-bit path, like Pillow): shrinking the
	// original with the matched filter reproduces it exactly, so nothing is marked as different
	Image large = Smooth(500, 400);
	const FREE_IMAGE_FILTER filters[] = { FILTER_BOX, FILTER_BILINEAR, FILTER_BICUBIC, FILTER_CATMULLROM, FILTER_LANCZOS3 };
	for (FREE_IMAGE_FILTER f : filters)
	{
		for (int k = 0; k < 2; ++k)
		{
			const unsigned w = k ? 213 : 250, h = k ? 170 : 200;   // factor 2.35 and 2
			Image small = ScaleTestBuffer::Shrink(large, w, h, f);
			ScaleTestBuffer b;
			Image imgs[2] = { large, small };
			b.SetImages(2, imgs);
			b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);
			CHECK_EQ(b.PreW(0), (int)w); CHECK_EQ(b.PreH(0), (int)h);
			CHECK_EQ(b.GetDiffCount(), 0);
			// any other single filter leaves differences
			b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_SMOOTH);
			CHECK(b.GetDiffCount() > 0);
		}
	}
	// the reference changes (the small image is edited): the match is redone
	Image small = ScaleTestBuffer::Shrink(large, 213, 170, FILTER_LANCZOS3);
	ScaleTestBuffer b;
	Image imgs[2] = { small, large };
	b.SetImages(2, imgs);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);
	CHECK_EQ(b.GetDiffCount(), 0);
	b.DeleteRectangle(0, 10, 10, 20, 20);
	CHECK_EQ(b.GetDiffCount(), 1);
	b.Undo();
	CHECK_EQ(b.GetDiffCount(), 0);
}

static void TestCopyDiffWithShrinkAndSmooth()
{
	// shrink mode: nothing is copied into the shrunk image (the copied pixels would be resampled with
	// their neighbours again and the difference would grow instead of disappear)
	Image large = Solid(200, 160, BLUE);
	Image small = MakeImage(100, 80, [](int x, int y) { return (x >= 20 && x < 40 && y >= 20 && y < 40) ? RED : BLUE; });
	ScaleTestBuffer b;
	Image imgs[2] = { large, small };
	b.SetImages(2, imgs);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);
	CHECK_EQ(b.GetDiffCount(), 1);
	b.CopyDiff(0, 1, 0);
	b.CopyDiffAll(1, 0);
	CHECK_EQ(b.CopyDiff3Way(0), 0);
	CHECK_EQ(b.CountOrig(0, RED), 0);
	CHECK_EQ(b.GetDiffCount(), 1);
	CHECK(!b.IsUndoable());
	// the other way round, the shrunk pixels it shows are copied, so the difference is gone
	b.CopyDiff(0, 0, 1);
	CHECK_EQ(b.CountOrig(1, RED), 0);
	CHECK_EQ(b.GetDiffCount(), 0);
	b.Undo();
	// selection edges map to the boundaries between the original pixels (scale 0.5)
	int rx, ry;
	b.ConvertToRealEdgePos(0, 10, 7, rx, ry); CHECK_EQ(rx, 20); CHECK_EQ(ry, 14);
	b.ConvertToRealEdgePos(0, 100, 80, rx, ry); CHECK_EQ(rx, 200); CHECK_EQ(ry, 160);
	b.ConvertToRealEdgePos(1, 10, 7, rx, ry); CHECK_EQ(rx, 10); CHECK_EQ(ry, 7);

	// smooth enlargement, copying from the enlarged image: the resampled pixels it shows are
	// copied, so nothing is left to mark
	Image imgs2[2] = { Solid(250, 200, WHITE), Smooth(100, 80) };
	b.SetImages(2, imgs2);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_SMOOTH);
	CHECK_EQ(b.ScaleX(1), 2.5);
	CHECK(b.GetDiffCount() > 0);
	b.CopyDiffAll(0, 1);                            // not into the smoothly enlarged image
	CHECK(!b.IsUndoable());
	b.CopyDiffAll(1, 0);
	CHECK_EQ(b.GetDiffCount(), 0);
	CHECK_EQ(b.CountOrig(0, WHITE), 0);
	// selection edges in the enlarged image (scale 2.5): pixel i is inside when its centre is
	b.ConvertToRealEdgePos(1, 3, 4, rx, ry); CHECK_EQ(rx, 1); CHECK_EQ(ry, 2);
	b.ConvertToRealEdgePos(1, 250, 200, rx, ry); CHECK_EQ(rx, 100); CHECK_EQ(ry, 80);
	// nearest neighbour x2, copying into the enlarged image: each original pixel is written once
	Image imgs3[2] = { MakeImage(200, 160, [](int x, int y) { return ((x / 2 + y / 2) % 2) ? RED : BLUE; }), Solid(100, 80, WHITE) };
	b.SetImages(2, imgs3);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_NEAREST_INTEGER);
	b.CopyDiffAll(0, 1);
	CHECK_EQ(b.GetDiffCount(), 0);
	CHECK_EQ(b.CountOrig(1, RED) + b.CountOrig(1, BLUE), 100 * 80);
}

static unsigned Channel(const Image& img, int x, int y, int c) { return img.scanLine(y)[x * 4 + c]; }

static void TestAreaShrink()
{
	// whole-number factor: the plain average of each 2x2 block, rounded half up
	Image src = Patterned(64, 48);
	Image a = ScaleTestBuffer::ShrinkArea(src, 32, 24);
	bool exact = true;
	for (int y = 0; y < 24; ++y)
		for (int x = 0; x < 32; ++x)
			for (int c = 0; c < 4; ++c)
			{
				const unsigned s = Channel(src, 2 * x, 2 * y, c) + Channel(src, 2 * x + 1, 2 * y, c) + Channel(src, 2 * x, 2 * y + 1, c) + Channel(src, 2 * x + 1, 2 * y + 1, c);
				if (Channel(a, x, y, c) != (s + 2) / 4)
					exact = false;
			}
	CHECK(exact);
	// non-integer factor: within one level of a double-precision coverage reference
	Image big = Smooth(500, 400);
	const unsigned w = 213, h = 170;
	Image b = ScaleTestBuffer::ShrinkArea(big, w, h);
	const double sx = 500.0 / w, sy = 400.0 / h;
	int maxdiff = 0;
	for (unsigned y = 0; y < h; y += 7)
		for (unsigned x = 0; x < w; x += 5)
			for (int c = 0; c < 3; ++c)
			{
				double acc = 0;
				for (int j = (int)(y * sy); j < (int)std::ceil((y + 1) * sy) && j < 400; ++j)
					for (int i = (int)(x * sx); i < (int)std::ceil((x + 1) * sx) && i < 500; ++i)
					{
						const double cx = std::min((x + 1) * sx, i + 1.0) - std::max(x * sx, (double)i);
						const double cy = std::min((y + 1) * sy, j + 1.0) - std::max(y * sy, (double)j);
						if (cx > 0 && cy > 0)
							acc += cx * cy * Channel(big, i, j, c);
					}
				maxdiff = std::max(maxdiff, std::abs((int)Channel(b, x, y, c) - (int)std::floor(acc / (sx * sy) + 0.5)));
			}
	CHECK(maxdiff <= 1);
	// shrink mode reproduces an area-averaged copy exactly (FreeImage's box filter does not at 2.35x)
	ScaleTestBuffer m;
	Image imgs[2] = { big, b };
	m.SetImages(2, imgs);
	m.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);
	CHECK_EQ(m.GetDiffCount(), 0);
	Image boxed = ScaleTestBuffer::Shrink(big, w, h, FILTER_BOX);
	Image imgs2[2] = { big, boxed };
	m.SetImages(2, imgs2);
	m.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_NONE);
	m.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);
	CHECK_EQ(m.GetDiffCount(), 0);                  // the box-filtered copy is still found as box
	// for the harness: compare with OpenCV's INTER_AREA
	big.getFipImage()->save("area_src.png");
	b.getFipImage()->save("area_cpp.png");
}

static void TestMatchedFilterKeptAfterEdits()
{
	// the filter is matched once per image pair and size; after an edit the larger image is only
	// shrunk again with it, and an edit of the smaller image does not resample the larger one
	Image large = Smooth(500, 400);
	ScaleTestBuffer b;
	Image imgs[2] = { large, ScaleTestBuffer::Shrink(large, 213, 170, FILTER_LANCZOS3) };
	b.SetImages(2, imgs);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);
	CHECK_EQ(b.MatchedFilter(0), (int)FILTER_LANCZOS3);
	CHECK_EQ(b.GetDiffCount(), 0);
	const std::uint64_t key = b.ScaledKey(0);
	b.DeleteRectangle(1, 10, 10, 60, 60);           // edit the small image
	CHECK_EQ(b.ScaledKey(0), key);                  // the large one is not resampled
	CHECK_EQ(b.GetDiffCount(), 1);
	b.DeleteRectangle(0, 0, 0, 400, 300);           // edit the large image heavily
	CHECK_EQ(b.MatchedFilter(0), (int)FILTER_LANCZOS3);
	Image expect = ScaleTestBuffer::Shrink(b.Orig(0), 213, 170, FILTER_LANCZOS3);
	bool same = b.Shown(0).width() == 213 && b.Shown(0).height() == 170;
	for (unsigned y = 0; same && y < 170; ++y)
		same = memcmp(b.Shown(0).scanLine(y), expect.scanLine(y), 213 * 4) == 0;
	CHECK(same);
	b.Undo();
	b.Undo();
	CHECK_EQ(b.GetDiffCount(), 0);
	// another pair is matched again
	Image imgs2[2] = { large, ScaleTestBuffer::Shrink(large, 213, 170, FILTER_BILINEAR) };
	b.SetImages(2, imgs2);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_NONE);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);
	CHECK_EQ(b.MatchedFilter(0), (int)FILTER_BILINEAR);
	CHECK_EQ(b.GetDiffCount(), 0);
}

static void TestSaveScaledForPython()
{
	// writes the smooth-scaled pane so the harness can compare it with its float reference
	ScaleTestBuffer b;
	const char *files[2] = { "large.png", "small.png" };
	if (!b.OpenFiles(2, files))
		return;
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_SMOOTH);
	b.CompareImages();
	b.SetShowDifferences(false);
	b.Save(1, "smooth_pane1.png");
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);
	b.Save(0, "down_pane0.png");
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_NEAREST_INTEGER);
	b.Save(1, "nn_pane1.png");
	std::printf("saved scaled panes (%dx%d)\n", b.PreW(1), b.PreH(1));
}

int main()
{
	FreeImage_Initialise();
	TestDefaultUnchanged();
	TestNearestIntegerSizes();
	TestNearestIntegerExactMatch();
	TestSmoothSnapsRoundedSizes();
	TestCacheReuseAndInvalidate();
	TestEditingScaledPane();
	TestInsertionDeletionWithScaling();
	TestRotationWithScaling();
	TestMatchedShrink();
	TestCopyDiffWithShrinkAndSmooth();
	TestAreaShrink();
	TestMatchedFilterKeptAfterEdits();
	TestSaveScaledForPython();
	FreeImage_DeInitialise();
	return Summary("test_scaling");
}
