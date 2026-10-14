// Build/run: ./build.sh <align-branch-checkout> test_alignment_undo3.cpp
// Three panes, centred, copies that grow images to the left, undo/redo in different orders.
#include "testlib.hpp"
static const unsigned RED = 0xffff0000, BLUE = 0xff0000ff, WHITE = 0xffffffff, BLACK = 0xff000000;
int main()
{
	FreeImage_Initialise();
	auto middle = [](int x, int y) { return ((x + y) % 3) ? BLUE : WHITE; };
	Image a = MakeImage(100, 60, [&](int x, int y) { if (x < 20) return RED; if (x >= 80) return BLACK; return middle(x - 20, y); });
	Image b = MakeImage(60, 60, middle);
	Image c = MakeImage(80, 60, [&](int x, int y) { if (x < 10) return RED; if (x >= 70) return BLACK; return middle(x - 10, y); });
	TestBuffer t;
	Image imgs[3] = { a, b, c };
	t.SetImages(3, imgs);
	t.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_CENTER);
	t.CompareImages();
	CHECK_EQ(t.OffX(0), 0); CHECK_EQ(t.OffX(1), 20); CHECK_EQ(t.OffX(2), 10);
	const int before[3] = { t.OffX(0), t.OffX(1), t.OffX(2) };
	int n0 = t.GetDiffCount();
	// copy every difference from pane 0 into pane 1 and pane 2 (they grow to the left and right)
	t.CopyDiffAll(0, 1);
	t.CopyDiffAll(0, 2);
	int g1 = t.GetImageWidth(1), g2 = t.GetImageWidth(2);
	CHECK(g1 > 60); CHECK(g2 > 80);
	const int after[3] = { t.OffX(0), t.OffX(1), t.OffX(2) };
	CHECK(t.Undo()); CHECK(t.Undo());
	CHECK_EQ(t.GetImageWidth(1), 60); CHECK_EQ(t.GetImageWidth(2), 80);
	CHECK_EQ(t.OffX(0), before[0]); CHECK_EQ(t.OffX(1), before[1]); CHECK_EQ(t.OffX(2), before[2]);
	CHECK_EQ(t.GetDiffCount(), n0);
	CHECK(t.Redo()); CHECK(t.Redo());
	CHECK_EQ(t.GetImageWidth(1), g1); CHECK_EQ(t.GetImageWidth(2), g2);
	CHECK_EQ(t.OffX(0), after[0]); CHECK_EQ(t.OffX(1), after[1]); CHECK_EQ(t.OffX(2), after[2]);
	// undo one, then a new copy (drops the redo record), then undo everything
	CHECK(t.Undo());
	t.CopyDiff3Way(2);
	while (t.Undo()) {}
	CHECK_EQ(t.GetImageWidth(1), 60); CHECK_EQ(t.GetImageWidth(2), 80);
	CHECK_EQ(t.OffX(1), before[1]); CHECK_EQ(t.OffX(2), before[2]);
	// same with the default alignment: offsets only from growth
	t.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_TOP_LEFT);
	CHECK_EQ(t.OffX(0), 0); CHECK_EQ(t.OffX(1), 0); CHECK_EQ(t.OffX(2), 0);
	FreeImage_DeInitialise();
	return Summary("test_undo3");
}
