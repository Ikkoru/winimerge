# MinGW syntax check for WinIMerge's Windows code

`mingw-syntax-check.sh` compiles WinIMerge's Windows-only C++ code and resource
scripts on Linux with the MinGW-w64 **i686** cross compiler. It only compiles:
it does not link and does not run anything. Use it after editing
`src/WinIMergeLib/*` or `src/WinIMerge/*` to find compile errors without a
Windows machine.

## Running it

```sh
# check /home/user/winimerge (the working tree, uncommitted edits included)
/home/user/research/tools/mingw-syntax-check.sh

# check another checkout (or its src/ directory)
/home/user/research/tools/mingw-syntax-check.sh /path/to/winimerge

# options
  -v / --verbose   also print warnings and the fixup details
  -k / --keep      keep the temporary copy and the raw compiler logs
  --obj            compile to .o (-c -O0) instead of -fsyntax-only
  --clang          also compile with clang++ --target=i686-w64-mingw32
```

* **Exit status:** 0 = every check passed, 1 = compile errors (printed with
  context and notes), 2 = setup problem (no toolchain, bad path, no FreeImage
  headers).
* **Time:** about 2–4 s on this 4-core box, depending on load (the TUs
  compile in parallel). `--obj` takes about 3.5–5 s and `--clang` about 4 s.
  The first run after a container restart took ~13 s while the toolchain was
  read from disk.
* **Validated:** passes (exit 0) on winimerge HEADs `da639cd`, `85df69b` and
  `139a6c0`, and on in-progress working trees. The injection tests below were
  re-run after a container restart on `139a6c0`: 12 of 12 behaved as
  expected.
* **Source tree:** it is never modified. The script copies `src/` to
  `$TMPDIR/mingw-check.XXXXXX` and makes its fixups there. Fixups keep line
  numbers, and paths in diagnostics are mapped back to the tree you passed.
  Column numbers can be off by one on lines changed by fixup F2.
* **Prerequisites:** `apt-get install -y g++-mingw-w64-i686 binutils-mingw-w64-i686`
  (installed here: GCC 13.2 "13-win32", mingw-w64 v11 headers). `--clang`
  also needs `clang++` (18.1 here).
* **Files** in `/home/user/research/tools/`:
  * `mingw-syntax-check.sh`: the checker.
  * `mingw-shim.h`: the force-included shim (only `#include <cmath>`).
  * `freeimage-include/FreeImage.h`, `freeimage-include/FreeImagePlus.h`:
    unmodified copies from github.com/WinMerge/freeimage at commit `c893af9`
    (2026-09-02). Set `FREEIMAGE_DIR=<freeimage checkout>` to use other
    headers.

Example run on a tree with one injected mistake:

```
mingw-syntax-check: /…/src
  compiler: i686-w64-mingw32-g++ 13-win32, i686 = MSVC Debug|Win32 config (_WIN64 code not checked), mode: syntax
  fixups: F1 case-folded includes: 7 | F2 sizeof(TYPE): 14 in 4 files | F3 Diff.hpp goto block: applied | F4 shim | F5 -fpermissive filter | F6 version stub
  PASS  WinIMergeLib/Win78Libraries.cpp      (whole file is #ifdef _WIN64: empty on i686)
  FAIL  WinIMergeLib/WinIMergeLib.cpp        2 error(s) (8 tolerated &rvalue, 13 warnings)
      /…/src/WinIMergeLib/WinIMergeLib.cpp: In function 'IImgMergeWindow* WinIMerge_CreateWindow(HINSTANCE, HWND, int)':
      /…/src/WinIMergeLib/WinIMergeLib.cpp:28:64: error: invalid new-expression of abstract class type 'CImgMergeWindow'
      /…/src/WinIMergeLib/ImgMergeWindow.hpp:49:7: note:   because the following virtual functions are pure within 'CImgMergeWindow':
      In file included from /…/src/WinIMergeLib/ImgMergeWindow.hpp:28:
      /…/src/WinIMergeLib/WinIMergeLib.h:197:62: note:     'virtual void IImgMergeWindow::NewPureVirtual(int)'
      /…/src/WinIMergeLib/WinIMergeLib.cpp: In function 'IImgMergeWindow* WinIMerge_CreateWindowless()':
      /…/src/WinIMergeLib/WinIMergeLib.cpp:36:64: error: invalid new-expression of abstract class type 'CImgMergeWindow'
  PASS  WinIMerge/WinIMerge.cpp
  PASS  cidiff/cidiff.cpp
  PASS  WinIMergeLib/WinIMergeLib.rc         (windres)
  PASS  WinIMerge/WinIMerge.rc               (windres)
FAILED: 1 of 6 checks failed (2.1s)
```

