"""Core operations shared by save.py, patch.py, finish.py, auto.py and step.py."""
import glob, json, os, re, shutil
import common as C
from check import check

PART = r'^[ \t]*@@(?:PART|PARTE) (\d{1,4})@@[ \t]*$'
END = r'\n@@(?:END|FINE)@@.*$'


# ---------------------------------------------------------------- translation

def parse_blocks(raw):
    """@@PART NNNN@@ text @@META@@ {json} … → [(n, text, meta)], errors."""
    raw = raw.replace('\r\n', '\n')
    if raw.strip().startswith('```'):
        raw = re.sub(r'^```[a-z]*\n|\n```\s*$', '', raw.strip())
    pieces = re.split(PART, raw, flags=re.M)
    items, errors = [], []
    for k in range(1, len(pieces), 2):
        n = int(pieces[k]); body = re.sub(END, '', pieces[k + 1], flags=re.S)
        text, meta_raw = (body.split('@@META@@', 1) + [''])[:2]
        text = text.strip('\n') + '\n'
        meta = {'new_entities': [], 'conflicts': []}
        if meta_raw.strip():
            m = re.search(r'\{.*\}', meta_raw, re.S)
            try:
                meta.update(json.loads(m.group(0) if m else meta_raw))
            except (json.JSONDecodeError, AttributeError) as e:
                errors.append(f'META of part {n:04d} is not valid JSON ({e})')
                continue
        if len(text.strip()) < 2:
            errors.append(f'empty text for part {n:04d}')
            continue
        items.append((n, text, meta))
    return items, errors


def save_blocks(d, raw, cfg, ts, expected=None, all_or_nothing=True):
    """Save the parts. Returns (saved, problems{n: [...]}, errors)."""
    items, errors = parse_blocks(raw)
    for n, _, _ in items:
        if not os.path.exists(C.src_path(d, n)):
            errors.append(f'part {n:04d} does not exist')
    if expected:
        got = {n for n, _, _ in items}
        errors += [f'part {n:04d} missing from the answer' for n in expected if n not in got]
    if errors and all_or_nothing:
        return [], {}, errors
    saved, problems = [], {}
    for n, text, meta in items:
        if not os.path.exists(C.src_path(d, n)) or (expected and n not in expected):
            continue
        text, _ = C.fix(text, cfg)
        C.write(C.out_path(d, n), text)
        C.jsave(C.meta_path(d, n), meta)
        saved.append(n)
        p, _w = check(d, n, cfg, ts)
        if p:
            problems[n] = p
    return saved, problems, errors


# ---------------------------------------------------------------- review

def parse_patches(raw):
    """@@PART NNNN@@ (@@OLD@@ … @@NEW@@ …)* or @@OK@@ → {n: [(old, new)]}."""
    raw = raw.replace('\r\n', '\n')
    pieces = re.split(PART, raw, flags=re.M)
    out = {}
    for k in range(1, len(pieces), 2):
        n = int(pieces[k]); body = re.sub(END, '', pieces[k + 1], flags=re.S)
        lst = out.setdefault(n, [])
        for m in re.finditer(r'@@(?:OLD|VECCHIO)@@\n(.*?)\n@@(?:NEW|NUOVO)@@\n(.*?)(?=\n@@(?:OLD|VECCHIO)@@|\n@@OK@@|\Z)',
                             body, re.S):
            old, new = m.group(1), m.group(2).rstrip('\n')
            if old.strip() and old != new:
                lst.append((old, new))
    return out


def apply_patches(d, raw, cfg, ts):
    """Apply review fixes; a fix that breaks the check is undone.
    Returns (applied, rejected[(n, reason)], parts_seen)."""
    bk = os.path.join(d, 'review', 'backup'); os.makedirs(bk, exist_ok=True)
    applied, rejected = 0, []
    patches = parse_patches(raw)
    for n, lst in patches.items():
        if not C.translated(d, n):
            rejected.append((n, 'part not translated')); continue
        p = C.out_path(d, n)
        if not os.path.exists(os.path.join(bk, os.path.basename(p))):
            shutil.copy2(p, bk)
        ok_before = not check(d, n, cfg, ts)[0]; done = []
        for old, new in lst:
            t = C.read(p)
            if t.count(old) != 1:
                rejected.append((n, f'text to replace found {t.count(old)} times: «{old[:50]}»')); continue
            new, _ = C.fix(new, cfg)
            C.write(p, t.replace(old, new))
            if ok_before and check(d, n, cfg, ts)[0]:
                C.write(p, t)
                rejected.append((n, f'the fix breaks the check: «{old[:50]}»')); continue
            applied += 1; done.append((old, new))
        if done:
            with open(os.path.join(d, 'review', 'changes.md'), 'a', encoding='utf-8') as f:
                for old, new in done:
                    f.write(f'- {n:04d}: «{old[:120]}» → «{new[:120]}»\n')
    return applied, rejected, sorted(patches)


