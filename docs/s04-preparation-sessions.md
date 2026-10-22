# S04 — Besoins, aménagements et séances

Référence : [#14](https://github.com/Progideo/training_management/issues/14), ORG01–ORG02,
SEC01–SEC02, NOT01 et UX01. Ce cadrage reprend les simplifications et les trois choix
validés dans la conversation S04. Catégories et PDF CAT01 sont un lot distinct,
conformément au report S03.1 ; ils ne sont pas livrés ici.

## Parcours et décisions

Une fiche de réalisation : besoin commun, participants, séances et diffusion.
Ajouter les séances, éventuellement en série ; confirmer la réalisation pour
contrôler et réserver les ressources ; vérifier les destinataires et envoyer.
Aucun état supplémentaire de validation du planning, aucun envoi à la confirmation.
Le coordinateur peut saisir les informations recueillies par courriel/téléphone :
aucune démarche supplémentaire obligatoire du client.

Objectifs, positionnement et synthèse utile au formateur sont portés par
l'inscription existante. Ils ne changent pas la décision de prérequis, la version
contractuelle ou les accès S03. Les dossiers d'aménagement sont distincts et privés :
un référent coordinateur par réalisation, avec suppléant facultatif. Le référent
courant ou son suppléant gère les changements d'habilitation dès qu'un dossier existe.
Les décisions et changements conservent auteur, date serveur et avant/après dans
un historique restreint ; les exports du dossier et de son historique sont tracés,
y compris depuis un export relationnel de la réalisation. Aucun détail dans le
journal général, le chatter, les activités ou les convocations. Qualité et commercial
n'obtiennent aucun accès sensible automatiquement.

Le formateur externe utilise le portail Odoo en lecture seule : ses séances
confirmées/en cours, les participants confirmés, la synthèse de positionnement et
la seule consigne utile. Une réaffectation retire l'accès immédiatement. Pas de
compte interne imposé ni seconde authentification. Le portail ne donne aucun droit
ORM général aux dossiers S03/S04. La liste paginée ouvre sur les séances à venir ;
les séances passées et la liste complète restent accessibles. Les écrans
participant/entreprise restent S05/P05.

## Planning et ressources

Identités des formateurs : contacts `res.partner`. Salles : ressources matérielles
`resource.resource` d'une seule société, capacité facultative. Équipements : texte
simple. Aucun sous-groupe, réservation détaillée de matériel, synchronisation
d'agenda extérieur ou partage de ressources entre sociétés.

Une séance porte dates/heures locales et fuseau de référence de la réalisation ;
les instants UTC sont calculés côté serveur. Une heure inexistante est refusée ;
une heure ambiguë exige le choix de la première/deuxième occurrence. Les invitations
utilisent le fuseau du contact, ou explicitement le fuseau de référence s'il manque.
Le fuseau de référence, la société, le programme et la nature sont conservés après
création des séances.

Présentiel : lieu/salle ; distanciel : lien HTTPS ; mixte : les deux. Une offre
autonome n'a pas de séance fictive. Une réalisation datée doit avoir ses séances
complètes pour être confirmée. Les séances restent dans les dates de réalisation ;
modifier celles-ci ne déplace pas automatiquement les séances ni les périodes d'accès.

Un formateur ou une salle ne peut pas être réservé sur deux intervalles qui se
chevauchent ; deux séances jointives sont possibles. Le contrôle inclut les
réservations S04 et les indisponibilités signalées. Un conflit exige une dérogation
motivée du coordinateur et conservée au journal. Le verrou et une révision par société
protègent les confirmations concurrentes, y compris un instantané de transaction périmé.
Les engagements extérieurs non signalés ne peuvent pas être détectés.

L'indisponibilité contient une ressource et une période, sans détail du rendez-vous.
Si une séance déjà confirmée existe, la déplacer d'abord, puis enregistrer
l'indisponibilité ; une confirmation ultérieure peut faire l'objet d'une dérogation.
La capacité de salle ne peut pas être inférieure à l'effectif engagé S03, places
non nominatives comprises. La nomination ne compte pas une deuxième fois.

Après confirmation, l'assistant de modification collecte le motif, revérifie les
réservations et propose les destinataires du changement. Ajouter/annuler une séance
préserve son historique. Aucune modification après le début de la réalisation.
Les réalisations historiques ne reçoivent aucune séance inventée à la mise à jour.
Le motif d'une modification n'autorise pas une dérogation de ressource. Si un conflit
apparaît, le même assistant conserve les saisies, décrit ressource et période et
demande un motif de dérogation distinct. Sans conflit, aucune étape supplémentaire.

## Convocations et limites de messagerie

Une action volontaire du coordinateur met un courriel individuel par personne et
séance dans la file native Odoo. Destinataires : participants confirmés et formateurs
affectés, sélection vérifiée côté serveur. Répéter la dernière demande ne crée pas de
doublon ; chaque changement successif, y compris un retour à un ancien horaire,
produit une nouvelle convocation après action explicite. Chaque diffusion est
numérotée par séance et destinataire ; une mise à jour conserve les anciens messages.
Les erreurs de distribution restent visibles ; une reprise utilise le même message.
Le transport revérifie la dernière diffusion, le destinataire et l'empreinte du planning avant tout envoi,
y compris lors d'une reprise. Aucun détail d'aménagement n'entre dans ces courriels.

La dette [#50](https://github.com/Progideo/training_management/issues/50) sur les circuits
commerciaux reste ouverte et obligatoire avant S05/P05 et toute production. S04 ne
modifie pas leurs règles : son contrôle de transport est limité à `training.session`.
Les fichiers d'aménagement conservent l'habilitation au parent même avec un jeton,
via les points natifs de contrôle/streaming ; ils ne peuvent pas devenir publics.

## Couverture native vérifiée

Image : celle épinglée dans `.github/workflows/odoo.yml`, Community `20.0-20261015`.
Lecture du code exact, sans déduire une capacité Enterprise :

| Standard | Réutilisation / écart |
| --- | --- |
| `base/models/res_partner.py` | Contacts, identité, langues et fuseaux ; aucun référentiel concurrent. |
| `resource/models/resource_resource.py`, sécurité `ir.access.csv` | Ressources humaines/matérielles, société et calendrier ; ajout ciblé salle/capacité, sans dépendance RH ou Planning. |
| `calendar/models/calendar_event.py`, `calendar_attendee.py` | Détection d'indisponibilité, invitations et ICS présents ; création/modification peut envoyer des invitations. Ne démontre pas la réservation concurrente requise. S04 utilise une vue calendrier native de ses séances, sans créer d'événement envoyant automatiquement. |
| `portal/controllers/portal.py` | Authentification et layout natifs ; projection explicite des seules données du formateur affecté. |
| `base/models/ir_attachment.py` | Accès parent natif, mais jeton accepté sans contrôle du parent dans `_can_return_content` : héritage ciblé de ce point et de `_to_http_stream`, tests ORM/HTTP associés. |
| `mail/models/mail_mail.py` | File et états de distribution ; contrôle S04 au dernier point de préparation du transport. |
| `base/models/ir_actions_report.py` | Rapports QWeb disponibles ; aucun rapport ni PDF ajouté par ce lot. |

Le socle dépend désormais de `resource` et `portal` (LGPL-3 dans l'image exacte),
en complément de `base`/`mail`. Pas de cœur modifié ni nouvel addon/service.

Sur une ancienne base équipée de Website, le défaut obligatoire de visibilité des
nouvelles vues peut manquer pendant le chargement de mise à jour. L'amorçage natif
déjà décrit dans [S03](s03-enrollment-access.md#sécurité-et-concurrence) et reproduit
par `tests/probes/s03_view_bootstrap.py` inclut désormais les vues S04. Les charger
avec le registre installé complet avant la mise à jour ; aucune valeur SQL par
défaut, contrainte ou source standard n'est modifiée. Cette procédure sera à
inclure dans une éventuelle recette de déploiement, qui reste hors de cette PR.

## Recette courte

1. Coordinateur restreint : renseigner un besoin et un positionnement sans changer
   prérequis/accès ; créer plusieurs séances en une action et confirmer une fois.
2. Référent : saisir un aménagement et sa consigne ; vérifier refus pour commercial,
   autre coordinateur et participant, y compris API/export/fichier avec jeton.
   Exporter aussi depuis la réalisation et l'historique ; vérifier le manifeste privé.
3. Formateur portail : lire uniquement ses affectations, participants nécessaires
   et consignes ; vérifier absence de détails, refus d'écriture et perte d'accès
   après réaffectation, ainsi que clavier et mobile. Parcourir plus de 200 séances,
   avec les filtres à venir/passées/toutes conservés lors de la pagination.
4. Confirmer deux créneaux concurrents : une réservation ordinaire réussit ; refus
   de la seconde, puis dérogation motivée. Refaire avec une indisponibilité et une salle.
5. Tester heure ambiguë/inexistante, plusieurs fuseaux et capacité de salle face
   aux places non nominatives. Déplacer une séance avec motif ; aucun envoi implicite.
   Un nouveau conflit exige une dérogation distincte, sans ressaisir le déplacement.
6. Vérifier les destinataires, envoyer vers un transport de test ; rejouer sans
   doublon, modifier puis renvoyer, revenir à l'ancien horaire et renvoyer ; vérifier
   erreur/reprise et refus d'un ancien message même si son horaire redevient actuel.
7. Installation vierge, mise à jour depuis S03.1 et comparaison des historiques :
   scénarios CI existants et `tests/ci/run_s04.sh`. Données fictives uniquement,
   environnements jetables et nettoyage. Résultats réels dans la PR et ses artefacts.
