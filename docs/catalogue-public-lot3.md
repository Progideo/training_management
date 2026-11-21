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
| Modalités possibles | Décision du 19 novembre 2026 : une version avec formateur garde sa modalité principale (qui préremplit les séances) et déclare ses autres modalités possibles (« Également en présentiel / distanciel / mixte »). Le catalogue retient la dernière version avec formateur et la dernière version eLearning ; la fiche, le PDF et la page des dates affichent par exemple « Présentiel ou distanciel » ; les filtres de modalité et « Distanciel possible » suivent les modalités déclarées ; le lieu du comparatif s'y adapte. Une version eLearning n'a pas d'autre modalité. Les versions existantes gardent leur seule modalité (nouvelles colonnes vides) ; les versions validées restant figées, une modalité s'ajoute par une nouvelle version. |
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

## Présentation alignée sur la maquette (20 novembre 2026)

Sans changement du serveur ni du modèle de données, la fiche reprend la maquette
« Fiche formation – versions (desktop) » : bandeau sombre avec badges (Nouveau,
domaine, « Niveau … », certifiante), filet d'accent sous le titre et sous chaque
titre de section, chiffres clés en ligne ; sommaire en gras souligné au survol ;
comparatif « Trois façons de suivre cette formation » à sa place (après les
modalités, avant les questions fréquentes, décision du 20 novembre), colonne du format choisi mise en avant et bouton par format
(`?format=` ouvre l'onglet de la carte de réservation) ; objectifs en liste à
coches quand ils sont saisis un par ligne ; points forts en tuiles (« Titre :
texte ») ; programme par blocs encadrés ; public et prérequis en deux colonnes ;
modalités en liste de définitions ; questions fréquentes en accordéon ;
formations associées en cartes. Carte de réservation : onglets courts (Inter,
Intra, Autonomie), accroche du format, prix en grand, note de prix, liste à
coches, sessions avec places restantes, bouton principal pleine largeur et
bouton secondaire. Barre mobile : prix et action du premier format.

## Retours du 20 novembre 2026 (après déploiement)

- Liste « Offres disponibles » supprimée (doublon de la carte de réservation) : la
  ligne de version des modalités donne la référence et l'intitulé de la version
  présentée ; l'onglet Autonomie donne l'intitulé et les conditions publiques de
  l'offre eLearning.
- Couleurs : Odoo compile Bootstrap sans ses variables CSS (`--bs-primary`,
  `--bs-warning`… sont vides sur le site) ; la feuille de style passe par les
  variables Sass du thème (`$primary`, `$warning`, `$success`) et la palette du site
  (`--o-color-1..3`). Les filets d'accent, la colonne choisie du comparatif, le
  contour de focus et le contraste du texte secondaire (lot 5) s'affichent désormais.
- Comparatif : titre de la colonne choisie lisible ; la colonne mise en avant suit l'onglet choisi dans la carte de
  réservation, et les boutons du comparatif ouvrent l'onglet sans recharger la page
  (`static/src/course_page.js` ; sans JavaScript, `?format=` recharge la page).
- Partage : bloc « Partager cette formation » sous la présentation, avec le lien
  de la fiche à copier et des liens vers LinkedIn, Facebook, X, WhatsApp et
  l'e-mail (adresses construites dans le navigateur).
- Prix inter : un tarif fixe s'affiche dès qu'un produit de formation de la
  formation est coché « Tarif inter-entreprises public » (vendu par personne).

## Retours du 21 novembre 2026

- Partage replié par défaut : lien discret « Partager cette formation » sous la
  présentation, qui ouvre le lien à copier et les réseaux. Les icônes sont dessinées
  en SVG dans le composant (le site n'a pas de police d'icônes de marques).
- Modalités : la ligne de version (référence, intitulé, modalité, durée) est
  supprimée ; la section n'apparaît que si la version a des modalités publiées.
