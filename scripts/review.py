#!/usr/bin/env python3
"""Final review of the book.

Usage:  review.py analyze      scan the whole book → review/flags.json + review/report.md
        review.py todo         parts the review still has to see (per project.json "review")
        review.py final        last analysis, build and review/FINAL_REPORT.md

The actual review (reading source + translation, @@OLD@@/@@NEW@@ fixes) is done by the
engine or by sub-agents: see auto.py (automatic) or step.py (in-chat).

Flags collected per part:
- blocking problems from check.py and those left after the translation retries;
- fixed terms expected but missing; glossary terms rendered differently across the book;
- sentences probably left in the source language; doubled words ("the the");
- straight or unbalanced quotes; "..." instead of "…" when the language profile replaces it.
"""
import collections, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as C
from check import check

# frequent function words of the SOURCE language: 3+ in one paragraph = probably untranslated
FUNCTION_WORDS = {
    'en': r"the|and|you|with|that|this|have|was|what|for|are|but|not|just|from|they|would|there|could|about|been|"
          r"were|which|their|your|into|don’t|didn’t|I’m|it’s",
    'fr': r"le|les|des|est|une|vous|nous|avec|pour|dans|qui|que|pas|sur|mais|elle|ils|cette|été|être",
    'de': r"der|die|das|und|ist|nicht|ich|sie|mit|ein|eine|auf|für|den|dem|sich|auch|wir|war|aber",
    'es': r"el|los|las|que|una|por|con|para|está|pero|como|más|este|esta|fue|todo|muy|él|ella|también",
    'it': r"il|gli|che|della|delle|sono|questo|questa|anche|perché|però|molto|nella|degli|alla|essere",
}
NOT_DOUBLED = {'ah', 'eh', 'oh', 'no', 'ha', 'hey', 'bla', 'tic', 'toc', 'sì', 'si', 'very', 'so', 'knock', 'bye'}


def analyze(d, say=print):
    cfg = C.project(d); ts = C.terms(d); st = C.state(d); tot = C.n_parts(d)
    flags = collections.defaultdict(list)
    missing_term = collections.Counter()
    src_lang = cfg.get('source_lang', 'en')
    fw = FUNCTION_WORDS.get(src_lang) if src_lang != cfg['target_lang'] else None
    fw_rx = re.compile(r'\b(' + fw + r')\b', re.I) if fw else None
    ellipsis_fix = any('\\.\\.\\.' in r.get('re', '') for r in cfg.get('replacements', []))
    for n in range(1, tot + 1):
        k = f'{n:04d}'
        if not C.translated(d, n):
            flags[k].append('part not translated'); continue
        p, w = check(d, n, cfg, ts)
        flags[k] += p + [f'warning: {x}' for x in w]
        flags[k] += [f'left over from translation: {x}' for x in st['flagged'].get(k, []) if x not in p]
        s = C.read(C.src_path(d, n)); o = C.read(C.out_path(d, n)); ol = o.lower()
        for t in C.present(ts, s):
            tc = re.sub(r'\s*\(.*?\)', '', t['target'])
            if t['source'].lower() not in tc.lower() and len(tc) > 3 and tc.lower()[:max(4, len(tc) - 3)] not in ol:
                missing_term[t['source']] += 1
        text = re.sub(r'\{[^}]*\}|\]\([^)]*\)|`[^`]*`', '', o)
        pars = C.paragraphs(text)
        for j, par in enumerate(pars, 1):
            after = pars[j] if j < len(pars) else ''
            if fw_rx and len(fw_rx.findall(par)) >= 3:
                flags[k].append(f'paragraph {j}: maybe still in the source language → «{par[:60]}…»')
            for m in re.finditer(r'\b(\w{2,}) \1\b', par, re.I):
                if m.group(1).lower() not in NOT_DOUBLED:
                    flags[k].append(f'paragraph {j}: doubled word «{m.group(0)}»')
            q = cfg.get('quotes', '')
            if len(q) == 2 and q != '""':
                if '"' in par:
                    flags[k].append(f'paragraph {j}: straight quotes " → {q[0]}…{q[1]}')
                if q[0] != q[1]:
                    a, c = par.count(q[0]), par.count(q[1])
                    if c > a or (a > c and not after.lstrip('*_> ').startswith(q[0])):
                        flags[k].append(f'paragraph {j}: unbalanced quotes {q[0]} {q[1]}')
            if ellipsis_fix and re.search(r'(?<!\.)\.\.\.(?!\.)', par):
                flags[k].append(f'paragraph {j}: "..." instead of "…"')
    inconsistent = [(s, c) for s, c in missing_term.most_common() if c >= 2]
    by_src = {t['source']: t for t in ts}
    for src, c in inconsistent[:40]:
        rx = C.rx_term(src)
        tc = re.sub(r'\s*\(.*?\)', '', by_src[src]['target'])
        for n in range(1, tot + 1):
            if C.translated(d, n) and rx.search(C.read(C.src_path(d, n))):
                if tc.lower()[:max(4, len(tc) - 3)] not in C.read(C.out_path(d, n)).lower():
                    flags[f'{n:04d}'].append(f'«{src}» not rendered as «{tc}» (glossary {C.letter(by_src[src])}): '
                                             'check consistency')
    flags = {k: list(dict.fromkeys(v)) for k, v in flags.items() if v}
    os.makedirs(os.path.join(d, 'review'), exist_ok=True)
    C.jsave(os.path.join(d, 'review', 'flags.json'), flags)
    serious = [k for k, v in flags.items() if any(not x.startswith('warning') for x in v)]
    lines = [f'# Translation analysis — {cfg.get("title", "")}', '',
             f'- Parts: {tot}; with flags: {len(flags)}; with more than warnings: {len(serious)}',
             f'- Parts reviewed: {len(st["reviewed"])}', '']
    if inconsistent:
        lines += ['## Glossary terms rendered differently in several parts', '',
                  '| source | translation | parts |', '|---|---|---|']
        lines += [f'| {s} | {by_src[s]["target"]} | {c} |' for s, c in inconsistent[:40]] + ['']
    if st['fixed_conflicts']:
        lines += ['## Proposed changes to fixed terms (to decide)', '']
        lines += [f'- {x["source"]}: «{x["current"]}» → «{x["proposed"]}» (part {x["part"]:04d}: {x["reason"]})'
                  for x in st['fixed_conflicts']] + ['']
    lines += ['## Flags per part', '']
    for k in sorted(flags):
        lines.append(f'- **{k}**: ' + ' · '.join(flags[k])[:600])
    C.write(os.path.join(d, 'review', 'report.md'), '\n'.join(lines) + '\n')
    say(f'ANALYSIS: {len(flags)} parts flagged ({len(serious)} with more than warnings); '
        f'{len(inconsistent)} inconsistent terms → review/report.md')
    return flags


