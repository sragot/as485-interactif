# Plan de travail — Données santé DI-TSA (SQDI)

*Refocus juillet 2026. Remplace la roadmap initiale.*
*Contexte : diffusion open data publique · maintenance no-code · dépôt de travail local `as485-interactif` (Documents/GitHub).*

---

## 1. Décision de périmètre (juillet 2026)

On concentre l'effort de **publication et de visualisation** sur les jeux réellement
utiles au plaidoyer SQDI. Le reste des formulaires AS est conservé **en archive brute
et en table canonique**, mais **sans dictionnaire ni visualisation** (sauf ce qui est
déjà généré).

| Jeu | Rôle | Canonique | Décodé | Visualisé |
|---|---|:--:|:--:|:--:|
| **AS485** (usagers DI-TSA) | **Cible viz** | ✅ | ✅ 6 pages | ✅ 2 onglets (desservis, attente) |
| **Effectifs démographiques** (Stats.xlsx) | **Cible viz** | ✅ | ✅ Population (historical) | ✅ 1 onglet (effectifs DI-TSA) |
| **Dépenses par activités** | **Cible viz** | ✅ | — | ✅ 1 onglet (par centre d'activités) |
| **Dépenses par région** (`Dépenses par région/`) | **Cible viz** | ✅ | — | ✅ 1 onglet (par programme) |
| **SAD** (soutien à domicile) | **Cible viz** | ✅ | — | ✅ 1 onglet (par programme, dès 2016-2017) |
| **Contour financier** | **Cible viz** | ✅ | — | ✅ 1 onglet (SAD par type de service) |
| AS484 (déficience physique) | Archive | ✅ | ✅ page 09 | ✅ 1 onglet (déjà généré — conservé) |
| AS481 (dépendance) | Archive | ✅ | ✅ page 02 | ✅ 1 onglet (déjà généré — conservé) |
| AS480 (centres jeunesse) | Archive | ✅ | ✅ page 04 | ✅ 1 onglet (déjà généré — conservé) |
| AS478 (CH/CHSLD/CLSC) | **Archive brute seulement** | ✅ | ❌ abandonné | ❌ **pas de viz** |

**Pourquoi AS478 est écarté de la viz** : grosse rupture de maquette. La page phare
candidate — page 18 « Répartition des usagers par catégorie de clientèle » (qui
contient pourtant les lignes DI-TED 11-15) — est instable dans le temps : les colonnes
changent en 2012, puis refonte complète + dimension `souspage` en 2018. Décodage
possible mais coûteux et fragile ; le jeu reste disponible en canonique
(`20_canonique/AS478/`) si besoin plus tard.

---

## 2. Ce qui est déjà livré (ne pas refaire)

- **AS485** : table canonique (13+ exercices empilés), 6 pages décodées (09, 10, 17,
  18, 19, 20 — usagers desservis + listes d'attente), 2 onglets dashboard.
- **AS484 / AS481 / AS480** : une page phare décodée chacun + un onglet dashboard.
  On les **garde tels quels** (viz déjà générée), sans y ajouter d'effort.
- **Socle** : catalogue des sources, base SQLite reconstructible (`construire_base.py`
  → `exporter_dashboard_data.py` → `generer_dashboard.py`), dictionnaire de codes
  (`30_dictionnaires/codes_as.csv`), recette de commit adaptée au mont (voir mémoire
  « as485-mount-git-workarounds »).

---

## 3. Le travail restant — 6 chantiers

Deux profils : (A) **effectifs AS485 déjà en format long** — reproduire une feuille
de synthèse ; (B) **tableaux larges xlsx** (dépenses / SAD / contours) — nouvel ETL
générique de « dépivotage » (large → long).

### Chantier 1 — Effectifs démographiques dans le temps 🟡
**Source** : `Demographic Data/Stats.xlsx` (feuilles annuelles 2010-2011 → 2022-2023 +
feuilles de synthèse : `Populational data (by year)`, `Population (historical)`,
`Employment - P13`, `Waiting list - P16,17,18,19,20`, `Housing P10`, …).
**Objectif** : reproduire **la feuille d'effectifs dans le temps** en table canonique
longue + un onglet dashboard (évolution des effectifs par année, ventilée région/âge
selon la feuille retenue).
**À clarifier en ouverture** : confirmer avec Samuel **quelle feuille exacte** joue le
rôle d'« effectifs dans le temps » (plusieurs candidates).
**Note** : exercices récents `2023-2024` et `2024-2025` disponibles en CSV bruts dans
le même dossier — possibilité d'étendre AS485 par la même occasion.

### Chantier 2 — Dépenses par activités 🔴
**Source** : `Dépenses par activités/` — 11 xlsx annuels `2013-2014.xlsx` →
`2023-2024.xlsx`, feuille « Par centre d'activités » (~325 lignes). PDF associés =
définitions de centres d'activités (référence).
**Objectif** : `harmoniser_depenses.py` (dépivotage) → table longue
`(exercice, centre_activites, programme, montant, …)` + onglet dashboard.

### Chantier 3 — Dépenses par région 🟡
**Source** : `Dépenses par région/` — `historique par région.xlsx` (feuille
« Budgets en DI-TSA », déjà quasi en format synthèse), `Classeur1.xlsx`, sous-dossier
`dépenses/`.
**Objectif** : table longue `(exercice, région, montant)` + onglet dashboard
(évolution des budgets DI-TSA par région).

### Chantier 4 — SAD (soutien à domicile) 🔴
**Source** : `SAD/` — ~23 xlsx, deux familles (par programme et par région / par
centre d'activités et par région), 2013-2014 → 2023-2024 + `Depenses SAD.xlsx`
(classeur multi-feuilles récapitulatif).
**Objectif** : table longue `(exercice, région, programme|CA, montant)` + onglet
dashboard. **Vigilance** : mises en page hétérogènes d'une année à l'autre → mapping
par variante, procéder fichier par fichier.

### Chantier 5 — Contour financier 🔴
**Source** : `Archives/Contours financiers/` — un dossier par exercice 2013-2014 →
2022-2023, 4 xlsx/an (par programme et par CA, par région, SAD par CA/région, SAD par
programme/région) + `03-Contour-Financier-...2014-15.xlsx` à la racine.
**Objectif** : table longue + onglet dashboard.

### Chantier 6 — Publication + vérifications 🟡
Intégrer les nouvelles tables à `40_base/sqdi_sante.db`, régénérer le JSON et le
dashboard, contrôles de cohérence (totaux = somme des postes, ordres de grandeur
plausibles, zéro perte de lignes), commit, MAJ README.

---

## 4. Le moule « tableaux larges » (dépenses / SAD / contours)

Script générique `harmoniser_depenses.py` à écrire, réutilisé par les chantiers 2-5 :

1. **Inspecter 2-3 fichiers d'années différentes** avant de coder (repérer l'en-tête,
   les variantes de mise en page).
2. **Repérer la ligne d'en-tête** (souvent pas la première ligne du xlsx).
3. **Dépivoter** : colonnes région/programme/CA → lignes ; une colonne `montant`.
4. **Normaliser** libellés région/programme (table d'alias) + ajouter l'`exercice`
   déduit du nom de fichier.
5. **Rapport qualité** par fichier (lignes lues/retenues, montants totaux) — toute
   perte = un motif à corriger.

Sortie : `20_canonique/<jeu>/<jeu>_long.parquet` + `.csv` + `rapport_qualite.csv`.

---

## 5. Cible technique (arborescence)

```
as485-interactif/            ← dépôt git local (Documents/GitHub)
├── 00_brut/                 copies des sources (non versionné)
├── 00_catalogue/            catalogue_sources.csv
├── 10_scripts/              ETL Python (AS + dépenses) + génération dashboard
├── 20_canonique/            sorties propres : 1 Parquet + 1 CSV par jeu
├── 30_dictionnaires/        codes_as.csv (P/L/C), référentiels
├── 40_base/                 sqdi_sante.db (reconstructible, non versionné, ~430 Mo)
└── 50_publication/          dashboard HTML autonome + JSON de données
```

Pipeline dashboard : `construire_base.py` → `exporter_dashboard_data.py` →
`generer_dashboard.py`. Base construite dans `/tmp/build/` (jamais sur le mont).

---

## 6. Ordre suggéré

1. **Chantier 1 (effectifs)** — proche de l'existant AS485, gain rapide + effet démo.
2. **Chantier 3 (dépenses par région)** — le plus proche du format synthèse, sert de
   patron au moule « tableaux larges ».
3. **Chantiers 2, 4, 5** (activités, SAD, contours) — dossier par dossier, une fois le
   moule stabilisé.
4. **Chantier 6** — publication publique + runbook une fois 2-3 jeux stabilisés.

---

## 7. Décisions (mise à jour juillet 2026)

**Tranchées (phase 6) :**
- **Hébergement open data** : ✅ dépôt GitHub existant `sragot/as485-interactif` rendu
  public (préparé + commité ; toggle « public » + push à faire côté GitHub).
- **Licence** : ✅ **CC BY-NC-SA 4.0** (Attribution · Pas d'utilisation commerciale ·
  Partage dans les mêmes conditions). Fichier `LICENSE` : préambule d'attribution MSSS
  + texte intégral. (À noter : le standard des données ouvertes du Québec est CC BY 4.0 ;
  le choix NC-SA est plus restrictif, retenu par Samuel.)
- **Dashboard en ligne** : ✅ GitHub Pages depuis `/docs`. Page d'accueil propre
  (`docs/index.html`) distincte du tableau de bord (`docs/dashboard.html`). URL cible
  `https://sragot.github.io/as485-interactif/` (activation Pages à faire côté GitHub).
- **Feuille « effectifs dans le temps »** : ✅ résolue au chantier 1 (`Population (historical)`).
- **Étendre AS485 aux exercices 2023-2024 / 2024-2025** : ✅ fait. `harmoniser_as485.py`
  ingère désormais aussi les CSV bruts `AS485_BD_*.csv` (dédup par exercice). Table
  canonique AS485 = **15 exercices (2010-2011 → 2024-2025), 422 461 lignes**.
- **Outillage MAJ** : ✅ GUI `10_scripts/maj_gui.py` (Tkinter) pour régénérer sans
  ligne de commande ; runbook de maintenance dans `README.md`.

**Encore ouvertes :** aucune pour l'instant.
