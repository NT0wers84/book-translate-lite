#!/usr/bin/env python3
"""Unisce le parti tradotte e crea EPUB, DOCX e PDF.

Uso:  build.py [--titolo "Titolo tradotto"] [--formati epub,docx,pdf] [--out CARTELLA] [--cover img.jpg] [--parziale]

- EPUB e DOCX con pandoc: lingua corretta (lang da progetto.json), sommario completo
  (un capitolo per ogni titolo #), CSS con riquadro per i messaggi di sistema
  (paragrafi interamente in grassetto), maiuscoletto, citazioni, note.
- PDF con Calibre (ebook-convert) a partire dall'EPUB.
- --parziale: costruisce anche se mancano parti (si ferma alla prima mancante).
Uscita predefinita: <cartella di lavoro>/libro/<titolo>.<formato>
"""
import argparse, glob, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import comune as C

M = os.path.join(C.SKILL, 'modelli')
CALIBRE = [shutil.which('ebook-convert') or '', '/Applications/calibre.app/Contents/MacOS/ebook-convert',
           '/usr/bin/ebook-convert']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--formati', default='epub,docx,pdf'); ap.add_argument('--out')
    ap.add_argument('--cover'); ap.add_argument('--titolo'); ap.add_argument('--parziale', action='store_true'); ap.add_argument('--dir')
    o = ap.parse_args(); d = C.trova_dir(o.dir); cfg = C.progetto(d); tot = C.n_parti(d)
    mancanti = [n for n in range(1, tot + 1) if not C.tradotta(d, n)]
    if mancanti and not o.parziale:
        sys.exit(f'ERRORE: mancano {len(mancanti)} parti (prima: {mancanti[0]:04d}). Usa --parziale per una prova.')
    fino = (mancanti[0] - 1) if mancanti else tot
    testo = '\n\n'.join(C.leggi(C.out_path(d, n)).strip() for n in range(1, fino + 1)) + '\n'
    md = os.path.join(d, 'libro.md')
    open(md, 'w', encoding='utf-8').write(testo)
    out = os.path.abspath(o.out or os.path.join(d, 'libro')); os.makedirs(out, exist_ok=True)
    titolo = o.titolo or cfg.get('titolo') or 'Libro'; autore = cfg.get('autore') or ''
    nome = re.sub(r'[/:\\]', '-', titolo)
    cover = o.cover or next(iter(sorted(glob.glob(os.path.join(d, 'images', 'cover.*')))), None)
    base = ['pandoc', md, '-f', 'markdown', '--resource-path', d, '--lua-filter', os.path.join(M, 'sistema.lua'),
            '-M', f'title={titolo}', '-M', f'lang={cfg["lingua"]}', '--toc', '--toc-depth=2']
    if autore:
        base += ['-M', f'author={autore}']
    fatti = []
    formati = o.formati.split(',')
    epub = os.path.join(out, nome + '.epub')
    if 'epub' in formati or 'pdf' in formati:
        cmd = base + ['-o', epub, '--split-level=1', '--css', os.path.join(M, 'stile.css'),
                      '-M', f'toc-title={"Sommario" if cfg["lingua"] == "it" else "Contents"}']
        if cover:
            cmd += ['--epub-cover-image', cover]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=d)
        if r.returncode:
            sys.exit('ERRORE pandoc (epub): ' + r.stderr[-1500:])
        fatti.append(epub)
    if 'docx' in formati:
        docx = os.path.join(out, nome + '.docx')
        r = subprocess.run(base + ['-o', docx], capture_output=True, text=True, cwd=d)
        print('ERRORE pandoc (docx): ' + r.stderr[-800:]) if r.returncode else fatti.append(docx)
    if 'pdf' in formati:
        cal = next((c for c in CALIBRE if c and os.path.exists(c)), None)
        if not cal:
            print('PDF saltato: Calibre (ebook-convert) non trovato.')
        else:
            pdf = os.path.join(out, nome + '.pdf')
            r = subprocess.run([cal, epub, pdf, '--pdf-page-numbers', '--paper-size', 'a5',
                                '--pdf-default-font-size', '12', '--pdf-page-margin-left', '50',
                                '--pdf-page-margin-right', '50', '--language', cfg['lingua']],
                               capture_output=True, text=True, timeout=1800)
            print('ERRORE Calibre (pdf): ' + (r.stderr or r.stdout)[-800:]) if r.returncode else fatti.append(pdf)
    if 'epub' not in formati and os.path.exists(epub):
        os.remove(epub); fatti.remove(epub)
    capitoli = len(re.findall(r'(?m)^# ', testo))
    print(f'Parti 1–{fino} di {tot} · {capitoli} capitoli nel sommario · lingua {cfg["lingua"]}')
    for f in fatti:
        print(f'  {f} ({os.path.getsize(f) // 1024} KB)')


if __name__ == '__main__':
    main()
