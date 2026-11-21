"""Shared helpers for every book-translate-lite script.

Working folder (<book>_temp/):
  chunkNNNN.md                 source parts
  output_chunkNNNN.md          translated parts
  output_chunkNNNN.meta.json   per-part metadata from the model (new terms, conflicts)
  project.json                 settings (target language, group size, engines, typography…)
  rules.md                     translation rules (copied into every task)
  terms.json                   glossary: [{source, target, type: fixed|proposed, note, aliases}]
  candidates.json              recurring names found in the source, not yet in the glossary
  state.json                   {"done": [...], "meta_merged": [...], "reviewed": [...], ...}
  _tasks/                      temporary tasks for sub-agents
  review/                      final review: flags, report, applied fixes, backups
"""
import glob, json, os, re, sys

SCRIPTS = os.path.dirname(os.path.realpath(__file__))
SKILL = os.path.dirname(SCRIPTS)
TEMPLATES = os.path.join(SKILL, 'templates')

DEFAULT = {
    'source_lang': 'en', 'target_lang': '', 'target_lang_name': '',
    'title': '', 'author': '', 'source': '',
    'subtitle': '', 'rights': '',   # title page: e.g. series/volume line, a note such as "personal use only"
    'group_size': 3, 'parallel': 3, 'retries': 2, 'timeout_minutes': 20,
    'tail_chars': 600, 'ratio_min': 0.6, 'ratio_max': 1.9,
    # typography (filled from templates/languages.json at init)
    'quotes': '“”', 'typographic_apostrophe': True, 'punct_outside_quotes': False,
    'replacements': [],     # [{"re": "\\bOkay\\b", "with": "Ok"}]  applied automatically on save
    'forbidden': [],        # [{"re": "...", "msg": "..."}]           blocking errors
    'genre': 'fiction',     # templates/genres/<genre>.md, appended to rules.md
    'system_boxes': None,   # box bold-only paragraphs (system messages); None = only for genre gamelit
    'uppercase_chat': [],   # names whose chat lines "Name: ..." must be ALL CAPS
    # automatic mode (auto.py)
    'engine': 'codex',      # codex | claude | command
    'engine_command': [],   # for engine = command: argv; task on stdin, answer on stdout
    'model': '', 'reasoning': 'low',
    'review_engine': '', 'review_model': '', 'review_reasoning': 'medium',
    # final review
    'review': 'full',       # full | flagged | none
    'review_group_size': 3,
    'formats': 'epub,docx,pdf',
}

B = r"(?<![\w’'])"   # word boundaries that respect apostrophes
E = r"(?![\w’'])"


def find_dir(argdir=None):
    d = os.path.abspath(argdir or os.getcwd())
    while True:
        if os.path.exists(os.path.join(d, 'project.json')):
            return d
        if os.path.exists(os.path.join(d, 'progetto.json')):
            sys.exit('ERROR: this is a version 1 project. Run: python3 '
                     f'{os.path.join(SCRIPTS, "migrate.py")} "{d}"')
        up = os.path.dirname(d)
        if up == d:
            sys.exit('ERROR: project.json not found (run inside <book>_temp/ or pass --dir).')
        d = up


def arg_dir():
    return sys.argv[sys.argv.index('--dir') + 1] if '--dir' in sys.argv else None


