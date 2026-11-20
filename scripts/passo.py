#!/usr/bin/env python3
"""Modalità in chat: dice all'orchestratore la PROSSIMA azione, fino alla fine del libro.

Uso:  passo.py [--dir CARTELLA]

Ogni volta che lo lanci:
1. chiude i task finiti (verifica, registra, integra il glossario; le parti respinte
   vengono rimesse in un task con l'elenco degli errori, fino a `tentativi` volte, poi
   accettate e segnalate per la revisione);
2. stampa i prompt dei sotto-agenti da avviare ADESSO (tutti insieme), oppure
   «FINITO» quando traduzione, revisione e libro sono pronti.
Fasi: traduzione → analisi → revisione (task rev_*) → finale (build + rapporto).
"""
import glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import comune as C
import lavoro as L
import revisione as R
import task as T
from check import verifica

PROMPT = ('Lavora in `{d}`. Esegui `cat _task/{f}` e segui le istruzioni in cima al file. '
          'Non leggere altri file. Rispondi solo «fatto …» oppure il problema residuo.')


def parti(f):
    nums = [int(x) for x in re.findall(r'\d{4}', os.path.basename(f))]
    return list(range(nums[0], nums[-1] + 1)) if nums else []


def main():
    d = C.trova_dir(sys.argv[sys.argv.index('--dir') + 1] if '--dir' in sys.argv else None)
    cfg = C.progetto(d); terms = C.glossario(d); st = C.stato(d); tot = C.n_parti(d)
    regole = C.leggi(os.path.join(d, 'regole.md')).strip()
    tent = st.setdefault('tentativi', {})
    lanciare = []

    # 1. chiusura dei task di traduzione
    chiuse = []; da_riv = {}
    for f in sorted(glob.glob(os.path.join(d, '_task', 'task_*.md'))):
        ids = parti(f)
        manc = [n for n in ids if not C.tradotta(d, n)]
        probs = {n: p for n in ids if n not in manc for p in [verifica(d, n, cfg, terms)[0]] if p}
        rifare = []
        for n in manc + sorted(probs):
            k = f'{n:04d}'; tent[k] = tent.get(k, 0) + 1
            if tent[k] <= cfg['tentativi']:
                rifare.append(n)
            elif n in probs:
                da_riv[n] = probs[n]
        if not manc and not probs:
            os.remove(f); chiuse += ids; continue
        if rifare:
            os.remove(f)
            ok = [n for n in ids if n not in rifare]
            chiuse += ok
            for gr in R.gruppi(rifare, cfg['gruppo']):
                p = T.traduzione(d, gr, cfg, terms, regole,
                                 problemi={n: probs.get(n, ['parte non salvata']) for n in gr})
                lanciare.append(p)
        else:
            os.remove(f); chiuse += [n for n in ids if C.tradotta(d, n)]
    if chiuse:
        L.chiudi(d, chiuse, st, da_rivedere=da_riv)
        st = C.stato(d); st['tentativi'] = tent
    C.salva_stato(d, st)

    # 2. nuova traduzione
    if not lanciare:
        mancanti = [n for n in range(1, tot + 1) if not C.tradotta(d, n)]
        bloccate = [n for n in mancanti if tent.get(f'{n:04d}', 0) > cfg['tentativi'] + 2]
        mancanti = [n for n in mancanti if n not in bloccate]
        if bloccate:
            print('BLOCCATE (non si riesce a tradurle, serve un intervento): '
                  + ', '.join(f'{n:04d}' for n in bloccate))
            if not mancanti:
                return
        if mancanti:
            for gr in R.gruppi(mancanti[:cfg['gruppo'] * cfg['paralleli']], cfg['gruppo']):
                lanciare.append(T.traduzione(d, gr, cfg, terms, regole))
                for n in gr:
                    if f'{n:04d}' in tent:
                        tent[f'{n:04d}'] += 1
            C.salva_stato(d, dict(C.stato(d), tentativi=tent))
    if lanciare:
        print(L.riga_stato(d))
        print(f'AVVIA ADESSO {len(lanciare)} sotto-agenti (tutti insieme), poi rilancia passo.py:')
        for p in lanciare:
            print('- ' + PROMPT.format(d=d, f=os.path.basename(p)))
        return

    # 3. revisione
    if cfg['revisione'] != 'nessuna':
        if not st.get('analisi_fatta'):
            R.analizza(d); st = C.stato(d); st['analisi_fatta'] = True; C.salva_stato(d, st)
        seg = C.jload(os.path.join(d, 'revisione', 'segnalazioni.json'), {}) or {}
        aperti = []
        for f in sorted(glob.glob(os.path.join(d, '_task', 'rev_*.md'))):
            if all(n in st['rivedute'] for n in parti(f)):
                os.remove(f)
            else:
                k = os.path.basename(f); tent[k] = tent.get(k, 0) + 1
                if tent[k] > 2:          # due lanci senza esito: segna come vista e vai avanti
                    st['rivedute'] = sorted(set(st['rivedute']) | set(parti(f))); os.remove(f)
                else:
                    aperti.append(f)
        st['tentativi'] = tent; C.salva_stato(d, st)
        if not aperti:
            occupati = {n for f in aperti for n in parti(f)}
            ids = [n for n in R.da_fare(d) if n not in occupati]
            aperti = [T.revisione(d, gr, cfg, terms, regole, seg)
                      for gr in R.gruppi(ids, cfg['gruppo_revisione'])[:cfg['paralleli']]]
        if aperti:
            print(f'REVISIONE: {len(st["rivedute"])} parti rivedute, {len(R.da_fare(d))} da fare.')
            print(f'AVVIA ADESSO {len(aperti)} sotto-agenti (tutti insieme), poi rilancia passo.py:')
            for p in aperti:
                print('- ' + PROMPT.format(d=d, f=os.path.basename(p)))
            return

    # 4. fine
    if st.get('finito'):
        print('FINITO (già completato). Per rigenerare il libro: build.py; rapporto: revisione/RAPPORTO_FINALE.md')
        return
    R.finale(d)


if __name__ == '__main__':
    main()
