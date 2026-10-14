// Unit tests for the image scaling option (CImgDiffBuffer::SetImageScalingMode).
// Build/run: ./build.sh /home/user/winimerge test_scaling.cpp
#include "testlib.hpp"

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
	double ScaleX(int pane) { double sx, sy; GetImageScale(pane, sx, sy); return sx; }
	double ScaleY(int pane) { double sx, sy; GetImageScale(pane, sx, sy); return sy; }
	unsigned PixelAt(int pane, int x, int y) { RGBQUAD c = GetPixelColor(pane, x, y); return (unsigned)c.rgbBlue | c.rgbGreen << 8 | c.rgbRed << 16 | (unsigned)c.rgbReserved << 24; }
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
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_SMOOTH);
	CHECK_EQ(b.PreW(0), 133); CHECK_EQ(b.PreH(0), 100);
	CHECK_EQ(b.PreW(1), 133);
	CHECK(b.ConvertToRealPos(0, 132, 99, rx, ry)); CHECK_EQ(rx, 398); CHECK_EQ(ry, 298);
	// a crop (aspect ratio differs) is scaled uniformly, not stretched
	Image imgs2[2] = { Patterned(400, 300), Patterned(100, 100) };
	b.SetImages(2, imgs2);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_SMOOTH);
	b.CompareImages();
	CHECK_EQ(b.PreW(1), 300); CHECK_EQ(b.PreH(1), 300);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_SMOOTH);
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
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_SMOOTH);
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
	TestSaveScaledForPython();
	FreeImage_DeInitialise();
	return Summary("test_scaling");
}
