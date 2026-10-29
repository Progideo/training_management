# P16 — statuts publics et alertes de session

Besoin : [#39](https://github.com/Progideo/training_management/issues/39).
P15 est annulé ; aucun comparateur ni devis associé n'entre dans P16.
Le catalogue P03/P04 et le registre S03 restent les références uniques.

## Cadrage validé le 29 octobre 2026

| Sujet | Règle | Exemple de recette |
| --- | --- | --- |
| Publication | Action explicite du coordinateur, limitée à une réalisation datée future et à un programme actuellement publié au catalogue de la même société. Aucune publication implicite d'une réalisation existante ou intra privée. | Une réalisation confirmée reste privée tant qu'elle n'est pas publiée. |
| Ouverture commerciale | Décision explicite distincte de l'état interne ; seule une session commercialement ouverte peut être présentée. | Préparation ouverte : « Ouverte ». Confirmation interne avec places : « Confirmée ». |
| Disponibilité | Calcul S03 à l'heure serveur, réservations non expirées et lots inclus. Capacité nulle : illimitée. « Complète » prime sur ouverte/confirmée. | Lot de 10, 7 noms, capacité 10 : complète ; expiration du lot : places disponibles. Aucune nouvelle admission publique. |
| Départ garanti | Engagement explicite motivé du coordinateur pour la société exploitante, avec auteur/date ; distinct de la confirmation interne et du seuil. | Seuil atteint ou confirmation interne : aucun départ garanti automatique. Un changement des dates ou du fuseau retire l'engagement et la publication jusqu'à nouvelle décision. |
| Informations publiques | Titre du programme, dates de début/fin, fuseau, modalité, statut et engagement autorisé. Aucun nom interne de réalisation, effectif, client, participant, salle privée ou lien distant. | Annulation, début de session, retrait du programme ou fermeture commerciale : projection supprimée à la prochaine lecture, sans cache. |
| Alerte volontaire | Compte Odoo existant authentifié, choix par formation et société ; case non précochée, texte exact, auteur et date conservés. Pas d'abonnement anonyme dans ce premier incrément. | Un client ne peut abonner ses salariés ; être inscrit ou follower n'abonne pas aux alertes. L'abonnement suit les versions publiées du même cours. |
| Déclenchement | Première publication d'une nouvelle réalisation datée future après abonnement. Une notification par abonnement/réalisation ; republier ou modifier les dates ne renvoie pas d'alerte. | Deux traitements concurrents ou répétés : un seul courrier. Une nouvelle réalisation : nouvelle alerte. |
| Désabonnement | Gestion depuis le compte, indépendante des accès pédagogiques ; effet immédiat, y compris sur les courriers encore en file. Réabonnement explicite sans rejeu des anciennes dates. | Désabonnement puis envoi de la file : aucun transport. |
| Courriel | File native `mail.mail`, destinataire unique ; lien vers la fiche publique et gestion des alertes. Consentement, adresse actuelle, société et publication revérifiés au transport. | Retrait/annulation après mise en file : envoi refusé ; aucune adresse collective ni donnée privée. |
| Conservation | Politique SEC02 approuvée avant abonnement, preuve privée ; aucune durée ou purge automatique inventée. | Retrait conserve la preuve sans conserver un abonnement actif. |

Le mainteneur a validé ces règles, y compris les alertes réservées aux comptes
Odoo existants. Aucun abonnement, publication ou garantie n’est repris
automatiquement sur les dossiers existants.

## Standard exact et choix technique

Sources lues dans l'image Community `20.0-20261015`,
[digest figé](ci.md), licence LGPL-3 :
`event/models/event_event.py`, `event/models/event_registration.py`,
`website_event/models/event_event.py`, `website_event/controllers/main.py`,
`mass_mailing/models/mailing_contact.py`, `mass_mailing/controllers/main.py` et
`mail/models/mail_followers.py`.

| Standard | Couverture / limite | Choix retenu |
| --- | --- | --- |
| Event | Dates/fuseau, capacité, inscriptions ouvertes/complet calculés ; comptage open/done, distinct des réservations et lots S03. | Réutiliser S03 sans deuxième registre ni nouvelle dépendance Event. |
| Website Event | Publication et visibilité sur site ; routes d'inscription liées aux événements. | Prolonger la projection scalaire P03/P04 en Portal/QWeb, avec et sans Website. |
| Chatter | Followers de ressources et sous-types de messages. | Ne pas confondre abonnement privé et accord aux alertes publiques. |
| Mass Mailing | Contacts de mailing, listes, opt-out et désabonnement avec jetons de campagne. | Ne pas créer de référentiel concurrent ; accord par formation sur le contact/compte existant et transport natif déjà utilisé par S10/P14. |

Reproduction ciblée : `python3 tests/ci/run_p16_native.py`, uniquement sur base
jetable fictive ; aucune communication externe. La sonde distingue le comptage
Event du comptage S03 et examine l'opt-out natif ; elle ne démontre pas une
inscription Website ni une résistance concurrente du standard.

## Utilisation

Sur une réalisation, l'action **Session : état et disponibilité** présente l'état
interne, l'état de publication du programme, les dates/fuseau et la disponibilité
S03 constatée à l'heure serveur. Réservée au coordinateur dans ses sociétés,
elle ne prend aucune décision de publication, d'ouverture ou de garantie.
Le coordinateur utilise l’onglet **Session publique** pour publier/ouvrir,
fermer la commercialisation, retirer ou garantir le départ avec motif. Le journal
S03 conserve auteur, date et décision. Les courriels figurent dans cet onglet.
L’administrateur sélectionne une politique SEC02 approuvée dans les paramètres
de notification de la société ; cela n’active pas le transport.

La fiche catalogue mène aux dates publiques et à l’accord volontaire. Le compte
retrouve ses alertes et leur retrait dans `/my/training-date-alerts`, même sans
accès pédagogique actif. Après retrait, **Me réabonner** rouvre le consentement
pour une version encore publique du même cours et de la même société.
L’accord porte sur les conditions affichées et leur
politique de conservation ; une modification oblige à relire avant validation.
La file native conserve les erreurs visibles ; aucun cron supplémentaire.
Les verrous et révisions S03/société sérialisent publication, abonnement,
désabonnement et préparation du transport. Les contraintes d’unicité complètent
ces contrôles. Un envoi déjà engagé avant le retrait ne peut être rappelé.

## Recette courte

1. Comparer lot de 10 et 7 noms, réservation expirée, gratuité et capacité illimitée.
2. Vérifier les refus coordinateur autre société, lecteur, commercial seul,
   interne sans rôle, portail et public, y compris par appel direct.
3. Vérifier qu'un diagnostic répété ne modifie ni réalisation, ni historique,
   ni programme, ni file de courriels. Contrôler les dates dans leur fuseau.
4. Installer à neuf avec/sans Website, mettre à jour deux fois et comparer les
   historiques et fichiers existants. Vérifier français et formulaire natif.
5. Compléter la recette publique : états, retrait,
   consentement, désabonnement, concurrence et revérification au transport ;
   navigateur, clavier et mobile 390 × 844.
