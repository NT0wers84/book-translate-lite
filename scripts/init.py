#!/usr/bin/env python3
"""Prepara un libro: conversione in parti Markdown + file di progetto.

Uso:  init.py libro.epub --lang it [--chunk-size 6000] [--gruppo 3] [--titolo "…"] [--autore "…"]
      (anche .pdf, .docx, .md)

Crea <libro>_temp/ accanto al libro (se il libro è direttamente in TRANSLATOR/,
crea prima la sottocartella TRANSLATOR/<libro>/: un lavoro per cartella) con:
chunkNNNN.md, progetto.json, regole.md (dal modello), glossario.json vuoto,
preglossario.json (nomi ricorrenti candidati) e stato.json.
Non sovrascrive mai regole.md, glossario.json o stato.json già presenti.
"""
import argparse, collections, glob, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import comune as C

LINGUE = {'it': 'italiano', 'en': 'inglese', 'fr': 'francese', 'es': 'spagnolo', 'de': 'tedesco',
          'pt': 'portoghese', 'nl': 'olandese', 'ja': 'giapponese', 'zh': 'cinese'}
STOP = set('''I A An The And But Or If So Then When While Where What Who Why How This That These Those
It Its He She We They You Your My Our His Her Their Me Him Us Them There Here Yes No Not Oh Ok Okay
Mr Mrs Ms Dr Sir Chapter Part Book One Two Three Four Five Six Seven Eight Nine Ten First Second Third
Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July
August September October November December After Before Now Just Well Still Even All Some Every Each
Maybe Okay Hey Wait Please Thanks Thank Of In On At For With From To By As Is Was Be Do Did Does Had Has Have
Il Lo La Le Gli Un Una E Ma Se Che Non Di Da In Con Su Per Tra Fra'''.split())


