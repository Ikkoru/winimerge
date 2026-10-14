#!/usr/bin/env bash
# mingw-syntax-check.sh: compile-check (no run, no link) WinIMerge's Windows-only
# C++ code and resource scripts on Linux, using the MinGW-w64 i686 cross toolchain.
#
# Usage: mingw-syntax-check.sh [options] [SOURCE_ROOT]
#
#   SOURCE_ROOT  A winimerge checkout (the directory that contains src/), or its
#                src/ directory itself. Default: /home/user/winimerge
#                The tree is only read. All fixups go into a temporary copy.
#
#   -v, --verbose  also print compiler warnings and fixup details
#   -k, --keep     keep the temporary copy and logs (the path is printed)
#   --obj          compile to object files (-c -O0) instead of -fsyntax-only
#   --clang        also run clang++ --target=i686-w64-mingw32 as a second front end
#   -h, --help     show this help
#
#   Environment:
#     FREEIMAGE_DIR  FreeImage source tree (Source/FreeImage.h plus
#                    Wrapper/FreeImagePlus/FreeImagePlus.h), or a directory
#                    that holds both headers. Default: freeimage-include/ next
#                    to this script (copied from github.com/WinMerge/freeimage).
#     CXX, WINDRES   override the i686 MinGW g++ / windres executables.
#     TMPDIR         where the temporary copy goes (default /tmp).
#
#   Exit status: 0 = every check passed, 1 = compile errors, 2 = setup problem.
#
# What is checked: it mirrors the MSVC "Debug|Win32" configuration. Files and
# -D flags are read from the WinIMergeLib, WinIMerge and cidiff .vcxproj files,
# with a built-in fallback. Today that means:
#   C++   src/WinIMergeLib/WinIMergeLib.cpp    (the DLL: every Img*.hpp header)
#         src/WinIMergeLib/Win78Libraries.cpp  (all #ifdef _WIN64, so empty on x86)
#         src/WinIMerge/WinIMerge.cpp          (the app)
#         src/cidiff/cidiff.cpp                (console tool, USE_WINIMERGELIB build)
#   RC    src/WinIMerge/WinIMerge.rc, src/WinIMergeLib/WinIMergeLib.rc (windres)
#
# The target is i686 (32-bit), so _WIN64 is NOT defined. That is deliberate:
# the _WIN64 code (WinRT PDF/SVG/WIC rendering in ImgConverter.hpp, WinRT OCR
# in Ocr.hpp, Win78Libraries.*) needs Windows SDK headers that MinGW-w64 does
# not ship (d2d1_3.h, windows.data.pdf*.h, windows.media.ocr.h,
# windows.graphics.imaging.h, and full WRL). That code is not checked. See
# MINGW-CHECK.md.
#
# FIXUPS. All of them are mechanical, apply only to the temporary copy, and keep
# line numbers unchanged, so diagnostics point at the right line of the
# original file. Each one is narrow on purpose, so that real errors (typos,
# wrong method names, type errors, a class left abstract) are still reported.
#   F1  Case-insensitive #include names. Windows file systems ignore case, so
#       <Windows.h>, <CommCtrl.h>, <WindowsX.h>, <Shlwapi.h> work there, but
#       MinGW's headers are lowercase. For every include that is not found
#       with its exact spelling but is found ignoring case, a symlink with the
#       requested spelling is made (system headers: a dir passed with -isystem;
#       project headers: next to the including file). Misspelled names are
#       still errors.
#   F2  "sizeof IDENT" -> "sizeof(IDENT)" when the operand is a single
#       (possibly ::-qualified) identifier directly followed by , ; ) } or ].
#       MSVC accepts "sizeof TYPE" without parentheses (e.g. sizeof SCROLLINFO,
#       sizeof POINT); GCC and clang do not. For a variable the parentheses
#       change nothing.
#   F3  Diff.hpp, xdl_prepare_ctx(): the code from the
#       "const Data& data = ...;" declaration up to the "abort:" label is
#       wrapped in { }. Earlier "goto abort" statements jump past that
#       reference initialisation. MSVC allows it; GCC rejects it even with
#       -fpermissive. The brace and label stay on their original lines. If the
#       pattern is not found, a notice is printed and nothing is changed.
#   F4  Force-included shim header (mingw-shim.h, next to this script). It
#       only does #include <cmath>, because MSVC's STL reaches <cmath>
#       transitively (WinIMerge.cpp calls pow() without including it).
#   F5  -fpermissive plus a filter on the output. GCC rejects "&" applied to a
#       class rvalue, e.g. PtInRect(&GetRect(), pt) or
#       memcmp(&a.GetPoint(), ...); MSVC only warns (C4238). -fpermissive
#       turns many kinds of error into warnings tagged [-fpermissive]. This
#       script counts every such warning as an ERROR, except the one message
#       "taking address of rvalue". (&scalar_rvalue stays a hard GCC error,
#       as it is in MSVC: C2102.)
#   F6  Stub src/gen-versioninfo.h (normally written by
#       GIT-VS-VERSION-GEN.bat before the build) if the copy has none. Only
#       the .rc files include it (via Version.h).
#   F7  FreeImage/FreeImagePlus headers come from FREEIMAGE_DIR or the
#       vendored copy. The .vcxproj expects a built FreeImage Dist directory.
#
# Extra strictness so that GCC rejects what MSVC rejects (GCC alone only warns,
# or accepts the GNU extension):
#   -Werror=return-type        MSVC C4716 "must return a value" is an error
#   -Werror=vla                MSVC has no variable-length arrays (C2131)
#   -Werror=pointer-arith      arithmetic on void* (C2036)
#   -Werror=narrowing          narrowing in {} initialisation (C2397)
#   -Wpedantic -Werror=c++20-extensions -Werror=c++23-extensions
#                              e.g. designated initialisers under /std:c++17
#                              (C7555). -Wpedantic only adds warnings.

