"""Operazioni di base condivise da save.py, patch.py, finish.py, auto.py e passo.py."""
import glob, json, os, re, shutil
import comune as C
from check import verifica


# ---------------------------------------------------------------- traduzione

def leggi_blocchi(raw):
    """@@PARTE NNNN@@ testo @@META@@ {json} … → [(n, testo, meta)], errori."""
    raw = raw.replace('\r\n', '\n')
    raw = re.sub(r'^```[a-z]*\n|\n```\s*$', '', raw.strip()) if raw.strip().startswith('```') else raw
    pezzi = re.split(r'^[ \t]*@@PARTE (\d{1,4})@@[ \t]*$', raw, flags=re.M)
    items, errori = [], []
    for k in range(1, len(pezzi), 2):
        n = int(pezzi[k]); corpo = re.sub(r'\n@@FINE@@.*$', '', pezzi[k + 1], flags=re.S)
        testo, meta_raw = (corpo.split('@@META@@', 1) + [''])[:2]
        testo = testo.strip('\n') + '\n'
        meta = {'new_entities': [], 'conflicts': []}
        if meta_raw.strip():
            m = re.search(r'\{.*\}', meta_raw, re.S)
            try:
                meta.update(json.loads(m.group(0) if m else meta_raw))
            except (json.JSONDecodeError, AttributeError) as e:
                errori.append(f'META della parte {n:04d} non è JSON valido ({e})')
                continue
        if len(testo.strip()) < 2:
            errori.append(f'testo vuoto per la parte {n:04d}')
            continue
        items.append((n, testo, meta))
    return items, errori


def salva_blocchi(d, raw, cfg, terms, attese=None, tutto_o_niente=True):
    """Salva le parti. Ritorna (salvate, problemi{n: [..]}, errori)."""
    items, errori = leggi_blocchi(raw)
    for n, _, _ in items:
        if not os.path.exists(C.src_path(d, n)):
            errori.append(f'la parte {n:04d} non esiste')
    if attese:
        arrivate = {n for n, _, _ in items}
        errori += [f'manca la parte {n:04d} nella risposta' for n in attese if n not in arrivate]
    if errori and tutto_o_niente:
        return [], {}, errori
    salvate, problemi = [], {}
    for n, testo, meta in items:
        if not os.path.exists(C.src_path(d, n)) or (attese and n not in attese):
            continue
        testo, _ = C.correggi(testo, cfg)
        with open(C.out_path(d, n), 'w', encoding='utf-8') as f:
            f.write(testo)
        C.jsave(C.meta_path(d, n), meta)
        salvate.append(n)
        p, _w = verifica(d, n, cfg, terms)
        if p:
            problemi[n] = p
    return salvate, problemi, errori


# ---------------------------------------------------------------- revisione

def leggi_patch(raw):
    """@@PARTE NNNN@@ (@@VECCHIO@@ … @@NUOVO@@ …)* oppure @@OK@@ → {n: [(vecchio, nuovo)]}."""
    raw = raw.replace('\r\n', '\n')
    pezzi = re.split(r'^[ \t]*@@PARTE (\d{1,4})@@[ \t]*$', raw, flags=re.M)
    out = {}
    for k in range(1, len(pezzi), 2):
        n = int(pezzi[k]); corpo = re.sub(r'\n@@FINE@@.*$', '', pezzi[k + 1], flags=re.S)
        lst = out.setdefault(n, [])
        for m in re.finditer(r'@@VECCHIO@@\n(.*?)\n@@NUOVO@@\n(.*?)(?=\n@@VECCHIO@@|\n@@OK@@|\Z)', corpo, re.S):
            v, nu = m.group(1), m.group(2).rstrip('\n')
            if v.strip() and v != nu:
                lst.append((v, nu))
    return out


def applica_patch(d, raw, cfg, terms):
    """Applica le correzioni; una correzione che rompe la verifica viene annullata.
    Ritorna (applicate, scartate[(n, motivo)], parti_viste)."""
    bk = os.path.join(d, 'revisione', 'backup'); os.makedirs(bk, exist_ok=True)
    applicate, scartate = 0, []
    patch = leggi_patch(raw)
    for n, lst in patch.items():
        if not C.tradotta(d, n):
            scartate.append((n, 'parte non tradotta')); continue
        p = C.out_path(d, n)
        if not os.path.exists(os.path.join(bk, os.path.basename(p))):
            shutil.copy2(p, bk)
        ok_prima = not verifica(d, n, cfg, terms)[0]; fatte = []
        for v, nu in lst:
            t = C.leggi(p)
            if t.count(v) != 1:
                scartate.append((n, f'testo da sostituire trovato {t.count(v)} volte: «{v[:50]}»')); continue
            nu, _ = C.correggi(nu, cfg)
            open(p, 'w', encoding='utf-8').write(t.replace(v, nu))
            if ok_prima and verifica(d, n, cfg, terms)[0]:
                open(p, 'w', encoding='utf-8').write(t)
                scartate.append((n, f'la correzione rompe la verifica: «{v[:50]}»')); continue
            applicate += 1; fatte.append((v, nu))
        if fatte:
            with open(os.path.join(d, 'revisione', 'modifiche.md'), 'a', encoding='utf-8') as f:
                for v, nu in fatte:
                    f.write(f'- {n:04d}: «{v[:120]}» → «{nu[:120]}»\n')
    return applicate, scartate, sorted(patch)


