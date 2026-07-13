#!/usr/bin/env python3
"""Phase 4 — Décodage ligne/colonne des pages de démo AS485 (09,10,17,18,19,20).

Remplit libelle / unite / theme / epoque dans 30_dictionnaires/codes_as.csv pour
les codes de ces 6 pages, à partir de la transcription du gabarit MSSS
(Archives/AS485/2013-2014/AS-485-2013-14-FORMULAIRE.pdf +
 AS-485-2013-14-EXPLICATIONS.pdf).

Point de vigilance (voir 10_scripts/prompts/PHASE4_prompt.md) : l'ensemble des
code_cellule de ces 6 pages a été vérifié stable sur tout 2013-2014 → 2022-2023
(seules des données manquantes certaines années, jamais de code_cellule
supplémentaire ou renommé) -> epoque = "stable" pour ces codes, un seul mapping
(référence 2013-2014) couvre toute la période.

Usage :
    python 10_scripts/decoder_pages_demo_as485.py --dico 30_dictionnaires/codes_as.csv
"""
from __future__ import annotations

import argparse

import pandas as pd

# ---------------------------------------------------------------------------
# Jeux de colonnes
# ---------------------------------------------------------------------------
COLS_AGE9 = {
    1: "0-4 ans", 2: "5-11 ans", 3: "12-17 ans", 4: "18-21 ans",
    5: "22-44 ans", 6: "45-64 ans", 7: "65-74 ans", 8: "75 ans et plus",
    9: "Total (C.1 à C.8)",
}
COLS_AGE6 = {
    1: "1 an", 2: "2 ans", 3: "3 ans", 4: "4 ans", 5: "5 ans",
    6: "Total (C.1 à C.5)",
}
COLS_NOMBRE1 = {1: "Nombre"}

