#!/usr/bin/env python3
"""Fake engine for the tests: reads a task on stdin and answers in the expected format,
with no model at all. "Translates" by swapping glossary terms and a few words.

FAKE_ERROR=<file>: the first task containing part 0002 drops a paragraph (to exercise
the retries); the file records that the error has been made.
"""
import os, re, sys

WORDS = {'the': 'il', 'The': 'Il', 'and': 'e', 'said': 'disse', 'she': 'lei', 'She': 'Lei', 'of': 'di',
         'was': 'era', 'to': 'a', 'a': 'un', 'her': 'sua', 'you': 'tu', 'with': 'con', 'that': 'che',
         'Chapter': 'Capitolo', 'for': 'per', 'not': 'non', 'is': 'è', 'it': 'esso', 'on': 'su', 'at': 'a',
         'from': 'da', 'but': 'ma', 'this': 'questo', 'have': 'avere', 'what': 'cosa', 'are': 'sono',
         'just': 'solo', 'they': 'loro', 'would': 'sarebbe', 'there': 'là', 'could': 'poteva', 'were': 'erano'}


def glossary(task):
    return [(m.group(1).strip(), m.group(2).strip())
            for m in re.finditer(r'^\| ([^|]+) \| ([^|]+) \| [FP] \|', task, re.M) if m.group(1).strip() != 'source']


def translate(text, gl):
    for s, t in sorted(gl, key=lambda x: -len(x[0])):
        text = re.sub(r'(?<![\w’])' + re.escape(s) + r'(?![\w’])', t, text)
    pieces = re.split(r'(\{[^}]*\}|\]\([^)]*\))', text)
    for k in range(0, len(pieces), 2):
        pieces[k] = re.sub(r'\b[A-Za-z]+\b', lambda m: WORDS.get(m.group(0), m.group(0)), pieces[k])
        pieces[k] = re.sub(r'“([^”]*)”', r'«\1»', pieces[k])
    return ''.join(pieces)


def main():
    task = sys.stdin.read()
    gl = glossary(task)
    if '# TASK review' in task:
        out = []
        for m in re.finditer(r'## Translation (\d{4})\n\n(.*?)(?=\n# Part \d{4}|\Z)', task, re.S):
            n, text = m.group(1), m.group(2).strip()
            pars = [p for p in text.split('\n\n') if len(p) > 60 and not p.startswith(('#', '!', '*', '>'))]
            if n == '0001' and pars:
                out.append(f'@@PART {n}@@\n@@OLD@@\n{pars[0]}\n@@NEW@@\n{pars[0]} (reviewed)')
            else:
                out.append(f'@@PART {n}@@\n@@OK@@')
        print('\n'.join(out)); return
    err = os.environ.get('FAKE_ERROR')
    out = []
    for m in re.finditer(r'## Source text — part (\d{4})\n\n(.*?)(?=\n## Source text — part |\Z)', task, re.S):
        n, src = m.group(1), m.group(2).strip()
        tr = translate(src, gl)
        if err and n == '0002' and not os.path.exists(err):
            open(err, 'w').write('done')
            tr = '\n\n'.join(tr.split('\n\n')[:-1])
        meta = ('{"new_entities": [{"source": "Salt Market", "target_proposal": "Mercato del Sale", '
                '"category": "place"}], "conflicts": []}')
        out.append(f'@@PART {n}@@\n{tr}\n@@META@@\n{meta}')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
