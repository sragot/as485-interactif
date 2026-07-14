#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harmoniser_depenses.py — moule générique « tableaux larges » (large → long).

Réutilisable par les chantiers financiers 2-5 (dépenses par région / par
activités, SAD, contours financiers). Ce fichier fournit :

  * `depivoter_tableau_large(...)` : dépivote UNE feuille « programme × ligne »
    (colonnes = postes ; lignes = régions/CA/programmes) en table longue, en
    ignorant les colonnes de pourcentage et de total, avec rapport qualité.
  * un driver `main()` pour le **Chantier 3 — Dépenses par région** :
    feuille « Par région » des fichiers annuels de
    `Dépenses par région/dépenses/` (2013-2014 → 2022-2023).

Principe (cf. PLAN §4) :
  1. repérer la vraie ligne d'en-tête (ici : juste au-dessus de « RSS 01 ») ;
  2. dépivoter les colonnes de postes → lignes, une colonne `montant` ;
  3. normaliser les libellés + déduire l'`exercice` du nom de fichier ;
  4. rapport qualité par fichier (postes, régions, total, écart vs GRAND TOTAL).

Zéro chiffre inventé : toute perte de lignes ou tout écart au GRAND TOTAL de la
source est reporté dans `rapport_qualite.csv`.

Sortie Chantier 3 : 20_canonique/depenses_region/depenses_region_long.{parquet,csv}
                    + rapport_qualite.csv
