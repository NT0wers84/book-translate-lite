#!/usr/bin/env python3
"""AUTOMATIC translation from start to finish: translation → review → book.

Usage:  auto.py [--engine codex|claude|command] [--model M] [--parallel 3]
                [--review-engine claude] [--review full|flagged|none]
                [--until N] [--no-build] [--dir FOLDER]
        auto.py --background …   start detached (with caffeinate on macOS) and return at once
        auto.py --status         last lines of auto.log and job status

The orchestrator is this script: no model spends tokens on coordination. Each group of
parts is ONE engine call (task on stdin, answer = @@PART@@ blocks), with no tools.
Parts rejected by the check are retranslated up to `retries` times with the list of
errors; then they are accepted and flagged for the review, so the job always reaches
the end. It can be stopped and restarted at any time: it resumes where it was.
Log: auto.log in the working folder.
"""
import argparse, concurrent.futures as CF, os, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as C
import engine as EN
import review as R
import tasks as T
import work as W


class Log:
    def __init__(self, d):
        self.p = os.path.join(d, 'auto.log')

    def __call__(self, msg):
        line = time.strftime('%Y-%m-%d %H:%M ') + msg
        print(line, flush=True)
        with open(self.p, 'a', encoding='utf-8') as f:
            f.write(line + '\n')


def translate_group(d, ids, cfg, ts, rules, log):
    """Returns {n: problems} for parts accepted with problems (after the retries)."""
    problems = None
    for attempt in range(1 + cfg['retries']):
        path = T.translation(d, ids, cfg, ts, rules, mode='direct', problems=problems)
        answer, err = EN.call(cfg, C.read(path), d)
        os.remove(path)
        if err:
            log(f'  {ids[0]:04d}-{ids[-1]:04d}: engine error: {err}')
            problems = None
            continue
        saved, probs, errors = W.save_blocks(d, answer, cfg, ts, expected=ids, all_or_nothing=False)
        rest = sorted(set(n for n in ids if n not in saved) | set(probs))
        if not rest:
            return {}
        problems = {n: probs.get(n) or [e for e in errors if f'{n:04d}' in e] or ['part missing from the answer']
                    for n in rest}
        log(f'  attempt {attempt + 1}: redo ' + ', '.join(f'{n:04d}' for n in rest)
            + ' — ' + '; '.join(problems[rest[0]])[:160])
        ids = rest
    return {n: problems[n] for n in ids if C.translated(d, n)} if problems else {}


def translation_phase(d, cfg, until, log):
    g, par = cfg['group_size'], cfg['parallel']
    stalled = 0
    while True:
        missing = [n for n in range(1, until + 1) if not C.translated(d, n)]
        if not missing:
            return True
        batch = C.groups(missing[:g * par], g)
        ts = C.terms(d); rules = C.rules(d)
        t0 = time.time()
        with CF.ThreadPoolExecutor(par) as ex:
            res = list(ex.map(lambda ids: translate_group(d, ids, cfg, ts, rules, log), batch))
        flagged = {n: p for r in res for n, p in r.items()}
        W.close(d, [n for gr in batch for n in gr], C.state(d), flagged=flagged, say=log)
        log(f'{batch[0][0]:04d}-{batch[-1][-1]:04d} in {int(time.time() - t0)} s · ' + W.status_line(d))
        left = [n for n in range(1, until + 1) if not C.translated(d, n)]
        stalled = stalled + 1 if len(left) == len(missing) else 0
        if stalled >= 2:
            log('STOP: no progress in two rounds (engine unavailable or invalid answers). '
                'Check auto.log and run again.')
            return False


def review_group(d, ids, cfg, ts, rules, flags, log):
    for _ in range(2):
        path = T.review(d, ids, cfg, ts, rules, flags, mode='direct')
        answer, err = EN.call(cfg, C.read(path), d, review=True)
        os.remove(path)
        if err:
            log(f'  review {ids[0]:04d}-{ids[-1]:04d}: engine error: {err}'); continue
        ok, rejected, seen = W.apply_patches(d, answer, cfg, ts)
        if seen:
            for n, m in rejected[:5]:
                log(f'  rejected {n:04d}: {m}')
            return [n for n in seen if n in ids], ok
        log(f'  review {ids[0]:04d}-{ids[-1]:04d}: answer without @@PART@@ blocks')
    return [], 0


