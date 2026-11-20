"""Costruzione dei task autosufficienti (traduzione e revisione).

modo = 'comando': il sotto-agente salva con save.py / patch.py (2 chiamate di strumenti).
modo = 'diretto': il motore risponde solo con i blocchi; li salva auto.py (0 chiamate).
"""
import os
import comune as C

META_DOC = ('META: `new_entities` = [{"source", "target_proposal", "category", "evidence"}] per nomi e termini '
            'nuovi; `conflicts` = [{"source", "current_target", "proposed_target", "reason"}] solo se cambi un '
            'termine P. Se non c\'è niente, lascia le liste vuote.')


def tabella(terms):
    if not terms:
        return '(nessun termine del glossario in queste parti)'
    righe = ['| originale | resa | V/P | nota |', '|---|---|---|---|']
    for t in terms:
        nota = (t.get('nota') or '').replace('|', '/').replace('\n', ' ')
        if t.get('alias'):
            nota = 'alias: ' + ', '.join(t['alias'][:3]) + ('. ' if nota else '') + nota
        if len(nota) > 90:
            nota = nota[:87] + '…'
        righe.append(f"| {t['source']} | {t['target']} | {t.get('tipo', 'P')} | {nota} |")
    return '\n'.join(righe)


def candidati(d, testo, terms):
    noti = {f.lower() for t in terms for f in C.forme(t)}
    pre = C.jload(os.path.join(d, 'preglossario.json'), []) or []
    out = [c['termine'] for c in pre if c['termine'].lower() not in noti and C.rx_term(c['termine']).search(testo)]
    return out[:20]


def coda(testo, k):
    t = testo.strip()
    if len(t) <= k:
        return t
    t = t[-k:]
    return t[t.find(' ') + 1:] if ' ' in t[:40] else t


def continuita(d, n, cfg):
    k = cfg['coda_continuita']
    if n == 1:
        return 'inizio del libro', ''
    if C.tradotta(d, n - 1):
        return 'fine della parte tradotta precedente', coda(C.leggi(C.out_path(d, n - 1)), k)
    return ('parte precedente non ancora tradotta: fine del testo ORIGINALE, solo contesto, NON tradurre',
            coda(C.leggi(C.src_path(d, n - 1)), k))


def _scrivi(d, prefisso, ids, txt):
    tag = f'{ids[0]:04d}' if len(ids) == 1 else f'{ids[0]:04d}-{ids[-1]:04d}'
    os.makedirs(os.path.join(d, '_task'), exist_ok=True)
    path = os.path.join(d, '_task', f'{prefisso}_{tag}.md')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(txt)
    return path


def traduzione(d, ids, cfg, terms, regole, modo='comando', problemi=None):
    srcs = {n: C.leggi(C.src_path(d, n)).strip() for n in ids}
    tutto = '\n'.join(srcs.values())
    nomi = ', '.join(f'{n:04d}' for n in ids)
    etichetta, cod = continuita(d, ids[0], cfg)
    blocchi = '\n'.join(f'@@PARTE {n:04d}@@\n…traduzione completa della parte {n:04d}…\n@@META@@\n'
                        '{"new_entities": [], "conflicts": []}' for n in ids)
    cand = candidati(d, tutto, terms)
    cand_txt = ('\n\n**Nomi ricorrenti ancora senza resa** (se li traduci, mettili in new_entities): '
                + ', '.join(cand)) if cand else ''
    testi = '\n\n'.join(f'## Testo originale — parte {n:04d}\n\n{srcs[n]}' for n in ids)
    titolo = cfg.get('titolo') or os.path.basename(d).replace('_temp', '')
    lingua = cfg['lingua_nome']
    if modo == 'diretto':
        proc = f"""**Compito:** traduci in {lingua} TUTTE le parti in fondo, in ordine, ciascuna per intero, con lo stesso Markdown e gli stessi paragrafi dell'originale. Non usare strumenti e non leggere file: hai già tutto qui.

**Rispondi SOLO con i blocchi qui sotto**, nient'altro prima o dopo (niente commenti, niente recinti ```):

{blocchi}"""
    else:
        save = os.path.join(C.SCRIPTS, 'save.py')
        proc = f"""**Procedura (DUE comandi in tutto):** hai già letto questo file. Traduci in {lingua} TUTTE le parti in fondo, in ordine, ciascuna per intero, con lo stesso Markdown e gli stessi paragrafi dell'originale. Poi salva tutto con UN SOLO comando:

```bash
python3 "{save}" <<'@@FINE@@'
{blocchi}
@@FINE@@
```

- `save.py` scrive le parti e i meta, fa le correzioni meccaniche e verifica.
- Se una parte risulta «DA CORREGGERE», correggi solo quei punti con una modifica mirata a `output_chunkNNNN.md`.
- Non leggere altri file. Rispondi solo «fatto {nomi}» oppure il problema residuo."""
    prob_txt = ''
    if problemi:
        prob_txt = ('\n\n## Il tentativo precedente è stato respinto dal controllo automatico\n\nEvita questi errori:\n'
                    + '\n'.join(f'- parte {n:04d}: {p}' for n, ps in problemi.items() for p in ps))
    txt = f"""# TASK traduzione parti {nomi} — {titolo} → {lingua}

{proc}

{META_DOC}{prob_txt}

## Termini (V = vincolante · P = proposta, cambiabile con conflicts)

{tabella(C.presenti(terms, tutto))}{cand_txt}

## Regole

{regole}

## Continuità — {etichetta}

```text
{cod}
```

{testi}
"""
    return _scrivi(d, 'task', ids, txt)


