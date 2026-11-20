"""Self-contained tasks for translation and review.

mode = 'tool':   a sub-agent saves with save.py / patch.py (2 tool calls in total).
mode = 'direct': the engine answers with the blocks only; auto.py saves them (0 tool calls).
"""
import os
import common as C

META_DOC = ('META: `new_entities` = [{"source", "target_proposal", "category", "evidence"}] for new names and '
            'terms; `conflicts` = [{"source", "current_target", "proposed_target", "reason"}] only to change a P '
            'term. Leave the lists empty if there is nothing.')


def table(ts):
    if not ts:
        return '(no glossary terms in these parts)'
    rows = ['| source | translation | F/P | note |', '|---|---|---|---|']
    for t in ts:
        note = (t.get('note') or '').replace('|', '/').replace('\n', ' ')
        if t.get('aliases'):
            note = 'aliases: ' + ', '.join(t['aliases'][:3]) + ('. ' if note else '') + note
        if len(note) > 90:
            note = note[:87] + '…'
        rows.append(f"| {t['source']} | {t['target']} | {C.letter(t)} | {note} |")
    return '\n'.join(rows)


def candidates(d, text, ts):
    known = {f.lower() for t in ts for f in C.forms(t)}
    pre = C.jload(os.path.join(d, 'candidates.json'), []) or []
    out = [c['term'] for c in pre if c['term'].lower() not in known and C.rx_term(c['term']).search(text)]
    return out[:20]


def tail(text, k):
    t = text.strip()
    if len(t) <= k:
        return t
    t = t[-k:]
    return t[t.find(' ') + 1:] if ' ' in t[:40] else t


def continuity(d, n, cfg):
    k = cfg['tail_chars']
    if n == 1:
        return 'start of the book', ''
    if C.translated(d, n - 1):
        return 'end of the previous translated part', tail(C.read(C.out_path(d, n - 1)), k)
    return ('previous part not translated yet: end of the SOURCE text, context only, do NOT translate',
            tail(C.read(C.src_path(d, n - 1)), k))


def _write(d, prefix, ids, text):
    tag = f'{ids[0]:04d}' if len(ids) == 1 else f'{ids[0]:04d}-{ids[-1]:04d}'
    os.makedirs(os.path.join(d, '_tasks'), exist_ok=True)
    path = os.path.join(d, '_tasks', f'{prefix}_{tag}.md')
    C.write(path, text)
    return path


def translation(d, ids, cfg, ts, rules, mode='tool', problems=None):
    srcs = {n: C.read(C.src_path(d, n)).strip() for n in ids}
    alltext = '\n'.join(srcs.values())
    names = ', '.join(f'{n:04d}' for n in ids)
    label, ctx = continuity(d, ids[0], cfg)
    blocks = '\n'.join(f'@@PART {n:04d}@@\n…complete translation of part {n:04d}…\n@@META@@\n'
                       '{"new_entities": [], "conflicts": []}' for n in ids)
    cand = candidates(d, alltext, ts)
    cand_txt = ('\n\n**Recurring names with no translation yet** (if you translate them, add them to new_entities): '
                + ', '.join(cand)) if cand else ''
    texts = '\n\n'.join(f'## Source text — part {n:04d}\n\n{srcs[n]}' for n in ids)
    title = cfg.get('title') or os.path.basename(d).replace('_temp', '')
    lang = cfg['target_lang_name']
    if mode == 'direct':
        proc = f"""**Job:** translate ALL the parts below into {lang}, in order, each one in full, keeping the same Markdown and the same paragraphs as the source. Do not use tools or read files: everything you need is here.

**Answer ONLY with the blocks below**, nothing before or after (no comments, no ``` fences):

{blocks}"""
    else:
        save = os.path.join(C.SCRIPTS, 'save.py')
        proc = f"""**Procedure (TWO commands in total):** you have already read this file. Translate ALL the parts below into {lang}, in order, each one in full, keeping the same Markdown and the same paragraphs as the source. Then save everything with ONE command:

```bash
python3 "{save}" <<'@@END@@'
{blocks}
@@END@@
```

- `save.py` writes the parts and the meta, applies mechanical fixes and checks the result.
- If a part is reported as "NEEDS FIXING", fix only those points with a targeted edit of `output_chunkNNNN.md`.
- Do not read other files. Reply only "done {names}" or the remaining problem."""
    prob_txt = ''
    if problems:
        prob_txt = ('\n\n## The previous attempt was rejected by the automatic check\n\nAvoid these errors:\n'
                    + '\n'.join(f'- part {n:04d}: {p}' for n, ps in problems.items() for p in ps))
    text = f"""# TASK translation of parts {names} — {title} → {lang}

{proc}

{META_DOC}{prob_txt}

## Terms (F = fixed, do not change · P = proposed, may be changed via conflicts)

{table(C.present(ts, alltext))}{cand_txt}

## Rules

{rules}

## Continuity — {label}

```text
{ctx}
```

{texts}
"""
    return _write(d, 'task', ids, text)


REVIEW_JOB = """Re-read each translation against its source and fix:
- meaning errors, omitted or added sentences or fragments;
- terms that differ from the glossary (F) or are inconsistent between parts;
- unnatural phrasing calqued on the source, typos, agreement, punctuation that breaks the rules;
- the problems listed under "Flags", if any.
Do not rewrite style that is already correct; do not touch Markdown, {…} attributes, links and images; never merge or split paragraphs."""


def review(d, ids, cfg, ts, rules, flags, mode='tool'):
    lang = cfg['target_lang_name']
    names = ', '.join(f'{n:04d}' for n in ids)
    example = ('@@PART NNNN@@\n@@OLD@@\n…exact text to replace (copied from the translation, long enough to be '
               'unique)…\n@@NEW@@\n…corrected text…\n@@OLD@@\n…\n@@NEW@@\n…\n@@PART MMMM@@\n@@OK@@')
    if mode == 'direct':
        proc = (f'**Answer ONLY with the fixes**, one section per part, in this format '
                f'(@@OK@@ if the part is fine), nothing else:\n\n{example}')
    else:
        patch = os.path.join(C.SCRIPTS, 'patch.py')
        proc = (f'**Procedure (TWO commands in total):** you have already read this file. Then apply all the fixes '
                f'with ONE command (@@OK@@ if the part is fine):\n\n```bash\npython3 "{patch}" <<\'@@END@@\'\n'
                f'{example}\n@@END@@\n```\n\n`patch.py` applies them, rejects fixes it cannot find or that break the '
                f'check, and prints the result. Do not read other files. Reply only "reviewed {names}".')
    blocks, alltext = [], ''
    for n in ids:
        s = C.read(C.src_path(d, n)).strip(); o = C.read(C.out_path(d, n)).strip(); alltext += s + '\n'
        fl = flags.get(f'{n:04d}') or []
        fl_txt = ('\n\n**Flags:**\n' + '\n'.join(f'- {x}' for x in fl)) if fl else ''
        blocks.append(f'# Part {n:04d}{fl_txt}\n\n## Source {n:04d}\n\n{s}\n\n## Translation {n:04d}\n\n{o}')
    text = f"""# TASK review of parts {names} — {cfg.get('title', '')} ({lang})

{REVIEW_JOB}

{proc}

## Terms (F = fixed · P = proposed)

{table(C.present(ts, alltext))}

## Translation rules

{rules}

{chr(10).join(blocks)}
"""
    return _write(d, 'rev', ids, text)
