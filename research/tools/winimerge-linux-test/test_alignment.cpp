// Unit tests for the image alignment option (CImgDiffBuffer::SetImageAlignment).
// Build/run: ./build.sh /home/user/winimerge test_alignment.cpp
#include "testlib.hpp"

static const unsigned RED = 0xffff0000, BLUE = 0xff0000ff, WHITE = 0xffffffff, BLACK = 0xff000000;

static Image Solid(int w, int h, unsigned c) { return MakeImage(w, h, [c](int, int) { return c; }); }

#ifndef NO_ALIGNMENT_API
static void TestAllAnchors()
{
	TestBuffer b;
	Image imgs[2] = { Solid(100, 80, RED), Solid(60, 40, RED) };
	b.SetImages(2, imgs);
	b.CompareImages();
	CHECK_EQ(b.OffX(1), 0); CHECK_EQ(b.OffY(1), 0);   // default: top-left, unchanged behaviour
	for (int a = 0; a < 9; ++a)
	{
		b.SetImageAlignment(static_cast<CImgDiffBuffer::IMAGE_ALIGNMENT>(a));
		CHECK_EQ(b.OffX(0), 0); CHECK_EQ(b.OffY(0), 0);
		CHECK_EQ(b.OffX(1), (a % 3) * 20); CHECK_EQ(b.OffY(1), (a / 3) * 20);
		CHECK_EQ(b.CanvasW(), 100); CHECK_EQ(b.CanvasH(), 80);
	}
}

static void TestCrossedSizes()
{
	// wider-but-shorter vs narrower-but-taller: each is centered along the other's larger dimension
	TestBuffer b;
	Image imgs[2] = { Solid(100, 40, RED), Solid(60, 80, RED) };
	b.SetImages(2, imgs);
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_CENTER);
	b.CompareImages();
	CHECK_EQ(b.OffX(0), 0); CHECK_EQ(b.OffY(0), 20);
	CHECK_EQ(b.OffX(1), 20); CHECK_EQ(b.OffY(1), 0);
	CHECK_EQ(b.CanvasW(), 100); CHECK_EQ(b.CanvasH(), 80);
}

static void TestOddDifference()
{
	TestBuffer b;
	Image imgs[2] = { Solid(101, 101, RED), Solid(60, 60, RED) };
	b.SetImages(2, imgs);
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_CENTER);
	b.CompareImages();
	CHECK_EQ(b.OffX(1), 20); CHECK_EQ(b.OffY(1), 20);  // floor(41 / 2)
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_BOTTOM_RIGHT);
	CHECK_EQ(b.OffX(1), 41); CHECK_EQ(b.OffY(1), 41);
}

static void TestThreePanes()
{
	TestBuffer b;
	Image imgs[3] = { Solid(100, 100, RED), Solid(50, 50, RED), Solid(80, 60, RED) };
	b.SetImages(3, imgs);
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_CENTER);
	b.CompareImages();
	CHECK_EQ(b.OffX(0), 0); CHECK_EQ(b.OffY(0), 0);
	CHECK_EQ(b.OffX(1), 25); CHECK_EQ(b.OffY(1), 25);
	CHECK_EQ(b.OffX(2), 10); CHECK_EQ(b.OffY(2), 20);
}

static void TestManualOffsetIsKept()
{
	TestBuffer b;
	Image imgs[2] = { Solid(100, 80, RED), Solid(60, 40, RED) };
	b.SetImages(2, imgs);
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_CENTER);
	b.CompareImages();
	b.AddImageOffset(1, 5, -3);
	CHECK_EQ(b.OffX(1), 25); CHECK_EQ(b.OffY(1), 17);
	// switching back to top-left keeps the user's nudge relative to the new anchor
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_TOP_LEFT);
	CHECK_EQ(b.OffX(0), 0); CHECK_EQ(b.OffY(0), 3);
	CHECK_EQ(b.OffX(1), 5); CHECK_EQ(b.OffY(1), 0);
	// re-centering
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_CENTER);
	CHECK_EQ(b.OffX(0), 0); CHECK_EQ(b.OffY(0), 0);
	CHECK_EQ(b.OffX(1), 25); CHECK_EQ(b.OffY(1), 17);
	// reopening resets user offsets
	b.SetImages(2, imgs);
	b.CompareImages();
	CHECK_EQ(b.OffX(1), 20); CHECK_EQ(b.OffY(1), 20);
}

static void TestCenteredContentMatches()
{
	// A: 100x100 white canvas with a 60x60 pattern at (20,20); B: the pattern alone.
	auto pattern = [](int x, int y) { return ((x / 7 + y / 5) % 2) ? BLACK : RED; };
	Image a = MakeImage(100, 100, [&](int x, int y) {
		return (x >= 20 && x < 80 && y >= 20 && y < 80) ? pattern(x - 20, y - 20) : WHITE; });
	Image bimg = MakeImage(60, 60, pattern);
	TestBuffer b;
	Image imgs[2] = { a, bimg };
	b.SetImages(2, imgs);
	b.SetDiffBlockSize(4);
	b.CompareImages();
	const int diffsTopLeft = b.GetDiffCount();
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_CENTER);
	// Only the area outside B (one ring) differs once centered.
	CHECK_EQ(b.GetDiffCount(), 1);
	CHECK(diffsTopLeft >= 1);
	// The pixel at canvas (50,50) is the same in both panes when centered.
	CHECK_EQ(b.GetColorDistance(0, 1, 50, 50), 0.0);
	CHECK_EQ(b.GetColorDistance(0, 1, 21, 79), 0.0);
	int rx, ry;
	CHECK(b.ConvertToRealPos(1, 20, 20, rx, ry));
	CHECK_EQ(rx, 0); CHECK_EQ(ry, 0);
	CHECK(!b.ConvertToRealPos(1, 19, 50, rx, ry));
}

