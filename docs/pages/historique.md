---
title: Évolution historique
---

```js
const meta = await FileAttachment("../data/meta.json").json();
const rawP09 = await FileAttachment("../data/p09.csv").csv({typed: true});
const rawP17 = await FileAttachment("../data/p17.csv").csv({typed: true});
```

# Évolution historique — 2010 à 2025

```js
const etabSelect = view(Inputs.select(
  ["Tout le Québec", ...meta.etablissements.filter(e => e && e.trim())],
  {label: "CISSS / CIUSSS / CRDI", value: "Tout le Québec", width: 400}
));
```

```js
function agg(raw, annee, etab) {
  let d = raw.filter(r => r.Annee === annee);
  if (etab !== "Tout le Québec") d = d.filter(r => r.NomEtablissement === etab);
  const out = {};
  for (const r of d) {
    const key = `${r.Ligne}-${r.Colonne}`;
    out[key] = (out[key] || 0) + (r.Chiffre || 0);
  }
  return out;
}
function v(data, l, c) { return Math.round(data[`${l}-${c}`] || 0); }

// Build full time series
const series = meta.annees.map(annee => {
  const d09 = agg(rawP09, annee, etabSelect);
  const d17 = agg(rawP17, annee, etabSelect);
  return {
    annee,
    clientsJeunes: v(d09, 1, 9),
    clientsAdultes: v(d09, 11, 9),
    clientsTotal: v(d09, 1, 9) + v(d09, 11, 9),
    heuresTotal: v(d09, 26, 9),
    attenteDI: v(d17, 1, 9),
    attenteTSA: v(d17, 2, 9),
    attenteTotal: v(d17, 3, 9),
  };
}).filter(d => d.clientsTotal > 0 || d.attenteTotal > 0);
```

---

## Clientèle desservie — évolution totale

```js
Plot.plot({
  title: `Usagers desservis — ${etabSelect}`,
  x: {label: "Année", tickRotate: -30},
  y: {label: "Usagers", grid: true},
  color: {legend: true},
  marks: [
    Plot.areaY(series, {x: "annee", y: "clientsJeunes", fill: "#1D9E75", fillOpacity: 0.4}),
    Plot.areaY(series, {x: "annee", y2: "clientsJeunes", y: "clientsTotal", fill: "#534AB7", fillOpacity: 0.4}),
    Plot.line(series, {x: "annee", y: "clientsTotal", stroke: "#534AB7", strokeWidth: 2, marker: "circle"}),
    Plot.line(series, {x: "annee", y: "clientsJeunes", stroke: "#1D9E75", strokeWidth: 2, marker: "circle", strokeDasharray: "4,3"}),
    Plot.ruleY([0]),
  ],
  width: 700,
  height: 300,
})
```

*Vert plein : 0-17 ans | Violet : 18 ans et plus*

---

## Heures de service — évolution

```js
Plot.plot({
  title: `Heures de service totales — ${etabSelect}`,
  x: {label: "Année", tickRotate: -30},
  y: {label: "Heures", grid: true},
  marks: [
    Plot.barY(series, {x: "annee", y: "heuresTotal", fill: "#378ADD"}),
    Plot.ruleY([0]),
  ],
  width: 700,
  height: 260,
})
```

---

## Liste d'attente — évolution

```js
Plot.plot({
  title: `Personnes en attente — ${etabSelect}`,
  x: {label: "Année", tickRotate: -30},
  y: {label: "Personnes en attente", grid: true},
  color: {legend: true},
  marks: [
    Plot.line(series, {x: "annee", y: "attenteDI", stroke: "#378ADD", strokeWidth: 2, marker: "circle"}),
    Plot.line(series, {x: "annee", y: "attenteTSA", stroke: "#1D9E75", strokeWidth: 2, marker: "circle"}),
    Plot.line(series, {x: "annee", y: "attenteTotal", stroke: "#D85A30", strokeWidth: 2.5, strokeDasharray: "4,3", marker: "circle"}),
    Plot.ruleY([0]),
  ],
  width: 700,
  height: 280,
})
```

*Bleu : DI | Vert : TSA | Orange pointillé : Total*

---

## Tableau récapitulatif — toutes les années

```js
view(Inputs.table(series.map(d => ({
  "Année": d.annee,
  "Clients 0-17 ans": d.clientsJeunes.toLocaleString('fr-CA'),
  "Clients 18+ ans": d.clientsAdultes.toLocaleString('fr-CA'),
  "Clients total": d.clientsTotal.toLocaleString('fr-CA'),
  "Heures de service": d.heuresTotal.toLocaleString('fr-CA'),
  "En attente — DI": d.attenteDI.toLocaleString('fr-CA'),
  "En attente — TSA": d.attenteTSA.toLocaleString('fr-CA'),
  "En attente — Total": d.attenteTotal.toLocaleString('fr-CA'),
})), {width: "100%"}));
```

<div style="font-size:12px; color: #888; margin-top: 2rem;">
Source : MSSS Québec — Rapport AS485. Données compilées de 2010-2011 à 2024-2025.
</div>
