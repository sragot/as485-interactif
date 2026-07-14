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

# AS480 (centres jeunesse) — page phare décodée (cf. decoder_pages_as480.py).
# Page 04 « signalements retenus par problématique » (LPJ art. 38/38.1), lignes
# 01-14, structure stable 2010-2011 → 2022-2023 (epoque = 'stable').
PAGES_DEMO_AS480 = ("04",)


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
    con.execute("CREATE INDEX IF NOT EXISTS idx_as480_code ON as480(code_cellule)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_as480_exercice ON as480(exercice_debut)")
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


def creer_vues_as480(con: sqlite3.Connection) -> None:
    """Vues AS480 (centres jeunesse) sur la page phare décodée (page 04).

    Comme les autres formulaires, mais les unités sont hétérogènes : certaines
    lignes sont des comptes (signalements, évaluations…), d'autres des durées
    moyennes (jours ou mois). L'agrégat fait donc la SOMME des comptes et la
    MOYENNE des durées, en s'appuyant sur l'unité du dictionnaire (epoque =
    'stable' : lignes 01-14 identiques sur 2010-2011 → 2022-2023)."""
    pages_in = "(" + ",".join("'" + str(pp) + "'" for pp in PAGES_DEMO_AS480) + ")"
    con.executescript(f"""
    DROP VIEW IF EXISTS as480_valeurs_libellees;
    CREATE VIEW as480_valeurs_libellees AS
    SELECT
        v.exercice, v.exercice_debut, v.rss, r.region_nom,
        v.etablissement_id, v.etablissement_nom,
        v.page, v.ligne, v.colonne, v.code_cellule, v.chiffre,
        d.libelle, d.unite, d.theme, d.page_titre, d.epoque
    FROM as480 AS v
    LEFT JOIN regions_rss AS r ON r.rss = v.rss
    LEFT JOIN dictionnaire AS d
        ON d.formulaire = 'AS480'
       AND d.code_cellule = v.code_cellule
       AND (d.epoque IS NULL OR d.epoque = 'stable');

    DROP VIEW IF EXISTS v_as480_demo_par_exercice_region;
    CREATE VIEW v_as480_demo_par_exercice_region AS
    SELECT
        exercice, exercice_debut, rss, region_nom,
        page, page_titre, ligne, colonne, code_cellule, libelle, theme, unite,
        CASE WHEN MAX(unite) IN ('jours','mois') THEN AVG(chiffre) ELSE SUM(chiffre) END AS valeur,
        COUNT(*) AS n_lignes_sources
    FROM as480_valeurs_libellees
    WHERE page IN {pages_in} AND libelle IS NOT NULL
    GROUP BY exercice, rss, page, ligne, colonne;

    DROP VIEW IF EXISTS v_as480_demo_par_exercice_qc;
    CREATE VIEW v_as480_demo_par_exercice_qc AS
    SELECT
        exercice, exercice_debut,
        page, page_titre, ligne, colonne, code_cellule, libelle, theme, unite,
        CASE WHEN MAX(unite) IN ('jours','mois') THEN AVG(chiffre) ELSE SUM(chiffre) END AS valeur,
        COUNT(*) AS n_lignes_sources
    FROM as480_valeurs_libellees
    WHERE page IN {pages_in} AND libelle IS NOT NULL
    GROUP BY exercice, page, ligne, colonne;
    """)
    print("[OK] vues créées : as480_valeurs_libellees, "
          "v_as480_demo_par_exercice_region, v_as480_demo_par_exercice_qc")



def charger_effectifs(con: sqlite3.Connection, canonique_dir: str) -> None:
    """Charge la table canonique des effectifs démographiques (Chantier 1).

    Reproduit la feuille « Population (historical) » de Stats.xlsx :
    usagers DI / TSA par groupe d'âge, par RSS et par exercice
    (cf. 10_scripts/harmoniser_effectifs.py)."""
    path = os.path.join(canonique_dir, "effectifs", "effectifs_long.parquet")
    if not os.path.exists(path):
        print(f"[SKIP] effectifs : introuvable {path}")
        return
    df = pd.read_parquet(path)
    df.to_sql("effectifs", con, if_exists="replace", index=False)
    print(f"[OK] table effectifs <- effectifs/effectifs_long.parquet  ({len(df):,} lignes)")


