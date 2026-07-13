# Prompts Claude Code — Phase 2 (harmonisation des formulaires AS)

Un prompt = une tâche = un chat Claude Code. Chaque tâche ne modifie que **ses propres
fichiers** (`10_scripts/harmoniser_asXXX.py` + `20_canonique/ASXXX/`), donc **aucun conflit
git** : les 4 peuvent tourner **en parallèle**, dans n'importe quel ordre.

| Fichier | Formulaire | Note |
|---|---|---|
| `AS478.md` | AS478 | — |
| `AS480.md` | AS480 | ⚠️ sous-formulaires A (Autochtones) / G → colonne `sous_formulaire` |
| `AS481.md` | AS481 | — |
| `AS484.md` | AS484 | — |

## Mode d'emploi
1. Ouvrir le dépôt `as485-interactif` dans Claude Code.
2. Coller le bloc du fichier voulu.
3. Après le run, **committer via GitHub Desktop** (les scripts ne committent jamais eux-mêmes).

Tous s'appuient sur `10_scripts/harmoniser_as485.py`, qui encode déjà les pièges connus :
deux schémas (ancien `;`/ISO-8859-1 · récent `,`), conversion UTF-8, et parseur PLC gérant
les pages à suffixe lettre (`P04T`, `P05A`).

Étape suivante (après les 4) : consolider en un module unique + bâtir le dictionnaire de codes
(canevas = pages des formulaires MSSS). Voir `../../PLAN_mise_en_ligne.md`.
