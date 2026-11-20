#!/usr/bin/env python3
"""Build a test EPUB (original text written for the tests, no third-party rights).

Usage: make_test_book.py FOLDER  →  FOLDER/The Clockwork Lighthouse.epub
"""
import os, struct, subprocess, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))


def png(w, h):
    raw = b''.join(b'\x00' + b'\x80\x40\x20' * w for _ in range(h))
    ch = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    return (b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b''))


def make(folder):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, 'map.png'), 'wb') as f:
        f.write(png(40, 20))
    out = os.path.join(folder, 'The Clockwork Lighthouse.epub')
    subprocess.run(['pandoc', os.path.join(HERE, 'test_book.md'), '-o', out, '--split-level=1',
                    '--resource-path', folder], check=True, cwd=folder)
    os.remove(os.path.join(folder, 'map.png'))
    return out


if __name__ == '__main__':
    print(make(sys.argv[1] if len(sys.argv) > 1 else '.'))
