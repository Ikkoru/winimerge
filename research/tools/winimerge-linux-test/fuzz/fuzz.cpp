// Randomized stress test of CImgMergeBuffer driven like the UI (build with ASan/UBSan).
// -DHAS_ALIGN / -DHAS_SCALE enable the ops of the branch under test (RNG consumption is identical
// either way, so the same seed runs the same sequence on every tree; disabled ops are no-ops).
// -DUI_RECTS: DeleteRectangle/CopySubImage get the unclamped rectangles the UI computes.
// Each iteration runs in a child process; on abnormal exit the op log is printed.
// Output per iteration (when DIGEST is set): a digest of the final state, for differential runs.
#include "testlib.hpp"
#include <random>
#include <cstdlib>
#include <cstdarg>
#include <unistd.h>
#include <sys/wait.h>

static std::mt19937 rng;
static int R(int lo, int hi) { return std::uniform_int_distribution<int>(lo, hi)(rng); }
static FILE *g_log;
static void Log(const char *fmt, ...)
{
	va_list ap; va_start(ap, fmt); vfprintf(g_log, fmt, ap); va_end(ap); fputc('\n', g_log); fflush(g_log);
}

static Image RandomImage(int w, int h, int seed)
{
	return MakeImage(w, h, [seed](int x, int y) {
		unsigned v = (unsigned)((x / 3) * 7 + (y / 2) * 13 + seed);
		return 0xff000000u | ((v * 37) & 0xff) << 16 | ((v * 11) & 0xff) << 8 | (v & 0xc0);
	});
}

static Image Derive(const Image& src, int seed)
{
	std::mt19937 r(seed);
	int w = src.width(), h = src.height();
	int insRow = r() % (h + 1), nIns = r() % 3, delRow = r() % (h ? h : 1), nDel = (h > 3) ? r() % 2 : 0;
	std::vector<std::vector<unsigned>> rows;
	for (int y = 0; y < h; ++y)
	{
		std::vector<unsigned> row(w);
		for (int x = 0; x < w; ++x)
		{
			const unsigned char *p = src.scanLine(y) + x * 4;
			row[x] = p[0] | p[1] << 8 | p[2] << 16 | (unsigned)p[3] << 24;
		}
		rows.push_back(row);
	}
	for (int i = 0; i < nDel && delRow < (int)rows.size(); ++i)
		rows.erase(rows.begin() + delRow);
	for (int i = 0; i < nIns; ++i)
		rows.insert(rows.begin() + (std::min)(insRow, (int)rows.size()), std::vector<unsigned>(w, 0xff00ff00u + i));
	if (rows.empty())
		rows.push_back(std::vector<unsigned>(w, 0xff123456u));
	for (auto& row : rows)
		if (!row.empty() && r() % 4 == 0)
			row[r() % row.size()] ^= 0x00ffffff;
	int nh = rows.size();
	return MakeImage(w, nh, [&](int x, int y) { return rows[y][x]; });
}

class FuzzBuffer : public TestBuffer
{
public:
	void RealRect(int pane, int l, int t, int r, int b, int& rl, int& rt, int& rr, int& rb) const
	{
#ifdef HAS_SCALE
		ConvertToRealEdgePos(pane, l, t, rl, rt, false);
		ConvertToRealEdgePos(pane, r, b, rr, rb, false);
#else
		ConvertToRealPos(pane, l, t, rl, rt, false);
		ConvertToRealPos(pane, r, b, rr, rb, false);
#endif
	}
	unsigned long long Digest() const
	{
		unsigned long long h = 1469598103934665603ULL;
		auto mix = [&](unsigned long long v) { h = (h ^ v) * 1099511628211ULL; };
		mix(m_nImages); mix(GetDiffCount()); mix(GetDiffImageWidth()); mix(GetDiffImageHeight());
		for (int i = 0; i < m_nImages; ++i)
		{
			mix(m_offset[i].x); mix(m_offset[i].y);
			const Image& img = m_imgOrig32[i];
			mix(img.width()); mix(img.height());
			for (unsigned y = 0; y < img.height(); ++y)
				for (unsigned x = 0; x < img.width() * 4; ++x)
					mix(img.scanLine(y)[x]);
		}
		return h;
	}
};

