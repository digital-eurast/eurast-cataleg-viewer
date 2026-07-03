#!/bin/bash
# Update catalog.pdf processing pipeline: refs → relations → CSV export.
# Run from project root or let this script cd there automatically.

set -euo pipefail

# Navigate to project root (parent of this script's directory)
cd "$(dirname "$0")/.."

# Validate that cataleg.pdf exists
if [ ! -f "cataleg.pdf" ]; then
    echo "Error: cataleg.pdf no trobat a l'arrel del projecte"
    exit 1
fi

echo "Processant cataleg.pdf..."
echo ""

# PyMuPDF (fitz) instal·lat en aquest Mac és el wheel x86_64: en arm64 falla
# amb "ImportError ... incompatible architecture (have 'x86_64', need
# 'arm64')". El prefix arch el fa córrer sota Rosetta 2.
echo "1. Construint references.json (x86_64)..."
arch -x86_64 python3 scripts/build-refs.py
echo ""

echo "2. Construint relations.json (x86_64)..."
arch -x86_64 python3 scripts/build-relations.py
echo ""

echo "3. Exportant relacions a CSV..."
python3 scripts/export-relacions-csv.py
echo ""

echo "4. Validant JSON..."
python3 -m json.tool references.json > /dev/null && echo "   references.json: OK"
python3 -m json.tool search-text.json > /dev/null && echo "   search-text.json: OK"
python3 -m json.tool relations.json > /dev/null && echo "   relations.json: OK"
echo ""

echo "5. Canvis detectats:"
git diff --stat -- references.json search-text.json relations.json
echo ""

echo "Passos següents:"
echo "  1. Revisar els canvis: git diff --stat"
echo "  2. Provar en local: python3 -m http.server 7788  →  http://localhost:7788"
echo "  3. Quan estigui verificat, fer commit de cataleg.pdf + references.json"
echo "     + search-text.json + relations.json, i push (amb aprovació)."
