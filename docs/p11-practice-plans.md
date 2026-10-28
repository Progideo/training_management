# P11 — Plan de mise en pratique

Référence : [#34](https://github.com/Progideo/training_management/issues/34),
chapitre 21 / P11, EVA02 et PED02 de la spécification v2. Socle Community
`20.0-20261015`, sans dépendance nouvelle. P12 reste hors périmètre.

## Couverture et choix

Lecture de l’image épinglée `61e3c71b0503`, code Community `49529f034a60` :
`mail/models/mail_activity.py` porte une échéance civile, un utilisateur et une
activité terminée/archivée, sans contrat P11 de preuve privée et de synthèse
commanditaire. `website_slides/models/slide_channel.py` possède sa progression
par adhésion ; la réutiliser créerait un second suivi à côté des inscriptions S03.
Le tutorat S05 contrôle l’accès pédagogique courant et s’arrête à la clôture.
Les retours différés S09 restent un questionnaire distinct, inchangé.

P11 ajoute des actions après formation, rattachées à l’inscription unique, sans
modifier sa progression. Il réutilise le tuteur S05 (inscription puis réalisation),
les identités Odoo, QWeb/Portal, `ir.attachment`, la file `mail.mail`, le journal
idempotent de notifications et les protections documentaires S05/S11. Les preuves
ne passent ni par les followers ni par le chatter de la réalisation.

## Parcours et règles

La coordination constate la fin de formation sur une réalisation effectuée,
avant sa clôture administrative. Dans **Formations → Plans de mise en pratique**,
elle crée une action par objectif à 30 ou 60 jours, avec référence de prestation,
retour du tuteur inclus ou non et politique S08 approuvée. Une action à chaque
horizon est possible ; aucun objectif fictif n’est créé automatiquement.
La définition est conservée : fermer puis remplacer une action pour la corriger.

L’échéance est la date civile de fin constatée + 30/60 jours calendaires dans le
fuseau de la réalisation, indépendant du navigateur et des changements d’heure.
Le portail affiche une date traduite ; les traces horodatées utilisent le fuseau
utilisateur (UTC en repli). La prestation n’est pas déduite d’un produit ou tarif.

Le participant retrouve **Mes plans de mise en pratique** depuis son portail,
même après expiration des supports ou clôture administrative normale. Il marque
l’action réalisée, avec note et fichier facultatifs (20 Mo maximum). Les états
sont prévue → réalisée → clôturée ; la coordination peut aussi clore une action
prévue. La réalisation suffit à arrêter les rappels, sans attendre un avis.
Le tuteur actuellement affecté peut ajouter un retour si la prestation l’inclut,
après réalisation et avant clôture. Les retours successifs conservent auteur,
date et texte ; une répétition identique sans fichier ne crée pas de doublon.

Les profils portail ne reçoivent aucun droit ORM général. Les routes vérifient
identité, société, inscription, rôle, prestation et état à chaque opération,
puis ne projettent que les valeurs autorisées. Révocation explicite/annulation,
compte archivé, suspension et retrait du tuteur bloquent les accès correspondants,
y compris les anciens liens et jetons. Une suspension/révocation antérieure à la
clôture normale n’est pas réactivée par cette clôture. La coordination conserve
les preuves dans ses seules sociétés ; aucun droit pédagogique n’est donné au
commanditaire par son rattachement employeur.

Un rappel générique est mis en file à échéance puis par intervalle configuré
(zéro désactive). Le planificateur ne rattrape pas les occurrences anciennes.
Le verrou de réalisation puis d’action et une clé unique inscription/action/
occurrence empêchent les doubles soumissions et envois. Le transport vérifie à
nouveau le destinataire, ses droits, l’état courant et l’enveloppe sans copie ni
fichier. Les courriels ne contiennent ni objectif, ni preuve, ni retour.
Aucun envoi rétroactif n’est créé lors de la mise à jour.

## Synthèse et conservation

**Synthèses de mise en pratique autorisées** reçoit uniquement un texte saisi
séparément, sa référence d’accord/autorisation, une politique approuvée et le lot
client couvert par une habilitation P05 nominative. Publier fige texte, auteur et
date ; retirer masque la synthèse tout en gardant la preuve. Le portail entreprise
ne projette que les synthèses publiées de cette habilitation encore active.
Aucune copie d’action, résultat, pièce privée ou retour ne l’alimente automatiquement.
Une nouvelle habilitation ne récupère pas les anciens destinataires.

Les politiques S08 versionnées et immuables portent finalité, responsable, durée,
archive et instruction des suppressions. Elles doivent couvrir explicitement ces
preuves/retours et synthèses avant collecte réelle ; une politique fictive de test
ne vaut pas approbation métier. Aucun délai légal ni purge automatique n’est ajouté.
Les actions, preuves et journaux sont conservés ; les exports en masse des preuves
restent refusés, comme S05. La confidentialité des liens est recontrôlée par la
politique commune avant résolution et diffusion native du fichier.

## Recette courte

1. Sur données fictives : terminer une formation, conserver les accès ouverts,
   créer deux actions à 30/60 jours depuis un formulaire vide avec politique
   approuvée et référence de prestation. Vérifier dates et échéances en français.
2. Participant : réaliser une action avec puis sans preuve ; double soumission.
   Tuteur inclus : ajouter un retour ; vérifier auteur/date/fichier immuables.
   Sans prestation ou après retrait du tuteur : accès refusé.
3. Planifier deux fois un rappel, puis réaliser/clore : aucune nouvelle occurrence,
   ancien courriel en file refusé au transport. Zéro désactive les rappels.
4. Essayer autre participant, commanditaire, société, profil sans mission, ancien
   jeton et lien direct. Révoquer puis clore la réalisation : aucun accès réactivé.
   Comparer avec la clôture administrative normale et l’expiration des supports.
5. Publier une synthèse convenue pour une habilitation P05 : seul le texte choisi
   apparaît, sans preuve privée. Retirer la synthèse ou révoquer l’habilitation :
   ancien dossier refusé/texte absent. Garder évaluations différées et progression.
6. À 320/390 px et au clavier : labels, lecture des traces, saisie, erreur conservée,
   téléchargement privé et retour. Mettre à jour deux fois et comparer les
   historiques et fichiers, sans transport réel ni donnée d’exploitation.
