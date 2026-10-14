// Integration of image alignment + image scaling (build against a tree that has both features).
#include "testlib.hpp"

static Image Solid(int w, int h, unsigned c) { return MakeImage(w, h, [c](int, int) { return c; }); }

int main()
{
	FreeImage_Initialise();
	TestBuffer b;
	Image imgs[2] = { Solid(300, 200, 0xffff0000), Solid(100, 90, 0xffff0000) };
	b.SetImages(2, imgs);
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_CENTER);
	b.CompareImages();
	CHECK_EQ(b.OffX(1), 100); CHECK_EQ(b.OffY(1), 55);          // unscaled 100x90 centred
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_NEAREST_INTEGER);
	CHECK_EQ(b.PreW(1), 200); CHECK_EQ(b.PreH(1), 180);          // k = min(3, 2) = 2
	CHECK_EQ(b.OffX(1), 50); CHECK_EQ(b.OffY(1), 10);            // re-centred after scaling
	int rx, ry;
	CHECK(b.ConvertToRealPos(1, 50, 10, rx, ry)); CHECK_EQ(rx, 0); CHECK_EQ(ry, 0);
	CHECK(b.ConvertToRealPos(1, 249, 189, rx, ry)); CHECK_EQ(rx, 99); CHECK_EQ(ry, 89);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_SMOOTH);
	CHECK_EQ(b.PreW(1), 222); CHECK_EQ(b.PreH(1), 200);          // s = min(3, 2.22): height touches
	CHECK_EQ(b.OffX(1), 39); CHECK_EQ(b.OffY(1), 0);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);
	CHECK_EQ(b.PreW(0), 135); CHECK_EQ(b.PreH(0), 90);           // s = max(1/3, 0.45)
	CHECK_EQ(b.OffX(1), 17); CHECK_EQ(b.OffY(1), 0);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_NONE);
	CHECK_EQ(b.OffX(1), 100); CHECK_EQ(b.OffY(1), 55);
	FreeImage_DeInitialise();
	return Summary("test_combined");
}