set -u -o pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
SHIM="$SCRIPT_DIR/mingw-shim.h"

VERBOSE=0 KEEP=0 MODE=syntax USE_CLANG=0 SRC_ARG=
usage() { sed -n '2,/^# What is checked/{/^# What is checked/d;s/^# \{0,1\}//;p}' "${BASH_SOURCE[0]}"; }
while [ $# -gt 0 ]; do
	case $1 in
	-v|--verbose) VERBOSE=1 ;;
	-k|--keep) KEEP=1 ;;
	--obj) MODE=obj ;;
	--clang) USE_CLANG=1 ;;
	-h|--help) usage; exit 0 ;;
	-*) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
	*) [ -z "$SRC_ARG" ] || { echo "only one SOURCE_ROOT allowed" >&2; exit 2; }; SRC_ARG=$1 ;;
	esac
	shift
done
SRC_ARG=${SRC_ARG:-/home/user/winimerge}

die() { echo "mingw-syntax-check: $*" >&2; exit 2; }
vnote() { [ "$VERBOSE" = 1 ] && echo "    $*"; return 0; }
now_ms() { date +%s%3N; }
T0=$(now_ms)

# ---- toolchain ---------------------------------------------------------------
if [ -z "${CXX:-}" ]; then
	for c in i686-w64-mingw32-g++ i686-w64-mingw32-g++-win32 i686-w64-mingw32-g++-posix; do
		if command -v "$c" >/dev/null 2>&1; then CXX=$c; break; fi
	done
fi
[ -n "${CXX:-}" ] && command -v "$CXX" >/dev/null 2>&1 ||
	die "i686 MinGW g++ not found. Install: apt-get install -y g++-mingw-w64-i686 binutils-mingw-w64-i686"
WINDRES=${WINDRES:-i686-w64-mingw32-windres}
command -v "$WINDRES" >/dev/null 2>&1 || die "$WINDRES not found. Install: apt-get install -y binutils-mingw-w64-i686"
CLANGXX=
if [ "$USE_CLANG" = 1 ]; then
	CLANGXX=$(command -v clang++ 2>/dev/null) || die "--clang given but clang++ is not installed"
fi
[ -f "$SHIM" ] || die "shim header missing: $SHIM"

# ---- sources -----------------------------------------------------------------
if [ -d "$SRC_ARG/src/WinIMergeLib" ]; then SRC_DIR=$SRC_ARG/src
elif [ -d "$SRC_ARG/WinIMergeLib" ]; then SRC_DIR=$SRC_ARG
else die "no WinIMergeLib under '$SRC_ARG' (expected a winimerge checkout or its src/ dir)"
fi
SRC_DIR=$(cd "$SRC_DIR" && pwd -P)

