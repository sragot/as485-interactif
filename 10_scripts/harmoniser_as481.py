#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harmoniser_as481.py
====================
Harmonise les BD annuelles AS481 (Archives/AS481/*.csv, 00_brut/AS481/**) en
UNE table canonique propre (format long), prête pour Grist / Postgres / analyse.

Toute la logique de reconciliation de schéma / parsing PLC / nettoyage est
partagée avec les autres formulaires (AS478, AS480, AS484, AS485) via le
module harmoniser_as.py — voir traiter_table() là-bas pour le détail des
pièges gérés (deux schémas de colonnes, encodage cp1252, pages à suffixe
lettre...). Schéma confirmé sur l'AS481 (2011-12, 2016-17, 2018-19, 2022-23) :
  - ancien (<= 2017-18) : séparateur ";", colonnes
    Rapport, PeriodeFinanciere, RSS, CorrespEtabInstal, NomAbreg, Classe,
    nomClasse, Groupe, GroupeDesc, Statut, ModFin, Missions, PLC, LC, P, L, C,
    ValeurSaisie, Chiffre
  - récent (>= 2018-19) : séparateur ",", colonnes
    Rapport, DateDebutAnneeFinanciere, DateFinAnneeFinanciere, RSS,
    NoEtablissement, NomEtablissement, PLC, LC, Page, SousPage, Ligne,
    Colonne, ValeurSaisie, Chiffre, NoInstallation, NomInstallation

Usage
-----
    python harmoniser_as481.py
    python harmoniser_as481.py --root ".." --outdir "20_canonique/AS481"

Dépendances : pandas, openpyxl, xlrd (facultatif pour les .xls anciens),
pyarrow (facultatif pour le .parquet)
    pip install pandas openpyxl xlrd pyarrow
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd

from harmoniser_as import RACINE, lister_sources, traiter_table

CODE_FORM = "AS481"


def main() -> int:
    ap = argparse.ArgumentParser(description="Harmonise les BD annuelles AS481.")
    ap.add_argument("--root", default=str(RACINE), help="Racine du depot.")
    ap.add_argument("--outdir", default=None,
                     help="Dossier de sortie (defaut : <root>/20_canonique/AS481)")
    args = ap.parse_args()

    racine = Path(args.root)
    outdir = Path(args.outdir) if args.outdir else racine / "20_canonique" / CODE_FORM
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Recherche des sources {CODE_FORM} dans {racine / 'Archives' / CODE_FORM} "
          f"et {racine / '00_brut' / CODE_FORM} ...")
    candidats = lister_sources(CODE_FORM, racine)
    if not candidats:
        print(f"ERREUR : aucune source {CODE_FORM} trouvee.", file=sys.stderr)
        return 1

    print(f"Exercices detectes : {len(candidats)}")

    morceaux, lignes_rapport, tous_plc_rejetes = [], [], []
    for (an_debut, _sous), candidat in sorted(candidats.items(), key=lambda kv: kv[0][0]):
        exercice = f"{an_debut}-{an_debut + 1}"
        try:
            brut = candidat.loader()
        except Exception as e:
            print(f"  {exercice}: ERREUR lecture ({candidat.label}) : {e}", file=sys.stderr)
            lignes_rapport.append({
                "exercice": exercice, "source": candidat.label,
                "lignes_brutes": 0, "lignes_retenues": 0, "lignes_ecartees": 0,
                "etablissements": 0, "pages": 0, "chiffre_null": 0,
                "motif": f"erreur de lecture : {e}",
            })
            continue

        propre, plc_rejetes = traiter_table(brut, CODE_FORM, exercice, an_debut, None, candidat.label)
        if plc_rejetes:
            tous_plc_rejetes.extend(plc_rejetes)

        lignes_brutes, lignes_retenues = len(brut), len(propre)
        if lignes_retenues == 0 and lignes_brutes > 0:
            motif = "format non reconnu (colonnes PLC/Page/Ligne/Colonne absentes ou non exploitables)"
        elif plc_rejetes:
            motif = f"{len(plc_rejetes)} code(s) PLC non reconnu(s)"
        else:
            motif = "ok"

        morceaux.append(propre)
        lignes_rapport.append({
            "exercice": exercice, "source": candidat.label,
            "lignes_brutes": lignes_brutes, "lignes_retenues": lignes_retenues,
            "lignes_ecartees": lignes_brutes - lignes_retenues,
            "etablissements": int(propre["etablissement_id"].nunique()) if lignes_retenues else 0,
            "pages": int(propre["page"].nunique()) if lignes_retenues else 0,
            "chiffre_null": int(propre["chiffre"].isna().sum()) if lignes_retenues else 0,
            "motif": motif,
        })
        print(f"  {exercice}: {lignes_brutes:>6} lignes brutes -> {lignes_retenues:>6} retenues   ({candidat.label})")
        if plc_rejetes:
            print(f"      PLC rejetes ({len(plc_rejetes)}): {plc_rejetes[:10]}")

    if not morceaux:
        print("ERREUR : aucune donnee exploitable.", file=sys.stderr)
        return 1

    canon = pd.concat(morceaux, ignore_index=True)

    # Exports
    csv_path = outdir / "as481_harmonise.csv"
    canon.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\nCSV ecrit : {csv_path}  ({len(canon):,} lignes)")

    try:
        pq_path = outdir / "as481_harmonise.parquet"
        canon.to_parquet(pq_path, index=False)
        print(f"Parquet ecrit : {pq_path}")
    except Exception as e:  # pyarrow absent : on continue sans bloquer
        print(f"(Parquet ignore : {e})")

    rapport = pd.DataFrame(lignes_rapport)
    rap_path = outdir / "rapport_qualite.csv"
    rapport.to_csv(rap_path, index=False, encoding="utf-8-sig")
    print(f"Rapport qualite : {rap_path}")

    print("\n--- Resume ---")
    print(f"Total lignes canoniques : {len(canon):,}")
    print(f"Exercices couverts      : {canon['exercice'].nunique()} "
          f"({canon['exercice_debut'].min()} -> {canon['exercice_debut'].max()})")
    print(f"Etablissements distincts : {canon['etablissement_id'].nunique()}")
    print(f"Regions (RSS) distinctes : {canon['rss'].nunique()}")

    total_brut = int(rapport["lignes_brutes"].sum())
    total_retenu = int(rapport["lignes_retenues"].sum())
    perte = total_brut - total_retenu
    taux = (perte / total_brut * 100) if total_brut else 0.0
    print(f"Lignes brutes totales    : {total_brut:,}")
    print(f"Lignes retenues totales  : {total_retenu:,}")
    print(f"Perte                    : {perte:,} ({taux:.3f} %)")
    if tous_plc_rejetes:
        distincts = sorted(set(tous_plc_rejetes))
        print(f"PLC non reconnus (total) : {len(distincts)} valeurs distinctes")
        print(f"  {distincts[:30]}")
    else:
        print("PLC non reconnus (total) : 0")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
