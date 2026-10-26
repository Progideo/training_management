# Catalogue — Catégories et PDF du programme

**Cadrage validé.** Lot distinct de S04 ([PR #54](https://github.com/Progideo/training_management/pull/54)).
Références : CAT01–CAT02, SEC01–SEC02 et UX01 de la
[spécification](references/Training_Management_Specification_Fonctionnelle_v2.md),
[S01 #11](https://github.com/Progideo/training_management/issues/11),
[P01 #23](https://github.com/Progideo/training_management/issues/23),
[P03 #25](https://github.com/Progideo/training_management/issues/25).

## Périmètre

Classer les formations dans le catalogue interne et fournir le PDF fidèle de
chaque version de programme. Réutiliser les fiches, états et habilitations S01 ;
les devis et réalisations gardent leur référence de programme S02/S03.

Ce lot complète CAT01–CAT02 sans achever le catalogue public. Recherche publique,
navigation du site et appels à l'action restent à articuler avec P01/P03.
Les supports pédagogiques privés restent S05 (#15), les extraits de démonstration
et mini-quiz restent P04 (#26). Aucun changement aux convocations S04.

## Décisions retenues

| Choix | Décision | Conséquence |
| --- | --- | --- |
| Classement | Une catégorie pédagogique par formation, liste plate propre à la société ; facultative en brouillon, demandée avant une nouvelle validation/publication | Une seule sélection, pas d'arborescence ni d'étiquettes multiples. Les formations historiques restent utilisables sans reclassement forcé. |
| PDF de référence | Génération et conservation automatiques lors de la validation du programme | Aucun bouton supplémentaire pour figer le document. Un échec PDF empêche la validation ; les téléchargements suivants rendent exactement le même fichier. |
| Diffusion initiale | Téléchargement interne par les profils déjà autorisés ; transmission au client volontaire dans le circuit commercial existant | Aucun compte ni action imposés au client, aucun envoi automatique. L'accès direct client/formateur et le téléchargement public seront traités dans leurs lots respectifs. |

Le catalogue public et le téléchargement portail restent hors de ce lot : ils
nécessitent leurs routes, leur sélection des versions et leur recette d'accès.

## Parcours courts

**Coordinateur :** choisir la catégorie sur la fiche formation ; compléter puis
valider le programme comme aujourd'hui. Le PDF devient disponible dans la même
fiche, en un clic. Publier reste l'action S01 existante, sans nouvelle approbation.
Une prévisualisation facultative du brouillon porte une mention « Brouillon »
et ne devient jamais le PDF de référence.

**Commercial ou lecteur autorisé :** ouvrir la version choisie sur le devis ou
la réalisation, puis télécharger son PDF. Aucune recherche manuelle de « dernière
version », aucun remplacement automatique d'une pièce jointe déjà envoyée.
Le lot n'ajoute ni assistant d'envoi ni modification des modèles de courriel.

**Client et formateur :** aucune démarche supplémentaire dans ce lot. Le programme
communiqué reste celui du devis/de la réalisation, même si V2 est publiée ensuite.
Les espaces S05/P05 et le portail formateur réutiliseront ultérieurement ce fichier
après leurs contrôles d'habilitation, sans donner de droits ORM généraux.

## Couverture native vérifiée et extensions nécessaires

Sources de l'image Community exacte : `20.0-20261015`,
`odoo@sha256:61e3c71b0503c5f658e604c3e340bede20b97d05f726179fa006eae50a32fd23`,
dans `/usr/lib/python3/dist-packages/odoo`. Les modules candidats ci-dessous
sont présents et déclarent LGPL-3. Leur présence ne prouve pas leur installation.

| Standard examiné, chemins sous `addons/` | Capacité observée | Choix retenu |
| --- | --- | --- |
| `product/models/product_category.py`, `product/security/ir.access.csv`, `account/models/product.py` | Catégories hiérarchiques, société facultative et droits de gestion produits ; propriétés comptables ajoutées par Account | Ne pas utiliser le classement pédagogique pour piloter la catégorie comptable du produit commercial. Une simple relation à ce référentiel imposerait aussi le module Product et l'adaptation des droits. |
| `product/models/product_tag.py`, `product/security/ir.access.csv` | Étiquettes plates traduisibles, unicité globale du nom, visibilité client par défaut, gestion par le responsable produits | Réutilisation possible, mais restriction pédagogique et isolation par société à ajouter. Peu d'avantage sur un petit référentiel dédié, et dépendance Product supplémentaire pour le socle. |
| `website_sale/models/product_public_category.py`, manifest Website Sale | Catégories publiques liées aux produits et au site ; dépendances commerce et paiement Website | Ne pas installer le commerce en ligne pour un classement interne. |
| `website_slides/models/slide_channel_tag.py`, manifest et droits eLearning | Étiquettes de cours regroupées ; visibilité publique liée à la couleur ; groupes visibles au public | Ne pas rendre eLearning/Website obligatoires pour le catalogue ; ces étiquettes ne sont pas déjà les catégories des formations S01. |
| `base/models/ir_actions_report.py` | Rapports QWeb HTML/PDF, nommage, stockage et réutilisation de pièces jointes | Réutiliser QWeb et le moteur natif ; créer seulement le gabarit du programme et les règles de gel. |
| `base/models/ir_attachment.py`, `base/models/ir_binary.py`, `web/controllers/report.py` | Fichiers liés aux enregistrements, contrôle d'accès, possibilités de liens publics ou de jetons | Réutiliser le stockage, sans rendre les fichiers publics ni créer de jeton de partage. Vérifier aussi les URL directes des fichiers et rapports. |

Le code de rapport réutilise une pièce par nom/modèle/identifiant lorsque
`attachment_use` est activé. Il peut continuer le rendu si l'enregistrement de la
pièce échoue par manque de droits. Ce mécanisme seul ne garantit donc ni le gel
métier ni l'atomicité validation/fichier. La présence de `wkhtmltopdf` est vérifiée ;
le rendu métier utilise QWeb et le moteur Community `base_report_wkhtmltox`
(LGPL-3), déclaré explicitement avec Web. Le HTML autonome évite le chargement
d'assets HTTP pendant la validation. La route de rapport PDF retourne elle aussi
le fichier conservé pour une version figée ; le rendu HTML reste limité aux brouillons.

Architecture retenue : petit référentiel `training.category` dans
`training_management` (nom traduisible, société, actif), relation unique depuis
`training.course`. Le programme lit cette catégorie par relation, sans seconde
valeur stockée ni affectation directe possible par API. Ce référentiel représente
le domaine pédagogique absent du
socle ; il ne recopie ni produits ni cours eLearning. Aucun second référentiel de
catégories pédagogiques dans un futur site : exposer cette même source, sans
synchronisation bidirectionnelle.
Aucune dépendance Product, Website Sale, eLearning ou service externe ajoutée pour
ce besoin ; utiliser explicitement les composants Web nécessaires au rapport.

## Fichier de référence et conservation

La validation est le bon point de gel : S02 autorise déjà les devis pour une
version **validée ou publiée**. Attendre la publication laisserait un devis sans
PDF de référence. Générer une seule pièce native liée à la version, avec auteur,
date serveur, langue du programme et empreinte du contenu. Verrouiller la version
et traiter validation, pièce et métadonnées dans la même transaction. Un double
clic ou une concurrence ne crée pas deux fichiers de référence.

### Contenu exact du PDF

Le PDF est la fiche du programme applicable, liée à une version précise. Son
contenu reprend les champs validés S01 :

- Titre du programme, référence de version et identité de l'organisme.
- Objectifs, public concerné et prérequis.
- Contenu détaillé du programme.
- Durée, modalité (présentiel, distanciel, mixte ou eLearning) et langue.
- Méthodes pédagogiques et modalités d'évaluation.
- Conditions d'accès à la formation.
- Informations et contact d'accessibilité.
- Mention « Sur devis », sans tarif propre à un client ni calcul depuis un produit vivant.

L'identité et la présentation viennent de la société exploitante, jamais d'une
entreprise codée en dur. La catégorie reste un filtre du catalogue, sans
engagement contractuel dans le PDF. Les dates des séances, participants,
adaptations individuelles et conditions commerciales du client restent dans
leurs documents respectifs. P03 complétera les inclusions, les supports et les
examens ; ne pas annoncer ici ses champs comme déjà livrés.

### Conservation et versions antérieures

Le téléchargement rend les octets conservés, même après changement du gabarit,
du logo, du nom de la formation ou d'une catégorie. Une nouvelle version crée
son propre document sans copier le fichier de V1. Un retrait enlève la version
des nouvelles propositions, sans supprimer le fichier des engagements existants.
Un fichier manquant ou altéré est signalé ; pas de régénération silencieuse.

Les versions antérieures à ce lot n'ont pas de PDF historique démontré. Ne pas
inventer un fichier ni sa date à la mise à jour. Prévoir pour le coordinateur une
action « Reconstituer le PDF historique », sur fiche ou sélection, de génération depuis le contenu déjà figé,
datée du jour et signalée comme reconstitution. Elle conserve tout fichier déjà
référencé et ne prétend pas reproduire une pièce ancienne envoyée au client.
Les pièces commerciales existantes restent intactes ; aucune reprise Odoo 19
réelle dans ce lot. Cette règle d'historique fait partie du choix PDF retenu.

## Droits et garde-fous proportionnés

Le coordinateur gère les catégories de sa société ; les lecteurs existants les
consultent dans leur périmètre. Archiver une catégorie utilisée plutôt que la
supprimer ; permettre de reclasser une formation sans réécrire ses programmes.
Aucun classement par défaut trompeur lors de la mise à jour.

Le PDF hérite du périmètre de la version, sans besoin client, aménagement S04,
participant, adresse personnelle ou donnée de vente. Protéger côté serveur
création, remplacement, suppression, rattachement et passage en public/jeton de
la pièce de référence ; masquer un bouton ne suffit pas. L'administrateur système
reste un rôle privilégié, aucune inviolabilité absolue n'est revendiquée.
Contrôler rapports HTML/PDF, téléchargements, exports et accès par identifiant
avec des profils restreints et plusieurs sociétés. Aucun droit portail/public
supplémentaire à ce stade. Si un `sudo()` ciblé est nécessaire au stockage,
le justifier après contrôle des droits métier ; aucun `sudo()` global sur le rendu.

## Recette à réaliser lors du développement

1. Créer/classer/retrouver une formation par texte, catégorie et modalité ;
   archiver/reclasser sans perdre l'historique ni exposer une autre société.
2. Refuser la validation incomplète ; valider une fiche complète et télécharger
   son PDF en une action. Vérifier le parcours sans catégorie des données anciennes.
3. Vérifier le vrai rendu PDF, les accents, tableaux longs, sauts de page et
   informations obligatoires ; contrôler clavier et lisibilité. Ne pas prétendre
   une conformité PDF/UA sur la seule présence de texte sélectionnable.
4. Conserver les mêmes octets V1 après création/publication de V2, changement de
   logo/gabarit/catégorie et mise à jour du module. La ligne de devis et la
   réalisation V1 doivent toujours ouvrir V1, même après retrait du catalogue.
5. Provoquer un échec de génération/stockage et une double validation concurrente :
   aucune validation sans fichier, aucun doublon, reprise possible sans ressaisie.
6. Refuser modification/suppression/détachement, partage public et accès croisés
   par ORM, export, rapport HTML/PDF, fichier et jeton, avec vrais profils restreints.
7. Installer sur base vierge, mettre à jour une base avec programmes historiques ;
   vérifier la reconstitution datée et l'absence d'envoi ou de remplacement implicite.

Ces critères sont des tests prévus. Les preuves des vérifications natives et,
ultérieurement, les résultats de recette restent dans la PR du lot.

La reprise S04 est testée directement avec et sans Website, sans précréation
de vues. Dans l’image Community vérifiée, le registre partiel de mise à jour ne
porte pas encore le défaut ORM `visibility` de Website lors de la création des
vues du socle. La migration fournit temporairement son défaut natif `public`
uniquement si la colonne requise existe sans défaut SQL. La phase native `post`
retire ce défaut avant validation de la transaction du module. Aucune valeur existante,
contrainte, permission ni source du cœur n’est modifiée. Un échec annule aussi
ce changement de schéma ; un défaut SQL préexistant est conservé.

Le préparateur historique S02 reste limité aux anciennes vues S03/S04. Il ne
prépare aucune vue catégories/PDF ; les 21 étapes historiques sont conservées.


## Navigation et contenu structuré

Le menu Formations regroupe les entrées par Catalogue, Organisation, Suivi
pédagogique, Qualité et Configuration ; le tableau de bord reste directement
accessible. Les groupes parents ne changent ni les habilitations des actions ni
les règles des enregistrements. Les examens blancs restent une intégration
optionnelle dans Suivi pédagogique.

Le contenu détaillé s’édite dans le champ HTML natif `content_formatted`, calculé
et inversé sur le stockage traduit `content` existant. Il n’existe qu’une source
de contenu. Les anciens textes conservent leurs sauts de ligne ; le HTML est
assaini côté serveur, y compris pour les anciens appels à l’API texte. Les titres,
listes et sous-listes sont rendus dans les fiches, les aperçus PDF et le catalogue
public d’une version explicitement publiée. Les programmes figés et leurs PDF
conservés restent immuables.

Recette : ouvrir un programme brouillon, saisir un titre et une liste imbriquée,
enregistrer et rouvrir ; vérifier l’aperçu PDF. Un lecteur ne peut pas modifier
le contenu et une version validée exige une nouvelle version pour toute retouche.
