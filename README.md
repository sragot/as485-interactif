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
- [ ] Phase 3 — ETL dépenses / SAD / contours *(non commencé)*
- [~] Phase 4 — Dictionnaire de codes : 23 953 codes extraits ; **démo AS485 décodée** (6 pages : 09, 10, 17, 18, 19, 20) + **AS484 page 09** (usagers admis en CRDP par groupe d'âge, `epoque=depuis_2013`)
- [~] Phase 5 — Base SQLite `40_base/sqdi_sante.db` : 5 tables AS + dictionnaire + vues agrégées AS485 et AS484
- [ ] Phase 6 — Publication open data (GitHub public)
- [~] Phase 7 — Visualisation : dashboard HTML autonome (`50_publication/`), 3 onglets : AS485 desservis / AS485 attente / AS484 déficience physique
- [ ] Phase 8 — Mise à jour annuelle

Légende : `[x]` fait · `[~]` partiel (démo) · `[ ]` à faire.
La base SQLite (`40_base/*.db`, ~430 Mo) est reconstructible et n'est pas versionné