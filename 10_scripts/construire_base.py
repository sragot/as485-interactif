#!/usr/bin/env python3
"""Phase 5 — Construction de la base SQLite 40_base/sqdi_sante.db.

Charge les tables canoniques (une par formulaire) et le dictionnaire de codes
(30_dictionnaires/codes_as.csv), puis crée des vues « valeurs libellées » et des
agrégats de démonstration :

  AS485 (DI-TSA) :
  - as485_valeurs_libellees : jointure valeurs AS485 <-> libellés (avec `epoque`).
  - v_as485_demo_par_exercice_region / _qc : agrégats sur les pages de démo.

  AS484 (déficience physique) :
  - as484_valeurs_libellees + v_as484_demo_par_exercice_region / _qc : idem sur la
    page phare décodée (page 09, structure depuis 2013-2014).

Script idempotent : la base est reconstruite à chaque exécution.

Usage :
    python 10_scripts/construire_base.py \
        --canonique 20_canonique --dico 30_dictionnaires/codes_as.csv \
        --out 40_base/sqdi_sante.db
"""
from __future__ import annotations

import argparse
import os
import sqlite3

import pandas as pd

PREFERES = {
    "AS478": "AS478/as478_harmonise.parquet",
    "AS480": "AS480/as480_unifie.parquet",
    "AS481": "AS481/as481_harmonise.parquet",
    "AS484": "AS484/as484_harmonise.parquet",
    "AS485": "AS485/as485_harmonise.parquet",
}

# Régions sociosanitaires du Québec (référence publique MSSS, codes 01-18).
REGIONS_RSS = [
    (1, "Bas-Saint-Laurent"), (2, "Saguenay-Lac-Saint-Jean"),
    (3, "Capitale-Nationale"), (4, "Mauricie et Centre-du-Québec"),
    (5, "Estrie"), (6, "Montréal"), (7, "Outaouais"),
    (8, "Abitibi-Témiscamingue"), (9, "Côte-Nord"), (10, "Nord-du-Québec"),
    (11, "Gaspésie-Îles-de-la-Madeleine"), (12, "Chaudière-Appalaches"),
    (13, "Laval"), (14, "Lanaudière"), (15, "Laurentides"),
    (16, "Montérégie"), (17, "Nunavik"), (18, "Terres-Cries-de-la-Baie-James"),
]

PAGES_DEMO = ("09", "10", "17", "18", "19", "20")

# AS484 (déficience physique) — page phare décodée (cf. decoder_pages_as484.py).
# Structure post-restructuration 2013-2014 (epoque = 'depuis_2013').
PAGES_DEMO_AS484 = ("09",)

# AS481 (dépendance) — page phare décodée (cf. decoder_pages_as481.py).
# Page 02 « Usagers admis – alcool-drogues et jeux pathologiques », lignes 01-14,
# structure stable sur tout l'historique 2011-2022 (epoque = 'stable').
PAGES_DEMO_AS481 = ("02",)


def charger_tables(con: sqlite3.Connection, canonique_dir: str) -> None:
    for formulaire, rel in PREFERES.items():
        path = os.path.join(canonique_dir, rel)
        if not os.path.exists(path):
            print(f"[SKIP] {formulaire}: introuvable {path}")
            continue
        df = pd.read_parquet(path)
        table = formulaire.lower()
        df.to_sql(table, con, if_exists="replace", index=False)
        print(f"[OK] table {table:<8} <- {rel}  ({len(df):,} lignes)")


def charger_dictionnaire(con: sqlite3.Connection, dico_path: str) -> None:
    d = pd.read_csv(dico_path, dtype=str)
    d.to_sql("dictionnaire", con, if_exists="replace", index=False)
    print(f"[OK] table dictionnaire <- {dico_path}  ({len(d):,} lignes)")


def charger_regions(con: sqlite3.Connection) -> None:
    d = pd.DataFrame(REGIONS_RSS, columns=["rss", "region_nom"])
    d["rss"] = d["rss"].astype(str)
    d.to_sql("regions_rss", con, if_exists="replace", index=False)
    print(f"[OK] table regions_rss ({len(d)} régions)")


def creer_index(con: sqlite3.Connection) -> None:
    con.execute("CREATE INDEX IF NOT EXISTS idx_as485_code ON as485(code_cellule)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_as485_exercice ON as485(exercice_debut)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_as484_code ON as484(code_cellule)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_as484_exercice ON as484(exercice_debut)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_as481_code ON as481(code_cellule)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_as481_exercice ON as481(exercice_debut)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_dico_formulaire_code ON dictionnaire(formulaire, code_cellule)")


