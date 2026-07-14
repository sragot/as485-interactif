#!/usr/bin/env python3
"""Phase 4 (consolidation) — Décodage de la page phare AS484 (déficience physique).

Remplit libelle / unite / theme / page_titre / epoque dans
30_dictionnaires/codes_as.csv pour la page 09 de l'AS484 (Centres de réadaptation
pour personnes ayant une déficience physique — CRDP), à partir de la transcription
du gabarit officiel MSSS :
  - Archives/AS484/2014-2015/AS-484-2014-15-EXPLICATIONS.pdf (définitions lignes)
  - en-tête d'âge (colonnes) confirmé sur le formulaire 2014-2015 (pages « par
    groupe d'âge »), identique à la convention AS485.

RUPTURE 2013-2014 (point de vigilance) : l'AS484 a été restructuré en 2013-2014.
La page 09 « ADMIS EN CRDP PAR GROUPE D'ÂGE » (GESTRED page 90) n'existe QUE de
2013-2014 à aujourd'hui ; l'ancienne génération (2010-2013) portait cet indicateur
sur des pages à identifiant distinct (09T/09B/09C/09E/09F, ventilé par nature de
déficience). Comme les identifiants de page diffèrent, il n'y a AUCUNE collision de
code_cellule : « P09Lxx Cyy » ne désigne toujours que la structure post-2013.
On étiquette donc ces codes epoque = "depuis_2013".

Usage :
    python 10_scripts/decoder_pages_as484.py --dico 30_dictionnaires/codes_as.csv
"""
from __future__ import annotations

import argparse

import pandas as pd

# ---------------------------------------------------------------------------
# Colonnes = groupes d'âge (en-tête officiel, convention MSSS partagée AS484/AS485)
# ---------------------------------------------------------------------------
COLS_AGE9 = {
    1: "0-4 ans", 2: "5-11 ans", 3: "12-17 ans", 4: "18-21 ans",
    5: "22-44 ans", 6: "45-64 ans", 7: "65-74 ans", 8: "75 ans et plus",
    9: "Total (C.1 à C.8)",
}

# ---------------------------------------------------------------------------
# Page 09 (GESTRED page 90) — lignes transcrites des EXPLICATIONS AS-484 2014-2015
# ---------------------------------------------------------------------------
PAGE_09 = {
    "page": "09",
    "page_titre": ("NOMBRE D'USAGERS DIFFÉRENTS ADMIS EN CRDP ENTRE LE 1ER AVRIL "
                   "ET LE 31 MARS PAR GROUPE D'ÂGE"),
    "theme": "Usagers admis",
    "cols": COLS_AGE9,
    "lignes": {
        1:  "Usagers au début de l'année (1er avril)",
        2:  "Admissions durant l'année",
        3:  "Total (L.01 + L.02)",
        4:  "Départs durant l'année",
        5:  "Décès",
        6:  "Total (L.04 + L.05)",
        7:  "Usagers à la fin de l'année (L.03 − L.06)",
        8:  "Répartis : Hommes",
        9:  "Répartis : Femmes",
        10: "Organisme payeur : Agence de la santé et des services sociaux",
        11: "Organisme payeur : Santé Canada, Anciens Combattants, Défense ou autre organisme fédéral",
        12: "Organisme payeur : Commission de la santé et de la sécurité du travail (CSST)",
        13: "Organisme payeur : Fonds de l'assurance automobile du Québec (SAAQ)",
        14: "Organisme payeur : Un autre organisme",
        15: "Non-résident du Québec : touriste ou nouveau résident d'une autre province",
        16: "Non-résident du Québec : sans droit légal de demeurer au Canada",
    },
}


def construire_lignes() -> list[dict]:
    """Aplati la page 09 en une entrée par (ligne, colonne)."""
    lignes = []
    p = PAGE_09
    for lg, lg_lib in p["lignes"].items():
        for col, col_lib in p["cols"].items():
            code = f"P{p['page']}L{lg:02d}C{col:02d}"
            lignes.append({
                "code_cellule": code,
                "libelle": f"{lg_lib} — {col_lib}",
                "unite": "usagers",
                "theme": p["theme"],
                "page_titre": p["page_titre"],
                "epoque": "depuis_2013",
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
    print(f"{len(maj)} codes décodés (AS484 page {PAGE_09['page']})")

    mask_cible = (d["formulaire"] == "AS484") & (d["page"] == PAGE_09["page"])
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

    n_cible = int(mask_cible.sum())
    manquants = set(d.loc[mask_cible, "code_cellule"]) - set(maj["code_cellule"])
    if manquants:
        print(f"[ATTENTION] {len(manquants)} codes AS484 page 09 présents en données "
              f"mais NON couverts par le gabarit : {sorted(manquants)[:20]}")
    else:
        print(f"Couverture complète : {n_cible}/{n_cible} codes AS484 page 09 décodés.")


if __name__ == "__main__":
    main()
