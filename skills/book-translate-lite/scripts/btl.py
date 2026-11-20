#!/usr/bin/env python3
"""btl — one command for the whole book-translate-lite workflow.

  btl start BOOK --to LANG [--from LANG] [--title "…"] [--engine codex|claude] [--review-engine claude]
                                         [--review full|flagged|none] [--chat] [--no-start]
                                         set up the book and start translating until the book is done
  btl status [JOB]                       progress of one job, or of every job
  btl next [JOB]                         in-chat mode: what to do now (prints sub-agent prompts)
  btl stop [JOB]                         stop the automatic run (it can be resumed)
  btl resume [JOB] [--engine …]          resume the automatic run where it stopped
  btl review [JOB] [--again] [--flagged] [--engine …]
                                         run (or rerun) the final review, then rebuild the book
  btl build [JOB] [--formats epub,docx,pdf] [--title "…"] [--partial]
  btl check [JOB]                        automatic checks on every translated part
  btl log [JOB] [-n 20]                  last lines of the automatic run log
  btl config [--job JOB] [KEY=VALUE …]   show or change project settings (title, engine, review, …)
  btl terms [--job JOB] list [TEXT] | add SOURCE TARGET [--proposed] [--note …] | remove SOURCE
  btl import FOLDER [--to LANG]          import a translate-book / v1 project
  btl jobs                               list known jobs
  btl doctor                             check that everything needed is installed

JOB can be a book file, its <book>_temp folder, or part of the title. Without JOB, btl uses
the project of the current folder, otherwise the most recent job.
"""
import argparse, json, os, shutil, signal, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as C
import engine as EN

HOME = os.environ.get('BTL_HOME') or os.path.expanduser('~/.book-translate-lite')
JOBS = os.path.join(HOME, 'jobs.json')


def script(name):
    return os.path.join(C.SCRIPTS, name)


def run(name, *args, capture=False):
    cmd = [sys.executable, script(name)] + [str(a) for a in args]
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True)
    return subprocess.run(cmd)


def die(msg, code=1):
    print(msg, file=sys.stderr); sys.exit(code)


# ------------------------------------------------------------------ jobs registry

def jobs():
    js = C.jload(JOBS, {}) or {}
    return {d: v for d, v in js.items() if os.path.exists(os.path.join(d, 'project.json'))}


def register(d):
    os.makedirs(HOME, exist_ok=True)
    js = C.jload(JOBS, {}) or {}
    cfg = C.project(d)
    js[d] = {'title': cfg.get('title', ''), 'to': cfg.get('target_lang', ''), 'added': js.get(d, {}).get(
        'added', time.strftime('%Y-%m-%d %H:%M'))}
    C.jsave(JOBS, js)


def touched(d):
    return max((os.path.getmtime(os.path.join(d, f)) for f in ('state.json', 'auto.log', 'project.json')
                if os.path.exists(os.path.join(d, f))), default=0)


def project_of(path):
    path = os.path.abspath(os.path.expanduser(path))
    if os.path.isfile(path):
        d = os.path.join(os.path.dirname(path), os.path.splitext(os.path.basename(path))[0] + '_temp')
        return d if os.path.exists(os.path.join(d, 'project.json')) else None
    while path != os.path.dirname(path):
        if os.path.exists(os.path.join(path, 'project.json')):
            return path
        path = os.path.dirname(path)
    return None


def resolve(target=None):
    if target:
        d = project_of(target)
        if d:
            return d
        hits = [d for d, v in jobs().items() if target.lower() in (v.get('title', '') + ' ' + d).lower()]
        if len(hits) == 1:
            return hits[0]
        if hits:
            die('More than one job matches "%s":\n  ' % target + '\n  '.join(hits))
        die(f'No job found for "{target}". Known jobs: btl jobs')
    d = project_of(os.getcwd())
    if d:
        return d
    js = list(jobs())
    if not js:
        die('No translation job yet. Start one with: btl start BOOK --to LANG')
    return max(js, key=touched)


# ------------------------------------------------------------------ status

def pid_alive(d):
    p = os.path.join(d, 'auto.pid')
    if not os.path.exists(p):
        return None
    try:
        pid = int(C.read(p).strip() or 0)
        os.kill(pid, 0)
        return pid
    except (ValueError, OSError):
        return None


