"""Non-interactive model call: the task goes to stdin, the answer text comes back.

Engines:
  codex   → `codex exec` (read-only sandbox, ephemeral session, no tools needed)
  claude  → `claude -p` (Claude Code print mode)
  command → project.json "engine_command": any argv (stdin = task, stdout = answer)
Binaries can be forced with the BTL_CODEX / BTL_CLAUDE environment variables.
"""
import os, re, shutil, subprocess, tempfile

# the engine cannot work until the user acts (credits, plan limits, login): stop at once, do not retry
QUOTA = re.compile(r'out of credits|add credits|usage limit|limit reached|hit your .{0,20}limit|quota|'
                   r'insufficient[_ ](?:quota|credit|funds)|billing|rate[_ ]limit|\b429\b|not logged in|'
                   r'please (?:log|sign) in|authentication|unauthorized', re.I)


class EngineBlocked(Exception):
    """Raised by callers when an engine error needs the user (credits, limits, login)."""


def blocked(err):
    return bool(err) and bool(QUOTA.search(err))


def hint(cfg):
    other = 'claude' if cfg.get('engine') == 'codex' else 'codex'
    alt = f'btl resume --engine {other}' if find(other) else 'btl next (in-chat mode)'
    return f'Add credits / wait for the limit to reset, then btl resume — or switch: {alt}'

CODEX = ['/Applications/Codex.app/Contents/Resources/codex',
         '/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex',
         os.path.expanduser('~/.local/bin/codex'), '/opt/homebrew/bin/codex', '/usr/local/bin/codex']
CLAUDE = [os.path.expanduser('~/.claude/local/claude'), os.path.expanduser('~/.local/bin/claude'),
          '/opt/homebrew/bin/claude', '/usr/local/bin/claude']


def find(name):
    cands = [os.environ.get(f'BTL_{name.upper()}', ''), shutil.which(name) or ''] + (CODEX if name == 'codex' else CLAUDE)
    return next((c for c in cands if c and os.path.exists(c)), None)


def _pick(cfg, review):
    return (cfg.get('review_engine') if review else '') or cfg['engine']


def available(cfg, review=False):
    e = _pick(cfg, review)
    if e == 'command':
        return bool(cfg.get('engine_command'))
    return find(e) is not None


def call(cfg, text, d, review=False):
    """Returns (answer, error)."""
    e = _pick(cfg, review)
    model = (cfg.get('review_model') if review else '') or cfg.get('model', '')
    effort = cfg.get('review_reasoning' if review else 'reasoning') or ''
    timeout = int(cfg.get('timeout_minutes', 20)) * 60
    out = None
    try:
        if e == 'codex':
            exe = find('codex')
            if not exe:
                return '', 'codex not found (install the CLI or set BTL_CODEX)'
            fd, out = tempfile.mkstemp(suffix='.txt'); os.close(fd)
            cmd = [exe, 'exec', '--skip-git-repo-check', '--ephemeral', '-s', 'read-only', '-C', d, '-o', out]
            if model:
                cmd += ['-m', model]
            if effort:
                cmd += ['-c', f'model_reasoning_effort="{effort}"']
            r = subprocess.run(cmd + ['-'], input=text, capture_output=True, text=True, timeout=timeout)
            answer = open(out, encoding='utf-8').read() if os.path.exists(out) else ''
        elif e == 'claude':
            exe = find('claude')
            if not exe:
                return '', 'claude not found (install Claude Code or set BTL_CLAUDE)'
            cmd = [exe, '-p', '--output-format', 'text'] + (['--model', model] if model else [])
            r = subprocess.run(cmd, input=text, capture_output=True, text=True, timeout=timeout, cwd=d)
            answer = r.stdout
        elif e == 'command':
            r = subprocess.run(cfg['engine_command'], input=text, capture_output=True, text=True, timeout=timeout, cwd=d)
            answer = r.stdout
        else:
            return '', f'unknown engine: {e}'
        if r.returncode and not answer.strip():
            return '', f'{e} exited with code {r.returncode}: {(r.stderr or r.stdout)[-300:].strip()}'
        return answer, ''
    except subprocess.TimeoutExpired:
        return '', f'{e}: timed out ({timeout // 60} min)'
    finally:
        if out and os.path.exists(out):
            os.remove(out)
