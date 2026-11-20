#!/usr/bin/env python3
"""Applica le correzioni della revisione da stdin.

  python3 patch.py <<'@@FINE@@'
  @@PARTE 0012@@
  @@VECCHIO@@
  testo esatto da sostituire
  @@NUOVO@@
  testo corretto
  @@PARTE 0013@@
  @@OK@@
  @@FINE@@

Ogni correzione deve trovare il testo VECCHIO una sola volta; se rompe la verifica
viene annullata. Il primo originale di ogni parte modificata resta in revisione/backup/.
Le parti elencate (anche con @@OK@@) vengono segnate come rivedute.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import comune as C
import lavoro as L


def main():
    d = C.trova_dir(sys.argv[sys.argv.index('--dir') + 1] if '--dir' in sys.argv else None)
    ok, scartate, viste = L.applica_patch(d, sys.stdin.read(), C.progetto(d), C.glossario(d))
    if not viste:
        sys.exit('ERRORE: nessun blocco @@PARTE NNNN@@.')
    st = C.stato(d); st['rivedute'] = sorted(set(st['rivedute']) | set(viste)); C.salva_stato(d, st)
    print(f'correzioni applicate: {ok}; parti rivedute: ' + ', '.join(f'{n:04d}' for n in viste))
    for n, m in scartate:
        print(f'  scartata {n:04d}: {m}')


if __name__ == '__main__':
    main()
