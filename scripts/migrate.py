#!/usr/bin/env python3
"""Import an existing project into book-translate-lite v2.

Usage:  migrate.py <folder>_temp [--to it] [--title "…"] [--author "…"] [--extra '{json for project.json}']
                   [--resync-glossary] [--clean-notes REGEX]

Handles two cases (and never touches chunk*.md, output_chunk*.md, *.meta.json,
glossary.json or run_state.json):

1. A translate-book project (https://github.com/deusyu/translate-book):
   creates project.json, rules.md, terms.json (from glossary.json: confidence low → proposed,
   otherwise fixed), candidates.json and state.json (done = parts recorded in run_state.json;
   meta merged = applied_meta_hashes). An old `_codex/check.py` with a BANNED dict becomes
   "forbidden" rules; `_codex/regole.md` or `_codex/rules.md` becomes rules.md.
   --resync-glossary rebuilds terms.json and state from glossary.json / run_state.json
   (use it if the old tool kept working after the first migration).
2. A book-translate-lite v1 project (Italian file names: progetto.json, glossario.json,
   stato.json, regole.md, …): converted to the v2 names and keys; the v1 files are moved
   to _v1_backup/.
"""
import argparse, ast, json, os, re, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as C
from init import apply_language, find_candidates, rules_template

KEYS = {'lingua': 'target_lang', 'gruppo': 'group_size', 'paralleli': 'parallel', 'tentativi': 'retries',
        'timeout_minuti': 'timeout_minutes', 'coda_continuita': 'tail_chars', 'rapporto_min': 'ratio_min',
        'rapporto_max': 'ratio_max', 'virgolette': 'quotes', 'apostrofo_tipografico': 'typographic_apostrophe',
        'punto_fuori': 'punct_outside_quotes', 'sostituzioni': 'replacements', 'vietate': 'forbidden',
        'maiuscolo_chat': 'uppercase_chat', 'motore': 'engine', 'comando_motore': 'engine_command',
        'modello': 'model', 'ragionamento': 'reasoning', 'motore_revisione': 'review_engine',
        'modello_revisione': 'review_model', 'ragionamento_revisione': 'review_reasoning', 'revisione': 'review',
        'gruppo_revisione': 'review_group_size', 'formati': 'formats', 'titolo': 'title', 'autore': 'author',
        'sorgente': 'source', 'migrato_da': 'migrated_from', 'max_gruppi_sessione': None, 'lingua_nome': None}
VALUES = {'comando': 'command', 'completa': 'full', 'segnalate': 'flagged', 'nessuna': 'none'}


def from_v1(d, say):
    bk = os.path.join(d, '_v1_backup'); os.makedirs(bk, exist_ok=True)
    old = C.jload(os.path.join(d, 'progetto.json'), {})
    cfg = {}
    for k, v in old.items():
        nk = KEYS.get(k, k)
        if nk:
            cfg[nk] = VALUES.get(v, v) if isinstance(v, str) else v
    cfg['replacements'] = [{'re': r['re'], 'with': r.get('con', r.get('with', ''))} for r in cfg.get('replacements', [])]
    lang = cfg.get('target_lang', 'it'); cfg.pop('target_lang_name', None)
    apply_language(cfg, lang)
    for k, v in C.DEFAULT.items():
        cfg.setdefault(k, v)
    C.jsave(os.path.join(d, 'project.json'), cfg)
    g = C.jload(os.path.join(d, 'glossario.json'), []) or []
    C.jsave(os.path.join(d, 'terms.json'), [{'source': t['source'], 'target': t['target'],
                                             'type': 'fixed' if t.get('tipo') == 'V' else 'proposed',
                                             'note': t.get('nota', ''), 'aliases': t.get('alias', [])} for t in g])
    pre = C.jload(os.path.join(d, 'preglossario.json'), []) or []
    C.jsave(os.path.join(d, 'candidates.json'),
            [{'term': x['termine'], 'count': x['n'], 'first_part': x['prima']} for x in pre])
    s = C.jload(os.path.join(d, 'stato.json'), {}) or {}
    st = {'done': s.get('fatte', []), 'meta_merged': s.get('meta_integrati', []), 'flagged': s.get('da_rivedere', {}),
          'reviewed': s.get('rivedute', []), 'attempts': s.get('tentativi', {}),
          'fixed_conflicts': [{'part': x.get('parte'), 'source': x.get('source'), 'current': x.get('attuale'),
                               'proposed': x.get('proposta'), 'reason': x.get('motivo', '')}
                              for x in s.get('conflitti_v', [])]}
    if s.get('finito'):
        st['finished'] = True
    if s.get('analisi_fatta'):
        st['analyzed'] = True
    C.save_state(d, st)
    if os.path.exists(os.path.join(d, 'regole.md')) and not os.path.exists(os.path.join(d, 'rules.md')):
        shutil.copy2(os.path.join(d, 'regole.md'), os.path.join(d, 'rules.md'))
    rv = os.path.join(d, 'revisione')
    if os.path.isdir(rv) and not os.path.exists(os.path.join(d, 'review')):
        shutil.copytree(rv, os.path.join(d, 'review'))
        for a, b in (('segnalazioni.json', 'flags.json'), ('rapporto.md', 'report.md'),
                     ('modifiche.md', 'changes.md'), ('RAPPORTO_FINALE.md', 'FINAL_REPORT.md')):
            if os.path.exists(os.path.join(d, 'review', a)):
                os.replace(os.path.join(d, 'review', a), os.path.join(d, 'review', b))
    for f in ('progetto.json', 'glossario.json', 'preglossario.json', 'stato.json', 'regole.md', 'revisione', '_task'):
        if os.path.exists(os.path.join(d, f)):
            shutil.move(os.path.join(d, f), os.path.join(bk, f))
    say(f'Converted from v1: {len(g)} terms, {len(st["done"])} parts done. v1 files moved to _v1_backup/.')