def summary(d, verbose=True):
    cfg = C.project(d); st = C.state(d); tot = C.n_parts(d)
    done = sum(1 for n in range(1, tot + 1) if C.translated(d, n))
    running = pid_alive(d)
    if done < tot:
        phase = f'translating {done}/{tot} ({100 * done // max(tot, 1)}%)'
    elif st.get('finished'):
        phase = 'FINISHED'
    elif cfg['review'] == 'none':
        phase = 'translated, book not built yet'
    else:
        import review as R
        phase = f'reviewing {len(st["reviewed"])}/{len(st["reviewed"]) + len(R.todo(d))}'
    bar_n = int(20 * done / max(tot, 1))
    lines = [f'{cfg.get("title") or os.path.basename(d)}  ({cfg.get("source_lang", "?")} → {cfg.get("target_lang")})',
             f'  phase:   {phase}  [{"#" * bar_n}{"." * (20 - bar_n)}]  · '
             + ('running' if running else 'stopped')]
    if verbose:
        lines.insert(1, f'  folder:  {d}')
        if st['flagged'] or st['fixed_conflicts']:
            lines.append(f'  flags:   {len(st["flagged"])} parts flagged for review · '
                         f'{len(st["fixed_conflicts"])} proposed changes to fixed terms')
        log = os.path.join(d, 'auto.log')
        if os.path.exists(log):
            last = C.read(log).strip().splitlines()[-1:]
            if last:
                lines.append(f'  last:    {last[0][:150]}')
        book = sorted(f for f in os.listdir(os.path.join(d, 'book'))) if os.path.isdir(os.path.join(d, 'book')) else []
        if book:
            lines.append('  book:    ' + ', '.join(os.path.join(d, 'book', f) for f in book))
        if st.get('finished'):
            lines.append(f'  report:  {os.path.join(d, "review", "FINAL_REPORT.md")}')
        elif not running:
            lines.append('  next:    btl resume' + ('' if EN.available(cfg) else '  (no CLI engine: use btl next)'))
    return '\n'.join(lines)


# ------------------------------------------------------------------ commands

def start_auto(d, extra=()):
    cfg = C.project(d)
    if not EN.available(cfg):
        print(f'No "{cfg["engine"]}" CLI found, so the automatic mode is not available.\n'
              'In-chat mode: run `btl next` and follow its instructions, again and again, until it says FINISHED.')
        return False
    r = run('auto.py', '--background', '--dir', d, *extra, capture=True)
    if r.returncode:
        print((r.stderr or r.stdout).strip()); return False
    print(f'Started in the background with {cfg["engine"]}: it will translate, review and build the book on its own.')
    print('Follow it with: btl status   ·   stop: btl stop   ·   resume later: btl resume')
    return r.returncode == 0


def cmd_start(o):
    book = os.path.abspath(os.path.expanduser(o.book))
    if not os.path.exists(book):
        die(f'Book not found: {book}')
    if os.path.isdir(book):
        die('That is a folder. To continue an existing job: btl resume "%s"' % book)
    if not o.to:
        langs = ', '.join(f'{k} ({v["name"]})' for k, v in C.languages().items())
        die(f'Which language should the book be translated into? Pass --to CODE.\nProfiles: {langs}; '
            'any other code works with generic rules.', 2)
    args = [book, '--to', o.to, '--from', o.src]
    if o.title:
        args += ['--title', o.title]
    if o.chunk_size:
        args += ['--chunk-size', o.chunk_size]
    r = run('init.py', *args, capture=True)
    if r.returncode:
        die(r.stdout + r.stderr)
    d = os.path.join(os.path.dirname(book), os.path.splitext(os.path.basename(book))[0] + '_temp')
    cfg = C.jload(os.path.join(d, 'project.json'), {})
    for k, v in (('engine', o.engine), ('review_engine', o.review_engine), ('review', o.review), ('model', o.model)):
        if v:
            cfg[k] = v
    C.jsave(os.path.join(d, 'project.json'), cfg)
    register(d)
    print('\n'.join(l for l in r.stdout.strip().splitlines() if not l.startswith('Next (optional)')))
    if o.no_start:
        print('\nReady. Optional: btl config title="Translated title" · btl terms add "Name" "Translation"\n'
              'Then: btl resume' + ('' if EN.available(C.project(d)) else '  (or btl next for the in-chat mode)'))
        return
    print()
    if o.chat or not start_auto(d):
        if o.chat:
            print('In-chat mode: run `btl next` and follow its instructions until it says FINISHED.')


def cmd_status(o):
    if o.job or project_of(os.getcwd()):
        print(summary(resolve(o.job)))
        return
    js = jobs()
    if not js:
        print('No translation job yet. Start one with: btl start BOOK --to LANG'); return
    for d in sorted(js, key=touched, reverse=True):
        print(summary(d, verbose=len(js) == 1)); print()


def cmd_next(o):
    run('step.py', '--dir', resolve(o.job))


