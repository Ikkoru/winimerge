// Deleting or pasting a rectangle that extends beyond the image must stay inside the image.
// Build/run (with AddressSanitizer): EXTRA_CXXFLAGS="-fsanitize=address" ./build.sh /home/user/winimerge test_bounds.cpp
#include "testlib.hpp"

static const unsigned RED = 0xffff0000, BLUE = 0xff0000ff;

class BoundsTestBuffer : public TestBuffer
{
public:
	unsigned At(int pane, int x, int y) const { const unsigned char *p = m_imgOrig32[pane].scanLine(y) + x * 4; return (unsigned)p[0] | p[1] << 8 | p[2] << 16 | (unsigned)p[3] << 24; }
	int Count(int pane, unsigned c) const { int n = 0; for (unsigned y = 0; y < m_imgOrig32[pane].height(); ++y) for (unsigned x = 0; x < m_imgOrig32[pane].width(); ++x) n += At(pane, x, y) == c; return n; }
};

static Image Solid(int w, int h, unsigned c) { return MakeImage(w, h, [c](int, int) { return c; }); }

int main()
{
	FreeImage_Initialise();
	BoundsTestBuffer b;
	Image imgs[2] = { Solid(100, 100, BLUE), Solid(60, 60, BLUE) };
	b.SetImages(2, imgs);
	b.CompareImages();
	// a selection starting left of the smaller image: only the part inside is erased
	CHECK(b.DeleteRectangle(1, -15, 10, 20, 20));
	CHECK_EQ(b.Count(1, BLUE), 60 * 60 - 20 * 10);
	CHECK_EQ(b.GetImageWidth(1), 60);
	// a selection reaching past the right and bottom edges
	CHECK(b.DeleteRectangle(1, 30, 30, 80, 80));
	CHECK_EQ(b.Count(1, BLUE), 60 * 60 - 20 * 10 - 30 * 30);
	// a selection entirely outside erases nothing
	CHECK(b.DeleteRectangle(1, 70, 70, 90, 90));
	CHECK_EQ(b.Count(1, BLUE), 60 * 60 - 20 * 10 - 30 * 30);
	// pasting right of or below the image changes nothing; pasting across the top-left corner is cut
	Image red = Solid(20, 20, RED);
	b.PasteImage(1, 70, 10, red);
	b.PasteImage(1, 10, 70, red);
	b.PasteImage(1, 60, 60, red);
	CHECK_EQ(b.Count(1, RED), 0);
	b.PasteImage(1, -5, -5, red);
	CHECK_EQ(b.Count(1, RED), 15 * 15);
	b.PasteImage(1, 50, 50, red);
	CHECK_EQ(b.Count(1, RED), 15 * 15 + 10 * 10);
	FreeImage_DeInitialise();
	return Summary("test_bounds");
}
