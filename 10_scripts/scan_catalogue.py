#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scan_catalogue.py
=================
Phase 1 — Inventaire machine-lisible de toutes les sources de données.

Parcourt les dossiers de données brutes, classe chaque fichier par FAMILLE et
EXERCICE, relève le format, la taille et une métrique de volume (lignes pour un
CSV, feuilles pour un XLSX, membres pour un ZIP), puis écrit un catalogue CSV.

Usage
-----
    python scan_catalogue.py                 # racine = dossier courant
    python scan_catalogue.py --root ".." --out "../00_catalogue/catalogue_sources.csv"
"""

from __future__ import annotations
import argparse
import csv
import re
import zipfile
from pathlib import Path

# Dossiers du projet (à NE PAS cataloguer comme sources).
DOSSIERS_PROJET = {
    "00_brut", "00_catalogue", "10_scripts", "20_canonique",
    "30_dictionnaires", "40_base", "50_publication",
    "AS485_repository", ".git",
}

EXT_DATA = {".csv", ".xlsx", ".xls", ".zip", ".pdf", ".doc", ".docx"}


def detecter_famille(rel: str) -> str:
    r = rel.replace("\\", "/")
    for f in ("AS478", "AS480", "AS481", "AS484", "AS485"):
        if f"/{f}/" in r or r.startswith(f"{f}/") or f"Archives/{f}" in r:
            return f
    if "Contours financiers" in r:
        return "Contours financiers"
    if "Dépenses par activités" in r or "Depenses" in r and "activ" in r.lower():
        return "Dépenses par activités"
    if "Dépenses par région" in r:
        return "Dépenses par région"
    if "/SAD/" in r or r.startswith("SAD/"):
        return "SAD"
    if "Stats usagers" in r:
        return "Stats usagers DI-TSA"
    if "Demographic Data" in r:
        return "Demographic Data"
    if "Archives" in r:
        return "Archives (autre)"
    return "Racine / divers"


def detecter_exercice(nom: str, chemin: str) -> str:
    texte = f"{chemin} {nom}"
    # Format long : 2014-2015 ou 2014_2015
    m = re.search(r"(20\d{2})[-_](20\d{2})", texte)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    # Format court accolé : 1516, 1617, 2324  -> 2015-2016 ...
    m = re.search(r"(?<!\d)(\d{2})(\d{2})(?!\d)", nom)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b == (a + 1) % 100 and 9 <= a <= 30:
            return f"20{a:02d}-20{b:02d}"
    # Année seule
    m = re.search(r"(?<!\d)(20\d{2})(?!\d)", texte)
    if m:
        return m.group(1)
    return ""


def metrique(p: Path, ext: str):
    """Retourne (type, valeur) selon le format ; tolérant aux erreurs."""
    try:
        if ext == ".csv":
            with open(p, "rb") as fh:
                n = sum(1 for _ in fh)
            return ("lignes", max(n - 1, 0))
        if ext in (".xlsx", ".xls"):
            import openpyxl
            wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
            n = len(wb.sheetnames)
            wb.close()
            return ("feuilles", n)
        if ext == ".zip":
            with zipfile.ZipFile(p) as z:
                return ("membres", len(z.namelist()))
    except Exception as e:
        return ("erreur", str(e)[:40])
    return ("", "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="Racine des données")
    ap.add_argument("--out", default="00_catalogue/catalogue_sources.csv")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    lignes = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        # sauter les dossiers de projet
        if rel.split("/", 1)[0] in DOSSIERS_PROJET:
            continue
        ext = p.suffix.lower()
        if ext not in EXT_DATA:
            continue
        mtype, mval = metrique(p, ext)
        lignes.append({
            "famille": detecter_famille(rel),
            "fichier": p.name,
            "chemin_relatif": rel,
            "exercice": detecter_exercice(p.name, rel),
            "format": ext.lstrip("."),
            "taille_ko": round(p.stat().st_size / 1024, 1),
            "metrique_type": mtype,
            "metrique_valeur": mval,
        })

    champs = ["famille", "fichier", "chemin_relatif", "exercice",
              "format", "taille_ko", "metrique_type", "metrique_valeur"]
    with open(out, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=champs)
        w.writeheader()
        w.writerows(lignes)

    # Résumé console
    from collections import Counter
    par_fam = Counter(l["famille"] for l in lignes)
    print(f"Catalogue écrit : {out}  ({len(lignes)} fichiers)")
    print("\nFichiers par famille :")
    for fam, n in sorted(par_fam.items(), key=lambda t: -t[1]):
        print(f"  {n:>4}  {fam}")
    total_ko = sum(l["taille_ko"] for l in lignes)
    print(f"\nTaille totale cataloguée : {total_ko/1024:.1f} Mo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