FI_INC=()
fi_try() {
	if [ -f "$1/Source/FreeImage.h" ] && [ -f "$1/Wrapper/FreeImagePlus/FreeImagePlus.h" ]; then
		FI_INC=("-I$1/Source" "-I$1/Wrapper/FreeImagePlus")
	elif [ -f "$1/FreeImage.h" ] && [ -f "$1/FreeImagePlus.h" ]; then
		FI_INC=("-I$1")
	else
		return 1
	fi
}
if [ -n "${FREEIMAGE_DIR:-}" ]; then
	fi_try "$FREEIMAGE_DIR" || die "FREEIMAGE_DIR=$FREEIMAGE_DIR has no FreeImage.h + FreeImagePlus.h"
else
	fi_try "$SCRIPT_DIR/freeimage-include" || die "FreeImage headers not found; set FREEIMAGE_DIR"
fi

# ---- temporary copy ----------------------------------------------------------
WORK=$(mktemp -d "${TMPDIR:-/tmp}/mingw-check.XXXXXX") || die "mktemp failed"
WORK=$(cd "$WORK" && pwd -P)
cleanup() { if [ "$KEEP" = 1 ]; then echo "kept temporary copy: $WORK"; else rm -rf "$WORK"; fi; }
trap cleanup EXIT
cp -a "$SRC_DIR" "$WORK/src" || die "copying $SRC_DIR failed"
mkdir -p "$WORK/case" "$WORK/logs" "$WORK/obj"
W=$WORK/src

CXX_VER=$("$CXX" -dumpversion 2>/dev/null)
echo "mingw-syntax-check: $SRC_DIR"
echo "  compiler: $CXX $CXX_VER, i686 = MSVC Debug|Win32 config (_WIN64 code not checked), mode: $MODE"

# ---- F6: version header stub for the .rc files --------------------------------
if [ ! -f "$W/gen-versioninfo.h" ]; then
	cat >"$W/gen-versioninfo.h" <<'EOF'
// Stub written by mingw-syntax-check.sh (normally GIT-VS-VERSION-GEN.bat output)
#define GEN_VER_VERSION_STRING   "0.0.0.0\0"
#define GEN_VER_DIGITAL_VERSION  0,0,0,0
#define GEN_VER_VERSION_HEX      0x0000000000000000
#define GEN_VER_COMMENT_STRING   "\0"
#define GEN_VER_PRIVATE_FLAG     0
#define GEN_VER_PRIVATE_STRING   "\0"
#define GEN_VER_PATCHED_FLAG     0
#define GEN_VER_PRERELEASE_FLAG  0
EOF
fi

# ---- F1: case-insensitive include resolution -----------------------------------
mapfile -t SYS_DIRS < <("$CXX" -xc++ -E -v - </dev/null 2>&1 |
	sed -n '/^#include <\.\.\.> search starts here:/,/^End of search list\./{s/^ \+//p}')
INC_DIRS=()
for f in "${FI_INC[@]}"; do INC_DIRS+=("${f#-I}"); done
INC_DIRS+=("${SYS_DIRS[@]}")

# ci_resolve BASE REL: print the path of REL below BASE, matching every path
# component case-insensitively; fail if there is no such file.
ci_resolve() {
	local cur=$1 part hit
	local -a parts
	IFS=/ read -r -a parts <<<"$2"
	for part in "${parts[@]}"; do
		case $part in '' | .) continue ;; ..) cur=$cur/..; continue ;; esac
		if [ -e "$cur/$part" ]; then cur=$cur/$part; continue; fi
		[ -d "$cur" ] || return 1
		hit=$(find "$cur/" -mindepth 1 -maxdepth 1 -iname "$part" -print -quit 2>/dev/null)
		[ -n "$hit" ] || return 1
		cur=$hit
	done
	[ -f "$cur" ] && printf '%s\n' "$cur"
}

