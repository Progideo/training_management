# S09.1 — Évaluations nominatives et droits

Références : [#19](https://github.com/Progideo/training_management/issues/19),
[EVA01 et cadrage S09](s09-evaluations-quality.md). Le tableau consolidé reste S10 ;
les retours anonymes restent S09.2, selon la règle validée dans #19/#20.

## Parcours

1. Coordinateur : créer une version d’évaluation de positionnement ou d’acquis,
   ses critères et son éventuel score/seuil. Le socle accepte une évaluation
   observée avec source justificative. Avec l’intégration Surveys, ouvrir
   « Questionnaire », saisir les questions, puis publier depuis l’évaluation.
2. Affecter la version publiée à une inscription et définir ouverture/échéance.
   Aucune modification de version publiée ; créer une nouvelle version pour changer
   les questions, critères ou barème. Le positionnement S04 reste conservé.
3. Sur la réalisation, affecter superviseurs, missions formateur sans séance si
   nécessaire et responsable qualité des évaluations. Celui-ci habilite chaque
   évaluateur, par finalité, réalisation et période. Aucun droit d’évaluation ne
   découle du seul rôle coordinateur, formateur ou superviseur.
4. Dans « Mes évaluations de formation », le participant commence, enregistre et
   remet ses réponses. La remise est distincte de la validation. En évaluation
   observée, le formateur suit son protocole et renseigne sa source.
5. L’évaluateur habilité consulte les réponses remises et valide avec conclusion,
   source et motif. La révision ajoute une décision liée à la précédente. Pour
   une nouvelle tentative, le coordinateur indique un motif et une nouvelle échéance.
6. Depuis l’affectation, créer la preuve PDF S08. Le responsable qualité du dossier
   valide cette preuve puis applique les critères S08 de délivrance habituels.

## Règles et intégrations

Définitions : `training.evaluation`. Affectations : `training.evaluation.assignment`.
Décisions : `training.evaluation.result`. Habilitations :
`training.evaluation.authorization`. États : attendue, non commencée, en cours,
terminée/à valider et validée. Une référence de tentative précédente reste dans
l’historique ; une nouvelle tentative redevient non évaluée jusqu’à validation.
`result_available` distingue un score absent ou non applicable d’un zéro validé.

Les questions/réponses en ligne utilisent exclusivement les modèles Survey.
QCU/QCM à barème exact pour les évaluations notées ; choix et texte pour le
qualitatif. Échéance serveur et éventuelle durée d’épreuve restent distinctes.
Le formulaire est lié à sa tentative : une page ancienne ne peut pas remettre
une tentative rouverte. Pour une épreuve chronométrée commencée, le portail affiche
l’échéance effective de la tentative.
La passation S09 ne donne ni accès au circuit d’examen blanc S06 ni certificat natif
Survey. Les versions S06 et les sondages ordinaires conservent leurs parcours.

Le superviseur lit uniquement les affectations et résultats de ses réalisations,
sans accès ORM aux réponses, décisions détaillées ou preuves S08. Le formateur
utilise le portail et sa mission courante. Les validations exigent une habilitation
courante et une mission formateur courante, même en cumul de rôles ; retirer
l’une ou l’autre bloque immédiatement l’action. Les contrôles portent aussi
sur recherches, listes, exports, routes et anciens liens. Un compte client seul
n’obtient aucun accès aux résultats. Les réponses S09 restent exclues des lectures et exports natifs Survey, y compris
pour le coordinateur ; l’évaluateur habilité passe par la projection contrôlée.
Les élévations du service sont privées,
après vérification de l’identité et de la société exploitante.

Le PDF `S091-QWEB-1` conserve critères, finalité, version, tentative, décision,
évaluateur et score/seuil applicable. Positionnement → catégorie S08 `positioning` ;
acquis notés → `assessment`. Répéter l’export d’une décision rend la même preuve ;
une révision crée une nouvelle version. L’évaluation qualitative ne fournit pas
le score exigé pour une attestation de réussite. La validation pédagogique ne
remplace pas la validation qualité S08. Aucun PDF ou ZIP antérieur n’est réécrit.

Le pont temporaire de mise à jour Website déjà utilisé par S08 est repris pour
`20.0.1.9.0` ; sa valeur SQL par défaut est retirée dans la même transaction.
Aucune affectation, habilitation, évaluation ou présence n’est inventée sur les bases
existantes. Le socle reste installable sans Surveys ; versions : socle
`20.0.1.9.0`, Surveys `20.0.1.1.0`, Ventes inchangé.

## Recette courte

- Mobile (320 et 390 px) et clavier : atteindre les évaluations, répondre, enregistrer,
  recharger et remettre. Une remise incomplète conserve la saisie courante sans
  l’enregistrer comme preuve ; le retour d’erreur ou de réussite reçoit le focus.
  Vérifier aussi validation/révision et réouverture, sans champ de score pour le qualitatif.

- Publier V1, répondre, remettre puis valider à zéro et au seuil ; distinguer
  non évalué, qualitatif et échec. Réviser puis ouvrir une nouvelle tentative :
  anciens résultats et réponses restent identiques. Publier V2 sans modifier V1.
- Deux clients/réalisations : vérifier participant, formateur affecté, superviseur,
  qualité affectée, coordinateur sans habilitation et société étrangère. Retirer
  mission, rôle ou habilitation puis reprendre un ancien lien ou une action ouverte.
- Générer le vrai PDF, valider dans S08 et émettre l’attestation ; réviser ensuite
  et comparer les anciennes preuves. Refuser positionnement, qualitatif et examen
  blanc comme substituts d’une preuve d’acquis notés.
- Exécuter [run_s091.sh](../tests/ci/run_s091.sh) : S08 avec Website vers S09.1,
  installation vierge, historiques S02/S05/S06/S07/S08, seconde mise à jour et
  transactions concurrentes. Les résultats et limites sont consignés dans la PR.
