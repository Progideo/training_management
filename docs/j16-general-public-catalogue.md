# J16 — Catalogue commun, présentation générale

Le cadrage validé du 3 novembre remplace l’ancien aperçu P03/P04 : avant achat,
seuls présentation générale, objectifs, public, prérequis, durée indicative et
conditions commerciales peuvent être publics. Ressources, questions et
démonstrations restent privées. Décision du 19 novembre 2026 : le programme est
public, y compris le PDF de référence de chaque version publiée au catalogue.

`training_catalog` fournit `/formations` et les fiches générales. Une même identité
regroupe les offres TM et autonomes, sans copier de programme ni créer de droit
pédagogique. Les extensions fournissent seulement une projection de champs autorisés.
La recherche porte sur ces données générales, jamais sur les contenus privés.
La grille affiche jusqu’à douze fiches par page et conserve la recherche, la
catégorie et la modalité dans les liens de pagination.
Le site courant natif Odoo 20 (`env.website`) fixe la société exploitante.
La présentation générale et les étiquettes appartiennent à la fiche commune.
Les étiquettes s’affichent sous le résumé, dans la grille et sur la fiche. Le catalogue seul affiche la catégorie. Quand
eLearning est installé, le champ « Étiquettes publiques » permet de sélectionner
les étiquettes natives et reprend leur libellé traduit et leur couleur. Les
étiquettes sans couleur restent internes selon la règle native d’Odoo.

Une fiche générale peut être publiée par l’éditeur catalogue. Les programmes TM
explicitement publiés au catalogue conservent leur présentation générale et leurs
liens vers devis, sessions, avis et orientation. Un cours autonome requiert une
publication générale distincte de sa publication pédagogique ; ses descriptions,
activités et pages natives restent privées. Ses conditions publiques sont explicites,
sans publier les prix négociés ni les contrats individuels.
La fiche et le catalogue affichent la dernière version publiée avec formateur et
la dernière version eLearning. Une version avec formateur a une modalité principale
et peut déclarer d’autres modalités possibles (présentiel, distanciel, mixte) ;
chaque session fixe la sienne par ses séances. Toutes les modalités déclarées
restent visibles et filtrables. Une version eLearning n’est présentée ni « avec
formateur » ni « sur devis ».
Depuis le lot 3, une version n’a plus de page propre : `/formations/<version>`
redirige (301) vers la fiche commune, à l’adresse unique
`/formations/catalogue/<nom>-<id>`, qui présente la version choisie (voir
[catalogue-public-lot3.md](catalogue-public-lot3.md)).

`/formations/<version>/pdf` rend, tel que conservé à la validation, le PDF de
référence d’une version publiée au catalogue ; la pièce jointe reste privée et une
version retirée renvoie 404. La route d’extrait renvoie 404 et le formulaire de
mini-quiz public est retiré. Les téléchargements privés autorisés sont conservés. Les choix « équipe » et
« individuel » restent transmis entre catalogue et fiche commune.

## Recette courte

1. Catalogue seul : publier une fiche, rechercher sa présentation, puis retirer
   ou archiver ; contrôler les refus entre sociétés et domaines Website.
2. Publier une offre TM et un cours autonome pour la même formation : une fiche,
   deux modes, aucun accès pédagogique créé par consultation.
3. Télécharger le PDF d’une version publiée : mêmes octets que le PDF conservé.
   Appeler directement l’extrait, la pièce jointe, une version privée ou retirée,
   un cours et une leçon : aucun contenu privé disponible avant achat.
4. Rejouer demandes de devis, orientation, sessions et avis ; vérifier la conservation
   du contexte et le téléchargement du programme par un participant autorisé.

## Avis sur la fiche commune

Un participant connecté peut déposer une note et un commentaire par formation, avec son accord de publication. Une session avec formateur doit être terminée et comporter une présence positive validée. Le cours autonome doit comporter des activités obligatoires et l’apprenant doit les avoir terminées. Les deux parcours utilisent le même avis sur la fiche commune.

