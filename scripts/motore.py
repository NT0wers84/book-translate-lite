"""Chiamata non interattiva di un modello: il task va su stdin, torna il testo della risposta.

Motori:
  codex   → `codex exec` (sandbox read-only, sessione effimera, nessuno strumento necessario)
  claude  → `claude -p` (Claude Code in modalità stampa)
  comando → progetto.json "comando_motore": argv qualsiasi (stdin = task, stdout = risposta)
"""
import glob, os, shutil, subprocess, tempfile

CODEX = ['/Applications/Codex.app/Contents/Resources/codex',
         '/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex',
         os.path.expanduser('~/.local/bin/codex'), '/opt/homebrew/bin/codex', '/usr/local/bin/codex']
CLAUDE = [os.path.expanduser('~/.claude/local/claude'), os.path.expanduser('~/.local/bin/claude'),
          '/opt/homebrew/bin/claude', '/usr/local/bin/claude']


def trova(nome):
    cands = [os.environ.get(f'BTL_{nome.upper()}', ''), shutil.which(nome) or ''] + (CODEX if nome == 'codex' else CLAUDE)
    return next((c for c in cands if c and os.path.exists(c)), None)


def disponibile(cfg, revisione=False):
    m = (cfg.get('motore_revisione') if revisione else '') or cfg['motore']
    if m == 'comando':
        return bool(cfg.get('comando_motore'))
    return trova(m) is not None


def chiama(cfg, testo, d, revisione=False):
    """Ritorna (risposta, errore)."""
    m = (cfg.get('motore_revisione') if revisione else '') or cfg['motore']
    modello = (cfg.get('modello_revisione') if revisione else '') or cfg.get('modello', '')
    rag = cfg.get('ragionamento_revisione' if revisione else 'ragionamento') or ''
    timeout = int(cfg.get('timeout_minuti', 20)) * 60
    out = None
    try:
        if m == 'codex':
            exe = trova('codex')
            if not exe:
                return '', 'codex non trovato (installa la CLI o imposta BTL_CODEX)'
            fd, out = tempfile.mkstemp(suffix='.txt'); os.close(fd)
            cmd = [exe, 'exec', '--skip-git-repo-check', '--ephemeral', '-s', 'read-only', '-C', d, '-o', out]
            if modello:
                cmd += ['-m', modello]
            if rag:
                cmd += ['-c', f'model_reasoning_effort="{rag}"']
            r = subprocess.run(cmd + ['-'], input=testo, capture_output=True, text=True, timeout=timeout)
            risposta = open(out, encoding='utf-8').read() if os.path.exists(out) else ''
        elif m == 'claude':
            exe = trova('claude')
            if not exe:
                return '', 'claude non trovato (installa Claude Code o imposta BTL_CLAUDE)'
            cmd = [exe, '-p', '--output-format', 'text'] + (['--model', modello] if modello else [])
            r = subprocess.run(cmd, input=testo, capture_output=True, text=True, timeout=timeout, cwd=d)
            risposta = r.stdout
        elif m == 'comando':
            r = subprocess.run(cfg['comando_motore'], input=testo, capture_output=True, text=True, timeout=timeout, cwd=d)
            risposta = r.stdout
        else:
            return '', f'motore sconosciuto: {m}'
        if r.returncode and not risposta.strip():
            return '', f'{m} è uscito con codice {r.returncode}: {(r.stderr or r.stdout)[-300:].strip()}'
        return risposta, ''
    except subprocess.TimeoutExpired:
        return '', f'{m}: tempo scaduto ({timeout // 60} min)'
    finally:
        if out and os.path.exists(out):
            os.remove(out)
