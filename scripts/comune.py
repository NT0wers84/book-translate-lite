"""Funzioni condivise da tutti gli script di book-translate-lite.

Cartella di lavoro (<libro>_temp/):
  chunkNNNN.md                 parti originali
  output_chunkNNNN.md          parti tradotte
  output_chunkNNNN.meta.json   meta del sotto-agente (termini nuovi, conflitti)
  progetto.json                configurazione
  regole.md                    regole di traduzione (copiate in ogni task)
  glossario.json               [{source, target, tipo V|P, nota, alias}]
  preglossario.json            nomi ricorrenti candidati (senza resa)
  stato.json                   {"fatte": [...], "meta_integrati": [...]}
  _task/                       task temporanei per i sotto-agenti
"""
import glob, json, os, re, sys

SCRIPTS = os.path.dirname(os.path.realpath(__file__))
SKILL = os.path.dirname(SCRIPTS)

DEFAULT = {
    'lingua': 'it', 'lingua_nome': 'italiano', 'gruppo': 3, 'max_gruppi_sessione': 5,
    'virgolette': '«»', 'apostrofo_tipografico': True, 'punto_fuori': True,
    'coda_continuita': 600, 'rapporto_min': 0.6, 'rapporto_max': 1.9,
    'sostituzioni': [],      # [{"re": "\\bOkay\\b", "con": "Ok"}]  correzioni automatiche
    'vietate': [],           # [{"re": "...", "msg": "..."}]        errori bloccanti
    'maiuscolo_chat': [],    # nomi che in chat scrivono TUTTO MAIUSCOLO
    'titolo': '', 'autore': '', 'sorgente': '',
    # automatico (auto.py)
    'motore': 'codex',           # codex | claude | comando
    'comando_motore': [],        # per motore = comando: argv; il task arriva su stdin, la risposta su stdout
    'modello': '', 'ragionamento': 'low',
    'motore_revisione': '', 'modello_revisione': '', 'ragionamento_revisione': 'medium',
    'paralleli': 3, 'tentativi': 2, 'timeout_minuti': 20,
    # revisione finale
    'revisione': 'completa',     # completa | segnalate | nessuna
    'gruppo_revisione': 3,
    'formati': 'epub,docx,pdf',
}

B = r"(?<![\w’'])"   # confini di parola che rispettano gli apostrofi
E = r"(?![\w’'])"


def trova_dir(argdir=None):
    d = os.path.abspath(argdir or os.getcwd())
    while True:
        if os.path.exists(os.path.join(d, 'progetto.json')):
            return d
        up = os.path.dirname(d)
        if up == d:
            sys.exit('ERRORE: progetto.json non trovato (lancia lo script dentro <libro>_temp/ o usa --dir).')
        d = up


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


def progetto(d):
    p = dict(DEFAULT)
    p.update(jload(os.path.join(d, 'progetto.json'), {}))
    return p


def glossario(d):
    return jload(os.path.join(d, 'glossario.json'), [])


def stato(d):
    s = jload(os.path.join(d, 'stato.json'), {}) or {}
    s.setdefault('fatte', []); s.setdefault('meta_integrati', [])
    s.setdefault('da_rivedere', {})      # "NNNN": [problemi rimasti dopo i tentativi]
    s.setdefault('rivedute', [])         # parti passate dalla revisione finale
    s.setdefault('conflitti_v', [])      # proposte di cambio su termini vincolanti
    return s


def salva_stato(d, s):
    jsave(os.path.join(d, 'stato.json'), s)


def leggi(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def src_path(d, n):
    return os.path.join(d, f'chunk{n:04d}.md')


def out_path(d, n):
    return os.path.join(d, f'output_chunk{n:04d}.md')


def meta_path(d, n):
    return os.path.join(d, f'output_chunk{n:04d}.meta.json')


def n_parti(d):
    return len(glob.glob(os.path.join(d, 'chunk[0-9][0-9][0-9][0-9].md')))


def tradotta(d, n):
    p = out_path(d, n)
    return os.path.exists(p) and os.path.getsize(p) > 0 and bool(leggi(p).strip())


def prossima(d):
    return next((i for i in range(1, n_parti(d) + 1) if not tradotta(d, i)), None)


def paragrafi(t):
    return [p for p in re.split(r'\n\s*\n', t.strip()) if p.strip()]


def forme(t):
    return [f for f in [t['source']] + list(t.get('alias', [])) if f]


_RX = {}


def rx_term(f):
    if f not in _RX:
        _RX[f] = re.compile(B + re.escape(f) + E)
    return _RX[f]


def presenti(terms, testo):
    return [t for t in terms if any(rx_term(f).search(testo) for f in forme(t))]


# ---------- correzioni meccaniche (save.py e check.py --fix) ----------

def _fuori_markup(testo, fn):
    """Applica fn solo al testo fuori da {attributi}, ](link) e `codice`."""
    pezzi = re.split(r'(\{[^}\n]*\}|\]\([^)\n]*\)|`[^`\n]*`)', testo)
    tot = 0
    for k in range(0, len(pezzi), 2):
        pezzi[k], c = fn(pezzi[k]); tot += c
    return ''.join(pezzi), tot


def correggi(testo, cfg):
    def fn(s):
        n = 0
        if cfg.get('apostrofo_tipografico'):
            s, c = re.subn(r"(?<=[A-Za-zÀ-ÿ])'", '’', s); n += c
        if cfg.get('punto_fuori') and cfg.get('virgolette') == '«»':
            s, c = re.subn(r'([?!…])\.»', r'\1»', s); n += c       # «Davvero?.» -> «Davvero?»
            s, c = re.subn(r'([?!])»\.', r'\1»', s); n += c         # «Davvero?». -> «Davvero?»
            s, c = re.subn(r'(?<![.\s])\.»', '».', s); n += c       # «Ciao.» -> «Ciao».
        for r in cfg.get('sostituzioni', []):
            s, c = re.subn(r['re'], r['con'], s); n += c
        return s, n
    return _fuori_markup(testo, fn)