# ---------------------------------------------------------------------------
# Structure des 6 pages de démo (source : gabarit MSSS AS-485 2013-2014,
# vérifié stable jusqu'en 2022-2023 pour ces pages précises)
# Chaque page = liste de blocs (titre_bloc, jeu_de_colonnes, {ligne: libelle_ligne})
# ---------------------------------------------------------------------------
PAGES = {
    "09": {
        "page_titre": "RÉPARTITION DES USAGERS DESSERVIS PAR SOUS-CENTRE D'ACTIVITÉS DU 1ER AVRIL AU 31 MARS",
        "theme": "Usagers desservis",
        "blocs": [
            ("Accueil, évaluation et orientation DITED (s-c/a 8001)", COLS_AGE9, {
                1: "Usagers desservis durant l'année",
                2: "Répartis : masculin",
                3: "Répartis : féminin",
                4: "Nombre total de HPS",
                5: "Nombre de demandes traitées",
            }),
            ("Services d'adaptation et de réadaptation à la personne - DITED", COLS_AGE9, {
                6: "Usagers différents desservis durant l'année",
                7: "Répartis : masculin",
                8: "Répartis : féminin",
                9: "Départs durant l'année",
                10: "Nombre total de HPS",
            }),
            ("Services d'adaptation et de réadaptation à la personne - DI (s-c/a 8051)", COLS_AGE9, {
                11: "Usagers desservis durant l'année",
                12: "Répartis : masculin",
                13: "Répartis : féminin",
                14: "Départs durant l'année",
                15: "Nombre total de HPS",
            }),
            ("Services d'intervention comportementale intensive - TED (s-c/a 8052)", COLS_AGE6, {
                16: "Enfants desservis durant l'année",
                17: "Nombre d'heures totales d'intervention comportementale intensive",
                18: "Nombre de semaines totales d'intervention comportementale intensive",
                19: "Répartis : masculin",
                20: "Répartis : féminin",
                21: "Départs durant l'année",
            }),
            ("Services d'adaptation et de réadaptation à la personne - TED (s-c/a 8053)", COLS_AGE9, {
                22: "Usagers desservis durant l'année",
                23: "Répartis : masculin",
                24: "Répartis : féminin",
                25: "Départs durant l'année",
                26: "Nombre total de HPS",
            }),
        ],
    },
    "10": {
        "page_titre": "RÉPARTITION DES USAGERS DESSERVIS AU 31 MARS SELON LE LIEU DE RÉSIDENCE",
        "theme": "Usagers desservis",
        "blocs": [
            ("Lieu de résidence des usagers (DITED) desservis le 31 mars", COLS_AGE9, {
                1: "Milieu naturel (parents)",
                2: "Milieu naturel (autonome)",
                3: "Ressources non institutionnelles (RNI) gérée par un autre établissement",
                4: "Autres RNI gérée par le CR",
                5: "Ressource résidentielle avec assistance résidentielle continue (RRAC)",
                6: "Ressource résidentielle avec allocations pour assistance résidentielle continue (RRAAC)",
                7: "Admis dans un autre établissement",
                8: "Ressource intermédiaire (RI)",
                9: "Ressource de type familial (RTF)",
                10: "Internat",
                11: "Foyer de groupe",
                12: "Autres",
                13: "Total (L.01 à L.12)",
            }),
            ("Services d'assistance éducative spécialisée à la famille et aux proches DITED (s-c/a 6910)", COLS_NOMBRE1, {
                14: "Dossiers durant l'année",
                15: "Distribution des heures de prestations de services (HPS)",
            }),
            ("Services de soutien spécialisé aux partenaires DITED (s-c/a 6920)", COLS_NOMBRE1, {
                16: "Dossiers durant l'année",
                17: "Distribution des heures de prestations de services (HPS)",
            }),
        ],
    },
    "17": {
        "page_titre": "NOMBRE D'USAGERS DIFFÉRENTS NE RECEVANT AUCUN SERVICE DU CRDITED POUR TOUS LES PROGRAMMES AU 31 MARS — USAGERS EN ATTENTE D'UN SERVICE AU 31 MARS",
        "theme": "Listes d'attente",
        "blocs": [
            ("Déficience intellectuelle (DI)", COLS_AGE9, {
                1: "Nombre de personnes", 2: "Délai moyen (jours)", 3: "Délai médian (jours)",
            }),
            ("Trouble envahissant du développement (TED)", COLS_AGE9, {
                4: "Nombre de personnes", 5: "Délai moyen (jours)", 6: "Délai médian (jours)",
            }),
            ("Total DI-TED", COLS_AGE9, {
                7: "Total du nombre de personnes (L.01+L.04)",
                8: "Total délai moyen (L.02+L.05)",
                9: "Total délai médian (L.03+L.06)",
            }),
        ],
    },
    "18": {
        "page_titre": "NOMBRE D'USAGERS EN ATTENTE D'UN SERVICE EN DI AU 31 MARS",
        "theme": "Listes d'attente",
        "blocs": [
            ("Services d'adaptation et de réadaptation en contexte d'intégration communautaire (s-c/a 7001)", COLS_AGE9, {
                1: "Nombre de personnes", 2: "Délai moyen (jours)", 3: "Délai médian (jours)",
            }),
            ("Service d'intégration au travail (s-c/a 7011-7024-7025-7031)", COLS_AGE9, {
                4: "Nombre de personnes", 5: "Délai moyen (jours)", 6: "Délai médian (jours)",
            }),
            ("Services d'intégration résidentielle (s-c/a 5516,5526,5536,5546,6945,6983,7041,7051)", COLS_AGE9, {
                7: "Nombre de personnes", 8: "Délai moyen (jours)", 9: "Délai médian (jours)",
            }),
            ("Services d'adaptation et de réadaptation à la personne (s-c/a 8051)", COLS_AGE9, {
                10: "Nombre de personnes", 11: "Délai moyen (jours)", 12: "Délai médian (jours)",
            }),
            ("Total en DI", COLS_AGE9, {
                13: "Total du nombre de personnes (L.01+L.04+L.07+L.10)",
                14: "Total du délai moyen (L.02+L.05+L.08+L.11)",
                15: "Total du délai médian (L.03+L.06+L.09+L.12)",
            }),
        ],
    },
    "19": {
        "page_titre": "NOMBRE D'USAGERS EN ATTENTE D'UN SERVICE AVEC UN TED AU 31 MARS",
        "theme": "Listes d'attente",
        "blocs": [
            ("Services d'adaptation et de réadaptation en contexte d'intégration communautaire (s-c/a 7001)", COLS_AGE9, {
                1: "Nombre de personnes", 2: "Délai moyen (jours)", 3: "Délai médian (jours)",
            }),
            ("Service d'intégration au travail (s-c/a 7011-7024-7025-7031)", COLS_AGE9, {
                4: "Nombre de personnes", 5: "Délai moyen (jours)", 6: "Délai médian (jours)",
            }),
            ("Services d'intégration résidentielle (s-c/a 5516,5526,5536,5546,6945,6983,7041,7051)", COLS_AGE9, {
                7: "Nombre de personnes", 8: "Délai moyen (jours)", 9: "Délai médian (jours)",
            }),
            ("Services d'adaptation et de réadaptation à la personne (s-c/a 8052 et 8053)", COLS_AGE9, {
                10: "Nombre de personnes", 11: "Délai moyen (jours)", 12: "Délai médian (jours)",
            }),
            ("Total", COLS_AGE9, {
                13: "Total du nombre de personnes (L.01+L.04+L.07+L.10)",
                14: "Total du délai moyen (L.02+L.05+L.08+L.11)",
                15: "Total du délai médian (L.03+L.06+L.09+L.12)",
            }),
        ],
    },
    "20": {
        "page_titre": "DÉLAI D'ATTENTE DES USAGERS DIFFÉRENTS AYANT OBTENU UN PREMIER SERVICE",
        "theme": "Listes d'attente",
        "blocs": [
            ("Attente d'admissions — Internat-DI", COLS_AGE9, {
                1: "Nombre d'usagers", 2: "Délai moyen (jours)", 3: "Délai médian (jours)",
            }),
            ("Attente d'admissions — Internat-TED", COLS_AGE9, {
                4: "Nombre d'usagers", 5: "Délai moyen (jours)", 6: "Délai médian (jours)",
            }),
            ("Attente d'admissions — Foyer de groupe-DI", COLS_AGE9, {
                7: "Nombre d'usagers", 8: "Délai moyen (jours)", 9: "Délai médian (jours)",
            }),
            ("Attente d'admissions — Foyer de groupe-TED", COLS_AGE9, {
                10: "Nombre d'usagers", 11: "Délai moyen (jours)", 12: "Délai médian (jours)",
            }),
            ("Attente d'admissions — Total", COLS_AGE9, {
                13: "Total nombre d'usagers (L.01+L.04+L.07+L.10)",
                14: "Total délai moyen (L.02+L.05+L.08+L.11)",
                15: "Total délai médian (L.03+L.06+L.09+L.12)",
            }),
            ("Attente d'inscriptions — DI", COLS_AGE9, {
                16: "Nombre d'usagers", 17: "Délai moyen (jours)", 18: "Délai médian (jours)",
            }),
            ("Attente d'inscriptions — TED", COLS_AGE9, {
                19: "Nombre d'usagers", 20: "Délai moyen (jours)", 21: "Délai médian (jours)",
            }),
            ("Attente d'inscriptions — Total", COLS_AGE9, {
                22: "Total nombre d'usagers (L.16+L.19)",
                23: "Total délai moyen (L.17+L.20)",
                24: "Total délai médian (L.18+L.21)",
            }),
        ],
    },
}


