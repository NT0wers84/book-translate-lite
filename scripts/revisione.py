#!/usr/bin/env python3
"""Revisione finale del libro.

Uso:  revisione.py analizza       scansione di tutto il libro → revisione/segnalazioni.json + rapporto.md
      revisione.py da-fare        parti che la revisione deve ancora vedere (secondo progetto.json "revisione")
      revisione.py finale         analisi finale, build e revisione/RAPPORTO_FINALE.md

La revisione vera (lettura originale + traduzione, correzioni @@VECCHIO@@/@@NUOVO@@)
la fanno i sotto-agenti o il motore: vedi auto.py (automatico) o passo.py (in chat).

Segnalazioni raccolte, per parte:
- problemi bloccanti di check.py e quelli rimasti dopo i tentativi di traduzione;
- termini V attesi e non trovati; termini del glossario resi in modo diverso nel libro;
- frasi probabilmente rimaste in lingua originale; parole ripetute («il il»);
- virgolette dritte o non bilanciate; puntini «...» invece di «…».
"""
import collections, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import comune as C
from check import verifica

EN = re.compile(r"\b(the|and|you|with|that|this|have|was|what|for|are|but|not|just|from|they|would|there|could|"
                r"about|been|were|which|their|your|into|don’t|didn’t|I’m|it’s)\b")


def analizza(d, stampa=print):
    cfg = C.progetto(d); terms = C.glossario(d); st = C.stato(d); tot = C.n_parti(d)
    seg = collections.defaultdict(list)
    mancati = collections.Counter()           # termine → parti in cui la resa manca
    for n in range(1, tot + 1):
        k = f'{n:04d}'
        if not C.tradotta(d, n):
            seg[k].append('parte non tradotta'); continue
        p, w = verifica(d, n, cfg, terms)
        seg[k] += p + [f'avviso: {x}' for x in w]
        seg[k] += [f'rimasto dalla traduzione: {x}' for x in st['da_rivedere'].get(k, []) if x not in p]
        s = C.leggi(C.src_path(d, n)); o = C.leggi(C.out_path(d, n)); ol = o.lower()
        for t in C.presenti(terms, s):
            tc = re.sub(r'\s*\(.*?\)', '', t['target'])
            if t['source'].lower() not in tc.lower() and len(tc) > 3 and tc.lower()[:max(4, len(tc) - 3)] not in ol:
                mancati[t['source']] += 1
        testo = re.sub(r'\{[^}]*\}|\]\([^)]*\)|`[^`]*`', '', o)
        pars = C.paragrafi(testo)
        for j, par in enumerate(pars, 1):
            dopo = pars[j] if j < len(pars) else ''
            if cfg['lingua'] != 'en' and len(EN.findall(par)) >= 3:
                seg[k].append(f'paragrafo {j}: forse in lingua originale → «{par[:60]}…»')
            for m in re.finditer(r'\b(\w{2,}) \1\b', par, re.I):
                if m.group(1).lower() not in ('ah', 'eh', 'oh', 'no', 'sì', 'si', 'ha', 'ehi', 'bla', 'tic', 'toc'):
                    seg[k].append(f'paragrafo {j}: parola ripetuta «{m.group(0)}»')
            if cfg.get('virgolette') == '«»':
                if '"' in par:
                    seg[k].append(f'paragrafo {j}: virgolette dritte " → «»')
                a, c = par.count('«'), par.count('»')
                if c > a or (a > c and not dopo.lstrip('*_> ').startswith('«')):
                    seg[k].append(f'paragrafo {j}: virgolette « » non bilanciate')
            if cfg['lingua'] == 'it' and re.search(r'(?<!\.)\.\.\.(?!\.)', par):
                seg[k].append(f'paragrafo {j}: «...» invece di «…»')
    # resa che manca in molte parti: probabile incoerenza nel libro
    incoerenti = [(s, c) for s, c in mancati.most_common() if c >= 2]
    tsrc = {t['source']: t for t in terms}
    for src, c in incoerenti[:40]:
        rx = C.rx_term(src)
        for n in range(1, tot + 1):
            if C.tradotta(d, n) and rx.search(C.leggi(C.src_path(d, n))):
                tc = re.sub(r'\s*\(.*?\)', '', tsrc[src]['target'])
                if tc.lower()[:max(4, len(tc) - 3)] not in C.leggi(C.out_path(d, n)).lower():
                    seg[f'{n:04d}'].append(f'«{src}» non reso come «{tc}» (glossario {tsrc[src].get("tipo")}): '
                                           'controlla la coerenza')
    seg = {k: list(dict.fromkeys(v)) for k, v in seg.items() if v}
    os.makedirs(os.path.join(d, 'revisione'), exist_ok=True)
    C.jsave(os.path.join(d, 'revisione', 'segnalazioni.json'), seg)
    bloccanti = [k for k, v in seg.items() if any(not x.startswith('avviso') for x in v)]
    righe = [f'# Analisi della traduzione — {cfg.get("titolo", "")}', '',
             f'- Parti: {tot}; con segnalazioni: {len(seg)}; con segnalazioni non solo «avviso»: {len(bloccanti)}',
             f'- Parti rivedute: {len(st["rivedute"])}', '']
    if incoerenti:
        righe += ['## Termini resi in modo diverso dal glossario in più parti', '',
                  '| originale | resa | parti |', '|---|---|---|']
        righe += [f'| {s} | {tsrc[s]["target"]} | {c} |' for s, c in incoerenti[:40]] + ['']
    if st['conflitti_v']:
        righe += ['## Proposte di cambio su termini vincolanti (da decidere)', '']
        righe += [f'- {x["source"]}: «{x["attuale"]}» → «{x["proposta"]}» (parte {x["parte"]:04d}: {x["motivo"]})'
                  for x in st['conflitti_v']] + ['']
    righe += ['## Segnalazioni per parte', '']
    for k in sorted(seg):
        righe.append(f'- **{k}**: ' + ' · '.join(seg[k])[:600])
    open(os.path.join(d, 'revisione', 'rapporto.md'), 'w', encoding='utf-8').write('\n'.join(righe) + '\n')
    stampa(f'ANALISI: {len(seg)} parti con segnalazioni ({len(bloccanti)} non solo avvisi); '
           f'{len(incoerenti)} termini incoerenti → revisione/rapporto.md')
    return seg


