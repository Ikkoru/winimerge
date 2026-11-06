// Copying a difference that lies right of or below a smaller image enlarges it and fills the new area
// in one go (upstream #42), also on the scaling branch when nothing is scaled.
#include "testlib.hpp"

static const unsigned RED = 0xffff0000, BLUE = 0xff0000ff;
static Image Solid(int w, int h, unsigned c) { return MakeImage(w, h, [c](int, int) { return c; }); }

class CopyTestBuffer : public TestBuffer
{
public:
	unsigned At(int pane, int x, int y) const { const unsigned char *p = m_imgOrig32[pane].scanLine(y) + x * 4; return (unsigned)p[0] | p[1] << 8 | p[2] << 16 | (unsigned)p[3] << 24; }
};

int main()
{
	FreeImage_Initialise();
	CopyTestBuffer b;
	Image imgs[2] = { Solid(100, 100, RED), Solid(60, 60, BLUE) };
	b.SetImages(2, imgs);
	b.CompareImages();
	CHECK(b.GetDiffCount() >= 1);
	b.CopyDiffAll(0, 1);
	CHECK_EQ(b.GetImageWidth(1), 100);
	CHECK_EQ(b.GetImageHeight(1), 100);
	CHECK_EQ(b.At(1, 90, 90), RED);   // in the enlarged area, filled at the first copy
	CHECK_EQ(b.At(1, 10, 10), RED);
	b.CompareImages();
	CHECK_EQ(b.GetDiffCount(), 0);
	FreeImage_DeInitialise();
	return Summary("test_copy_extend");
}
