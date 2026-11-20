#!/usr/bin/env python3
"""In-chat mode: tells the orchestrator the NEXT action, until the book is finished.

Usage:  step.py [--dir FOLDER]

Every run:
1. closes finished tasks (check, record, merge glossary). Rejected parts are put back
   into a task with the list of errors, up to `retries` times, then accepted and
   flagged for the review;
2. prints the sub-agent prompts to launch NOW (all together), or "FINISHED" when
   translation, review and book are ready.
Phases: translation → analysis → review (rev_* tasks) → final (build + report).
"""
import glob, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as C
import review as R
import tasks as T
import work as W
from check import check

PROMPT = ('Work in `{d}`. Run `cat _tasks/{f}` and follow the instructions at the top of the file. '
          'Do not read other files. Reply only "done …" or the remaining problem.')


def parts_of(f):
    nums = [int(x) for x in re.findall(r'\d{4}', os.path.basename(f))]
    return list(range(nums[0], nums[-1] + 1)) if nums else []


def launch(d, paths, header):
    print(header)
    print(f'LAUNCH NOW {len(paths)} sub-agents (all together), then run step.py again:')
    for p in paths:
        print('- ' + PROMPT.format(d=d, f=os.path.basename(p)))


def main():
    d = C.find_dir(C.arg_dir())
    cfg = C.project(d); ts = C.terms(d); st = C.state(d); tot = C.n_parts(d); rules = C.rules(d)
    att = st['attempts']; to_launch = []

    # 1. close translation tasks
    closed, flagged = [], {}
    for f in sorted(glob.glob(os.path.join(d, '_tasks', 'task_*.md'))):
        ids = parts_of(f)
        miss = [n for n in ids if not C.translated(d, n)]
        probs = {n: p for n in ids if n not in miss for p in [check(d, n, cfg, ts)[0]] if p}
        redo = []
        for n in miss + sorted(probs):
            k = f'{n:04d}'; att[k] = att.get(k, 0) + 1
            if att[k] <= cfg['retries']:
                redo.append(n)
            elif n in probs:
                flagged[n] = probs[n]
        os.remove(f)
        closed += [n for n in ids if n not in redo and C.translated(d, n)]
        for gr in C.groups(redo, cfg['group_size']):
            to_launch.append(T.translation(d, gr, cfg, ts, rules,
                                           problems={n: probs.get(n, ['part not saved']) for n in gr}))
    if closed:
        W.close(d, closed, st, flagged=flagged)
        st = C.state(d); st['attempts'] = att
    C.save_state(d, st)

    # 2. new translation tasks
    if not to_launch:
        missing = [n for n in range(1, tot + 1) if not C.translated(d, n)]
        blocked = [n for n in missing if att.get(f'{n:04d}', 0) > cfg['retries'] + 2]
        missing = [n for n in missing if n not in blocked]
        if blocked:
            print('BLOCKED (cannot be translated, needs a human): ' + ', '.join(f'{n:04d}' for n in blocked))
            if not missing:
                return
        for gr in C.groups(missing[:cfg['group_size'] * cfg['parallel']], cfg['group_size']):
            to_launch.append(T.translation(d, gr, cfg, ts, rules))
            for n in gr:
                if f'{n:04d}' in att:
                    att[f'{n:04d}'] += 1
        st['attempts'] = att; C.save_state(d, st)
    if to_launch:
        launch(d, to_launch, W.status_line(d)); return

    # 3. review
    if cfg['review'] != 'none':
        if not st.get('analyzed'):
            R.analyze(d); st = C.state(d); st['analyzed'] = True; C.save_state(d, st)
        flags = C.jload(os.path.join(d, 'review', 'flags.json'), {}) or {}
        open_tasks = []
        for f in sorted(glob.glob(os.path.join(d, '_tasks', 'rev_*.md'))):
            if all(n in st['reviewed'] for n in parts_of(f)):
                os.remove(f); continue
            k = os.path.basename(f); att[k] = att.get(k, 0) + 1
            if att[k] > 2:                 # two launches without result: mark as seen and move on
                st['reviewed'] = sorted(set(st['reviewed']) | set(parts_of(f))); os.remove(f)
            else:
                open_tasks.append(f)
        st['attempts'] = att; C.save_state(d, st)
        if not open_tasks:
            open_tasks = [T.review(d, gr, cfg, ts, rules, flags)
                          for gr in C.groups(R.todo(d), cfg['review_group_size'])[:cfg['parallel']]]
        if open_tasks:
            launch(d, open_tasks, f'REVIEW: {len(st["reviewed"])} parts reviewed, {len(R.todo(d))} to do.'); return

    # 4. end
    if st.get('finished'):
        print('FINISHED (already complete). To rebuild the book: build.py; report: review/FINAL_REPORT.md')
        return
    R.final(d)


if __name__ == '__main__':
    main()
