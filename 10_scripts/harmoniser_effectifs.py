#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harmoniser_effectifs.py — Chantier 1 (effectifs démographiques dans le temps).

Reproduit la feuille « Population (historical) » de
`Demographic Data/Stats.xlsx` en table canonique LONGUE.

Modèle de données (rétro-ingénierie des formules SUMIFS de la feuille) :
  - Chaque feuille annuelle brute ('2010-2011' … '2022-2023') est un export
    AS-485 au niveau enregistrement. Colonnes utiles :
        col B  = RSS            (région sociosanitaire, 1..18)
        col E  = PLC            (code Page/Ligne/Colonne, ex. "P23L01C03")
        col K  = Chiffre        (valeur / effectif)
  - Effectifs DI / TSA par groupe d'âge :
        époque « ancien »  (2010-2011 → 2012-2013) : Page 04A/04B, Ligne 08
            DI  = P04AL08C{01..07}   TSA = P04BL08C{01..07}
        époque « nouveau » (2013-2014 → 2022-2023) : Page 23, Lignes 01/02
            DI  = P23L01C{01..09}    TSA = P23L02C{01..09}
    (rupture de maquette 2013 : la ventilation âge×déficience migre en P23,
     les tranches d'âge sont redécoupées).
  - « Tout le Québec » = somme de col K sur tous les établissements ; on
    conserve la ventilation par RSS.

Sorties : 20_canonique/effectifs/effectifs_long.{parquet,csv} + rapport_qualite.csv
"""
from __future__ import annotations
import sys, warnings
from pathlib import Path
import pandas as pd

warnings.filterwarnings("ignore")

RACINE = Path(__file__).resolve().parents[1]
SRC = RACINE / "Demographic Data" / "Stats.xlsx"
OUT = RACINE / "20_canonique" / "effectifs"
JEU = "effectifs_population_historique"

# --- Époque par exercice (fidèle au choix de la feuille source) -------------
EXERCICES = {
    "2010-2011": "ancien", "2011-2012": "ancien", "2012-2013": "ancien",
    "2013-2014": "nouveau", "2014-2015": "nouveau", "2015-2016": "nouveau",
    "2016-2017": "nouveau", "2017-2018": "nouveau", "2018-2019": "nouveau",
    "2019-2020": "nouveau", "2020-2021": "nouveau", "2021-2022": "nouveau",
    "2022-2023": "nouveau",
}

# --- Codes P/L par déficience et époque -------------------------------------
CODES = {
    ("ancien", "DI"):  "P04AL08C",
    ("ancien", "TSA"): "P04BL08C",
    ("nouveau", "DI"):  "P23L01C",
    ("nouveau", "TSA"): "P23L02C",
}

# --- Libellés des colonnes d'âge (C = numéro de colonne, 2 chiffres) --------
AGE_ANCIEN = {
    "01": "0 à 4 ans", "02": "5 à 17 ans", "03": "18 à 21 ans",
    "04": "22 à 44 ans", "05": "45 à 64 ans", "06": "65 ans et plus",
    "07": "Total",
}
AGE_NOUVEAU = {
    "01": "0 à 4 ans", "02": "5 à 11 ans", "03": "12 à 17 ans",
    "04": "18 à 21 ans", "05": "22 à 44 ans", "06": "45 à 64 ans",
    "07": "65 à 74 ans", "08": "75 ans et plus", "09": "Total",
}
AGES = {"ancien": AGE_ANCIEN, "nouveau": AGE_NOUVEAU}

# --- Noms des régions sociosanitaires (RSS) ---------------------------------
RSS_NOMS = {
    1: "Bas-Saint-Laurent", 2: "Saguenay–Lac-Saint-Jean",
    3: "Capitale-Nationale", 4: "Mauricie et Centre-du-Québec",
    5: "Estrie", 6: "Montréal", 7: "Outaouais",
    8: "Abitibi-Témiscamingue", 9: "Côte-Nord", 10: "Nord-du-Québec",
    11: "Gaspésie–Îles-de-la-Madeleine", 12: "Chaudière-Appalaches",
    13: "Laval", 14: "Lanaudière", 15: "Laurentides", 16: "Montérégie",
    17: "Nunavik", 18: "Terres-Cries-de-la-Baie-James",
}

# Index PLC -> (deficience, code_colonne)
def _index_codes(epoque: str):
    idx = {}
    for (ep, defi), prefix in CODES.items():
        if ep != epoque:
            continue
        for col in AGES[epoque]:
            idx[f"{prefix}{col}"] = (defi, col)
    return idx


def harmoniser() -> tuple[pd.DataFrame, pd.DataFrame]:
    xls = pd.ExcelFile(SRC)
    lignes = []
    rapport = []

    for exercice, epoque in EXERCICES.items():
        if exercice not in xls.sheet_names:
            rapport.append({"exercice": exercice, "statut": "FEUILLE ABSENTE",
                            "lignes_lues": 0, "lignes_retenues": 0, "total": 0})
            continue
        df = xls.parse(exercice, header=0)
        df.columns = [str(c).strip() for c in df.columns]
        # Colonnes B/E/K par position (mise en page stable) ; on retombe sur
        # les noms si présents.
        col_rss = "RSS" if "RSS" in df.columns else df.columns[1]
        col_plc = "PLC" if "PLC" in df.columns else df.columns[4]
        col_val = "Chiffre" if "Chiffre" in df.columns else df.columns[10]

        idx = _index_codes(epoque)
        n_lues = len(df)
        sub = df[[col_rss, col_plc, col_val]].copy()
        sub.columns = ["rss", "plc", "valeur"]
        sub["plc"] = sub["plc"].astype(str).str.strip()
        sub = sub[sub["plc"].isin(idx.keys())].copy()
        # valeur -> numérique
        sub["valeur"] = pd.to_numeric(sub["valeur"], errors="coerce")
        non_num = int(sub["valeur"].isna().sum())
        sub = sub.dropna(subset=["valeur"])
        sub["rss"] = pd.to_numeric(sub["rss"], errors="coerce").astype("Int64")

        sub[["deficience", "code_colonne"]] = sub["plc"].map(idx).apply(pd.Series)
        agg = (sub.groupby(["rss", "deficience", "code_colonne", "plc"],
                           dropna=False)["valeur"].sum().reset_index())

        for _, r in agg.iterrows():
            col = r["code_colonne"]
            libelle = AGES[epoque][col]
            rss = int(r["rss"]) if pd.notna(r["rss"]) else None
            lignes.append({
                "jeu": JEU,
                "exercice": exercice,
                "epoque": epoque,
                "deficience": r["deficience"],
                "groupe_age": libelle,
                "est_total": libelle == "Total",
                "rss": rss,
                "rss_nom": RSS_NOMS.get(rss, "Inconnu"),
                "code_plc": r["plc"],
                "effectif": int(round(r["valeur"])),
            })

        total_brackets = int(agg[agg["code_colonne"].map(
            lambda c: AGES[epoque][c] != "Total")]["valeur"].sum())
        rapport.append({
            "exercice": exercice, "epoque": epoque, "statut": "OK",
            "lignes_lues": n_lues, "lignes_retenues": int(len(sub)),
            "valeurs_non_numeriques": non_num,
            "total_effectifs_hors_total": total_brackets,
        })

    long = pd.DataFrame(lignes).sort_values(
        ["deficience", "exercice", "rss", "groupe_age"]).reset_index(drop=True)
    rap = pd.DataFrame(rapport)
    return long, rap


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    long, rap = harmoniser()
    long.to_parquet(OUT / "effectifs_long.parquet", index=False)
    long.to_csv(OUT / "effectifs_long.csv", index=False, encoding="utf-8")
    rap.to_csv(OUT / "rapport_qualite.csv", index=False, encoding="utf-8")

    print(f"[OK] {len(long)} lignes -> {OUT/'effectifs_long.parquet'}")
    print("\n=== Rapport qualité ===")
    print(rap.to_string(index=False))
    # Contrôle rapide : totaux DI « Tout le Québec » (brackets) par exercice
    print("\n=== Totaux DI Québec (hors ligne Total) par exercice ===")
    di = long[(long.deficience == "DI") & (~long.est_total)]
    print(di.groupby("exercice")["effectif"].sum().to_string())


if __name__ == "__main__":
    sys.exit(main())
