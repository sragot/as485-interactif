# Plan — Rendre les données disponibles et visualisables

*Roadmap actionnable (Claude Code ou autre) — juillet 2026*
*Contexte : diffusion open data publique · maintenance no-code · dépôt de travail local sur le Bureau (`Data Santé`)*

---

## 1. Où on en est

- ✅ **Stratégie validée** : séparer 3 couches — archive brute → données canoniques harmonisées → publication (voir `Strategie_data_repository.md`).
- ✅ **Preuve de concept AS485 faite** : script `harmoniser_as485.py` qui empile les 13 exercices de `Stats.xlsx` en une table propre (371 446 lignes, UTF-8, code PLC reparsé y compris pages à suffixe lettre). Livré dans `Data Santé\AS485_repository\`.
- 🔜 **Reste à faire** : appliquer la même logique aux **autres familles**, construire le **dictionnaire de codes**, puis **publier + visualiser**.

Ce plan découpe tout ça en phases autonomes. Chaque phase se termine par un livrable concret et un exemple de consigne à donner à Claude Code.

---

## 2. Inventaire des données à traiter

| Famille | Fichiers | Structure | Traitement |
|---|---|---|---|
| **AS485** (usagers DI-TSA) | 8 csv, 35 pdf, 5 zip + Stats.xlsx | Format long codé (P/L/C) | ✅ Fait — sert de modèle |
| **AS478** | 5 csv, 3 xlsx, 14 pdf, 10 zip | Format long codé | Réutiliser le script AS485 |
| **AS480** | 10 csv, 6 xlsx, 24 pdf, 9 zip | Format long codé | Réutiliser le script AS485 |
| **AS481** | 7 csv, 19 pdf, 5 zip | Format long codé | Réutiliser le script AS485 |
| **AS484** | 7 csv, 18 pdf, 6 zip | Format long codé | Réutiliser le script AS485 |
| **Contours financiers** | 42 xlsx | Tableaux larges | ETL « large → long » (nouveau) |
| **Dépenses par activités** | 14 xlsx, 40 pdf | Tableaux larges | ETL « large → long » |
| **Dépenses par région** | 13 xlsx | Tableaux larges | ETL « large → long » |
| **SAD** (soutien à domicile) | 23 xlsx | Tableaux larges | ETL « large → long » |
| **Stats usagers DI-TSA** | 7 csv, 4 xlsx, 2 zip | Format long codé | Réutiliser le script AS485 |
| **Documents de référence** | ~150 pdf | Documents / rapports | Cataloguer (pas d'ETL) |

**Deux moules seulement** : (A) le **format long codé** des formulaires AS — déjà résolu ; (B) les **tableaux larges** en xlsx (dépenses, contours, SAD) — à traiter avec un nouveau script générique de « dépivotage ». Les PDF et ZIP sont soit des archives à décompresser, soit des documents à référencer.

---

## 3. La cible (rappel en une image)

```
Bureau/Data Santé/  ← dépôt de travail local (git)
├── 00_brut/            copies des fichiers sources (jamais modifiées)
├── 10_scripts/         les ETL Python (AS + dépenses)
├── 20_canonique/       sorties propres : 1 Parquet + 1 CSV par jeu
├── 30_dictionnaires/   dictionnaire de codes P/L/C, référentiels
├── 40_base/            base SQLite unique (toutes les tables)
└── 50_publication/     catalogue open data + dashboard
```

Choix techno retenus (cohérents avec « public + no-code ») :
- **Stockage canonique** : fichiers **Parquet/CSV** + une **base SQLite** unique (un seul fichier, zéro serveur).
- **Diffusion open data** : un **dépôt public GitHub** (gratuit, versionné, téléchargeable) + fiches de métadonnées.
- **Visualisation** : au choix selon l'effort — **dashboard HTML autonome**, **Datasette** (exploration SQL publique), ou **Grist** (vues no-code). Décidé en Phase 7.

---

## 4. Le plan par phases

> Chaque phase est indépendante et se lance telle quelle dans Claude Code. Effort indicatif : 🟢 court · 🟡 moyen · 🔴 long.

### Phase 0 — Poser le dépôt de travail 🟢
**Objectif** : un projet local propre et versionné, à l'abri des soucis OneDrive.
- Créer l'arborescence ci-dessus dans `Data Santé`.
- `git init` + un `.gitignore` (exclure les gros bruts si besoin).
- Y déposer `harmoniser_as485.py` (dans `10_scripts/`) et les sorties AS485 (dans `20_canonique/`).

**Livrable** : dépôt git initialisé avec la structure.
**Consigne Claude Code** : *« Crée l'arborescence de projet 00_brut … 50_publication dans ce dossier, initialise git, déplace le script et les sorties AS485 aux bons endroits. »*

---

### Phase 1 — Catalogue machine-lisible des sources 🟢
**Objectif** : savoir exactement ce qu'on a (base de tout le reste).
- Scanner récursivement les dossiers sources ; produire `catalogue_sources.csv` : chemin, famille, exercice détecté, format, taille, nb lignes/feuilles.
- Décompresser les ZIP des AS anciens vers `00_brut/`.

**Livrable** : `catalogue_sources.csv`.
**Consigne** : *« Génère un inventaire CSV de tous les fichiers de données (famille, année, format, taille, nb de lignes), et décompresse les .zip des dossiers AS. »*

---

### Phase 2 — Généraliser l'ETL des formulaires AS 🟡
**Objectif** : une table canonique par formulaire (AS478, AS480, AS481, AS484), sur le modèle AS485.
- Refactorer `harmoniser_as485.py` en module réutilisable prenant le n° de formulaire en paramètre.
- Gérer les sources CSV (séparateur `;`/`,`, encodage ISO-8859-1) **et** les feuilles xlsx, comme pour AS485.
- Vérifier les schémas de chaque formulaire (les colonnes peuvent différer légèrement) et étendre la table d'alias.

**Livrable** : `20_canonique/as478.parquet`, `as480.parquet`, `as481.parquet`, `as484.parquet` + rapports qualité.
**Consigne** : *« Généralise harmoniser_as485.py pour traiter aussi AS478/480/481/484 depuis leurs CSV et zip ; sors un Parquet + un rapport qualité par formulaire, avec zéro perte de lignes. »*
**Vigilance** : valider le taux de lignes retenues par exercice (comme on l'a fait pour AS485 : toute perte = un motif de code à décoder).

---

### Phase 3 — ETL « tableaux larges » : dépenses, contours, SAD 🔴
**Objectif** : convertir les xlsx en format long comparable.
- Écrire `harmoniser_depenses.py` : pour chaque xlsx, repérer l'en-tête, dépivoter (colonnes région/programme → lignes), normaliser les libellés, ajouter l'exercice.
- Attention : ces fichiers changent de mise en page d'une année à l'autre → prévoir un mapping par variante, procéder **un dossier à la fois** (SAD, puis Dépenses activités, puis région, puis Contours).

**Livrable** : `20_canonique/sad.parquet`, `depenses_activites.parquet`, `depenses_region.parquet`, `contours.parquet`.
**Consigne** : *« Écris un ETL qui dépivote les xlsx du dossier SAD en table longue (exercice, région, programme, centre_activites, montant) ; commence par inspecter 3 fichiers d'années différentes pour repérer les variantes de mise en page. »*
**Vigilance** : c'est la phase la plus longue (mises en page hétérogènes). La traiter dossier par dossier, pas tout d'un coup.

---

### Phase 4 — Dictionnaire de codes (chemin critique) 🔴
**Objectif** : rendre la donnée lisible. Sans lui, `P09L01C03` ne veut rien dire pour le public.
- Extraire la liste des `code_cellule` distincts par formulaire (déjà possible depuis les Parquet).
- Les mettre en correspondance avec leur libellé, à partir des **gabarits officiels des formulaires AS** (MSSS) — travail semi-manuel.
- Stocker le dictionnaire dans un fichier éditable (`30_dictionnaires/codes_as.csv`) — idéalement maintenu **dans Grist** (no-code) puis exporté.

**Livrable** : `codes_as.csv` (code_cellule → libellé, unité, thème, page-titre).
**Consigne** : *« Extrais tous les code_cellule distincts de as485.parquet avec un exemple de valeur et leur fréquence, et prépare un gabarit CSV à compléter (libellé, unité, thème). »*
**Vigilance** : prioriser les pages réellement utilisées pour le plaidoyer (usagers desservis, listes d'attente, etc.) plutôt que tout décoder d'un coup.

---

### Phase 5 — Base canonique unique 🟢
**Objectif** : tout requêtable au même endroit.
- Charger tous les Parquet + le dictionnaire dans **une base SQLite** (`40_base/sqdi_sante.db`), avec des vues joignant les valeurs à leurs libellés.
- Créer quelques **vues agrégées** utiles (par exercice/région/programme) — ce sont elles qui seront publiées.

**Livrable** : `sqdi_sante.db` + un script de (re)construction.
**Consigne** : *« Charge tous les Parquet de 20_canonique et le dictionnaire dans une base SQLite, crée une vue qui joint les valeurs AS485 à leurs libellés, et 3 vues agrégées par région et par année. »*

---

### Phase 6 — Publication open data 🟡
**Objectif** : que d'autres puissent télécharger et réutiliser.
- Créer un **dépôt GitHub public** contenant : les CSV canoniques, le dictionnaire, un `README` clair, une fiche `datapackage.json` (métadonnées standard), la **licence** (confirmer la licence ouverte du gouvernement du Québec + créditer le MSSS).
- Option : publier une release datée à chaque mise à jour annuelle.

**Livrable** : dépôt public consultable et téléchargeable.
**Consigne** : *« Prépare un dépôt open data : structure les CSV, écris un README (source, méthodo, limites), génère un datapackage.json, ajoute le fichier de licence. »*
**Décision** : confirmer les conditions de rediffusion des données MSSS avant publication.

---

### Phase 7 — Visualisation 🟡
**Objectif** : rendre les chiffres parlants pour un public non technique. Choisir **une** voie :

| Voie | Ce que ça donne | Effort | Maintenance |
|---|---|---|---|
| **Dashboard HTML autonome** | Un fichier ouvrable dans le navigateur, graphiques + filtres | 🟡 | Faible |
| **Datasette** | Site d'exploration + requêtes SQL publiques + export | 🟡 | Faible |
| **Grist (vues publiques)** | Tableaux/graphes no-code, partage en 1 clic | 🟢 | Très faible |
| **WordPress + wpDataTables** | Intégré à ton site existant, graphiques depuis SQL | 🔴 | Moyenne |

**Recommandation** : commencer par un **dashboard HTML autonome** (ou Grist si tu veux du no-code pur) sur 2-3 indicateurs phares, puis étendre.
**Consigne** : *« À partir de sqdi_sante.db, génère un dashboard HTML autonome : évolution du nombre d'usagers DI-TSA par région et par année, avec filtres. »*

---

### Phase 8 — Mise à jour annuelle 🟢
**Objectif** : qu'une mise à jour prenne des heures, pas des semaines.
- Rédiger un **runbook** : où déposer les nouveaux fichiers MSSS, quelles commandes lancer, comment republier.
- Option : tâche planifiée qui te rappelle chaque année à la sortie des données.

**Livrable** : `RUNBOOK.md` + procédure testée sur un exercice.
**Consigne** : *« Rédige un runbook de mise à jour annuelle : ajouter l'exercice N, relancer les ETL, régénérer la base et le dashboard, publier une release. »*

---

## 5. Ordre suggéré et gains rapides

1. **Phases 0-1** (une session) : socle propre + inventaire. Débloque tout le reste.
2. **Phase 2** : les 4 autres formulaires AS — réutilise 90 % du code AS485. **Gain rapide.**
3. **Phase 4 (partielle)** : décoder d'abord les 20-30 codes les plus utiles → la donnée devient parlante.
4. **Phases 5 + 7** : base SQLite + un premier dashboard sur AS485/AS478. **Effet démo.**
5. **Phase 3** : dépenses/SAD/contours (le plus long) en parallèle, dossier par dossier.
6. **Phase 6 + 8** : publication publique + runbook, une fois 2-3 jeux stabilisés.

**Principe** : ne pas attendre que tout soit parfait. Publier tôt un sous-ensemble propre (AS485 + AS478 + dictionnaire partiel), puis élargir.

---

## 6. Décisions à prendre avant de lancer

- **Hébergement open data** : dépôt GitHub public (recommandé), ou portail dédié ?
- **Voie de visualisation** : dashboard HTML, Datasette, Grist, ou WordPress ? (cf. Phase 7)
- **Licence** : confirmer les conditions de rediffusion des données MSSS.
- **Périmètre initial** : quels 2-3 indicateurs publier en premier pour la démo ?

Dis-moi par quelle phase tu veux commencer — je peux enchaîner directement sur la Phase 0-1 (socle + inventaire) ou la Phase 2 (généraliser l'ETL aux autres formulaires AS).
