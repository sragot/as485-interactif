#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harmoniser_as485.py
===================
Harmonise les feuilles annuelles AS485 du classeur « Stats.xlsx » en UNE table
canonique propre (format long), prête pour Grist / Postgres / analyse.

Ce que fait le script
---------------------
1. Ouvre Stats.xlsx et repère les feuilles annuelles (nom = "AAAA-AAAA").
2. Réconcilie les DEUX schémas présents dans le fichier :
      - récent  (>= 2018-19) : NoEtablissement / NomEtablissement / Page / SousPage / Ligne / Colonne
      - ancien  (<= 2017-18) : CorrespEtabInstal / NomAbreg / P / L / C
3. Reparse le code PLC (P09-0L01C01, P09L01C01, P04TL09C06...) pour fiabiliser
   page / souspage / ligne / colonne, y compris les pages à suffixe lettre.
4. Nettoie : encodage UTF-8, espaces, valeurs numériques, exercice normalisé.
5. Exporte :
      - as485_harmonise.csv      (UTF-8-BOM, ouvrable direct dans Excel)
      - as485_harmonise.parquet  (si pyarrow dispo — idéal pour Postgres/BI)
      - rapport_qualite.csv      (contrôles par exercice)

Usage
-----
    python harmoniser_as485.py
    python harmoniser_as485.py --input "Demographic Data/Stats.xlsx" --outdir "AS485_harmonise"

Dépendances : pandas, openpyxl  (pyarrow optionnel pour le .parquet)
    pip install pandas openpyxl pyarrow
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

import pandas as pd

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# Une feuille annuelle a un nom de la forme "2019-2020".
RE_FEUILLE_ANNEE = re.compile(r"^\s*(\d{4})\s*-\s*(\d{4})\s*$")

# Le code PLC : P<page>[-<souspage>]L<ligne>C<colonne>
#   ex. "P09-0L01C01", "P09L01C01", "P01L40C03",
#   et surtout les pages à SUFFIXE LETTRE des années anciennes :
#   "P04TL09C06", "P05AL01C01", "P07BL03C02" (variantes A / B / T d'une page).
RE_PLC = re.compile(r"P(\d+[A-Za-z]?)(?:-(\d+))?L(\d+)C(\d+)", re.IGNORECASE)

# Correspondance en-tête source -> nom de colonne canonique.
# On liste tous les alias rencontrés dans les deux schémas du fichier.
ALIAS_COLONNES = {
    "rapport": "rapport",
    "rss": "rss",
    # identifiant d'établissement
    "noetablissement": "etablissement_id",
    "correspetabinstal": "etablissement_id",
    # nom d'établissement
    "nometablissement": "etablissement_nom",
    "nomabreg": "etablissement_nom",
    # coordonnées de cellule
    "page": "page",
    "p": "page",
    "souspage": "souspage",
    "ligne": "ligne",
    "l": "ligne",
    "colonne": "colonne",
    "c": "colonne",
    # codes bruts
    "plc": "plc",
    "lc": "lc",
    # valeurs
    "valeursaisie": "valeur_saisie",
    "chiffre": "chiffre",
}

# Colonnes finales, dans l'ordre.
COLONNES_FINALES = [
    "exercice", "exercice_debut", "rapport", "rss",
    "etablissement_id", "etablissement_nom",
    "page", "souspage", "ligne", "colonne", "plc",
    "valeur_saisie", "chiffre",
    "code_cellule",          # clé stable page-ligne-colonne pour jointure au dictionnaire
    "source_feuille",
]


# --------------------------------------------------------------------------- #
# Fonctions utilitaires
# --------------------------------------------------------------------------- #

def normaliser_entete(nom) -> str:
    """Nettoie un nom de colonne pour le matcher aux alias (minuscule, sans espaces)."""
    return re.sub(r"[^a-z0-9]", "", str(nom).strip().lower())


def normaliser_page(tok):
    """Normalise un jeton de page ("9", "04T", "5a") -> "09", "04T", "05A" ; ou None."""
    if tok is None:
        return None
    m = re.match(r"\s*(\d+)\s*([A-Za-z]?)", str(tok))
    if not m:
        return None
    num, suf = m.groups()
    return f"{int(num):02d}{suf.upper()}"


def parser_plc(plc):
    """Reparse le code PLC -> (page:str, souspage:int|None, ligne:int, colonne:int).

    La page est renvoyée en TEXTE car elle peut porter un suffixe lettre
    (ex. "04T"). Retourne (None, None, None, None) si le code est illisible.
    """
    if plc is None:
        return (None, None, None, None)
    m = RE_PLC.search(str(plc))
    if not m:
        return (None, None, None, None)
    page, souspage, ligne, colonne = m.groups()
    return (
        normaliser_page(page),
        int(souspage) if souspage is not None else None,
        int(ligne),
        int(colonne),
    )


def vers_int(serie: pd.Series) -> pd.Series:
    """Convertit en entier nullable (Int64), tolérant aux vides et aux flottants."""
    return pd.to_numeric(serie, errors="coerce").astype("Int64")


def vers_num(serie: pd.Series) -> pd.Series:
    """Convertit en flottant, tolérant aux vides et aux textes."""
    return pd.to_numeric(serie, errors="coerce")


def nettoyer_texte(serie: pd.Series) -> pd.Series:
    """Strip + espaces multiples réduits ; garde la casse d'origine."""
    return (
        serie.astype("string")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )


