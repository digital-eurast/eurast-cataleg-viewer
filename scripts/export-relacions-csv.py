#!/usr/bin/env python3
"""Export relations to CSV: sobretaula+suport=kit pricing analysis for the team.

Generates relacions-g4-g5.csv from relations.json and references.json.
Run after build-relations.py when cataleg.pdf has been updated.
"""
import json, csv, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REL  = os.path.join(HERE, 'relations.json')
REFS = os.path.join(HERE, 'references.json')
OUT  = os.path.join(HERE, 'relacions-g4-g5.csv')

def price(p):
    """'1.695' -> 1695"""
    try:
        return int(p.replace('.', ''))
    except:
        return None

def main():
    rel  = json.load(open(REL))['items']
    refs = json.load(open(REFS))['pages']
    fam = {}
    for pg in refs:
        for c in pg['c']:
            fam.setdefault(c, pg['f'])

    V = {'open': 'obert', 'doors': 'portes', 'drawers': 'calaixos'}
    rows = []
    for code, it in rel.items():
        if it['t'] != 'top':
            continue
        mounted = [rc for rc, k in it['rel'] if k == 'mounted']
        if not mounted:
            continue
        m = rel[mounted[0]]
        sups = [(rc, rel[rc]) for rc, k in it['rel'] if k == 'support']
        sups.sort(key=lambda s: (s[1].get('v') != 'open', price(s[1]['pr']) or 0))
        sup_code, sup = (sups[0] if sups else (None, None))
        pt = price(it['pr'])
        ps = price(sup['pr']) if sup else None
        pk = price(m['pr'])
        grup = 'G04' if it['pg'] < 151 else 'G05'
        rows.append({
            'grup': grup,
            'familia': fam.get(code, ''),
            'sobretaula_ref': code,
            'sobretaula_dims': it['d'],
            'sobretaula_preu': pt,
            'sobretaula_pag': it['pg'],
            'suport_ref': sup_code or '',
            'suport_tipus': V.get(sup.get('v'), '') if sup else '',
            'suport_dims': sup['d'] if sup else '',
            'suport_preu': ps if sup else '',
            'suport_pag': sup['pg'] if sup else '',
            'kit_ref': mounted[0],
            'kit_dims': m['d'],
            'kit_preu': pk,
            'kit_pag': m['pg'],
            'suma_sobretaula_suport': (pt + ps) if (pt and ps) else '',
            'diferencia_kit_vs_suma': (pk - pt - ps) if (pt and ps and pk) else '',
        })

    rows.sort(key=lambda r: (r['grup'], r['sobretaula_pag'], r['sobretaula_ref']))
    with open(OUT, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=';')
        w.writeheader()
        w.writerows(rows)
    print(len(rows), 'files → relacions-g4-g5.csv')

if __name__ == '__main__':
    main()
