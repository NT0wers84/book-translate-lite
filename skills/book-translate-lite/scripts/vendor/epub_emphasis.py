#!/usr/bin/env python3
"""Keep bold and italics that an EPUB sets through CSS classes.

Many publishers mark emphasis with classes (`<span class="c12">`, `<p class="sys">`) whose stylesheet
says `font-weight: bold` or `font-style: italic`, instead of `<b>`/`<i>`. Calibre's HTMLZ output keeps
the classes but pandoc ignores CSS, so all that emphasis would vanish from the Markdown and from the
translated book. `restyle_epub()` writes a copy of the EPUB where those elements get real
`<strong>`/`<em>` around their content; the conversion then reads the copy.

Only simple selectors are read (`.cls`, `tag.cls`) plus inline `style=""`. Headings are left alone
(they are bold anyway). Block containers (div, section, blockquote…) pass their style down to the
paragraphs inside them, so the tags never wrap block elements. A `<b>`/`<i>` already inside a wrapped
element is dropped, so pandoc never sees nested emphasis of the same kind.

Usage: epub_emphasis.py IN.epub OUT.epub   (prints the number of elements made bold / italic)
"""
import re, sys, zipfile
from html.parser import HTMLParser

HEADINGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
CONTAINERS = {'html', 'body', 'div', 'section', 'article', 'aside', 'blockquote', 'figure', 'header',
              'footer', 'main', 'nav', 'ul', 'ol', 'dl', 'table', 'thead', 'tbody', 'tfoot', 'tr'}
VOID = {'br', 'img', 'hr', 'meta', 'link', 'input', 'col', 'area', 'base', 'wbr', 'source'}
BOLD_TAGS, ITAL_TAGS = {'b', 'strong'}, {'i', 'em'}


def declared(body):
    """(bold, italic) a CSS declaration block sets: True, False (explicitly normal) or None."""
    b = i = None
    for prop, val in re.findall(r'([\w-]+)\s*:\s*([^;]+)', body):
        prop, val = prop.lower(), val.lower()
        if prop == 'font-weight':
            v = val.strip()
            b = v in ('bold', 'bolder') or (v.isdigit() and int(v) >= 600)
        elif prop == 'font-style':
            i = 'italic' in val or 'oblique' in val
        elif prop == 'font':
            if re.search(r'\b(bold|bolder|[6-9]00)\b', val):
                b = True
            if re.search(r'\b(italic|oblique)\b', val):
                i = True
    return b, i


def class_styles(css):
    """{class: (bold, italic)} from the simple class selectors of a stylesheet."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    css = re.sub(r'@media[^{]*\{((?:[^{}]*\{[^}]*\})*)\s*\}', r'\1', css)
    out = {}
    for sels, body in re.findall(r'([^{}@]+)\{([^}]*)\}', css):
        b, i = declared(body)
        if b is None and i is None:
            continue
        for sel in sels.split(','):
            m = re.fullmatch(r'\s*(?:[a-zA-Z][\w-]*)?\.([\w-]+)\s*', sel)
            if m:
                ob, oi = out.get(m.group(1), (None, None))
                out[m.group(1)] = (ob if b is None else b, oi if i is None else i)
    return out


class _Rewriter(HTMLParser):
    def __init__(self, styles):
        super().__init__(convert_charrefs=False)
        self.styles, self.out, self.stack = styles, [], []
        self.count = [0, 0]

    def _state(self):
        # (bold applied, italic applied, bold pending, italic pending)
        return self.stack[-1][2] if self.stack else (False, False, False, False)

    def _want(self, tag, attrs):
        b = i = None
        for c in (dict(attrs).get('class') or '').split():
            cb, ci = self.styles.get(c, (None, None))
            b = cb if cb is not None else b
            i = ci if ci is not None else i
        sb, si = declared(dict(attrs).get('style') or '')
        b = sb if sb is not None else b
        i = si if si is not None else i
        if tag in HEADINGS:
            b = None
        return b, i

    def handle_starttag(self, tag, attrs):
        ab, ai, pb, pi = self._state()
        if (tag in BOLD_TAGS and ab) or (tag in ITAL_TAGS and ai):
            self.stack.append((tag, None, (ab, ai, pb, pi)))       # dropped: already inside that emphasis
            return
        raw = self.get_starttag_text()
        self.out.append(raw)
        if tag in VOID:
            return
        b, i = self._want(tag, attrs)
        wb = pb if b is None else b
        wi = pi if i is None else i
        if tag in CONTAINERS:
            self.stack.append((tag, [], (ab, ai, wb and not ab, wi and not ai)))
            return
        opened = []
        if wb and not ab:
            opened.append('strong'); self.count[0] += 1
        if wi and not ai:
            opened.append('em'); self.count[1] += 1
        self.out.extend(f'<{t}>' for t in opened)
        self.stack.append((tag, opened, (ab or 'strong' in opened, ai or 'em' in opened, False, False)))

    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if not any(t == tag for t, _, _ in self.stack):
            self.out.append(f'</{tag}>')
            return
        while self.stack:
            t, opened, _ = self.stack.pop()
            if opened is not None:
                self.out.extend(f'</{x}>' for x in reversed(opened))
                self.out.append(f'</{t}>')
            if t == tag:
                break

    def handle_data(self, d): self.out.append(d)
    def handle_entityref(self, n): self.out.append(f'&{n};')
    def handle_charref(self, n): self.out.append(f'&#{n};')
    def handle_comment(self, d): self.out.append(f'<!--{d}-->')
    def handle_decl(self, d): self.out.append(f'<!{d}>')
    def handle_pi(self, d): self.out.append(f'<?{d}>')
    def unknown_decl(self, d): self.out.append(f'<![{d}]>')


def restyle_html(html, styles):
    """Return (html, bold_count, italic_count) with class/inline-styled emphasis made explicit."""
    css = ' '.join(re.findall(r'<style[^>]*>(.*?)</style>', html, flags=re.S | re.I))
    if css:
        styles = dict(styles, **class_styles(css))
    p = _Rewriter(styles)
    p.feed(html)
    p.close()
    return ''.join(p.out), p.count[0], p.count[1]


def restyle_epub(src, dst):
    """Copy EPUB `src` to `dst` with CSS-styled emphasis turned into <strong>/<em>. Returns (bold, italic)."""
    with zipfile.ZipFile(src) as z:
        names = z.namelist()
        styles = {}
        for n in names:
            if n.lower().endswith('.css'):
                styles.update(class_styles(z.read(n).decode('utf-8', 'replace')))
        tb = ti = 0
        with zipfile.ZipFile(dst, 'w') as w:
            for info in z.infolist():
                data = z.read(info.filename)
                if info.filename.lower().endswith(('.xhtml', '.html', '.htm')):
                    try:
                        text = data.decode('utf-8')
                    except UnicodeDecodeError:
                        text = None
                    if text is not None:
                        new, b, i = restyle_html(text, styles)
                        if b or i:
                            data, tb, ti = new.encode('utf-8'), tb + b, ti + i
                kind = zipfile.ZIP_STORED if info.filename == 'mimetype' else zipfile.ZIP_DEFLATED
                w.writestr(info, data, compress_type=kind)
    return tb, ti


if __name__ == '__main__':
    print(*restyle_epub(sys.argv[1], sys.argv[2]))
