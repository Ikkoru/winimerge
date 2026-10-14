// Timing of the scaling modes at the brief's example size: 1000x1500 vs 4000x6000.
#include "testlib.hpp"
#include <chrono>
#include <cmath>

static double ms(std::chrono::steady_clock::time_point a) { return std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - a).count(); }

int main()
{
	FreeImage_Initialise();
	auto pat = [](int x, int y) { const int v = (int)(128 + 100 * std::sin(x * 0.013) * std::cos(y * 0.011)) + (((x / 37 + y / 23) & 1) ? 20 : -20);
		const unsigned c = (unsigned)std::max(0, std::min(255, v)); return 0xff000000u | c << 16 | (255 - c) << 8 | ((c * 3) & 0xff); };
	Image large = MakeImage(4000, 6000, pat);
	Image small;
	{ FIBITMAP *d = FreeImage_Rescale(static_cast<FIBITMAP *>(*const_cast<fipImageEx *>(large.getImage())), 1000, 1500, FILTER_CATMULLROM); *small.getFipImage() = d; }
	TestBuffer b;
	Image imgs[2] = { large, small };
	b.SetImages(2, imgs);
	auto t = std::chrono::steady_clock::now();
	b.CompareImages();                                                    std::printf("compare, no scaling:            %7.0f ms\n", ms(t));
	t = std::chrono::steady_clock::now(); b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_NEAREST_INTEGER); std::printf("UP_NEAREST_INTEGER (x4):       %7.0f ms\n", ms(t));
	t = std::chrono::steady_clock::now(); b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_UP_SMOOTH);          std::printf("UP_SMOOTH (Lanczos3):           %7.0f ms\n", ms(t));
	t = std::chrono::steady_clock::now(); b.SetColorDistanceThreshold(16.0);                                        std::printf("  option change (cached):       %7.0f ms\n", ms(t));
	t = std::chrono::steady_clock::now(); b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_DOWN_MATCHED);        std::printf("DOWN_MATCHED, first (matching): %7.0f ms  diffs=%d\n", ms(t), b.GetDiffCount());
	t = std::chrono::steady_clock::now(); b.SetColorDistanceThreshold(8.0);                                         std::printf("  option change (cached):       %7.0f ms\n", ms(t));
	t = std::chrono::steady_clock::now(); b.DeleteRectangle(0, 100, 100, 400, 400);                                 std::printf("  edit of the large image:      %7.0f ms\n", ms(t));
	t = std::chrono::steady_clock::now(); b.DeleteRectangle(1, 10, 10, 50, 50);                                     std::printf("  edit of the small image:      %7.0f ms\n", ms(t));
	t = std::chrono::steady_clock::now(); b.SetImageScalingMode(CImgDiffBuffer::IMAGE_SCALING_NONE);                std::printf("back to NONE:                   %7.0f ms\n", ms(t));
	FreeImage_DeInitialise();
	return 0;
}
