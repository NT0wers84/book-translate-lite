#!/usr/bin/env python3
"""Create self-contained tasks for sub-agents by hand (step.py does this for you).

Usage:  prep.py                 from the next missing part, `parallel` groups of `group_size`
        prep.py 12 20 [--g 2]   parts 12–20 in groups of g
        prep.py --review 12 20  REVIEW tasks (uses review/flags.json if present)

Prints, for each task, the exact prompt to give the sub-agent.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as C
import tasks as T

PROMPT = ('Work in `{d}`. Run `cat _tasks/{f}` and follow the instructions at the top of the file. '
          'Do not read other files. Reply only "done …" or the remaining problem.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a', type=int, nargs='?'); ap.add_argument('b', type=int, nargs='?')
    ap.add_argument('--g', type=int); ap.add_argument('--review', action='store_true'); ap.add_argument('--dir')
    o = ap.parse_args(); d = C.find_dir(o.dir); cfg = C.project(d); tot = C.n_parts(d)
    ts = C.terms(d); rules = C.rules(d)
    if o.review:
        if not o.a:
            ap.error('--review needs A [B]')
        flags = C.jload(os.path.join(d, 'review', 'flags.json'), {}) or {}
        ids = list(range(o.a, (o.b or o.a) + 1))
        for g in C.groups(ids, o.g or cfg['review_group_size']):
            p = T.review(d, g, cfg, ts, rules, flags)
            print(f'{os.path.basename(p)} → PROMPT: ' + PROMPT.format(d=d, f=os.path.basename(p)))
        return
    g = o.g or cfg['group_size']
    a = o.a or C.next_missing(d)
    if not a:
        sys.exit('Every part is translated: go on with step.py (review) or auto.py.')
    b = min(o.b or (a + cfg['parallel'] * g - 1), tot)
    ids = list(range(a, b + 1))
    already = [n for n in ids if C.translated(d, n)]
    if already:
        print('WARNING: already translated (will be overwritten if redone):', ', '.join(f'{n:04d}' for n in already))
    for k in range(0, len(ids), g):
        p = T.translation(d, ids[k:k + g], cfg, ts, rules)
        print(f'{os.path.basename(p)} ({os.path.getsize(p) // 1024} KB) → PROMPT: '
              + PROMPT.format(d=d, f=os.path.basename(p)))
    print(f'Then: finish.py {a} {b}')


if __name__ == '__main__':
    main()
