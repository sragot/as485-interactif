#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harmoniser_as480.py
====================
Harmonise le formulaire AS480 (Archives/AS480/*.csv et 00_brut/AS480/**) en
UNE table canonique propre (format long), prête pour Grist / Postgres / analyse.

Particularité de l'AS480 : deux SOUS-FORMULAIRES distincts, livrés dans des
fichiers séparés à partir de 2014-15 (dossiers AS480A_*/AS480G_*,
BD-AS-480A-*/BD-AS-480G-*) :
  - AS480A (Autochtones)
  - AS480G (Général)
Ils sont traités comme deux jeux de données distincts (colonne
`sous_formulaire`), JAMAIS fusionnés/mélangés dans le calcul des agrégats.

Les millésimes 2010-11 à 2013-14 sont livrés dans des classeurs Excel
"pivotés" (un onglet par page/colonne, établissements en lignes) : format
structurellement différent, non pris en charge ici. Ils apparaissent dans
rapport_qualite.csv avec 0 ligne retenue et un motif explicite plutôt que
d'être ignorés silencieusement.

Toute la logique de réconciliation de schéma (deux schémas de colonnes selon
l'année), d'encodage (cp1252 systématique), de parsing PLC (pages à suffixe
lettre incluses) et de découverte des sources (00_brut préféré à Archives) est
partagée avec les autres formulaires via le module harmoniser_as.py — voir
traiter_table() et lister_sources() là-bas pour le détail.

Usage
-----
    python harmoniser_as480.py
    python harmoniser_as480.py --root "C:/chemin/vers/depot"

Dépendances : pandas, openpyxl, xlrd (pour les .xls anciens), pyarrow (optionnel)
    pip install pandas openpyxl xlrd pyarrow
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from harmoniser_as import RACINE, lister_sources, traiter_table

CODE_FORM = "AS480"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Harmonise le formulaire AS480 (AS480A + AS480G) depuis "
                    "Archives/AS480 et 00_brut/AS480 en table canonique."
    )
    ap.add_argument("--root", default=str(RACINE), help="Racine du depot (contient Archives/ et 00_brut/).")
    args = ap.parse_args()

    racine = Path(args.root)
    print(f"=== {CODE_FORM} (sous-formulaires AS480A / AS480G) ===")

    candidats = lister_sources(CODE_FORM, racine)
    if not candidats:
        print(f"Aucune source trouvee pour {CODE_FORM}.", file=sys.stderr)
        return 1

    # L'AS480 n'a de sens qu'en tant que sous-formulaire A ou G : toute source
    # dont le sous-formulaire n'a pas pu etre determine (ex. un formulaire
    # vierge glisse dans 00_brut/Archives sans porter "480A"/"480G" dans son
    # nom) n'est pas une banque de donnees exploitable pour ce pipeline -> on
    # l'ecarte explicitement plutot que de la laisser polluer le rapport.
    ignores = {cle: c for cle, c in candidats.items() if cle[1] is None}
    for (an_debut, _), c in sorted(ignores.items()):
        print(f"  [!] source ignoree (sous-formulaire AS480A/AS480G indetermine) : {c.label}")
    candidats = {cle: c for cle, c in candidats.items() if cle[1] is not None}

    if not candidats:
        print("Aucune source AS480A/AS480G exploitable trouvee.", file=sys.stderr)
        return 1

    morceaux, lignes_rapport, tous_plc_rejetes = [], [], []
    for (an_debut, sous), candidat in sorted(candidats.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        exercice = f"{an_debut}-{an_debut + 1}"
        try:
            brut = candidat.loader()
        except Exception as e:  # classeur pivote, zip illisible, moteur absent...
            print(f"  {exercice} [{sous}]: ERREUR lecture ({candidat.label}) : {e}")
            lignes_rapport.append({
                "exercice": exercice, "sous_formulaire": sous, "source": candidat.label,
                "lignes_brutes": 0, "lignes_retenues": 0, "lignes_ecartees": 0,
                "etablissements": 0, "pages": 0, "chiffre_null": 0,
                "motif": f"erreur de lecture : {e}",
            })
            continue

        propre, plc_rejetes = traiter_table(brut, CODE_FORM, exercice, an_debut, sous, candidat.label)
        lignes_brutes, lignes_retenues = len(brut), len(propre)
        if plc_rejetes:
            tous_plc_rejetes.extend(plc_rejetes)

        if lignes_retenues == 0 and lignes_brutes > 0:
            motif = "format non reconnu (colonnes PLC/Page/Ligne/Colonne absentes ou non exploitables)"
        elif plc_rejetes:
            motif = f"{len(plc_rejetes)} code(s) PLC non reconnu(s)"
        else:
            motif = "ok"

        morceaux.append(propre)
        lignes_rapport.append({
            "exercice": exercice, "sous_formulaire": sous, "source": candidat.label,
            "lignes_brutes": lignes_brutes, "lignes_retenues": lignes_retenues,
            "lignes_ecartees": lignes_brutes - lignes_retenues,
            "etablissements": int(propre["etablissement_id"].nunique()) if lignes_retenues else 0,
            "pages": int(propre["page"].nunique()) if lignes_retenues else 0,
            "chiffre_null": int(propre["chiffre"].isna().sum()) if lignes_retenues else 0,
            "motif": motif,
        })
        print(f"  {exercice} [{sous}]: {lignes_brutes:>6,} lignes brutes -> {lignes_retenues:>6,} retenues   ({candidat.label})")
        if plc_rejetes:
            print(f"      PLC rejetes ({len(plc_rejetes)}) : {plc_rejetes[:10]}")

    if not morceaux:
        print("Aucune ligne retenue au total.", file=sys.stderr)
        return 1

    canon = pd.concat(morceaux, ignore_index=True)
    rapport = pd.DataFrame(lignes_rapport)

    # Exports
    outdir = racine / "20_canonique" / CODE_FORM
    outdir.mkdir(parents=True, exist_ok=True)

    csv_path = outdir / "as480_harmonise.csv"
    canon.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\nCSV ecrit : {csv_path}  ({len(canon):,} lignes)")

    try:
        pq_path = outdir / "as480_harmonise.parquet"
        canon.to_parquet(pq_path, index=False)
        print(f"Parquet ecrit : {pq_path}")
    except Exception as e:  # pyarrow absent : on continue sans bloquer
        print(f"(Parquet ignore : {e})")

    rap_path = outdir / "rapport_qualite.csv"
    rapport.to_csv(rap_path, index=False, encoding="utf-8-sig")
    print(f"Rapport qualite : {rap_path}")

    # --- Verification : lignes_brutes vs retenues, par exercice ET par sous-formulaire ---
    print("\n--- Verification lignes_brutes vs retenues (par exercice x sous-formulaire) ---")
    pertes = rapport[rapport["lignes_ecartees"] > 0]
    if pertes.empty:
        print("Aucune perte : 100% des lignes brutes sont retenues, sur tous les exercices/sous-formulaires.")
    else:
        print("ATTENTION - pertes detectees (PLC non reconnu ou format non exploitable) :")
        print(pertes[["exercice", "sous_formulaire", "lignes_brutes", "lignes_retenues",
                       "lignes_ecartees", "motif"]].to_string(index=False))

    total_brutes = int(rapport["lignes_brutes"].sum())
    total_retenues = int(rapport["lignes_retenues"].sum())
    taux = (total_retenues / total_brutes * 100) if total_brutes else 0.0
    print(f"\nTotal (sources exploitables) : {total_brutes:,} lignes brutes -> {total_retenues:,} retenues ({taux:.2f}%)")
    if tous_plc_rejetes:
        distincts = sorted(set(tous_plc_rejetes))
        print(f"PLC non reconnus (total) : {len(distincts)} valeurs distinctes -> {distincts[:20]}")

    print("\n--- Resume par sous-formulaire ---")
    for sous in sorted(canon["sous_formulaire"].dropna().unique()):
        sub = canon[canon["sous_formulaire"] == sous]
        print(f"  {sous}: {len(sub):,} lignes, {sub['exercice'].nunique()} exercices "
              f"({sub['exercice_debut'].min()} -> {sub['exercice_debut'].max()}), "
              f"{sub['etablissement_id'].nunique()} etablissements, "
              f"{sub['page'].nunique()} pages")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