def jload(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def jsave(path, obj):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def write(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)


def languages():
    return jload(os.path.join(TEMPLATES, 'languages.json'), {})


def project(d):
    p = dict(DEFAULT)
    p.update(jload(os.path.join(d, 'project.json'), {}))
    return p


def terms(d):
    return jload(os.path.join(d, 'terms.json'), [])


def state(d):
    s = jload(os.path.join(d, 'state.json'), {}) or {}
    for k, v in (('done', []), ('meta_merged', []), ('reviewed', []), ('flagged', {}),
                 ('fixed_conflicts', []), ('attempts', {})):
        s.setdefault(k, v)
    return s


def save_state(d, s):
    jsave(os.path.join(d, 'state.json'), s)


def rules(d):
    return read(os.path.join(d, 'rules.md')).strip()


def src_path(d, n):
    return os.path.join(d, f'chunk{n:04d}.md')


def out_path(d, n):
    return os.path.join(d, f'output_chunk{n:04d}.md')


def meta_path(d, n):
    return os.path.join(d, f'output_chunk{n:04d}.meta.json')


def n_parts(d):
    return len(glob.glob(os.path.join(d, 'chunk[0-9][0-9][0-9][0-9].md')))


def translated(d, n):
    p = out_path(d, n)
    return os.path.exists(p) and os.path.getsize(p) > 0 and bool(read(p).strip())


def next_missing(d):
    return next((i for i in range(1, n_parts(d) + 1) if not translated(d, i)), None)


def paragraphs(t):
    return [p for p in re.split(r'\n\s*\n', t.strip()) if p.strip()]


def forms(t):
    return [f for f in [t['source']] + list(t.get('aliases', [])) if f]


def letter(t):
    return 'F' if t.get('type') == 'fixed' else 'P'


_RX = {}


def rx_term(f):
    if f not in _RX:
        _RX[f] = re.compile(B + re.escape(f) + E)
    return _RX[f]


def present(ts, text):
    return [t for t in ts if any(rx_term(f).search(text) for f in forms(t))]


GENRES = ('fiction', 'nonfiction', 'technical', 'children', 'poetry', 'gamelit', 'general')


def genre_rules(genre, lang_name):
    """The '## Genre: …' section for rules.md (templates/genres/<genre>.md)."""
    p = os.path.join(TEMPLATES, 'genres', f'{genre}.md')
    if not os.path.exists(p):
        raise SystemExit(f'Unknown genre "{genre}". Available: ' + ', '.join(GENRES))
    return read(p).strip().replace('{language}', lang_name)


def set_genre(rules, section):
    """Replace (or append) the genre section of a rules.md text."""
    rx = re.compile(r'(?ms)^## Genre:.*?(?=^## (?!Genre:)|\Z)')
    if rx.search(rules):
        return rx.sub(section.rstrip() + '\n\n', rules, count=1).rstrip() + '\n'
    return rules.rstrip() + '\n\n' + section.rstrip() + '\n'


def bare(text):
    """Text without Markdown, images, links, URLs and {attributes}: what a translator would translate."""
    t = re.sub(r'!\[[^\]]*\]\([^)]*\)|\]\([^)]*\)|\{[^}]*\}|https?://\S+', ' ', text)
    return re.sub(r'[*_#>\[\]|`~\\]', ' ', t).strip()


def nothing_to_translate(text, cfg=None):
    """True for parts/paragraphs that legitimately stay identical: only links/images/markup, or only the
    author's name."""
    b = ' '.join(bare(text).split())
    if not re.search(r'[^\W\d_]', b):
        return True
    author = ' '.join(((cfg or {}).get('author') or '').split())
    return bool(author) and b.lower() == author.lower()


def rendered(target, text_lower):
    """Is a glossary rendering present, allowing inflection (Maestro/Maestra, -o/-i/-a/-e)?
    Every word of 4+ letters must appear by its stem (the word minus its last 2 letters)."""
    tc = re.sub(r'\s*\(.*?\)', '', target).lower()
    words = [w for w in re.findall(r'[^\W\d_]+', tc) if len(w) >= 4]
    if not words:
        return tc in text_lower if tc.strip() else True
    return all(w[:max(3, len(w) - 2)] in text_lower for w in words)


def generic(term):
    """Single lowercase common words (phase, blob, outworlder): their translation depends on context, so
    they are not checked for consistency."""
    s = term['source']
    return ' ' not in s.strip() and s[:1].islower()


def kept_name(src, out, source):
    """Is every occurrence of `src` in `out` part of a longer proper name kept as it is in the source
    (“Pride” inside “Pride and Prejudice”, “Moon” inside “Blue Moon Tavern”)?"""
    tok = r"[A-Z][\w’'\-]*"
    conn = r"(?:and|&|of|the|de|du|von|van)"
    rx = re.compile(rf"(?:(?:{tok}|{conn})\s+)*" + re.escape(src) + rf"(?:\s+(?:{tok}|{conn}))*")
    hits = list(rx_term(src).finditer(out))
    if not hits:
        return False
    for m in hits:
        ok = False
        for big in rx.finditer(out):
            if big.start() <= m.start() and big.end() >= m.end():
                phrase = big.group(0).strip()
                phrase = re.sub(rf"^(?:{conn}\s+)+|(?:\s+{conn})+$", '', phrase)
                ok = phrase != src and len(phrase.split()) > len(src.split()) and phrase in source
                break
        if not ok:
            return False
    return True


def groups(ids, g):
    """Runs of consecutive part numbers, at most g per group."""
    out = []
    for n in ids:
        if out and len(out[-1]) < g and out[-1][-1] == n - 1:
            out[-1].append(n)
        else:
            out.append([n])
    return out


# ---------- mechanical fixes (save.py, patch.py, check.py --fix) ----------

def _outside_markup(text, fn):
    """Apply fn only outside {attributes}, ](links) and `code`."""
    pieces = re.split(r'(\{[^}\n]*\}|\]\([^)\n]*\)|`[^`\n]*`)', text)
    total = 0
    for k in range(0, len(pieces), 2):
        pieces[k], c = fn(pieces[k]); total += c
    return ''.join(pieces), total


def fix(text, cfg):
    def fn(s):
        n = 0
        if cfg.get('typographic_apostrophe'):
            s, c = re.subn(r"(?<=[A-Za-zÀ-ÿ])'", '’', s); n += c
        if cfg.get('punct_outside_quotes') and cfg.get('quotes') == '«»':
            s, c = re.subn(r'([?!…])\.»', r'\1»', s); n += c       # «Really?.» -> «Really?»
            s, c = re.subn(r'([?!])»\.', r'\1»', s); n += c         # «Really?». -> «Really?»
            s, c = re.subn(r'(?<![.\s])\.»', '».', s); n += c       # «Hello.» -> «Hello».
        for r in cfg.get('replacements', []):
            s, c = re.subn(r['re'], r.get('with', r.get('con', '')), s); n += c
        return s, n
    return _outside_markup(text, fn)
