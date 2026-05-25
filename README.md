# AS485 DI-TSA — Données Québec

Site de consultation publique des données du rapport statistique AS485 sur la clientèle en déficience intellectuelle (DI) et trouble du spectre de l'autisme (TSA) au Québec.

**→ [Voir le site](https://ton-org.github.io/as485-di-tsa)**

## Contenu

- **15 années** de données : 2010-2011 à 2024-2025
- **Tous les CISSS et CIUSSS** du Québec
- **6 pages de formulaire** interactives reproduisant fidèlement le rapport AS485 :
  - P09 — Clientèle desservie
  - P10 — Lieu de résidence
  - P11 — Ressources résidentielles (RRAC)
  - P13 — Emploi et occupation
  - P16-17 — Listes d'attente
  - P23 — Répartition par déficience

## Installation locale

```bash
npm install
npm run dev
```

Puis ouvrir http://localhost:3000

## Mise à jour annuelle

1. Déposer le nouveau CSV AS485 dans `docs/data/`
2. Exécuter `python scripts/update_data.py`
3. Pousser sur GitHub — le site se met à jour automatiquement

## Déploiement

Le site se déploie automatiquement sur GitHub Pages via GitHub Actions à chaque push sur `main`.

## Source des données

Rapport AS485 — MSSS Québec. Données gouvernementales ouvertes.

## Technologie

- [Observable Framework](https://observablehq.com/framework/) — générateur de sites de données
- [Observable Plot](https://observablehq.com/plot/) — visualisations
- GitHub Pages — hébergement gratuit
