#!/usr/bin/env python3
"""Test end-to-end senza modelli: python3 tests/test_completo.py   (servono pandoc e Calibre per il PDF)

- automatico: init → auto.py con motore finto (con un errore da ritentare) → revisione → libro
- in chat: init → passo.py in ciclo, sotto-agenti simulati che usano save.py / patch.py → FINITO
- save.py respinge una parte con un paragrafo mancante
- migra.py converte un progetto translate-book senza toccare le parti fatte
"""
import glob, hashlib, json, os, re, subprocess, sys, tempfile, unittest, zipfile

QUI = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(os.path.dirname(QUI), 'scripts')
sys.path.insert(0, QUI)
from crea_libro_prova import crea

PY = sys.executable


def jl(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def jw(p, o):
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(o, f, ensure_ascii=False)


def rd(p, mode='r'):
    with open(p, mode, **({} if 'b' in mode else {'encoding': 'utf-8'})) as f:
        return f.read()


def wr(p, s):
    with open(p, 'w', encoding='utf-8') as f:
        f.write(s)


FINTO = [PY, os.path.join(QUI, 'motore_finto.py')]


def run(args, cwd, inp=None, env=None):
    return subprocess.run([PY, os.path.join(S, args[0])] + args[1:], cwd=cwd, input=inp, capture_output=True,
                          text=True, env=dict(os.environ, **(env or {})))


def nuovo_progetto(tmp, formati='epub'):
    libro = crea(tmp)
    r = run(['init.py', libro, '--lang', 'it', '--chunk-size', '400'], tmp)
    assert r.returncode == 0, r.stdout + r.stderr
    d = os.path.join(tmp, 'The Clockwork Lighthouse_temp')
    jw(os.path.join(d, 'glossario.json'),
       [{'source': 'Brass Warden', 'target': 'Custode d’Ottone', 'tipo': 'V', 'nota': '', 'alias': []},
        {'source': 'Copper Gull', 'target': 'Gabbiano di Rame', 'tipo': 'P', 'nota': '', 'alias': []}])
    p = jl(os.path.join(d, 'progetto.json'))
    p.update({'motore': 'comando', 'comando_motore': FINTO, 'titolo': 'Il Faro a Orologeria', 'formati': formati,
              'gruppo': 2, 'paralleli': 2})
    jw(os.path.join(d, 'progetto.json'), p)
    return d


def controlla_finale(t, d):
    st = jl(os.path.join(d, 'stato.json'))
    n = len(glob.glob(os.path.join(d, 'chunk[0-9]*.md')))
    t.assertGreaterEqual(n, 4)
    t.assertEqual(len(st['fatte']), n)
    t.assertEqual(len(st['rivedute']), n)
    t.assertTrue(st.get('finito'))
    t.assertTrue(os.path.exists(os.path.join(d, 'revisione', 'RAPPORTO_FINALE.md')))
    t.assertIn('(rivisto)', rd(os.path.join(d, 'output_chunk0001.md')))
    gl = {x['source']: x for x in jl(os.path.join(d, 'glossario.json'))}
    t.assertEqual(gl['Salt Market']['tipo'], 'P')
    epub = os.path.join(d, 'libro', 'Il Faro a Orologeria.epub')
    with zipfile.ZipFile(epub) as z:
        opf = z.read('EPUB/content.opf').decode(); ncx = z.read('EPUB/toc.ncx').decode()
    t.assertIn('<dc:language>it</dc:language>', opf)
    t.assertEqual(len(re.findall(r'<text>Capitolo \d', ncx)), 3)
    t.assertEqual(glob.glob(os.path.join(d, '_task', '*')), [])


class Test(unittest.TestCase):
    def test_automatico(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = nuovo_progetto(tmp, 'epub,docx,pdf')
            r = run(['auto.py'], d, env={'FINTO_ERRORE': os.path.join(tmp, 'errore_fatto')})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('tentativo 1: da rifare 0002', r.stdout)
            self.assertIn('FINITO', r.stdout)
            controlla_finale(self, d)
            for ext in ('docx', 'pdf'):
                if ext == 'pdf' and 'PDF saltato' in r.stdout:
                    continue
                self.assertTrue(os.path.exists(os.path.join(d, 'libro', f'Il Faro a Orologeria.{ext}')), ext)
            r2 = run(['auto.py'], d)        # rilancio a lavoro finito: nessun danno
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)

    def test_in_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = nuovo_progetto(tmp)
            env = {'FINTO_ERRORE': os.path.join(tmp, 'errore_fatto')}
            for giro in range(40):
                r = run(['passo.py'], d)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                if 'FINITO' in r.stdout:
                    break
                tasks = re.findall(r'cat _task/(\S+?)`', r.stdout)
                self.assertTrue(tasks, r.stdout)
                for f in tasks:            # sotto-agente simulato: 2 comandi (cat + save/patch)
                    testo = rd(os.path.join(d, '_task', f))
                    risp = subprocess.run(FINTO, input=testo, capture_output=True, text=True,
                                          env=dict(os.environ, **env)).stdout
                    run(['patch.py' if f.startswith('rev_') else 'save.py'], d, inp=risp)
            else:
                self.fail('passo.py non è arrivato a FINITO')
            controlla_finale(self, d)

    def test_save_respinge(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = nuovo_progetto(tmp)
            src = rd(os.path.join(d, 'chunk0001.md')).strip().split('\n\n')
            r = run(['save.py'], d, inp='@@PARTE 0001@@\n' + '\n\n'.join(src[:-1]) + '\n')
            self.assertEqual(r.returncode, 1)
            self.assertIn('DA CORREGGERE', r.stdout)
            r = run(['save.py'], d, inp='@@PARTE 0001@@\nciao\n@@META@@\n{non json')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('Niente salvato', r.stderr)

    def test_migra(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, 'vecchio_temp'); os.makedirs(d)
            for n in (1, 2, 3):
                wr(os.path.join(d, f'chunk{n:04d}.md'), f'# {n}\n\nThe Brass Warden sang.\n')
            for n in (1, 2):
                wr(os.path.join(d, f'output_chunk{n:04d}.md'), f'# {n}\n\nIl Custode d’Ottone cantava.\n')
            jw(os.path.join(d, 'glossary.json'),
               {'terms': [{'source': 'Brass Warden', 'target': 'Custode d’Ottone', 'confidence': 'high',
                           'notes': '', 'aliases': []}], 'applied_meta_hashes': {'chunk0001': 'x'}})
            jw(os.path.join(d, 'run_state.json'), {'chunks': {'chunk0001': {}, 'chunk0002': {}}})
            wr(os.path.join(d, 'config.txt'), 'output_lang=it\noriginal_title=Old (x)\n')
            prima = {f: hashlib.sha256(rd(f, 'rb')).hexdigest() for f in glob.glob(os.path.join(d, '*'))}
            r = run(['migra.py', d], tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('Prossima parte: 3', r.stdout)
            for f, h in prima.items():
                self.assertEqual(hashlib.sha256(rd(f, 'rb')).hexdigest(), h, f)
            st = jl(os.path.join(d, 'stato.json'))
            self.assertEqual(st['fatte'], [1, 2])
            self.assertEqual(jl(os.path.join(d, 'glossario.json'))[0]['tipo'], 'V')
            self.assertEqual(run(['check.py', '--tutte'], d).returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