def creer_vues(con: sqlite3.Connection) -> None:
    con.executescript(f"""
    DROP VIEW IF EXISTS as485_valeurs_libellees;
    CREATE VIEW as485_valeurs_libellees AS
    SELECT
        v.exercice, v.exercice_debut, v.rss, r.region_nom,
        v.etablissement_id, v.etablissement_nom,
        v.page, v.ligne, v.colonne, v.code_cellule, v.chiffre,
        d.libelle, d.unite, d.theme, d.page_titre, d.epoque
    FROM as485 AS v
    LEFT JOIN regions_rss AS r ON r.rss = v.rss
    LEFT JOIN dictionnaire AS d
        ON d.formulaire = 'AS485'
       AND d.code_cellule = v.code_cellule
       AND (
            d.epoque IS NULL OR d.epoque = 'stable'
            OR d.epoque = (CASE WHEN v.exercice_debut <= 2017 THEN '2013-2017' ELSE '2018-2023' END)
       )
       AND (d.page NOT IN {PAGES_DEMO} OR v.exercice_debut >= 2013);

    DROP VIEW IF EXISTS v_as485_demo_par_exercice_region;
    CREATE VIEW v_as485_demo_par_exercice_region AS
    SELECT
        exercice, exercice_debut, rss, region_nom,
        page, page_titre, ligne, colonne, code_cellule, libelle, theme, unite,
        CASE WHEN MAX(unite) = 'jours' THEN AVG(chiffre) ELSE SUM(chiffre) END AS valeur,
        COUNT(*) AS n_lignes_sources
    FROM as485_valeurs_libellees
    WHERE page IN {PAGES_DEMO} AND exercice_debut >= 2013 AND libelle IS NOT NULL
    GROUP BY exercice, rss, page, ligne, colonne;

    DROP VIEW IF EXISTS v_as485_demo_par_exercice_qc;
    CREATE VIEW v_as485_demo_par_exercice_qc AS
    SELECT
        exercice, exercice_debut,
        page, page_titre, ligne, colonne, code_cellule, libelle, theme, unite,
        CASE WHEN MAX(unite) = 'jours' THEN AVG(chiffre) ELSE SUM(chiffre) END AS valeur,
        COUNT(*) AS n_lignes_sources
    FROM as485_valeurs_libellees
    WHERE page IN {PAGES_DEMO} AND exercice_debut >= 2013 AND libelle IS NOT NULL
    GROUP BY exercice, page, ligne, colonne;
    """)
    print("[OK] vues créées : as485_valeurs_libellees, "
          "v_as485_demo_par_exercice_region, v_as485_demo_par_exercice_qc")


def creer_vues_as484(con: sqlite3.Connection) -> None:
    """Vues AS484 (déficience physique) sur la page phare décodée (page 09).

    Même logique que l'AS485 : une vue valeurs libellées qui joint le dictionnaire
    en tenant compte de epoque (ici 'depuis_2013' : ces code_cellule ne désignent
    la structure courante qu'à partir de 2013-2014), puis deux agrégats."""
    pages_in = "(" + ",".join("'" + str(pp) + "'" for pp in PAGES_DEMO_AS484) + ")"
    con.executescript(f"""
    DROP VIEW IF EXISTS as484_valeurs_libellees;
    CREATE VIEW as484_valeurs_libellees AS
    SELECT
        v.exercice, v.exercice_debut, v.rss, r.region_nom,
        v.etablissement_id, v.etablissement_nom,
        v.page, v.ligne, v.colonne, v.code_cellule, v.chiffre,
        d.libelle, d.unite, d.theme, d.page_titre, d.epoque
    FROM as484 AS v
    LEFT JOIN regions_rss AS r ON r.rss = v.rss
    LEFT JOIN dictionnaire AS d
        ON d.formulaire = 'AS484'
       AND d.code_cellule = v.code_cellule
       AND (
            d.epoque IS NULL OR d.epoque = 'stable'
            OR (d.epoque = 'depuis_2013' AND v.exercice_debut >= 2013)
       );

    DROP VIEW IF EXISTS v_as484_demo_par_exercice_region;
    CREATE VIEW v_as484_demo_par_exercice_region AS
    SELECT
        exercice, exercice_debut, rss, region_nom,
        page, page_titre, ligne, colonne, code_cellule, libelle, theme, unite,
        SUM(chiffre) AS valeur,
        COUNT(*) AS n_lignes_sources
    FROM as484_valeurs_libellees
    WHERE page IN {pages_in} AND exercice_debut >= 2013 AND libelle IS NOT NULL
    GROUP BY exercice, rss, page, ligne, colonne;

    DROP VIEW IF EXISTS v_as484_demo_par_exercice_qc;
    CREATE VIEW v_as484_demo_par_exercice_qc AS
    SELECT
        exercice, exercice_debut,
        page, page_titre, ligne, colonne, code_cellule, libelle, theme, unite,
        SUM(chiffre) AS valeur,
        COUNT(*) AS n_lignes_sources
    FROM as484_valeurs_libellees
    WHERE page IN {pages_in} AND exercice_debut >= 2013 AND libelle IS NOT NULL
    GROUP BY exercice, page, ligne, colonne;
    """)
    print("[OK] vues créées : as484_valeurs_libellees, "
          "v_as484_demo_par_exercice_region, v_as484_demo_par_exercice_qc")


