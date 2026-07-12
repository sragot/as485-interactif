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
- [ ] Phase 2 — ETL formulaires AS478/480/481/484
- [ ] Phase 3 — ETL dépenses / SAD / contours
- [ ] Phase 4 — Dictionnaire de codes (canevas = pages des formulaires MSSS)
- [ ] Phase 5 — Base SQLite
- [ ] Phase 6 — Publication open data (GitHub public)
- [ ] Phase 7 — Visualisation
- [ ] Phase 8 — Mise à jour annuelle

Voir `PLAN_mise_en_ligne.md` pour le détail des phases.

## Reproduire

```bash
# Inventaire des sources
python 10_scripts/scan_catalogue.py --root . --out 00_catalogue/catalogue_sources.csv

# Harmoniser l'AS485 (exemple)
python 10_scripts/harmoniser_as485.py \
    --input "Demographic Data/Stats.xlsx" \
    --outdir 20_canonique/AS485
```

Dépendances : `pip install pandas openpyxl pyarrow`
