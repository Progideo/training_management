# J15 — Implantation finale des addons

Suite du cadrage du 3 novembre ; suivi dans
[eLearning #19](https://github.com/Progideo/training_management_elearning/issues/19).

Le dépôt TM porte sept addons : `training_catalog`, `training_interactive`,
`training_mock_exam`, `training_management`, `training_management_sale`,
`training_management_survey` et `training_management_interactive`.
Les trois addons autonomes restent dans le dépôt eLearning. L’option fiscale
indépendante ne fait pas partie de ces dix addons.

L’adaptateur `training_management_interactive` remplace l’ancien
`training_management_elearning`. Ses modèles, tables, routes privées, tentatives,
usages et décisions restent identiques. Le menu Website éditable appartient
à `training_catalog` ; l’ancien addon `training_management_website` est retiré.
Aucun programme, support, résultat ou fichier n’est importé ou recopié.

## Mise à jour technique

Sur une installation existante, ne pas désinstaller les anciens addons.
Une désinstallation détruirait leurs métadonnées et leurs références.

1. Arrêter les services HTTP, workers et cron. Sauvegarder ensemble base et filestore,
   et conserver les sources et configurations permettant le retour arrière.
2. Avec les **anciennes sources et l’ancien registre**, exécuter
   `tools/relocate_modules.py` dans le shell administrateur Odoo. Vérifier le marqueur
   de réussite, puis valider explicitement la transaction. Le script ne valide
   jamais lui-même. Il refuse un addon cible déjà découvert ou une dépendance
   installée sur le pont Website retiré.
3. Remplacer les sources par la composition qualifiée à dix addons. Mettre à jour
   `training_catalog,training_management_interactive` avec services toujours arrêtés.
   Les autres mises à jour requises par la version livrée restent nécessaires.
4. Vérifier reprise, droits, fichiers, progression et menu avant de redémarrer.
   En cas d’échec, restaurer la sauvegarde cohérente et les anciennes sources.

Le script renomme les métadonnées du module et ses identifiants externes,
actualise les noms techniques QWeb et statiques, puis transfère le seul menu
Website sans modifier sa personnalisation. Les identités métier et octets restent
inchangés. Une seconde exécution est sans effet. Le script doit être répété sur
une restauration avant toute intervention réelle ; ce déplacement technique
n’est pas une reprise métier Odoo 19.

## Recette courte

1. Installer l’adaptateur seul avec ses dépendances, sans cours autonomes.
2. Sur la génération précédente, conserver une tentative réussie, son état de reprise,
   ses événements et fichiers, ainsi qu’un menu personnalisé.
3. Effectuer le déplacement, deux mises à jour et une seconde exécution du script.
   Comparer les lignes métier, empreintes binaires, identités et menu.
4. En coexistence, vérifier que le même paquet alimente des tentatives et acquis
   distincts TM et autonomes ; les liens directs conservent leur autorisation.

La qualification reproductible du déplacement se trouve dans
`ci/validate-module-relocation.py` du dépôt eLearning, avec les deux générations
précédentes épinglées. Les résultats exécutés restent dans les PR.
