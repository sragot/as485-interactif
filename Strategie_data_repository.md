# Stratégie — Data repository des budgets de la santé (SQDI)

*Document de décision — juillet 2026*
*Cible : diffusion open data publique · Maintenance visée : no-code / faible*

---

## 1. État des lieux

Le dossier contient ~500 Mo de données publiques du MSSS, accumulées depuis 2010. On y trouve six familles de contenu :

| Famille | Description | Format dominant | Volumétrie |
|---|---|---|---|
| **Formulaires AS** (AS478, AS480, AS481, AS484, AS485) | Rapports financiers et statistiques annuels des établissements du réseau. L'**AS485** = statistiques usagers (dont DI-TSA). | CSV / XLSX / ZIP | AS485 seul ≈ **422 000 lignes** sur 14 exercices ; ~190 fichiers au total dans Archives |
| **Dépenses par activité** | Dépenses par programme et centre d'activités | XLSX (1 fichier/an, 2013→2024) | ~11 fichiers + PDF de référence |
| **Dépenses par région** | Historique régional | XLSX | Quelques fichiers |
| **SAD** (soutien à domicile) | Dépenses par CA / programme / région | XLSX (1-2 fichiers/an) | ~22 fichiers |
| **Contours financiers** | Cadres financiers annuels | XLSX | Par exercice |
| **Données démographiques / stats usagers** | AS485 retravaillé, programmes sociopro | CSV / XLSX / DOCX | — |
| **Documents de référence** | Périscope TSA, rapports MSSS, crédits | PDF | 161 PDF |

### Le vrai défi n'est pas l'hébergement, c'est l'harmonisation

Trois problèmes structurels rendent ces données difficiles à requêter en l'état :

1. **Dérive de schéma dans le temps.** Les fichiers AS485 anciens (2010-11) utilisent le séparateur `;` et les colonnes `PeriodeFinanciere, CorrespEtabInstal, NomAbreg, Classe, Groupe, P, L, C`. Les récents (2023-24) utilisent `,` et `DateDebut/FinAnneeFinanciere, NoEtablissement, NomEtablissement, Page, SousPage, Ligne, Colonne, NoInstallation`. Même donnée, colonnes différentes selon l'année.
2. **Encodage ISO-8859-1** (Latin-1), pas UTF-8 → accents cassés (« CISSS des Îles » apparaît « CISSS des �les »). À convertir systématiquement.
3. **Format « long » codé.** Une ligne = une cellule de rapport repérée par des coordonnées `Page / Ligne / Colonne`. Sans **dictionnaire de codes** (que signifie P09-L01C01 ?), la donnée est illisible pour le public. C'est la pièce maîtresse à construire.

**Conséquence :** quelle que soit la techno choisie (Grist, Postgres, WordPress), 70 % du travail est un pipeline d'harmonisation fait une fois. La techno ne fait que présenter le résultat.

---

## 2. Principe directeur : séparer 3 couches

Ne pas mélanger « stocker » et « publier ». Trois couches indépendantes, chacune remplaçable sans casser les autres :

```
┌─────────────────────────────────────────────────────────────┐
│  COUCHE 1 — ARCHIVE BRUTE (inchangée, immuable)             │
│  Les fichiers originaux MSSS tels quels. Preuve/traçabilité.│
│  → Reste dans OneDrive + une copie versionnée.              │
└─────────────────────────────────────────────────────────────┘
                          │ pipeline ETL (fait une fois, puis 1×/an)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  COUCHE 2 — DONNÉES CANONIQUES HARMONISÉES                  │
│  Schéma unique, UTF-8, dictionnaire de codes appliqué.     │
│  Tables « propres » prêtes à requêter. C'est le cœur.      │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  COUCHE 3 — PUBLICATION (ce que le public voit)            │
│  Tableaux filtrables, graphiques, requêtes, export CSV.    │
│  Interchangeable : Grist public / WordPress / explorateur. │
└─────────────────────────────────────────────────────────────┘
```

Le choix « Grist vs Postgres vs WordPress » ne concerne que les couches 2 et 3. Décidons-les séparément.

---

## 3. Comparaison des options

### Pour la couche 2 (stockage canonique)