## What it covers

| Check | What is compiled |
|---|---|
| `WinIMergeLib/WinIMergeLib.cpp` | The whole DLL. All its code is in headers: ImgMergeWindow, ImgWindow, ImgToolWindow, ImgMergeBuffer, ImgDiffBuffer, ImgConverter, Diff, image, Ocr (non-`_WIN64` stub), WinIMergeLib.h, plus FreeImage/FreeImagePlus. Covers missing overrides of `IImgMergeWindow` / `IImgToolWindow` (it does `new CImgMergeWindow()` and `new CImgToolWindow()`). |
| `WinIMergeLib/Win78Libraries.cpp` | In the DLL project, but the whole file is `#ifdef _WIN64`, so it is empty on i686. |
| `WinIMerge/WinIMerge.cpp` | The app. Covers the app's use of the `IImgMergeWindow` API. |
| `cidiff/cidiff.cpp` | The console tool, `USE_WINIMERGELIB` build. Also uses the public API. |
| `WinIMerge/WinIMerge.rc`, `WinIMergeLib/WinIMergeLib.rc` | `i686-w64-mingw32-windres`: resource-script syntax, undefined ID macros (e.g. a `MENUITEM` whose `ID_…` is missing from resource.h), missing `END`, unterminated strings, missing icon files. |

* **Where the file lists and defines come from:** each project's `.vcxproj`.
  The ClCompile/ResourceCompile items, the `Debug|Win32` ClCompile
  `PreprocessorDefinitions`, and the macros MSBuild adds implicitly
  (`_UNICODE;UNICODE` for `CharacterSet=Unicode`, `_WINDLL` for DLLs). A
  `.cpp` added to a project is picked up automatically. The defines in use
  today are `WIN32 _DEBUG _WINDOWS _UNICODE UNICODE FREEIMAGE_LIB _WINDLL`
  (lib), `WIN32 _DEBUG _WINDOWS _UNICODE UNICODE` (app), and
  `WIN32 USE_WINIMERGELIB _DEBUG _CONSOLE FREEIMAGE_LIB _CRT_SECURE_NO_WARNINGS _UNICODE UNICODE`
  (cidiff). Debug is used rather than Release so that `assert()` expressions
  get compiled; no code depends on `NDEBUG`.
* **Target:** i686, the same configuration as MSVC "Win32". `_WIN64` is not
  defined. MinGW-w64 v11 defaults `_WIN32_WINNT` to 0x0A00, as the Windows 10
  SDK does.
* **Header coverage:** every project header is reached by some checked TU,
  except `Win78Libraries.h` (`_WIN64` only) and `WinIMerge/WinIMerge.h`,
  which nothing includes.

**Stricter than plain GCC, to match MSVC errors.** GCC on its own only warns
about (or accepts as GNU extensions) these, while MSVC rejects them:

| Flag | MSVC equivalent |
|---|---|
| `-Werror=return-type` | C4716 "must return a value" (an error by default) |
| `-Werror=vla` | C2131: MSVC has no variable-length arrays |
| `-Werror=pointer-arith` | C2036: arithmetic on `void*` |
| `-Werror=narrowing` | C2397: narrowing inside `{}` |
| `-Wpedantic -Werror=c++20-extensions -Werror=c++23-extensions` | e.g. C7555: designated initialisers under `/std:c++17` |