Odoo conserve la note et le commentaire dans ses avis natifs. Le menu **Site Web → Configuration → Avis sur les formations** permet au responsable du site de publier ou de retirer un avis dans ses sociétés. La participation est contrôlée à nouveau avant publication et la dernière décision conserve son auteur et sa date. La fiche publique affiche uniquement la note et le commentaire validés.

L’option **Responsable des avis formation** de la fiche Société désigne un responsable habilité à modérer les avis. Un dépôt planifie l’activité Odoo **Avis formation à valider**, liée à l’avis. La validation et le refus clôturent l’activité. Sans responsable configuré, l’avis reste disponible dans la liste de modération.

## Demandes d’inscription sur la fiche commune

Les dates inter-entreprises ouvertes s’affichent dans l’onglet Inter de la fiche, à cocher, en heure locale de
la session et sans décalage UTC ; la modalité est celle des séances planifiées,
dont le lieu reste privé. Le visiteur peut
demander de une à cinq places, dans la limite des places disponibles. Odoo CRM
conserve la session choisie, la version du programme et le nombre de participants.
L’équipe confirme ensuite l’inscription. Les demandes de devis suivent leur
parcours habituel.

Pour la recette, publier une session future sur une offre visible, demander une
place puis plusieurs places et vérifier les deux demandes dans le CRM. Remplir
ou fermer la session, puis vérifier que le lien ne permet plus de soumettre
une demande.


### Confirmation depuis la piste CRM

Le coordinateur ouvre **Confirmer les places de la session** sur la piste.
La fenêtre présente la session et une ligne par participant. Les contacts se
sélectionnent ou se créent avec le sélecteur natif Odoo. Le nombre de personnes
doit correspondre à la demande.

L’origine des places est une ligne de commande confirmée, un lot confirmé
existant pour cette session ou une invitation gratuite avec son motif.
Le coordinateur atteste avoir vérifié les prérequis et saisit le motif de
validation. **Confirmer toutes les places** enregistre le groupe en une seule
transaction. Odoo vérifie les droits, les contacts distincts, les dates et la
capacité. Un échec annule toute l’opération et un nouvel envoi conserve les
inscriptions déjà créées.

Le bouton **Participants à la session** permet ensuite d’ouvrir les inscriptions.
L’autorisation commerciale et l’ouverture des accès suivent le parcours existant.

Pour la recette, traiter une demande individuelle puis une demande de trois
personnes. Vérifier les trois origines des places, rejouer la confirmation,
puis essayer une session complète et un compte commercial sans rôle coordinateur.


### Emails de confirmation

La confirmation CRM prépare les courriers avec un modèle natif Odoo, dans la
file d’envoi standard. Le demandeur et chaque participant doivent avoir une
adresse valide, modifiable pour les participants dans la même fenêtre.
Une adresse partagée reçoit un seul message par demande, y compris lorsque
le demandeur participe. Une répétition conserve le courrier initial.

Les messages indiquent la formation, les dates, horaires, fuseau et modalité.
Les lieux et liens de visioconférence proviennent des créneaux actifs du planning.
Les informations pratiques manquantes sont annoncées comme restant à communiquer.
Chaque participant reçoit uniquement les noms des personnes partageant son
adresse. Les messages utilisent l’identité d’expédition configurée pour la société.

Le bouton **Emails de confirmation** sur la piste affiche les destinataires,
les informations préparées et l’état natif du courrier. Le modèle se modifie
dans les modèles d’email Odoo. Une erreur de préparation annule toute la confirmation.
Le transport revérifie les destinataires, les inscriptions, les dates et le
planning avant envoi. Les mises à jour de planning utilisent ensuite les
invitations existantes.

La recette couvre une personne également demandeuse, trois participants,
une adresse manquante, une panne de préparation, une répétition après envoi,
un changement de destinataire ou de planning et les accès restreints.
