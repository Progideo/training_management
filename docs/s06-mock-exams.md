# S06 — examens blancs, navigation et résultats par thème

Périmètre : [S06 #16](https://github.com/Progideo/training_management/issues/16),
[P07 #29](https://github.com/Progideo/training_management/issues/29) et
[P08 #30](https://github.com/Progideo/training_management/issues/30).
Référence fonctionnelle : EXA01–EXA06 et P07/P08 de la
[spécification v2](references/Training_Management_Specification_Fonctionnelle_v2.md).

## Standard conservé et extensions

L’addon optionnel `training_management_survey` dépend de `training_management`
et de `survey` Community, LGPL-3. Le socle reste installable sans Sondages.
La cible exacte est celle de la [couverture native](native-coverage.md).
Aucun fichier du cœur ni module standard n’est copié ou modifié.

| Besoin | Réutilisation / extension |
| --- | --- |
| Créer un examen | Éditeur et vues héritées de `survey.survey`, `survey.question`, `survey.question.answer`. Création depuis la version de programme. |
| Questions fixes | Configuration native : toutes les questions, ordre défini, QCU/QCM, sans condition ni tirage aléatoire. Publication vérifiée côté serveur. |
| Barème | Champ natif de points de la question ; extension ciblée de la notation : ensemble exact = points, sinon zéro. Aucun crédit partiel ni pénalité. |
| Réponses et tentatives | `survey.user_input` et `survey.user_input.line`, sauvegarde native `_save_lines`. Pas de référentiel concurrent. |
| Chronométrage | Début et échéance natifs ; durée figée par publication. Composant `survey.SurveyTimer` conservé. Contrôle serveur strict, sans la tolérance de dix secondes du contrôleur générique. |
| Expiration | Les réponses reçues sont figées à échéance, à la requête suivante ou par tâche native `ir.cron` chaque minute. L’échéance logique reste exacte même si la tâche s’exécute plus tard. |
| Répétitions | Questionnaire noté sans Certification, tentatives illimitées, y compris après 100 %. Le lien de nouvelle tentative reste accessible après tout résultat. |
| Navigation | Cadre de passation Sondages, portail/QWeb Odoo et widgets QCU/QCM natifs ; palette, marquage à revoir, effacement, récapitulatif et confirmation finale. |
| P08 | Thème principal ou section native, points et score par thème, explications et liens PDF autorisés après remise. Une section vide reste non évaluée. |
| Versions | Une version publiée devient immuable ; l’action de nouvelle version utilise la copie native. Les tentatives anciennes gardent leurs questions et barèmes. |
| Révision | Assistant natif : motif et nouveaux points par question. Révisions ajoutées, jamais écrasées ; résultat initial conservé. |

Les questions n’utilisent pas les points par proposition : le barème est celui de
la question. Les lignes natives portent les points une seule fois, sans double
comptage pour un QCM exact. Le seuil se compare avant arrondi d’affichage.

Le parcours de passation est intégré à Mes formations. Les routes génériques de
passation, d’impression et de résultat Sondages ne servent pas d’accès alternatif
aux examens privés. Les autres sondages gardent leurs comportements standards.
Le champ de marquage et l’interface de sauvegarde complètent les widgets natifs ;
ils ne remplacent ni les questions ni le stockage des réponses.

## Accès et historique

La coordination utilise le rôle natif Sondages/utilisateur pour l’éditeur. Les
examens, questions, propositions et tentatives de formation sont limités par une
règle globale à la coordination de la société exploitante autorisée. Le rôle
Sondages seul ne donne pas accès aux examens de formation. La société cliente
n’accorde aucun droit sur les résultats d’un salarié.

Le participant passe par un service privé qui contrôle l’utilisateur, le contact,
la société et l’inscription exacte avant toute lecture privilégiée. Les réponses
brutes et corrigés ne sont pas lisibles directement par les comptes portail, ni
par recherche, export ou jeton partagé. Les images de propositions ont une route
contrôlée par la même identité ; les jetons binaires génériques ne suffisent pas.
Les fichiers rattachés aux examens et questions restent privés et liés à leur
parent. Ils ne peuvent être partagés, détachés ou copiés par les opérations de
pièces jointes ; leur contenu devient immuable à publication. Les propositions
composées d’une image conservent leur libellé natif et leur image dans le corrigé.

Les mutations reprennent le contrôle d’accès et le verrou natif S03. La règle
EXA05 se limite à reprendre une tentative active ; un index unique natif protège
cette unicité. Aucun dispositif général de gestion de concurrence n’est ajouté.

Chaque changement reçu est sauvegardé, y compris un effacement ou un marquage.
L’écran distingue sauvegarde en cours, reçue et échouée. Une coupure ne permet
pas de récupérer les changements que le serveur n’a pas reçus ; la remise
manuelle attend la fin des sauvegardes. À expiration, seules les réponses déjà
reçues avant l’échéance comptent. Un rechargement reprend la même tentative.

Une tentative commencée avec des droits valides peut être terminée jusqu’à son
échéance si les droits de formation expirent entre-temps. Cette expiration
interdit tout nouveau départ. Suspension et révocation bloquent immédiatement
la lecture et les mutations, y compris pour une tentative déjà commencée.

Une réussite ne bloque jamais une nouvelle tentative si les droits restent
actifs. Chaque tentative a sa propre durée complète et son propre résultat.
Une tentative en cours est reprise au lieu d’en créer une seconde. Les résultats
restent consultables dans Mes tentatives après expiration des accès ; suspension
et révocation bloquent leur lecture. Les ressources de révision restent soumises
à la politique S05 actuelle, sans diffusion de ressources devenues interdites.

Une activité S05 d’évaluation référence une version publiée du même programme.
Son meilleur résultat de tentative terminée, avec les révisions motivées, fournit
le score de référence au seuil de progression S05. Une activité ayant des
tentatives reste inchangée ; affecter V2 à une nouvelle activité. L’archivage
standard d’un examen interdit les nouveaux départs et conserve ses historiques.

Aucun certificat, badge ni courriel de réussite n’est généré. Un examen blanc
ne constitue ni une certification officielle ni une attestation de formation.
Le rapport générique de certification refuse aussi les tentatives d’examen blanc,
y compris depuis le menu d’impression de la coordination.
Conservation et exports en masse restent rattachés à S11.

## Recette courte

1. Depuis un programme, créer un examen ; saisir deux QCU/QCM, points, durée,
   seuil, thèmes et explication. Vérifier le refus d’une publication invalide,
   puis publier et affecter l’examen à une activité d’évaluation.
2. Comme participant, confirmer le départ ; répondre, effacer, marquer à revoir,
   naviguer et recharger. Vérifier les états de sauvegarde et le temps continu.
3. Remettre après récapitulatif ; vérifier 18/24 = 75 %, seuil inclusif, QCM
   partiel ou inexact à zéro, correction finale et somme des thèmes égale au total.
4. Réussir à 100 %, puis repasser immédiatement et réussir à nouveau : deux
   résultats conservés, nouvelle durée complète. Recliquer avant la fin reprend
   la tentative active. Une remise répétée ne crée pas une autre tentative.
5. Tester la coupure et l’échéance : aucune réponse tardive retenue ; vérifier
   les refus avec un pair, un rôle Sondages seul, une autre société et un accès
   suspendu, y compris liens directs et jetons natifs.
6. Créer V2 et réviser un résultat avec motif : V1, ses réponses et son résultat
   initial restent lisibles. Vérifier la progression S05 et les liens de révision.

Tests reproductibles : [run_s06.sh](../tests/ci/run_s06.sh). Les résultats
réellement exécutés et les limites de recette sont consignés dans la PR.
