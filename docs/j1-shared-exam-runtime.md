# Passation commune et chronométrage serveur

La [tranche suivante](j2-shared-exam-obligations.md) raccorde les examens partagés
aux offres et fige leurs obligations par inscription TM.

Suite de [J1 #123](https://github.com/Progideo/training_management/issues/123),
après les [lecteurs et définitions](j1-shared-readers-exams.md). Le cadrage consolidé
du 3 novembre 2026, notamment D01/D02, conserve les réponses natives Survey et
une seule tentative active par personne, famille et contexte d’inscription.

## Frontière

`training_mock_exam` possède le moteur `training.mock.exam.service`, les réponses,
les marquages, le score exact, les totaux par thème et la fermeture à expiration.
Il dépend seulement du catalogue et de Survey Community. Les noms techniques
historiques `training_family_id`, `training_review_ids` et les transitions privées
sont conservés pour garder les identifiants et références des preuves existantes.

Un adaptateur autorise et verrouille son inscription/adhésion avant d’appeler la
fabrique privée. Il fournit une clé de contexte stable et ses références propres.
La clé n’est ni un jeton d’accès ni un nouveau référentiel d’inscriptions. Le moteur
ne résout aucun modèle métier depuis une chaîne reçue du navigateur.

Sans adaptateur, sauvegarde, remise et lecture des résultats refusent toute demande.
Les fabriques et transitions sont des méthodes privées, inaccessibles par RPC.
Les routes Survey génériques restent fermées pour les examens gérés. Un auteur
n’obtient aucun droit implicite sur les réponses des apprenants.

## Délai, reprise et résultats

Le serveur fixe début et échéance depuis la durée de la version publiée. Les
sauvegardes et remises contrôlent l’accès courant et verrouillent la tentative.
À l’échéance exacte, la réponse tardive n’est pas enregistrée ; la fermeture est
persistée dans la réponse normale. La fin retenue ne dépasse jamais l’échéance.
Le délai de tolérance du contrôleur Survey standard n’est pas utilisé.

Une reprise conserve version, contexte, réponses, marquages et échéance. Une
remise répétée conserve le résultat. Le cron commun ferme les tentatives expirées
sans déclencher certification, badge ou attestation. Les verrous natifs et les
index d’unicité empêchent deux tentatives actives dans le même contexte.

Deux contextes d’une personne restent indépendants, même sur une même famille.
Une nouvelle tentative autorisée est vide, y compris après réussite. Elle ne
modifie ni les réponses ni l’acquis d’une tentative terminée. QCU/QCM, appariement
et mise en ordre utilisent le barème exact sans crédit partiel. La correction
est disponible après fermeture, avec une nouvelle vérification de l’identité.

Un adaptateur peut exclure des preuves de son agrégat par un filtre privé, par exemple une tentative interrompue par l’organisme. Ce filtre est une conjonction avec le contexte, la personne et la version autorisés : il ne peut pas élargir leur périmètre. Il ne supprime ni réponse ni résultat et ne change pas l’échéance. La qualification de l’interruption appartient à l’adaptateur.

## Raccordement TM et limites

`training_management_survey` hérite du moteur. Il conserve les règles d’inscription,
les prérequis, les droits après expiration, les révisions motivées et les liens
vers les PDF privés. La dernière révision détermine l’affichage corrigé, tandis
que toutes les révisions et le score original restent conservés. Évaluations,
retours, clôture et attestations gardent leurs politiques propres.

Les tentatives de la génération précédente restent lisibles et reprenables sans
réécriture de contexte ni de chronomètre. Le cron historique délègue au moteur
et garde la fermeture des évaluations ; les appels répétés sont idempotents.
Le contrôle de mise à jour utilise uniquement des données fictives de la génération
J1 précédente. Il ne qualifie aucune migration métier historique ou Odoo 19.

Les pages apprenant TM conservent leurs URLs et widgets. Les [contextes autonomes](j3-autonomous-exam-rendering.md) raccordent les pages, obligations et autorisations de `training_elearning_survey`. La bibliothèque seule ne propose pas d’accès apprenant.

## Recette courte

1. Installer le commun seul ; tester le moteur via son contrat privé, puis refuser
   toute sauvegarde, remise ou correction sans adaptateur autorisant le contexte.
2. Dans TM, démarrer le même examen dans deux inscriptions d’une personne.
   Sauvegarder et terminer l’une ; l’autre reste indépendante. Refuser un tiers.
3. Sauvegarder avant, à et après l’échéance ; vérifier les réponses retenues,
   la clôture serveur et l’absence de redémarrage du chronomètre à la reprise.
4. Répéter la remise, démarrer deux fois simultanément et lancer cron/requête en
   concurrence. Vérifier une seule tentative active par contexte et aucune perte.
5. Mettre à jour depuis la tranche précédente ; comparer identifiants, réponses,
   marquages, délais, scores et révisions, puis reprendre une tentative existante.

Commandes : `python3 tests/ci/run_j1_mock_exam.py` pour le commun et
`python3 tests/ci/run_j1_mock_upgrade.py` pour la conservation TM. Les preuves
réellement exécutées restent dans les PR.
