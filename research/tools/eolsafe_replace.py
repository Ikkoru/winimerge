#!/usr/bin/env python3
"""Exact-match text replacement that preserves a file's line endings (CRLF or LF).

Usage (as a module):
    from eolsafe_replace import replace_once
    replace_once(path, old, new)   # old/new written with '\n'; converted to the file's EOL
"""
import sys

def replace_once(path, old, new, count=1):
    data = open(path, 'rb').read()
    crlf = b'\r\n' in data
    def conv(t):
        b = t.encode('utf-8')
        return b.replace(b'\n', b'\r\n') if crlf else b
    o, n = conv(old), conv(new)
    found = data.count(o)
    if found != count:
        raise SystemExit(f"{path}: expected {count} match(es), found {found} for:\n{old[:200]}")
    open(path, 'wb').write(data.replace(o, n))

if __name__ == '__main__':
    print(__doc__)
