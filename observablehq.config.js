export default {
  title: "AS485 DI-TSA — Québec",
  pages: [
    { name: "Accueil", path: "/" },
    {
      name: "Formulaires AS485",
      pages: [
        { name: "P01 — Places autorisées", path: "/pages/p01" },
        { name: "P02 — Jours-présence / taux d'occupation", path: "/pages/p02" },
        { name: "P05-0 — Sommaire mouvement internat DITSA", path: "/pages/p05" },
        { name: "P05-1 — Mouvement internat DI", path: "/pages/p05-1" },
        { name: "P05-2 — Mouvement internat TSA", path: "/pages/p05-2" },
        { name: "P09 — Clientèle desservie (externe)", path: "/pages/p09" },
        { name: "P10 — Lieu de résidence", path: "/pages/p10" },
        { name: "P11 — Ressources résidentielles (RRAC)", path: "/pages/p11" },
        { name: "P12 — Intégration communautaire", path: "/pages/p12" },
        { name: "P13-0 — Sommaire emploi et occupation DITSA", path: "/pages/p13" },
        { name: "P13-1 — Emploi et occupation DI", path: "/pages/p13-1" },
        { name: "P13-2 — Emploi et occupation TSA", path: "/pages/p13-2" },
        { name: "P14 — Provenance régionale (travail)", path: "/pages/p14" },
        { name: "P15 — Provenance régionale (réadaptation)", path: "/pages/p15" },
        { name: "P16 — Demandes de services", path: "/pages/p16" },
        { name: "P17 — Attente premier service", path: "/pages/p17" },
        { name: "P18 — Attente services DI", path: "/pages/p18" },
        { name: "P19 — Attente services TSA", path: "/pages/p19" },
        { name: "P23 — Répartition par déficience", path: "/pages/p23" },
      ]
    },
    { name: "Évolution historique", path: "/pages/historique" },
    { name: "À propos", path: "/pages/apropos" },
  ],
  footer: "Données : MSSS Québec — Rapport AS485 DI-TSA",
};
