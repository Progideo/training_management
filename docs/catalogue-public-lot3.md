# Catalogue public — page formation (lot 3)

Refonte de la fiche commune à partir des données du [lot 1](catalogue-public-lot1.md),
après la page catalogue du [lot 2](catalogue-public-lot2.md).

## Décisions

| Sujet | Règle |
| --- | --- |
| Adresse | Une seule adresse publique par formation : `/formations/catalogue/<nom>-<id>`. L'identifiant seul et un ancien nom redirigent (301) en gardant les paramètres. `/formations/<version>` redirige (301) vers la fiche ; une dernière version publiée de sa modalité est sélectionnée par `?version=`. Les adresses `/pdf`, `/sessions`, `/date-alert` et `/avis` d'une version sont conservées. |
| Bandeau | Fil d'Ariane, badges (Nouveau, domaine, niveau, certifiante), titre, accroche (premier paragraphe de la présentation), chiffres clés : durée en jours et en heures, formats, validation, référence. |
| Sommaire | Liens d'ancre fixés en haut au défilement, limités aux sections affichées. |
| Carte de réservation | Fixe à droite sur ordinateur, un onglet par format disponible, `?format=` choisit l'onglet. Inter : prix HT par participant ou « Sur devis », sessions à cocher (dates, horaires, lieu public, places, « Session confirmée »), « S'inscrire » vers la demande de la session ; sans session, « Être alerté des nouvelles dates ». Intra : « Sur devis », « Demander un devis pour mon équipe », « Besoin d'une autre durée ? Demande sur mesure ». Autonomie : prix HT, durée du contenu, activités, durée d'accès, lien de l'offre (fiche produit en boutique) ou devis individuel. |
| Sections | Présentation et points forts, objectifs, programme complet et PDF, public et prérequis, modalités (accessibilité, résultats attendus, accès aux supports, prestations, examen officiel, offres disponibles), comparatif des formats (à partir de deux formats), FAQ, formations associées, avis (masqués si vides). |
| Version présentée | La version choisie par `?version=`, sinon la dernière version avec formateur publiée, sinon la version eLearning. Le contenu détaillé de la version n'est jamais affiché ; le programme est celui de la fiche commune. |
| Mobile | Onglets empilés en cartes ; barre fixe en bas : prix et « S'inscrire » (ou « Voir les formats ») vers la carte de réservation. |
| Données structurées | schema.org `Course` (nom, accroche, adresse, organisme, référence, niveau, durée `timeRequired`, tarif inter `Offer`) et `CourseInstance` par session ouverte (mode, dates UTC, lieu public). |

Les anciennes pages de version (modèles `training_management.public_programme` et
leurs extensions) sont supprimées par la mise à jour des modules.

## Limites

- « Ajouter au panier » n'est pas direct : le bouton de l'offre autonome ouvre la
  fiche produit de la boutique, où l'achat se fait.
- La balise `link rel="canonical"` reste celle du module Website.

## Recette courte

1. Ouvrir `/formations/catalogue/<id>` et une ancienne page `/formations/<version>` :
   redirection vers l'adresse avec le nom, onglet et version conservés.
2. Formation avec versions présentielle, distancielle et eLearning, une session
   publiée et un tarif inter : trois onglets, session cochée, « S'inscrire »
   ouvre la demande ; comparatif après les modalités, avant la FAQ.
3. Sans session : « Être alerté des nouvelles dates » dans l'onglet Inter.
4. Mobile : barre fixe, onglets lisibles, ancres du sommaire.
5. Vérifier les données structurées avec l'outil de test des résultats enrichis.
