#!/usr/bin/env python3
"""Motore finto per i test: legge un task da stdin e risponde nel formato atteso,
senza nessun modello. «Traduce» sostituendo i termini del glossario e qualche parola.

FINTO_ERRORE=<file>: al primo task che contiene la parte 0002 salta un paragrafo
(per provare i tentativi); il file segna che l'errore è già stato fatto.
"""
import os, re, sys

PAROLE = {'the': 'il', 'The': 'Il', 'and': 'e', 'said': 'disse', 'she': 'lei', 'She': 'Lei', 'of': 'di',
          'was': 'era', 'to': 'a', 'a': 'un', 'her': 'sua', 'you': 'tu', 'with': 'con', 'that': 'che',
          'Chapter': 'Capitolo', 'for': 'per', 'not': 'non', 'is': 'è', 'it': 'esso', 'on': 'su', 'at': 'a',
          'in': 'in', 'from': 'da', 'but': 'ma', 'this': 'questo', 'have': 'avere', 'what': 'cosa', 'are': 'sono',
          'just': 'solo', 'they': 'loro', 'would': 'sarebbe', 'there': 'là', 'could': 'poteva', 'were': 'erano'}


def glossario(task):
    return [(m.group(1).strip(), m.group(2).strip())
            for m in re.finditer(r'^\| ([^|]+) \| ([^|]+) \| [VP] \|', task, re.M) if m.group(1).strip() != 'originale']


def traduci(testo, gl):
    for s, t in sorted(gl, key=lambda x: -len(x[0])):
        testo = re.sub(r'(?<![\w’])' + re.escape(s) + r'(?![\w’])', t, testo)
    pezzi = re.split(r'(\{[^}]*\}|\]\([^)]*\))', testo)
    for k in range(0, len(pezzi), 2):
        pezzi[k] = re.sub(r'\b[A-Za-z]+\b', lambda m: PAROLE.get(m.group(0), m.group(0)), pezzi[k])
        pezzi[k] = re.sub(r'“([^”]*)”', r'«\1»', pezzi[k])
    return ''.join(pezzi)


def main():
    task = sys.stdin.read()
    gl = glossario(task)
    if '# TASK revisione' in task:
        out = []
        for m in re.finditer(r'## Traduzione (\d{4})\n\n(.*?)(?=\n# Parte \d{4}|\Z)', task, re.S):
            n, testo = m.group(1), m.group(2).strip()
            pars = [p for p in testo.split('\n\n') if len(p) > 60 and not p.startswith(('#', '!', '*', '>'))]
            if n == '0001' and pars:
                out.append(f'@@PARTE {n}@@\n@@VECCHIO@@\n{pars[0]}\n@@NUOVO@@\n{pars[0]} (rivisto)')
            else:
                out.append(f'@@PARTE {n}@@\n@@OK@@')
        print('\n'.join(out)); return
    errore = os.environ.get('FINTO_ERRORE')
    out = []
    for m in re.finditer(r'## Testo originale — parte (\d{4})\n\n(.*?)(?=\n## Testo originale — parte |\Z)', task, re.S):
        n, src = m.group(1), m.group(2).strip()
        it = traduci(src, gl)
        if errore and n == '0002' and not os.path.exists(errore):
            open(errore, 'w').write('fatto')
            it = '\n\n'.join(it.split('\n\n')[:-1])
        meta = '{"new_entities": [{"source": "Salt Market", "target_proposal": "Mercato del Sale", "category": "luogo"}], "conflicts": []}'
        out.append(f'@@PARTE {n}@@\n{it}\n@@META@@\n{meta}')
    print('\n'.join(out))


if __name__ == '__main__':
    main()
