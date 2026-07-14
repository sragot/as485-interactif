#!/usr/bin/env python3
"""Phase 4 (consolidation) — Décodage de la page phare AS481 (dépendance).

Remplit libelle / unite / theme / page_titre / epoque dans
30_dictionnaires/codes_as.csv pour la page 02 de l'AS481 (Centres de réadaptation
en dépendance — CRD), à partir de la transcription du gabarit officiel MSSS :
  - Archives/AS481/2014-2015/FORMULAIRE-AS-481-2014-15.pdf, page 02 (GESTRED 20)
  - Archives/AS481/2014-2015/Explication-Formul-AS-481-2014-1.pdf, NOTES PAGE 02
  - grille confirmée identique sur Archives/AS481/2012-2013/FORMULAIRE-AS-481-2012-13.pdf

PAGE 02 « USAGERS ADMIS – ALCOOL-DROGUES ET JEUX PATHOLOGIQUES ». Page sommaire
des mouvements d'usagers admis en CRD, ventilés par groupe d'âge, en deux blocs :
alcool-drogues (lignes 01-07) et jeux pathologiques (lignes 08-14).

PÉRIMÈTRE DÉCODÉ (lignes 01-14, colonnes 1-6) :
Ces 14 lignes × 6 colonnes d'âge forment le cœur stable de la page. Vérifié sur les
données (as481_harmonise) : lignes 01-14 présentes à l'identique pour TOUS les
exercices 2011-2012 à 2022-2023, avec les mêmes tranches d'âge sur les deux
gabarits (2012-2013 et 2014-2015). On étiquette donc epoque = "stable".

NON DÉCODÉ (volontaire, zéro invention) : les lignes 15-18. La ligne 15 (délai
moyen d'attente) a une sémantique de colonnes différente (types de substance, non
des âges) et une mise en page qui varie selon les années ; les lignes 16-18
n'apparaissent qu'à partir de 2016-2017 sur un gabarit non transcrit ici. Elles
restent sans libellé plutôt que d'être décodées de façon incertaine.

Usage :
    python 10_scripts/decoder_pages_as481.py --dico 30_dictionnaires/codes_as.csv
"""
from __future__ import annotations

import argparse

import pandas as pd

# ---------------------------------------------------------------------------
# Colonnes = groupes d'âge (en-tête officiel du gabarit AS-481 page 02)
# ---------------------------------------------------------------------------
COLS_AGE = {
    1: "0-17 ans", 2: "18-24 ans", 3: "25-39 ans", 4: "40-64 ans",
    5: "65 ans et plus", 6: "Total (C.1 à C.5)",
}

# ---------------------------------------------------------------------------
# Page 02 (GESTRED page 20) — deux blocs, lignes transcrites du gabarit MSSS
# ---------------------------------------------------------------------------
PAGE_02 = {
    "page": "02",
    "page_titre": "USAGERS ADMIS – ALCOOL-DROGUES ET JEUX PATHOLOGIQUES",
    "theme": "Usagers admis",
    "cols": COLS_AGE,
    # (bloc, libellé de ligne)
    "lignes": {
        1:  ("Alcool-drogues", "Nombre au début de l'année (1er avril)"),
        2:  ("Alcool-drogues", "Admissions durant l'année"),
        3:  ("Alcool-drogues", "Total (L.01 + L.02)"),
        4:  ("Alcool-drogues", "Nombre de sorties durant l'année"),
        5:  ("Alcool-drogues", "Nombre à la fin de l'année (L.03 − L.04)"),
        6:  ("Alcool-drogues", "Répartis : Hommes"),
        7:  ("Alcool-drogues", "Répartis : Femmes"),
        8:  ("Jeux pathologiques", "Nombre au début de l'année (1er avril)"),
        9:  ("Jeux pathologiques", "Admissions durant l'année"),
        10: ("Jeux pathologiques", "Total (L.08 + L.09)"),
        11: ("Jeux pathologiques", "Nombre de sorties durant l'année"),
        12: ("Jeux pathologiques", "Nombre à la fin de l'année (L.10 − L.11)"),
        13: ("Jeux pathologiques", "Répartis : Hommes"),
        14: ("Jeux pathologiques", "Répartis : Femmes"),
    },
}


def construire_lignes() -> list[dict]:
    """Aplati la page 02 en une entrée par (ligne, colonne)."""
    lignes = []
    p = PAGE_02
    for lg, (bloc, lg_lib) in p["lignes"].items():
        for col, col_lib in p["cols"].items():
            code = f"P{p['page']}L{lg:02d}C{col:02d}"
            lignes.append({
                "code_cellule": code,
                "libelle": f"{bloc} — {lg_lib} — {col_lib}",
                "unite": "usagers",
                "theme": p["theme"],
                "page_titre": p["page_titre"],
                "epoque": "stable",
            })
    return lignes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dico", default="30_dictionnaires/codes_as.csv")
    args = ap.parse_args()

    d = pd.read_csv(args.dico, dtype=str)
    if "epoque" not in d.columns:
        d["epoque"] = pd.NA

    maj = pd.DataFrame(construire_lignes())
    print(f"{len(maj)} codes décodés (AS481 page {PAGE_02['page']})")

    mask_cible = (d["formulaire"] == "AS481") & (d["page"] == PAGE_02["page"])
    idx_par_code = {c: i for i, c in zip(d.index[mask_cible], d.loc[mask_cible, "code_cellule"])}

    n_maj, n_absents = 0, []
    for _, row in maj.iterrows():
        i = idx_par_code.get(row["code_cellule"])
        if i is None:
            n_absents.append(row["code_cellule"])
            continue
        for col in ("libelle", "unite", "theme", "page_titre", "epoque"):
            d.loc[i, col] = row[col]
        n_maj += 1

    d.to_csv(args.dico, index=False, encoding="utf-8")

    print(f"\n{n_maj} lignes du dictionnaire mises à jour.")
    if n_absents:
        print(f"[INFO] {len(n_absents)} codes du gabarit absents des données "
              f"(cellules jamais saisies) : {n_absents[:20]}")

    # Codes présents en données mais volontairement non couverts (lignes 15-18).
    manquants = set(d.loc[mask_cible, "code_cellule"]) - set(maj["code_cellule"])
    if manquants:
        print(f"[INFO] {len(manquants)} codes AS481 page 02 présents en données mais "
              f"NON décodés (lignes 15-18, hors périmètre stable) : "
              f"{sorted(manquants)[:20]}")
    else:
        print("Couverture complète de la page 02.")


if __name__ == "__main__":
    main()
