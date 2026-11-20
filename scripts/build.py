#!/usr/bin/env python3
"""Merge the translated parts and build EPUB, DOCX and PDF.

Usage:  build.py [--title "Translated title"] [--formats epub,docx,pdf] [--out FOLDER]
                 [--cover img.jpg] [--partial]

- EPUB and DOCX with pandoc: correct language (target_lang from project.json), full table of
  contents (one chapter per # heading), CSS with a box for system messages (paragraphs that
  are entirely bold), small caps, quotes, notes.
- PDF with Calibre (ebook-convert) from the EPUB.
- --partial: build even if parts are missing (stops at the first missing one).
Default output: <working folder>/book/<title>.<format>
"""
import argparse, glob, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as C

CALIBRE = [shutil.which('ebook-convert') or '', '/Applications/calibre.app/Contents/MacOS/ebook-convert',
           '/usr/bin/ebook-convert', 'C:\\Program Files\\Calibre2\\ebook-convert.exe']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--formats'); ap.add_argument('--out'); ap.add_argument('--title')
    ap.add_argument('--cover'); ap.add_argument('--partial', action='store_true'); ap.add_argument('--dir')
    o = ap.parse_args(); d = C.find_dir(o.dir); cfg = C.project(d); tot = C.n_parts(d)
    missing = [n for n in range(1, tot + 1) if not C.translated(d, n)]
    if missing and not o.partial:
        sys.exit(f'ERROR: {len(missing)} parts missing (first: {missing[0]:04d}). Use --partial for a preview.')
    upto = (missing[0] - 1) if missing else tot
    text = '\n\n'.join(C.read(C.out_path(d, n)).strip() for n in range(1, upto + 1)) + '\n'
    md = os.path.join(d, 'book.md')
    C.write(md, text)
    out = os.path.abspath(o.out or os.path.join(d, 'book')); os.makedirs(out, exist_ok=True)
    title = o.title or cfg.get('title') or 'Book'; author = cfg.get('author') or ''
    lang = cfg['target_lang'] or 'en'
    name = re.sub(r'[/:\\]', '-', title)
    cover = o.cover or next(iter(sorted(glob.glob(os.path.join(d, 'images', 'cover.*')))), None)
    toc_title = cfg.get('toc_title') or C.languages().get(lang, {}).get('toc_title', 'Contents')
    base = ['pandoc', md, '-f', 'markdown', '--resource-path', d,
            '--lua-filter', os.path.join(C.TEMPLATES, 'system.lua'),
            '-M', f'title={title}', '-M', f'lang={lang}', '--toc', '--toc-depth=2', '-M', f'toc-title={toc_title}']
    if author:
        base += ['-M', f'author={author}']
    made = []
    formats = (o.formats or cfg['formats']).split(',')
    epub = os.path.join(out, name + '.epub')
    if 'epub' in formats or 'pdf' in formats:
        cmd = base + ['-o', epub, '--split-level=1', '--css', os.path.join(C.TEMPLATES, 'style.css')]
        if cover:
            cmd += ['--epub-cover-image', cover]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=d)
        if r.returncode:
            sys.exit('ERROR pandoc (epub): ' + r.stderr[-1500:])
        made.append(epub)
    if 'docx' in formats:
        docx = os.path.join(out, name + '.docx')
        r = subprocess.run(base + ['-o', docx], capture_output=True, text=True, cwd=d)
        print('ERROR pandoc (docx): ' + r.stderr[-800:]) if r.returncode else made.append(docx)
    if 'pdf' in formats:
        cal = next((c for c in CALIBRE if c and os.path.exists(c)), None)
        if not cal:
            print('PDF skipped: Calibre (ebook-convert) not found.')
        else:
            pdf = os.path.join(out, name + '.pdf')
            r = subprocess.run([cal, epub, pdf, '--pdf-page-numbers', '--paper-size', 'a5',
                                '--pdf-default-font-size', '12', '--pdf-page-margin-left', '50',
                                '--pdf-page-margin-right', '50', '--language', lang],
                               capture_output=True, text=True, timeout=1800)
            print('ERROR Calibre (pdf): ' + (r.stderr or r.stdout)[-800:]) if r.returncode else made.append(pdf)
    if 'epub' not in formats and os.path.exists(epub):
        os.remove(epub); made.remove(epub)
    chapters = len(re.findall(r'(?m)^# ', text))
    print(f'Parts 1–{upto} of {tot} · {chapters} chapters in the table of contents · language {lang}')
    for f in made:
        print(f'  {f} ({os.path.getsize(f) // 1024} KB)')


if __name__ == '__main__':
    main()
