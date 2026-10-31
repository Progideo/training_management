# S07 — Présences et émargement

Référence : [#17](https://github.com/Progideo/training_management/issues/17), PRE01–PRE03.

## Parcours

Le coordinateur configure la collecte papier, électronique ou mixte dans la séance
existante. La déclaration peut être régularisée sans date limite après la séance,
mais uniquement avant la clôture de la formation et avec les accès existants encore
valides. Aucun accès expiré, suspendu ou révoqué n’est rouvert. Le texte de
confirmation est configurable. Les anciennes séances ne reçoivent aucune présence inventée à la mise à jour.

Depuis « Mes formations », le participant authentifié confirme son statut présent ou absent par demi-journée
écoulée et accepte le texte affiché. Le [parcours par demi-journée](review-experience-performance.md)
définit le découpage, le regroupement des séances et la conservation des anciens intervalles. Le serveur conserve identité, séance, texte,
méthode et date réelle de déclaration. Une déclaration tardive conserve son
horodatage réel, sans antidatage ; les intervalles futurs ou hors séance sont refusés.
Un lien collectif ne porte aucun droit de signature. Les accès S03 doivent être
actifs ; suspension, révocation, expiration ou annulation empêchent une déclaration.
Un formulaire devenu périmé après modification du planning ou du texte est refusé :
le participant doit relire et confirmer les informations actualisées. L'empreinte
du formulaire détecte ce changement ; elle ne donne aucun droit d'accès.

Depuis ses séances affectées, le formateur contrôle les demi-journées écoulées, valide séparément et peut constater une absence sans déclaration.
Il ne valide ni sa propre présence ni une déclaration dont il est l'auteur.
Une absence papier reste cochée au contrôle. En cas d'erreur, le choix de présence et le
commentaire saisis sont conservés sur le seul formulaire concerné.
Le formateur affecté ou un coordinateur habilité peut invalider une déclaration
erronée avec un motif obligatoire. Une décision immuable conserve auteur, date,
état précédent et motif ; les minutes validées deviennent nulles sans supprimer
la déclaration ni les justificatifs. Une nouvelle déclaration puis une validation
distincte peuvent régulariser la présence. Les décisions périmées sont refusées.
La clôture de la formation bloque déclaration, validation et invalidation.

Le coordinateur importe un papier signé depuis la séance en indiquant la personne,
la demi-journée et la provenance ; ce dépôt attend le contrôle du formateur.
Un fichier collectif reste réservé aux coordinateurs de la société exploitante :
aucune diffusion aux autres participants ni au client.

Une ligne unique par inscription, séance et demi-journée porte la durée retenue. La dernière
validation, correction ou invalidation fait autorité : les sources ne s'additionnent jamais.
Une présence validée retient la durée prévue au planning ; une absence retient zéro.
Les anciens intervalles et retards restent historiques.
Une correction exige un motif et un justificatif, conserve avant/après, auteur,
date serveur et toutes les déclarations et pièces initiales. Aucun antidatage.
Les décisions périmées sont refusées avec demande de rechargement.

## Standard et sécurité

Vérification sur l'image Community `20.0-20261015` épinglée dans la CI :

| Standard vérifié | Usage / limite |
| --- | --- |
| `hr_attendance/models/hr_attendance.py` | Pointage et temps de travail d'un `hr.employee` ; imposer des employés aux stagiaires créerait un référentiel RH inadapté. |
| `event/models/event_registration.py` | Inscription et état de présence événement ; ne couvre pas les intervalles PRE01 et les déclarations/contrôles PRE02 par séance S04. |
| `portal`, `web`, ORM et QWeb | Authentification, formulaires CSRF, vues, assistants, règles de société et téléchargements natifs réutilisés. |
| `sign` | Absent de cette image Community ; aucune dépendance Enterprise ajoutée. |

Ajout ciblé dans le socle existant : ligne de présence et événements immuables,
sans autre application ni authentification. Pas de copie ou modification du cœur.
Les pièces sont des champs binaires natifs privés, sans pièces jointes publiques
ou jetons autonomes. Le contrôle natif de streaming et la politique documentaire
revérifient l'utilisateur réel ; pas d'envoi par messagerie. Les portails reçoivent
des valeurs explicitement sélectionnées, sans droits ORM généraux ni pièces collectives.
Le verrou et la révision S03 protègent les doubles déclarations et les suspensions
concurrentes ; la contrainte unique empêche un second compte de présence.
Les fichiers temporaires de l'assistant suivent la même politique, même avec
un jeton natif : créateur uniquement et société actuellement autorisée. Les règles
ORM de société et de propriétaire complètent ses droits de coordinateur ; les
preuves enregistrées restent accessibles aux coordinateurs autorisés de la société.
Le contrôle natif de société refuse un lien entre séance et inscription de
sociétés différentes, y compris dans un brouillon.

Le chargement des nouvelles vues sur une base équipée de Website réutilise le
pont de migration ciblé S05 : défaut de visibilité natif limité à la transaction,
puis restauration immédiate. Aucun changement de visibilité des vues existantes.

Ce dispositif constitue une déclaration et un contrôle interne. Aucune signature
dessinée ou certification juridique n'est ajoutée. L'asynchrone reste suivi par
les activités S05, sans séance fictive ; les attestations relèvent de S08.

## Recette courte

1. Créer une séance mixte de 120 minutes le matin et régler le texte.
2. Participant : confirmer la matinée présente, puis rejouer ; une déclaration, zéro minute
   validée avant le contrôle. Refuser accès d'un autre participant ou d'une autre société.
3. Formateur affecté : valider ; vérifier les 120 minutes prévues au planning. Tester
   absence, déclaration tardive, décision périmée et auto-validation.
   Invalider avec motif sous formateur puis coordinateur ; contrôler les historiques,
   le refus des autres profils et la nouvelle signature. Tester accès expiré et clôture.
4. Coordinateur : importer le papier de la même personne ; aucun cumul.
   Corriger avec justificatif ; vérifier les anciens fichiers et le journal inchangés.
5. Vérifier formulaire mobile, parcours clavier, CSRF, liens directs et jetons,
   refus des pièces collectives aux profils portail/commercial et hors société.
   Tester aussi un brouillon d'import avec jeton, un autre coordinateur et un
   retrait d'habilitation ; modifier le texte/planning après affichage, puis confirmer.
6. Exécuter `tests/ci/run_s07.sh` : S06 vers S07, historiques catalogue/documents/
   apprentissage/Survey, tests du socle et intégrations, installation vierge,
   deuxième mise à jour avec présences et deux transactions concurrentes.

Les résultats réellement exécutés sont consignés dans la PR et ses artefacts CI.

Contrôle C06 ciblé (droits, HTTP, mise à jour et concurrence) :
`python3 tests/ci/run_attendance_policy.py`.
