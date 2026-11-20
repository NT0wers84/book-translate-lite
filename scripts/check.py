#!/usr/bin/env python3
"""Verifica una o più parti tradotte. Stampa solo i problemi. NON modifica i file
(salvo --fix, che applica le correzioni meccaniche di progetto.json).

Uso:  check.py 12            check.py 12 20         check.py --tutte
      check.py 12 20 --fix   check.py --tutte --breve   (solo il riepilogo)
Exit 1 se almeno una parte è DA CORREGGERE.

Bloccanti: numero di paragrafi, **grassetti**, *corsivi*, {.classi} (maiuscoletto…),
immagini, titoli #, paragrafi sospetti per lunghezza, termini lasciati in originale,
regole «vietate» del progetto, chat in maiuscolo, testo non tradotto, meta non valido.
Avvisi: termine vincolante (V) atteso ma non trovato.
"""
import argparse, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import comune as C


def italici(t):
    t = t.replace('***', '\0')
    return len(re.findall(r'(?<![*\\])\*(?!\*)', t)) + t.count('\0')


CONTE = [('grassetti **', lambda t: t.replace('***', '').count('**') + t.count('***')),
         ('corsivi *', italici),
         ('immagini', lambda t: len(re.findall(r'!\[', t))),
         ('titoli #', lambda t: len(re.findall(r'(?m)^#{1,6} ', t))),
         ('citazioni >', lambda t: len(re.findall(r'(?m)^>', t)))]


def verifica(d, n, cfg, terms, fix=False):
    probs, avvisi = [], []
    if not os.path.exists(C.src_path(d, n)):
        return [f'la parte {n:04d} non esiste'], []
    if not C.tradotta(d, n):
        return [f'manca output_chunk{n:04d}.md'], []
    s = C.leggi(C.src_path(d, n)); o = C.leggi(C.out_path(d, n))
    if fix:
        o2, k = C.correggi(o, cfg)
        if k:
            open(C.out_path(d, n), 'w', encoding='utf-8').write(o2); o = o2
            avvisi.append(f'{k} correzioni meccaniche applicate')
    if o.strip() == s.strip():
        return ['testo identico all’originale (non tradotto)'], avvisi
    ps, po = C.paragrafi(s), C.paragrafi(o)
    if len(ps) != len(po):
        probs.append(f'paragrafi orig. {len(ps)} / trad. {len(po)} (battuta saltata o unita?)')
    for nome, f in CONTE:
        a, b = f(s), f(o)
        if a != b:
            probs.append(f'{nome}: orig. {a} / trad. {b}')
    cs, co = sorted(re.findall(r'\{\.[\w-]+', s)), sorted(re.findall(r'\{\.[\w-]+', o))
    if cs != co:
        probs.append(f'attributi {{.classe}}: orig. {len(cs)} / trad. {len(co)}')
    if len(ps) == len(po):
        lo, hi = cfg['rapporto_min'], cfg['rapporto_max']
        for j, (x, y) in enumerate(zip(ps, po), 1):
            if len(x) > 80 and not (lo <= len(y) / len(x) <= hi):
                probs.append(f'paragrafo {j}: lunghezza trad./orig. {len(y)/len(x):.2f} → «{y[:50]}…»')
            elif len(x) > 120 and x.strip() == y.strip():
                probs.append(f'paragrafo {j} non tradotto → «{y[:50]}…»')
    pulito = re.sub(r'\{[^}]*\}|\]\([^)]*\)', '', o)
    for r in cfg['vietate']:
        for m in re.finditer(r['re'], pulito):
            probs.append(f'«{pulito[max(0, m.start()-20):m.end()+10].strip()}» → {r["msg"]}')
    for nome in cfg['maiuscolo_chat']:
        for m in re.finditer(r'(?m)^\**' + re.escape(nome) + r':\**\s*(.+)$', o):
            if re.search(r'[a-zà-ÿ]{3,}', re.sub(r'\*|https?://\S+|\{[^}]*\}', '', m.group(1))):
                probs.append(f'chat di {nome} non in MAIUSCOLO: «{m.group(1)[:40]}»')
    ol = o.lower()
    for t in C.presenti(terms, s):
        src, tgt = t['source'], t['target']
        if len(src) < 4 or src.lower() in tgt.lower():
            continue
        if C.rx_term(src).search(o):
            probs.append(f'termine lasciato in originale: «{src}» → «{tgt}»')
            continue
        if t.get('tipo') == 'V' and ' ' in src.strip():
            tc = re.sub(r'\s*\(.*?\)', '', tgt)
            stem = tc.lower()[:max(4, len(tc) - 3)]
            if stem not in ol and stem[:5] not in ol:
                avvisi.append(f'«{src}»: atteso «{tc}» (ok se reso diversamente per contesto)')
    mp = C.meta_path(d, n)
    if os.path.exists(mp):
        try:
            C.jload(mp)
        except Exception as e:
            probs.append(f'meta JSON non valido: {e}')
    return probs, avvisi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a', type=int, nargs='?'); ap.add_argument('b', type=int, nargs='?')
    ap.add_argument('--tutte', action='store_true', help='tutte le parti già tradotte')
    ap.add_argument('--fix', action='store_true'); ap.add_argument('--breve', action='store_true')
    ap.add_argument('--dir')
    o = ap.parse_args(); d = C.trova_dir(o.dir); cfg = C.progetto(d); terms = C.glossario(d)
    if o.tutte:
        ids = [i for i in range(1, C.n_parti(d) + 1) if C.tradotta(d, i)]
    elif o.a:
        ids = list(range(o.a, (o.b or o.a) + 1))
    else:
        ap.error('indica le parti (A [B]) oppure --tutte')
    bad = []
    for n in ids:
        p, w = verifica(d, n, cfg, terms, o.fix)
        if p:
            bad.append(n)
        if o.breve:
            continue
        if p:
            print(f'{n:04d}: DA CORREGGERE'); [print('  -', x) for x in p]
        else:
            print(f'OK {n:04d}' + (' (avvisi)' if w else ''))
        [print('  · avviso:', x) for x in w]
    if len(ids) > 1 or o.breve:
        print(f'RIEPILOGO: {len(ids) - len(bad)}/{len(ids)} OK' +
              (f'; da correggere: {", ".join(f"{n:04d}" for n in bad)}' if bad else ''))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