def cmd_stop(o):
    d = resolve(o.job); pid = pid_alive(d)
    if not pid:
        print('Not running.'); return
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except OSError:
        os.kill(pid, signal.SIGTERM)
    os.remove(os.path.join(d, 'auto.pid'))
    print('Stopped; progress is saved. Resume with: btl resume')


def passthrough(o):
    extra = []
    for flag, val in (('--engine', o.engine), ('--review-engine', getattr(o, 'review_engine', None)),
                      ('--model', getattr(o, 'model', None))):
        if val:
            extra += [flag, val]
    return extra


def cmd_resume(o):
    d = resolve(o.job)
    if pid_alive(d):
        print('Already running.'); print(summary(d)); return
    start_auto(d, passthrough(o))


def cmd_review(o):
    d = resolve(o.job)
    if C.next_missing(d):
        die('The translation is not finished yet: the review starts by itself at the end. See: btl status')
    cfg = C.jload(os.path.join(d, 'project.json'), {})
    st = C.state(d)
    if o.flagged:
        cfg['review'] = 'flagged'
    elif cfg.get('review') == 'none':
        cfg['review'] = 'full'
    if o.engine:
        cfg['review_engine'] = o.engine
    C.jsave(os.path.join(d, 'project.json'), cfg)
    if o.again or st.get('finished'):
        st['reviewed'] = []; st.pop('analyzed', None)
    st.pop('finished', None); C.save_state(d, st)
    if not start_auto(d):
        print('Or, in chat: btl next')


def cmd_build(o):
    d = resolve(o.job)
    args = ['--dir', d] + (['--formats', o.formats] if o.formats else []) + (['--title', o.title] if o.title else []) \
        + (['--partial'] if o.partial else [])
    run('build.py', *args)


def cmd_check(o):
    run('check.py', '--all', '--short', '--dir', resolve(o.job))


def cmd_log(o):
    p = os.path.join(resolve(o.job), 'auto.log')
    print('\n'.join(C.read(p).splitlines()[-o.n:]) if os.path.exists(p) else 'No log yet.')


def cmd_config(o):
    d = resolve(o.job); p = os.path.join(d, 'project.json'); cfg = C.jload(p, {})
    if not o.pairs:
        keys = ('title', 'author', 'source_lang', 'target_lang', 'engine', 'model', 'review', 'review_engine',
                'review_model', 'group_size', 'parallel', 'retries', 'formats')
        for k in keys:
            print(f'{k:15} {json.dumps(cfg.get(k, C.DEFAULT.get(k)), ensure_ascii=False)}')
        print('Change with: btl config KEY=VALUE   (other keys: see project.json)'); return
    for pair in o.pairs:
        if '=' not in pair:
            die(f'Expected KEY=VALUE, got "{pair}"')
        k, v = pair.split('=', 1)
        try:
            val = json.loads(v)
        except json.JSONDecodeError:
            val = v
        if k == 'target_lang':
            import init
            init.apply_language(cfg, val)
        cfg[k] = val
        print(f'{k} = {json.dumps(val, ensure_ascii=False)}')
    C.jsave(p, cfg); register(d)


def cmd_terms(o):
    d = resolve(o.job); p = os.path.join(d, 'terms.json'); ts = C.terms(d)
    if o.action == 'list':
        q = ' '.join(o.args).lower()
        hits = [t for t in ts if q in (t['source'] + ' ' + t['target']).lower()]
        for t in hits[:200]:
            print(f'{C.letter(t)}  {t["source"]} → {t["target"]}' + (f'   ({t["note"]})' if t.get('note') else ''))
        print(f'{len(hits)} of {len(ts)} terms' + (' (first 200 shown)' if len(hits) > 200 else '')); return
    if o.action == 'add':
        if len(o.args) != 2:
            die('Usage: btl terms add "Source" "Translation" [--proposed] [--note "…"]')
        src, tgt = o.args
        ts = [t for t in ts if t['source'].lower() != src.lower()]
        ts.append({'source': src, 'target': tgt, 'type': 'proposed' if o.proposed else 'fixed',
                   'note': o.note or '', 'aliases': []})
        C.jsave(p, ts); print(f'{"P" if o.proposed else "F"}  {src} → {tgt}'); return
    if o.action == 'remove':
        src = ' '.join(o.args)
        left = [t for t in ts if t['source'].lower() != src.lower()]
        C.jsave(p, left); print(f'removed {len(ts) - len(left)} term(s)'); return


def cmd_import(o):
    args = [os.path.abspath(o.folder)] + (['--to', o.to] if o.to else [])
    r = run('migrate.py', *args)
    if r.returncode == 0:
        register(os.path.abspath(o.folder))
        print('Imported. Continue with: btl resume')


