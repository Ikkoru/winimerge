// mingw-shim.h: force-included (g++ -include) into every C++ translation unit
// compiled by mingw-syntax-check.sh. It is never used by the real MSVC build.
//
// Keep this file MINIMAL. Anything declared here can hide a genuine error that
// MSVC would report. Only add things that MSVC provides implicitly and MinGW
// does not, and say why next to each one.
//
// Things this file deliberately does NOT need to provide, because MinGW-w64
// (v11 headers) already declares them: the MSVC "secure CRT" functions used
// by WinIMerge (_wdupenv_s, _snwprintf_s, swprintf_s, wcscpy_s, _wfopen_s,
// _TRUNCATE, _countof) and _wcsicmp. GCC ignores the MSVC-only pragmas
// (#pragma comment(lib/linker, ...) and #pragma warning(...)) without
// warning, because -Wunknown-pragmas is not enabled.

#pragma once

#ifdef __cplusplus

// 1. <cmath>
//    MSVC's STL pulls in <cmath> transitively from <string>, <iostream> and
//    similar headers, so WinIMerge.cpp calls pow() without including <cmath>
//    or <math.h>. libstdc++ does not include <cmath> that way, so without this
//    GCC reports "'pow' was not declared in this scope".
//    Caveat: this include runs before the TU's own code. If a source file
//    ever does "#define _USE_MATH_DEFINES" and then "#include <cmath>" to get
//    M_PI, M_PI will be missing here (false error). Fix that case by passing
//    -D_USE_MATH_DEFINES in the script instead. No current source does it.
#include <cmath>

#endif // __cplusplus
