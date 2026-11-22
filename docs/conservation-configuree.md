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
