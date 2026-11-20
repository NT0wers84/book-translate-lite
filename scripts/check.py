#!/usr/bin/env python3
"""Check one or more translated parts. Prints only the problems. Does NOT modify files
(unless --fix, which applies the mechanical fixes from project.json).

Usage:  check.py 12            check.py 12 20         check.py --all
        check.py 12 20 --fix   check.py --all --short   (summary only)
Exit 1 if at least one part NEEDS FIXING.

Blocking: paragraph count, **bold**, *italics*, {.classes} (small caps…), images,
# headings, > quotes, paragraphs suspiciously short/long, glossary terms left in the
source language, project "forbidden" rules, all-caps chat names, untranslated text,
invalid meta.  Warnings: a fixed term expected but not found.
"""
import argparse, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as C


def italics(t):
    t = t.replace('***', '\0')
    return len(re.findall(r'(?<![*\\])\*(?!\*)', t)) + t.count('\0')


COUNTS = [('bold **', lambda t: t.replace('***', '').count('**') + t.count('***')),
          ('italics *', italics),
          ('images', lambda t: len(re.findall(r'!\[', t))),
          ('headings #', lambda t: len(re.findall(r'(?m)^#{1,6} ', t))),
          ('quotes >', lambda t: len(re.findall(r'(?m)^>', t)))]


def check(d, n, cfg, ts, fix=False):
    probs, warns = [], []
    if not os.path.exists(C.src_path(d, n)):
        return [f'part {n:04d} does not exist'], []
    if not C.translated(d, n):
        return [f'output_chunk{n:04d}.md is missing'], []
    s = C.read(C.src_path(d, n)); o = C.read(C.out_path(d, n))
    if fix:
        o2, k = C.fix(o, cfg)
        if k:
            C.write(C.out_path(d, n), o2); o = o2
            warns.append(f'{k} mechanical fixes applied')
    if o.strip() == s.strip():
        return ['identical to the source (not translated)'], warns
    ps, po = C.paragraphs(s), C.paragraphs(o)
    if len(ps) != len(po):
        probs.append(f'paragraphs source {len(ps)} / translation {len(po)} (line skipped or merged?)')
    for name, f in COUNTS:
        a, b = f(s), f(o)
        if a != b:
            probs.append(f'{name}: source {a} / translation {b}')
    cs, co = sorted(re.findall(r'\{\.[\w-]+', s)), sorted(re.findall(r'\{\.[\w-]+', o))
    if cs != co:
        probs.append(f'{{.class}} attributes: source {len(cs)} / translation {len(co)}')
    if len(ps) == len(po):
        lo, hi = cfg['ratio_min'], cfg['ratio_max']
        for j, (x, y) in enumerate(zip(ps, po), 1):
            if len(x) > 80 and not (lo <= len(y) / len(x) <= hi):
                probs.append(f'paragraph {j}: length translation/source {len(y)/len(x):.2f} → «{y[:50]}…»')
            elif len(x) > 120 and x.strip() == y.strip():
                probs.append(f'paragraph {j} not translated → «{y[:50]}…»')
    clean = re.sub(r'\{[^}]*\}|\]\([^)]*\)', '', o)
    for r in cfg['forbidden']:
        for m in re.finditer(r['re'], clean):
            probs.append(f'«{clean[max(0, m.start()-20):m.end()+10].strip()}» → {r["msg"]}')
    for name in cfg['uppercase_chat']:
        for m in re.finditer(r'(?m)^\**' + re.escape(name) + r':\**\s*(.+)$', o):
            if re.search(r'[a-zà-ÿ]{3,}', re.sub(r'\*|https?://\S+|\{[^}]*\}', '', m.group(1))):
                probs.append(f'{name}’s chat is not ALL CAPS: «{m.group(1)[:40]}»')
    ol = o.lower()
    for t in C.present(ts, s):
        src, tgt = t['source'], t['target']
        if len(src) < 4 or src.lower() in tgt.lower():
            continue
        if C.rx_term(src).search(o):
            probs.append(f'term left untranslated: «{src}» → «{tgt}»')
            continue
        if t.get('type') == 'fixed' and ' ' in src.strip():
            tc = re.sub(r'\s*\(.*?\)', '', tgt)
            stem = tc.lower()[:max(4, len(tc) - 3)]
            if stem not in ol and stem[:5] not in ol:
                warns.append(f'«{src}»: expected «{tc}» (fine if rendered differently for context)')
    mp = C.meta_path(d, n)
    if os.path.exists(mp):
        try:
            C.jload(mp)
        except Exception as e:
            probs.append(f'invalid meta JSON: {e}')
    return probs, warns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a', type=int, nargs='?'); ap.add_argument('b', type=int, nargs='?')
    ap.add_argument('--all', action='store_true', help='every translated part')
    ap.add_argument('--fix', action='store_true'); ap.add_argument('--short', action='store_true')
    ap.add_argument('--dir')
    o = ap.parse_args(); d = C.find_dir(o.dir); cfg = C.project(d); ts = C.terms(d)
    if o.all:
        ids = [i for i in range(1, C.n_parts(d) + 1) if C.translated(d, i)]
    elif o.a:
        ids = list(range(o.a, (o.b or o.a) + 1))
    else:
        ap.error('give the parts (A [B]) or --all')
    bad = []
    for n in ids:
        p, w = check(d, n, cfg, ts, o.fix)
        if p:
            bad.append(n)
        if o.short:
            continue
        if p:
            print(f'{n:04d}: NEEDS FIXING'); [print('  -', x) for x in p]
        else:
            print(f'OK {n:04d}' + (' (warnings)' if w else ''))
        [print('  · warning:', x) for x in w]
    if len(ids) > 1 or o.short:
        print(f'SUMMARY: {len(ids) - len(bad)}/{len(ids)} OK' +
              (f'; needs fixing: {", ".join(f"{n:04d}" for n in bad)}' if bad else ''))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
