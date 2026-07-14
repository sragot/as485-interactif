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

# AS481 — page 02 (usagers admis en dépendance par groupe d'âge), colonne 6 = total tous âges.
INDICATEURS_AS481 = [
    ("P02L02C06", "dep481", "Admissions durant l'année — alcool-drogues"),
    ("P02L05C06", "dep481", "Usagers à la fin de l'année — alcool-drogues"),
    ("P02L02C01", "dep481", "Admissions — alcool-drogues, 0-17 ans"),
    ("P02L09C06", "dep481", "Admissions durant l'année — jeux pathologiques"),
    ("P02L12C06", "dep481", "Usagers à la fin de l'année — jeux pathologiques"),
]

# AS480 — page 04 (signalements retenus par problématique, LPJ art. 38/38.1),
# colonne 7 = total toutes problématiques. Indicateurs de comptes (somme propre).
INDICATEURS_AS480 = [
    ("P04L01C07", "cj480", "Signalements retenus — total"),
    ("P04L01C01", "cj480", "Signalements retenus — négligence"),
    ("P04L01C03", "cj480", "Signalements retenus — abus sexuel"),
    ("P04L05C07", "cj480", "Évaluations : sécurité/développement compromis"),
    ("P04L12C07", "cj480", "Nouvelles applications de mesures"),
]

# Effectifs démographiques DI-TSA dans le temps (Chantier 1 — reproduit la
# feuille « Population (historical) » de Stats.xlsx). Codes synthétiques EFF:*
# produits par les vues v_effectifs_par_exercice_qc / _region.
_AGE_BANDS_EFF = [
    "0 à 4 ans", "5 à 11 ans", "12 à 17 ans", "18 à 21 ans",
    "22 à 44 ans", "45 à 64 ans", "65 à 74 ans", "75 ans et plus",
]
INDICATEURS_EFF = [
    ("EFF:DITSA", "eff", "Usagers DI-TSA — total (tous âges)"),
    ("EFF:DI", "eff", "Usagers DI — total (tous âges)"),
    ("EFF:TSA", "eff", "Usagers TSA — total (tous âges)"),
] + [(f"EFF:DI:{a}", "eff", f"DI — {a} (dès 2013-2014)") for a in _AGE_BANDS_EFF] \
  + [(f"EFF:TSA:{a}", "eff", f"TSA — {a} (dès 2013-2014)") for a in _AGE_BANDS_EFF]

# Dépenses par région et par programme (Chantier 3 — moule « tableaux larges »,
# 10_scripts/harmoniser_depenses.py). Codes DEPR:<programme>, montants en $.
# Ventilation régionale identique aux autres onglets ; DI-TSA en tête.
_PROGRAMMES_DEPR = [
    "Déficience intellectuelle et TSA",
    "Déficience physique",
    "Dépendances",
    "Jeunes en difficulté",
    "Santé mentale",
    "Santé physique",
    "Santé publique",
    "Soutien à l'autonomie des PA",
    "Services généraux",
    "Administration",
    "Soutien aux services",
    "Gestion des bâtiments",
]
INDICATEURS_DEPR = [
    (f"DEPR:{prog}", "depr", prog, "$") for prog in _PROGRAMMES_DEPR
]

# Dépenses par centre d'activités (Chantier 2). Mêmes programmes ; grain =
# centre d'activités (section JSON dédiée "activites"). DI-TSA continu sur
# tout l'historique ; les autres programmes n'apparaissent que les années
# récentes (ventilation partielle dans la source).
INDICATEURS_DACT = [
    (f"DACT:{prog}", "dact", prog, "$") for prog in _PROGRAMMES_DEPR
]

