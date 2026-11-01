# S07 — Tableau des présences et signatures personnelles

Référence : [#111](https://github.com/Progideo/training_management/issues/111),
PRE01–PRE03 et UX01. Complète [S07](s07-attendance.md).

## Utilisation

1. Depuis « Mes formations », ouvrir « Ma signature ». Dessiner sa signature
   ou charger un dessin PNG, cocher l'accord personnel et enregistrer.
   Le formateur enregistre sa propre signature depuis son espace de contrôle.
2. Participant : ouvrir la formation puis « Mes présences ». Dans la cellule
   du jour et de la demi-journée, développer les séances et actions, puis ouvrir
   la déclaration. Vérifier les horaires, choisir présent ou absent, accepter
   le texte et cliquer sur « Signer cette demi-journée ».
3. Formateur : ouvrir le contrôle de sa séance affectée, examiner la déclaration,
   choisir la décision, accepter le texte puis cliquer sur « Signer et valider ».
   Le tableau collectif est accessible depuis le suivi de la réalisation ou
   depuis le contrôle d'une séance. Le superviseur le consulte sans valider.

La signature enregistrée évite de redessiner à chaque fois ; chaque déclaration
et chaque contrôle nécessitent toujours leur propre confirmation. Après un
remplacement ou une suppression, recharger les formulaires déjà ouverts.
Sur petit écran, faire défiler le tableau horizontalement ; au clavier, placer
le focus sur sa zone de défilement et utiliser les flèches.

## Tableaux

Le participant voit une ligne par jour et deux colonnes matin/après-midi.
Le tableau collectif, accessible depuis le suivi de la réalisation, présente
une ligne par participant et les demi-journées regroupées par date. Il propose
les filtres jour/semaine/tous les jours et les compteurs du périmètre affiché.
La page de contrôle par séance conserve ses actions et renvoie au tableau collectif.

Chaque cellule contient une pastille, un libellé, les minutes validées et les
signatures des déclarations actives du participant. La signature apparaît dès
sa déclaration, avant contrôle formateur. Elle ne prouve pas la validation finale.
Les détails donnent les séances, horaires, fuseaux et accès aux actions autorisées.
Les signatures identiques sont affichées une fois par cellule ; chaque événement
conserve sa propre copie. Une invalidation retire la déclaration de l'affichage
actif sans supprimer la preuve historique.

Le statut agrège les parties : futur, non planifié, à signer, papier attendu,
déclaration reçue/contrôle attendu, validation partielle x/y, présence ou absence
validée, présence mixte contrôlée, invalidation ou anomalie. Une absence de
déclaration ne devient jamais une absence validée. Les séances historiques
à intervalles restent séparées. Les durées et le découpage du planning restent
ceux du [parcours par demi-journée](review-experience-performance.md).

| Pastille | Lecture du statut |
| --- | --- |
| Verte | Présence validée par le formateur. |
| Orange | Déclaration en attente de contrôle, validation partielle ou présences et absences mélangées après contrôle de toutes les séances. Lire le libellé et le détail. |
| Rouge | Absence validée, déclaration invalidée ou anomalie à examiner. Le libellé distingue ces situations. |
| Grise | Demi-journée à venir, à signer ou papier attendu. |
| Contour vide | Aucune séance planifiée. |

La couleur complète toujours un libellé. Une signature visible avec une pastille
orange correspond à une déclaration reçue, pas encore à une présence validée.

Le superviseur consulte uniquement les réalisations affectées ; il ne reçoit
aucune action de validation par ce rôle. Chaque formateur voit ses séances et
valide uniquement celles qui lui sont affectées. Les droits cumulés restent possibles.

## Signature et preuve

« Ma signature » permet de dessiner puis confirmer une signature personnelle,
ou de charger un dessin PNG pour l'accessibilité. Le composant natif
`web.NameAndSignature`, présent dans l'image Community `20.0-20261015` épinglée
dans la CI, est réutilisé en mode dessin. Aucune dépendance Enterprise.

Le dessin est privé et remplaçable/supprimable pour les usages futurs. Sa
suppression ne supprime pas les copies déjà utilisées dans des preuves.
Chaque déclaration ou contrôle affiche le contexte et le dessin courant ;
le bouton « Signer cette demi-journée » ou « Signer et valider » exige une
action personnelle. L'absence utilise un engagement adapté. Un formateur peut
constater une absence sans fabriquer de signature du participant.

Chaque événement signé conserve dessin normalisé PNG, version, empreinte,
compte auteur, date serveur, texte, statut et liens séance/inscription/période.
Le contrôle formateur reste distinct, sans auto-validation. Les signatures
personnelles n'ont aucun droit ORM public ; seuls les services privés accèdent
au profil du compte connecté. Les images d'événements revérifient l'accès
participant ou l'affectation du personnel à chaque requête, sans cache public
ni jeton autonome. Le téléchargement binaire natif des dessins est refusé.

Le serveur refuse signature périmée/absente, futur, accès retirés, clôture,
texte/planning périmé et double décision. Le verrou de la réalisation précède
celui du compte signataire ; l'édition du dessin verrouille seulement le compte.
Les corrections et pièces papier suivent toujours les règles S07 existantes.

Ce dessin complète la preuve de déclaration et de contrôle interne. Il ne
constitue aucune revendication de signature qualifiée ou certifiée.

## Mise à jour et recette courte

La mise à jour ajoute un profil privé et des champs facultatifs aux événements.
Elle ne crée aucune signature pour les anciennes déclarations ou pièces papier.
Les attestations et minutes existantes restent calculées sur les décisions S07.

1. Avec des comptes sans signature préenregistrée, enregistrer un premier dessin
   pour un participant et un formateur et vérifier sa conservation après rechargement ; signer une matinée
   présente et une après-midi absente. Vérifier pastille et dessin avant contrôle.
2. Contrôler les parties avec deux formateurs ; vérifier x/y puis état final,
   minutes, détail et refus hors affectation ou auto-validation.
3. Remplacer/supprimer le dessin ; vérifier anciennes preuves inchangées et
   refus d'un ancien formulaire. Invalider puis régulariser sans antidatage.
4. Vérifier accès pair/client/autre société, superviseur en lecture, retrait
   d'affectation, suspension et liens directs vers les images sans cache public.
5. Vérifier mobile, tactile, clavier, chargement PNG alternatif, double clic,
   changement planning/texte, concurrence et clôture.
6. Installer sur base vierge puis mettre à jour une base avec historiques ;
   rapprocher les minutes et attestations. Les résultats restent dans la PR.

Pour la recette tactile, utiliser un téléphone ou une tablette physique : tracer,
enregistrer, signer une demi-journée, puis recharger et vérifier dessin et statut.
Une largeur mobile simulée ne démontre pas le tracé au doigt. Consigner appareil,
navigateur et résultat dans la PR, sans données personnelles réelles.
