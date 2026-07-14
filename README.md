# Données santé DI-TSA (Québec) — as485-interactif

Harmonisation, publication et visualisation des données financières et statistiques
publiques du réseau de la santé du Québec (formulaires MSSS), avec un focus déficience
intellectuelle et trouble du spectre de l'autisme (DI-TSA). Projet de plaidoyer SQDI.

**Tableau de bord en ligne :** https://sragot.github.io/as485-interactif/
**Couverture :** 15 exercices, 2010-2011 → 2024-2025.

---

## Ce que contient le dépôt

Trois couches, du brut au publié :

1. **Archive brute** — fichiers sources du MSSS, jamais modifiés (non versionnés).
2. **Données canoniques** — tables harmonisées, UTF-8, format long (`20_canonique/`).
3. **Publication** — catalogue, tableau de bord et page d'accueil (`50_publication/`, `docs/`).

| Dossier | Contenu |
|---|---|
| `00_catalogue/` | `catalogue_sources.csv` — inventaire machine-lisible des sources |
| `10_scripts/` | Scripts ETL + génération du dashboard + **GUI de mise à jour** |
| `20_canonique/` | Tables propres : 1 CSV + 1 Parquet par jeu |
| `30_dictionnaires/` | Dictionnaire de codes P/L/C, référentiels |
| `40_base/` | Base SQLite unique (reconstructible, non versionnée, ~450 Mo) |
| `50_publication/` | Tableau de bord HTML autonome + JSON de données |
| `docs/` | Site GitHub Pages : `index.html` (accueil) + `dashboard.html` |

---

## Mettre à jour les données (MAJ annuelle)

Chaque année, le MSSS publie de nouveaux exercices. Deux façons de régénérer.

### Option A — Interface graphique (recommandée, sans ligne de commande)

```
python 10_scripts/maj_gui.py
```

Une fenêtre s'ouvre avec des boutons pour chaque étape (1 → 5) et un bouton
**« Tout faire »**. Le journal s'affiche en direct. Cliquer sur « Tout faire »
harmonise, reconstruit la base, exporte les indicateurs, régénère le dashboard et
le publie dans `docs/`.

### Option B — Ligne de commande

```
python 10_scripts/harmoniser_as485.py       # -> 20_canonique/AS485/
python 10_scripts/construire_base.py         # -> 40_base/sqdi_sante.db
python 10_scripts/exporter_dashboard_data.py # -> 50_publication/donnees_dashboard.json
python 10_scripts/generer_dashboard.py       # -> 50_publication/dashboard_as485.html
cp 50_publication/dashboard_as485.html docs/dashboard.html
```

### Ajouter un nouvel exercice AS485

L'harmonisation AS485 lit d'abord les onglets annuels de `Demographic Data/Stats.xlsx`,
puis **ingère automatiquement** tout export brut `AS485_BD_AAAA-AAAA*.csv` déposé dans
le même dossier, dédupliqué par exercice (l'onglet Stats.xlsx reste prioritaire, jamais
de double comptage). Pour ajouter une année :

1. Déposer le CSV brut du MSSS dans `Demographic Data/` sous le nom
   `AS485_BD_AAAA-AAAA*.csv` (ex. `AS485_BD_2025-2026.csv`) **ou** ajouter un onglet
   `AAAA-AAAA` dans `Stats.xlsx`.
2. Relancer la MAJ (option A ou B).
3. Vérifier le rapport `20_canonique/AS485/rapport_qualite.csv` (lignes retenues,
   `chiffre_null`, PLC rejetés) — toute perte de lignes est un motif à corriger.

Les autres jeux (dépenses, SAD, contours, effectifs) suivent le même principe via
`harmoniser_depenses.py` et `harmoniser_effectifs.py` (voir `PLAN_mise_en_ligne.md`).

---

## Publier

Le tableau de bord est servi par **GitHub Pages** depuis `docs/`.

1. `git push origin main`
2. (une seule fois) *Settings → Pages → Source : `main` / `/docs`*.

Le site se met à jour automatiquement à chaque push touchant `docs/`.

---

## Données & licence

**Source :** ministère de la Santé et des Services sociaux du Québec (MSSS) — données
publiques. Ce dépôt n'implique aucun endossement du MSSS.

**Licence :** le travail d'harmonisation et les visualisations sont diffusés sous
[CC BY-NC-SA 4.0](LICENSE) — Attribution · Pas d'utilisation commerciale · Partage dans
les mêmes conditions. Créditer : « Données MSSS ; harmonisation et visualisation :
projet as485-interactif (SQDI), CC BY-NC-SA 4.0 ».

---

*Historique de conception et périmètre détaillé : `PLAN_mise_en_ligne.md`.*
*Contraintes techniques du dépôt local : voir la mémoire projet.*
