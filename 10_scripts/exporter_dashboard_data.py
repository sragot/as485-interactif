#!/usr/bin/env python3
"""Phase 7 — Export des données du dashboard (multi-formulaires).

Interroge 40_base/sqdi_sante.db et produit un JSON compact, embarqué ensuite
dans le dashboard HTML autonome (50_publication/dashboard_as485.html).

Deux formulaires y sont exposés :
  - AS485 (DI-TSA) : usagers desservis (pages 09-10) et listes d'attente
    (pages 17-20)  ->  vues v_as485_demo_par_exercice_qc / _region.
  - AS484 (déficience physique) : usagers admis en CRDP par groupe d'âge
    (page 09, structure depuis 2013-2014)  ->  vues v_as484_demo_par_exercice_qc / _region.

Les code_cellule de l'AS484 sont préfixés « AS484: » dans le JSON pour éviter
toute collision avec ceux de l'AS485 (les deux ont une page 09).

Usage :
    python 10_scripts/exporter_dashboard_data.py \
        --db 40_base/sqdi_sante.db --out 50_publication/donnees_dashboard.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3

# (code_cellule brut, categorie, libellé court) — un onglet par catégorie.
INDICATEURS_AS485 = [
    ("P09L06C09", "desservis", "Usagers desservis - DI et TED"),
    ("P09L11C09", "desservis", "Usagers desservis - DI seulement"),
    ("P09L22C09", "desservis", "Usagers desservis - TED seulement"),
    ("P17L07C09", "attente", "Ne reçoivent aucun service - DI et TED"),
    ("P17L01C09", "attente", "Ne reçoivent aucun service - DI"),
    ("P17L04C09", "attente", "Ne reçoivent aucun service - TED"),
    ("P18L13C09", "attente", "Sur liste d'attente d'un service en DI"),
    ("P19L13C09", "attente", "Sur liste d'attente d'un service en TED"),
    ("P20L13C09", "attente", "Attente d'admissions - nombre d'usagers"),
    ("P20L14C09", "attente", "Attente d'admissions - délai moyen (jours)"),
    ("P20L22C09", "attente", "Attente d'inscriptions - nombre d'usagers"),
    ("P20L23C09", "attente", "Attente d'inscriptions - délai moyen (jours)"),
]

# AS484 — page 09 (admis en CRDP par groupe d'âge), colonne 9 = total tous âges.
INDICATEURS_AS484 = [
    ("P09L02C09", "dp484", "Admissions durant l'année"),
    ("P09L01C09", "dp484", "Usagers admis au début de l'année"),
    ("P09L07C09", "dp484", "Usagers admis à la fin de l'année"),
    ("P09L08C09", "dp484", "Répartis : hommes (fin d'année)"),
    ("P09L09C09", "dp484", "Répartis : femmes (fin d'année)"),
]


def _collecter(cur, vue_qc, vue_region, codes, prefixe=""):
    """Retourne (national, regional, rss_presentes) pour une liste de codes bruts.
    Les clés de sortie sont préfixées (pour namespacer par formulaire)."""
    ph = ",".join("?" * len(codes))
    national: dict = {}
    for code, exercice, valeur in cur.execute(
        f"SELECT code_cellule, exercice, valeur FROM {vue_qc} WHERE code_cellule IN ({ph})", codes):
        national.setdefault(prefixe + code, {})[exercice] = valeur
    regional: dict = {}
    rss_presentes = set()
    for code, exercice, rss, valeur in cur.execute(
        f"SELECT code_cellule, exercice, rss, valeur FROM {vue_region} WHERE code_cellule IN ({ph})", codes):
        regional.setdefault(prefixe + code, {}).setdefault(exercice, {})[rss] = valeur
        rss_presentes.add(rss)
    return national, regional, rss_presentes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="40_base/sqdi_sante.db")
    ap.add_argument("--out", default="50_publication/donnees_dashboard.json")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    cur = con.cursor()

    codes485 = [c for c, _, _ in INDICATEURS_AS485]
    codes484 = [c for c, _, _ in INDICATEURS_AS484]

    ph485 = ",".join("?" * len(codes485))
    cur.execute(f"SELECT DISTINCT exercice FROM v_as485_demo_par_exercice_qc WHERE code_cellule IN ({ph485})", codes485)
    exercices = {r[0] for r in cur.fetchall()}
    ph484 = ",".join("?" * len(codes484))
    cur.execute(f"SELECT DISTINCT exercice FROM v_as484_demo_par_exercice_qc WHERE code_cellule IN ({ph484})", codes484)
    exercices |= {r[0] for r in cur.fetchall()}
    exercices = sorted(exercices)

    nat485, reg485, rss485 = _collecter(cur, "v_as485_demo_par_exercice_qc", "v_as485_demo_par_exercice_region", codes485)
    nat484, reg484, rss484 = _collecter(cur, "v_as484_demo_par_exercice_qc", "v_as484_demo_par_exercice_region", codes484, prefixe="AS484:")

    national = {**nat485, **nat484}
    regional = {**reg485, **reg484}
    rss_presentes = rss485 | rss484

    cur.execute("SELECT rss, region_nom FROM regions_rss ORDER BY CAST(rss AS INTEGER)")
    regions = [{"rss": rss, "nom": nom} for rss, nom in cur.fetchall() if rss in rss_presentes]

    indicateurs = (
        [{"code": c, "categorie": cat, "label": lbl} for c, cat, lbl in INDICATEURS_AS485]
        + [{"code": "AS484:" + c, "categorie": cat, "label": lbl} for c, cat, lbl in INDICATEURS_AS484]
    )

    con.close()

    data = {
        "periode": exercices,
        "regions": regions,
        "indicateurs": indicateurs,
        "national": national,
        "regional": regional,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    print(f"[LIVRABLE] {args.out}  "
          f"({len(exercices)} exercices, {len(regions)} régions, "
          f"{len(INDICATEURS_AS485)} indic. AS485 + {len(INDICATEURS_AS484)} indic. AS484)")


if __name__ == "__main__":
    main()
