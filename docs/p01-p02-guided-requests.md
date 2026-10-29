# P01–P02 — parcours commerciaux et demande guidée

Références : #23, #24 et [matrice C02/C04](p01-p06-coverage.md).
L’accueil `/formations` privilégie « Former mon équipe », puis « Me former ».
Le catalogue, la fiche et le formulaire conservent le parcours et la version choisie.
Après le choix, le catalogue affiche le parcours retenu et propose de changer de
parcours. Sur la fiche, « Demander un devis individuel » ou « Demander un devis
pour mon équipe » annonce l’étape suivante sans faire choisir à nouveau l’intention.
Le formulaire garde ses champs lorsque le parcours change ; aucun compte,
contact, accès, inscription ou devis n’est créé automatiquement.

La demande étend `crm.lead` et réutilise l’accusé natif déjà livré en S10.
Le public renseigne catalogue/adaptation/sur mesure, objectifs, niveau, effectif,
pays, dates ou dates à discuter, modalité, outils et demande de conseil.
Pays, langue et devise sont indépendants. MAD et EUR peuvent être demandées
avant leur activation comptable ; le commercial configure ensuite le devis natif.
Une demande sur mesure doit être rattachée à un programme validé avant le devis.

La pièce facultative est un PDF privé de 10 Mo maximum. Les contrôles serveur
refusent type, taille et champs invalides. La création CRM et sa pièce sont
atomiques. L’erreur conserve les textes ; le navigateur impose de sélectionner
à nouveau le fichier. Les fichiers restent réservés aux lecteurs CRM autorisés,
y compris par lien direct ou ancien jeton ; partage public et copie interdits.

Un nonce aléatoire lié à la session et une contrainte SQL identifient la soumission.
Même contenu et même nonce retrouvent la demande ; un contenu différent demande
un nouveau formulaire. Le conflit concurrent est renvoyé au mécanisme natif de
reprise transactionnelle Odoo. CSRF reste actif. Aucun rattachement à une entreprise
ou habilitation n’est déduit du nom, du pays ou du domaine email saisi.

## Recette courte

1. Depuis chaque parcours, rechercher une formation et ouvrir sa fiche, puis le
   formulaire : vérifier version et parcours conservés. Changer de parcours dans
   le formulaire ; les valeurs restent présentes.
2. Envoyer une adaptation intra avec PDF, puis une demande sur mesure sans
   programme : retrouver les champs, pièce privée et journal d’accusé dans CRM.
   Configurer le programme et créer le devis natif MAD/EUR après qualification.
3. Omettre un champ obligatoire ou joindre un fichier interdit : erreur claire,
   aucune demande partielle et conservation des textes. Rechoisir le fichier.
4. Répéter une soumission identique : une demande et un accusé. Modifier le contenu
   d’un formulaire déjà envoyé : message explicite, sans écrasement de la demande.
5. Avec un visiteur, un portail ou un lecteur catalogue, essayer les URL du PDF et
   ses anciens jetons : refus. Avec un commercial de la bonne société : accès CRM.
   Vérifier l’absence de commande, inscription et accès pédagogique automatiques.
