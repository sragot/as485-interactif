#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harmoniser_as484.py
====================
Harmonise les bases de données annuelles AS484 (Archives/AS484/*.csv|*.zip et
00_brut/AS484/**, un fichier par exercice) en UNE table canonique propre
(format long), prête pour Grist / Postgres / analyse.

Schéma confirmé sur l'AS484 (inspection de 2010-11, 2013-14, 2016-17, 2018-19
et 2022-23) — identique à l'AS485, géré par la table d'alias partagée :
  - ancien (<= 2017-18) : séparateur ";", encodage cp1252, colonnes
    Rapport, PeriodeFinanciere, RSS, CorrespEtabInstal, NomAbreg, Classe,
    nomClasse, Groupe, GroupeDesc, Statut, ModFin, Missions, PLC, LC, P, L, C,
    ValeurSaisie, Chiffre
  - récent (>= 2018-19) : séparateur ",", colonnes
    Rapport, DateDebutAnneeFinanciere, DateFinAnneeFinanciere, RSS,
    NoEtablissement, NomEtablissement, [Statut, ModFin, Missions en 2018-19
    seulement], PLC, LC, Page, SousPage, Ligne, Colonne, ValeurSaisie, Chiffre,
    NoInstallation, NomInstallation
Aucun alias supplémentaire n'a été nécessaire : la table ALIAS_COLONNES de
harmoniser_as.py (construite sur l'AS485) couvre déjà tous ces en-têtes.

Toute la logique de découverte des sources (00_brut préféré, puis CSV direct
dans Archives, puis CSV extrait d'un zip), de décodage (cp1252 systématique)
et de reconciliation de schéma / parsing PLC est partagée via le module
harmoniser_as.py — voir traiter_table() là-bas pour le détail des pièges
gérés (deux schémas de colonnes, pages à suffixe lettre...).

Usage
-----
    python harmoniser_as484.py
    python harmoniser_as484.py --root "C:/chemin/vers/le/depot"

Dépendances : pandas, openpyxl, xlrd (pour les .xls anciens rencontrés en
Archives ; absent -> ces fichiers sont ignorés avec un avertissement),
pyarrow (optionnel pour le .parquet).
    pip install pandas openpyxl xlrd pyarrow
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd

from harmoniser_as import RACINE, lister_sources, traiter_table

CODE_FORM = "AS484"


def main() -> int:
    ap = argparse.ArgumentParser(description="Harmonise les bases de données annuelles AS484.")
    ap.add_argument("--root", default=str(RACINE), help="Racine du dépôt.")
    args = ap.parse_args()

    racine = Path(args.root)
    outdir = racine / "20_canonique" / CODE_FORM
    outdir.mkdir(parents=True, exist_ok=True)

    candidats = lister_sources(CODE_FORM, racine)
    if not candidats:
        print(f"ERREUR : aucune source AS484 trouvee sous {racine / 'Archives' / CODE_FORM} "
              f"ni {racine / '00_brut' / CODE_FORM}", file=sys.stderr)
        return 1

    print(f"Sources AS484 detectees : {len(candidats)}")

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
            "exercice": exercice,
            "source": candidat.label,
            "lignes_brutes": lignes_brutes,
            "lignes_retenues": lignes_retenues,
            "lignes_ecartees": lignes_brutes - lignes_retenues,
            "etablissements": int(propre["etablissement_id"].nunique()),
            "pages": int(propre["page"].nunique()),
            "chiffre_null": int(propre["chiffre"].isna().sum()),
            "motif": motif,
        })
        print(f"  {exercice}: {lignes_brutes:>6} lignes brutes -> {lignes_retenues:>6} retenues   ({candidat.label})")
        if plc_rejetes:
            print(f"      PLC rejetes ({len(plc_rejetes)}): {plc_rejetes[:10]}")

    if not morceaux:
        print("Aucune source exploitable.", file=sys.stderr)
        return 1

    canon = pd.concat(morceaux, ignore_index=True)

    # Exports
    csv_path = outdir / "as484_harmonise.csv"
    canon.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\nCSV ecrit : {csv_path}  ({len(canon):,} lignes)")

    try:
        pq_path = outdir / "as484_harmonise.parquet"
        canon.to_parquet(pq_path, index=False)
        print(f"Parquet ecrit : {pq_path}")
    except Exception as e:  # pyarrow absent : on continue sans bloquer
        print(f"(Parquet ignore : {e})")

    rapport = pd.DataFrame(lignes_rapport)
    rap_path = outdir / "rapport_qualite.csv"
    rapport.to_csv(rap_path, index=False, encoding="utf-8-sig")
    print(f"Rapport qualite : {rap_path}")

    # --- Verification obligatoire : lignes_brutes vs lignes_retenues par exercice ---
    print("\n--- Verification lignes_brutes vs lignes_retenues ---")
    print(rapport[["exercice", "lignes_brutes", "lignes_retenues", "lignes_ecartees", "motif"]]
          .to_string(index=False))
    total_brutes = int(rapport["lignes_brutes"].sum())
    total_ecartees = int(rapport["lignes_ecartees"].sum())
    taux_perte = (total_ecartees / total_brutes * 100) if total_brutes else 0.0
    print(f"\nTotal lignes brutes  : {total_brutes:,}")
    print(f"Total lignes ecartees: {total_ecartees:,}  ({taux_perte:.3f} %)")
    if tous_plc_rejetes:
        distincts = sorted(set(tous_plc_rejetes))
        print(f"PLC non reconnus (total) : {len(distincts)} valeurs distinctes -> {distincts[:20]}")
    else:
        print("PLC non reconnus : aucun.")

    print("\n--- Resume ---")
    print(f"Total lignes canoniques : {len(canon):,}")
    print(f"Exercices couverts      : {canon['exercice'].nunique()} "
          f"({canon['exercice_debut'].min()} -> {canon['exercice_debut'].max()})")
    print(f"Etablissements distincts : {canon['etablissement_id'].nunique()}")
    print(f"Regions (RSS) distinctes : {canon['rss'].nunique()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
