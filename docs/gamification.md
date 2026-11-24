# Gamification des formations

Décisions du 24 novembre 2026 ([#201](https://github.com/Progideo/training_management/issues/201)). Deux addons optionnels relient les preuves de
formation au moteur natif `gamification` (karma, rangs, badges, défis) :
`training_gamification` et, avec les examens blancs, `training_gamification_survey`
(installé automatiquement). Aucun module existant ne dépend d'eux.

## Règles

- Le module ne livre aucune règle active, aucun barème ni badge. Un administrateur
  global (`base.group_system`) crée les règles de points dans
  *Formations > Configuration > Gamification*, comme pour la
  [conservation configurée](conservation-configuree.md).
- Une règle associe un événement, un nombre de points, une limite facultative par
  inscription, des formations facultatives et une date de départ. Les événements
  antérieurs à cette date ne rapportent rien : activer une règle n'est pas rétroactif.
- Les points récompensent l'engagement, jamais le score. Ils n'ouvrent ni accès, ni
  session, ni tarif, ni document, et ne figurent pas sur les attestations.
- Seul le compte portail du participant reçoit des points. Sans compte, rien
  n'est attribué, et un compte créé plus tard ne récupère rien.
- Aucun classement n'est proposé : les défis natifs restent en visibilité personnelle.
  Seule exception acceptée : la page native `/profile/users` classe par karma les
  participants qui ont choisi de publier leur profil.
- Les campagnes d'évaluation anonymes ne rapportent jamais de points.

## Événements

| Événement | Preuve lue | Retrait si |
| --- | --- | --- |
| Présence validée (demi-journée) | `training.attendance` validée, non absente | présence invalidée |
| Activité terminée | `training.learning.progress` terminée | activité de nouveau incomplète |
| Travail validé par le formateur | progression d'une activité à validation, validée | validation retirée |
| Action de mise en pratique réalisée | `training.practice.action` réalisée ou close | accès retiré |
| Évaluation nominative complétée | destinataire participant, réponse reçue | — |
| Séance de tutorat tenue | réservation confirmée, créneau terminé | réservation ou créneau annulé |
| Formation terminée | inscription close (date de la transition) | — |
| Examen blanc terminé | première tentative remise, une fois par examen et inscription | — |

## Fonctionnement

- Une tâche planifiée horaire (ou le bouton « Appliquer maintenant ») compare,
  règle par règle, les preuves aux attributions. Elle est idempotente.
- Le journal `training.gamification.point` est écrit par le serveur seul. Un
  retrait ajoute une ligne négative ; l'attribution n'est pas réécrite.
- Chaque ligne crédite le karma natif, avec le nom de la règle comme motif.
- Badges et défis natifs comptent les lignes du journal (définition d'objectif sur
  `training.gamification.point`, par exemple `[('user_id', '=', user.id),
  ('kind', '=', 'grant'), ('withdrawn', '=', False)]`). Viser les comptes portail :
  le domaine d'utilisateurs proposé par défaut par Odoo ne retient que les internes.
- Supprimer un dossier terminé supprime ses points et leur karma.
- Une règle ayant attribué des points ne change plus d'événement ni de société :
  l'archiver et en créer une autre.

## Recette

1. Créer une règle « Présence » active, datée du jour ; valider une présence d'un
   participant avec compte ; appliquer : 1 ligne, karma crédité.
2. Appliquer une deuxième fois : rien ne change.
3. Invalider la présence ; appliquer : ligne de retrait, karma revenu.
4. Participant sans compte : aucune ligne.
5. Repasser plusieurs fois un examen blanc : une seule attribution.
6. Annuler puis supprimer le dossier : lignes et karma supprimés.
7. Un coordinateur ne voit ni le menu, ni les règles, ni le journal.
