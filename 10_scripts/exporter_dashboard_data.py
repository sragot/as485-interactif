#!/usr/bin/env python3
"""Phase 7 — Export des données du dashboard AS485 (usagers desservis / listes d'attente).

Interroge 40_base/sqdi_sante.db (vues v_as485_demo_par_exercice_qc et
v_as485_demo_par_exercice_region) pour un jeu d'indicateurs "phares" et
produit un JSON compact, embarqué ensuite dans le dashboard HTML autonome
(50_publication/dashboard_as485.html).

Usage :
    python 10_scripts/exporter_dashboard_data.py \
        --db 40_base/sqdi_sante.db --out 50_publication/donnees_dashboard.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3

# code_cellule phares -> (catégorie, libellé court pour le dashboard)
INDICATEURS = [
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="40_base/sqdi_sante.db")
    ap.add_argument("--out", default="50_publication/donnees_dashboard.json")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    cur = con.cursor()

    codes = [c for c, _, _ in INDICATEURS]
    placeholders = ",".join("?" * len(codes))

    cur.execute(f"""
        SELECT DISTINCT exercice FROM v_as485_demo_par_exercice_qc
        WHERE code_cellule IN ({placeholders}) ORDER BY exercice
    """, codes)
    exercices = [r[0] for r in cur.fetchall()]

    cur.execute("SELECT rss, region_nom FROM regions_rss ORDER BY CAST(rss AS INTEGER)")
    regions_all = cur.fetchall()

    cur.execute(f"""
        SELECT DISTINCT rss FROM v_as485_demo_par_exercice_region
        WHERE code_cellule IN ({placeholders})
    """, codes)
    rss_presentes = {r[0] for r in cur.fetchall()}
    regions = [{"rss": rss, "nom": nom} for rss, nom in regions_all if rss in rss_presentes]

    national: dict = {}
    cur.execute(f"""
        SELECT code_cellule, exercice, valeur FROM v_as485_demo_par_exercice_qc
        WHERE code_cellule IN ({placeholders})
    """, codes)
    for code, exercice, valeur in cur.fetchall():
        national.setdefault(code, {})[exercice] = valeur

    regional: dict = {}
    cur.execute(f"""
        SELECT code_cellule, exercice, rss, valeur FROM v_as485_demo_par_exercice_region
        WHERE code_cellule IN ({placeholders})
    """, codes)
    for code, exercice, rss, valeur in cur.fetchall():
        regional.setdefault(code, {}).setdefault(exercice, {})[rss] = valeur

    con.close()

    data = {
        "periode": exercices,
        "regions": regions,
        "indicateurs": [
            {"code": c, "categorie": cat, "label": lbl} for c, cat, lbl in INDICATEURS
        ],
        "national": national,
        "regional": regional,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    print(f"[LIVRABLE] {args.out}  "
          f"({len(exercices)} exercices, {len(regions)} régions, {len(INDICATEURS)} indicateurs)")


if __name__ == "__main__":
    main()
