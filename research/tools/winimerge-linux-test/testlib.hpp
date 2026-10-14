// Minimal helpers for testing CImgDiffBuffer/CImgMergeBuffer on Linux.
#pragma once
#include <climits>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <string>
#include <functional>
#include "ImgMergeBuffer.hpp"

static int g_failures = 0, g_checks = 0;
#define CHECK(cond) do { ++g_checks; if (!(cond)) { ++g_failures; std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); } } while (0)
#define CHECK_EQ(a, b) do { ++g_checks; auto _a = (a); auto _b = (b); if (!(_a == _b)) { ++g_failures; std::printf("FAIL %s:%d: %s == %s (got %lld vs %lld)\n", __FILE__, __LINE__, #a, #b, (long long)_a, (long long)_b); } } while (0)

// Fill an Image (32-bit BGRA) with a function of (x, y) -> 0xAARRGGBB
inline Image MakeImage(int w, int h, std::function<unsigned(int, int)> f)
{
	Image img(w, h);
	for (int y = 0; y < h; ++y)
	{
		unsigned char *p = img.scanLine(y);
		for (int x = 0; x < w; ++x)
		{
			unsigned c = f(x, y);
			p[x * 4 + 0] = c & 0xff;
			p[x * 4 + 1] = (c >> 8) & 0xff;
			p[x * 4 + 2] = (c >> 16) & 0xff;
			p[x * 4 + 3] = (c >> 24) & 0xff;
		}
	}
	return img;
}

class TestBuffer : public CImgMergeBuffer
{
public:
	// Equivalent of OpenImages() for in-memory images (FreeImage_LoadU is Windows-only).
	void SetImages(int n, const Image *images)
	{
		CloseImages();
		m_nImages = n;
		for (int i = 0; i < n; ++i)
		{
			m_filename[i] = L"mem" + std::to_wstring(i) + L".png";
			m_currentPage[i] = 0;
			m_imgOrig[i] = images[i];
			m_imgOrig32[i] = images[i];
			m_imgOrig32[i].convertTo32Bits();
			m_angle[i] = 0.f;
			m_horizontalFlip[i] = false;
			m_verticalFlip[i] = false;
		}
	}
	bool OpenFiles(int n, const char *const files[])
	{
		CloseImages();
		m_nImages = n;
		for (int i = 0; i < n; ++i)
		{
			m_filename[i] = std::wstring(files[i], files[i] + std::strlen(files[i]));
			m_currentPage[i] = 0;
			if (!m_imgOrig[i].getFipImage()->load(files[i]))
				return false;
			m_imgOrig32[i] = m_imgOrig[i];
			m_imgOrig32[i].convertTo32Bits();
			m_angle[i] = 0.f;
			m_horizontalFlip[i] = false;
			m_verticalFlip[i] = false;
		}
		return true;
	}
	int OffX(int pane) const { return static_cast<int>(GetImageOffset(pane).x); }
	int OffY(int pane) const { return static_cast<int>(GetImageOffset(pane).y); }
	int CanvasW() const { return GetDiffImageWidth(); }
	int CanvasH() const { return GetDiffImageHeight(); }
	int PreW(int pane) const { return GetPreprocessedImageWidth(pane); }
	int PreH(int pane) const { return GetPreprocessedImageHeight(pane); }
	void Save(int pane, const char *name) { SaveDiffImageAs(pane, std::wstring(name, name + std::strlen(name)).c_str()); }
};

inline int Summary(const char *name)
{
	std::printf("%s: %d checks, %d failures\n", name, g_checks, g_failures);
	return g_failures ? 1 : 0;
}
