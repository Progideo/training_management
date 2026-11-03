# Lecteurs et définitions d’examens communs

Suite de [J1 #123](https://github.com/Progideo/training_management/issues/123),
selon le cadrage consolidé du 3 novembre 2026. Le graphe cible à dix addons est
conservé. Cette tranche ajoute les lecteurs à la [bibliothèque interactive](j1-shared-interactive.md)
et crée `training_mock_exam`. L’application eLearning autonome reste à construire.

## Lecteurs privés

`training_interactive` possède les autorisations courtes, le lecteur parent,
le runtime isolé et les dépendances H5P/SCORM, avec leurs licences conservées.
L’auteur peut prévisualiser sans TM. Les paramètres d’origine, URLs et noms
techniques historiques restent stables ; ils ne créent pas de dépendance métier.

Les autorisations durent cinq minutes, sont liées à une version et un utilisateur
actif et revérifient ses droits à chaque lecture/renouvellement. Retrait ou perte
d’habilitation ferme l’accès. Le paquet s’exécute sur un nom d’hôte distinct,
sans session portail ; les messages vérifient origine, fenêtre et nonce.

L’adaptateur historique fournit le contexte apprenant et l’URL de sauvegarde.
Il conserve inscriptions, tentatives, révisions, idempotence et progression TM.
Le lecteur commun ne calcule ni présence ni acquis et ne délivre pas d’attestation.

## Bibliothèque native d’examens

`training_mock_exam` dépend du catalogue et de Survey Community. Il réutilise
`survey.survey`, ses questions et ses propositions. Plusieurs familles d’examens
peuvent référencer une formation. Une version publiée est figée ; une nouvelle
version copie les questions natives et exige une référence distincte et un motif.

L’auteur dédié travaille dans ses sociétés, sans rôle TM. QCU/QCM, thème principal,
explication finale, durée et points positifs sont contrôlés à la publication.
Appariement et mise en ordre réutilisent les propositions natives et leur correction
exacte ; l’éditeur appartient au commun. Les évaluations, retours et diagnostics
TM gardent leurs propres règles. Une définition ne peut cumuler les deux contextes.

Les fichiers et corrections sont privés, y compris via les pièces jointes publiques,
jetons et routes Survey natives. La publication d’un lot est atomique ; le changement
de société d’une formation déjà référencée est refusé. Les versions, questions,
corrections et fichiers publiés ne sont pas réécrits.

Cette bibliothèque ne lance pas encore de passation commune. Ses jetons Survey et
créations directes de réponses sont fermés jusqu’au raccordement d’un contexte
apprenant contrôlé. Le service TM existant conserve son chronométrage serveur,
ses résultats et les interactions enrichies. L’extraction de ce service, des pages
apprenant et des obligations par contexte est l’étape suivante.

## Recette courte

1. Installer `training_interactive` seul ; configurer les deux origines et
   prévisualiser un paquet fictif avec un auteur sans rôle TM. Vérifier sous-fichiers,
   refus des URLs natives et fermeture après retrait.
2. Installer `training_mock_exam` seul ; créer deux examens sur une formation,
   publier QCU/QCM et interactions, puis créer une version motivée. Refuser la
   modification publiée, une référence de version répétée et une société étrangère.
3. Refuser la passation directe par jeton Survey et la lecture d’un fichier privé
   par portail, utilisateur étranger ou pièce jointe publique.
4. Mettre à jour les bibliothèques : rapprocher identifiants, versions, corrections
   et octets. Avec l’adaptateur historique, reprendre une tentative TM et vérifier
   les examens, évaluations, orientation et attestations existants.

Commandes : `python3 tests/ci/run_j1_interactive.py` et
`python3 tests/ci/run_j1_mock_exam.py`. La composition utilise le commit TM
épinglé par `compatibility.json` dans l’autre dépôt. Les résultats et limites
réels restent dans les PR. Aucune migration de données historiques ni bascule
vers l’application autonome n’est qualifiée par cette tranche.
