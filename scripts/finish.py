#!/usr/bin/env python3
"""Chiude un blocco di parti: verifica → registra → integra i meta → cancella i task.

Uso:  finish.py 12 20            finish.py 12 20 --force (registra anche con problemi,
                                  segnandoli per la revisione finale)
      finish.py                  solo stato e prossima parte

Lo stato è semplice: stato.json elenca le parti fatte. Cambiare il glossario NON
rende mai «da ritradurre» una parte già fatta.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import comune as C
import lavoro as L
from check import verifica


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a', type=int, nargs='?'); ap.add_argument('b', type=int, nargs='?')
    ap.add_argument('--force', action='store_true'); ap.add_argument('--dir')
    o = ap.parse_args(); d = C.trova_dir(o.dir); st = C.stato(d)
    if o.a:
        cfg = C.progetto(d); terms = C.glossario(d)
        ids = list(range(o.a, (o.b or o.a) + 1))
        probs = {n: p for n in ids for p in [verifica(d, n, cfg, terms)[0]] if p}
        if probs and not o.force:
            for n, p in probs.items():
                print(f'{n:04d}: DA CORREGGERE'); [print('  -', x) for x in p]
            print('Correggi questi punti (modifica mirata) o rilancia il task della parte mancante, poi rilancia '
                  'finish.py. Se sono falsi positivi: --force (restano segnalati per la revisione).')
            sys.exit(1)
        L.chiudi(d, ids, st, da_rivedere={n: p for n, p in probs.items() if C.tradotta(d, n)})
    print(L.riga_stato(d))


if __name__ == '__main__':
    main()