def preglossario(d):
    testo = '\n'.join(C.leggi(p) for p in sorted(glob.glob(os.path.join(d, 'chunk[0-9]*.md'))))
    testo = re.sub(r'\{[^}]*\}|\]\([^)]*\)|!\[[^\]]*\]|[*_#>\[\]]', ' ', testo)
    parola = r"[A-Z][\w\-]*(?:[’'][A-Z][\w\-]*)?"
    rx = re.compile(r"(?<![\w’'])" + parola + r"(?:\s+(?:of|the|de|del|la|di|von|van|du|le)?\s*" + parola + r")*")
    tot, medio, prima = collections.Counter(), collections.Counter(), {}
    parti = sorted(glob.glob(os.path.join(d, 'chunk[0-9]*.md')))
    for i, p in enumerate(parti, 1):
        t = re.sub(r'\{[^}]*\}|\]\([^)]*\)|!\[[^\]]*\]|[*_#>\[\]]', ' ', C.leggi(p))
        t = re.sub(r"[’'](?:s|m|d|ll|ve|re|t)\b", ' ', t)   # Mira’s → Mira, I’m → I
        for m in rx.finditer(t):
            w = re.sub(r'^(?:The|A|An)\s+', '', m.group(0)).strip()
            ws = w.split()
            while ws and ws[-1] in STOP:
                ws.pop()
            while ws and ws[0] in STOP:
                ws.pop(0)
            if not ws:
                continue
            w = ' '.join(ws)
            if w.isupper() and len(w) > 3:      # titoli, urla, chat in maiuscolo
                continue
            tot[w] += 1; prima.setdefault(w, i)
            pre = t[max(0, m.start() - 3):m.start()]
            if not re.search(r'(^|[.!?:“"«—\n]\s*)$', pre):
                medio[w] += 1
    low = collections.Counter(re.findall(r"\b[a-z][\w’'-]*", testo))
    out = []
    for w, n in tot.items():
        multi = ' ' in w
        if multi and n >= 2 or (not multi and n >= 3 and medio[w] >= 2 and low[w.lower()] < n / 4):
            out.append({'termine': w, 'n': n, 'prima': prima[w]})
    out.sort(key=lambda x: (-x['n'], x['termine']))
    return out[:400]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('libro'); ap.add_argument('--lang', default='it')
    ap.add_argument('--chunk-size', type=int, default=6000); ap.add_argument('--gruppo', type=int, default=3)
    ap.add_argument('--titolo', default=''); ap.add_argument('--autore', default='')
    o = ap.parse_args()
    libro = os.path.abspath(o.libro)
    if not os.path.exists(libro):
        sys.exit(f'ERRORE: {libro} non esiste')
    radice = os.path.dirname(libro)
    stem = os.path.splitext(os.path.basename(libro))[0]
    if os.path.basename(radice) == 'TRANSLATOR':
        radice = os.path.join(radice, stem); os.makedirs(radice, exist_ok=True)
    d = os.path.join(radice, f'{stem}_temp')
    if not glob.glob(os.path.join(d, 'chunk0001.md')):
        r = subprocess.run([sys.executable, os.path.join(C.SCRIPTS, 'vendor', 'convert.py'), libro,
                            '--olang', o.lang, '--chunk-size', str(o.chunk_size), '--temp-root', radice],
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit('ERRORE di conversione:\n' + r.stdout[-2000:] + r.stderr[-2000:])
    cfgtxt = {}
    if os.path.exists(os.path.join(d, 'config.txt')):
        for l in C.leggi(os.path.join(d, 'config.txt')).splitlines():
            if '=' in l and not l.startswith('#'):
                k, v = l.split('=', 1); cfgtxt[k.strip()] = v.strip()
    pp = os.path.join(d, 'progetto.json')
    cfg = C.jload(pp, {}) or {}
    titolo = o.titolo or cfg.get('titolo') or re.sub(r'\s*\(.*?\)\s*$', '', cfgtxt.get('original_title', stem))
    cfg.update({'lingua': o.lang, 'lingua_nome': LINGUE.get(o.lang, o.lang), 'gruppo': o.gruppo,
                'titolo': titolo, 'autore': o.autore or cfg.get('autore') or cfgtxt.get('creator', ''),
                'sorgente': libro})
    if o.lang == 'it':
        cfg.setdefault('virgolette', '«»'); cfg.setdefault('apostrofo_tipografico', True); cfg.setdefault('punto_fuori', True)
        cfg.setdefault('sostituzioni', [{'re': r'\bOkay\b', 'con': 'Ok'},
                                        {'re': r'(?<![.!?…])\.\.\.(?!\.)', 'con': '…'}])
    else:
        cfg.setdefault('virgolette', '“”'); cfg.setdefault('apostrofo_tipografico', o.lang in ('fr', 'en'))
        cfg.setdefault('punto_fuori', False)
    for k, v in C.DEFAULT.items():
        cfg.setdefault(k, v)
    C.jsave(pp, cfg)
    rp = os.path.join(d, 'regole.md')
    if not os.path.exists(rp):
        modello = os.path.join(C.SKILL, 'modelli', f'regole_{o.lang}.md')
        if not os.path.exists(modello):
            modello = os.path.join(C.SKILL, 'modelli', 'regole_generico.md')
        open(rp, 'w', encoding='utf-8').write(C.leggi(modello).replace('{lingua_nome}', cfg['lingua_nome']))
    if not os.path.exists(os.path.join(d, 'glossario.json')):
        C.jsave(os.path.join(d, 'glossario.json'), [])
    if not os.path.exists(os.path.join(d, 'stato.json')):
        C.jsave(os.path.join(d, 'stato.json'), {'fatte': [], 'meta_integrati': []})
    pre = preglossario(d)
    C.jsave(os.path.join(d, 'preglossario.json'), pre)
    print(f'Cartella di lavoro: {d}')
    print(f'Parti: {C.n_parti(d)} · lingua {o.lang} · gruppi da {o.gruppo} · titolo «{titolo}»')
    print(f'Pre-glossario: {len(pre)} candidati. I più frequenti: ' + ', '.join(f"{x['termine']} ({x['n']})" for x in pre[:25]))
    print('Prossimo passo (facoltativo): fissa in glossario.json le rese dei nomi principali; poi prep.py.')


if __name__ == '__main__':
    main()