def _unite(ligne_libelle: str) -> str:
    l = ligne_libelle.lower()
    if "délai" in l:
        return "jours"
    if "hps" in l or "heures" in l:
        return "heures"
    if "semaines" in l:
        return "semaines"
    if "dossiers" in l:
        return "dossiers"
    return "usagers"


def construire_lignes() -> list[dict]:
    """Aplati PAGES en une ligne par (page, ligne, colonne)."""
    lignes = []
    for page, info in PAGES.items():
        for bloc_titre, cols, lignes_bloc in info["blocs"]:
            for ligne, ligne_libelle in lignes_bloc.items():
                for col, col_libelle in cols.items():
                    code_cellule = f"P{page}L{ligne:02d}C{col:02d}"
                    libelle = f"{bloc_titre} — {ligne_libelle} — {col_libelle}"
                    lignes.append({
                        "code_cellule": code_cellule,
                        "libelle": libelle,
                        "unite": _unite(ligne_libelle),
                        "theme": info["theme"],
                        "page_titre": info["page_titre"],
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
    print(f"{len(maj)} codes décodés (pages {sorted(PAGES)})")

    mask_cible = (d["formulaire"] == "AS485") & (d["page"].isin(PAGES))
    idx_par_code = {c: i for i, c in zip(d.index[mask_cible], d.loc[mask_cible, "code_cellule"])}

    n_maj, n_absents = 0, []
    for _, row in maj.iterrows():
        i = idx_par_code.get(row["code_cellule"])
        if i is None:
            n_absents.append(row["code_cellule"])
            continue
        d.loc[i, "libelle"] = row["libelle"]
        d.loc[i, "unite"] = row["unite"]
        d.loc[i, "theme"] = row["theme"]
        d.loc[i, "page_titre"] = row["page_titre"]
        d.loc[i, "epoque"] = row["epoque"]
        n_maj += 1

    d.to_csv(args.dico, index=False, encoding="utf-8")

    print(f"\n{n_maj} lignes du dictionnaire mises à jour.")
    if n_absents:
        print(f"[ATTENTION] {len(n_absents)} code_cellule du gabarit absents du dictionnaire : {n_absents[:20]}")

    n_cible = int(mask_cible.sum())
    if n_maj != n_cible:
        manquants = set(d.loc[mask_cible, "code_cellule"]) - set(maj["code_cellule"])
        print(f"[ATTENTION] {n_cible - n_maj} codes du dictionnaire (pages démo) non couverts par le gabarit : "
              f"{sorted(manquants)[:20]}")
    else:
        print(f"Couverture complète : {n_cible}/{n_cible} codes des pages de démo décodés.")


if __name__ == "__main__":
    main()