def banned(d):
    p = os.path.join(d, '_codex', 'check.py')
    if not os.path.exists(p):
        return []
    for node in ast.parse(C.read(p)).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'BANNED':
            return [{'re': k, 'msg': v} for k, v in ast.literal_eval(node.value).items()]
    return []


def from_translate_book(d, o, say):
    conf = {}
    if os.path.exists(os.path.join(d, 'config.txt')):
        for line in C.read(os.path.join(d, 'config.txt')).splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1); conf[k.strip()] = v.strip()
    lang = o.to or conf.get('output_lang')
    if not lang:
        sys.exit('ERROR: target language unknown: pass --to <code>.')
    pp = os.path.join(d, 'project.json'); cfg = C.jload(pp, {}) or {}
    apply_language(cfg, lang)
    for k, v in {'title': o.title or cfg.get('title') or re.sub(r'\s*\(.*?\)\s*$', '', conf.get('original_title', '')),
                 'author': o.author or cfg.get('author') or conf.get('creator', ''),
                 'source': conf.get('input_file', ''), 'migrated_from': 'translate-book'}.items():
        if v:
            cfg[k] = v
    if not cfg.get('forbidden'):
        cfg['forbidden'] = banned(d)
    for k, v in C.DEFAULT.items():
        cfg.setdefault(k, v)
    C.jsave(pp, cfg)
    rp = os.path.join(d, 'rules.md')
    if not os.path.exists(rp):
        src = next((p for p in (os.path.join(d, '_codex', 'rules.md'), os.path.join(d, '_codex', 'regole.md'))
                    if os.path.exists(p)), rules_template(lang))
        C.write(rp, C.read(src).replace('{language}', cfg['target_lang_name']))
    old = C.jload(os.path.join(d, 'glossary.json'), {}) or {}
    old_terms = old.get('terms', []) if isinstance(old, dict) else old
    tp = os.path.join(d, 'terms.json')
    if os.path.exists(tp) and not o.resync_glossary:
        ts = C.jload(tp, [])
        say('terms.json already exists: left as it is (use --resync-glossary to rebuild it from glossary.json)')
    else:
        ts = []
        for t in old_terms:
            note = re.sub(r'\[updated\].*', '', (t.get('notes') or '').replace('\n', ' '))
            if o.clean_notes:
                note = re.sub(o.clean_notes, '', note)
            ts.append({'source': t['source'], 'target': t['target'],
                       'type': 'proposed' if t.get('confidence') == 'low' else 'fixed',
                       'note': note.strip(), 'aliases': list(t.get('aliases', []))})
        C.jsave(tp, ts)
    rs = C.jload(os.path.join(d, 'run_state.json'), {}) or {}
    recorded = [int(k[-4:]) for k in rs.get('chunks', {}) if C.translated(d, int(k[-4:]))]
    applied = [int(k[-4:]) for k in (old.get('applied_meta_hashes', {}) if isinstance(old, dict) else {})]
    st = C.state(d)
    st['done'] = sorted(set(st['done']) | set(recorded))
    st['meta_merged'] = sorted(set(st['meta_merged']) | set(applied))
    C.save_state(d, st)
    fixed = sum(1 for t in ts if t.get('type') == 'fixed')
    say(f'terms.json: {len(ts)} terms ({fixed} fixed, {len(ts) - fixed} proposed) · forbidden rules: {len(cfg["forbidden"])}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir'); ap.add_argument('--to'); ap.add_argument('--title', default='')
    ap.add_argument('--author', default=''); ap.add_argument('--extra', default='{}')
    ap.add_argument('--resync-glossary', action='store_true')
    ap.add_argument('--clean-notes', default='', help='regex removed from glossary notes')
    o = ap.parse_args(); d = os.path.abspath(o.dir)
    if not os.path.exists(os.path.join(d, 'chunk0001.md')):
        sys.exit('ERROR: not a working folder (chunk0001.md missing)')
    if os.path.exists(os.path.join(d, 'progetto.json')) and not os.path.exists(os.path.join(d, 'project.json')):
        from_v1(d, print)
        if o.resync_glossary and os.path.exists(os.path.join(d, 'glossary.json')):
            from_translate_book(d, o, print)
    else:
        from_translate_book(d, o, print)
    extra = json.loads(o.extra)
    if extra:
        cfg = C.jload(os.path.join(d, 'project.json'), {}); cfg.update(extra); C.jsave(os.path.join(d, 'project.json'), cfg)
    if not os.path.exists(os.path.join(d, 'candidates.json')):
        C.jsave(os.path.join(d, 'candidates.json'), find_candidates(d))
    st = C.state(d)
    print(f'Migrated: {d}')
    print(f'state.json: {len(st["done"])} parts done, {len(st["meta_merged"])} meta merged · '
          f'next part: {C.next_missing(d) or "none"} of {C.n_parts(d)}')


if __name__ == '__main__':
    main()
