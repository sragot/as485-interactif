#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
harmoniser_as.py
================
Module générique d'harmonisation des formulaires statistiques annuels du MSSS
(AS478, AS480, AS481, AS484, AS485) en une table canonique propre (format
long), prête pour Grist / Postgres / analyse.

Tous ces formulaires partagent le même modèle de données : un code de cellule
PLC (Page/Ligne/Colonne) et deux générations de schéma CSV au fil des ans.

Pièges connus (identifiés sur l'AS485, valables pour toute la famille) :
  1. DEUX schémas selon l'année :
       - ancien (<= 2017-18) : séparateur ";", colonnes
         Rapport, PeriodeFinanciere, RSS, CorrespEtabInstal, NomAbreg, ...,
         PLC, LC, P, L, C, ValeurSaisie, Chiffre
       - récent (>= 2018-19) : séparateur ",", colonnes
         Rapport, DateDebutAnneeFinanciere, ..., NoEtablissement,
         NomEtablissement, PLC, LC, Page, SousPage, Ligne, Colonne,
         ValeurSaisie, Chiffre
     L'AS478 n'a JAMAIS de colonne "Rapport" (ni ancien ni récent schéma) :
     le code de formulaire est alors déduit du paramètre --formulaire.
  2. Encodage ISO-8859-1 / cp1252 sur TOUTE la période (anciens ET récents
     fichiers) : jamais d'UTF-8 réel malgré les apparences. Décoder en
     cp1252 systématiquement, sinon accents cassés ("des Îles" -> "des ëles").
  3. Code PLC : "P09-0L01C01", "P09L01C01", et les pages à SUFFIXE LETTRE
     "P04TL09C06", "P05AL01C01". La page reste du TEXTE (ex. "04T").
  4. AS480 a deux sous-formulaires distincts : AS480A (Autochtones) et
     AS480G (Général), livrés dans des fichiers séparés à partir de 2014-15.
     Les millésimes 2010-11 à 2013-14 sont livrés dans des classeurs Excel
     "pivotés" (un onglet par page/colonne, établissements en lignes) —
     un format structurellement différent, non pris en charge ici : ils sont
     déclarés dans le rapport qualité avec 0 ligne retenue et un motif
     explicite plutôt que d'être ignorés silencieusement.

Sources d'entrée (pour chaque formulaire) :
  - 00_brut/<ASxxx>/<dossier>/*.csv|*.txt   (déjà décompressés)
  - Archives/<ASxxx>/<exercice>/*.csv|*.zip|*.xls|*.xlsx  (bruts / zippés)
  Quand un même exercice existe aux deux endroits, 00_brut est préféré, puis
  un CSV direct dans Archives, puis un CSV extrait d'un .zip d'Archives —
  afin de ne jamais compter deux fois les mêmes lignes.

Usage
-----
    python harmoniser_as.py --formulaire AS478
    python harmoniser_as.py --formulaire AS480      # traite AS480A + AS480G
    python harmoniser_as.py                         # AS478, AS480, AS481, AS484

Le formulaire AS485 dispose d'un classeur consolidé (Demographic Data/Stats.xlsx,
un onglet par exercice, couvrant aussi 2023-24/2024-25 absents des Archives) :
son pipeline reste harmoniser_as485.py, qui réutilise les fonctions de ce
module. Passer --formulaire AS485 ici ne scanne QUE Archives/00_brut (utile en
validation croisée) et écrit dans un dossier distinct pour ne jamais écraser
la sortie de référence.

Dépendances : pandas, openpyxl, xlrd (xlrd seulement pour lire les .xls
anciens rencontrés en 00_brut/Archives ; absent -> ces fichiers sont ignorés
avec un avertissement).
    pip install pandas openpyxl xlrd pyarrow
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import unicodedata
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

# --------------------------------------------------------------------------- #
# Configuration commune à tous les formulaires
# --------------------------------------------------------------------------- #

RACINE = Path(__file__).resolve().parent.parent

FORMULAIRES_CONNUS = ["AS478", "AS480", "AS481", "AS484", "AS485"]

# Une feuille annuelle (classeur consolidé type Stats.xlsx) a un nom "2019-2020".
RE_FEUILLE_ANNEE = re.compile(r"^\s*(\d{4})\s*-\s*(\d{4})\s*$")

# Le code PLC : P<page>[-<souspage>]L<ligne>C<colonne>
#   ex. "P09-0L01C01", "P09L01C01", "P01L40C03",
#   et les pages à SUFFIXE LETTRE : "P04TL09C06", "P05AL01C01", "P07BL03C02".
RE_PLC = re.compile(r"P(\d+[A-Za-z]?)(?:-(\d+))?L(\d+)C(\d+)", re.IGNORECASE)

# Extrait l'année de DÉBUT d'un exercice depuis un nom de dossier/fichier :
# "2019-2020", "2019_2020", "2010-11", "2010_11" -> 2019 / 2010.
RE_AN_DEBUT_LONG = re.compile(r"(20\d{2})\s*[-_]\s*(?:20)?(\d{2,4})")
RE_AN_DEBUT_SEUL = re.compile(r"(20\d{2})")

# Correspondance en-tête source -> nom de colonne canonique (union des deux
# schémas et de tous les formulaires observés).
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

# Colonnes canoniques de base, dans l'ordre (communes à tous les formulaires).
COLONNES_FINALES = [
    "exercice", "exercice_debut", "rapport", "rss",
    "etablissement_id", "etablissement_nom",
    "page", "souspage", "ligne", "colonne", "plc",
    "valeur_saisie", "chiffre",
    "code_cellule",          # clé stable page-ligne-colonne pour jointure au dictionnaire
    "source_feuille",
]

# Colonnes brutes que traiter_table() garantit toujours présentes avant renommage.
COLONNES_REQUISES_BRUT = [
    "rapport", "rss", "etablissement_id", "etablissement_nom",
    "page", "souspage", "ligne", "colonne", "plc",
    "valeur_saisie", "chiffre",
]

# Fragments de nom de fichier signalant un document qui n'est PAS une banque
# de données (formulaire vierge, notice explicative...) à écarter d'emblée.
MOTS_EXCLUS = ("formulaire", "explication", "instruction", "rapport-statistique-annuel")

EXTENSIONS_DONNEES = {".csv", ".txt", ".xls", ".xlsx", ".xlsm"}


# --------------------------------------------------------------------------- #
# Fonctions utilitaires (génériques, réutilisées par harmoniser_as485.py)
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
    if plc is None or (isinstance(plc, float) and pd.isna(plc)):
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


def _sans_accents(texte: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c)
    )


def extraire_an_debut(texte: str) -> Optional[int]:
    """Extrait l'année de début d'exercice depuis un nom de dossier/fichier."""
    m = RE_AN_DEBUT_LONG.search(texte)
    if m:
        return int(m.group(1))
    m = RE_AN_DEBUT_SEUL.search(texte)
    if m:
        return int(m.group(1))
    return None


def detecter_sous_formulaire(nom: str) -> Optional[str]:
    """Détecte le sous-formulaire AS480A / AS480G depuis un nom de fichier."""
    n = _sans_accents(nom).upper()
    if "480A" in n or "AUTOCHTONE" in n:
        return "AS480A"
    if "480G" in n or "GENERAL" in n:
        return "AS480G"
    return None


def _nom_exclu(nom: str) -> bool:
    n = _sans_accents(nom).lower()
    return any(mot in n for mot in MOTS_EXCLUS)


# --------------------------------------------------------------------------- #
# Lecture des fichiers bruts (CSV deux schémas, xls/xlsx, dans ou hors zip)
# --------------------------------------------------------------------------- #

def lire_csv_bytes(data: bytes, label: str) -> pd.DataFrame:
    """Lit un CSV brut MSSS : encodage cp1252 systématique, séparateur ; ou ,."""
    texte = data.decode("cp1252", errors="replace")
    lignes = texte.splitlines()
    premiere = lignes[0] if lignes else ""
    sep = ";" if premiere.count(";") >= premiere.count(",") else ","
    try:
        return pd.read_csv(io.StringIO(texte), sep=sep, dtype=str)
    except pd.errors.ParserError:
        # Repli : dernière ligne tronquée (guillemet non refermé) -> on l'ignore.
        if lignes and lignes[-1].count('"') % 2 == 1:
            print(f"    [!] {label} : ligne finale tronquee ignoree")
            return pd.read_csv(io.StringIO("\n".join(lignes[:-1])), sep=sep, dtype=str)
        raise


# Au-dela de ce nombre d'onglets, un classeur Excel n'est plus un simple export
# "banque de donnees" (1 onglet = 1 exercice) mais un formulaire pivote (1 onglet
# par page/ligne/colonne, etablissements en lignes) : structure differente, non
# prise en charge ici (necessiterait un depivotage dedie).
SEUIL_ONGLETS_PIVOTE = 3


def lire_excel_bytes(data: bytes, ext: str, label: str) -> pd.DataFrame:
    """Lit la première feuille d'un classeur Excel (xls/xlsx/xlsm)."""
    engine = "xlrd" if ext == ".xls" else "openpyxl"
    try:
        xls = pd.ExcelFile(io.BytesIO(data), engine=engine)
    except Exception as e:  # moteur absent, classeur corrompu, etc.
        print(f"    [!] {label} : lecture Excel impossible ({e})")
        return pd.DataFrame()
    if len(xls.sheet_names) > SEUIL_ONGLETS_PIVOTE:
        raise ValueError(
            f"classeur multi-onglets pivote ({len(xls.sheet_names)} onglets) - "
            "format non standard hors perimetre (necessiterait un depivotage dedie)"
        )
    return pd.read_excel(xls, sheet_name=0, dtype=str)


def lire_fichier(chemin: Path) -> pd.DataFrame:
    ext = chemin.suffix.lower()
    if ext in (".csv", ".txt"):
        return lire_csv_bytes(chemin.read_bytes(), str(chemin))
    return lire_excel_bytes(chemin.read_bytes(), ext, str(chemin))


def lire_membre_zip(chemin_zip: Path, membre: str) -> pd.DataFrame:
    with zipfile.ZipFile(chemin_zip) as z:
        data = z.read(membre)
    ext = Path(membre).suffix.lower()
    label = f"{chemin_zip}::{membre}"
    if ext in (".csv", ".txt"):
        return lire_csv_bytes(data, label)
    return lire_excel_bytes(data, ext, label)


# --------------------------------------------------------------------------- #
# Découverte des sources annuelles (Archives/ + 00_brut/)
# --------------------------------------------------------------------------- #

@dataclass
class SourceCandidate:
    label: str
    priorite: tuple
    loader: Callable[[], pd.DataFrame]


def _enregistrer(index: dict, cle, candidat: SourceCandidate) -> None:
    existant = index.get(cle)
    if existant is None or candidat.priorite < existant.priorite:
        index[cle] = candidat


def lister_sources(code_form: str, racine: Path = RACINE) -> dict:
    """Retourne { (an_debut, sous_formulaire|None): SourceCandidate } pour un formulaire.

    Priorité en cas de doublon (même exercice trouvé à plusieurs endroits) :
    00_brut (0) < CSV/TXT direct dans Archives (1) < CSV/TXT extrait d'un zip
    Archives (2) < classeur Excel direct (3) < classeur Excel dans un zip (4).
    Ainsi un même exercice n'est jamais compté deux fois.
    """
    index: dict = {}
    racines = [(racine / "00_brut" / code_form, 0), (racine / "Archives" / code_form, 1)]

    for dossier, base_prio in racines:
        if not dossier.exists():
            continue
        for chemin in sorted(dossier.rglob("*")):
            if not chemin.is_file():
                continue
            ext = chemin.suffix.lower()

            if ext in (".csv", ".txt", ".xls", ".xlsx", ".xlsm"):
                if _nom_exclu(chemin.name):
                    continue
                an_debut = extraire_an_debut(chemin.parent.name) or extraire_an_debut(chemin.name)
                if an_debut is None:
                    print(f"    [!] exercice indetermine, ignore : {chemin}")
                    continue
                sous = detecter_sous_formulaire(chemin.name) if code_form == "AS480" else None
                rang_type = 0 if ext in (".csv", ".txt") else 3
                candidat = SourceCandidate(
                    label=str(chemin.relative_to(racine)),
                    priorite=(base_prio, rang_type),
                    loader=(lambda p=chemin: lire_fichier(p)),
                )
                _enregistrer(index, (an_debut, sous), candidat)

            elif ext == ".zip":
                if _nom_exclu(chemin.name):
                    continue
                try:
                    with zipfile.ZipFile(chemin) as z:
                        membres = [n for n in z.namelist() if Path(n).suffix.lower() in EXTENSIONS_DONNEES]
                except zipfile.BadZipFile:
                    print(f"    [!] archive zip illisible : {chemin}")
                    continue
                for membre in membres:
                    if _nom_exclu(Path(membre).name):
                        continue
                    an_debut = (
                        extraire_an_debut(chemin.parent.name)
                        or extraire_an_debut(chemin.name)
                        or extraire_an_debut(membre)
                    )
                    if an_debut is None:
                        print(f"    [!] exercice indetermine, ignore : {chemin}::{membre}")
                        continue
                    sous = None
                    if code_form == "AS480":
                        sous = detecter_sous_formulaire(membre) or detecter_sous_formulaire(chemin.name)
                    ext_membre = Path(membre).suffix.lower()
                    rang_type = 2 if ext_membre in (".csv", ".txt") else 4
                    candidat = SourceCandidate(
                        label=f"{chemin.relative_to(racine)}::{membre}",
                        priorite=(base_prio, rang_type),
                        loader=(lambda p=chemin, m=membre: lire_membre_zip(p, m)),
                    )
                    _enregistrer(index, (an_debut, sous), candidat)

    return index


# --------------------------------------------------------------------------- #
# Traitement d'une source annuelle -> table canonique
# --------------------------------------------------------------------------- #

def traiter_table(
    df: pd.DataFrame,
    code_form: str,
    exercice: str,
    an_debut: int,
    sous_formulaire: Optional[str],
    source_label: str,
) -> tuple[pd.DataFrame, list]:
    """Transforme une table brute (un exercice) en table canonique.

    Retourne (table_canonique, plc_rejetes) où plc_rejetes est la liste des
    codes PLC distincts présents mais non reconnus par le parseur — à
    surveiller : toute valeur ici signale un motif de code non couvert.
    """
    # 1. Renommer les colonnes vers le schéma canonique.
    renommage = {}
    for col in df.columns:
        cle = normaliser_entete(col)
        if cle in ALIAS_COLONNES and ALIAS_COLONNES[cle] not in renommage.values():
            renommage[col] = ALIAS_COLONNES[cle]
    df = df.rename(columns=renommage)
    df = df.loc[:, ~df.columns.duplicated()]

    # 2. S'assurer que toutes les colonnes attendues existent.
    for c in COLONNES_REQUISES_BRUT:
        if c not in df.columns:
            df[c] = pd.NA

    # 3. Reparse du PLC (source de vérité) avec repli sur les colonnes déjà
    #    présentes (P/L/C ou Page/Ligne/Colonne) si le PLC est absent/illisible.
    parsed = df["plc"].map(parser_plc)
    p_page = parsed.map(lambda t: t[0])
    p_sous = parsed.map(lambda t: t[1])
    p_ligne = parsed.map(lambda t: t[2])
    p_col = parsed.map(lambda t: t[3])

    fallback_page = df["page"].map(normaliser_page)
    df["page"] = p_page.where(p_page.notna(), fallback_page).astype("string")
    df["souspage"] = vers_int(p_sous.where(p_sous.notna(), df["souspage"]))
    df["ligne"] = vers_int(p_ligne.where(p_ligne.notna(), df["ligne"]))
    df["colonne"] = vers_int(p_col.where(p_col.notna(), df["colonne"]))

    # PLC renseigné mais non reconnu (ni par le regex, ni via un repli) : à corriger.
    plc_rejetes = sorted(
        df.loc[df["plc"].notna() & df["page"].isna(), "plc"].dropna().unique().tolist()
    )

    # 4. Nettoyage des champs texte / numériques.
    df["rapport"] = nettoyer_texte(df["rapport"])
    vide = df["rapport"].isna() | (df["rapport"].str.len() == 0)
    df.loc[vide, "rapport"] = code_form
    df["rss"] = nettoyer_texte(df["rss"])
    df["etablissement_id"] = nettoyer_texte(df["etablissement_id"])
    df["etablissement_nom"] = nettoyer_texte(df["etablissement_nom"])
    df["plc"] = nettoyer_texte(df["plc"])
    df["valeur_saisie"] = vers_num(df["valeur_saisie"])
    df["chiffre"] = vers_num(df["chiffre"])

    # 5. Colonnes dérivées.
    df["exercice"] = exercice
    df["exercice_debut"] = an_debut
    df["source_feuille"] = source_label
    df["code_cellule"] = (
        "P" + df["page"].astype("string")
        + "L" + df["ligne"].astype("string").str.zfill(2)
        + "C" + df["colonne"].astype("string").str.zfill(2)
    )
    if code_form == "AS480":
        df["sous_formulaire"] = sous_formulaire

    # 6. Ne garder que les lignes du bon formulaire (si plusieurs codes de
    #    rapport se trouvent mélangés dans la même source) et aux coordonnées valides.
    rapports_distincts = df["rapport"].str.upper().dropna().unique()
    if len(rapports_distincts) > 1:
        df = df[df["rapport"].str.upper().str.startswith(code_form)]
    df = df[df["page"].notna() & df["ligne"].notna() & df["colonne"].notna()]

    colonnes = COLONNES_FINALES + (["sous_formulaire"] if code_form == "AS480" else [])
    return df[colonnes], plc_rejetes


# --------------------------------------------------------------------------- #
# Orchestration par formulaire (mode "scan Archives/00_brut")
# --------------------------------------------------------------------------- #

def traiter_formulaire(code_form: str, racine: Path = RACINE) -> Optional[tuple]:
    """Découvre, lit et harmonise toutes les sources annuelles d'un formulaire."""
    candidats = lister_sources(code_form, racine)
    if not candidats:
        print(f"  Aucune source trouvee pour {code_form}.")
        return None

    morceaux, lignes_rapport = [], []
    for (an_debut, sous), candidat in sorted(candidats.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        exercice = f"{an_debut}-{an_debut + 1}"
        etiquette_sous = f" [{sous}]" if sous else ""
        try:
            brut = candidat.loader()
        except Exception as e:
            print(f"  {exercice}{etiquette_sous}: ERREUR lecture ({candidat.label}) : {e}")
            lignes_rapport.append({
                "exercice": exercice, "sous_formulaire": sous or "", "source": candidat.label,
                "lignes_brutes": 0, "lignes_retenues": 0, "lignes_ecartees": 0,
                "etablissements": 0, "pages": 0, "chiffre_null": 0,
                "motif": f"erreur de lecture : {e}",
            })
            continue

        propre, plc_rejetes = traiter_table(brut, code_form, exercice, an_debut, sous, candidat.label)
        lignes_brutes, lignes_retenues = len(brut), len(propre)

        if lignes_retenues == 0 and lignes_brutes > 0:
            motif = "format non reconnu (colonnes PLC/Page/Ligne/Colonne absentes ou non exploitables)"
        elif plc_rejetes:
            motif = f"{len(plc_rejetes)} code(s) PLC non reconnu(s)"
        else:
            motif = "ok"

        morceaux.append(propre)
        lignes_rapport.append({
            "exercice": exercice, "sous_formulaire": sous or "", "source": candidat.label,
            "lignes_brutes": lignes_brutes, "lignes_retenues": lignes_retenues,
            "lignes_ecartees": lignes_brutes - lignes_retenues,
            "etablissements": int(propre["etablissement_id"].nunique()) if lignes_retenues else 0,
            "pages": int(propre["page"].nunique()) if lignes_retenues else 0,
            "chiffre_null": int(propre["chiffre"].isna().sum()) if lignes_retenues else 0,
            "motif": motif,
        })
        print(f"  {exercice}{etiquette_sous}: {lignes_brutes:>7,} lignes brutes -> {lignes_retenues:>7,} retenues   ({candidat.label})")
        if plc_rejetes:
            print(f"      PLC rejetes ({len(plc_rejetes)}) : {plc_rejetes[:10]}")

    if not morceaux:
        return None

    canon = pd.concat(morceaux, ignore_index=True)
    rapport = pd.DataFrame(lignes_rapport)
    return canon, rapport


def exporter(code_form: str, canon: pd.DataFrame, rapport: pd.DataFrame, racine: Path = RACINE) -> Path:
    outdir = racine / "20_canonique" / code_form
    outdir.mkdir(parents=True, exist_ok=True)
    prefixe = code_form.lower()

    csv_path = outdir / f"{prefixe}_harmonise.csv"
    canon.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"  CSV ecrit : {csv_path}  ({len(canon):,} lignes)")

    try:
        pq_path = outdir / f"{prefixe}_harmonise.parquet"
        canon.to_parquet(pq_path, index=False)
        print(f"  Parquet ecrit : {pq_path}")
    except Exception as e:  # pyarrow absent : on continue sans bloquer
        print(f"  (Parquet ignore : {e})")

    rap_path = outdir / "rapport_qualite.csv"
    rapport.to_csv(rap_path, index=False, encoding="utf-8-sig")
    print(f"  Rapport qualite : {rap_path}")
    return outdir


# --------------------------------------------------------------------------- #
# Programme principal
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Harmonise les formulaires AS478/AS480/AS481/AS484(/AS485) "
                    "depuis Archives/ et 00_brut/ en table canonique."
    )
    ap.add_argument("--formulaire", choices=FORMULAIRES_CONNUS, default=None,
                     help="Formulaire a traiter. Par defaut : AS478, AS480, AS481, AS484.")
    ap.add_argument("--root", default=str(RACINE), help="Racine du depot.")
    ap.add_argument("--force-as485", action="store_true",
                     help="Autorise --formulaire AS485 en mode scan Archives/00_brut "
                          "(ecrit dans 20_canonique/AS485_scan_archives ; ne touche pas "
                          "a la sortie de reference produite par harmoniser_as485.py).")
    args = ap.parse_args()

    racine = Path(args.root)
    formulaires = [args.formulaire] if args.formulaire else ["AS478", "AS480", "AS481", "AS484"]

    if "AS485" in formulaires and not args.force_as485:
        print(
            "AS485 dispose d'un classeur consolide (Demographic Data/Stats.xlsx) qui "
            "couvre plus d'exercices que Archives/00_brut : utilisez harmoniser_as485.py "
            "pour la sortie de reference, ou relancez avec --force-as485 pour une "
            "validation croisee (ecrite a part, sans ecraser la sortie de reference).",
            file=sys.stderr,
        )
        return 1

    recap = []
    for code in formulaires:
        print(f"\n=== {code} ===")
        resultat = traiter_formulaire(code, racine)
        if resultat is None:
            continue
        canon, rapport = resultat
        dossier_sortie = "AS485_scan_archives" if code == "AS485" else code
        outdir = racine / "20_canonique" / dossier_sortie
        outdir.mkdir(parents=True, exist_ok=True)
        prefixe = "as485" if code == "AS485" else code.lower()
        canon.to_csv(outdir / f"{prefixe}_harmonise.csv", index=False, encoding="utf-8-sig")
        try:
            canon.to_parquet(outdir / f"{prefixe}_harmonise.parquet", index=False)
        except Exception as e:
            print(f"  (Parquet ignore : {e})")
        rapport.to_csv(outdir / "rapport_qualite.csv", index=False, encoding="utf-8-sig")
        print(f"  -> {outdir}  ({len(canon):,} lignes, {canon['exercice'].nunique()} exercices)")
        recap.append((code, canon, rapport))

    if not recap:
        print("\nAucun formulaire traite.", file=sys.stderr)
        return 1

    print("\n--- Recapitulatif (formulaire x exercice x lignes) ---")
    for code, canon, rapport in recap:
        print(f"\n{code} : {len(canon):,} lignes canoniques au total, "
              f"{canon['exercice'].nunique()} exercices "
              f"({canon['exercice_debut'].min()} -> {canon['exercice_debut'].max()})")
        cols = ["exercice", "sous_formulaire", "lignes_brutes", "lignes_retenues", "lignes_ecartees", "motif"]
        cols = [c for c in cols if c in rapport.columns]
        print(rapport[cols].to_string(index=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