| Critère | Grist | Postgres géré (Supabase / Neon) | Fichiers plats (CSV/Parquet + SQLite) |
|---|---|---|---|
| No-code à maintenir | ✅ Excellent | 🟡 Géré = pas de serveur à administrer, mais SQL requis | 🟡 Aucun serveur, mais pas d'édition visuelle |
| Volumétrie (1-2 M lignes cible) | ⚠️ Ralentit au-delà de ~100-200 k lignes/doc | ✅ Sans problème | ✅ Sans problème |
| Requêtes publiques libres | 🟡 Vues partagées, pas de SQL libre public | ✅ API auto + SQL | ✅ (via explorateur type Datasette) |
| Coût | Gratuit à ~faible | Gratuit → ~25 $/mois | ~0 $ (hébergement statique) |
| Édition manuelle des tables de référence | ✅ Idéal | ❌ | ❌ |

### Pour la couche 3 (publication publique)

| Option | Effort de mise en place | Maintenance | Adapté open data ? |
|---|---|---|---|
| **Grist — pages publiques** | Faible | Très faible (no-code) | 🟡 Bien pour tableaux filtrables, moins pour requêtes libres |
| **WordPress + plugin SQL** (ex. *wpDataTables*) | Moyen | Moyenne (vous gérez déjà WP) | ✅ Tableaux + graphiques depuis SQL, sans coder |
| **Explorateur open data** (Datasette) | Moyen (mise en place technique) | Faible une fois en place | ✅ Excellent : navigation à facettes, SQL, export |

---

## 4. Recommandation

Compte tenu de tes contraintes (**public, no-code, tu as déjà Grist ET WordPress**), la combinaison la plus robuste et la moins coûteuse à entretenir :

### Architecture recommandée

**Couche 2 — Deux tables distinctes selon leur nature :**

- **Postgres géré (Supabase, offre gratuite puis ~25 $/mois)** pour les **données de fait volumineuses** (les ~1-2 M lignes AS485 et autres formulaires). Managed = aucun serveur à administrer, ce qui respecte la contrainte no-code côté infra. Il expose automatiquement une API et permet le SQL.
- **Grist** pour les **tables de référence / dictionnaires** : le dictionnaire de codes Page/Ligne/Colonne, la liste des établissements, les régions (RSS), les libellés de programmes. Ce sont de petites tables (centaines à milliers de lignes) qui doivent être **éditées à la main facilement** — c'est exactement le point fort de Grist, et ça reste no-code.

**Couche 3 — publication :**

- **Court terme (le plus rapide à livrer) : Grist en pages publiques.** Tu publies des vues pré-agrégées (par année / région / programme) avec filtres. Zéro code, partage public en un clic. Idéal pour lancer vite.
- **Cible (ton idée initiale) : WordPress + wpDataTables**, connecté en lecture seule à Postgres. wpDataTables génère tableaux triables et graphiques à partir de requêtes SQL, sans écrire de PHP. Tu réutilises ton WordPress existant → maintenance marginale faible.

**Insight important :** le public n'a pas besoin des ~2 M cellules brutes. Il veut des **agrégats** (dépenses par région et par an, nombre d'usagers DI-TSA par établissement, etc.). En publiant des **tables agrégées** plutôt que le format long brut, le volume tombe à quelques milliers de lignes — et **Grist seul pourrait alors suffire**, sans Postgres, tant que tu ne publies que des agrégats. Garde Postgres uniquement si tu veux exposer la donnée cellule par cellule.

### Deux scénarios concrets

| | Scénario A — « Grist d'abord » (le plus simple) | Scénario B — « Postgres + WordPress » (le plus puissant) |
|---|---|---|
| Stockage | Grist (agrégats seulement) | Supabase Postgres (données complètes) + Grist (référentiels) |
| Publication | Pages Grist publiques | WordPress + wpDataTables |
| Requête SQL libre par le public | Non | Oui (via API/vues) |
| Effort initial | Faible | Moyen |
| Maintenance | Très faible | Faible (WP déjà en place) |
| Recommandé si… | Tu veux publier vite, agrégats suffisent | Tu veux de la donnée granulaire et des requêtes ouvertes |

**Ma recommandation : commencer par le Scénario A** (Grist, agrégats), le mettre en ligne, puis **évoluer vers B** si le besoin de granularité/SQL public se confirme. Les deux partagent exactement le même pipeline d'harmonisation (couche 2), donc rien n'est perdu.

---

## 5. Le pipeline d'harmonisation (couche 2) — spécification

C'est le livrable technique central. Un script (Python) exécuté **une fois** pour le rattrapage historique, puis **une fois par an** à la sortie des nouveaux fichiers MSSS. Étapes :

