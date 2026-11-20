#!/usr/bin/env python3
"""Converte un progetto translate-book (o il kit _codex/) in un progetto book-translate-lite.

Uso:  migra.py <cartella>_temp [--lang it] [--titolo "…"] [--autore "…"] [--extra '{json per progetto.json}']

- NON tocca chunk*.md, output_chunk*.md, *.meta.json, glossary.json, run_state.json.
- Crea/aggiorna: progetto.json, regole.md (da _codex/regole.md se c'è), glossario.json
  (da glossary.json: confidence low → P, altrimenti V), preglossario.json, stato.json
  (parti fatte = registrate in run_state.json; meta integrati = applied_meta_hashes).
- Rilanciabile: glossario.json, regole.md e preglossario.json esistenti non vengono toccati
  (--rifai-glossario rigenera glossario.json da glossary.json, perdendo le modifiche successive).
- Se c'è un vecchio kit `_codex/check.py` con un dizionario BANNED, le sue regole
  diventano «vietate» in progetto.json.
"""
import argparse, ast, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import comune as C
from init import LINGUE, preglossario



def banned(d):
    p = os.path.join(d, '_codex', 'check.py')
    if not os.path.exists(p):
        return []
    for nodo in ast.parse(C.leggi(p)).body:
        if isinstance(nodo, ast.Assign) and getattr(nodo.targets[0], 'id', '') == 'BANNED':
            return [{'re': k, 'msg': v} for k, v in ast.literal_eval(nodo.value).items()]
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir'); ap.add_argument('--lang'); ap.add_argument('--titolo', default='')
    ap.add_argument('--autore', default=''); ap.add_argument('--extra', default='{}')
    ap.add_argument('--rifai-glossario', action='store_true')
    ap.add_argument('--pulisci-note', default='', help='regex da togliere dalle note dei termini')
    o = ap.parse_args(); d = os.path.abspath(o.dir)
    if not os.path.exists(os.path.join(d, 'chunk0001.md')):
        sys.exit('ERRORE: non sembra una cartella di translate-book (manca chunk0001.md)')
    conf = {}
    if os.path.exists(os.path.join(d, 'config.txt')):
        for l in C.leggi(os.path.join(d, 'config.txt')).splitlines():
            if '=' in l and not l.startswith('#'):
                k, v = l.split('=', 1); conf[k.strip()] = v.strip()
    lang = o.lang or conf.get('output_lang', 'it')
    pp = os.path.join(d, 'progetto.json'); cfg = C.jload(pp, {}) or {}
    cfg.update({k: v for k, v in {
        'lingua': lang, 'lingua_nome': LINGUE.get(lang, lang),
        'titolo': o.titolo or cfg.get('titolo') or re.sub(r'\s*\(.*?\)\s*$', '', conf.get('original_title', '')),
        'autore': o.autore or cfg.get('autore') or conf.get('creator', ''),
        'sorgente': conf.get('input_file', ''), 'migrato_da': 'translate-book'}.items() if v})
    if not cfg.get('vietate'):
        cfg['vietate'] = banned(d)
    cfg.update(json.loads(o.extra))
    for k, v in C.DEFAULT.items():
        cfg.setdefault(k, v)
    C.jsave(pp, cfg)

    rp = os.path.join(d, 'regole.md')
    if not os.path.exists(rp):
        src = os.path.join(d, '_codex', 'regole.md')
        if not os.path.exists(src):
            src = os.path.join(C.SKILL, 'modelli', f'regole_{lang}.md')
        if not os.path.exists(src):
            src = os.path.join(C.SKILL, 'modelli', 'regole_generico.md')
        open(rp, 'w', encoding='utf-8').write(C.leggi(src).replace('{lingua_nome}', cfg['lingua_nome']))

    vecchio = C.jload(os.path.join(d, 'glossary.json'), {}) or {}
    vt = vecchio.get('terms', vecchio) if isinstance(vecchio, (dict, list)) else []
    nuovo = []
    for t in vt:
        nota = (t.get('notes') or '').replace('\n', ' ')
        nota = re.sub(r'\[updated\].*', '', nota)
        if o.pulisci_note:
            nota = re.sub(o.pulisci_note, '', nota)
        nota = nota.strip()
        nuovo.append({'source': t['source'], 'target': t['target'],
                      'tipo': 'P' if t.get('confidence') == 'low' else 'V',
                      'nota': nota, 'alias': list(t.get('aliases', []))})
    gp = os.path.join(d, 'glossario.json')
    if os.path.exists(gp) and not o.rifai_glossario:
        nuovo = C.jload(gp, [])      # già migrato: glossario.json è ormai il riferimento
        print('glossario.json esiste già: lasciato com’è (usa --rifai-glossario per rigenerarlo da glossary.json)')
    else:
        C.jsave(gp, nuovo)

    rs = C.jload(os.path.join(d, 'run_state.json'), {}) or {}
    reg = [int(k[-4:]) for k in rs.get('chunks', {}) if C.tradotta(d, int(k[-4:]))]
    applied = [int(k[-4:]) for k in (vecchio.get('applied_meta_hashes', {}) if isinstance(vecchio, dict) else {})]
    st = C.stato(d)
    st['fatte'] = sorted(set(st['fatte']) | set(reg))
    st['meta_integrati'] = sorted(set(st['meta_integrati']) | set(applied))
    C.jsave(os.path.join(d, 'stato.json'), st)

    if not os.path.exists(os.path.join(d, 'preglossario.json')):
        C.jsave(os.path.join(d, 'preglossario.json'), preglossario(d))
    v = sum(1 for t in nuovo if t['tipo'] == 'V')
    print(f'Migrato: {d}')
    print(f'glossario.json: {len(nuovo)} termini ({v} V, {len(nuovo) - v} P) · regole vietate: {len(cfg["vietate"])}')
    print(f'stato.json: {len(st["fatte"])} parti fatte, {len(st["meta_integrati"])} meta già integrati')
    print(f'Prossima parte: {C.prossima(d) or "nessuna"} di {C.n_parti(d)}')


if __name__ == '__main__':
    main()