ISTR_REV = """Rileggi ogni traduzione confrontandola con l'originale e correggi:
- errori di senso, frasi o pezzi omessi o aggiunti;
- termini diversi dal glossario (V) o incoerenti fra le parti;
- italiano innaturale o calcato sull'originale, refusi, concordanze, punteggiatura contro le regole;
- i problemi elencati in «Segnalazioni», se ci sono.
Non riscrivere lo stile quando è corretto; non toccare Markdown, attributi {…}, link e immagini; non unire o dividere paragrafi."""


def revisione(d, ids, cfg, terms, regole, segnalazioni, modo='comando'):
    lingua = cfg['lingua_nome']
    nomi = ', '.join(f'{n:04d}' for n in ids)
    esempio = ('@@PARTE NNNN@@\n@@VECCHIO@@\n…testo esatto da sostituire (copiato dalla traduzione, '
               'abbastanza lungo da essere unico)…\n@@NUOVO@@\n…testo corretto…\n'
               '@@VECCHIO@@\n…\n@@NUOVO@@\n…\n@@PARTE MMMM@@\n@@OK@@')
    if modo == 'diretto':
        proc = (f'**Rispondi SOLO con le correzioni**, una sezione per parte, in questo formato '
                f'(@@OK@@ se la parte va bene), nient\'altro:\n\n{esempio}')
    else:
        patch = os.path.join(C.SCRIPTS, 'patch.py')
        proc = (f'**Procedura (DUE comandi in tutto):** hai già letto questo file. Poi applica tutte le correzioni '
                f'con UN SOLO comando (@@OK@@ se la parte va bene):\n\n```bash\npython3 "{patch}" <<\'@@FINE@@\'\n'
                f'{esempio}\n@@FINE@@\n```\n\n`patch.py` applica, scarta le correzioni che non trova o che rompono '
                f'la verifica e stampa l\'esito. Non leggere altri file. Rispondi solo «rivisto {nomi}».')
    blocchi = []
    tutto = ''
    for n in ids:
        s = C.leggi(C.src_path(d, n)).strip(); o = C.leggi(C.out_path(d, n)).strip(); tutto += s + '\n'
        seg = segnalazioni.get(f'{n:04d}') or []
        seg_txt = ('\n\n**Segnalazioni:**\n' + '\n'.join(f'- {x}' for x in seg)) if seg else ''
        blocchi.append(f'# Parte {n:04d}{seg_txt}\n\n## Originale {n:04d}\n\n{s}\n\n## Traduzione {n:04d}\n\n{o}')
    txt = f"""# TASK revisione parti {nomi} — {cfg.get('titolo', '')} ({lingua})

{ISTR_REV}

{proc}

## Termini (V = vincolante · P = proposta)

{tabella(C.presenti(terms, tutto))}

## Regole della traduzione

{regole}

{chr(10).join(blocchi)}
"""
    return _scrivi(d, 'rev', ids, txt)