def review_phase(d, cfg, log):
    if cfg['review'] == 'none':
        return
    flags = R.analyze(d, log)
    stalled = 0
    while True:
        ids = R.todo(d)
        if not ids:
            return
        batch = C.groups(ids, cfg['review_group_size'])[:cfg['parallel']]
        ts = C.terms(d); rules = C.rules(d)
        with CF.ThreadPoolExecutor(cfg['parallel']) as ex:
            res = list(ex.map(lambda g: review_group(d, g, cfg, ts, rules, flags, log), batch))
        st = C.state(d)
        seen = [n for v, _ in res for n in v]
        st['reviewed'] = sorted(set(st['reviewed']) | set(seen)); C.save_state(d, st)
        log(f'review {batch[0][0]:04d}-{batch[-1][-1]:04d}: {sum(k for _, k in res)} fixes · '
            f'reviewed {len(st["reviewed"])}, to do {len(R.todo(d))}')
        stalled = 0 if seen else stalled + 1
        if stalled >= 2:
            log('STOP review: no progress in two rounds. Run auto.py again to resume.'); return


def alive(pid):
    try:
        os.kill(pid, 0); return pid > 0
    except OSError:
        return False


def running_pid(d):
    p = os.path.join(d, 'auto.pid')
    if os.path.exists(p):
        pid = int(C.read(p).strip() or 0)
        if pid != os.getpid() and alive(pid):
            return pid
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--engine'); ap.add_argument('--model'); ap.add_argument('--parallel', type=int)
    ap.add_argument('--review-engine'); ap.add_argument('--review-model')
    ap.add_argument('--review', choices=['full', 'flagged', 'none'])
    ap.add_argument('--until', type=int); ap.add_argument('--no-build', action='store_true'); ap.add_argument('--dir')
    ap.add_argument('--background', action='store_true'); ap.add_argument('--status', action='store_true')
    o = ap.parse_args(); d = C.find_dir(o.dir); cfg = C.project(d); log = Log(d)
    if o.status:
        lines = C.read(log.p).splitlines()[-8:] if os.path.exists(log.p) else []
        print('\n'.join(lines)); print(('RUNNING · ' if running_pid(d) else 'STOPPED · ') + W.status_line(d)); return
    if running_pid(d):
        sys.exit(f'auto.py is already running on this folder (pid {running_pid(d)}): use auto.py --status.')
    if o.background:
        argv = [a for a in sys.argv[1:] if a != '--background'] + ['--dir', d]
        caff = shutil.which('caffeinate')
        cmd = ([caff, '-i'] if caff else []) + [sys.executable, os.path.realpath(__file__)] + argv
        with open(os.path.join(d, 'auto.out'), 'a') as out:
            pr = subprocess.Popen(cmd, stdout=out, stderr=out, stdin=subprocess.DEVNULL, start_new_session=True, cwd=d)
        print(f'Started in the background (pid {pr.pid}). Status: auto.py --status · log: {log.p}'); return
    C.write(os.path.join(d, 'auto.pid'), str(os.getpid()))
    for k, v in {'engine': o.engine, 'model': o.model, 'parallel': o.parallel, 'review': o.review,
                 'review_engine': o.review_engine, 'review_model': o.review_model}.items():
        if v:
            cfg[k] = v
    tot = C.n_parts(d); until = min(o.until or tot, tot)
    if not EN.available(cfg):
        sys.exit(f'ERROR: engine "{cfg["engine"]}" not available. Use --engine or the in-chat mode (step.py).')
    log(f'START {cfg.get("title", "")} → {cfg["target_lang_name"]}: engine {cfg["engine"]} {cfg.get("model", "")}, '
        f'groups of {cfg["group_size"]}, {cfg["parallel"]} in parallel, review {cfg["review"]} · ' + W.status_line(d))
    if not translation_phase(d, cfg, until, log):
        sys.exit(1)
    if until < tot:
        log(f'Stopped at part {until:04d} as requested.'); return
    if cfg['review'] != 'none' and not EN.available(cfg, review=True):
        sys.exit(f'ERROR: review engine "{cfg["review_engine"]}" not available.')
    review_phase(d, cfg, log)
    if o.no_build:
        R.analyze(d, log); log('Translation and review complete (build skipped).'); return
    R.final(d, log)


if __name__ == '__main__':
    main()