# ---------------------------------------------------------------- closing

def merge_meta(d, ids, st, say=print):
    ts = C.terms(d); idx = {}
    for t in ts:
        for f in C.forms(t):
            idx.setdefault(f.lower(), t)
    new, changed, fixed_conf = [], [], []
    for n in ids:
        if n in st['meta_merged']:
            continue
        meta = C.jload(C.meta_path(d, n), {}) or {}
        for e in meta.get('new_entities', []) or []:
            if not isinstance(e, dict):
                continue
            src = (e.get('source') or '').strip(); tgt = (e.get('target_proposal') or e.get('target') or '').strip()
            if not src or not tgt or src.lower() in idx:
                continue
            t = {'source': src, 'target': tgt, 'type': 'proposed',
                 'note': (e.get('category') or '') + f' (part {n:04d})', 'aliases': []}
            ts.append(t); idx[src.lower()] = t; new.append(f'{src}={tgt}')
        for c in meta.get('conflicts', []) or []:
            if not isinstance(c, dict):
                continue
            src = (c.get('source') or '').strip(); prop = (c.get('proposed_target') or '').strip()
            t = idx.get(src.lower())
            if not t or not prop or prop == t['target']:
                continue
            if t.get('type') == 'fixed':
                fixed_conf.append({'part': n, 'source': src, 'current': t['target'], 'proposed': prop,
                                   'reason': (c.get('reason') or '')[:120]})
                continue
            t['note'] = (t.get('note', '') + f' · was: {t["target"]}').strip(' ·')
            t['target'] = prop; changed.append(f'{src}={prop}')
        st['meta_merged'].append(n)
    if new or changed:
        C.jsave(os.path.join(d, 'terms.json'), ts)
    if fixed_conf:
        st['fixed_conflicts'].extend(fixed_conf)
    if new:
        say(f'glossary: +{len(new)} proposed terms: ' + '; '.join(new)[:300])
    if changed:
        say('glossary: proposed renderings changed: ' + '; '.join(changed)[:300])
    for x in fixed_conf:
        say(f'CONFLICT ON FIXED TERM (noted in state.json): {x["source"]}: «{x["current"]}» → «{x["proposed"]}»')


def close(d, ids, st, flagged=None, say=print):
    """Record translated parts, merge meta into the glossary, delete finished tasks."""
    done = [n for n in ids if C.translated(d, n)]
    st['done'] = sorted(set(st['done']) | set(done))
    for n, probs in (flagged or {}).items():
        st['flagged'][f'{n:04d}'] = probs
    for n in done:
        if not flagged or n not in flagged:
            st['flagged'].pop(f'{n:04d}', None)
    merge_meta(d, done, st, say)
    st['meta_merged'] = sorted(set(st['meta_merged']))
    C.save_state(d, st)
    for f in glob.glob(os.path.join(d, '_tasks', 'task_*.md')):
        nums = [int(x) for x in re.findall(r'\d{4}', os.path.basename(f))]
        if nums and all(n in st['done'] for n in range(nums[0], nums[-1] + 1)):
            os.remove(f)


def status_line(d, st=None):
    st = st or C.state(d); tot = C.n_parts(d); nx = C.next_missing(d)
    done = sum(1 for i in range(1, tot + 1) if C.translated(d, i))
    s = f'STATUS: {done}/{tot} translated, {len(st["done"])} recorded'
    if st['flagged']:
        s += f', {len(st["flagged"])} flagged for review'
    return s + '. Next: ' + (f'{nx:04d}' if nx else 'none (translation complete)')
