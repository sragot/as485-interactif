#!/usr/bin/env python3
"""Phase 4 — Extraction des codes de cellule distincts des tables canoniques AS.

Pour chaque formulaire AS harmonisé, produit la liste des `code_cellule`
distincts avec :
  - fréquence (nb de lignes),
  - nb de lignes avec une valeur numérique non nulle (signal d'utilisation réelle),
  - page / ligne / colonne décomposés,
  - un exemple de valeur,
  - nb d'exercices couverts + premier/dernier exercice.

Sortie : gabarit CSV à compléter à la main (libelle, unite, theme, page_titre).
C'est la base du dictionnaire de codes (Phase 4).

Usage :
    python 10_scripts/extraire_codes.py \
        --canonique 20_canonique \
        --out 30_dictionnaires/codes_as.csv
"""
from __future__ import annotations

import argparse
import glob
import os
import re

import pandas as pd

# Une seule table « de référence » par formulaire (on évite les doublons
# harmonise / unifie / depivote pour l'AS480).
PREFERES = {
    "AS478": "AS478/as478_harmonise.parquet",
    "AS480": "AS480/as480_unifie.parquet",  # version dépivotée + unifiée (couverture complète)
    "AS481": "AS481/as481_harmonise.parquet",
    "AS484": "AS484/as484_harmonise.parquet",
    "AS485": "AS485/as485_harmonise.parquet",
}

PLC_RE = re.compile(r"^P(?P<page>[0-9]+[A-Z]?)L(?P<ligne>[0-9]+)C(?P<colonne>[0-9]+)$")


def _formulaire(rapport: str) -> str:
    """AS480A / AS480B -> AS480 ; sinon inchangé."""
    m = re.match(r"^(AS\d{3})", str(rapport))
    return m.group(1) if m else str(rapport)


def extraire(parquet_path: str, formulaire: str) -> pd.DataFrame:
    df = pd.read_parquet(parquet_path)

    # valeur numérique exploitable
    chiffre = pd.to_numeric(df.get("chiffre"), errors="coerce")
    df = df.assign(_chiffre=chiffre, _nonzero=(chiffre.fillna(0) != 0))

    g = df.groupby("code_cellule", dropna=True)
    out = g.agg(
        freq=("code_cellule", "size"),
        n_nonzero=("_nonzero", "sum"),
        somme=("_chiffre", "sum"),
        exemple_valeur=("_chiffre", lambda s: next((v for v in s if pd.notna(v) and v != 0), pd.NA)),
        nb_exercices=("exercice", "nunique"),
        premier_exercice=("exercice", "min"),
        dernier_exercice=("exercice", "max"),
    ).reset_index()

    # décomposer le code
    comp = out["code_cellule"].str.extract(PLC_RE)
    out["page"] = comp["page"]
    out["ligne"] = pd.to_numeric(comp["ligne"], errors="coerce").astype("Int64")
    out["colonne"] = pd.to_numeric(comp["colonne"], errors="coerce").astype("Int64")
    out["formulaire"] = formulaire

    # colonnes à compléter à la main
    for c in ("libelle", "unite", "theme", "page_titre"):
        out[c] = pd.NA

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--canonique", default="20_canonique")
    ap.add_argument("--out", default="30_dictionnaires/codes_as.csv")
    args = ap.parse_args()

    frames = []
    for form, rel in PREFERES.items():
        path = os.path.join(args.canonique, rel)
        if not os.path.exists(path):
            print(f"[SKIP] {form}: introuvable {path}")
            continue
        f = extraire(path, form)
        frames.append(f)
        print(f"[OK] {form}: {len(f):>5} codes distincts  <-  {rel}")

    allc = pd.concat(frames, ignore_index=True)

    cols = [
        "formulaire", "code_cellule", "page", "ligne", "colonne",
        "freq", "n_nonzero", "somme", "exemple_valeur",
        "nb_exercices", "premier_exercice", "dernier_exercice",
        "libelle", "unite", "theme", "page_titre",
    ]
    allc = allc[cols].sort_values(
        ["formulaire", "n_nonzero", "freq"], ascending=[True, False, False]
    )

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    allc.to_csv(args.out, index=False, encoding="utf-8")
    print(f"\n[LIVRABLE] {args.out}  ({len(allc)} lignes)")

    # petit résumé console
    print("\nCodes distincts par formulaire :")
    print(allc.groupby("formulaire").size().to_string())


if __name__ == "__main__":
    main()