n_links=0 unresolved=()
while IFS=$'\t' read -r file delim name; do
	dir=$(dirname "$file")
	if [ "$delim" = '"' ]; then
		[ -e "$dir/$name" ] && continue
	fi
	found=0
	for d in "${INC_DIRS[@]}"; do [ -e "$d/$name" ] && { found=1; break; }; done
	[ "$found" = 1 ] && continue
	[ -e "$WORK/case/$name" ] && continue
	real=
	if [ "$delim" = '"' ] && real=$(ci_resolve "$dir" "$name"); then
		link=$(realpath -m "$dir/$name")
		case $link in "$W"/*) ;; *) real= ;; esac   # never write outside the copy
		if [ -n "$real" ]; then
			mkdir -p "$(dirname "$link")" && ln -s "$(realpath "$real")" "$link" && n_links=$((n_links + 1))
			vnote "F1: \"$name\" -> $(realpath "$real")  (next to $(basename "$file"))"
			continue
		fi
	fi
	for d in "${INC_DIRS[@]}"; do
		if real=$(ci_resolve "$d" "$name"); then
			mkdir -p "$(dirname "$WORK/case/$name")" && ln -s "$(realpath "$real")" "$WORK/case/$name" &&
				n_links=$((n_links + 1))
			vnote "F1: <$name> -> $(realpath "$real")"
			continue 2
		fi
	done
	if [ "$delim" = '<' ]; then u="<$name>"; else u="\"$name\""; fi
	unresolved+=("$u (in ${file#"$W"/})")
done < <(grep -rHoE '^[[:space:]]*#[[:space:]]*include[[:space:]]*[<"][^>"]+[>"]' \
	--include='*.cpp' --include='*.h' --include='*.hpp' --include='*.rc' "$W" |
	sed -E 's/^([^:]+):[[:space:]]*#[[:space:]]*include[[:space:]]*(.)(.*).$/\1\t\2\t\3/' | sort -u)
for u in ${unresolved[@]+"${unresolved[@]}"}; do
	vnote "F1: no such header, any case: $u (fine if it is in an inactive #if branch, e.g. _WIN64)"
done

# ---- F2: sizeof IDENT -> sizeof(IDENT) -----------------------------------------
SIZEOF_RE='\bsizeof[[:space:]]+([A-Za-z_][A-Za-z0-9_]*(::[A-Za-z_][A-Za-z0-9_]*)*)([[:space:]]*[],;)}])'
n_sizeof=0 sizeof_files=0
while IFS= read -r -d '' f; do
	c=$(grep -oE "$SIZEOF_RE" "$f" | wc -l)
	[ "$c" -gt 0 ] || continue
	sed -i -E "s/$SIZEOF_RE/sizeof(\\1)\\3/g" "$f"
	n_sizeof=$((n_sizeof + c)) sizeof_files=$((sizeof_files + 1))
	vnote "F2: sizeof without parentheses: $c in ${f#"$W"/}"
done < <(find "$W" -type f \( -name '*.cpp' -o -name '*.h' -o -name '*.hpp' \) -print0)

# ---- F3: Diff.hpp goto past a reference initialisation -------------------------
DIFF_HPP=$W/WinIMergeLib/Diff.hpp
f3_state="not needed"
DECL_RE='^[[:space:]]*const Data[[:space:]]*&[[:space:]]*data[[:space:]]*=.*;[[:space:]]*$'
if [ -f "$DIFF_HPP" ] && grep -qE "$DECL_RE" "$DIFF_HPP"; then
	sed -i -E "/$DECL_RE/,/^abort:/{
		s/^([[:space:]]*)(const Data[[:space:]]*&[[:space:]]*data[[:space:]]*=)/\\1{ \\2/
		s/^abort:/} abort:/
	}" "$DIFF_HPP"
	opened=$(grep -cE '^[[:space:]]*\{ const Data' "$DIFF_HPP")
	closed=$(grep -cE '^\} abort:' "$DIFF_HPP")
	if [ "$opened" = 1 ] && [ "$closed" = 1 ]; then
		f3_state=applied
	else
		f3_state="MISMATCH ({ x$opened, } x$closed): check F3 in this script"
		echo "  NOTICE: F3 (Diff.hpp goto fixup) did not apply cleanly: $f3_state" >&2
	fi
fi

echo "  fixups: F1 case-folded includes: $n_links | F2 sizeof(TYPE): $n_sizeof in $sizeof_files files" \
	"| F3 Diff.hpp goto block: $f3_state | F4 shim | F5 -fpermissive filter | F6 version stub"

# ---- compile --------------------------------------------------------------------
GCC_FLAGS=(-std=c++17 -fdiagnostics-plain-output -fpermissive
	-Wpedantic -Werror=return-type -Werror=vla -Werror=pointer-arith -Werror=narrowing
	-Werror=c++20-extensions -Werror=c++23-extensions
	-include "$SHIM" -isystem "$WORK/case")
# clang: -fms-extensions for __declspec/#pragma comment etc. -fms-compatibility
# is not usable with the MinGW headers (it undefines __GNUC__).
CLANG_FLAGS=(--target=i686-w64-mingw32 -std=c++17 -fms-extensions
	-fno-caret-diagnostics -fno-color-diagnostics -fno-diagnostics-fixit-info
	-Wno-error=address-of-temporary -Wno-nonportable-include-path -Wno-microsoft
	-Werror=return-type -Werror=vla-cxx-extension -Werror=pointer-arith
	-Werror=c++20-extensions -Werror=c++23-extensions
	-include "$SHIM" -isystem "$WORK/case")

# Translation units, resource scripts and -D flags come from each project's
# .vcxproj (ClCompile / ResourceCompile items; "Debug|Win32" ClCompile
# PreprocessorDefinitions plus the macros MSBuild adds implicitly for
# CharacterSet and DLL projects). A .cpp added to a project is therefore
# checked automatically. If a .vcxproj is missing or unreadable, the values
# below (taken from the project files of Oct 2026) are used instead.
#   project dir | .vcxproj | fallback .cpp/.rc files | fallback defines
PROJECTS=(
	"WinIMergeLib|WinIMergeLib.vcxproj|Win78Libraries.cpp WinIMergeLib.cpp WinIMergeLib.rc|-DWIN32 -D_DEBUG -D_WINDOWS -D_UNICODE -DUNICODE -DFREEIMAGE_LIB -D_WINDLL"
	"WinIMerge|WinIMerge.vcxproj|WinIMerge.cpp WinIMerge.rc|-DWIN32 -D_DEBUG -D_WINDOWS -D_UNICODE -DUNICODE"
	"cidiff|cidiff.vcxproj|cidiff.cpp|-DWIN32 -DUSE_WINIMERGELIB -D_DEBUG -D_CONSOLE -DFREEIMAGE_LIB -D_CRT_SECURE_NO_WARNINGS -D_UNICODE -DUNICODE"
)
# vcx_defines VCXPROJ: the -D flags of the Debug|Win32 configuration.
vcx_defines() {
	awk '
	{ sub(/\r$/, "") }
	/<PropertyGroup / && /Debug\|Win32/ && /Label="Configuration"/ { pg = 1 }
	pg && /<\/PropertyGroup>/ { pg = 0 }
	pg && /<CharacterSet>/ { cs = $0; gsub(/.*<CharacterSet>|<\/CharacterSet>.*/, "", cs) }
	pg && /<ConfigurationType>/ { ct = $0; gsub(/.*<ConfigurationType>|<\/ConfigurationType>.*/, "", ct) }
	/<ItemDefinitionGroup / && /Debug\|Win32/ { ig = 1 }
	ig && /<\/ItemDefinitionGroup>/ { ig = 0 }
	ig && /<ClCompile>/ { cl = 1 }
	ig && /<\/ClCompile>/ { cl = 0 }
	ig && cl && /<PreprocessorDefinitions>/ && !got { d = $0; gsub(/.*<PreprocessorDefinitions>|<\/PreprocessorDefinitions>.*/, "", d); got = 1 }
	END {
		if (!got) exit 1
		if (cs == "Unicode") d = d ";_UNICODE;UNICODE"; else if (cs == "MultiByte") d = d ";_MBCS"
		if (ct == "DynamicLibrary") d = d ";_WINDLL"
		n = split(d, a, ";")
		for (i = 1; i <= n; i++)
			if (a[i] != "" && a[i] !~ /[$%]\(/ && !seen[a[i]]++) out = out " -D" a[i]
		print substr(out, 2)
	}' "$1"
}
# vcx_items VCXPROJ TAG: the Include="..." paths of <TAG> items, with forward slashes.
vcx_items() { sed -n "s/\r\$//; s/.*<$2 Include=\"\([^\"]*\)\".*/\1/p" "$1" | tr '\\' '/'; }

