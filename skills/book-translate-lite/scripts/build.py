#!/usr/bin/env python3
"""Merge the translated parts and build EPUB, DOCX and PDF.

Usage:  build.py [--title "Translated title"] [--formats epub,docx,pdf] [--out FOLDER]
                 [--cover img.jpg] [--partial]

- EPUB and DOCX with pandoc: correct language (target_lang from project.json), full table of
  contents (one chapter per # heading), small caps, quotes, notes; system messages (paragraphs
  that are entirely bold) are boxed for genre gamelit or with project.json "system_boxes": true.
- PDF with Calibre (ebook-convert) from the EPUB.
- --partial: build even if parts are missing (stops at the first missing one).
- Title page: title, subtitle, author and rights from project.json (`btl config subtitle="…" rights="…"`).
- Cover: images/cover.* or --cover; if neither exists and the original book is an EPUB, its cover is
  extracted to images/cover.<ext> automatically.
- Scene breaks: an ornament image followed by a text break (`* * *`) is shown once — the image in
  EPUB/PDF, the text in DOCX (pandoc cannot put SVG ornaments into DOCX without rsvg-convert).
Default output: <working folder>/book/<title>.<format>
"""
import argparse, glob, os, re, shutil, subprocess, sys, zipfile
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import common as C

CALIBRE = [shutil.which('ebook-convert') or '', '/Applications/calibre.app/Contents/MacOS/ebook-convert',
           '/usr/bin/ebook-convert', 'C:\\Program Files\\Calibre2\\ebook-convert.exe']

TEXT_BREAK = r'(?:\\?\*[ \t]*\\?\*[ \t]*\\?\*|\\?-[ \t]*\\?-[ \t]*\\?-|⁂)'
BREAK_IMG = r'!\[[^\]]*\]\([^)]*\)(?:\{[^}]*\})?'


def scene_breaks(text):
    """Return (text for EPUB/PDF, text for DOCX) with doubled scene breaks collapsed.

    Some EPUBs mark a scene break with an ornament image plus a text fallback (`* * *`); after
    conversion both are visible. Keep the image for EPUB/PDF and the text for DOCX."""
    pair = re.compile(r'(?m)^(' + BREAK_IMG + r')[ \t]*\n(?:[ \t]*\n)*[ \t]*' + TEXT_BREAK + r'[ \t]*$')
    epub = pair.sub(lambda m: m.group(1), text)
    docx = pair.sub('\\* \\* \\*', text)
    # ornament images without a text fallback: in DOCX an SVG ornament would be dropped
    docx = re.sub(r'(?m)^!\[[^\]]*\]\([^)]*\.svg\)\{[^}]*(?:break|ornament)[^}]*\}[ \t]*$', '\\* \\* \\*', docx)
    return epub, docx


def source_path(d, cfg):
    s = cfg.get('source') or ''
    if not s:
        return None
    if os.path.isabs(s):
        return s if os.path.exists(s) else None
    p = d
    while True:                      # relative paths may be relative to any parent folder
        if os.path.exists(os.path.join(p, s)):
            return os.path.join(p, s)
        if os.path.dirname(p) == p:
            return None
        p = os.path.dirname(p)


def epub_cover(epub, dest_dir):
    """Extract the cover image of an EPUB to dest_dir/cover.<ext>; return the path or None."""
    try:
        with zipfile.ZipFile(epub) as z:
            cont = ET.fromstring(z.read('META-INF/container.xml'))
            opf = next(e.get('full-path') for e in cont.iter() if e.tag.endswith('rootfile'))
            root = ET.fromstring(z.read(opf))
            items = [e for e in root.iter() if e.tag.endswith('}item') or e.tag == 'item']
            href = next((i.get('href') for i in items if 'cover-image' in (i.get('properties') or '')), None)
            if not href:
                cid = next((m.get('content') for m in root.iter()
                            if m.tag.endswith('meta') and m.get('name') == 'cover'), None)
                href = next((i.get('href') for i in items if cid and i.get('id') == cid), None)
            if not href:
                href = next((i.get('href') for i in items if (i.get('media-type') or '').startswith('image/')
                             and 'cover' in (i.get('id', '') + i.get('href', '')).lower()), None)
            if not href:
                return None
            from urllib.parse import unquote
            name = os.path.normpath(os.path.join(os.path.dirname(opf), unquote(href))).replace(os.sep, '/')
            ext = os.path.splitext(name)[1].lower() or '.jpg'
            os.makedirs(dest_dir, exist_ok=True)
            out = os.path.join(dest_dir, 'cover' + ext)
            with open(out, 'wb') as f:
                f.write(z.read(name))
            return out
    except (KeyError, StopIteration, zipfile.BadZipFile, ET.ParseError, OSError):
        return None


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
    text, text_docx = scene_breaks(text)
    md = os.path.join(d, 'book.md'); md_docx = os.path.join(d, 'book_docx.md')
    C.write(md, text)
    out = os.path.abspath(o.out or os.path.join(d, 'book')); os.makedirs(out, exist_ok=True)
    title = o.title or cfg.get('title') or 'Book'; author = cfg.get('author') or ''
    lang = cfg['target_lang'] or 'en'
    name = re.sub(r'[/:\\]', '-', title)
    cover = o.cover or next(iter(sorted(glob.glob(os.path.join(d, 'images', 'cover.*')))), None)
    src = source_path(d, cfg)
    if not cover and src and src.lower().endswith('.epub'):
        cover = epub_cover(src, os.path.join(d, 'images'))
        if cover:
            print(f'Cover taken from the original EPUB: {os.path.relpath(cover, d)}')
    toc_title = cfg.get('toc_title') or C.languages().get(lang, {}).get('toc_title', 'Contents')
    raw = C.jload(os.path.join(d, 'project.json'), {}) or {}
    boxes = raw.get('system_boxes')
    if boxes is None:                 # boxed system messages are a game-fiction convention
        boxes = raw.get('genre') in (None, 'gamelit')       # (None: projects made before genres)
    base = ['pandoc', md, '-f', 'markdown', '--resource-path', d] \
        + (['--lua-filter', os.path.join(C.TEMPLATES, 'system.lua')] if boxes else []) + [
            '-M', f'title={title}', '-M', f'lang={lang}', '--toc', '--toc-depth=2', '-M', f'toc-title={toc_title}']
    if author:
        base += ['-M', f'author={author}']
    for k in ('subtitle', 'rights'):
        if cfg.get(k):
            base += ['-M', f'{k}={cfg[k]}']
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
        C.write(md_docx, text_docx)
        r = subprocess.run([md_docx if x == md else x for x in base] + ['-o', docx],
                           capture_output=True, text=True, cwd=d)
        os.remove(md_docx)
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
