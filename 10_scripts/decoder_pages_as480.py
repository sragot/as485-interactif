#!/usr/bin/env python3
"""Phase 4 (consolidation) — Décodage de la page phare AS480 (centres jeunesse).

Remplit libelle / unite / theme / page_titre / epoque dans
30_dictionnaires/codes_as.csv pour la page 04 de l'AS480 (rapport général des
centres jeunesse — AS-480 G), à partir de la transcription du gabarit officiel :
  - Archives/AS480/2014-2015/Formulaire-AS-480G-2014-15.pdf, page 04 (coin « 04 »)
  - en-têtes de colonnes confirmés directement sur les données (colonne `entete`
    de 20_canonique/AS480/as480_unifie.parquet).

PAGE 04 « INFORMATION VENTILÉE EN FONCTION DES ALINÉAS DES ARTICLES 38 ET 38.1
DE LA L.P.J. (REGROUPÉS PAR PROBLÉMATIQUE) ». C'est la page phare de protection
de la jeunesse : nombre de signalements retenus, évaluations et orientations,
ventilés par problématique (négligence, abus physique, abus sexuel, trouble de
comportement, abandon, mauvais traitements psychologiques, total).

PÉRIMÈTRE (lignes 01-14, colonnes 1-7) : vérifié sur as480_unifie, ces 14 lignes ×
7 colonnes sont présentes à l'identique sur TOUT l'historique 2010-2011 →
2022-2023, y compris à travers la rupture de source 2013-2014 (dépivotage des
années 2010-2014 vs harmonisation 2014+). Les en-têtes de colonnes sont identiques.
On étiquette donc epoque = "stable".

NON DÉCODÉ (volontaire) : la ligne 15, qui n'apparaît qu'à un seul exercice
(2018-2019) sur un gabarit non transcrit ici — laissée sans libellé.

UNITÉS HÉTÉROGÈNES : certaines lignes sont des comptes (signalements, évaluations…)
et d'autres des durées moyennes (jours ou mois). L'unité est renseignée ligne par
ligne pour que les agrégats de la base traitent correctement chaque cas (somme pour
les comptes, moyenne pour les durées).

Usage :
    python 10_scripts/decoder_pages_as480.py --dico 30_dictionnaires/codes_as.csv
"""
from __future__ import annotations

import argparse

import pandas as pd

# ---------------------------------------------------------------------------
# Colonnes = problématiques (en-tête officiel, confirmé sur la colonne `entete`)
# ---------------------------------------------------------------------------
COLS_PROB = {
    1: "Négligence", 2: "Abus physique", 3: "Abus sexuel",
    4: "Trouble de comportement", 5: "Abandon",
    6: "Mauvais traitements psychologiques", 7: "Total (Art. 38 et Art. 38.1)",
}

# ---------------------------------------------------------------------------
# Page 04 — lignes transcrites du gabarit MSSS (Formulaire AS-480 G 2014-2015).
# (libellé, unité) : l'unité pilote l'agrégation (somme vs moyenne).
# ---------------------------------------------------------------------------
PAGE_04 = {
    "page": "04",
    "page_titre": ("INFORMATION VENTILÉE EN FONCTION DES ALINÉAS DES ARTICLES 38 "
                   "ET 38.1 DE LA L.P.J. (REGROUPÉS PAR PROBLÉMATIQUE)"),
    "theme": "Signalements et évaluation (LPJ)",
    "cols": COLS_PROB,
    "lignes": {
        1:  ("Nombre de signalements retenus", "signalements"),
        2:  ("Durée moyenne entre la rétention des signalements et le premier contact", "jours"),
        3:  ("Durée moyenne entre la réception des signalements et la fin de l'évaluation", "jours"),
        4:  ("Nombre moyen d'enfants en attente d'évaluation", "usagers"),
        5:  ("Évaluations terminées durant l'année : sécurité/développement compromis", "évaluations"),
        6:  ("Évaluations terminées durant l'année : sécurité/développement non compromis", "évaluations"),
        7:  ("Évaluations terminées durant l'année : fermeture pour autres raisons", "évaluations"),
        8:  ("Durée moyenne des évaluations terminées durant l'année à partir du premier contact", "jours"),
        9:  ("Nombre d'orientations réalisées", "orientations"),
        10: ("Durée moyenne des orientations réalisées : sans intervention judiciaire", "jours"),
        11: ("Durée moyenne des orientations réalisées : avec intervention judiciaire", "jours"),
        12: ("Nombre de nouvelles applications de mesures", "applications"),
        13: ("Durée moyenne d'attente à l'application des mesures", "jours"),
        14: ("Durée moyenne de l'application des mesures (en mois)", "mois"),
    },
}


def construire_lignes() -> list[dict]:
    """Aplati la page 04 en une entrée par (ligne, colonne)."""
    lignes = []
    p = PAGE_04
    for lg, (lg_lib, unite) in p["lignes"].items():
        for col, col_lib in p["cols"].items():
            code = f"P{p['page']}L{lg:02d}C{col:02d}"
            lignes.append({
                "code_cellule": code,
                "libelle": f"{lg_lib} — {col_lib}",
                "unite": unite,
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
    print(f"{len(maj)} codes décodés (AS480 page {PAGE_04['page']})")

    mask_cible = (d["formulaire"] == "AS480") & (d["page"] == PAGE_04["page"])
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

    manquants = set(d.loc[mask_cible, "code_cellule"]) - set(maj["code_cellule"])
    if manquants:
        print(f"[INFO] {len(manquants)} codes AS480 page 04 présents en données mais "
              f"NON décodés (hors périmètre stable, ex. ligne 15) : "
              f"{sorted(manquants)[:20]}")
    else:
        print("Couverture complète de la page 04.")


if __name__ == "__main__":
    main()
