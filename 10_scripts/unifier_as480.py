#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
unifier_as480.py
================
Fusionne les deux blocs AS480 en UNE vue unique (format long) :

  * 2014-15 -> 2022-23 : as480_harmonise.csv        (pipeline harmoniser_as480.py)
  * 2010-11 -> 2013-14 : as480_depivote_2010_2014.csv (pipeline depivoter_as480.py)

Schéma superset : toutes les colonnes canoniques de l'harmonisé + les trois
colonnes de provenance du dépivotage (col_index, entete, mapping) + une colonne
`origine` indiquant le pipeline source de chaque ligne. Les lignes harmonisées
ont col_index/entete vides et mapping = "canonique_plc".

ATTENTION — non-comparabilité des codes P/L/C à travers 2014
------------------------------------------------------------
Le formulaire AS480 a été RESTRUCTURÉ entre 2013-14 et 2014-15 (pages P06/P07/
P13/P16 présentes avant, absentes après ; réorganisation des lignes/colonnes).
Les couples (page, ligne, colonne) — et donc `plc`/`code_cellule` — NE sont
PAS comparables d'un bloc à l'autre. Pour toute analyse de série temporelle
franchissant 2014, s'appuyer sur le sens métier (colonne `entete` côté pivoté,
dictionnaire de cellules côté harmonisé) et non sur le code P/L/C brut. La
colonne `origine` permet de filtrer/segmenter proprement les deux régimes.

Rappels sur le bloc pivoté (voir depivoter_as480.py) :
  - `etablissement_id` vide (absent des sources 2010-14) ; seuls rss + nom.
  - ~6 % des cellules (onglets multi-colonnes empaquetés) sans P/L/C numérique,
    identifiées par mapping = "entete_seule" (l'en-tête reste la clé sûre).
  - AS480A limité à 3 lignes de la page 5 sur ces années (rapport Autochtones
    complet indisponible avant 2014-15).

Sortie : 20_canonique/AS480/as480_unifie.csv (UTF-8-BOM) + .parquet
Les fichiers sources ne sont pas modifiés.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parent.parent

# Colonnes canoniques de l'harmonisé, dans l'ordre, + extras pivot + origine.
COLS_CANON = [
    "exercice", "exercice_debut", "rapport", "sous_formulaire", "rss",
    "etablissement_id", "etablissement_nom", "page", "souspage",
    "ligne", "colonne", "plc", "valeur_saisie", "chiffre",
    "code_cellule", "source_feuille",
]
COLS_EXTRA = ["col_index", "entete", "mapping"]
ORDRE_FINAL = ["origine"] + COLS_CANON + COLS_EXTRA


def main() -> int:
    ap = argparse.ArgumentParser(description="Unifie AS480 harmonisé + dépivoté.")
    ap.add_argument("--root", default=str(RACINE))
    args = ap.parse_args()
    outdir = Path(args.root) / "20_canonique" / "AS480"

    f_harm = outdir / "as480_harmonise.csv"
    f_dep = outdir / "as480_depivote_2010_2014.csv"
    for f in (f_harm, f_dep):
        if not f.is_file():
            print(f"Fichier source manquant : {f}", file=sys.stderr)
            return 1

    harm = pd.read_csv(f_harm, dtype=str)
    dep = pd.read_csv(f_dep, dtype=str)

    harm["origine"] = "harmonise_2014plus"
    dep["origine"] = "depivote_2010_2014"

    # Bloc harmonisé : ajouter les colonnes extra (vides) ; mapping canonique.
    for c in COLS_EXTRA:
        if c not in harm.columns:
            harm[c] = ""
    harm["mapping"] = "canonique_plc"

    # Bloc pivoté : la colonne `feuille` double source_feuille -> on la retire.
    if "feuille" in dep.columns:
        dep = dep.drop(columns=["feuille"])

    # Aligner strictement sur l'ordre final (colonnes manquantes -> vides).
    for df in (harm, dep):
        for c in ORDRE_FINAL:
            if c not in df.columns:
                df[c] = ""

    uni = pd.concat([dep[ORDRE_FINAL], harm[ORDRE_FINAL]], ignore_index=True)

    # Tri stable : par exercice, sous-formulaire, rss, page.
    uni = uni.sort_values(
        ["exercice", "sous_formulaire", "rss", "page"],
        kind="stable", na_position="last"
    ).reset_index(drop=True)

    csv_path = outdir / "as480_unifie.csv"
    uni.to_csv(csv_path, index=False, encoding="utf-8-sig")
    try:
        uni.to_parquet(outdir / "as480_unifie.parquet", index=False)
    except Exception as e:
        print(f"  [info] parquet non écrit ({e})")

    # ---- vérifications ----
    attendu = len(harm) + len(dep)
    ok = len(uni) == attendu
    print(f"Écrit : {csv_path}")
    print(f"Lignes : harmonisé {len(harm)} + dépivoté {len(dep)} = {attendu} "
          f"-> unifié {len(uni)}  [{'OK' if ok else 'ÉCART'}]")
    print("Par origine :", uni.origine.value_counts().to_dict())
    print("Exercices    :", sorted(uni.exercice.unique()))
    print("Sous-formul. :", uni.sous_formulaire.value_counts().to_dict())
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