UNITS=() RC_UNITS=()
for p in "${PROJECTS[@]}"; do
	IFS='|' read -r pdir vcx fb_files fb_defs <<<"$p"
	[ -d "$W/$pdir" ] || continue
	defs= files=()
	if [ -f "$W/$pdir/$vcx" ] && defs=$(vcx_defines "$W/$pdir/$vcx") && [ -n "$defs" ]; then
		mapfile -t files < <(vcx_items "$W/$pdir/$vcx" ClCompile; vcx_items "$W/$pdir/$vcx" ResourceCompile)
	fi
	if [ ${#files[@]} -eq 0 ]; then
		echo "  NOTICE: could not read $pdir/$vcx, using built-in file list and defines" >&2
		defs=$fb_defs
		read -r -a files <<<"$fb_files"
	fi
	vnote "project $pdir: ${files[*]} | $defs"
	for f in "${files[@]}"; do
		case $f in
		*.rc) RC_UNITS+=("$pdir/$f") ;;
		*.cpp | *.cc | *.cxx) UNITS+=("$pdir/$f|$defs") ;;
		esac
	done
done
[ ${#UNITS[@]} -gt 0 ] || die "no C++ translation units found under $SRC_DIR"

# Static remarks shown next to a unit in the report.
unit_remark() {
	case $1 in
	WinIMergeLib/Win78Libraries.cpp) echo "(whole file is #ifdef _WIN64: empty on i686)" ;;
	esac
}

run_cxx() { # run_cxx KIND UNIT DEFS
	local kind=$1 unit=$2 defs=$3 id
	id=$kind.$(echo "$unit" | tr '/.' '__')
	local -a mode=(-fsyntax-only) flags
	[ "$MODE" = obj ] && mode=(-c -O0 -o "$WORK/obj/$id.o")
	if [ "$kind" = gcc ]; then flags=("$CXX" "${GCC_FLAGS[@]}"); else flags=("$CLANGXX" "${CLANG_FLAGS[@]}"); fi
	# shellcheck disable=SC2086  # $defs is a space-separated list of -D flags
	"${flags[@]}" "${mode[@]}" $defs "${FI_INC[@]}" "$W/$unit" >"$WORK/logs/$id.log" 2>&1
	echo $? >"$WORK/logs/$id.rc"
}

run_rc() { # run_rc UNIT
	local unit=$1 id
	id=rc.$(echo "$unit" | tr '/.' '__')
	(cd "$(dirname "$W/$unit")" &&
		"$WINDRES" -D_UNICODE -DUNICODE --include-dir="$(dirname "$W/$unit")" --include-dir="$WORK/case" \
			-i "$W/$unit" -o "$WORK/obj/$id.o") >"$WORK/logs/$id.log" 2>&1
	echo $? >"$WORK/logs/$id.rc"
}

KINDS=(gcc)
[ "$USE_CLANG" = 1 ] && KINDS+=(clang)
for kind in "${KINDS[@]}"; do
	for u in "${UNITS[@]}"; do
		[ -f "$W/${u%%|*}" ] || continue
		run_cxx "$kind" "${u%%|*}" "${u#*|}" &
	done
done
for r in ${RC_UNITS[@]+"${RC_UNITS[@]}"}; do [ -f "$W/$r" ] && run_rc "$r" & done
wait

# ---- report ---------------------------------------------------------------------
# Classify -fdiagnostics-plain-output lines. Errors are printed with their
# context ("In file included from", "required from") and their notes.
# [-fpermissive] warnings count as errors unless the message is tolerated (F5).
FILTER='
function rewrite(s,   out, i) {
	out = ""
	while ((i = index(s, from)) > 0) { out = out substr(s, 1, i - 1) to; s = substr(s, i + length(from)) }
	return out s
}
function emit(s) { print "      " rewrite(s) }
function flush(   i) { for (i = 1; i <= nctx; i++) emit(ctx[i]); nctx = 0 }
function shown(s) { flush(); emit(s); notes = 1 }
function hidden() { nctx = 0; notes = 0 }
BEGIN { nerr = nprom = ntol = nwarn = nctx = notes = 0 }
/^cc1plus: [^:]*$|^compilation terminated\.|^[0-9]+ (warning|error)s? (and [0-9]+ (warning|error)s? )?generated\./ { next }
/: (fatal )?error: / { nerr++; shown($0); next }
/: warning: .*\[-fpermissive\]$/ {
	msg = $0; sub(/^.*: warning: /, "", msg); sub(/ \[-fpermissive\]$/, "", msg)
	if (msg == "taking address of rvalue") { ntol++; if (verbose) shown($0 "  <- tolerated (MSVC C4238)"); else hidden(); next }
	nprom++; line = $0; sub(/: warning: /, ": error: ", line)
	shown(line "  <- -fpermissive downgrade, counted as error"); next
}
/: warning: .*\[-Waddress-of-temporary\]$/ { ntol++; if (verbose) shown($0 "  <- tolerated (MSVC C4238)"); else hidden(); next }
/: warning: / { nwarn++; if (verbose) shown($0); else hidden(); next }
/: note: / { if (notes) { flush(); emit($0) } else nctx = 0; next }
{ ctx[++nctx] = $0 }
END { printf "%d %d %d %d\n", nerr, nprom, ntol, nwarn > countfile }
'

n_fail=0 n_checks=0
report() { # report ID LABEL KIND
	local id=$1 label=$2 kind=$3 rc nerr nprom ntol nwarn extra=() out
	rc=$(cat "$WORK/logs/$id.rc" 2>/dev/null || echo 99)
	n_checks=$((n_checks + 1))
	if [ "$kind" = rc ]; then
		if [ "$rc" = 0 ]; then
			printf '  PASS  %-36s (windres)\n' "$label"
		else
			n_fail=$((n_fail + 1))
			printf '  FAIL  %-36s (windres, exit %s)\n' "$label" "$rc"
			awk -v from="$W/" -v to="$SRC_DIR/" '
				function rewrite(s,   out, i) { out = ""; while ((i = index(s, from)) > 0) { out = out substr(s, 1, i - 1) to; s = substr(s, i + length(from)) }; return out s }
				{ print "      " rewrite($0) }' "$WORK/logs/$id.log"
		fi
		return
	fi
	out=$(awk -v from="$W/" -v to="$SRC_DIR/" -v verbose="$VERBOSE" -v countfile="$WORK/logs/$id.counts" \
		"$FILTER" "$WORK/logs/$id.log")
	read -r nerr nprom ntol nwarn <"$WORK/logs/$id.counts"
	[ "$ntol" -gt 0 ] && extra+=("$ntol tolerated &rvalue")
	[ "$nwarn" -gt 0 ] && extra+=("$nwarn warnings")
	[ "$kind" = clang ] && extra+=("clang")
	local suffix=
	[ ${#extra[@]} -gt 0 ] && suffix="($(IFS=,; echo "${extra[*]}" | sed 's/,/, /g'))"
	local remark
	remark=$(unit_remark "$label")
	[ -n "$remark" ] && suffix="${suffix:+$suffix }$remark"
	if [ "$rc" = 0 ] && [ "$nerr" = 0 ] && [ "$nprom" = 0 ]; then
		printf '  PASS  %-36s %s\n' "$label" "$suffix"
		[ -n "$out" ] && printf '%s\n' "$out"
	else
		n_fail=$((n_fail + 1))
		printf '  FAIL  %-36s %d error(s) %s\n' "$label" $((nerr + nprom)) "$suffix"
		if [ -n "$out" ]; then
			printf '%s\n' "$out"
		else # no parsable diagnostic (driver failure?): show the raw log
			sed 's/^/      /' "$WORK/logs/$id.log"
		fi
	fi
}

for kind in "${KINDS[@]}"; do
	for u in "${UNITS[@]}"; do
		unit=${u%%|*}
		[ -f "$W/$unit" ] || { printf '  SKIP  %-36s (not in this tree)\n' "$unit"; continue; }
		report "$kind.$(echo "$unit" | tr '/.' '__')" "$unit" "$kind"
	done
done
for r in ${RC_UNITS[@]+"${RC_UNITS[@]}"}; do
	[ -f "$W/$r" ] || { printf '  SKIP  %-36s (not in this tree)\n' "$r"; continue; }
	report "rc.$(echo "$r" | tr '/.' '__')" "$r" rc
done

ELAPSED=$(awk -v a="$T0" -v b="$(now_ms)" 'BEGIN { printf "%.1f", (b - a) / 1000 }')
if [ "$n_fail" -gt 0 ]; then
	echo "FAILED: $n_fail of $n_checks checks failed (${ELAPSED}s)"
	exit 1
fi
echo "OK: all $n_checks checks passed (${ELAPSED}s)"
exit 0
