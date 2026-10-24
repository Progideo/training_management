# S09.4 — Intervenants, sous-traitance et veille

Réf. [cadrage S09](s09-evaluations-quality.md), QUA03 et issue #19.

## Règles

Le menu **Intervenants, sous-traitance et veille** ouvre trois types de dossiers
privés. Un intervenant réutilise un contact Odoo, sans salarié artificiel ni
nouvelle authentification. Une politique de conservation S08 approuvée est
obligatoire. Aucun délai légal ni effacement automatique n’est imposé.

Le référent qualité désigné gère les membres explicitement autorisés, la revue,
l’archivage et le gel conservatoire. Les membres coordonnateurs/qualité contribuent
au contenu et aux pièces. Une habilitation générale au groupe qualité ne donne
pas accès aux autres dossiers. Le retrait d’un membre retire aussi son accès
aux pièces et à l’historique. Aucun dossier n’est publié au portail ou au chatter.

Les justificatifs conservent le fichier original, la source, la date, la compétence
ou le périmètre, la validité et l’empreinte SHA-256. Une correction ajoute une
version liée à la précédente. Les pièces et historiques sont immuables ; un
dossier se conserve par archivage. Le gel empêche les mutations de contenu. Le référent désigné peut toujours
retirer le gel ou modifier les accès, avec traçabilité dans l’historique.

L’affectation synchrone (y compris séries de séances) et la mission asynchrone
affichent une alerte générique si les justificatifs sont absents ou hors validité
sur la période prévue (fin de séance/série ou réalisation incluse).
L’alerte reste affichée dans le formulaire, sans fenêtre modale à fermer.
Cette projection réservée aux coordonnateurs ne révèle ni fichier ni détail du
dossier privé et ne bloque pas la planification. L’archivage d’un ancien dossier
permet de conserver son histoire sans le considérer comme dossier courant.

Les habilitations d’évaluation S09.1 restent distinctes : mission effective,
société, usage et période sont contrôlés côté serveur. Les nouvelles décisions
conservent leur auteur/date et les retraits leur auteur/date. Un retrait est
définitif ; renouveler exige une nouvelle décision motivée. Les décisions anciennes
restent inchangées, avec auteur/date absents si non connus. Aucune habilitation
ni aucun dossier ne sont créés automatiquement à la mise à jour.

Une obligation contractuelle porte un responsable membre du dossier, une échéance,
une pièce et un constat de contrôle. Seul le référent désigné enregistre la
conformité/non-conformité datée. Un contrôle réalisé se conserve ; ajouter une
nouvelle obligation pour le suivi. Aucun achat ni traitement comptable n’est requis.

Une veille doit comporter source datée, analyse, décision et soit un impact,
soit une justification d’absence d’impact. Une URL seule ne permet pas la revue.
Les liens vers une action d’amélioration et une version de programme sont
facultatifs selon l’impact réel et soumis aux droits de lecture. Modifier le
contenu d’un dossier revu le remet en brouillon et conserve la décision précédente.

La mise à jour avec Website réutilise le mécanisme de compatibilité S08 pour
le chargement des vues, puis restaure le schéma natif (contrainte et défaut SQL).

## Contrat S10

`training.provider.service._states(offset, limit)` renvoie `total` et les lignes
`id/kind/state/frozen`, après filtrage natif des sociétés et des membres, avant
comptage et pagination (maximum 200 lignes). États stables : `draft`, `active`
(revu), `closed` (archivé). Les obligations exposent `pending/conform/nonconform`,
`due_date`, `checked_at` et `checked_by_id`, sous les mêmes droits que leur dossier.
Le gel est indépendant de l’état. L’échéance dépassée ne signifie pas conformité.
Ce contrat complète les sources S08/S09.1–3 ; aucun tableau de bord S10 ni accès
aux réponses pédagogiques privées n’est ajouté.

## Recette courte

Utiliser des profils restreints et des données fictives, dans une base de recette.

1. Comme coordonnateur, créer un dossier intervenant lié à un contact et choisir
   le référent et la politique approuvée. Enregistrer, puis utiliser « Ajouter un
   justificatif » (formulaire natif) pour joindre une pièce avec
   compétence/source et une validité expirée. Comme référent, revoir le dossier.
2. Dans l’assistant de séance, choisir cet intervenant : l’alerte apparaît et
   l’enregistrement reste possible. Vérifier aussi une série couvrant l’expiration
   et la mission asynchrone dans les rôles d’évaluation. Ajouter une pièce valide
   remplaçant l’ancienne ; la pièce originale reste consultable.
3. Créer un dossier sous-traitance et une obligation avec responsable et échéance.
   Une validation sans pièce/constat est refusée. Ajouter ces éléments, constater
   une non-conformité comme référent et vérifier l’auteur/date et l’immutabilité.
4. Créer une veille avec une URL seule : la revue est refusée. Ajouter date,
   analyse, décision et justification d’absence d’impact ; revoir. Modifier pour
   un impact réel, lier programme/action lisibles et refaire la revue.
5. Avec un autre référent, un superviseur et un compte portail, vérifier le refus
   de lecture/export/téléchargement des dossiers, pièces et historiques. Retirer
   le coordonnateur des membres et vérifier le retrait immédiat de ses accès.
6. Geler un dossier : modification, ajout de pièce et archivage sont refusés.
   Dégeler puis archiver ; vérifier la conservation du contenu et de l’historique.
   Retirer une habilitation d’évaluation : évaluation refusée et retrait daté,
   sans possibilité de réactivation de la décision retirée.
7. En français, mobile et clavier : parcourir la liste, créer/enregistrer les
   trois types de dossiers, joindre une pièce et contrôler une obligation.
   Vérifier libellés, focus, défilement et accès aux actions sans souris.
