Contexte : dépôt de données open data des formulaires financiers/statistiques du MSSS.
Le script 10_scripts/harmoniser_as485.py harmonise déjà l'AS485 (format long codé
Page/Ligne/Colonne). Objectif de cette tâche : GÉNÉRALISER ce script pour traiter aussi
les formulaires AS478, AS480, AS481 et AS484, sur le même modèle.

Pièges déjà identifiés sur l'AS485 (à gérer d'emblée, ne pas les redécouvrir) :
1. DEUX schémas selon l'année :
   - ancien (≤ 2017-18) : séparateur ";", encodage ISO-8859-1, colonnes
     Rapport, PeriodeFinanciere, RSS, CorrespEtabInstal, NomAbreg, Classe, Groupe, PLC, LC, P, L, C, ValeurSaisie, Chiffre
   - récent (≥ 2018-19) : séparateur ",", colonnes
     Rapport, DateDebutAnneeFinanciere, DateFinAnneeFinanciere, RSS, NoEtablissement,
     NomEtablissement, PLC, LC, Page, SousPage, Ligne, Colonne, ValeurSaisie, Chiffre
2. Encodage ISO-8859-1 → tout convertir en UTF-8 (sinon accents cassés type "des Îles").
3. Code PLC : "P09-0L01C01", "P09L01C01", et surtout les pages à SUFFIXE LETTRE
   "P04TL09C06", "P05AL01C01" (variantes A/B/T d'une page). Le regex doit accepter
   P(\d+[A-Za-z]?)(?:-(\d+))?L(\d+)C(\d+) et la page reste du TEXTE (ex. "04T").
4. AS480 a des sous-formulaires : AS480A (Autochtones) et AS480G. Les traiter comme
   des jeux distincts (colonne "sous_formulaire") plutôt que de les mélanger.

Données d'entrée : les BD annuelles sont dans Archives/<ASxxx>/*.csv ET décompressées
dans 00_brut/<ASxxx>/<dossier>/ (fichiers .csv/.txt). Inspecte d'abord 2-3 fichiers
d'années différentes de CHAQUE formulaire pour confirmer son schéma réel (ils peuvent
différer légèrement de l'AS485) et étends la table d'alias de colonnes en conséquence.

Travail :
- Refactore harmoniser_as485.py en un module réutilisable (ex. harmoniser_as.py) qui
  prend le n° de formulaire en paramètre et lit CSV (les deux séparateurs/encodages) et
  xlsx. Garde harmoniser_as485.py fonctionnel (ou fais-en un appel du module générique).
- Produis pour chaque formulaire : 20_canonique/<ASxxx>/<asxxx>_harmonise.parquet,
  .csv (UTF-8-BOM) et rapport_qualite.csv, avec les mêmes colonnes canoniques que l'AS485
  (exercice, exercice_debut, rapport, rss, etablissement_id, etablissement_nom, page,
  souspage, ligne, colonne, plc, valeur_saisie, chiffre, code_cellule, source_feuille)
  + une colonne sous_formulaire pour l'AS480.

Vérification (obligatoire) : pour chaque formulaire et chaque exercice, compare
lignes_brutes vs lignes_retenues. Toute perte de lignes = un motif de PLC non reconnu :
liste les PLC rejetés distincts et corrige le parseur jusqu'à perte ≈ 0, comme on l'a
fait pour l'AS485. Affiche un tableau récap final (formulaire × exercice × lignes).

Ne fais AUCUN commit git : je committe moi-même via GitHub Desktop.