`-Wpedantic` only adds warnings, which are shown with `-v`.

**Verified by injecting errors** into scratch copies. Every case gave the
expected exit status with GCC, and again with `--clang`:

| Injected change | Result |
|---|---|
| (a) `m_buffer.NoSuchMethod(pane);` in `CImgMergeWindow` (ImgMergeWindow.hpp) | exit 1: `'class CImgMergeBuffer' has no member named 'NoSuchMethod'` |
| (b) new `virtual void NewPureVirtual(int) = 0;` in `IImgMergeWindow` (WinIMergeLib.h) | exit 1: `invalid new-expression of abstract class type 'CImgMergeWindow'` at both `new CImgMergeWindow()`, with a note naming the method |
| app calls `GetFilename` instead of `GetFileName` | exit 1, with GCC's "did you mean 'GetFileName'?" hint |
| `m_buffer.SetReadOnly(L"pane", …)` (type error) | exit 1 (GCC downgrades it under `-fpermissive`; the filter counts it as an error) |
| `wchar_t* p = (const wchar_t*)…` | exit 1 (same) |
| calling a non-const method on a `const CImgMergeBuffer` | exit 1 (same) |
| `return` removed from a non-void method | exit 1 (`-Werror=return-type`) |
| `override` method whose signature no longer matches | exit 1 (`marked 'override', but does not override`, plus the abstract-class error) |
| `POINT p{ .x = 0, .y = 0 }` | exit 1 (`-Werror=c++20-extensions`) |
| `sizeof NoSuchType` (passes through fixup F2) | exit 1 (`'NoSuchType' was not declared`) |
| undefined `ID_…` in a WinIMerge.rc `MENUITEM` | exit 1 (windres `syntax error`) |
| typo inside `#ifdef _WIN64` code (Win78Libraries.cpp) | **exit 0: not detected** (blind spot, see below) |

## What it cannot catch

1. **`_WIN64`-only code**: about 960 of the ~10,700 lines in WinIMergeLib (~9%):
   * ImgConverter.hpp: `PdfRenderer`, `SvgRenderer`, `WICRenderer` (lines
     ~32–453), plus the `_WIN64` branches of `getImageType()` / `load()`.
   * Ocr.hpp: `COcr`, the WinRT OCR engine (lines ~37–363). On i686 only the
     `#else` stub is compiled.
   * `Win78Libraries.h` and `Win78Libraries.cpp` entirely, and the `_WIN64`
     parts of `DllMain`.

   x86_64 MinGW defines `_WIN64`, and then the build stops on headers MinGW-w64
   v11 does not have: `d2d1_3.h`, `windows.data.pdf.h`,
   `windows.data.pdf.interop.h`, `windows.graphics.imaging.h`,
   `windows.media.ocr.h`. Its WRL is also only `ComPtr`; the code needs
   `Wrappers::Event`, `HStringReference`, `HString`, `HandleT`, `FileHandle`
   and `Callback`. Stubbing those would mean inventing SDK signatures, which
   would hide exactly the errors you want to find, so it is not done.
   64-bit-only problems (for example `size_t` → `UINT` narrowing) are not
   visible on i686 either. For this code, rely on the Windows CI: GitHub
   Actions `windows-latest` and AppVeyor run `BuildBin.cmd`, an MSVC Release
   build for x86, x64 and ARM64. Another option is clang-cl with a real
   Windows SDK, e.g. fetched with `xwin`; that needs accepting Microsoft's SDK
   license, so it was not set up.
2. **Linking**: a method that is declared but never defined, names in
   `WinIMergeLib.def`, mismatches with the FreeImage library, missing
   libraries.
