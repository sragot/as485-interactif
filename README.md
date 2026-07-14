# Données budgétaires de la santé — DI-TSA (SQDI)

Dépôt de travail pour harmoniser, publier et visualiser les données financières et
statistiques du réseau de la santé (formulaires MSSS), avec un focus déficience
intellectuelle et trouble du spectre de l'autisme (DI-TSA).

## Principe : 3 couches

1. **Archive brute** — fichiers sources du MSSS, jamais modifiés (non versionnés ici).
2. **Données canoniques** — tables harmonisées, UTF-8, format long (`20_canonique/`).
3. **Publication** — catalogue open data + visualisations (`50_publication/`).

Données publiques du MSSS. Aucune restriction de rediffusion ; source à créditer (MSSS).

## Structure

| Dossier | Contenu |
|---|---|
| `00_brut/` | Copies/décompressions des sources (non versionné) |
| `00_catalogue/` | `catalogue_sources.csv` — inventaire machine-lisible |
| `10_scripts/` | Scripts ETL (`harmoniser_as485.py`, `scan_catalogue.py`, …) |
| `20_canonique/` | Tables propres : 1 Parquet + 1 CSV par jeu |
| `30_dictionnaires/` | Dictionnaire de codes P/L/C, référentiels (calqués sur les pages des formulaires MSSS) |
| `40_base/` | Base SQLite unique (reconstructible) |
| `50_publication/` | Catalogue open data + dashboards |

## État d'avancement

- [x] Phase 0 — Socle de projet + git
- [x] Phase 1 — Catalogue des sources
- [x] Phase 2 — ETL formulaires AS478/480/481/484/485 (tables canoniques + rapports qualité)
- [~] Phase 3 — ETL dépenses / SAD / contours *(SAD + contours à faire)* · **Effectifs démographiques (Chantier 1) fait** · **Dépenses par région (Chantier 3) fait** · **Dépenses par activités (Chantier 2) fait** : même moule, matrice C/A × programme → `20_canonique/depenses_activites/` (2013-2014 → 2023-2024 ; DI-TSA par centre d'activités recoupée au dollar près avec les dépenses par région) : moule générique `10_scripts/harmoniser_depenses.py` (dépivotage large→long) → `20_canonique/depenses_region/` (12 programmes × 18 RSS × 10 exercices ; somme des postes = GRAND TOTAL source ; DI-TSA recoupé au chiffre près avec « historique par région ») : table canonique longue `20_canonique/effectifs/` reproduisant la feuille « Population (historical) » de Stats.xlsx (usagers DI/TSA par âge, RSS, exercice ; 2010-2011 → 2022-2023 ; totaux validés au chiffre près contre la feuille source)
- [~] Phase 4 — Dictionnaire de codes : 23 953 codes extraits ; **démo AS485 décodée** (6 pages : 09, 10, 17, 18, 19, 20) + **AS484 page 09** (usagers admis en CRDP par groupe d'âge, `epoque=depuis_2013`) + **AS481 page 02** (usagers admis en dépendance — alcool-drogues et jeux pathologiques — par groupe d'âge, lignes 01-14, `epoque=stable`) + **AS480 page 04** (signalements retenus par problématique, LPJ art. 38/38.1, lignes 01-14, `epoque=stable`)
- [~] Phase 5 — Base SQLite `40_base/sqdi_sante.db` : 5 tables AS + tables `effectifs`, `depenses_region` et `depenses_activites` + dictionnaire + vues agrégées AS485-484-481-480, `v_effectifs_*`, `v_depenses_region_*` et `v_depenses_activites_*`
- [ ] Phase 6 — Publication open data (GitHub public)
- [~] Phase 7 — Visualisation : dashboard HTML autonome (`50_publication/`), 8 onglets : AS485 desservis / AS485 attente / AS484 déficience physique / AS481 dépendance / AS480 centres jeunesse / **effectifs DI-TSA dans le temps** / **dépenses par région** / **dépenses par centre d'activités**
- [ ] Phase 8 — Mise à jour annuelle

Légende : `[x]` fait · `[~]` partiel (démo) · `[ ]` à faire.
La base SQLite (`40_base/*.db`, ~430 Mo) est reconstructible et n'est pas versionné