#!/usr/bin/env python3
"""Apply review fixes from stdin.

  python3 patch.py <<'@@END@@'
  @@PART 0012@@
  @@OLD@@
  exact text to replace
  @@NEW@@
  corrected text
  @@PART 0013@@
  @@OK@@
  @@END@@

Each fix must find the OLD text exactly once; a fix that breaks the check is undone.
The first original of every changed part is kept in review/backup/.
Every listed part (including @@OK@@) is marked as reviewed.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as C
import work as W


def main():
    d = C.find_dir(C.arg_dir())
    ok, rejected, seen = W.apply_patches(d, sys.stdin.read(), C.project(d), C.terms(d))
    if not seen:
        sys.exit('ERROR: no @@PART NNNN@@ block.')
    st = C.state(d); st['reviewed'] = sorted(set(st['reviewed']) | set(seen)); C.save_state(d, st)
    print(f'fixes applied: {ok}; parts reviewed: ' + ', '.join(f'{n:04d}' for n in seen))
    for n, m in rejected:
        print(f'  rejected {n:04d}: {m}')


if __name__ == '__main__':
    main()
