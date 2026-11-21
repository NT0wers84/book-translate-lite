"""Series continuity: carry the glossary, rules and settings of a previous volume into a new job,
and rewrite a changed rendering in parts that are already translated.

  inherit(d, prev)            terms (types kept), rules.md and the typography/check/build settings of
                              `prev`; returns the terms whose rendering differs between the two jobs
  retro(d, source, old, new)  in every translated part, replaces `old` with `new` only in paragraphs
                              whose source paragraph contains `source` (any of its forms); returns the
                              number of replacements

Paragraph alignment is safe because every part keeps the source's paragraph count (a blocking check).
"""
import os, re
import common as C

# settings that describe the series' house style, not the single book
SERIES_KEYS = ('genre', 'quotes', 'typographic_apostrophe', 'punct_outside_quotes', 'replacements', 'forbidden',
               'uppercase_chat', 'toc_title', 'rights', 'formats', 'group_size', 'review', 'review_group_size',
               'engine', 'engine_command', 'model', 'reasoning', 'review_engine', 'review_model',
               'review_reasoning', 'ratio_min', 'ratio_max')

WORD = r'A-Za-zÀ-ÖØ-öø-ÿ'


def variants(old, new):
    """(old, new) pairs: as given, with a capital first letter, and all caps (for shouted chat)."""
    out = [(old, new)]
    if old[:1].islower():
        out.append((old[:1].upper() + old[1:], new[:1].upper() + new[1:]))
    out.append((old.upper(), new.upper()))
    return list(dict.fromkeys(out))


def _rx(text):
    return re.compile(rf'(?<![{WORD}]){re.escape(text)}(?![{WORD}])')


def retro(d, source, old, new, parts=None):
    """Replace a rendering in already translated parts, paragraph by paragraph."""
    if not old or old == new:
        return 0
    src_rx = [C.rx_term(f) for f in [source] if f]
    pairs = [(_rx(a), b) for a, b in variants(old, new)]
    total = 0
    for n in parts or range(1, C.n_parts(d) + 1):
        if not C.translated(d, n):
            continue
        s, o = C.read(C.src_path(d, n)), C.read(C.out_path(d, n))
        sp = [p for p in re.split(r'\n\s*\n', s) if p.strip()]
        chunks = re.split(r'(\n\s*\n)', o)
        i, changed = -1, 0
        for k, p in enumerate(chunks):
            if not p.strip():
                continue
            i += 1
            sp_i = sp[i] if i < len(sp) else s
            if not any(r.search(sp_i) for r in src_rx):
                continue
            for rx, b in pairs:
                p, c = rx.subn(b, p)
                changed += c
            chunks[k] = p
        if changed:
            C.write(C.out_path(d, n), ''.join(chunks)); total += changed
    return total


def inherit(d, prev, keep_rules=False):
    """Bring the previous volume's glossary, rules and house-style settings into job `d`."""
    prev = os.path.abspath(prev)
    if not os.path.exists(os.path.join(prev, 'project.json')):
        raise SystemExit(f'ERROR: {prev} is not a book-translate-lite job (no project.json)')
    old = {t['source'].lower(): t for t in C.terms(prev)}
    cur = C.terms(d)
    differ = [(t, old[t['source'].lower()]) for t in cur
              if t['source'].lower() in old and t['target'] != old[t['source'].lower()]['target']]
    mine = [t for t in cur if t['source'].lower() not in old]
    merged = list(old.values()) + mine
    C.jsave(os.path.join(d, 'terms.json'), merged)
    pr = os.path.join(prev, 'rules.md')
    if os.path.exists(pr) and not keep_rules:
        C.write(os.path.join(d, 'rules.md'), C.read(pr))
    pcfg, cfg = C.jload(os.path.join(prev, 'project.json'), {}), C.jload(os.path.join(d, 'project.json'), {})
    for k in SERIES_KEYS:
        if k in pcfg:
            cfg[k] = pcfg[k]
    cfg['series_from'] = prev
    C.jsave(os.path.join(d, 'project.json'), cfg)
    return {'terms_prev': len(old), 'terms_new': len(mine), 'differ': differ}


def siblings(d, author, jobs):
    """Other jobs by the same author (likely the same series)."""
    a = (author or '').strip().lower()
    if not a:
        return []
    return [j for j in jobs if os.path.abspath(j) != os.path.abspath(d)
            and (C.jload(os.path.join(j, 'project.json'), {}) or {}).get('author', '').strip().lower() == a]
