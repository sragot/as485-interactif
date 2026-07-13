#!/usr/bin/env python3
"""Phase 7 — Génère le dashboard HTML autonome à partir du template + des
données exportées de la base (10_scripts/exporter_dashboard_data.py).

Le dashboard produit ne dépend d'aucune ressource externe (pas de CDN) :
tout le CSS/JS/données est inline, il s'ouvre directement dans un navigateur.

Usage :
    python 10_scripts/generer_dashboard.py \
        --template 50_publication/dashboard_as485_template.html \
        --donnees 50_publication/donnees_dashboard.json \
        --out 50_publication/dashboard_as485.html
"""
from __future__ import annotations

import argparse


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default="50_publication/dashboard_as485_template.html")
    ap.add_argument("--donnees", default="50_publication/donnees_dashboard.json")
    ap.add_argument("--out", default="50_publication/dashboard_as485.html")
    args = ap.parse_args()

    with open(args.template, "r", encoding="utf-8") as f:
        template = f.read()
    with open(args.donnees, "r", encoding="utf-8") as f:
        donnees_json = f.read()

    if "__DONNEES_JSON__" not in template:
        raise SystemExit("Placeholder __DONNEES_JSON__ introuvable dans le template.")

    html = template.replace("__DONNEES_JSON__", donnees_json)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[LIVRABLE] {args.out}  ({len(html):,} caractères)")


if __name__ == "__main__":
    main()
