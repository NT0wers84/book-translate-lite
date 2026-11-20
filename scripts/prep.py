#!/usr/bin/env python3
"""Crea i task autosufficienti per i sotto-agenti (modalità in chat).

Uso:  prep.py                 dalla prossima parte da tradurre, `paralleli` gruppi (default 3×3 parti)
      prep.py 12 20 [--g 2]   parti 12–20 in gruppi da g
      prep.py --rev 12 20     task di REVISIONE (vedi revisione.py)

Stampa per ogni task il prompt esatto da dare al sotto-agente.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import comune as C
import task as T

PROMPT = ('Lavora in `{d}`. Esegui `cat _task/{f}` e segui le istruzioni in cima al file. '
          'Non leggere altri file. Rispondi solo «fatto …» oppure il problema residuo.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a', type=int, nargs='?'); ap.add_argument('b', type=int, nargs='?')
    ap.add_argument('--g', type=int); ap.add_argument('--rev', action='store_true'); ap.add_argument('--dir')
    o = ap.parse_args(); d = C.trova_dir(o.dir); cfg = C.progetto(d); tot = C.n_parti(d)
    terms = C.glossario(d); regole = C.leggi(os.path.join(d, 'regole.md')).strip()
    if o.rev:
        g = o.g or cfg['gruppo_revisione']
        seg = C.jload(os.path.join(d, 'revisione', 'segnalazioni.json'), {}) or {}
        ids = list(range(o.a, (o.b or o.a) + 1))
        for k in range(0, len(ids), g):
            p = T.revisione(d, ids[k:k + g], cfg, terms, regole, seg)
            print(f'{os.path.basename(p)} → PROMPT: ' + PROMPT.format(d=d, f=os.path.basename(p)))
        return
    g = o.g or cfg['gruppo']
    a = o.a or C.prossima(d)
    if not a:
        sys.exit('Tutte le parti sono tradotte: passa alla revisione (passo.py).')
    b = min(o.b or (a + cfg['paralleli'] * g - 1), tot)
    ids = list(range(a, b + 1))
    gia = [n for n in ids if C.tradotta(d, n)]
    if gia:
        print('ATTENZIONE: già tradotte (verranno sovrascritte se le rifai):', ', '.join(f'{n:04d}' for n in gia))
    for k in range(0, len(ids), g):
        p = T.traduzione(d, ids[k:k + g], cfg, terms, regole)
        print(f'{os.path.basename(p)} ({os.path.getsize(p) // 1024} KB) → PROMPT: '
              + PROMPT.format(d=d, f=os.path.basename(p)))
    print(f'Poi: finish.py {a} {b}')


if __name__ == '__main__':
    main()