1. **Ingestion** — lire tous les CSV/XLSX, détecter automatiquement séparateur (`;` vs `,`) et encodage.
2. **Ré-encodage** — tout convertir en UTF-8 (corrige les accents).
3. **Mapping de colonnes** — table de correspondance ancien schéma ↔ nouveau schéma, pour aboutir à **un schéma unique** par formulaire. Exemple pour AS485 :

   | Colonne canonique | Source ancienne (2010-11) | Source récente (2023-24) |
   |---|---|---|
   | `exercice` | PeriodeFinanciere | DateDebutAnneeFinanciere |
   | `rss` (région) | RSS | RSS |
   | `etablissement_id` | CorrespEtabInstal | NoEtablissement |
   | `etablissement_nom` | NomAbreg | NomEtablissement |
   | `page` / `ligne` / `colonne` | P / L / C | Page / Ligne / Colonne |
   | `valeur` | Chiffre | Chiffre |

4. **Jointure au dictionnaire de codes** — traduire `page/ligne/colonne` en libellés lisibles (« Nb d'usagers desservis — DI adultes »). *À construire à partir des gabarits de formulaires MSSS ; c'est le principal travail manuel.*
5. **Validation** — contrôles de cohérence (totaux, valeurs nulles, exercices manquants).
6. **Chargement** — écrire dans Postgres (Scénario B) ou exporter des CSV agrégés prêts pour Grist (Scénario A).

Sortie : un jeu de tables propres + un journal de qualité. Réexécutable chaque année en changeant un paramètre d'exercice.

---

## 6. Plan par phases

| Phase | Contenu | Sortie |
|---|---|---|
| **0 — Cadrage** (1 sem.) | Choisir Scénario A ou B ; fixer les agrégats publics prioritaires (quelles vues le public veut) | Liste des tableaux cibles |
| **1 — Dictionnaire de codes** (le gros morceau) | Décoder Page/Ligne/Colonne des formulaires AS à partir des gabarits MSSS | Table de référence (dans Grist) |
| **2 — Pipeline ETL** | Script d'harmonisation historique 2010→2024, toutes familles | Tables canoniques UTF-8 |
| **3 — Mise en ligne v1** | Publier les agrégats en pages Grist publiques | Site consultable |
| **4 — Évolution (optionnel)** | Postgres + WordPress/wpDataTables pour granularité et SQL public | Portail complet |
| **5 — Automatisation annuelle** | Procédure de mise à jour à la sortie des données MSSS | Runbook 1×/an |

---

## 7. Coûts indicatifs

| Poste | Scénario A (Grist) | Scénario B (Postgres + WP) |
|---|---|---|
| Stockage / DB | Grist gratuit → ~ selon plan équipe | Supabase gratuit (500 Mo) → ~25 $/mois (Pro, 8 Go) |
| Publication | Inclus (pages Grist) | WordPress existant + wpDataTables (~99 $/an licence) |
| Hébergement | — | WordPress déjà payé |
| **Total récurrent** | **≈ 0 $** | **≈ 25-35 $/mois** |

Le coût réel est le **temps de construction du dictionnaire de codes et du pipeline**, pas l'infrastructure.

---

## 8. Points de vigilance

- **Dictionnaire de codes = chemin critique.** Sans lui, la donnée reste illisible. À sécuriser en priorité (gabarits MSSS, éventuellement documentation officielle des formulaires AS).
- **Licence / mentions.** Confirmer les conditions de rediffusion des données MSSS (généralement licence ouverte du gouvernement du Québec) et créditer la source.
- **Archive immuable.** Ne jamais écraser les fichiers bruts ; le pipeline lit, il n'écrit jamais dans l'archive.
- **Grist et la volumétrie.** Si tu tiens à publier la donnée cellule par cellule (non agrégée), passe directement au Scénario B — Grist n'est pas fait pour des millions de lignes.
- **Reproductibilité annuelle.** Documenter le pipeline pour qu'une mise à jour annuelle prenne des heures, pas des semaines.

---

## 9. Prochaine étape suggérée

Décider entre Scénario A et B, puis lancer la **Phase 1 (dictionnaire de codes)** sur l'AS485, qui sert de modèle pour les autres formulaires. Je peux enchaîner avec un **prototype d'ETL** sur l'AS485 (harmonisation des 14 exercices + export d'un tableau agrégé) pour valider l'approche sur des données réelles.
