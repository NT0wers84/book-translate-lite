#!/usr/bin/env python3
"""End-to-end tests with no model:  python3 tests/test_all.py   (needs pandoc; Calibre for PDF)

- automatic: init → auto.py with the fake engine (one error to retry) → review → book
- in-chat: init → step.py in a loop, simulated sub-agents using save.py / patch.py → FINISHED
- other target language: profile, rules and EPUB language follow --to
- save.py rejects a part with a missing paragraph and invalid meta
- migrate.py imports a translate-book project without touching finished parts
- migrate.py converts a v1 (Italian file names) project
- btl: the user-facing command, start → background run → status FINISHED, terms, config, stop/resume
- build: title page (subtitle, rights), cover taken from the original EPUB, doubled scene breaks collapsed
"""
import glob, hashlib, json, os, re, subprocess, sys, tempfile, unittest, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(os.path.dirname(HERE), 'skills', 'book-translate-lite', 'scripts')
sys.path.insert(0, HERE)
from make_test_book import make

PY = sys.executable
FAKE = [PY, os.path.join(HERE, 'fake_engine.py')]


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


def run(args, cwd, inp=None, env=None):
    return subprocess.run([PY, os.path.join(S, args[0])] + args[1:], cwd=cwd, input=inp, capture_output=True,
                          text=True, env=dict(os.environ, **(env or {})))


def new_project(tmp, formats='epub', lang='it', title='Il Faro a Orologeria'):
    book = make(tmp)
    r = run(['init.py', book, '--to', lang, '--chunk-size', '400'], tmp)
    assert r.returncode == 0, r.stdout + r.stderr
    d = os.path.join(tmp, 'The Clockwork Lighthouse_temp')
    jw(os.path.join(d, 'terms.json'),
       [{'source': 'Brass Warden', 'target': 'Custode d’Ottone', 'type': 'fixed', 'note': '', 'aliases': []},
        {'source': 'Copper Gull', 'target': 'Gabbiano di Rame', 'type': 'proposed', 'note': '', 'aliases': []}])
    p = jl(os.path.join(d, 'project.json'))
    p.update({'engine': 'command', 'engine_command': FAKE, 'title': title, 'formats': formats,
              'group_size': 2, 'parallel': 2})
    jw(os.path.join(d, 'project.json'), p)
    return d


def rd_opf(epub):
    with zipfile.ZipFile(epub) as z:
        return z.read(next(n for n in z.namelist() if n.endswith('.opf'))).decode()


def check_final(t, d, title='Il Faro a Orologeria', lang='it'):
    st = jl(os.path.join(d, 'state.json'))
    n = len(glob.glob(os.path.join(d, 'chunk[0-9]*.md')))
    t.assertGreaterEqual(n, 4)
    t.assertEqual(len(st['done']), n)
    t.assertEqual(len(st['reviewed']), n)
    t.assertTrue(st.get('finished'))
    t.assertTrue(os.path.exists(os.path.join(d, 'review', 'FINAL_REPORT.md')))
    t.assertIn('(reviewed)', rd(os.path.join(d, 'output_chunk0001.md')))
    gl = {x['source']: x for x in jl(os.path.join(d, 'terms.json'))}
    t.assertEqual(gl['Salt Market']['type'], 'proposed')
    with zipfile.ZipFile(os.path.join(d, 'book', f'{title}.epub')) as z:
        opf = z.read('EPUB/content.opf').decode(); ncx = z.read('EPUB/toc.ncx').decode()
    t.assertIn(f'<dc:language>{lang}</dc:language>', opf)
    t.assertEqual(len(re.findall(r'<navPoint', ncx)) >= 4, True)
    t.assertEqual(glob.glob(os.path.join(d, '_tasks', '*')), [])


