# S09 — Évaluations, retours et qualité : cadrage validé

Références : [S09 #19](https://github.com/Progideo/training_management/issues/19),
[S10 #20](https://github.com/Progideo/training_management/issues/20), EVA01–EVA02,
QUA01–QUA03, SEC01–SEC02 et chapitres 9, 10, 13–14 de la
[spécification v2](references/Training_Management_Specification_Fonctionnelle_v2.md).
Les compléments validés de #19/#20 font référence pour les droits et le tableau.
Décision utilisateur du 23 octobre 2026 : restitution anonyme dès trois réponses
recevables, sans contrôle supplémentaire de réidentification. Cette décision
prévaut sur les restrictions de restitution proposées précédemment ; elle est reportée dans les issues #19 et #20.
S09.1 est livré ([PR #63](https://github.com/Progideo/training_management/pull/63)).
S09.2 est décrit dans [sa page](s092-feedback.md), S09.3 dans [sa page](s093-quality.md). S09.4 reste distinct.

## Référence et périmètre

Base : `main` à `802bc302fce2f647560b6f3d684c9d6935315f9d`,
[PR S08 #62](https://github.com/Progideo/training_management/pull/62).
Versions : socle `20.0.1.8.0`, Ventes `20.0.1.10.6`, Surveys `20.0.1.0.0`.
S01 à S08 sont fusionnés ; les livraisons et validations sont dans les PR,
dont [S06/P07/P08 #60](https://github.com/Progideo/training_management/pull/60)
et [S07 #61](https://github.com/Progideo/training_management/pull/61).
Le résumé de [#3](https://github.com/Progideo/training_management/issues/3) est ancien.
Les deux références importées correspondent aux sources synchronisées ; leurs
empreintes restent celles de [l’index](README.md). Aucune réécriture des sources.

S09 couvre toutes les finalités : positionnement, acquis, formatif, examen blanc,
satisfaction immédiate et différée, retour formateur, retour commanditaire.
Il inclut réclamations, améliorations et efficacité, compétences et habilitations,
sous-traitance et veille analysée. Le formatif S05 et les examens S06 restent leurs
sources métier : les distinguer ne signifie pas les redévelopper.

S09 fournit états, populations et droits. **S10 livre la vue consolidée native par
réalisation en phase 1, avant L01**, sans date imposée. Exercices, devoirs,
remises/corrections et échanges privés S05 sont exclus de cette vue.
P09–P16, certification officielle, avis publics et P17–P20 restent hors de S09.

## Découpage validé

| Incrément | Résultat utilisable et condition de sortie |
| --- | --- |
| S09.1 — évaluations et droits | Finalités et versions, affectations superviseur, habilitations d’évaluation ; positionnement et acquis nominatifs, états/validation/révisions ; raccord contrôlé S08. Vérifier isolement et retrait des accès. |
| S09.2 — retours | Campagnes immédiates/différées, formateur/commanditaire, populations, invitations/échéances/relances et synthèses ; collecte anonyme dissociée, restitution dès trois réponses recevables. Vérifier la séparation des invitations et réponses et le seuil de restitution. |
| S09.3 — réclamations et améliorations | Dossiers confidentiels, traitement/réponse, actions liées, contrôle d’efficacité distinct de la réalisation, preuves S08 autorisées. |
| S09.4 — intervenants, sous-traitance et veille | Compétences/justificatifs, habilitations datées et alertes avant affectation, obligations contractuelles, analyse/impact de veille ; recette transversale et contrat S10 stabilisé. |

Chaque incrément conserve une PR avec preuves et recette, sans clôturer #19 avant
la couverture complète. S09.1 pose le contrôle d’habilitation ; S09.4 complète son
dossier justificatif. Les anciens formateurs ne deviennent pas habilités par migration.

## Couverture native et écarts

Cible : Community `20.0-20261015`, image
`odoo@sha256:61e3c71b0503c5f658e604c3e340bede20b97d05f726179fa006eae50a32fd23`.
Les preuves natives ci-dessous sont des **constats de code**, pas des tests de parcours.
Chemins relatifs à `/usr/lib/python3/dist-packages/odoo` dans cette image.

| Besoin | Couverture native / configuration | Écart et proposition | Preuve à consulter |
| --- | --- | --- | --- |
| EVA01 : questionnaires variés | Éditeur, questions, sections, réponses, notation facultative, seuil | Finalité/version publiée immuable, critères propres, réalisation et population à ajouter ; copie native pour V2 | `addons/survey/models/survey_survey.py` : champs de notation, `copy`, `_create_answer` ; [S06](s06-mock-exams.md) |
| EVA01 : acquis/positionnement | `survey.user_input` : `new/in_progress/done`, score et seuil | `done` ne vaut pas validation pédagogique ; décision d’évaluateur, révision et sélection explicite du résultat de référence à ajouter. Aucun zéro implicite | `addons/survey/models/survey_user_input.py:28–56,80–92` ; [preuve S08](../addons/training_management/models/training_closure.py) |
| EVA02 : invitations et échéances | `survey.invite`, échéance par réponse, file `mail.mail` | Population versionnée, journal durable, relance idempotente et refus après retrait ; ne pas prendre l’assistant transitoire pour historique | `addons/survey/wizard/survey_invite.py:_prepare_answers` ; [envois S04](s04-preparation-sessions.md) et [S05](s05-private-materials.md) |
| EVA02 : anonymat | Accès public ou sur invitation ; identité facultative dans le modèle | L’invitation native crée une réponse liée au contact/courriel. Collecte dissociée et restitution protégée indispensables ; un nom masqué ne suffit pas | `survey_survey.py:_create_answer:571–600`, `survey_invite.py:191–205`, `survey_user_input.py:45–50` |
| Droits et révocation | Comptes Odoo, ORM, portail, restrictions Survey | Les ACL Survey standard n’expriment pas les affectations formation. Projections autorisées et protections globales à étendre ; ne pas attribuer Sondages au superviseur | `addons/survey/security/ir.access.csv`, `addons/survey/controllers/main.py:_fetch_from_access_token,_check_validity` ; [sécurité S06](../addons/training_management_survey/security/ir.access.csv) |
| QUA01–QUA02 | Contacts, activités et fichiers natifs ; Project fournit des tâches, sans démonstration du dossier qualité requis | Registres métier ciblés dans le socle, vues/activités natives et confidentialité par dossier. `helpdesk` et `quality` absents de l’image ; pas de dépendance Enterprise | Présence des addons dans l’image ; [politique documentaire](../addons/training_management/models/training_document_policy.py), [S08](s08-closure-documents.md) |
| QUA03 : compétences | `hr_skills` présent ; compétences et validités rattachées à `hr.employee` | Les intervenants S04 sont des contacts, dont externes. Dossier ciblé sur `res.partner`, sans créer d’employés artificiels ; décisions par société/programme/mission | `addons/hr_skills/models/hr_employee_skill.py:7–26` ; [S04](s04-preparation-sessions.md) |
| QUA03 : sous-traitance/veille | Contacts/fichiers/activités ; Purchase gère commande fournisseur, fournisseur et états | Suivi des obligations et analyse de veille à ajouter. Aucun achat/comptabilité obligatoire pour ce registre ; référencer les pièces existantes autorisées | `addons/purchase/models/purchase_order.py` ; QUA03 et chap. 13–14 de la spécification |
| Preuves et attestations | QWeb, preuves S08 versionnées, score/seuil et instantanés | Publier une preuve d’acquis dédiée S09 ; conserver validation qualité S08 et anciens documents | [S08](s08-closure-documents.md), `training_closure.py:382–383,592–610` |

Les empreintes des deux modèles Survey sont identiques à celles de la
[couverture native](native-coverage.md). `survey_invite.py` :
`7b51ac5183b83f1ddce36e4af640bbfdd4e6537ef50bb7b32cdbb5a8310f7aed`.
La présence de Project/Purchase/RH ne prouve pas leur adéquation à QUA01–QUA03.
Aucun module communautaire supplémentaire n’est nécessaire à ce stade : les écarts
portent sur les règles métier et les périmètres, avec composants natifs déjà disponibles.

Architecture recommandée : registres et autorisations génériques dans
`training_management` ; éditeur/passation Survey dans `training_management_survey`,
LGPL-3, sans dépendance Survey imposée au socle. Pas de nouvel addon/service/frontend.
L’intégration S06 actuelle impose QCU/QCM chronométrés, correction finale,
tentatives illimitées et routes privées à tout Survey marqué `training_program_id`.
**Ne pas utiliser ce marqueur inchangé pour les retours S09.** Étendre explicitement
la distinction des finalités et toutes ses frontières : publication, réponses,
ACL, routes, images, rapports et fichiers ; préserver les sondages ordinaires et S06.
La mutualisation exacte reste à vérifier par les tests de non-régression.

## Parcours et états

Le coordinateur ouvre la réalisation, choisit une finalité/version publiée, la
population, l’échéance et les évaluateurs autorisés ; il contrôle les destinataires
puis invite. Une nouvelle version ne remplace jamais celle déjà adressée.
Le participant retrouve ses évaluations/retours dans Mes formations ; formateur
et commanditaire reçoivent leur propre questionnaire. Une personne peut avoir
plusieurs qualités : le rôle de destinataire reste explicite, sans dédoublonnage abusif.
L’évaluateur habilité valide le résultat ; la qualité valide ensuite la preuve S08.

| Objet | États et règles proposés |
| --- | --- |
| Définition/version | Brouillon → publiée → archivée ; publication fige questions, critères, barème, seuil, anonymat et règles de restitution. Nouvelle version avec motif et lien d’origine. |
| Campagne/population | Réalisation, programme/version, finalité, population et critères d’inclusion conservés. Ajout/retrait ultérieur tracé ; aucune invitation/évaluation supprimée pour masquer un abandon. |
| Questionnaire nominatif | À inviter → invité → en cours → réponse reçue ; non-réponse à échéance = invité sans réponse recevable à cette date. Avant invitation : « non invité », même après échéance. Non-applicable exige un motif ; absence de donnée = manquant. |
| Évaluation nominative hors exercices | Attendue (affectée, accès non encore ouvert) → non commencée (disponible) → en cours → terminée/à valider → validée. Invitation et retard restent des dimensions distinctes. Résultat absent = non évalué ; score zéro explicite possible après évaluation. Une appréciation qualitative peut être validée avec score non applicable. |
| Résultat | Questions/barème/version, tentative, date de remise, résultat, seuil éventuel, validateur et date conservés. Une remise complète ne prouve pas la réussite. Révision motivée avec avant/après ; nouveau résultat de référence désigné explicitement, jamais « meilleur score » implicite. |
| Réclamation | Reçue → en traitement → résolue avec réponse → clôturée ; responsable, canal, confidentialité, échéance, traitement/action ou justification requis. Réouverture motivée, traces conservées. |
| Amélioration | À décider → planifiée → réalisée → efficacité à vérifier → efficace / non efficace. Critère, preuve et vérificateur requis ; non efficace appelle une suite documentée. |
| Intervenant/habilitation | Compétences, justificatifs et validités ; décision datée avec périmètre/mission, auteur, motif et retrait. Alerte avant affectation si justificatif expiré ; validation d’évaluation soumise à habilitation courante. |
| Sous-traitance / veille | Obligations, responsable, échéance, justificatif et contrôle ; veille avec source/date, analyse, décision, impact ou absence d’impact motivée, lien à action/version de programme si pertinent. |

Positionnement S04 reste la synthèse utile au formateur ; une évaluation S09 peut
la compléter par une décision tracée, sans écraser la synthèse ni changer les prérequis.
Le formatif garde ses critères S05 ; les examens blancs gardent S06, y compris
tentatives illimitées. Pour les acquis, conserver plusieurs tentatives, avec
validation humaine et désignation explicite de celle faisant référence ; publier
la règle de nouvelle tentative par évaluation sans appliquer celle de S06 par défaut.
Aucune assimilation d’un exercice, d’une satisfaction ou d’un examen blanc aux acquis.

L’échéance de campagne est distincte d’une éventuelle durée d’épreuve. À échéance,
refuser les nouvelles remises ; une réouverture explicite conserve l’ancienne date,
le constat de non-réponse et la nouvelle échéance. Toute durée contrôlée utilise
l’heure serveur, sans reprendre la tolérance du contrôleur Survey générique.

Relances : paramétrage par campagne, envois individuels et clé stable
campagne/version/destinataire/occurrence ; résultat de file et erreurs visibles.
Vérifier destinataire et affectation au transport, y compris reprise. S09 fournit
ses relances utilisables ; S10 consolide les notifications sans second moteur d’envoi.
Les délais différés, de réclamation et de contrôle restent configurables ; aucun
engagement de service ou calendrier de lancement n’est inventé.

## Droits proposés, dans les limites validées

Chaque autorisation associe rôle, société exploitante et réalisation/dossier.
L’entreprise cliente n’est jamais la société exploitante ; appartenance à un client
ou rôle Sondages ne vaut pas habilitation pédagogique. Cumuls explicites seulement.

| Profil | Consultation | Actions / exclusions |
| --- | --- | --- |
| Participant | Ses évaluations nominatives, résultats communicables et documents autorisés ; ses invitations | Répondre et soumettre ; aucune validation ni donnée d’un pair. Plainte personnelle et réponse via parcours confidentiel, sans accès au registre. |
| Formateur | Réalisations/séances affectées, participants autorisés, états/résultats utiles à sa mission | Évaluer/contrôler seulement avec habilitation correspondante ; conserver contrôle S07. Pas de dossiers sensibles, comptabilité ni droits qualité implicites. |
| Superviseur | Toutes les inscriptions autorisées des réalisations explicitement confiées, y compris états d’abandon/annulation | Lecture seule ; ni validation/correction, approbation qualité, dossiers sensibles, comptabilité, échanges privés ou réponses anonymes individuelles. |
| Coordinateur | Gestion opérationnelle dans sa société autorisée, populations/invitations et états nécessaires | Paramétrer/affecter/inviter ; ni approbation qualité ni validation pédagogique sans habilitation distincte. Contenus sensibles hors habilitation refusés. |
| Qualité | Évaluations nécessaires et registres/dossiers explicitement confiés | Traiter, vérifier efficacité, décider habilitation si mandatée ; validation S08 sur ses dossiers. Le groupe qualité seul ne donne pas accès à tous les dossiers. |
| Commanditaire / contact entreprise | Son questionnaire et documents/synthèses expressément autorisés | Répondre ; pas de réponses ou scores individuels des salariés. Un rôle client ne devient pas superviseur. |
| Commercial / facturation / sans rôle | Leurs droits existants | Aucun nouveau droit aux réponses, scores, plaintes ou pièces qualité. |

Réutiliser `res.users`/`res.partner`, affectation `training.session.instructor_id`
et tutorat S05 lorsqu’il constitue effectivement la mission. Ajouter seulement
l’affectation superviseur par réalisation et l’habilitation d’évaluation manquantes.
Prévoir une affectation de mission à la réalisation pour l’asynchrone sans séance,
sans séance fictive ni nomination automatique de tous les tuteurs comme évaluateurs.
Le retrait/réaffectation retire immédiatement la lecture et les actions, y compris
historiques par ancien lien/jeton ; les traces restent conservées pour les habilités.

Formateur externe : conserver le portail Odoo. Supervision : vues natives internes
pour un compte interne, projection portail pour un compte externe explicitement
affecté ; ne pas lui imposer coordinateur ou Sondages. S09 contrôle ses états ;
la vue consolidée de ces parcours est S10.
Les ACL S06 actuelles réservent les données brutes à la coordination : fournir
une projection de résultats autorisés au formateur/superviseur sans élargir les ACL
des réponses/corrigés. Recontrôler recherches, totaux, regroupements, actions,
routes, liens, binaires et exports ; `sudo()` limité après contrôle de l’identité
réelle et du périmètre, jamais comme moyen de contourner une règle de rôle.

## Anonymat : restitution décidée et collecte à démontrer

Choisir nominatif/anonyme à publication selon la finalité. Les acquis destinés à
une attestation restent nominatifs. Pour une campagne anonyme :

- Séparer liste administrative des invitations et collecte : aucune relation
  réponse ↔ inscription/contact/invitation ; ni courriel, pseudonyme identifiant,
  auteur utilisateur personnel ou jeton d’invitation réutilisé dans la réponse.
  Interdire les questions enregistrant courriel/nom et avertir sur le texte libre.
- L’invitation nominative peut être suivie ; réponse, début de réponse, score et
  non-réponse individuels restent **indisponibles**, pour tous les rôles métier.
  S10 affiche « collecte anonyme, suivi individuel indisponible » ; aucun état
  individuel déduit par soustraction. Relance collective aux invités éligibles,
  y compris ceux ayant peut-être répondu, avec mention « si vous avez déjà répondu… ».
- Décision validée : publication de l’agrégat figé à clôture dès **3 réponses
  recevables**. En dessous : « effectif insuffisant ». Aucun contrôle supplémentaire
  de réidentification ni condition de blocage liée à l’homogénéité, aux recoupements
  ou aux réponses rares. Le seuil de trois constitue la règle de restitution ;
  il ne démontre pas à lui seul l’impossibilité d’une réidentification.
- Qualité et superviseur ne lèvent pas l’anonymat. Pas de réponses brutes individuelles
  par export ou rapport générique. Les questionnaires formateur/commanditaire à
  une personne sont nominatifs ou sans restitution à ce niveau ; jamais « anonymes »
  avec leur score visible sous un libellé de réalisation.

La séparation doit aussi couvrir métadonnées ORM, dates techniques, messages,
notifications et journaux. Une preuve jetable devra établir délivrance d’un droit
de réponse, contrôle d’éligibilité/révocation et anti-double remise **sans lien
persistant exploitable avec les réponses**. Les liens ne doivent pas devenir des
jetons publics transférables. Cette faisabilité n’est pas démontrée par la lecture
du standard ; elle conditionne S09.2, sans en reporter l’exigence à S10/S11.
Si la preuve échoue, revenir avec l’écart précis avant implémentation ; aucun mode
simplement pseudonymisé ne sera présenté comme anonyme. Les capacités privilégiées
de support technique restent celles de SEC01, limitées et surveillées.

## Contrat des états consommés par S10

Contrat fonctionnel à traduire en champs/services natifs, sans API externe nouvelle.
Tous les résultats sont filtrés côté serveur **avant** comptage, regroupement et pagination.

| Niveau / clé | Informations et règles |
| --- | --- |
| Réalisation | Société exploitante, programme/version, date de situation, population et filtres explicites ; aucune addition de sociétés ou de devises implicite. |
| Ligne participant : `enrollment_id` | Une ligne par inscription de la réalisation, identité autorisée et état S03 ; actifs, abandons et annulations retrouvables par filtres explicites. Les relations séances/tentatives/questionnaires restent des détails, sans multiplication de lignes. |
| Présence : inscription + séance S07 | Feuille attendue, déclarée, à contrôler, validée ; absence/anomalie, électronique/papier à déposer/papier déposé à contrôler ; durée validée, révision et détail autorisé. « Attendues » vient du planning/population, pas des seules lignes existantes. |
| Questionnaire : campagne + version + destinataire/rôle | Pour nominatif : invitation, échéance, état démontré et complétion. Pour anonyme : uniquement invitation administrative autorisée et restitution collective protégée. Formateur/commanditaire dans une synthèse séparée de réalisation, sans copie sur chaque participant. |
| Évaluation : inscription + finalité/version | État, retard, tentative de référence, résultat présent/absent, seuil applicable/absent, validation et révision ; acquis, positionnement et examens blancs séparés. Aucun devoir/remise/échange privé. |
| Synthèse vérifiable | Formule/version, population, date/période, numérateur, dénominateur, couverture, manquants et non-applicables motivés ; détail autorisé, sauf restriction d’anonymat. |

S07 ne stocke que `pending/anomaly/validated` : les libellés plus fins demandés
par S10 sont une projection des événements et du mode de collecte, à vérifier
sur les cas de la recette. Une ligne absente n’est pas une absence validée.
Asynchrone sans séance = non applicable ; aucune présence construite depuis un quiz.
La dernière validation/correction S07 fait autorité, sans addition de sources.

Résultat d’acquis : taux de réussite = validations au seuil / évaluations validées
avec score applicable ; afficher aussi couverture / population attendue applicable.
Exemple de contrôle S10 : 10/12 = 83,33 %, couverture 12/20 ; zéro dénominateur
= non calculable. Satisfaction : formule de la version et réponses recevables,
non-réponses séparées ; jamais une non-réponse favorable. Aucun taux de certification
officielle issu de S06. Les règles d’anonymat peuvent interdire l’affichage de ces
comptages même lorsque le calcul interne est possible.

## Preuves S08 et conservation

Pour des acquis validés : générer une preuve PDF dédiée avec finalité, version,
inscription, tentative/révision de référence, critères, score/seuil, évaluateur et
dates. La déposer dans la catégorie S08 `assessment`, avec provenance et empreinte ;
la qualité affectée la valide, puis peut émettre l’attestation selon S08.
La validation pédagogique et la validation de preuve qualité restent distinctes.
La valeur par défaut 70 du champ S08 ne remplace jamais le seuil publié S09.
Une évaluation non notée ne délivre pas de réussite chiffrée par défaut.

Relier positionnement, retours et actions aux catégories S08 existantes. Pour un
retour anonyme, déposer seulement la preuve de campagne et la synthèse autorisée,
sans lien individuel aux réponses ; une collecte insuffisante reste explicite.
Une réclamation n’est pas copiée intégralement dans chaque dossier participant :
preuve restreinte ou synthèse autorisée, sans données de tiers. Les exports client
gardent les exclusions S08 des évaluations, retours, incidents et métadonnées privées.

Une correction produit une nouvelle version de preuve ; anciens scores, seuils,
PDF, ZIP et instantanés restent inchangés. Aucun remplacement dans un dossier
clôturé : traitement selon le gel existant et décision qualité distincte.
Pas de synchronisation qui réémettrait automatiquement les attestations.

Réutiliser les politiques S08 : catégorie/finalité, responsable, durée approuvée,
archive/suppression et gel. Étendre leur rattachement aux registres S09 ; aucune
durée juridique ni purge automatique inventée. Les paramètres doivent être
approuvés avant collecte réelle ; S11 vérifiera transversalement le dispositif.
Pièces privées sous politique documentaire courante, pas de détail sensible dans
chatter, activité partagée, objet de courriel ou pièce jointe autonome partageable.

## Recette prévue et critères de sortie

Ces scénarios sont **à exécuter pendant les incréments**, avec données fictives :

1. Deux clients, deux réalisations, deux formateurs, participants et société
   étrangère ; superviseur sur une seule réalisation, qualité affectée/sans
   affectation, commanditaire, commercial, sans rôle et cumuls explicites.
   Tester écrans et ORM/recherche/totaux/export, routes, liens, fichiers et jetons.
   Retirer les affectations avant lecture, remise, validation et transport en file.
2. Positionnement/acquis/formatif/examen blanc distincts ; version V1 publiée puis
   V2, réponse partielle, échéance dépassée, non-réponse et non-applicable motivé.
   Vérifier « non évalué », zéro réel, seuil non atteint, score au seuil, remise
   à valider, habilitation expirée et révision sans écrasement de V1.
3. Campagnes participant/formateur/commanditaire, immédiates/différées ; double
   invitation, relance rejouée, erreur/reprise et retrait avant envoi. État cohérent
   sans inventer des questionnaires participant pour les autres populations.
4. Anonyme : deux réponses recevables refusent la restitution ; trois l’autorisent
   après clôture, sans contrôle complémentaire. Vérifier séparation des invitations
   et réponses, absence de statut de réponse nominatif et de relance ciblée sur les
   répondants, y compris export et anciens liens. Vérifier anti-double remise et
   révocation sans rompre la dissociation.
5. Réclamation confidentielle : pas de clôture sans réponse/traitement ou
   justification ; action réalisée restant « efficacité à vérifier », échec puis
   suite documentée. Justificatif expiré signalé avant affectation ; veille avec
   analyse sans impact ou nouvelle version liée ; obligations échues et contrôlées.
6. Acquis validés → PDF S09 → preuve/validation S08 → attestation ; refuser examen
   blanc seul. Corriger ensuite : nouvelles preuves/documents, anciens PDF et ZIP
   byte-identiques, aucune fuite vers index/client ni modification sous gel.
7. Contrat S10 : deux séances, présence partielle, absence, papier attendu/déposé,
   correction et asynchrone ; plusieurs questionnaires/tentatives sans doublon de
   participant ; abandons/annulations retrouvables, manquant/non-applicable distincts,
   chiffres rapprochés des sources autorisées. Vérifier clavier, mobile, focus,
   erreurs, libellés sans dépendance à la couleur et PDF lisibles.
8. Installation vierge et mise à jour depuis S08 avec Website, Ventes et Survey,
   socle sans Survey ; conservation S02/S05/S06/S07/S08 puis deuxième mise à jour
   avec données S09. Deux transactions pour doubles remises, validation/révision
   et retrait concurrent. Réutiliser les scénarios CI existants, isoler et nettoyer
   les ressources ; consigner résultats et limites dans chaque PR.

## Décisions et paramètres restants

Les droits, le périmètre complet S09 et le tableau S10 sont déjà décidés.
Le choix de restitution anonyme est validé :

| Choix | Décision utilisateur | Conséquence |
| --- | --- | --- |
| Restitution anonyme | Agrégat figé après clôture, minimum 3 réponses recevables, sans contrôle supplémentaire ; relance collective et aucun statut de réponse nominatif | En dessous de trois réponses, pas de restitution ; à partir de trois, pas de blocage supplémentaire pour risque de recoupement. |

QUA03 prévoit déjà l’alerte avant affectation en cas de justificatif expiré :
l’appliquer sans ajouter un blocage général du planning. Une habilitation
d’évaluation absente/retirée/expirée interdit l’action correspondante, conformément
aux droits validés. Aucun nouvel arbitrage n’est nécessaire pour ces deux règles.

Les responsables nommés, politiques de conservation, délais et modalités de chaque
campagne sont des paramètres d’exploitation à approuver avant usage réel, pas des
raisons de rouvrir le périmètre. Le découpage et l’architecture ci-dessus sont validés ; aucune capacité S09 non testée
n’est annoncée livrée.
