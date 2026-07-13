# Phase 4 (partielle) → 5 → 7 — Tranche verticale de démo

Contexte : dépôt `as485-interactif`. Les 5 formulaires AS sont déjà en table canonique
(`20_canonique/AS4xx/*.parquet`, format long, colonne `code_cellule` = P{page}L{ligne}C{colonne}).
Deux scripts Phase 4 existent déjà :
- `10_scripts/extraire_codes.py` → `30_dictionnaires/codes_as.csv` (25 312 codes distincts, tous formulaires)
- `10_scripts/enrichir_titres_pages.py` → remplit `page_titre` depuis les gabarits FORMULAIRE PDF du MSSS

## Décision de périmètre (déjà tranchée)
- Formulaire : **AS485** (DI-TSA, phare).
- Période : **2013-2014 à 2022-2023 uniquement**. On ignore 2010-2011 → 2012-2013 (ancienne
  génération de maquette, sens des pages différent — mapping séparé remis à plus tard).
- Indicateurs de démo : **usagers desservis** (pages 09 et 10) et **listes d'attente**
  (pages 17, 18, 19, 20).

## Point de vigilance critique
Le formulaire AS485 a changé de format **autour de 2017/2018** *à l'intérieur* de la période
retenue (réorganisation lignes/colonnes, pas ajout/retrait de page). AVANT de décoder,
vérifier pour chaque page de démo (09,10,17,18,19,20) si l'ensemble des `code_cellule`
présents est stable de 2013-2014 à 2022-2023 :
- si stable → un seul mapping couvre 2013-2023 ;
- si rupture → scinder en deux époques (ex. 2013-2017 / 2018-2023) et décoder chacune.
Ajouter au dictionnaire une colonne **`epoque`** (`2013-2017` / `2018-2023` / `stable`).

## Tâches
1. **Décoder ligne/colonne des pages de démo.** À partir des PDF `EXPLICATIONS` et `FORMULAIRE`
   du MSSS (`Archives/AS485/<annee>/AS-485-*-EXPLICATIONS.pdf` et `*-FORMULAIRE.pdf`), extraire
   le libellé de chaque ligne et de chaque colonne des pages 09,10,17,18,19,20. Remplir
   `libelle`, `unite`, `theme` dans `30_dictionnaires/codes_as.csv` pour ces codes, en gérant
   la rupture 2017/2018 via la colonne `epoque`. Prendre une année de chaque époque comme
   référence (ex. 2014-2015 et 2019-2020).
2. **Base SQLite (Phase 5).** Créer `40_base/sqdi_sante.db` : charger tous les Parquet de
   `20_canonique/` + le dictionnaire, et créer une **vue** qui joint les valeurs AS485 à leurs
   libellés (jointure sur `code_cellule` + `epoque`). Ajouter 2-3 vues agrégées pour les
   indicateurs de démo (par exercice et par région `rss`). Script de (re)construction versionné.
3. **Dashboard (Phase 7).** À partir de la base, générer un **dashboard HTML autonome**
   (`50_publication/`) sur les 2 indicateurs : évolution 2013-2023 des usagers desservis et
   des listes d'attente, par région, avec filtres. Priorité UX : explorer l'année récente ET
   comparer dans le temps.

## Vérifications de fin
- Aucune perte de lignes à la jointure valeurs↔libellés pour les pages de démo.
- Cohérence temporelle : une valeur agrégée par exercice ne doit pas faire de saut aberrant à
  la frontière 2017/2018 (sinon = code mal apparié entre époques).
- Totaux du dashboard reconciliés avec une requête SQL directe sur la base.
