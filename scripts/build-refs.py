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
def codes(t):
    out = []
    for line in t.split('\n'):
        c = line.strip().replace(' ', '').upper()
        if CODE_RE.match(c) and len(re.findall(r'[0-9]', c)) >= 5:
            out.append(c)
    return list(dict.fromkeys(out))

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
        cs = codes(t)
        if not cs: continue
        pages.append({'p': p, 'g': group_idx(p), 'f': family(doc, p), 'c': cs})

    json.dump({'v': 5, 'pages': pages}, open(OUT, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    json.dump({'v': 1, 'pages': text_pages}, open(OUT_TEXT, 'w', encoding='utf-8'),
              ensure_ascii=False, separators=(',', ':'))
    print(f'{len(pages)} table pages, {sum(len(x["c"]) for x in pages)} refs → {OUT} '
          f'({os.path.getsize(OUT)//1024} KB)')
    print(f'{len(text_pages)} text pages → {OUT_TEXT} '
          f'({os.path.getsize(OUT_TEXT)//1024} KB)')

if __name__ == '__main__':
    main()
