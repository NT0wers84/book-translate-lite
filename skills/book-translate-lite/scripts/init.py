#!/usr/bin/env python3
"""Set up a book: conversion into Markdown parts + project files.

Usage:  init.py book.epub --to it [--from en] [--chunk-size 6000] [--group 3]
                [--title "Translated title"] [--author "…"]
        (.pdf, .docx and .md work too; `--to` is any language code, see templates/languages.json)

Creates <book>_temp/ next to the book with: chunkNNNN.md, project.json (typography from the
language profile), rules.md (from templates/rules/<lang>.md or generic.md), an empty
terms.json, candidates.json (recurring names) and state.json.
Never overwrites an existing rules.md, terms.json or state.json.
"""
import argparse, collections, glob, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as C

STOP = set('''I A An The And But Or If So Then When While Where What Who Why How This That These Those
It Its He She We They You Your My Our His Her Their Me Him Us Them There Here Yes No Not Oh Ok Okay
Mr Mrs Ms Dr Sir Chapter Part Book One Two Three Four Five Six Seven Eight Nine Ten First Second Third
Monday Tuesday Wednesday Thursday Friday Saturday Sunday January February March April May June July
August September October November December After Before Now Just Well Still Even All Some Every Each
Maybe Hey Wait Please Thanks Thank Of In On At For With From To By As Is Was Be Do Did Does Had Has Have
Don Didn Can Could Would Should Will Let Yeah'''.split())


def find_candidates(d):
    parts = sorted(glob.glob(os.path.join(d, 'chunk[0-9]*.md')))
    strip = lambda t: re.sub(r'\{[^}]*\}|\]\([^)]*\)|!\[[^\]]*\]|[*_#>\[\]]', ' ', t)
    alltext = strip('\n'.join(C.read(p) for p in parts))
    word = r"[A-Z][\w\-]*(?:[’'][A-Z][\w\-]*)?"
    rx = re.compile(r"(?<![\w’'])" + word + r"(?:\s+(?:of|the|de|del|la|di|von|van|du|le)?\s*" + word + r")*")
    total, mid, first = collections.Counter(), collections.Counter(), {}
    for i, p in enumerate(parts, 1):
        t = strip(C.read(p))
        t = re.sub(r"[’'](?:s|m|d|ll|ve|re|t)\b", ' ', t)   # Mira’s → Mira, I’m → I
        for m in rx.finditer(t):
            ws = re.sub(r'^(?:The|A|An)\s+', '', m.group(0)).split()
            while ws and ws[-1] in STOP:
                ws.pop()
            while ws and ws[0] in STOP:
                ws.pop(0)
            if not ws:
                continue
            w = ' '.join(ws)
            if w.isupper() and len(w) > 3:      # headings, shouting, all-caps chat
                continue
            total[w] += 1; first.setdefault(w, i)
            if not re.search(r'(^|[.!?:“"«—\n]\s*)$', t[max(0, m.start() - 3):m.start()]):
                mid[w] += 1
    low = collections.Counter(re.findall(r"\b[a-z][\w’'-]*", alltext))
    out = []
    for w, n in total.items():
        multi = ' ' in w
        if multi and n >= 2 or (not multi and n >= 3 and mid[w] >= 2 and low[w.lower()] < n / 4):
            out.append({'term': w, 'count': n, 'first_part': first[w]})
    out.sort(key=lambda x: (-x['count'], x['term']))
    return out[:400]


def apply_language(cfg, lang):
    prof = C.languages().get(lang, {})
    cfg['target_lang'] = lang
    cfg['target_lang_name'] = prof.get('name', lang)
    for k in ('quotes', 'typographic_apostrophe', 'punct_outside_quotes', 'replacements', 'toc_title'):
        if k in prof:
            cfg.setdefault(k, prof[k])
    return prof


def rules_template(lang):
    p = os.path.join(C.TEMPLATES, 'rules', f'{lang}.md')
    return p if os.path.exists(p) else os.path.join(C.TEMPLATES, 'rules', 'generic.md')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('book'); ap.add_argument('--to', required=True, help='target language code (it, fr, de, es, …)')
    ap.add_argument('--from', dest='src', default='en', help='source language code (default en)')
    ap.add_argument('--chunk-size', type=int, default=6000); ap.add_argument('--group', type=int, default=3)
    ap.add_argument('--title', default=''); ap.add_argument('--author', default='')
    o = ap.parse_args()
    book = os.path.abspath(o.book)
    if not os.path.exists(book):
        sys.exit(f'ERROR: {book} does not exist')
    root = os.path.dirname(book)
    stem = os.path.splitext(os.path.basename(book))[0]
    d = os.path.join(root, f'{stem}_temp')
    if not glob.glob(os.path.join(d, 'chunk0001.md')):
        r = subprocess.run([sys.executable, os.path.join(C.SCRIPTS, 'vendor', 'convert.py'), book,
                            '--olang', o.to, '--chunk-size', str(o.chunk_size), '--temp-root', root],
                           capture_output=True, text=True)
        if r.returncode:
            sys.exit('ERROR during conversion:\n' + r.stdout[-2000:] + r.stderr[-2000:])
    meta = {}
    if os.path.exists(os.path.join(d, 'config.txt')):
        for line in C.read(os.path.join(d, 'config.txt')).splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1); meta[k.strip()] = v.strip()
    pp = os.path.join(d, 'project.json')
    cfg = C.jload(pp, {}) or {}
    prof = apply_language(cfg, o.to)
    cfg.update({'source_lang': o.src, 'group_size': o.group, 'source': book,
                'title': o.title or cfg.get('title') or re.sub(r'\s*\(.*?\)\s*$', '', meta.get('original_title', stem)),
                'author': o.author or cfg.get('author') or meta.get('creator', '')})
    for k, v in C.DEFAULT.items():
        cfg.setdefault(k, v)
    C.jsave(pp, cfg)
    rp = os.path.join(d, 'rules.md')
    if not os.path.exists(rp):
        C.write(rp, C.read(rules_template(o.to)).replace('{language}', cfg['target_lang_name']))
    if not os.path.exists(os.path.join(d, 'terms.json')):
        C.jsave(os.path.join(d, 'terms.json'), [])
    if not os.path.exists(os.path.join(d, 'state.json')):
        C.save_state(d, C.state(d))
    cand = find_candidates(d)
    C.jsave(os.path.join(d, 'candidates.json'), cand)
    print(f'Working folder: {d}')
    print(f'Parts: {C.n_parts(d)} · {o.src} → {o.to} ({cfg["target_lang_name"]}'
          + ('' if prof else ', no language profile: generic rules') + f') · groups of {o.group} · title «{cfg["title"]}»')
    print(f'Candidates: {len(cand)} recurring names. Most frequent: '
          + ', '.join(f"{x['term']} ({x['count']})" for x in cand[:25]))
    print('Next (optional): translated title in project.json, key names in terms.json, style notes in rules.md;'
          ' then auto.py or step.py.')


if __name__ == '__main__':
    main()
