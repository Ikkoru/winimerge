// Delete on a rotated, non-square image must stay inside the image (rotation swaps width and height).
// Build/run with AddressSanitizer: EXTRA_CXXFLAGS="-fsanitize=address" ./build.sh /path/to/winimerge test_bounds_rotated.cpp
#include "testlib.hpp"

static const unsigned BLUE = 0xff0000ff;
static Image Solid(int w, int h, unsigned c) { return MakeImage(w, h, [c](int, int) { return c; }); }

int main()
{
	FreeImage_Initialise();
	TestBuffer b;
	Image imgs[2] = { Solid(100, 100, BLUE), Solid(60, 20, BLUE) };
	b.SetImages(2, imgs);
	b.SetRotation(1, 90.f);   // shown 20 wide and 60 tall
	b.CompareImages();
	// inside the stored 60x20 bitmap but past the shown 20-wide image: must not write past the rows
	CHECK(b.DeleteRectangle(1, 0, 0, 60, 20));
	CHECK_EQ(b.GetImageWidth(1), 20);
	// the lower part of the shown image (y 40..60) lies outside the stored bitmap's 20 rows: still deleted
	CHECK(b.DeleteRectangle(1, 0, 40, 20, 60));
	FreeImage_DeInitialise();
	return Summary("test_bounds_rotated");
}