static void RunIteration(unsigned seed0, int it)
{
	rng.seed(seed0 * 100003u + it);
	FuzzBuffer b;
	const int n = R(2, 3);
	Image imgs[3];
	Image base = RandomImage(R(1, 40), R(1, 40), R(0, 1000));
	for (int i = 0; i < n; ++i)
	{
		int kind = R(0, 3), a = R(1, 40), c = R(1, 40), d = R(0, 1 << 20), e = R(1, 3), f = R(1, 3);
		switch (kind)
		{
		case 0: imgs[i] = base; break;
		case 1: imgs[i] = Derive(base, d); break;
		case 2: imgs[i] = RandomImage(a, c, d % 1000); break;
		default: imgs[i] = RandomImage(base.width() * e, base.height() * f, d % 10); break;
		}
		Log("img %d: %ux%u kind %d", i, imgs[i].width(), imgs[i].height(), kind);
	}
	b.SetImages(n, imgs);
	b.CompareImages();
	for (int step = 0; step < 40; ++step)
	{
		const int op = R(0, 22);
		const int pane = R(0, n - 1);
		const int other = (pane + R(1, n - 1)) % n;
		const int a = R(0, 1 << 20), c = R(0, 1 << 20), d = R(0, 1 << 20), e = R(0, 1 << 20);
		if (const char *skip = getenv("SKIP"))
		{
			char key[16]; snprintf(key, sizeof key, ",%d,", step);
			std::string sk = std::string(",") + skip + ",";
			if (sk.find(key) != std::string::npos)
				continue;
		}
		switch (op)
		{
		case 0:
#ifdef HAS_SCALE
			Log("SetImageScalingMode(%d)", a % 4);
			b.SetImageScalingMode(static_cast<CImgDiffBuffer::IMAGE_SCALING_MODE>(a % 4));
#endif
			break;
		case 1:
#ifdef HAS_ALIGN
			Log("SetImageAlignment(%d)", a % 9);
			b.SetImageAlignment(static_cast<CImgDiffBuffer::IMAGE_ALIGNMENT>(a % 9));
#endif
			break;
		case 2:
#ifdef NO_GHOST
			break;
#endif
			Log("SetInsertionDeletionDetectionMode(%d)", a % 3); b.SetInsertionDeletionDetectionMode(static_cast<CImgDiffBuffer::INSERTION_DELETION_DETECTION_MODE>(a % 3)); break;
		case 3: Log("SetDiffBlockSize(%d)", 1 << (a % 5)); b.SetDiffBlockSize(1 << (a % 5)); break;
		case 4: Log("SetColorDistanceThreshold(%d)", (a % 2) ? 0 : 1 + c % 60); b.SetColorDistanceThreshold((a % 2) ? 0.0 : 1 + c % 60); break;
		case 5: Log("SetRotation(%d, %d)", pane, 90 * (a % 4)); b.SetRotation(pane, 90.f * (a % 4)); break;
		case 6: Log("SetHorizontalFlip(%d, %d)", pane, a % 2); b.SetHorizontalFlip(pane, a % 2); break;
		case 7: Log("SetVerticalFlip(%d, %d)", pane, a % 2); b.SetVerticalFlip(pane, a % 2); break;
		case 8: Log("AddImageOffset(%d, %d, %d)", pane, a % 21 - 10, c % 21 - 10); b.AddImageOffset(pane, a % 21 - 10, c % 21 - 10); break;
		case 9: case 10:
			if (b.GetDiffCount() > 0) { int di = a % b.GetDiffCount(); Log("CopyDiff(%d, %d, %d)", di, pane, other); b.CopyDiff(di, pane, other); }
			break;
		case 11: Log("CopyDiffAll(%d, %d)", pane, other); b.CopyDiffAll(pane, other); break;
		case 12: if (n == 3) { Log("CopyDiff3Way(%d)", pane); b.CopyDiff3Way(pane); } break;
		case 13: case 14: Log("Undo()"); b.Undo(); break;
		case 15: Log("Redo()"); b.Redo(); break;
		case 16: Log("Resize(%d, %d, %d)", pane, 1 + a % 50, 1 + c % 50); b.Resize(pane, 1 + a % 50, 1 + c % 50); break;
		case 17:
		{
			int cw = b.CanvasW(), ch = b.CanvasH();
			if (cw <= 0 || ch <= 0) break;
			int l = a % (cw + 1), t = c % (ch + 1), r = d % (cw + 1), btm = e % (ch + 1);
			if (l > r) std::swap(l, r);
			if (t > btm) std::swap(t, btm);
			int rl, rt, rr, rb;
			b.RealRect(pane, l, t, r, btm, rl, rt, rr, rb);
#ifndef UI_RECTS
			const int W = b.GetImageWidth(pane), H = b.GetImageHeight(pane);
			rl = std::clamp(rl, 0, W); rr = std::clamp(rr, 0, W);
			rt = std::clamp(rt, 0, H); rb = std::clamp(rb, 0, H);
			if (rl > rr || rt > rb) break;
#endif
			Log("select canvas (%d,%d)-(%d,%d) -> real (%d,%d)-(%d,%d) on %d", l, t, r, btm, rl, rt, rr, rb, pane);
			Image sub;
			b.CopySubImage(pane, rl, rt, rr, rb, sub);
			b.DeleteRectangle(pane, rl, rt, rr, rb);
			break;
		}
		case 18:
		{
			Image p = RandomImage(1 + a % 20, 1 + c % 20, d % 99);
			int rl, rt, rr, rb;
			int x = e % (b.CanvasW() + 6) - 5, y = (e / 7) % (b.CanvasH() + 6) - 5;
			b.RealRect(pane, x, y, x + p.width(), y + p.height(), rl, rt, rr, rb);
#ifdef SAFE_PASTE
			// avoid the pre-existing PasteImageInternal crash for positions right of / below the image
			rl = (std::min)(rl, b.GetImageWidth(pane) - 1);
			rt = (std::min)(rt, b.GetImageHeight(pane) - 1);
#endif
			Log("PasteImage(%d, %d, %d, %ux%u)", pane, rl, rt, p.width(), p.height());
			b.PasteImage(pane, rl, rt, p);
			break;
		}
		case 19:
		{
			for (int y = -2; y < b.CanvasH() + 2; ++y)
				for (int x = -2; x < b.CanvasW() + 2; ++x)
				{
					int rx, ry;
					bool inside = b.ConvertToRealPos(pane, x, y, rx, ry);
					if (inside && (rx < 0 || ry < 0 || rx >= b.GetImageWidth(pane) || ry >= b.GetImageHeight(pane)))
					{
						Log("BAD ConvertToRealPos(%d, %d, %d) inside but (%d, %d) not in %dx%d",
							pane, x, y, rx, ry, b.GetImageWidth(pane), b.GetImageHeight(pane));
						std::printf("seed %u it %d: BAD ConvertToRealPos(%d, %d, %d) -> (%d, %d) not in %dx%d\n",
							seed0, it, pane, x, y, rx, ry, b.GetImageWidth(pane), b.GetImageHeight(pane));
						x = 1 << 29; y = 1 << 29;
					}
					(void)b.GetPixelColor(pane, x, y);
				}
			break;
		}
		case 20: Log("SetShowDifferences(%d)", a % 2); b.SetShowDifferences(a % 2); break;
		case 21: Log("SetDiffAlgorithm(%d)", a % 5); b.SetDiffAlgorithm(static_cast<CImgDiffBuffer::DIFF_ALGORITHM>(a % 5)); break;
		default: { int di = b.GetDiffCount() ? (int)(a % (b.GetDiffCount() + 1)) - 1 : -1; Log("SelectDiff(%d)", di); b.SelectDiff(di); break; }
		}
	}
	if (getenv("DIGEST"))
		std::printf("digest %u %d %016llx\n", seed0, it, b.Digest());
}