static void TestRotationRealigns()
{
	TestBuffer b;
	Image imgs[2] = { Solid(100, 100, RED), Solid(60, 40, RED) };
	b.SetImages(2, imgs);
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_CENTER);
	b.CompareImages();
	CHECK_EQ(b.OffX(1), 20); CHECK_EQ(b.OffY(1), 30);
	b.SetRotation(1, 90.f);
	CHECK_EQ(b.PreW(1), 40); CHECK_EQ(b.PreH(1), 60);
	CHECK_EQ(b.OffX(1), 30); CHECK_EQ(b.OffY(1), 20);
}

static void TestCopyDiffDoesNotMoveImages()
{
	// A: 100x60 with distinct left and right margins; B: 60x60 equal to A's middle.
	auto middle = [](int x, int y) { return ((x + y) % 3) ? BLUE : WHITE; };
	Image a = MakeImage(100, 60, [&](int x, int y) {
		if (x < 20) return RED; if (x >= 80) return BLACK; return middle(x - 20, y); });
	Image bimg = MakeImage(60, 60, middle);
	TestBuffer b;
	Image imgs[2] = { a, bimg };
	b.SetImages(2, imgs);
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_CENTER);
	b.CompareImages();
	CHECK_EQ(b.OffX(1), 20);
	CHECK_EQ(b.GetDiffCount(), 2);           // left margin, right margin
	// Copy the left-margin difference into B: B grows to the left and must stay in place.
	int leftDiff = -1;
	for (int i = 0; i < b.GetDiffCount(); ++i)
		if (b.GetDiffInfo(i)->rc.left == 0)
			leftDiff = i;
	CHECK(leftDiff >= 0);
	b.CopyDiff(leftDiff, 0, 1);
	CHECK_EQ(b.GetImageWidth(1), 80);
	CHECK_EQ(b.OffX(0), 0); CHECK_EQ(b.OffX(1), 0);
	CHECK_EQ(b.GetDiffCount(), 1);           // only the right margin is left
	CHECK_EQ(b.GetColorDistance(0, 1, 50, 30), 0.0);
	CHECK_EQ(b.GetColorDistance(0, 1, 5, 30), 0.0);
	// Note: copying the right-margin difference as well does not work on master either:
	// CopyDiffInternal() grows the image to the right but ConvertToRealPos() still checks
	// against the old preprocessed width, so the new columns stay empty (pre-existing issue).
}

static void TestInsertionDeletionDetection()
{
	TestBuffer b;
	Image a = MakeImage(100, 80, [](int x, int y) { return (y % 10 < 5) ? RED : BLUE; });
	Image c = MakeImage(60, 50, [](int x, int y) { return (y % 10 < 5) ? RED : BLUE; });
	Image imgs[2] = { a, c };
	b.SetImages(2, imgs);
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_CENTER);
	b.SetInsertionDeletionDetectionMode(CImgDiffBuffer::INSERTION_DELETION_DETECTION_VERTICAL);
	b.CompareImages();
	CHECK_EQ(b.PreH(0), b.PreH(1));          // ghost lines equalize the heights
	CHECK_EQ(b.OffX(1), 20);
	CHECK_EQ(b.OffY(0), 0); CHECK_EQ(b.OffY(1), 0);
	b.SetInsertionDeletionDetectionMode(CImgDiffBuffer::INSERTION_DELETION_DETECTION_NONE);
	CHECK_EQ(b.OffX(1), 20); CHECK_EQ(b.OffY(1), 15);
}

static void TestNoImages()
{
	TestBuffer b;
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_CENTER);   // no images: must not crash
	Image imgs[1] = { Solid(10, 10, RED) };
	b.SetImages(1, imgs);
	b.SetImageAlignment(CImgDiffBuffer::IMAGE_ALIGNMENT_BOTTOM_RIGHT);
	CHECK(true);
}
#endif

// Behaviour that must be identical with and without the alignment change (default = top-left).
static void TestDefaultOffsets()
{
	TestBuffer b;
	Image imgs[2] = { Solid(100, 80, RED), Solid(60, 40, BLUE) };
	b.SetImages(2, imgs);
	b.CompareImages();
	CHECK_EQ(b.OffX(1), 0); CHECK_EQ(b.OffY(1), 0);
	CHECK_EQ(b.CanvasW(), 100); CHECK_EQ(b.CanvasH(), 80);
	b.AddImageOffset(1, 10, 7);
	CHECK_EQ(b.OffX(1), 10); CHECK_EQ(b.OffY(1), 7);
	b.AddImageOffset(1, -15, 0);
	CHECK_EQ(b.OffX(0), 5); CHECK_EQ(b.OffX(1), 0); CHECK_EQ(b.OffY(1), 7);
	CHECK_EQ(b.CanvasW(), 105); CHECK_EQ(b.CanvasH(), 80);
	b.SetRotation(1, 90.f);
	CHECK_EQ(b.OffX(0), 5); CHECK_EQ(b.OffX(1), 0); CHECK_EQ(b.OffY(1), 7);
	CHECK_EQ(b.GetDiffCount(), 1);
}

int main()
{
	FreeImage_Initialise();
	TestDefaultOffsets();
#ifndef NO_ALIGNMENT_API
	TestAllAnchors();
	TestCrossedSizes();
	TestOddDifference();
	TestThreePanes();
	TestManualOffsetIsKept();
	TestCenteredContentMatches();
	TestRotationRealigns();
	TestCopyDiffDoesNotMoveImages();
	TestInsertionDeletionDetection();
	TestNoImages();
#endif
	FreeImage_DeInitialise();
	return Summary("test_alignment");
}
