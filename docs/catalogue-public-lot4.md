# Catalogue public — contenu et back-office (lot 4)

Suite des lots [1](catalogue-public-lot1.md), [2](catalogue-public-lot2.md) et
[3](catalogue-public-lot3.md).

## Formulaire de la formation

| Zone | Contenu |
| --- | --- |
| En-tête | Bouton **Aperçu de la fiche publique** (éditeurs du catalogue). Ruban « Publiée » quand la présentation générale est publiée. |
| Haut de fiche | Intitulé, catégorie, société ; case de publication et date de première publication (lecture seule). |
| Onglet **Site web** | Présentation générale (le premier paragraphe est l'accroche), objectifs, points forts, logo ; informations clés (référence, durée, niveau, certification) ; formations associées. Le module eLearning y ajoute les étiquettes publiques. |
| Onglet **Programme** | Programme public complet. |
| Onglet **Questions fréquentes** | Questions et réponses ordonnées. |

## Aperçu

`/formations/catalogue/<nom>-<id>?preview=1` affiche une formation de la société du
site même non publiée, uniquement pour un éditeur du catalogue connecté, avec un
bandeau d'aperçu et sans mise en cache. L'aperçu ne publie rien, n'ajoute pas la
formation au catalogue et ne propose pas de lien de devis tant qu'elle n'est pas
publiée. Les visiteurs, lecteurs et utilisateurs du portail obtiennent 404.

## Données

- Le complément des formations existantes (~140) relève du projet de migration.
- Site de dev : données fictives acceptées. Les données de recette [RECETTE DEV]
  ne sont pas destinées à la production.

## Recette courte

1. Ouvrir une formation non publiée, cliquer sur **Aperçu de la fiche publique** :
   bandeau d'aperçu, contenu complet.
2. Se déconnecter et ouvrir la même adresse : 404.
3. Publier : le ruban « Publiée » apparaît, l'aperçu n'a plus de bandeau.