class Test(unittest.TestCase):
    def test_automatic(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = new_project(tmp, 'epub,docx,pdf')
            r = run(['auto.py'], d, env={'FAKE_ERROR': os.path.join(tmp, 'error_done')})
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('attempt 1: redo 0002', r.stdout)
            self.assertIn('FINISHED', r.stdout)
            check_final(self, d)
            for ext in ('docx', 'pdf'):
                if ext == 'pdf' and 'PDF skipped' in r.stdout:
                    continue
                self.assertTrue(os.path.exists(os.path.join(d, 'book', f'Il Faro a Orologeria.{ext}')), ext)
            r2 = run(['auto.py'], d)        # running again on a finished job does no harm
            self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)

    def test_in_chat(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = new_project(tmp)
            env = dict(os.environ, FAKE_ERROR=os.path.join(tmp, 'error_done'))
            for _ in range(40):
                r = run(['step.py'], d)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                if 'FINISHED' in r.stdout:
                    break
                todo = re.findall(r'cat _tasks/(\S+?)`', r.stdout)
                self.assertTrue(todo, r.stdout)
                for f in todo:            # simulated sub-agent: 2 commands (cat + save/patch)
                    ans = subprocess.run(FAKE, input=rd(os.path.join(d, '_tasks', f)), capture_output=True,
                                         text=True, env=env).stdout
                    run(['patch.py' if f.startswith('rev_') else 'save.py'], d, inp=ans)
            else:
                self.fail('step.py never reached FINISHED')
            check_final(self, d)

    def test_other_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = new_project(tmp, lang='fr', title='Le Phare Mécanique')
            p = jl(os.path.join(d, 'project.json'))
            self.assertEqual((p['target_lang'], p['target_lang_name'], p['quotes']), ('fr', 'French', '«»'))
            self.assertIn('French publishing conventions', rd(os.path.join(d, 'rules.md')))
            self.assertEqual(run(['prep.py'], d).returncode, 0)
            tasks = sorted(glob.glob(os.path.join(d, '_tasks', '*')))
            self.assertIn('into French', rd(tasks[0]))
            for f in tasks:
                os.remove(f)
            r = run(['auto.py'], d)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            check_final(self, d, title='Le Phare Mécanique', lang='fr')
            r = run(['init.py', os.path.join(tmp, 'The Clockwork Lighthouse.epub'), '--to', 'xx'], tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)   # unknown code: generic rules, no crash

    def test_save_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = new_project(tmp)
            src = rd(os.path.join(d, 'chunk0001.md')).strip().split('\n\n')
            r = run(['save.py'], d, inp='@@PART 0001@@\n' + '\n\n'.join(src[:-1]) + '\n')
            self.assertEqual(r.returncode, 1)
            self.assertIn('NEEDS FIXING', r.stdout)
            r = run(['save.py'], d, inp='@@PART 0001@@\nhello\n@@META@@\n{not json')
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('Nothing saved', r.stderr)

    def test_migrate_translate_book(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, 'old_temp'); os.makedirs(d)
            for n in (1, 2, 3):
                wr(os.path.join(d, f'chunk{n:04d}.md'), f'# {n}\n\nThe Brass Warden sang.\n')
            for n in (1, 2):
                wr(os.path.join(d, f'output_chunk{n:04d}.md'), f'# {n}\n\nIl Custode d’Ottone cantava.\n')
            jw(os.path.join(d, 'glossary.json'),
               {'terms': [{'source': 'Brass Warden', 'target': 'Custode d’Ottone', 'confidence': 'high',
                           'notes': '', 'aliases': []}], 'applied_meta_hashes': {'chunk0001': 'x'}})
            jw(os.path.join(d, 'run_state.json'), {'chunks': {'chunk0001': {}, 'chunk0002': {}}})
            wr(os.path.join(d, 'config.txt'), 'output_lang=it\noriginal_title=Old (x)\n')
            before = {f: hashlib.sha256(rd(f, 'rb')).hexdigest() for f in glob.glob(os.path.join(d, '*'))}
            r = run(['migrate.py', d], tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('next part: 3', r.stdout)
            for f, h in before.items():
                self.assertEqual(hashlib.sha256(rd(f, 'rb')).hexdigest(), h, f)
            self.assertEqual(jl(os.path.join(d, 'state.json'))['done'], [1, 2])
            self.assertEqual(jl(os.path.join(d, 'terms.json'))[0]['type'], 'fixed')
            self.assertEqual(run(['check.py', '--all'], d).returncode, 0)

    def test_btl(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {'BTL_HOME': os.path.join(tmp, 'home')}
            book = make(tmp)
            r = run(['btl.py', 'start', book], tmp, env=env)
            self.assertEqual(r.returncode, 2)                       # no language: asks for --to
            self.assertIn('--to', r.stderr)
            r = run(['btl.py', 'start', book, '--to', 'it', '--chunk-size', '400', '--no-start'], tmp, env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('Ready', r.stdout)
            job = 'Clockwork'                                        # a job can be named by part of its title
            r = run(['btl.py', 'config', '--job', job, 'title=Il Faro a Orologeria', 'engine=command',
                     'engine_command=' + json.dumps(FAKE), 'group_size=2', 'formats=epub'], tmp, env=env)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            r = run(['btl.py', 'terms', 'add', 'Brass Warden', 'Custode d’Ottone', '--job', 'Faro'], tmp, env=env)
            self.assertIn('F  Brass Warden', r.stdout)
            self.assertIn('Brass Warden', run(['btl.py', 'terms', 'list', '--job', 'Faro'], tmp, env=env).stdout)
            r = run(['btl.py', 'resume', 'Faro'], tmp, env=env)
            self.assertIn('Started in the background', r.stdout, r.stdout + r.stderr)
            for _ in range(60):
                st = run(['btl.py', 'status'], tmp, env=env).stdout   # no job given: the only/most recent one
                if 'FINISHED' in st and 'stopped' in st:
                    break
                import time; time.sleep(0.5)
            self.assertIn('FINISHED', st)
            self.assertIn('Il Faro a Orologeria.epub', st)
            self.assertIn('FINAL_REPORT.md', st)
            d = os.path.join(tmp, 'The Clockwork Lighthouse_temp')
            check_final(self, d)
            self.assertIn('Faro', run(['btl.py', 'jobs'], tmp, env=env).stdout)
            self.assertIn('Not running', run(['btl.py', 'stop'], d, env=env).stdout)
            r = run(['btl.py', 'review', '--again', '--flagged'], d, env=env)     # rerun of the review
            self.assertIn('Started in the background', r.stdout, r.stdout + r.stderr)
            for _ in range(60):
                if 'FINISHED' in run(['btl.py', 'status'], d, env=env).stdout:
                    break
                import time; time.sleep(0.5)
            self.assertIn('FINISHED', run(['btl.py', 'status'], d, env=env).stdout)
            self.assertEqual(jl(os.path.join(d, 'project.json'))['review'], 'flagged')

    def test_build_extras(self):
        sys.path.insert(0, S)
        import build
        ep, dx = build.scene_breaks('a\n\n![](images/o.svg){.ornamental-break-image}\n\n\\* \\* \\*\n\nb\n\n![](p.png)\n\nc')
        self.assertEqual(ep, 'a\n\n![](images/o.svg){.ornamental-break-image}\n\nb\n\n![](p.png)\n\nc')
        self.assertEqual(dx, 'a\n\n\\* \\* \\*\n\nb\n\n![](p.png)\n\nc')
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, 'orig.epub')
            with zipfile.ZipFile(src, 'w') as z:
                z.writestr('META-INF/container.xml', '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                           '<rootfiles><rootfile full-path="OEBPS/c.opf"/></rootfiles></container>')
                z.writestr('OEBPS/c.opf', '<package xmlns="http://www.idpf.org/2007/opf"><manifest>'
                           '<item id="x" href="img/front%20art.jpg" media-type="image/jpeg" properties="cover-image"/>'
                           '</manifest></package>')
                z.writestr('OEBPS/img/front art.jpg', b'JPEGDATA')
            d = new_project(tmp)
            p = jl(os.path.join(d, 'project.json'))
            p.update({'source': 'orig.epub', 'subtitle': 'Series, volume 2', 'rights': 'Personal use only.'})
            jw(os.path.join(d, 'project.json'), p)
            for f in glob.glob(os.path.join(d, 'chunk[0-9]*.md')):
                wr(os.path.join(d, 'output_' + os.path.basename(f)), rd(f))
            r = run(['build.py', '--formats', 'epub'], d)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(rd(os.path.join(d, 'images', 'cover.jpg'), 'rb'), b'JPEGDATA')
            with zipfile.ZipFile(os.path.join(d, 'book', 'Il Faro a Orologeria.epub')) as z:
                allx = ''.join(z.read(n).decode('utf-8', 'ignore') for n in z.namelist() if n.endswith('.xhtml'))
            self.assertIn('Series, volume 2', allx)
            self.assertIn('Personal use only.', allx)
            self.assertIn('cover-image', rd_opf(os.path.join(d, 'book', 'Il Faro a Orologeria.epub')))

    def test_migrate_v1(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, 'v1_temp'); os.makedirs(d)
            wr(os.path.join(d, 'chunk0001.md'), '# 1\n\nThe Brass Warden sang.\n')
            wr(os.path.join(d, 'output_chunk0001.md'), '# 1\n\nIl Custode d’Ottone cantava.\n')
            jw(os.path.join(d, 'progetto.json'), {'lingua': 'it', 'lingua_nome': 'italiano', 'gruppo': 3,
                                                  'revisione': 'completa', 'motore': 'codex',
                                                  'sostituzioni': [{'re': 'x', 'con': 'y'}],
                                                  'vietate': [{'re': 'Buff', 'msg': 'bonus'}]})
            jw(os.path.join(d, 'glossario.json'), [{'source': 'Brass Warden', 'target': 'Custode d’Ottone',
                                                    'tipo': 'V', 'nota': 'n', 'alias': []}])
            jw(os.path.join(d, 'stato.json'), {'fatte': [1], 'meta_integrati': [1], 'da_rivedere': {},
                                               'rivedute': [], 'conflitti_v': []})
            wr(os.path.join(d, 'regole.md'), '## Regole\n')
            r = run(['migrate.py', d], tmp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            p = jl(os.path.join(d, 'project.json'))
            self.assertEqual((p['target_lang'], p['target_lang_name'], p['review'], p['group_size']),
                             ('it', 'Italian', 'full', 3))
            self.assertEqual(p['replacements'], [{'re': 'x', 'with': 'y'}])
            self.assertEqual(p['forbidden'][0]['msg'], 'bonus')
            self.assertEqual(jl(os.path.join(d, 'terms.json'))[0]['type'], 'fixed')
            self.assertEqual(jl(os.path.join(d, 'state.json'))['done'], [1])
            self.assertTrue(os.path.exists(os.path.join(d, 'rules.md')))
            self.assertTrue(os.path.exists(os.path.join(d, '_v1_backup', 'progetto.json')))
            self.assertFalse(os.path.exists(os.path.join(d, 'progetto.json')))
            self.assertEqual(run(['finish.py'], d).returncode, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
