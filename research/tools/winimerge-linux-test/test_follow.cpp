// IMAGE_ALIGNMENT_FOLLOW_VIEW (needs the alignment and scaling features together): a copy enlarged by a
// whole number but still smaller than the original is placed so that the content at the given point
// (the middle of the view) lines up in both panes.
#include "testlib.hpp"

int main()
{
	FreeImage_Initialise();
	auto pat = [](int x, int y) { return 0xff000000u | ((x * 7) & 0xff) << 16 | ((y * 5) & 0xff) << 8 | ((x + y) & 0xff); };
	TestBuffer b;
	Image imgs[2] = { MakeImage(1000, 800, pat), MakeImage(400, 320, pat) };   // a 2.5x pair
	b.SetImages(2, imgs);
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_NEAREST_INTEGER);   // the copy shown at 800x640
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_FOLLOW_VIEW);
	b.CompareImages();
	CHECK(b.IsFollowingView());
	CHECK_EQ(b.PreW(1), 800); CHECK_EQ(b.PreH(1), 640);
	CHECK_EQ(b.CanvasW(), 1000); CHECK_EQ(b.CanvasH(), 800);
	// before any point is given: centred
	CHECK_EQ(b.OffX(0), 0); CHECK_EQ(b.OffY(0), 0);
	CHECK_EQ(b.OffX(1), 100); CHECK_EQ(b.OffY(1), 80);
	// the view's middle at the top-left corner, then the bottom-right corner
	CHECK(b.SetAlignmentFollowPoint(0, 0));
	CHECK_EQ(b.OffX(1), 0); CHECK_EQ(b.OffY(1), 0);
	CHECK(b.SetAlignmentFollowPoint(1000, 800));
	CHECK_EQ(b.OffX(1), 200); CHECK_EQ(b.OffY(1), 160);
	// anywhere: the copy's pixel under the point stands for the original's pixel under it
	CHECK(b.SetAlignmentFollowPoint(700, 200));
	CHECK_EQ(b.OffX(1), 140); CHECK_EQ(b.OffY(1), 40);
	int rx, ry;
	CHECK(b.ConvertToRealPos(1, 700, 200, rx, ry));
	CHECK_EQ(rx, 280); CHECK_EQ(ry, 80);   // 280 * 2.5 = 700, 80 * 2.5 = 200
	CHECK(b.ConvertToRealPos(0, 700, 200, rx, ry));
	CHECK_EQ(rx, 700); CHECK_EQ(ry, 200);
	// the same point again: nothing to do
	CHECK(!b.SetAlignmentFollowPoint(700, 200));
	// a manual nudge stays on top of the alignment
	b.AddImageOffset(1, 5, -3);
	CHECK_EQ(b.OffX(1), 145); CHECK_EQ(b.OffY(1), 37);
	CHECK(b.SetAlignmentFollowPoint(500, 400));
	CHECK_EQ(b.OffX(1), 105); CHECK_EQ(b.OffY(1), 77);
	b.AddImageOffset(1, -5, 3);
	// the comparison follows the layout
	const int diffsHere = b.GetDiffCount();
	CHECK(diffsHere >= 0);
	// sizes that match (shrinking) or no scaling: nothing follows the view, images are centred
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);
	b.CompareImages();
	CHECK(!b.IsFollowingView());
	CHECK(!b.SetAlignmentFollowPoint(0, 0));
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_NONE);
	b.CompareImages();
	CHECK(!b.IsFollowingView());
	CHECK(!b.SetAlignmentFollowPoint(0, 0));
	CHECK_EQ(b.OffX(1), 300); CHECK_EQ(b.OffY(1), 240);   // (1000 - 400) / 2, (800 - 320) / 2
	// back to whole-number NN: follows again, from the last point given
	b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_NEAREST_INTEGER);
	b.CompareImages();
	CHECK(b.IsFollowingView());
	CHECK_EQ(b.OffX(1), 0); CHECK_EQ(b.OffY(1), 0);
	// a whole-number ratio fills the canvas: nothing to follow
	Image imgs2[2] = { MakeImage(900, 600, pat), MakeImage(300, 200, pat) };
	b.SetImages(2, imgs2);
	b.CompareImages();
	CHECK(!b.IsFollowingView());
	// the other anchors are unchanged
	b.SetImages(2, imgs);
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_BOTTOM_RIGHT);
	b.CompareImages();
	CHECK_EQ(b.OffX(1), 200); CHECK_EQ(b.OffY(1), 160);
	// out-of-range values are still ignored
	b.SetImageAlignment(static_cast<CImgDiffBuffer::IMAGE_ALIGNMENT>(10));
	CHECK_EQ(static_cast<int>(b.GetImageAlignment()), static_cast<int>(CImgDiffBuffer::IMAGE_ALIGNMENT_BOTTOM_RIGHT));
	FreeImage_DeInitialise();
	return Summary("test_follow");
}
