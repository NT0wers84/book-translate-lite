#!/usr/bin/env python3
"""Crea un EPUB di prova (testo originale scritto per i test, nessun diritto di terzi).

Uso: crea_libro_prova.py CARTELLA  →  CARTELLA/The Clockwork Lighthouse.epub
"""
import os, struct, subprocess, sys, zlib

QUI = os.path.dirname(os.path.abspath(__file__))


def png(w, h):
    raw = b''.join(b'\x00' + b'\x80\x40\x20' * w for _ in range(h))
    ch = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    return (b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
            + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b''))


def crea(cartella):
    os.makedirs(cartella, exist_ok=True)
    with open(os.path.join(cartella, 'mappa.png'), 'wb') as f:
        f.write(png(40, 20))
    out = os.path.join(cartella, 'The Clockwork Lighthouse.epub')
    subprocess.run(['pandoc', os.path.join(QUI, 'libro_prova.md'), '-o', out, '--split-level=1',
                    '--resource-path', cartella], check=True, cwd=cartella)
    os.remove(os.path.join(cartella, 'mappa.png'))
    return out


if __name__ == '__main__':
    print(crea(sys.argv[1] if len(sys.argv) > 1 else '.'))