def cmd_jobs(o):
    js = jobs()
    if not js:
        print('No jobs yet.'); return
    for d in sorted(js, key=touched, reverse=True):
        print(summary(d, verbose=False)); print(f'  folder:  {d}')


def cmd_doctor(o):
    ok = True

    def line(good, name, hint=''):
        nonlocal ok
        ok &= bool(good) or name.startswith('(optional)')
        print(('  ✓ ' if good else '  ✗ ') + name + ('' if good else f'  → {hint}'))
    print('book-translate-lite — environment check')
    line(sys.version_info >= (3, 9), f'Python {sys.version.split()[0]}', 'Python 3.9 or newer is required')
    line(shutil.which('pandoc'), 'pandoc', 'install from https://pandoc.org/installing.html')
    from build import CALIBRE
    line(any(c and os.path.exists(c) for c in CALIBRE), 'Calibre (ebook-convert)', 'install from https://calibre-ebook.com (EPUB/PDF input, PDF output)')
    cx, cl = EN.find('codex'), EN.find('claude')
    line(cx, f'(optional) codex CLI{" — " + cx if cx else ""}', 'https://github.com/openai/codex')
    line(cl, f'(optional) claude CLI{" — " + cl if cl else ""}', 'https://docs.anthropic.com/claude-code')
    if not (cx or cl):
        print('  ! no CLI engine: only the in-chat mode (btl next) is available')
    print('Everything needed is installed.' if ok else 'Some requirements are missing (see above).')


def main():
    ap = argparse.ArgumentParser(prog='btl', description='book-translate-lite: translate a whole book with AI agents.',
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__.split('\n\n')[1])
    sub = ap.add_subparsers(dest='cmd', metavar='COMMAND')
    s = sub.add_parser('start', help='set up a book and translate it to the end')
    s.add_argument('book'); s.add_argument('--to'); s.add_argument('--from', dest='src', default='en')
    s.add_argument('--title'); s.add_argument('--engine'); s.add_argument('--review-engine'); s.add_argument('--model')
    s.add_argument('--review', choices=['full', 'flagged', 'none']); s.add_argument('--chunk-size', type=int)
    s.add_argument('--chat', action='store_true', help='use the in-chat mode even if a CLI engine exists')
    s.add_argument('--no-start', action='store_true', help='only set up; start later with btl resume')
    s.set_defaults(fn=cmd_start)
    for name, fn, hlp in (('status', cmd_status, 'progress'), ('next', cmd_next, 'in-chat mode: next action'),
                          ('stop', cmd_stop, 'stop the automatic run'), ('check', cmd_check, 'run the checks')):
        p = sub.add_parser(name, help=hlp); p.add_argument('job', nargs='?'); p.set_defaults(fn=fn)
    p = sub.add_parser('resume', help='resume the automatic run'); p.add_argument('job', nargs='?')
    p.add_argument('--engine'); p.add_argument('--review-engine'); p.add_argument('--model'); p.set_defaults(fn=cmd_resume)
    p = sub.add_parser('review', help='run or rerun the final review'); p.add_argument('job', nargs='?')
    p.add_argument('--again', action='store_true'); p.add_argument('--flagged', action='store_true')
    p.add_argument('--engine'); p.set_defaults(fn=cmd_review)
    p = sub.add_parser('build', help='build EPUB/DOCX/PDF'); p.add_argument('job', nargs='?')
    p.add_argument('--formats'); p.add_argument('--title'); p.add_argument('--partial', action='store_true')
    p.set_defaults(fn=cmd_build)
    p = sub.add_parser('log', help='last lines of the run log'); p.add_argument('job', nargs='?')
    p.add_argument('-n', type=int, default=20); p.set_defaults(fn=cmd_log)
    p = sub.add_parser('config', help='show or change settings'); p.add_argument('pairs', nargs='*')
    p.add_argument('--job'); p.set_defaults(fn=cmd_config)
    p = sub.add_parser('terms', help='glossary'); p.add_argument('action', choices=['list', 'add', 'remove'])
    p.add_argument('args', nargs='*'); p.add_argument('--job'); p.add_argument('--proposed', action='store_true')
    p.add_argument('--note'); p.set_defaults(fn=cmd_terms)
    p = sub.add_parser('import', help='import a translate-book or v1 project'); p.add_argument('folder')
    p.add_argument('--to'); p.set_defaults(fn=cmd_import)
    sub.add_parser('jobs', help='list jobs').set_defaults(fn=cmd_jobs)
    sub.add_parser('doctor', help='check the installation').set_defaults(fn=cmd_doctor)
    o = ap.parse_args()
    if not getattr(o, 'fn', None):
        print(__doc__); return
    o.fn(o)


if __name__ == '__main__':
    main()