def da_fare(d):
    cfg = C.progetto(d); st = C.stato(d)
    if cfg['revisione'] == 'nessuna':
        return []
    tutte = [n for n in range(1, C.n_parti(d) + 1) if C.tradotta(d, n)]
    if cfg['revisione'] == 'segnalate':
        seg = C.jload(os.path.join(d, 'revisione', 'segnalazioni.json'), {}) or {}
        tutte = [n for n in tutte if any(not x.startswith('avviso') for x in seg.get(f'{n:04d}', []))]
    return [n for n in tutte if n not in st['rivedute']]


def gruppi(ids, g):
    """Gruppi di parti consecutive, al massimo g per gruppo."""
    out = []
    for n in ids:
        if out and len(out[-1]) < g and out[-1][-1] == n - 1:
            out[-1].append(n)
        else:
            out.append([n])
    return out


def finale(d, stampa=print):
    cfg = C.progetto(d); st = C.stato(d)
    seg = analizza(d, stampa)
    r = subprocess.run([sys.executable, os.path.join(C.SCRIPTS, 'build.py'), '--dir', d, '--formati', cfg['formati']],
                       capture_output=True, text=True)
    build = r.stdout.strip() if r.returncode == 0 else 'BUILD NON RIUSCITA: ' + (r.stderr or r.stdout)[-500:]
    mod = os.path.join(d, 'revisione', 'modifiche.md')
    n_mod = sum(1 for _ in open(mod, encoding='utf-8')) if os.path.exists(mod) else 0
    bloccanti = sorted(k for k, v in seg.items() if any(not x.startswith('avviso') for x in v))
    txt = f"""# Rapporto finale — {cfg.get('titolo', '')}

- Parti tradotte: {sum(1 for n in range(1, C.n_parti(d) + 1) if C.tradotta(d, n))}/{C.n_parti(d)}
- Parti rivedute: {len(st['rivedute'])} (revisione: {cfg['revisione']})
- Correzioni applicate in revisione: {n_mod} (elenco in `revisione/modifiche.md`, originali in `revisione/backup/`)
- Parti ancora con segnalazioni non solo «avviso»: {len(bloccanti)}{(' → ' + ', '.join(bloccanti[:60])) if bloccanti else ''}
- Proposte su termini vincolanti da decidere: {len(st['conflitti_v'])}

Dettagli: `revisione/rapporto.md`.

## Libro

```
{build}
```

## Ultima lettura consigliata (Claude o umano)

1. Le parti elencate sopra, partendo da `revisione/rapporto.md`.
2. Le proposte sui termini vincolanti: se le accetti, cambia `glossario.json` e cerca la vecchia resa nelle `output_chunk*.md`.
3. Poi `build.py` per rigenerare il libro.
"""
    open(os.path.join(d, 'revisione', 'RAPPORTO_FINALE.md'), 'w', encoding='utf-8').write(txt)
    st['finito'] = True; C.salva_stato(d, st)
    stampa(f'FINITO. {build.splitlines()[0] if build else ""} Rapporto: revisione/RAPPORTO_FINALE.md')
    return txt


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('analizza', 'da-fare', 'finale'):
        sys.exit(__doc__)
    d = C.trova_dir(sys.argv[sys.argv.index('--dir') + 1] if '--dir' in sys.argv else None)
    if sys.argv[1] == 'analizza':
        analizza(d)
    elif sys.argv[1] == 'da-fare':
        ids = da_fare(d)
        print(f'{len(ids)} parti da rivedere' + (': ' + ', '.join(f'{n:04d}' for n in ids[:50]) if ids else ''))
    else:
        finale(d)


if __name__ == '__main__':
    main()