def todo(d):
    cfg = C.project(d); st = C.state(d)
    if cfg['review'] == 'none':
        return []
    ids = [n for n in range(1, C.n_parts(d) + 1) if C.translated(d, n)]
    if cfg['review'] == 'flagged':
        flags = C.jload(os.path.join(d, 'review', 'flags.json'), {}) or {}
        ids = [n for n in ids if any(not x.startswith('warning') for x in flags.get(f'{n:04d}', []))]
    return [n for n in ids if n not in st['reviewed']]


def final(d, say=print):
    cfg = C.project(d); st = C.state(d)
    flags = analyze(d, say)
    r = subprocess.run([sys.executable, os.path.join(C.SCRIPTS, 'build.py'), '--dir', d, '--formats', cfg['formats']],
                       capture_output=True, text=True)
    build = r.stdout.strip() if r.returncode == 0 else 'BUILD FAILED: ' + (r.stderr or r.stdout)[-500:]
    ch = os.path.join(d, 'review', 'changes.md')
    n_ch = sum(1 for _ in open(ch, encoding='utf-8')) if os.path.exists(ch) else 0
    serious = sorted(k for k, v in flags.items() if any(not x.startswith('warning') for x in v))
    text = f"""# Final report — {cfg.get('title', '')}

- Parts translated: {sum(1 for n in range(1, C.n_parts(d) + 1) if C.translated(d, n))}/{C.n_parts(d)}
- Parts reviewed: {len(st['reviewed'])} (review mode: {cfg['review']})
- Fixes applied during review: {n_ch} (list in `review/changes.md`, originals in `review/backup/`)
- Parts still flagged with more than warnings: {len(serious)}{(' → ' + ', '.join(serious[:60])) if serious else ''}
- Proposed changes to fixed terms, to decide: {len(st['fixed_conflicts'])}

Details: `review/report.md`.

## Book

```
{build}
```

## Suggested last pass (Claude or a human)

1. The parts listed above, starting from `review/report.md`.
2. The proposed changes to fixed terms: if you accept one, change `terms.json` and search the old rendering in `output_chunk*.md`.
3. Then `build.py` to rebuild the book.
"""
    C.write(os.path.join(d, 'review', 'FINAL_REPORT.md'), text)
    st['finished'] = True; C.save_state(d, st)
    say(f'FINISHED. {build.splitlines()[0] if build else ""} Report: review/FINAL_REPORT.md')
    return text


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('analyze', 'todo', 'final'):
        sys.exit(__doc__)
    d = C.find_dir(C.arg_dir())
    if sys.argv[1] == 'analyze':
        analyze(d)
    elif sys.argv[1] == 'todo':
        ids = todo(d)
        print(f'{len(ids)} parts to review' + (': ' + ', '.join(f'{n:04d}' for n in ids[:50]) if ids else ''))
    else:
        final(d)


if __name__ == '__main__':
    main()