# ---------------------------------------------------------------- chiusura

def integra_meta(d, ids, st, stampa=print):
    terms = C.glossario(d); idx = {}
    for t in terms:
        for f in C.forme(t):
            idx.setdefault(f.lower(), t)
    nuovi, cambiati, conflitti_v = [], [], []
    for n in ids:
        if n in st['meta_integrati']:
            continue
        meta = C.jload(C.meta_path(d, n), {}) or {}
        for e in meta.get('new_entities', []) or []:
            if not isinstance(e, dict):
                continue
            src = (e.get('source') or '').strip(); tgt = (e.get('target_proposal') or e.get('target') or '').strip()
            if not src or not tgt or src.lower() in idx:
                continue
            t = {'source': src, 'target': tgt, 'tipo': 'P', 'nota': (e.get('category') or '') + f' (parte {n:04d})', 'alias': []}
            terms.append(t); idx[src.lower()] = t; nuovi.append(f'{src}={tgt}')
        for c in meta.get('conflicts', []) or []:
            if not isinstance(c, dict):
                continue
            src = (c.get('source') or '').strip(); new = (c.get('proposed_target') or '').strip()
            t = idx.get(src.lower())
            if not t or not new or new == t['target']:
                continue
            if t.get('tipo') == 'V':
                conflitti_v.append({'parte': n, 'source': src, 'attuale': t['target'], 'proposta': new,
                                    'motivo': (c.get('reason') or '')[:120]})
                continue
            t['nota'] = (t.get('nota', '') + f' · prima: {t["target"]}').strip(' ·')
            t['target'] = new; cambiati.append(f'{src}={new}')
        st['meta_integrati'].append(n)
    if nuovi or cambiati:
        C.jsave(os.path.join(d, 'glossario.json'), terms)
    if conflitti_v:
        st.setdefault('conflitti_v', []).extend(conflitti_v)
    if nuovi:
        stampa(f'glossario: +{len(nuovi)} termini P: ' + '; '.join(nuovi)[:300])
    if cambiati:
        stampa('glossario: rese P cambiate: ' + '; '.join(cambiati)[:300])
    for x in conflitti_v:
        stampa(f'CONFLITTO SU TERMINE V (annotato in stato.json): {x["source"]}: «{x["attuale"]}» → «{x["proposta"]}»')


def chiudi(d, ids, st, da_rivedere=None, stampa=print):
    """Registra le parti tradotte, integra i meta, cancella i task chiusi."""
    fatte = [n for n in ids if C.tradotta(d, n)]
    st['fatte'] = sorted(set(st['fatte']) | set(fatte))
    for n, probs in (da_rivedere or {}).items():
        st['da_rivedere'][f'{n:04d}'] = probs
    for n in fatte:
        if not da_rivedere or n not in da_rivedere:
            st['da_rivedere'].pop(f'{n:04d}', None)
    integra_meta(d, fatte, st, stampa)
    st['meta_integrati'] = sorted(set(st['meta_integrati']))
    C.salva_stato(d, st)
    for f in glob.glob(os.path.join(d, '_task', 'task_*.md')):
        nums = [int(x) for x in re.findall(r'\d{4}', os.path.basename(f))]
        if nums and all(n in st['fatte'] for n in range(nums[0], nums[-1] + 1)):
            os.remove(f)


def riga_stato(d, st=None):
    st = st or C.stato(d); tot = C.n_parti(d); nx = C.prossima(d)
    fatte = sum(1 for i in range(1, tot + 1) if C.tradotta(d, i))
    s = f'STATO: {fatte}/{tot} tradotte, {len(st["fatte"])} registrate'
    if st['da_rivedere']:
        s += f', {len(st["da_rivedere"])} segnalate per la revisione'
    return s + '. Prossima: ' + (f'{nx:04d}' if nx else 'nessuna (traduzione completa)')
