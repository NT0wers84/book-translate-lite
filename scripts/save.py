#!/usr/bin/env python3
"""Salva più parti tradotte da stdin, applica le correzioni meccaniche e verifica.

  python3 save.py <<'@@FINE@@'
  @@PARTE 0012@@
  …testo tradotto…
  @@META@@
  {"new_entities": [], "conflicts": []}
  @@PARTE 0013@@
  …
  @@FINE@@

Il META è facoltativo. Se un blocco non è valido non viene salvato niente.
Exit 1 se una parte è DA CORREGGERE (allora: modifica mirata a output_chunkNNNN.md).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import comune as C
import lavoro as L


def main():
    d = C.trova_dir(sys.argv[sys.argv.index('--dir') + 1] if '--dir' in sys.argv else None)
    salvate, problemi, errori = L.salva_blocchi(d, sys.stdin.read(), C.progetto(d), C.glossario(d))
    if errori:
        sys.exit('ERRORE: ' + '; '.join(errori) + '. Niente salvato: ripeti il comando.')
    if not salvate:
        sys.exit('ERRORE: nessun blocco @@PARTE NNNN@@. Niente salvato.')
    for n in salvate:
        if n in problemi:
            print(f'{n:04d}: DA CORREGGERE'); [print('  -', x) for x in problemi[n]]
        else:
            print(f'OK {n:04d}')
    print('salvate: ' + ', '.join(f'{n:04d}' for n in salvate))
    sys.exit(1 if problemi else 0)


if __name__ == '__main__':
    main()
