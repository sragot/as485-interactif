---
title: AS485 DI-TSA — Données Québec
---

```js
const meta = await FileAttachment("data/meta.json").json();
const annees = meta.annees;
const etablissements = meta.etablissements;
```

# Données AS485 — Déficience intellectuelle et TSA

Rapport statistique de clientèle en déficience intellectuelle (DI) et trouble du spectre de l'autisme (TSA), produit annuellement par les CISSS et CIUSSS du Québec pour le MSSS.

Ce site permet d'explorer les données de **${annees[0]}** à **${annees[annees.length-1]}** pour l'ensemble des établissements du réseau de la santé et des services sociaux du Québec.

---

## Ce que contient ce site

<div class="grid grid-cols-3">
  <div class="card">
    <h2>15 années</h2>
    <p>De 2010-2011 à 2024-2025, incluant la période pré- et post-réforme (fusion des CRDI en CISSS/CIUSSS).</p>
  </div>
  <div class="card">
    <h2>${etablissements.length} établissements</h2>
    <p>Tous les CISSS, CIUSSS et anciens CRDI ayant soumis le rapport AS485 au MSSS.</p>
  </div>
  <div class="card">
    <h2>6 pages de formulaire</h2>
    <p>Clientèle, résidence, ressources résidentielles, emploi, listes d'attente, répartition par déficience.</p>
  </div>
</div>

---

## Navigation

Utilisez le menu de gauche pour accéder aux différentes **pages du formulaire AS485**, chacune reproduisant fidèlement la structure du rapport officiel du MSSS avec des filtres par établissement et par année.

La page **Évolution historique** présente des graphiques de tendances sur l'ensemble de la période.

---

## Source des données

Les données proviennent des fichiers AS485 transmis au MSSS par les établissements du réseau. Elles sont rendues disponibles ici à des fins de consultation publique et de recherche.

- Rapport : **AS485** — Rapport statistique de clientèle en déficience intellectuelle et TSA
- Producteur : **Ministère de la Santé et des Services sociaux (MSSS)**, Québec
- Période couverte : **2010-2011 à 2024-2025**
- Mise à jour : annuelle

<style>
.card { background: var(--theme-background-alt); border-radius: 8px; padding: 1.5rem; }
.card h2 { font-size: 1.5rem; margin-bottom: 0.5rem; }
.grid-cols-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin: 1.5rem 0; }
</style>