def creer_vues_effectifs(con: sqlite3.Connection) -> None:
    """Vues agrégées des effectifs DI-TSA.

    - Totaux DI / TSA / DI+TSA (toutes époques, tous âges) : codes EFF:DI,
      EFF:TSA, EFF:DITSA.
    - Ventilation par groupe d'âge (brackets de la maquette « nouveau »,
      2013-2014 →) : codes EFF:DI:<âge> et EFF:TSA:<âge>.
    Le RSS est casté en TEXT pour rester cohérent avec regions_rss et les
    autres vues (jointure/filtre côté export)."""
    con.executescript("""
    DROP VIEW IF EXISTS v_effectifs_par_exercice_qc;
    CREATE VIEW v_effectifs_par_exercice_qc AS
      SELECT exercice, 'EFF:' || deficience AS code_cellule, SUM(chiffre_) AS valeur
        FROM (SELECT exercice, deficience, effectif AS chiffre_ FROM effectifs WHERE est_total = 0)
       GROUP BY exercice, deficience
      UNION ALL
      SELECT exercice, 'EFF:DITSA' AS code_cellule, SUM(effectif) AS valeur
        FROM effectifs WHERE est_total = 0 GROUP BY exercice
      UNION ALL
      SELECT exercice, 'EFF:' || deficience || ':' || groupe_age AS code_cellule,
             SUM(effectif) AS valeur
        FROM effectifs WHERE est_total = 0 AND epoque = 'nouveau'
       GROUP BY exercice, deficience, groupe_age;

    DROP VIEW IF EXISTS v_effectifs_par_exercice_region;
    CREATE VIEW v_effectifs_par_exercice_region AS
      SELECT exercice, CAST(rss AS TEXT) AS rss, 'EFF:' || deficience AS code_cellule,
             SUM(effectif) AS valeur
        FROM effectifs WHERE est_total = 0 GROUP BY exercice, rss, deficience
      UNION ALL
      SELECT exercice, CAST(rss AS TEXT) AS rss, 'EFF:DITSA' AS code_cellule,
             SUM(effectif) AS valeur
        FROM effectifs WHERE est_total = 0 GROUP BY exercice, rss
      UNION ALL
      SELECT exercice, CAST(rss AS TEXT) AS rss,
             'EFF:' || deficience || ':' || groupe_age AS code_cellule,
             SUM(effectif) AS valeur
        FROM effectifs WHERE est_total = 0 AND epoque = 'nouveau'
       GROUP BY exercice, rss, deficience, groupe_age;
    """)
    print("[OK] vues créées : v_effectifs_par_exercice_qc, "
          "v_effectifs_par_exercice_region")



def charger_depenses_region(con: sqlite3.Connection, canonique_dir: str) -> None:
    """Charge la table canonique des dépenses par région (Chantier 3).

    Dépivotage des feuilles « Par région » (programme × RSS) des rapports
    annuels de dépenses MSSS — cf. 10_scripts/harmoniser_depenses.py."""
    path = os.path.join(canonique_dir, "depenses_region", "depenses_region_long.parquet")
    if not os.path.exists(path):
        print(f"[SKIP] depenses_region : introuvable {path}")
        return
    df = pd.read_parquet(path)
    df.to_sql("depenses_region", con, if_exists="replace", index=False)
    print(f"[OK] table depenses_region <- depenses_region/depenses_region_long.parquet  ({len(df):,} lignes)")


def creer_vues_depenses_region(con: sqlite3.Connection) -> None:
    """Vues agrégées des dépenses par région et par programme.

    Un code synthétique par programme : DEPR:<programme> (montant en $).
    RSS casté en TEXT pour rester cohérent avec regions_rss et l'export."""
    con.executescript("""
    DROP VIEW IF EXISTS v_depenses_region_par_exercice_qc;
    CREATE VIEW v_depenses_region_par_exercice_qc AS
      SELECT exercice, 'DEPR:' || programme AS code_cellule, SUM(montant) AS valeur
        FROM depenses_region GROUP BY exercice, programme;

    DROP VIEW IF EXISTS v_depenses_region_par_exercice_region;
    CREATE VIEW v_depenses_region_par_exercice_region AS
      SELECT exercice, CAST(rss AS TEXT) AS rss,
             'DEPR:' || programme AS code_cellule, SUM(montant) AS valeur
        FROM depenses_region GROUP BY exercice, rss, programme;
    """)
    print("[OK] vues créées : v_depenses_region_par_exercice_qc, "
          "v_depenses_region_par_exercice_region")



def charger_depenses_activites(con: sqlite3.Connection, canonique_dir: str) -> None:
    """Charge la table canonique des dépenses par centre d'activités (Chantier 2)."""
    path = os.path.join(canonique_dir, "depenses_activites", "depenses_activites_long.parquet")
    if not os.path.exists(path):
        print(f"[SKIP] depenses_activites : introuvable {path}")
        return
    df = pd.read_parquet(path)
    df.to_sql("depenses_activites", con, if_exists="replace", index=False)
    print(f"[OK] table depenses_activites <- depenses_activites/depenses_activites_long.parquet  ({len(df):,} lignes)")


def creer_vues_depenses_activites(con: sqlite3.Connection) -> None:
    """Vues agrégées des dépenses par programme et par centre d'activités.

    Code synthétique DACT:<programme> (montant en $). Deux grains : total
    Québec par programme, et détail par centre d'activités."""
    con.executescript("""
    DROP VIEW IF EXISTS v_depenses_activites_par_exercice_qc;
    CREATE VIEW v_depenses_activites_par_exercice_qc AS
      SELECT exercice, 'DACT:' || programme AS code_cellule, SUM(montant) AS valeur
        FROM depenses_activites GROUP BY exercice, programme;

    DROP VIEW IF EXISTS v_depenses_activites_par_ca;
    CREATE VIEW v_depenses_activites_par_ca AS
      SELECT exercice, centre_activites,
             'DACT:' || programme AS code_cellule, SUM(montant) AS valeur
        FROM depenses_activites GROUP BY exercice, centre_activites, programme;
    """)
    print("[OK] vues créées : v_depenses_activites_par_exercice_qc, "
          "v_depenses_activites_par_ca")


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
        charger_effectifs(con, args.canonique)
        charger_depenses_region(con, args.canonique)
        charger_depenses_activites(con, args.canonique)
        creer_index(con)
        creer_vues(con)
        creer_vues_as484(con)
        creer_vues_as481(con)
        creer_vues_as480(con)
        creer_vues_effectifs(con)
        creer_vues_depenses_region(con)
        creer_vues_depenses_activites(con)
        con.commit()
    finally:
        con.close()

    print(f"\n[LIVRABLE] {args.out}")


if __name__ == "__main__":
    main()
