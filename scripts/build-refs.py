#!/usr/bin/env python3
"""Build references.json from cataleg.pdf.

One entry per price-table page: {p: page, g: groupIdx, f: family, c: [codes]}.
Run from the pdf-viewer-demo directory:  python3 scripts/build-refs.py

Done offline (PyMuPDF) because pdf.js splits code tokens inconsistently in the
browser, whereas fitz reads each code whole and reliably. Re-run whenever
cataleg.pdf changes.
"""
import fitz, re, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF  = os.path.join(HERE, 'cataleg.pdf')
OUT  = os.path.join(HERE, 'references.json')
OUT_TEXT = os.path.join(HERE, 'search-text.json')

# First PDF page of each group (must match the GROUPS array in index.html).
GROUP_STARTS = [2, 47, 65, 93, 151, 207, 248, 286, 342, 391, 425, 498, 590, 662, 733, 817]

def group_idx(p):
    g = 0
    for i, s in enumerate(GROUP_STARTS):
        if p >= s: g = i
        else: break
    return g

# A price-table page has a MOD./COD. (or COD.) column header and a € column.
def has_table(t):
    return bool(re.search(r'MOD\./COD\.|(?:^|\s)COD\.(?:\s|$)', t)) and ('€' in t)

# A reference code: 7-8 alphanumeric chars, starts with a digit, >=5 digits.
CODE_RE = re.compile(r'^[0-9][0-9A-Z]{6,7}$')
# WxDxH (o WxD en taules d'accessoris/plaques): números de 3-4 xifres, així
# no confon potències ("2x7,5"), pesos ni preus.
DIMS_RE = re.compile(r'^(\d{3,4})x(\d{3,4})(x\d{3,4})?$', re.I)

# Order codes by their position in the actual price table, not by PDF reading
# order — a code's caption near its product photo is often read by fitz
# BEFORE the table row that repeats it, which scrambled the widget/table order
# relative to what's visually printed. We locate the table column(s) (tight,
# evenly-spaced rows at a consistent x — as opposed to the widely-spaced
# per-photo captions above) and read them top-to-bottom, left-to-right.
# Returns [(code, dims)] where dims is the WxDxH cell found on the code's
# table row ('' if none) — powers the dimension search in the viewer.
def codes(doc, pno):
    d = doc[pno - 1].get_text('dict')
    items = []  # (x, y, code)
    all_lines = []  # (x, y, text) — for same-row dims lookup
    for b in d['blocks']:
        for ln in b.get('lines', []):
            text = ''.join(sp['text'] for sp in ln['spans'])
            t = text.strip()
            if t:
                all_lines.append((ln['bbox'][0], ln['bbox'][1], t))
            c = t.replace(' ', '').upper()
            if CODE_RE.match(c) and len(re.findall(r'[0-9]', c)) >= 5:
                items.append((ln['bbox'][0], ln['bbox'][1], c))
    if not items:
        return []

    def dims_at(x, y):
        for lx, ly, lt in all_lines:
            if lx > x + 5 and abs(ly - y) < 4 and DIMS_RE.match(lt.replace(' ', '')):
                return lt.replace(' ', '').lower()
        return ''

    # Cluster into x-columns (tolerant of the few px of jitter between rows).
    items.sort(key=lambda t: t[0])
    cols = []
    for x, y, c in items:
        if cols and x - cols[-1]['x'] <= 4:
            cols[-1]['items'].append((y, c))
            cols[-1]['x'] = x
        else:
            cols.append({'x': x, 'items': [(y, c)]})

    # A genuine table column has >=2 rows with tight (line-height) y-gaps;
    # photo captions stacked in the same visual column are spaced much wider
    # (image height apart).
    table_items, caption_items = [], []
    for col in cols:
        rows = sorted(col['items'], key=lambda t: t[0])
        gaps = [rows[i + 1][0] - rows[i][0] for i in range(len(rows) - 1)]
        is_table = len(rows) >= 2 and gaps and max(gaps) <= 30
        for y, c in rows:
            (table_items if is_table else caption_items).append((y, col['x'], c))

    # Row-major order across table column(s) — same-row entries (e.g. two
    # model variants side by side) share a y-band and sort left-to-right.
    table_items.sort(key=lambda t: (round(t[0] / 6), t[1]))
    out, seen = [], set()
    for y, x, c in table_items:
        if c not in seen:
            seen.add(c); out.append((c, dims_at(x, y)))
    # Codes seen only in captions (no matching table row) are appended after,
    # in their natural top-to-bottom order.
    caption_items.sort(key=lambda t: (t[0], t[1]))
    for y, x, c in caption_items:
        if c not in seen:
            seen.add(c); out.append((c, dims_at(x, y)))
    return out

def is_heading(s):
    s = s.strip()
    if len(s) < 5 or len(s) > 70: return False
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 4: return False
    if sum(1 for c in letters if c.isupper()) / len(letters) < 0.9: return False
    U = s.upper()
    if U[:2] in ('E ', 'F ', 'D '): return False
    if any(k in U for k in ('GRUPO','PAG','SIMBOLOG','CARACTER','GENERAL','FEATURES','MOD','COD')):
        return False
    return True

# Family = topmost uppercase heading on the page (by coordinates, not reading order).
def family(doc, pno):
    d = doc[pno - 1].get_text('dict')
    H = doc[pno - 1].rect.height
    lines = {}
    for b in d['blocks']:
        for ln in b.get('lines', []):
            y = ln['bbox'][1]
            if y > H * 0.18: continue
            e = lines.setdefault(round(y / 2), {'y': y, 'p': []})
            for sp in ln['spans']:
                e['p'].append((sp['bbox'][0], sp['text']))
    best = None
    for e in lines.values():
        s = re.sub(r'\s+', ' ', ' '.join(t for _, t in sorted(e['p']))).strip()
        if is_heading(s) and (best is None or e['y'] < best[0]):
            best = (e['y'], s)
    return best[1] if best else ''

def main():
    doc = fitz.open(PDF)
    pages = []        # references (table pages only)
    text_pages = []   # full text of every page, for the fallback search
    for p in range(1, doc.page_count + 1):
        t = doc[p - 1].get_text('text')
        text_pages.append({'p': p, 'g': group_idx(p), 't': t})
        if not has_table(t): continue
        cs = codes(doc, p)
        if not cs: continue
        pages.append({'p': p, 'g': group_idx(p), 'f': family(doc, p),
                      'c': [c for c, _ in cs], 'd': [dm for _, dm in cs]})

    json.dump({'v': 6, 'pages': pages}, open(OUT, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    json.dump({'v': 1, 'pages': text_pages}, open(OUT_TEXT, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print(f'{len(pages)} table pages, {sum(len(x["c"]) for x in pages)} refs → {OUT} '
          f'({os.path.getsize(OUT)//1024} KB)')
    print(f'{len(text_pages)} text pages → {OUT_TEXT} '
          f'({os.path.getsize(OUT_TEXT)//1024} KB)')

if __name__ == '__main__':
    main()
