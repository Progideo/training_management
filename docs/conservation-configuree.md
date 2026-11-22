# Conservation configurée hors du module

Décisions du 22 novembre 2026. Elles remplacent les politiques de conservation de
[S08](s08-closure-documents.md) et de [J31](j31-calendar-retention.md) ; [SEC02](references/Training_Management_Specification_Fonctionnelle_v2.md#sec02-gouverner-conservation-et-exports) est amendée.

## Règles

- Même philosophie qu'Odoo standard : le module ne livre aucune règle, durée ni
  politique de conservation. Seul le nettoyage technique est codé.
- Les durées relèvent de l'organisme. Un administrateur global (`base.group_system`)
  les configure avec Data Recycle ou des actions automatisées, comme dans Odoo.
- Les preuves restent par défaut. Une fois leur dossier terminé, elles sont
  supprimables par l'administrateur ou par une règle qu'il a configurée.
- Le gel existant (« Legal Hold » des dossiers de clôture, qualité et intervenants)
  est conservé : il bloque la suppression tant qu'il est actif.
- Les suppressions suivent la traçabilité native d'Odoo, sans journal dédié.
- Le module fournit l'anonymisation, sans échéance par défaut.
- Nettoyage technique : un abonnement aux alertes jamais confirmé est supprimé
  après 60 jours.

## Lot A — politiques retirées

- Aucun dossier n'exige plus de politique : clôture, qualité, intervenants,
  campagnes d'évaluation, mise en pratique, tutorat, témoignages, projets,
  réclamations en ligne.
- Le menu et les vues des politiques sont retirés. Les champs `retention_id` et la
  table `training_retention_category` restent en base comme historique, en lecture
  seule, comme pour les alertes (#190). Les politiques approuvées ne sont ni
  modifiées ni supprimées.

Recette : créer un dossier de clôture, une réclamation et un droit de tutorat
sans politique ; vérifier l'absence du menu « Politiques de conservation » et du
champ dans les formulaires ; mettre à jour une base contenant des politiques et
vérifier qu'elles sont conservées.

## Lot B — courriels des journaux

- Les journaux d'envoi gardent leur courriel par défaut comme preuve d'envoi.
- Leur lien vers le courriel ne bloque plus sa suppression (`set null`) : le
  nettoyage natif des courriels annulés (6 mois) et les règles Data Recycle sur
  `mail.mail` s'appliquent ; le journal reste, sans courriel, et n'est pas renvoyé.

Recette : annuler le courriel d'un journal, le vieillir de 7 mois, lancer
« Base : Auto-vacuum internal data » ; le courriel disparaît, le journal reste.

## Lot F — nettoyage technique

- Une demande d'alerte de visiteur jamais confirmée est supprimée 60 jours après
  sa dernière demande de confirmation (`@api.autovacuum`, tâche quotidienne
  native). Un abonnement confirmé, même désabonné, reste une preuve.
- Les autorisations de lecture eLearning expirées étaient déjà nettoyées ; aucun
  autre jeton du module n'expire.

Recette : créer une demande de visiteur, la vieillir de 61 jours, lancer
« Base : Auto-vacuum internal data » ; la demande disparaît, un abonnement
confirmé puis désabonné reste.

## Lot C — preuves supprimables par l'administrateur

- Les preuves restent par défaut. Seul un administrateur (`base.group_system`)
  peut les supprimer : par l'action « Supprimer le dossier » ou par une règle qu'il
  a configurée (Data Recycle, action automatisée ; les tâches planifiées tournent
  sous `__system__`, qui est administrateur). Les droits d'accès des modules ne
  changent pas : l'administrateur n'obtient pas la lecture des données privées.
  L'utilisateur réel décide : un parcours en `sudo()` d'un autre utilisateur reste
  refusé.
- Le gel (« Legal Hold ») bloque la suppression du dossier et de ses preuves
  (preuves de clôture, fichiers et évènements qualité, pièces des intervenants).
  Un dossier de clôture est gelé par défaut ; ses rôles (qualité, coordination)
  peuvent lever le gel, même une fois le dossier clos.
- Inscriptions, réalisations et allocations ne se suppriment qu'une fois
  terminées : inscription clôturée, annulée, remplacée ou abandonnée ; réalisation
  clôturée ou annulée ; allocation expirée ou annulée.
- L'action « Supprimer le dossier » (menu Action des inscriptions, réalisations,
  réclamations, actions d'amélioration et dossiers intervenants, ou `records.action_training_delete_dossier()` dans une action
  automatisée) supprime le dossier et les preuves training qui en dépendent, des
  plus profondes au dossier. Ventes, factures et pistes ne sont jamais supprimées :
  si l'une référence encore le dossier, rien n'est supprimé.
- Les protections d'intégrité restent : versions validées, contenus d'examens
  publiés, PDF de référence, lignes de vente acceptées.

Recette : en coordinateur, la suppression d'un journal d'envoi est refusée ; en
administrateur, elle réussit. Sur une inscription en cours, « Supprimer le
dossier » est refusé ; après annulation, l'inscription et ses journaux
disparaissent, la réalisation reste. Un dossier de clôture gelé et ses preuves
restent jusqu'à la levée du gel.

## Lot E — anonymisation

- « Anonymiser le dossier » (inscription terminée, non gelée ; administrateur,
  à la main ou par `records.action_training_anonymize_dossier()` dans une action
  automatisée) efface les copies de données personnelles du dossier et de ses
  preuves training : adresses des journaux d'envoi et des nominations, identité
  publique des témoignages, signature recopiée dans la preuve d'émargement. Les
  courriels envoyés sont supprimés. Les preuves restent ; `anonymized_at` permet
  à une règle de filtrer les dossiers déjà anonymisés.
- « Anonymiser le participant » (contact) anonymise tous ses dossiers et ses
  abonnements aux alertes, puis renomme et archive le contact. Il est refusé si le
  contact a un utilisateur, des factures, des commandes ou des pistes : leurs
  outils natifs décident.
- Chaque modèle déclare ses copies (`_training_personal_fields`) ; un e-mail
  obligatoire est remplacé par une adresse neutre propre à la ligne.
- Limites : les textes libres (motifs, commentaires, messages de discussion) ne
  sont pas réécrits.

Recette : sur une inscription annulée, « Anonymiser le dossier » vide l'adresse
des journaux et supprime leurs courriels, l'inscription et ses journaux restent.
Sur un contact sans utilisateur, « Anonymiser le participant » l'archive sans
nom ni coordonnées ; sur un participant ayant un compte portail, l'action est
refusée.
