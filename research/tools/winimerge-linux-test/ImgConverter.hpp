// Stub of WinIMergeLib/ImgConverter.hpp for building the platform-independent
// diff/merge buffer (ImgDiffBuffer.hpp, ImgMergeBuffer.hpp) on Linux.
// The real file renders PDF/SVG/EMF/WIC images through Windows APIs.
#pragma once
#include "image.hpp"

class ImgConverter
{
public:
	static bool isSupportedImage(const wchar_t *) { return false; }
	bool isValid() const { return false; }
	bool load(const wchar_t *) { return false; }
	void close() {}
	void render(Image&, int, float) {}
	unsigned getPageCount() const { return 1; }
};
