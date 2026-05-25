export default {
  title: "AS485 DI-TSA — Québec",
  pages: [
    { name: "Accueil", path: "/" },
    {
      name: "Formulaires AS485",
      pages: [
        { name: "P09 — Clientèle desservie", path: "/pages/p09" },
        { name: "P10 — Lieu de résidence", path: "/pages/p10" },
        { name: "P11 — Ressources résidentielles", path: "/pages/p11" },
        { name: "P13 — Emploi et occupation", path: "/pages/p13" },
        { name: "P16-17 — Liste d'attente", path: "/pages/p16" },
        { name: "P23 — Répartition par déficience", path: "/pages/p23" },
      ]
    },
    { name: "Évolution historique", path: "/pages/historique" },
    { name: "À propos", path: "/pages/apropos" },
  ],
  footer: "Données : MSSS Québec — Rapport AS485 DI-TSA. Source : données.gouv.qc.ca",
};
