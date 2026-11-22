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