3. **Differences between MSVC and GCC/MinGW** (the check approximates MSVC; it
   is not MSVC):
   * *Possible false errors* (MSVC accepts the code, this check rejects it):
     * binding a non-const reference to a temporary (MSVC C4239 extension);
     * missing `typename`/`template`, or unqualified use of members of a
       dependent base class (MSVC's permissive mode has no two-phase lookup);
     * `goto` past an initialisation anywhere other than the one Diff.hpp
       site;
     * a header that MSVC's STL includes transitively but libstdc++ does not
       (fix it by adding the `#include`, which is correct for MSVC too);
     * MSVC-only keywords (`__super`, `__declspec(property)`, `__try/__except`);
     * explicit specialisation at class scope;
     * `sizeof TYPE` written in a form F2 does not rewrite (e.g. `sizeof RECT * 2`);
     * a missing return on only some paths (MSVC C4715 is just a warning;
       `-Werror=return-type` rejects it);
     * a newer Win32 API that mingw-w64 v11 lacks.
   * *Possible missed errors* (MSVC rejects the code, this check passes it):
     * GNU extensions that only produce `[-Wpedantic]` warnings (statement
       expressions, `a ?: b`, case ranges, zero-length arrays);
     * code that relies on libstdc++ pulling in a header that MSVC's STL does
       not;
     * MSVC compiler limits (e.g. C2026 string literal too long);
     * API names that mingw-w64 declares but the Windows SDK does not;
     * differences in overload resolution or lookup;
     * any `[-fpermissive]` downgrade GCC might print without that tag. None
       was found in testing; the GCC 13 diagnostics that carry other tags are
       `-Wnarrowing`, which is made an error, and `-Wchanges-meaning`, which
       MSVC does not diagnose either.
   * MSVC warnings (`/W3`) are not reproduced, and of course runtime
     behaviour is not tested.
4. **Code in other inactive branches**: `#ifndef _WIN32` parts of image.hpp,
   cidiff's non-`USE_WINIMERGELIB` path, the `_M_X64`/`_M_IA64` manifest
   pragmas in WinIMerge.cpp, and ARM/ARM64 configurations.
5. **Templates that are never instantiated** are only checked for errors that
   do not depend on the template parameters. MSVC checks even less there.

## Fixups applied (temporary copy only, every one keeps line numbers)

| # | Fixup | Why | Sites in the tree today |
|---|---|---|---|
| F1 | Case-insensitive `#include` lookup: an include not found with its exact spelling but found ignoring case gets a symlink with the requested spelling. System headers go into a dir passed with `-isystem`, project headers next to the including file. | Windows file systems ignore case; MinGW headers are lowercase. | `<Windows.h>`, `<CommCtrl.h>`, `<WindowsX.h>`, `<Shlwapi.h>`, and 3 WinRT headers used only under `_WIN64`. A name that exists in no spelling is still an error. |
| F2 | `sizeof IDENT` → `sizeof(IDENT)` when the operand is one (possibly `::`-qualified) identifier directly followed by `, ; ) } ]`. | MSVC accepts `sizeof TYPE` without parentheses. For a variable the parentheses change nothing. | 14 sites: `sizeof SCROLLINFO` ×11 (ImgWindow.hpp ×8, ImgMergeWindow.hpp ×3), `sizeof POINT` ×1 (ImgMergeWindow.hpp), and 2 variables (`sizeof buf`, `sizeof buffer`). |
| F3 | Diff.hpp `xdl_prepare_ctx()`: the code from `const Data& data = …;` down to the `abort:` label is wrapped in `{ }`. The brace and label stay on their original lines. | Earlier `goto abort` statements jump past that reference initialisation. MSVC allows it; GCC rejects it even with `-fpermissive`. | 1 site (lines 1762/1811 at `da639cd` through `139a6c0`). If the pattern ever stops matching, a NOTICE is printed. |
| F4 | `-include mingw-shim.h`, which only does `#include <cmath>`. | MSVC's STL reaches `<cmath>` transitively; WinIMerge.cpp calls `pow()` without including it. | 1 call site. |
| F5 | `-fpermissive`, plus an output filter: every `[-fpermissive]` diagnostic counts as an error except `taking address of rvalue`. | `&` applied to a class rvalue, e.g. `PtInRect(&GetRightBoxRect(pane), pt)` or `memcmp(&w.GetRectangleSelectionStart(), …)`, is an MSVC extension (C4238 warning). `&` of a scalar rvalue stays a hard error, as in MSVC (C2102). | 8 sites in ImgMergeWindow.hpp (`ChildWnd_OnLButtonDown/Up`, `ChildWnd_OnMouseMove`). |
| F6 | Stub `src/gen-versioninfo.h`, written only if the copy has none. | `GIT-VS-VERSION-GEN.bat` writes it before the MSVC build; the .rc files include it via Version.h. | rc files only. |
| F7 | FreeImage headers from `freeimage-include/` or `FREEIMAGE_DIR`. | The .vcxproj expects a built FreeImage `Dist` directory. | – |

**Not needed**, because MinGW-w64 already provides them:

* `_wdupenv_s`, `_snwprintf_s`, `swprintf_s`, `wcscpy_s`, `_wfopen_s`,
  `_TRUNCATE`, `_countof`, `_wcsicmp`;
* `#pragma comment(lib/linker, …)` and `#pragma warning(…)`, which GCC
  ignores silently (no `-Wunknown-pragmas`).

The win32 and posix thread-model variants of MinGW g++ both support
`std::thread`/`std::mutex`, so either one works.

## Why GCC and i686, and what clang does

* **i686 vs x86_64:** see blind spot 1. i686 compiles cleanly with the six
  small fixups above.
* **clang with `-fms-extensions -fms-compatibility`** (tried as asked) does
  **not** accept the code as-is:
  * `sizeof TYPE` is still an error;
  * taking the address of a temporary is an error by default
    (`-Waddress-of-temporary`);
  * `-fms-compatibility` stops defining `__GNUC__`, which breaks the MinGW
    headers (`#error VARARGS not implemented for this compiler`) and
    libstdc++;
  * it also needs `-fms-compatibility-version=19.x`, otherwise
    `char16_t`/`char32_t` are not keywords.

  `-fms-compatibility` does turn the Diff.hpp `goto` into a warning, but that
  is not worth the `__GNUC__` problems. `--clang` therefore runs
  `clang++ --target=i686-w64-mingw32 -fms-extensions -Wno-error=address-of-temporary`
  plus the same MSVC-parity errors, on the same fixed-up copy. It is a second
  opinion with different diagnostics, and it is off by default.
* **`-fsyntax-only` vs `-c`:** GCC's `-fsyntax-only` still instantiates
  templates, including virtual members reached only through a vtable (tested).
  `--obj` adds code generation, about 1–2 s, and very rarely finds anything
  more.

## Maintenance notes

* A `NOTICE` from F3, or from reading a `.vcxproj`, means the upstream code
  changed shape. Check the fixup or fallback list in the script header.
* If a new MSVC-ism appears, prefer a line-preserving rewrite of just that
  construct, or one more exact message in F5's tolerated list. Do not use
  blanket flags like `-w` or `-fpermissive` without the filter. Then document
  it in the table above.
* To show the check still catches errors (for example after a toolchain
  upgrade), run the two required injection tests again:

  ```sh
  d=$(mktemp -d); cp -a /home/user/winimerge/src "$d/"
  # (a) a call to a method m_buffer does not have
  sed -i 's/return m_buffer.GetFileName(pane);/m_buffer.NoSuchMethod(pane); &/' "$d/src/WinIMergeLib/ImgMergeWindow.hpp"
  /home/user/research/tools/mingw-syntax-check.sh "$d"; echo "exit $? (expect 1)"
  cp /home/user/winimerge/src/WinIMergeLib/ImgMergeWindow.hpp "$d/src/WinIMergeLib/"
  # (b) a pure virtual method CImgMergeWindow does not implement
  sed -i 's/virtual void ResetSplitterRatios() = 0;/& virtual void NewPureVirtual(int) = 0;/' "$d/src/WinIMergeLib/WinIMergeLib.h"
  /home/user/research/tools/mingw-syntax-check.sh "$d"; echo "exit $? (expect 1)"
  rm -rf "$d"
  ```