"""
from __future__ import annotations
import re, sys, warnings
from pathlib import Path
import pandas as pd
import openpyxl

warnings.filterwarnings("ignore")

RACINE = Path(__file__).resolve().parents[1]
SRC_DIR = RACINE / "Dépenses par région" / "dépenses"
OUT = RACINE / "20_canonique" / "depenses_region"
JEU = "depenses_par_region"

# Noms des régions sociosanitaires (RSS) — référence publique MSSS.
RSS_NOMS = {
    1: "Bas-Saint-Laurent", 2: "Saguenay–Lac-Saint-Jean",
    3: "Capitale-Nationale", 4: "Mauricie et Centre-du-Québec",
    5: "Estrie", 6: "Montréal", 7: "Outaouais",
    8: "Abitibi-Témiscamingue", 9: "Côte-Nord", 10: "Nord-du-Québec",
    11: "Gaspésie–Îles-de-la-Madeleine", 12: "Chaudière-Appalaches",
    13: "Laval", 14: "Lanaudière", 15: "Laurentides", 16: "Montérégie",
    17: "Nunavik", 18: "Terres-Cries-de-la-Baie-James",
}

# Colonnes à ne jamais traiter comme un poste de dépense.
COLS_IGNOREES = {"%", "GRAND TOTAL", "TOTAL", ""}

# Fichiers du Chantier 3 -> exercice (le nom de fichier porte l'année de fin).
FICHIERS_REGION = {
    "Depenses-par-programme-et-par-region-2013-2014.xlsx": "2013-2014",
    "04-Contour-Financier-Depenses-prog-Regions-2014-15.xlsx": "2014-2015",
    "Depenses_par_programme_et_par_regions_1516.xlsx": "2015-2016",
    "depenses-par-programme-et-par-region-1617.xlsx": "2016-2017",
    "depenses-par-programme-et-par-region-1718.xlsx": "2017-2018",
    "depenses-par-programme-et-par-region-1819.xlsx": "2018-2019",
    "depenses-par-programme-et-par-region-1920.xlsx": "2019-2020",
    "depenses-par-programme-et-par-region-2021.xlsx": "2020-2021",
    "depenses-par-programme-et-par-region-2022.xlsx": "2021-2022",
    "depenses-par-programme-et-par-region-2023.xlsx": "2022-2023",
}


def _norm(s: str) -> str:
    """Normalise un libellé : espaces/retours-ligne compactés."""
    return re.sub(r"\s+", " ", str(s)).strip()


def depivoter_tableau_large(
    path: Path, exercice: str,
    motif_ligne: str = r"^RSS\s*(\d{2})\b",
    sheet: str | None = None,
):
    """Dépivote une feuille « postes en colonnes × entités en lignes ».

    - `motif_ligne` : regex sur la 1re colonne pour reconnaître une ligne de
      données ; le 1er groupe capture le code d'entité (ici le n° de RSS).
    - En-tête = la ligne juste au-dessus de la 1re ligne de données.
    Retourne (lignes: list[dict], rapport: dict).
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    if sheet is None:
        cand = [s for s in wb.sheetnames if "gion" in s.lower()]
        sheet = cand[0] if cand else wb.sheetnames[0]
    ws = wb[sheet]
    rows = list(ws.iter_rows(values_only=True))
    rx = re.compile(motif_ligne)

    # 1re ligne de données
    i_data0 = None
    for i, r in enumerate(rows):
        if r and isinstance(r[0], str) and rx.search(r[0].strip()):
            i_data0 = i
            break
    if i_data0 is None:
        return [], {"fichier": path.name, "exercice": exercice, "statut": "AUCUNE LIGNE RSS"}

    header = rows[i_data0 - 1]
    postes = {}  # col_index -> libellé normalisé
    col_grand_total = None
    for j, v in enumerate(header):
        if v in (None, ""):
            continue
        lib = _norm(v)
        if lib.upper() in {"GRAND TOTAL", "TOTAL", "TOTAL QUÉBEC"}:
            col_grand_total = j
            continue
        if lib in COLS_IGNOREES or lib == "%":
            continue
        postes[j] = lib

    lignes = []
    n_rss = 0
    somme_montants = 0.0
    ecart_grand_total = 0.0
    non_num = 0
    for r in rows[i_data0:]:
        if not (r and isinstance(r[0], str) and rx.search(r[0].strip())):
            continue
        m = rx.search(r[0].strip())
        rss = int(m.group(1))
        n_rss += 1
        somme_ligne = 0.0
        for j, poste in postes.items():
            val = r[j] if j < len(r) else None
            montant = pd.to_numeric(val, errors="coerce")
            if pd.isna(montant):
                if val not in (None, ""):
                    non_num += 1
                continue
            montant = float(montant)
            somme_ligne += montant
            somme_montants += montant
            lignes.append({
                "jeu": JEU, "exercice": exercice, "rss": rss,
                "region_nom": RSS_NOMS.get(rss, "Inconnu"),
                "programme": poste, "montant": montant,
            })
        # contrôle : somme des postes vs GRAND TOTAL de la source
        if col_grand_total is not None and col_grand_total < len(r):
            gt = pd.to_numeric(r[col_grand_total], errors="coerce")
            if not pd.isna(gt):
                ecart_grand_total += abs(somme_ligne - float(gt))

    rapport = {
        "fichier": path.name, "exercice": exercice, "statut": "OK",
        "n_postes": len(postes), "n_regions": n_rss,
        "n_lignes_long": len(lignes),
        "somme_montants": round(somme_montants, 2),
        "ecart_total_vs_grand_total": round(ecart_grand_total, 2),
        "valeurs_non_numeriques": non_num,
    }
    return lignes, rapport


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    toutes = []
    rapports = []
    for fichier, exercice in FICHIERS_REGION.items():
        path = SRC_DIR / fichier
        if not path.exists():
            rapports.append({"fichier": fichier, "exercice": exercice,
                             "statut": "FICHIER ABSENT"})
            continue
        lignes, rap = depivoter_tableau_large(path, exercice)
        toutes.extend(lignes)
        rapports.append(rap)

    long = pd.DataFrame(toutes).sort_values(
        ["exercice", "rss", "programme"]).reset_index(drop=True)
    long["montant"] = long["montant"].round(2)
    rap = pd.DataFrame(rapports)

    long.to_parquet(OUT / "depenses_region_long.parquet", index=False)
    long.to_csv(OUT / "depenses_region_long.csv", index=False, encoding="utf-8")
    rap.to_csv(OUT / "rapport_qualite.csv", index=False, encoding="utf-8")

    print(f"[OK] {len(long):,} lignes -> {OUT/'depenses_region_long.parquet'}")
    print("\n=== Rapport qualité ===")
    print(rap.to_string(index=False))
    ditsa = long[long.programme.str.contains("Déficience intellectuelle")]
    print("\n=== DI-TSA Québec par exercice (contrôle) ===")
    print(ditsa.groupby("exercice")["montant"].sum().apply(lambda v: f"{v:,.0f}").to_string())
    print("\nProgrammes:", sorted(long.programme.unique()))


if __name__ == "__main__":
    sys.exit(main())