# --------------------------------------------------------------------------- #
# Traitement d'une feuille
# --------------------------------------------------------------------------- #

def traiter_feuille(df: pd.DataFrame, nom_feuille: str, an_debut: int) -> pd.DataFrame:
    """Transforme une feuille annuelle brute en table canonique."""
    # 1. Renommer les colonnes vers le schéma canonique
    renommage = {}
    for col in df.columns:
        cle = normaliser_entete(col)
        if cle in ALIAS_COLONNES:
            renommage[col] = ALIAS_COLONNES[cle]
    df = df.rename(columns=renommage)

    # 2. S'assurer que toutes les colonnes attendues existent
    for c in ["rapport", "rss", "etablissement_id", "etablissement_nom",
              "page", "souspage", "ligne", "colonne", "plc",
              "valeur_saisie", "chiffre"]:
        if c not in df.columns:
            df[c] = pd.NA

    # 3. Reparse du PLC (source de vérité pour les coordonnées) avec repli
    #    sur les colonnes déjà présentes si le PLC est absent.
    parsed = df["plc"].map(parser_plc)
    p_page = parsed.map(lambda t: t[0])
    p_sous = parsed.map(lambda t: t[1])
    p_ligne = parsed.map(lambda t: t[2])
    p_col = parsed.map(lambda t: t[3])

    # page = TEXTE (peut contenir un suffixe lettre) ; repli sur la colonne P/Page
    fallback_page = df["page"].map(normaliser_page)
    df["page"]     = p_page.where(p_page.notna(), fallback_page).astype("string")
    df["souspage"] = vers_int(p_sous.where(p_sous.notna(), df["souspage"]))
    df["ligne"]    = vers_int(p_ligne.where(p_ligne.notna(), df["ligne"]))
    df["colonne"]  = vers_int(p_col.where(p_col.notna(), df["colonne"]))

    # 4. Nettoyage des champs texte / numériques
    df["rapport"] = nettoyer_texte(df["rapport"])
    df["rss"] = nettoyer_texte(df["rss"])
    df["etablissement_id"] = nettoyer_texte(df["etablissement_id"])
    df["etablissement_nom"] = nettoyer_texte(df["etablissement_nom"])
    df["plc"] = nettoyer_texte(df["plc"])
    df["valeur_saisie"] = vers_num(df["valeur_saisie"])
    df["chiffre"] = vers_num(df["chiffre"])

    # 5. Colonnes dérivées
    df["exercice"] = f"{an_debut}-{an_debut + 1}"
    df["exercice_debut"] = an_debut
    df["source_feuille"] = nom_feuille
    # Clé de cellule stable (indépendante du format PLC) pour jointure au dictionnaire
    df["code_cellule"] = (
        "P" + df["page"].astype("string")
        + "L" + df["ligne"].astype("string").str.zfill(2)
        + "C" + df["colonne"].astype("string").str.zfill(2)
    )

    # 6. Ne garder que les lignes AS485 avec des coordonnées valides
    df = df[(df["rapport"].str.upper() == "AS485")]
    df = df[df["page"].notna() & df["ligne"].notna() & df["colonne"].notna()]

    return df[COLONNES_FINALES]


# --------------------------------------------------------------------------- #
# Programme principal
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description="Harmonise les feuilles AS485 de Stats.xlsx.")
    ap.add_argument("--input", default="Demographic Data/Stats.xlsx",
                    help="Chemin vers Stats.xlsx")
    ap.add_argument("--outdir", default="AS485_harmonise",
                    help="Dossier de sortie")
    args = ap.parse_args()

    chemin = Path(args.input)
    if not chemin.exists():
        print(f"ERREUR : fichier introuvable -> {chemin}", file=sys.stderr)
        return 1

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"Lecture de : {chemin}")
    xls = pd.ExcelFile(chemin, engine="openpyxl")

    feuilles_annuelles = []
    for nom in xls.sheet_names:
        m = RE_FEUILLE_ANNEE.match(nom)
        if m:
            feuilles_annuelles.append((nom, int(m.group(1))))

    if not feuilles_annuelles:
        print("Aucune feuille annuelle 'AAAA-AAAA' trouvée.", file=sys.stderr)
        return 1

    print(f"Feuilles annuelles détectées : {len(feuilles_annuelles)}")

    morceaux, lignes_rapport = [], []
    for nom, an in sorted(feuilles_annuelles, key=lambda t: t[1]):
        brut = pd.read_excel(xls, sheet_name=nom, dtype=object)
        propre = traiter_feuille(brut, nom, an)
        morceaux.append(propre)
        lignes_rapport.append({
            "exercice": f"{an}-{an + 1}",
            "feuille": nom,
            "lignes_brutes": len(brut),
            "lignes_retenues": len(propre),
            "etablissements": propre["etablissement_id"].nunique(),
            "regions_rss": propre["rss"].nunique(),
            "pages": propre["page"].nunique(),
            "lignes_ecartees": int(brut.shape[0] - len(propre)),
            "chiffre_null": int(propre["chiffre"].isna().sum()),
        })
        print(f"  {nom}: {len(brut):>6} lignes brutes -> {len(propre):>6} retenues")

    canon = pd.concat(morceaux, ignore_index=True)

    # Exports
    csv_path = outdir / "as485_harmonise.csv"
    canon.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\nCSV ecrit : {csv_path}  ({len(canon):,} lignes)")

    try:
        pq_path = outdir / "as485_harmonise.parquet"
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