int main(int argc, char **argv)
{
	FreeImage_Initialise();
	const int iterations = argc > 1 ? atoi(argv[1]) : 200;
	const unsigned seed0 = argc > 2 ? atoi(argv[2]) : 1;
	const int only = argc > 3 ? atoi(argv[3]) : -1;
	int crashes = 0;
	char logname[256];
	const char *logdir = getenv("FUZZ_LOGDIR");
	snprintf(logname, sizeof logname, "%s/fuzzlog.%d", logdir ? logdir : "/tmp", (int)getpid());
	for (int it = (only >= 0 ? only : 0); it < (only >= 0 ? only + 1 : iterations); ++it)
	{
		fflush(stdout);
		pid_t pid = fork();
		if (pid == 0)
		{
			g_log = fopen(logname, "w");
			RunIteration(seed0, it);
			fflush(stdout);
			_exit(0);
		}
		int status = 0;
		waitpid(pid, &status, 0);
		if (!(WIFEXITED(status) && WEXITSTATUS(status) == 0))
		{
			++crashes;
			std::printf("CRASH seed %u it %d (status %d); op log:\n", seed0, it, status);
			FILE *f = fopen(logname, "r");
			char line[512];
			std::vector<std::string> lines;
			while (f && fgets(line, sizeof line, f))
				lines.push_back(line);
			if (f) fclose(f);
			for (size_t i = 0; i < lines.size(); ++i)
				if (i < 3 || i + 12 >= lines.size())
					std::printf("   %s", lines[i].c_str());
		}
	}
	std::printf("fuzz: %d crashes\n", crashes);
	FreeImage_DeInitialise();
	return crashes ? 1 : 0;
}
