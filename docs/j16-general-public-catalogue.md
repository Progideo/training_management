# J16 — Catalogue commun, présentation générale

Le cadrage validé du 3 novembre remplace l’ancien aperçu P03/P04 : avant achat,
seuls présentation générale, objectifs, public, prérequis, durée indicative et
conditions commerciales peuvent être publics. Programme détaillé, ressources,
questions et démonstrations restent privés.

`training_catalog` fournit `/formations` et les fiches générales. Une même identité
regroupe les offres TM et autonomes, sans copier de programme ni créer de droit
pédagogique. Les extensions fournissent seulement une projection de champs autorisés.
La recherche porte sur ces données générales, jamais sur les contenus privés.
La grille affiche jusqu’à douze fiches par page et conserve la recherche, la
catégorie et la modalité dans les liens de pagination.
Le site courant natif Odoo 20 (`env.website`) fixe la société exploitante.
La présentation générale et les étiquettes appartiennent à la fiche commune.
Les étiquettes s’affichent sous le résumé, dans la grille et sur les pages de
la fiche et du programme. Le catalogue seul affiche la catégorie. Quand
eLearning est installé, le champ « Étiquettes publiques » permet de sélectionner
les étiquettes natives et reprend leur libellé traduit et leur couleur. Les
étiquettes sans couleur restent internes selon la règle native d’Odoo.

Une fiche générale peut être publiée par l’éditeur catalogue. Les programmes TM
explicitement publiés au catalogue conservent leur présentation générale et leurs
liens vers devis, sessions, avis et orientation. Un cours autonome requiert une
publication générale distincte de sa publication pédagogique ; ses descriptions,
activités et pages natives restent privées. Ses conditions publiques sont explicites,
sans publier les prix négociés ni les contrats individuels.

Les anciennes routes publiques PDF/extrait renvoient 404 et le formulaire de
mini-quiz public est retiré. Les octets existants, la génération des programmes PDF
et les téléchargements privés autorisés sont conservés. Les choix « équipe » et
« individuel » restent transmis entre catalogue, fiche commune et offre TM.

## Recette courte

1. Catalogue seul : publier une fiche, rechercher sa présentation, puis retirer
   ou archiver ; contrôler les refus entre sociétés et domaines Website.
2. Publier une offre TM et un cours autonome pour la même formation : une fiche,
   deux modes, aucun accès pédagogique créé par consultation.
3. Rechercher un texte privé et appeler directement PDF, extrait, cours et leçon :
   aucun contenu privé disponible avant achat.
4. Rejouer demandes de devis, orientation, sessions et avis ; vérifier la conservation
   du contexte et le téléchargement du programme par un participant autorisé.

## Avis sur la fiche commune

Un participant connecté peut déposer une note et un commentaire par formation, avec son accord de publication. Une session avec formateur doit être terminée et comporter une présence positive validée. Le cours autonome doit comporter des activités obligatoires et l’apprenant doit les avoir terminées. Les deux parcours utilisent le même avis sur la fiche commune.

Odoo conserve la note et le commentaire dans ses avis natifs. Le menu **Site Web → Configuration → Avis sur les formations** permet au responsable du site de publier ou de retirer un avis dans ses sociétés. La participation est contrôlée à nouveau avant publication et la dernière décision conserve son auteur et sa date. La fiche publique affiche uniquement la note et le commentaire validés.

L’option **Responsable des avis formation** de la fiche Société désigne un responsable habilité à modérer les avis. Un dépôt planifie l’activité Odoo **Avis formation à valider**, liée à l’avis. La validation et le refus clôturent l’activité. Sans responsable configuré, l’avis reste disponible dans la liste de modération.
