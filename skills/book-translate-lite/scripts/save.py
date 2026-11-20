#!/usr/bin/env python3
"""Save several translated parts from stdin, apply mechanical fixes and check them.

  python3 save.py <<'@@END@@'
  @@PART 0012@@
  …translated text…
  @@META@@
  {"new_entities": [], "conflicts": []}
  @@PART 0013@@
  …
  @@END@@

META is optional. If any block is invalid nothing is saved.
Exit 1 if a part NEEDS FIXING (then: targeted edit of output_chunkNNNN.md).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as C
import work as W


def main():
    d = C.find_dir(C.arg_dir())
    saved, problems, errors = W.save_blocks(d, sys.stdin.read(), C.project(d), C.terms(d))
    if errors:
        sys.exit('ERROR: ' + '; '.join(errors) + '. Nothing saved: run the command again.')
    if not saved:
        sys.exit('ERROR: no @@PART NNNN@@ block. Nothing saved.')
    for n in saved:
        if n in problems:
            print(f'{n:04d}: NEEDS FIXING'); [print('  -', x) for x in problems[n]]
        else:
            print(f'OK {n:04d}')
    print('saved: ' + ', '.join(f'{n:04d}' for n in saved))
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
