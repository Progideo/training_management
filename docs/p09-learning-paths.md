# P09.1 — Composition et suivi interne des parcours

Référence : [P09 #32](https://github.com/Progideo/training_management/issues/32),
spécification §21, CAT01, INS02 et PED01.

## Couverture native et choix

La cible reste Community `20.0-20261015`, image et commit précisés dans
[native-coverage.md](native-coverage.md). Le code installé de `website_slides`
propose `slide.channel.prerequisite_channel_ids` et calcule les acquis depuis
`slide.channel.partner.member_status = completed`. Les méthodes d'adhésion
`_action_add_members` alimentent ce registre natif, pas `training.enrollment`.
Il ne couvre pas les versions pédagogiques et inscriptions contrôlées du projet.

Sources inspectées dans cette image, sous `odoo/addons/website_slides/` :

| Fichier | SHA-256 |
| --- | --- |
| `models/slide_channel.py` | `4de032cf3bd434dbf90bbe704f80ff7cd7ac3917c119216d97d965abe1324561` |
| `models/slide_channel_partner.py` | `ffab1416cc2caaa54220e1873d026fa88cc180b035c6b540937168a570a0e999` |

L'extension ciblée du socle ajoute donc une composition pédagogique et des
références aux inscriptions existantes. Aucun module standard n'est copié,
aucune adhésion eLearning ni inscription supplémentaire n'est créée.

## Règles

- Un parcours contient une version standard par formation, des positions uniques,
  un ordre conseillé ou obligatoire et des prérequis explicites vers des étapes
  antérieures. La durée additionne les durées pédagogiques des programmes.
- La validation fige sa définition. Pour évoluer, dupliquer en brouillon puis
  réviser et valider ; les anciennes références restent attachées à l'original.
- Le coordinateur rattache chaque étape à une inscription existante. Le participant
  et la société viennent de cette inscription. Un programme différent nécessite
  une équivalence motivée, validée par ce coordinateur et datée par le serveur.
  L'équivalence est individuelle, sans validité générale implicite.
- Une inscription ne compte qu'une fois parmi les rattachements courants du parcours et une étape une fois par
  participant. La même inscription peut servir dans plusieurs parcours : ses
  droits, places, preuves et progressions restent uniques.
- Une étape est complète si l'inscription est confirmée ou clôturée et si toutes
  ses activités obligatoires sont complètes selon S05/S06. L'absence d'activité,
  une simple clôture administrative ou un examen blanc isolé ne suffit pas.
  La complétion du parcours ne certifie pas à elle seule une compétence.
- L'ordre obligatoire exige toutes les étapes précédentes ; les prérequis
  explicites s'appliquent aussi à l'ordre conseillé. Une référence manquante
  bloque l'étape. Le contrôle d'accès serveur réévalue ces conditions.
  Si une inscription appartient à plusieurs parcours, leurs contraintes se cumulent.
- Aucun rattachement bloquant à une inscription déjà active n'est accepté.
  Les références validées et leurs motifs sont immuables. Les créations et
  ouvertures utilisent les verrous natifs et les unicités en base.
- Un rattachement erroné peut être retiré avec un motif obligatoire via
  l'assistant natif existant. Auteur, date et motif sont journalisés ; le retrait
  répété garde sa trace initiale. La référence reste conservée mais ne participe
  plus au blocage ni aux unicités des références courantes. Une nouvelle
  référence peut la remplacer. Retirer un prérequis peut bloquer les étapes qui
  en dépendent ; les accès sont toujours réévalués, sans ouverture automatique.
- Lecteur : composition seulement. Coordinateur : composition et suivi individuel
  dans ses sociétés autorisées. Aucun accès aux nouveaux objets pour le public,
  le portail, les représentants clients ou l'interne sans rôle.

## Limites de cet incrément

Interface interne native ; la synthèse participant au portail et la vente d'un
parcours restent à réaliser. Aucun prix global ni produit commercial de parcours
n'est introduit. Avant vente : fixer contenu de l'offre, tarif global ou par
formation, devise unique, reports, annulations et traitement des acquis déjà
obtenus. Les ventes de formations existantes conservent leur fonctionnement.
Les données historiques non qualifiées restent des archives ; aucune équivalence
n'en est déduite automatiquement. L01 reste une validation de lancement.

## Recette courte

1. Coordinateur : créer deux étapes de formations distinctes, choisir l'ordre,
   fixer un prérequis puis valider. Vérifier durée et refus de modification.
2. Rattacher une inscription existante par étape pour un participant fictif.
   L'étape suivante reste bloquée tant que la précédente n'est pas acquise.
3. Compléter les activités obligatoires via le circuit S05/S06 : l'étape devient
   disponible, sans création de place, droit ou progression supplémentaire.
4. Tester une autre version avec motif d'équivalence et un acquis antérieur,
   puis refuser motif vide, doublon, écriture et suppression des références.
   Retirer un mauvais rattachement avec motif, rejouer, vérifier le journal et
   créer son remplacement sans effacer l'ancienne référence.
5. Lire avec un lecteur, un portail et un coordinateur d'une autre société :
   composition seule pour le lecteur, refus des suivis individuels et hors société.
6. Mettre à jour une copie fictive V1, comparer inscriptions/progressions et
   historiques avant/après, puis répéter la mise à jour.
