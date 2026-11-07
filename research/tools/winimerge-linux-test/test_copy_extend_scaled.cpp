// With Size Matching on, copying a difference into a scaled pane never enlarges that image (needs the
// scale branch or a tree that contains it): the area past the scaled image belongs to the canvas, not to it.
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
	{   // whole-number NN: 45x45 is shown at 2x (90x90) on a 100x100 canvas
		CopyTestBuffer b;
		Image imgs[2] = { Solid(100, 100, RED), Solid(45, 45, BLUE) };
		b.SetImages(2, imgs);
		b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_NEAREST_INTEGER);
		b.CompareImages();
		CHECK(b.GetDiffCount() >= 1);
		b.CopyDiffAll(0, 1);
		CHECK_EQ(b.GetImageWidth(1), 45);    // not enlarged to the canvas
		CHECK_EQ(b.GetImageHeight(1), 45);
		CHECK_EQ(b.At(1, 10, 10), RED);      // the part the scaled image covers was copied
		CHECK_EQ(b.At(1, 44, 44), RED);
	}
	{   // shrink to smallest: the 100x100 image is shown at 50x50; copying into it is refused, nothing grows
		CopyTestBuffer b;
		Image imgs[2] = { Solid(100, 100, RED), Solid(50, 50, BLUE) };
		b.SetImages(2, imgs);
		b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);
		b.CompareImages();
		b.CopyDiffAll(1, 0);
		CHECK_EQ(b.GetImageWidth(0), 100);
		CHECK_EQ(b.At(0, 10, 10), RED);
	}
	FreeImage_DeInitialise();
	return Summary("test_copy_extend_scaled");
}