def creer_vues_as481(con: sqlite3.Connection) -> None:
    """Vues AS481 (dépendance) sur la page phare décodée (page 02).

    Même logique que l'AS485/AS484 : une vue valeurs libellées qui joint le
    dictionnaire (ici epoque = 'stable' : lignes 01-14 identiques sur tout
    l'historique 2011-2022), puis deux agrégats de démonstration."""
    pages_in = "(" + ",".join("'" + str(pp) + "'" for pp in PAGES_DEMO_AS481) + ")"
    con.executescript(f"""
    DROP VIEW IF EXISTS as481_valeurs_libellees;
    CREATE VIEW as481_valeurs_libellees AS
    SELECT
        v.exercice, v.exercice_debut, v.rss, r.region_nom,
        v.etablissement_id, v.etablissement_nom,
        v.page, v.ligne, v.colonne, v.code_cellule, v.chiffre,
        d.libelle, d.unite, d.theme, d.page_titre, d.epoque
    FROM as481 AS v
    LEFT JOIN regions_rss AS r ON r.rss = v.rss
    LEFT JOIN dictionnaire AS d
        ON d.formulaire = 'AS481'
       AND d.code_cellule = v.code_cellule
       AND (d.epoque IS NULL OR d.epoque = 'stable');

    DROP VIEW IF EXISTS v_as481_demo_par_exercice_region;
    CREATE VIEW v_as481_demo_par_exercice_region AS
    SELECT
        exercice, exercice_debut, rss, region_nom,
        page, page_titre, ligne, colonne, code_cellule, libelle, theme, unite,
        SUM(chiffre) AS valeur,
        COUNT(*) AS n_lignes_sources
    FROM as481_valeurs_libellees
    WHERE page IN {pages_in} AND libelle IS NOT NULL
    GROUP BY exercice, rss, page, ligne, colonne;

    DROP VIEW IF EXISTS v_as481_demo_par_exercice_qc;
    CREATE VIEW v_as481_demo_par_exercice_qc AS
    SELECT
        exercice, exercice_debut,
        page, page_titre, ligne, colonne, code_cellule, libelle, theme, unite,
        SUM(chiffre) AS valeur,
        COUNT(*) AS n_lignes_sources
    FROM as481_valeurs_libellees
    WHERE page IN {pages_in} AND libelle IS NOT NULL
    GROUP BY exercice, page, ligne, colonne;
    """)
    print("[OK] vues créées : as481_valeurs_libellees, "
          "v_as481_demo_par_exercice_region, v_as481_demo_par_exercice_qc")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--canonique", default="20_canonique")
    ap.add_argument("--dico", default="30_dictionnaires/codes_as.csv")
    ap.add_argument("--out", default="40_base/sqdi_sante.db")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    if os.path.exists(args.out):
        os.remove(args.out)

    con = sqlite3.connect(args.out)
    try:
        charger_tables(con, args.canonique)
        charger_dictionnaire(con, args.dico)
        charger_regions(con)
        creer_index(con)
        creer_vues(con)
        creer_vues_as484(con)
        creer_vues_as481(con)
        con.commit()
    finally:
        con.close()

    print(f"\n[LIVRABLE] {args.out}")


if __name__ == "__main__":
    main()