# Dépenses SAD (soutien à domicile) par programme × région (Chantier 4).
# Maquette « par programme » dès 2016-2017 ; 7 programmes (pas de « Jeunes en
# difficulté », « Administration », etc. côté SAD). DI-TSA en tête.
_PROGRAMMES_SAD = [
    "Déficience intellectuelle et TSA",
    "Déficience physique",
    "Soutien à l'autonomie des PA",
    "Santé physique",
    "Santé mentale",
    "Santé publique",
    "Services généraux",
]
INDICATEURS_SAD = [
    (f"SAD:{prog}", "sad", prog, "$") for prog in _PROGRAMMES_SAD
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
    codes481 = [c for c, _, _ in INDICATEURS_AS481]
    codes480 = [c for c, _, _ in INDICATEURS_AS480]
    codeseff = [c for c, _, _ in INDICATEURS_EFF]
    codesdepr = [c for c, _, _, _ in INDICATEURS_DEPR]
    codesdact = [c for c, _, _, _ in INDICATEURS_DACT]
    codessad = [c for c, _, _, _ in INDICATEURS_SAD]
    # SADS (Chantier 5) : services SAD listés dynamiquement, triés par montant.
    cur.execute("SELECT code_cellule, SUM(valeur) FROM v_sad_service_par_exercice_qc GROUP BY code_cellule ORDER BY 2 DESC")
    codessads = [row[0] for row in cur.fetchall()]
    INDICATEURS_SADS = [(c, "sads", c.split(":", 1)[1], "$") for c in codessads]

    ph485 = ",".join("?" * len(codes485))
    cur.execute(f"SELECT DISTINCT exercice FROM v_as485_demo_par_exercice_qc WHERE code_cellule IN ({ph485})", codes485)
    exercices = {r[0] for r in cur.fetchall()}
    ph484 = ",".join("?" * len(codes484))
    cur.execute(f"SELECT DISTINCT exercice FROM v_as484_demo_par_exercice_qc WHERE code_cellule IN ({ph484})", codes484)
    exercices |= {r[0] for r in cur.fetchall()}
    ph481 = ",".join("?" * len(codes481))
    cur.execute(f"SELECT DISTINCT exercice FROM v_as481_demo_par_exercice_qc WHERE code_cellule IN ({ph481})", codes481)
    exercices |= {r[0] for r in cur.fetchall()}
    ph480 = ",".join("?" * len(codes480))
    cur.execute(f"SELECT DISTINCT exercice FROM v_as480_demo_par_exercice_qc WHERE code_cellule IN ({ph480})", codes480)
    exercices |= {r[0] for r in cur.fetchall()}
    pheff = ",".join("?" * len(codeseff))
    cur.execute(f"SELECT DISTINCT exercice FROM v_effectifs_par_exercice_qc WHERE code_cellule IN ({pheff})", codeseff)
    exercices |= {r[0] for r in cur.fetchall()}
    phdepr = ",".join("?" * len(codesdepr))
    cur.execute(f"SELECT DISTINCT exercice FROM v_depenses_region_par_exercice_qc WHERE code_cellule IN ({phdepr})", codesdepr)
    exercices |= {r[0] for r in cur.fetchall()}
    phdact = ",".join("?" * len(codesdact))
    cur.execute(f"SELECT DISTINCT exercice FROM v_depenses_activites_par_exercice_qc WHERE code_cellule IN ({phdact})", codesdact)
    exercices |= {r[0] for r in cur.fetchall()}
    phsad = ",".join("?" * len(codessad))
    cur.execute(f"SELECT DISTINCT exercice FROM v_depenses_sad_par_exercice_qc WHERE code_cellule IN ({phsad})", codessad)
    exercices |= {r[0] for r in cur.fetchall()}
    cur.execute("SELECT DISTINCT exercice FROM v_sad_service_par_exercice_qc")
    exercices |= {r[0] for r in cur.fetchall()}
    exercices = sorted(exercices)

    nat485, reg485, rss485 = _collecter(cur, "v_as485_demo_par_exercice_qc", "v_as485_demo_par_exercice_region", codes485)
    nat484, reg484, rss484 = _collecter(cur, "v_as484_demo_par_exercice_qc", "v_as484_demo_par_exercice_region", codes484, prefixe="AS484:")
    nat481, reg481, rss481 = _collecter(cur, "v_as481_demo_par_exercice_qc", "v_as481_demo_par_exercice_region", codes481, prefixe="AS481:")
    nat480, reg480, rss480 = _collecter(cur, "v_as480_demo_par_exercice_qc", "v_as480_demo_par_exercice_region", codes480, prefixe="AS480:")
    nateff, regeff, rsseff = _collecter(cur, "v_effectifs_par_exercice_qc", "v_effectifs_par_exercice_region", codeseff)
    natdepr, regdepr, rssdepr = _collecter(cur, "v_depenses_region_par_exercice_qc", "v_depenses_region_par_exercice_region", codesdepr)
    natdact: dict = {}
    for code, exercice, valeur in cur.execute(
        f"SELECT code_cellule, exercice, valeur FROM v_depenses_activites_par_exercice_qc WHERE code_cellule IN ({phdact})", codesdact):
        natdact.setdefault(code, {})[exercice] = valeur
    activites: dict = {}
    for code, exercice, ca, valeur in cur.execute(
        f"SELECT code_cellule, exercice, centre_activites, valeur FROM v_depenses_activites_par_ca WHERE code_cellule IN ({phdact})", codesdact):
        activites.setdefault(code, {}).setdefault(exercice, {})[ca] = valeur
    natsad, regsad, rsssad = _collecter(cur, "v_depenses_sad_par_exercice_qc", "v_depenses_sad_par_exercice_region", codessad)
    natsads, regsads, rsssads = _collecter(cur, "v_sad_service_par_exercice_qc", "v_sad_service_par_exercice_region", codessads)

    national = {**nat485, **nat484, **nat481, **nat480, **nateff, **natdepr, **natdact, **natsad, **natsads}
    regional = {**reg485, **reg484, **reg481, **reg480, **regeff, **regdepr, **regsad, **regsads}
    rss_presentes = rss485 | rss484 | rss481 | rss480 | rsseff | rssdepr | rsssad | rsssads

    cur.execute("SELECT rss, region_nom FROM regions_rss ORDER BY CAST(rss AS INTEGER)")
    regions = [{"rss": rss, "nom": nom} for rss, nom in cur.fetchall() if rss in rss_presentes]

    indicateurs = (
        [{"code": c, "categorie": cat, "label": lbl} for c, cat, lbl in INDICATEURS_AS485]
        + [{"code": "AS484:" + c, "categorie": cat, "label": lbl} for c, cat, lbl in INDICATEURS_AS484]
        + [{"code": "AS481:" + c, "categorie": cat, "label": lbl} for c, cat, lbl in INDICATEURS_AS481]
        + [{"code": "AS480:" + c, "categorie": cat, "label": lbl} for c, cat, lbl in INDICATEURS_AS480]
        + [{"code": c, "categorie": cat, "label": lbl} for c, cat, lbl in INDICATEURS_EFF]
        + [{"code": c, "categorie": cat, "label": lbl, "unite": u} for c, cat, lbl, u in INDICATEURS_DEPR]
        + [{"code": c, "categorie": cat, "label": lbl, "unite": u} for c, cat, lbl, u in INDICATEURS_DACT]
        + [{"code": c, "categorie": cat, "label": lbl, "unite": u} for c, cat, lbl, u in INDICATEURS_SAD]
        + [{"code": c, "categorie": cat, "label": lbl, "unite": u} for c, cat, lbl, u in INDICATEURS_SADS]
    )

    con.close()

    data = {
        "periode": exercices,
        "regions": regions,
        "indicateurs": indicateurs,
        "national": national,
        "regional": regional,
        "activites": activites,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    print(f"[LIVRABLE] {args.out}  "
          f"({len(exercices)} exercices, {len(regions)} régions, "
          f"{len(INDICATEURS_AS485)} AS485 + {len(INDICATEURS_AS484)} AS484 + {len(INDICATEURS_AS481)} AS481 + {len(INDICATEURS_AS480)} AS480 + {len(INDICATEURS_EFF)} EFF + {len(INDICATEURS_DEPR)} DEPR + {len(INDICATEURS_DACT)} DACT + {len(INDICATEURS_SAD)} SAD + {len(INDICATEURS_SADS)} SADS)")


if __name__ == "__main__":
    main()
