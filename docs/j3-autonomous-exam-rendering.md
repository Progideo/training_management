# Rendu commun des examens et contextes autonomes

Suite de [J2](j2-shared-exam-obligations.md), dans le périmètre de [J1 #123](https://github.com/Progideo/training_management/issues/123).

`training_mock_exam` possède désormais le rendu privé, la navigation et les interactions de questions enrichies, en plus de la définition et du moteur Survey. Le chronomètre natif et les sauvegardes serveur sont conservés. Le moteur refuse tout contexte non autorisé par un adaptateur.

Les gabarits communs reçoivent les URL de sauvegarde et d’images privées de leur adaptateur. Les anciens identifiants QWeb et imports JavaScript TM restent disponibles par héritage ou redirection, y compris pour l’adaptateur eLearning historique. Les traductions du rendu sont transférées au module commun.

Le dépôt eLearning livre `training_elearning` et `training_elearning_survey` sur les cours, contenus et adhésions Community natifs. Ces deux addons ne dépendent d’aucun modèle métier TM. Leur [contrat et recette](https://github.com/Progideo/training_management_elearning/blob/feat/j3-autonomous-exam-offers/docs/J3-autonomous-exam-offers.md) décrit les accès, obligations figées et limites de cette tranche.

Le contexte autonome est `slide.channel.partner:<id>` ; TM reste `training.enrollment:<id>`. Le test optionnel de coexistence utilise un même examen et apprenant dans les deux applications : preuves, progression et droits de lecture restent séparés. Il est exécuté par la CI autonome après la phase d’installation et de conservation sans TM. Les suites TM seules signalent explicitement son absence par un test ignoré.

La société de lecture des tentatives est figée par la fabrique privée, sans recalculer ni réécrire les dates d’audit des réponses natives antérieures. Les chemins S09.3 et continuité P20 sont conservés sans assouplir leurs comparaisons de données historiques.
