#!/usr/bin/env python3
"""Close a block of parts by hand: check → record → merge meta → delete tasks.

Usage:  finish.py 12 20            finish.py 12 20 --force (record even with problems,
                                    flagging them for the final review)
        finish.py                  status and next part only

State is simple: state.json lists the finished parts. Changing the glossary NEVER
makes a finished part look "to be retranslated".
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as C
import work as W
from check import check


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a', type=int, nargs='?'); ap.add_argument('b', type=int, nargs='?')
    ap.add_argument('--force', action='store_true'); ap.add_argument('--dir')
    o = ap.parse_args(); d = C.find_dir(o.dir); st = C.state(d)
    if o.a:
        cfg = C.project(d); ts = C.terms(d)
        ids = list(range(o.a, (o.b or o.a) + 1))
        probs = {n: p for n in ids for p in [check(d, n, cfg, ts)[0]] if p}
        if probs and not o.force:
            for n, p in probs.items():
                print(f'{n:04d}: NEEDS FIXING'); [print('  -', x) for x in p]
            print('Fix these points (targeted edit) or rerun the task of the missing part, then run finish.py '
                  'again. If they are false positives: --force (they stay flagged for the review).')
            sys.exit(1)
        W.close(d, ids, st, flagged={n: p for n, p in probs.items() if C.translated(d, n)})
    print(W.status_line(d))


if __name__ == '__main__':
    main()
