Training Management pour NeoPro Academy

Spécification fonctionnelle

Version 2.0 • 15 octobre 2026 • Périmètre et séquencement validés

Ce document décrit le fonctionnement attendu de la future plateforme de formation. Il sert à valider les parcours, les règles métier, les droits et les preuves qualité avant de choisir les modules et de figer l'architecture Odoo 20 Community.

## Décisions validées

| **Domaine**       | **Choix NeoPro**                                                                                                       |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------- |
| Public            | Marché francophone mondial ; français au lancement.                                                                    |
| Priorités         | Formations intraentreprise, puis inscriptions individuelles ; présentiel, distanciel, eLearning et mixte.              |
| Commercialisation | Ventes en dirhams marocains MAD ou euros EUR ; virement bancaire ; pas de paiement en ligne.                           |
| Pédagogie         | PDF, quiz et examens blancs à questions fixes, chronométrés, avec score et correction finale ; répétitions illimitées. |
| Présences         | Papier ou numérique selon le cas ; émargement électronique dès le lancement.                                           |
| Qualité           | Alignement volontaire sur Qualiopi ; aucune certification effective engagée.                                           |
| Reprise           | Données Odoo 19 indispensables ; migration automatisée ou manuelle contrôlée.                                          |

## Statut des propositions

Le cadrage et le séquencement sont validés le 15 octobre 2026 : P01 à P08 en phase 1, P09 à P16 en phase 2, P17 à P20 après validation complémentaire. MVP désigne le socle de lancement, complété par P01 à P08. Les chapitres 18 à 24 détaillent ces ajouts et priment en cas de conflit de priorité. La couverture technique Community reste à établir en étape 3.

L'audit Odoo 19 reste suspendu. Cette révision porte sur les spécifications. L'architecture, le développement et le déploiement restent des étapes distinctes ; cette validation n'autorise aucune intervention sur la production.

# 1 Parcours et responsabilités

| **Parcours**                | **Déroulement et résultat**                                                                                                                                                                                                                              |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Intraentreprise prioritaire | Le commercial analyse le besoin, prépare un devis MAD ou EUR, puis réserve les places. Le coordinateur nomme les participants, prépare la session et ouvre les accès. Le formateur suit présences et acquis. Le responsable qualité contrôle la clôture. |
| Individuel synchrone        | Le visiteur choisit une formation et une session, transmet une demande, reçoit les modalités de virement. NeoPro confirme la place et les accès ; le participant suit la formation et retrouve ses documents.                                            |
| eLearning autonome          | La demande porte sur un parcours, sans session collective obligatoire. Après validation NeoPro, le participant consulte les PDF, réalise les activités et examens, puis conserve les accès jusqu'à leur échéance.                                        |
| Mixte                       | Une inscription réunit activités autonomes et séances datées. Les critères de présence et de complétion sont visibles séparément ; le bilan rassemble les deux.                                                                                          |
| Annulation ou report        | NeoPro trace le motif, les impacts commerciaux et les accès. Le report crée un lien vers la nouvelle réalisation ; les preuves de l'ancienne ne sont pas réécrites.                                                                                      |

## Acteurs et responsabilité finale

Le commercial porte l'offre et les engagements ; le coordinateur prépare et suit les inscriptions ; le formateur ou tuteur anime et évalue ; la facturation enregistre les règlements ; la qualité valide les preuves et les améliorations. Un même salarié peut cumuler des rôles explicitement attribués.

Le participant conserve ses accès personnels aux réponses, devoirs et résultats. L'entreprise cliente dispose dès la phase 1 d'un portail limité à ses demandes, sessions, listes de participants et documents autorisés (P05). Ce portail ne donne aucun accès par défaut aux scores individuels, réponses ou échanges privés.

## Critères de réussite du MVP

NeoPro peut réaliser chaque parcours ci-dessus sans fichier parallèle obligatoire pour piloter les inscriptions. Chaque participant accède à ses propres contenus et documents. Chaque vente conserve sa devise. Chaque examen peut être repassé sans perdre les tentatives passées. Les données indispensables de l'ancien système sont reprises et contrôlées avant ouverture.

# 2 Objets métier et cycles de vie

| **Objet**               | **Relations et informations de référence**                                                                                                                                                                  |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Formation et programme  | Une formation possède plusieurs versions de programme. Chaque version fige objectifs, prérequis, durée, méthodes et critères d'évaluation. Une réalisation utilise une version déterminée.                  |
| Réalisation             | Session datée ou offre de parcours autonome. Elle précise modalités, capacité éventuelle, calendrier, contenus et responsable. Une session possède zéro à plusieurs séances avant finalisation du planning. |
| Inscription             | Relie un participant à une réalisation et à une version de programme. Référence la ligne commerciale ou le motif gratuit. Une seule inscription active par participant et réalisation.                      |
| Places et groupe        | Une commande peut contenir des places non nominatives. Un groupe rassemble des inscrits et partage des ressources ; il ne crée pas de second registre d'inscriptions.                                       |
| Séance et activité      | La séance porte horaires et ressources synchrones ; l'activité porte contenu, consigne, échéance et complétion. Un parcours mixte rassemble les deux.                                                       |
| Évaluation et tentative | Une évaluation possède des versions et plusieurs tentatives par inscrit. La tentative conserve questions, réponses, barème, durée et résultat applicables.                                                  |
| Présence et preuve      | Une présence relie inscrit et séance. Une preuve référence le document ou événement, son auteur, sa date, sa version et les droits de consultation.                                                         |
| Parties commerciales    | Client, commanditaire, payeur, contact administratif et participant sont des rôles distincts. Leur rattachement à une entreprise ne donne aucun accès implicite.                                            |

## États indépendants

Programme : brouillon → validé → publié → retiré. Session : préparation → confirmée → en cours → réalisée → clôturée ; annulation possible avec motif. Inscription : demandée → réservée ou en attente → confirmée → clôturée ; branches annulée, remplacée ou abandonnée.

Accès : non ouvert → actif → expiré, suspendu ou révoqué. Progression : non commencée → en cours → terminée, avec résultat pédagogique distinct. Paiement : non réglé → partiel → réglé ; remboursement suivi séparément. Aucun de ces états ne doit être déduit automatiquement d'un autre sans règle explicite.

# 3 Catalogue et commercialisation

## CAT01 Publier un programme contrôlé

Priorité MVP. Le coordinateur valide objectifs évaluables, public, prérequis, contenu, durée, modalités, langue, prix ou sur devis, accès, évaluation et contact accessibilité. Recherche par texte, catégorie et modalité. P01, P03 et P04 complètent le catalogue dès la phase 1 ; P14 à P16 relèvent de la phase 2.

Acceptation — Nominal : une fiche publiée est trouvable et son PDF correspond à sa version. Erreur ou limite : publication refusée si un champ obligatoire manque ; un brouillon est invisible au public.

## CAT02 Préserver les versions

Priorité MVP. Une modification substantielle crée une nouvelle version. Les inscriptions existantes gardent leur programme ; une adaptation individuelle est datée et motivée.

Acceptation — Nominal : la session de novembre conserve V1 après publication de V2. Erreur ou limite : la modification de V2 ne remplace pas le PDF contractuel V1.

## COM01 Traiter les demandes

Priorité MVP. Distinguer demande individuelle et groupe ; saisir besoin, modalité, dates souhaitées, effectif, contact et devise. Relier la demande au devis, sans créer automatiquement un accès. Le parcours intra guidé P02 et le dossier client P06 complètent cette règle en phase 1.

Acceptation — Nominal : une demande intra de 12 personnes produit un devis traçable. Erreur ou limite : une soumission répétée signale le doublon et ne crée pas deux réservations.

## COM02 Vendre en MAD ou EUR

Priorité MVP. Une offre peut avoir deux tarifs commerciaux validés indépendamment. Une commande et ses documents portent une seule devise, prix par personne ou forfait, quantité, taxes et conditions. Aucun taux implicite.

Acceptation — Nominal : un forfait EUR reste en EUR dans la commande et la facture. Erreur ou limite : un changement de devise après confirmation exige une révision contrôlée ; aucune simple substitution de symbole.

## COM03 Suivre le virement

Priorité MVP. La facturation enregistre date, montant, devise, référence et affectation du règlement ; acomptes et soldes restent distincts. Un avis de virement client ne vaut pas règlement constaté.

Acceptation — Nominal : un virement partiel réduit le solde sans marquer réglé. Erreur ou limite : une référence déjà traitée déclenche un contrôle ; un versement dans une autre devise attend un rapprochement explicite.

La devise comptable, les taxes, les mentions marocaines et les règles de conversion seront validées avec le responsable comptable. Le pays du client ne suffit pas à déterminer automatiquement le traitement fiscal.

# 4 Inscriptions et accès

## INS01 Gérer les places

Priorité MVP. Une entreprise peut acheter N places puis nommer les participants progressivement. La capacité tient compte des réservations non expirées et des confirmations, sans compter deux fois les places nominatives.

Acceptation — Nominal : 10 places achetées et 7 noms donnent 3 places à désigner. Erreur ou limite : le onzième nom ou deux confirmations concurrentes sur la dernière place sont bloqués.

## INS02 Confirmer sans doublon

Priorité MVP. La confirmation vérifie identité, réalisation, conditions commerciales, prérequis validés ou dérogation et places disponibles. Les invitations gratuites ont un motif.

Acceptation — Nominal : une répétition de validation restitue la même inscription. Erreur ou limite : un homonyme n'est pas fusionné automatiquement ; la même personne ne reçoit pas deux inscriptions actives.

## INS03 Ouvrir les droits

Priorité MVP. Accès si inscription confirmée, autorisation commerciale, prérequis validés ou dérogation, compte actif et période ouverte. Par défaut NeoPro autorise manuellement ; le paiement différé B2B est possible avec justification.

Acceptation — Nominal : une commande payable après formation peut donner accès sur validation. Erreur ou limite : commande confirmée seule ou preuve de virement non contrôlée ne donne pas accès.

## INS04 Annuler reporter remplacer

Priorité MVP. Tracer auteur, motif, date, conséquences sur places, documents, accès et finances. Un remplacement transfère la place, jamais les résultats de l'ancien participant. Un avoir ou remboursement suit sa propre validation.

Acceptation — Nominal : un report relie ancienne et nouvelle inscription, en conservant les traces. Erreur ou limite : annuler une inscription ne supprime ni facture ni tentative et ne déclenche pas automatiquement un remboursement.

## INS05 Définir les périodes

Priorité MVP. Chaque offre définit début et fin d'accès ou durée à partir d'une activation explicite ; les dates calculées figurent dans l'inscription. Une prolongation est motivée. Documents délivrés et contenus pédagogiques ont des droits distincts.

Acceptation — Nominal : après prolongation le nouveau terme est visible. Erreur ou limite : un accès expiré bloque les nouveaux examens et supports, sans supprimer les résultats archivés.

Réservation : une échéance obligatoire libère la place à expiration. Liste d'attente : ordre d'arrivée visible et proposition manuelle d'une place, avec nouveau délai d'acceptation. Le seuil d'ouverture d'une session génère une alerte ; le coordinateur décide et motive une ouverture sous le seuil.

# 5 Préparation et espace de formation

## ORG01 Analyser et adapter

Priorité MVP. Conserver besoin du commanditaire, objectifs du participant, positionnement, prérequis et décision d'adaptation. Les demandes d'aménagement détaillées sont réservées aux personnes habilitées.

Acceptation — Nominal : une adaptation produit une consigne utile au formateur. Erreur ou limite : le commercial et les autres participants ne voient pas les détails confidentiels.

## ORG02 Planifier les séances

Priorité MVP. Définir horaires, fuseau de référence, formateur, lieu ou lien distant, équipements et capacité. Bloquer les conflits de formateur et salle ; dérogation du coordinateur avec motif.

Acceptation — Nominal : une invitation affiche date, heure et fuseau local du destinataire. Erreur ou limite : un horaire ambigu lors d'un changement d'heure doit être clarifié avant confirmation.

## ESP01 Présenter un espace unique

Priorité MVP. Afficher programme applicable, agenda, PDF, exercices, examens, présence personnelle, questionnaires, documents et assistance. Les supports communs sont limités aux groupes autorisés ; les devoirs sont privés.

Acceptation — Nominal : un inscrit au mixte retrouve activités et séances dans le même espace. Erreur ou limite : une URL directe ne révèle pas la remise ou le résultat d'un autre inscrit.

## PED01 Suivre la progression

Priorité MVP. Chaque activité précise son critère : consultation déclarée, remise, validation du formateur ou seuil d'évaluation. Une activité optionnelle ne bloque pas la complétion. Les dépendances ne forment pas de cycle.

Acceptation — Nominal : un parcours autonome commence sans session datée. Erreur ou limite : ouvrir un PDF ne suffit pas à certifier l'acquisition d'une compétence.

## PED02 Accompagner et relancer

Priorité MVP. Un participant peut demander une aide privée et déposer un exercice. Affecter un tuteur et des échéances ; relancer après un seuil d'inactivité configuré par offre, avec journal des envois.

Acceptation — Nominal : une remise reçoit une correction et un statut. Erreur ou limite : une activité facultative ou une suspension justifiée n'entraîne pas une relance inappropriée.

La durée totale d'un parcours distingue durée pédagogique estimée et heures synchrones. Les connexions et durées de navigation sont des observations techniques ; elles ne remplacent pas les présences ou évaluations.

# 6 Examens blancs et quiz

## EXA01 Configurer un examen fixe

Priorité MVP. Le créateur choisit explicitement questions et ordre, durée positive en minutes, barème et éventuel seuil indicatif. Par défaut QCU et QCM ; pas de tirage aléatoire au MVP.

Acceptation — Nominal : tous les candidats de la même version voient la liste prévue. Erreur ou limite : publication bloquée si durée nulle, total de points nul ou question notée sans correction.

## EXA02 Calculer un score explicable

Priorité MVP. Proposition : points positifs par question ; QCU exact et QCM avec ensemble exact des réponses attendues obtiennent les points ; sinon zéro. Sans pénalité ni crédit partiel par défaut. Score = 100 × points obtenus / maximum.

Acceptation — Nominal : 18 points sur 24 donnent 75 % ; 75 % atteint un seuil fixé à 75 %. Erreur ou limite : absence de réponse compte zéro ; cocher toutes les réponses d'un QCM ne procure pas un succès automatique.

## EXA03 Faire respecter la durée

Priorité MVP. Le temps démarre après confirmation du candidat ; échéance contrôlée côté serveur. Retour ou rechargement reprend le temps restant, sans pause. Clôture automatique à échéance à partir des réponses enregistrées.

Acceptation — Nominal : après 10 minutes d'un examen de 60 minutes, il reste 50 minutes. Erreur ou limite : une réponse tardive ou une horloge locale modifiée ne prolonge pas la tentative.

## EXA04 Enregistrer et corriger

Priorité MVP. Enregistrer chaque changement de réponse avec état visible de sauvegarde. À remise ou expiration, afficher score, réponses données et attendues, points et explication si renseignée. Pas de correction avant remise.

Acceptation — Nominal : une déconnexion temporaire conserve les réponses déjà reçues. Erreur ou limite : une réponse non reçue est signalée comme non sauvegardée ; le système ne prétend pas la récupérer.

## EXA05 Autoriser les répétitions

Priorité MVP. Tentatives illimitées tant que les droits sont actifs, y compris après réussite. Une seule tentative active par personne et examen ; chacune possède son propre résultat.

Acceptation — Nominal : un candidat ayant 100 % peut recommencer immédiatement. Erreur ou limite : double clic ou deux onglets ne créent pas deux tentatives ; une nouvelle tentative ne réinitialise pas les anciennes.

## EXA06 Figer les résultats

Priorité MVP. Conserver la version des questions, réponses attendues, points, durée autorisée et résultat. Une correction administrative crée une révision motivée avec ancien résultat conservé.

Acceptation — Nominal : V2 peut évoluer sans modifier les scores V1. Erreur ou limite : une suppression de question utilisée ne casse pas la lecture d'une ancienne tentative.

# 7 Étude de la fonction Certification Odoo

Décision fonctionnelle : privilégier le mécanisme Sondages/Certification d'Odoo s'il satisfait EXA01 à EXA06 ainsi que P07 et P08. Ce choix reste candidat ; la couverture exacte dans Odoo 20 Community, les écarts et les extensions éventuelles devront être démontrés en étape 3.

## Faits documentaires vérifiés

La documentation officielle Odoo 19 décrit un score avec affichage des bonnes réponses à la fin, une durée limite, un seuil de réussite et une limitation de tentatives configurable. L'option Certification y est associée à la génération et à l'envoi d'un certificat aux candidats reçus \[S1, S2\]. Ces informations concernent la documentation 19 ; elles ne prouvent pas la couverture 20 Community.

| **Besoin NeoPro**             | **Conclusion de cette étape**                                                                                                        |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Liste définie par le créateur | Exigence EXA01 ; vérifier configuration de toutes les questions et ordre fixe dans la version cible.                                 |
| Durée et score                | Piste standard documentée en version 19 ; vérifier expiration et calcul QCM exact.                                                   |
| Correction finale             | Option documentée en version 19 ; vérifier explications et absence de fuite avant remise.                                            |
| Repasser après réussite       | Vérifier la relance depuis l'espace formation, notamment après réussite de la certification ou complétion du cours.                  |
| Historique et versions        | Vérifier ce qui est figé nativement et les effets des modifications de questions. Ne pas supposer l'immuabilité.                     |
| Protection des réponses       | Vérifier chaque route web, pièce jointe, jeton et lien de correction ; login seul ne suffit pas à prouver le contrôle d'inscription. |
| Fonctionnement Community      | À prouver par code, licence, dépendances et édition du livrable 20. Aucun achat Enterprise prévu.                                    |

## Orientation proposée

Utiliser un questionnaire noté comme examen blanc, avec libellé clair « Examen blanc ». Ne pas délivrer de certificat de réussite à chaque tentative. Si l'intégration eLearning impose l'option Certification, prévoir le contrôle des notifications, badges et documents pour ne pas suggérer une certification officielle. La nécessité d'une extension sera évaluée après vérification.

Limite de vérification : les pages 20.0 et le code cible n'ont pas pu être consultés pendant cette étude. Aucune installation ni démonstration n'a été réalisée. Ce point reste ouvert et ne signifie pas que la fonction est absente.

# 8 Présences et documents

## PRE01 Collecter les présences

Priorité MVP. Par séance, choisir papier, électronique ou mixte. Enregistrer intervalle réellement suivi, retard, absence, source et validation formateur. Le temps présent est borné par le temps prévu, sans double compte.

Acceptation — Nominal : un participant présent 90 minutes sur 120 compte pour 90 minutes. Erreur ou limite : papier et électronique pour la même présence ne produisent pas 240 minutes.

## PRE02 Émarger en ligne

Priorité MVP. Le participant authentifié confirme sa présence dans une fenêtre définie ; journaliser identité, séance, texte accepté, horodatage serveur et méthode. Le formateur valide séparément. Une signature tracée peut compléter ce processus.

Acceptation — Nominal : un émargement mobile est rattaché à la bonne séance. Erreur ou limite : un QR code collectif seul ne permet pas de signer au nom d'un autre ; hors fenêtre, traitement en anomalie.

## PRE03 Corriger avec traçabilité

Priorité MVP. Importer le papier signé et le rattacher aux personnes et séances. Toute correction conserve ancienne valeur, nouvelle valeur, auteur et motif. Aucune signature a posteriori ne doit être antidatée.

Acceptation — Nominal : le coordinateur corrige une présence avec justificatif. Erreur ou limite : la correction n'efface pas la déclaration initiale ni l'origine papier.

## DOC01 Délivrer des documents distincts

Priorité MVP. Participation : durée de présence validée ; réalisation : activités obligatoires et justificatifs contrôlés ; réussite : évaluation des acquis dédiée et seuil atteint. Les modèles portent identifiant, version, bénéficiaire et dates.

Acceptation — Nominal : une attestation de participation mentionne la durée réellement validée. Erreur ou limite : réussir un examen blanc seul ne délivre pas une certification ISTQB ni automatiquement une attestation de réussite de formation.

## DOC02 Clôturer et exporter

Priorité MVP. Un dossier rassemble index, pièces, versions, dates, auteurs, éléments manquants et destinataire autorisé. La clôture signale les manquants ; toute dérogation est approuvée et motivée.

Acceptation — Nominal : l'export qualité contient les preuves permises et un index des manquants. Erreur ou limite : l'export client exclut résultats privés, notes confidentielles et dossiers d'autres clients.

L'émargement proposé est une preuve de déclaration et de contrôle interne. Son niveau juridique et l'éventuel recours à un prestataire de signature doivent être décidés selon les contrats et financeurs ; une image de signature ne garantit pas seule l'identité ou l'intégrité. L'asynchrone utilise des traces d'activité et évaluations, sans fabriquer de présence à une séance inexistante.

# 9 Évaluations et gestion de la qualité

## EVA01 Distinguer les finalités

Priorité MVP. Identifier positionnement, quiz formatif, acquis, examen blanc, satisfaction immédiate, retour différé, formateur et commanditaire. Versionner chaque questionnaire ; critères de complétion distincts.

Acceptation — Nominal : le bilan sépare résultats aux acquis et satisfaction. Erreur ou limite : un score d'examen blanc répété n'est pas présenté comme taux de certification officielle.

## EVA02 Recueillir les retours

Priorité MVP. Paramétrer destinataires, échéance, caractère nominatif ou anonyme, relances et synthèse. En mode anonyme, ne pas rendre les réponses réidentifiables par le portail ; prévenir les recoupements sur petits effectifs.

Acceptation — Nominal : le tableau indique invitations et réponses valides. Erreur ou limite : une absence de réponse ne vaut pas satisfaction ; une vue dite anonyme ne montre pas le nom.

## QUA01 Traiter une réclamation

Priorité MVP. Ouvrir un dossier avec objet, canal, auteur, confidentialité, responsable, échéance, traitement et clôture. Lier les incidents de réalisation à une action corrective si nécessaire.

Acceptation — Nominal : une plainte passe de reçue à en traitement puis résolue avec réponse. Erreur ou limite : aucune clôture sans action ou justification ; le participant ne voit pas les plaintes des autres.

## QUA02 Suivre les améliorations

Priorité MVP. Une action porte origine, responsable, échéance, décision, réalisation et vérification d'efficacité. Les retours, réclamations et revues alimentent le registre.

Acceptation — Nominal : un support corrigé est relié à la réclamation d'origine. Erreur ou limite : réaliser une action ne la marque pas efficace sans contrôle documenté.

## QUA03 Gérer intervenants et veille

Priorité MVP. Conserver compétences, justificatifs et décisions d'habilitation des formateurs ; registre de veille avec source, date, analyse et impact. Suivre les obligations contractuelles des sous-traitants.

Acceptation — Nominal : une veille conduit à une nouvelle version du programme. Erreur ou limite : un justificatif expiré déclenche une alerte avant affectation ; une URL enregistrée seule ne prouve pas son exploitation.

Les délais de réponse à l'assistance et aux réclamations sont des engagements NeoPro à définir. Le MVP permet leur paramétrage et le suivi des dépassements. Le responsable qualité contrôle l'organisation réelle ; les documents logiciels ne remplacent pas les pratiques pédagogiques.

# 10 Droits et confidentialité

Principe commun : accès limité au rôle et au périmètre affecté. Le contrôle vaut dans les écrans, API, fichiers, exports et liens directs. Le refus ne doit révéler ni contenu ni métadonnées privées. Les cumuls de rôles sont explicites.

| **Rôle**                      | Droits fonctionnels                                                                                           | **Restrictions**                                                                                  |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Visiteur                      | Catalogue et demande publique                                                                                 | Aucun inscrit, résultat ou support privé.                                                         |
| Participant                   | Son parcours, ses remises, tentatives, présences et documents                                                 | Ressources communes autorisées seulement ; aucun dossier d'un pair.                               |
| Formateur ou tuteur           | Séances et participants affectés ; correction, suivi, validation de présence                                  | Pas de comptabilité ; informations d'aménagement utiles seulement.                                |
| Coordinateur                  | Programme, sessions, inscriptions, accès, planning et corrections motivées                                    | Pas de modification de règlement comptable.                                                       |
| Commercial                    | Demandes, offres, clients, places et statut administratif                                                     | Pas de réponses détaillées, devoirs ou données d'aménagement.                                     |
| Responsable qualité           | Preuves, évaluations nécessaires, réclamations, actions et exports internes                                   | Accès aux données sensibles seulement si habilité pour le dossier.                                |
| Entreprise cliente            | Phase 1 : portail limité aux demandes, sessions, participants et documents autorisés de son entreprise (P05). | Aucun score individuel, réponse ou échange privé par défaut ; aucun accès à une autre entreprise. |
| Administration et facturation | Pièces commerciales, factures, règlements, contacts de facturation                                            | Pas de corrigés ni de résultats individuels par défaut.                                           |
| Administrateur technique      | Gestion comptes, droits et exploitation ; accès de support exceptionnel tracé                                 | Les capacités techniques privilégiées sont assumées, limitées et surveillées.                     |

## SEC01 Isoler les données

Priorité MVP. Tester les périmètres entreprise, groupe, session et personne ; refuser par défaut. Un changement d'employeur ne transfère pas les accès historiques.

Acceptation — Nominal : un participant ouvre son propre PDF protégé. Erreur ou limite : modifier un identifiant dans une URL ou réutiliser un lien expiré échoue sans divulgation.

## SEC02 Gouverner conservation et exports

Priorité MVP. Définir par catégorie finalité, responsable, durée validée, archive, suppression et éventuel gel. Les demandes de suppression sont instruites ; journaliser les exports et appliquer les mêmes droits.

Acceptation — Nominal : un export conserve un manifeste de son périmètre. Erreur ou limite : aucune purge de tentatives par défaut et aucune suppression d'une preuve sous gel.

# 11 Écrans et communications

| **Écran**                     | **Contenu et actions principales**                                            |
| ----------------------------- | ----------------------------------------------------------------------------- |
| Catalogue public              | Filtres, modalités, devises, prix ou devis, programmes, dates et formulaires. |
| Demande et dossier commercial | Besoin, contacts, parties, devis, commande, conditions et pièces.             |
| Gestion de réalisation        | Version programme, planning, formateurs, places, groupes et checklist.        |
| Inscription individuelle      | Identité, prérequis, accès, progression, documents et historique.             |
| Accueil participant           | Mes formations, prochaines séances, travaux attendus et documents.            |
| Espace de formation           | Supports PDF, agenda, activités, examens, assistance et suivi personnel.      |
| Passage et correction         | Consignes, chronomètre, sauvegarde, remise, score, correction et recommencer. |
| Présences                     | Vue de séance, émargement personnel, contrôle formateur et anomalies.         |
| Qualité                       | Dossiers, manquants, réclamations, actions, veille et intervenants.           |
| Pilotage                      | Indicateurs filtrables et export suivant rôle et périmètre.                   |

## Documents et déclencheurs

Programme : à publication ; devis et conditions : à proposition ; convocation : après confirmation et planning validé ; feuille de présence : par séance ; attestations : selon DOC01 ; bilan : à clôture ; export qualité : à la demande d'un habilité. Chaque document conserve son modèle, sa version et son périmètre.

## NOT01 Envoyer au bon moment

Priorité MVP. Prévoir accusé de demande, validation, invitation, convocation, changement de séance, échéance, relance et disponibilité d'attestation. Chaque déclencheur possède destinataire, modèle, historique et résultat de distribution.

Acceptation — Nominal : retraiter un événement ne renvoie pas deux fois le même message. Erreur ou limite : une notification collective ne révèle pas les adresses des autres ; une erreur d'envoi reste visible.

## UX01 Rendre les parcours accessibles

Priorité MVP. Navigation clavier, libellés de champs, contrastes lisibles, focus visible, erreurs explicites et vues mobiles. Les supports PDF font l'objet d'un contrôle pédagogique d'accessibilité.

Acceptation — Nominal : un participant réalise inscription, quiz et émargement au clavier. Erreur ou limite : un chronomètre inaccessible ou une erreur indiquée seulement par couleur fait échouer la recette.

# 12 Indicateurs de pilotage

Toute vue affiche période, population, date d'extraction, numérateur et dénominateur. Dénominateur nul : « non calculable ». Pas de somme brute de MAD et EUR. Le dossier qualité publie seulement des indicateurs validés et non identifiants.

| **Indicateur**           | **Formule et périmètre proposé**                                                                                                                        | **Accès**                    |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| Conversion               | Demandes d'une cohorte ayant une commande confirmée / demandes qualifiées de cette cohorte. Date de situation affichée ; doublons et spam exclus.       | Commercial                   |
| Remplissage              | Places confirmées / capacité des sessions à capacité définie ; situation à la date choisie. Réservations affichées à part.                              | Coordination                 |
| Ventes et facturation    | Commandes confirmées HT d'une part ; factures validées HT moins avoirs d'autre part, par date et devise. Encaissements séparés.                         | Commercial et facturation    |
| Présence                 | Minutes validées / minutes planifiées applicables aux inscrits confirmés au démarrage. Séances annulées exclues ; départs en cours visibles.            | Coordination et qualité      |
| Complétion               | Inscrits ayant satisfait les critères / inscrits dont l'échéance de parcours est dans la période. Annulations avant démarrage exclues.                  | Pédagogie et qualité         |
| Abandon                  | Inscrits ayant commencé puis statut abandonné / inscrits ayant commencé dans la cohorte. Date de situation affichée.                                    | Pédagogie et qualité         |
| Acquis                   | Participants ayant atteint le seuil de l'évaluation dédiée / participants évalués. Couverture = évalués / éligibles. Examens blancs exclus.             | Formateur affecté et qualité |
| Examens blancs           | Premier, dernier et meilleur score par version et participant ; nombre de tentatives. Pas de moyenne mélangeant toutes les reprises et les personnes.   | Participant et pédagogie     |
| Satisfaction             | Réponses favorables / réponses valides à une question définie ; taux de réponse = répondants uniques / invités éligibles. Échelle et période affichées. | Qualité                      |
| Dossiers et réclamations | Dossiers sans pièce requise manquante / dossiers à clôturer ; réclamations ouvertes et hors délai, à date.                                              | Qualité                      |
| Marge prévisionnelle     | Vente HT moins coûts directs documentés, dans une devise commune explicitement convertie. Différée si coûts ou taux absents.                            | Gestion habilitée            |

## PIL01 Rendre les chiffres vérifiables

Priorité MVP. Chaque agrégat peut être rapproché de ses lignes autorisées. Une définition modifiée est versionnée ; publication publique approuvée par qualité.

Acceptation — Nominal : 10 réponses favorables sur 12 donnent 83,33 %, avec 12 réponses sur 20 invités. Erreur ou limite : un tableau ne présente pas 83,33 % comme représentant les 20 personnes.

# 13 Matrice qualité pour le MVP

Matrice de conception volontaire, non attestation de conformité. Repères d'indicateurs : RNQ, décret du 6 juin 2019 \[S4\]. Guide identifié par le ministère : V9 du 8 janvier 2024 \[S3\]. Le périmètre de référence envisagé est « actions de formation ». Aucun bilan de compétences, VAE ou apprentissage n'est inclus. Les choix ci-dessous sont proposés pour NeoPro ; l'applicabilité juridique reste à confirmer si une certification est engagée.

Lecture : R = retenu comme bonne pratique ; C = conditionnel ; H = hors périmètre envisagé. Chaque ligne lie processus, fonction, preuve, responsable et contrôle. La limite humaine figure dans la dernière colonne.

| **Critère et indicateur** | **Statut et fonction**           | **Preuve et responsable**                           | **Contrôle et limite hors logiciel**                                                        |
| ------------------------- | -------------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| C1 • 1                    | R • CAT01 catalogue              | Programme publié ; coordinateur                     | Champs et version ; exactitude de l'offre.                                                  |
| C1 • 2                    | R • PIL01 résultats              | Calcul daté ; qualité                               | Population et formule ; représentativité.                                                   |
| C1 • 3                    | C • information certification    | Fiche de la certification visée ; qualité           | À instruire selon offre ; ne pas assimiler tout examen à une certification professionnelle. |
| C2 • 4                    | R • ORG01 besoins                | Analyse signée ou validée ; commercial et pédagogie | Dossier renseigné ; pertinence de l'entretien.                                              |
| C2 • 5 et 6               | R • CAT02 conception             | Objectifs et programme ; coordinateur               | Versions cohérentes ; qualité pédagogique.                                                  |
| C2 • 7                    | C • correspondance certification | Matrice programme référentiel ; pédagogie           | Référence à jour ; habilitations externes.                                                  |
| C2 • 8                    | R • EVA01 positionnement         | Résultat initial et décision ; formateur            | Présence du bilan ; justesse du diagnostic.                                                 |
| C3 • 9 et 10              | R • ESP01 et ORG01               | Convocation et adaptations ; coordinateur           | Diffusion et suivi ; accompagnement réel.                                                   |
| C3 • 11 et 12             | R • EVA01 et PED02               | Acquis et relances ; pédagogie                      | Écarts suivis ; efficacité de l'accompagnement.                                             |
| C3 • 13 à 15              | H • alternance et apprentissage  | Aucune activité correspondante déclarée             | Réévaluer si l'offre évolue.                                                                |
| C3 • 16                   | C • préparation certification    | Conditions de présentation ; coordinateur           | Éligibilité à vérifier ; autorité tierce souveraine.                                        |
| C4 • 17 à 19              | R • ORG02 et ESP01               | Planning, affectations, supports ; coordinateur     | Disponibilité ; adéquation effective des moyens.                                            |
| C4 • 20                   | H • dispositif apprentissage     | Hors activité déclarée                              | N'empêche pas de désigner un contact accessibilité.                                         |

# 14 Registre des preuves et amélioration

| **Critère et indicateur** | **Statut et fonction**                | **Preuve et responsable**                               | **Contrôle et limite hors logiciel**                                  |
| ------------------------- | ------------------------------------- | ------------------------------------------------------- | --------------------------------------------------------------------- |
| C5 • 21 et 22             | R • QUA03 compétences                 | Dossiers intervenants et développement ; direction      | Validité et actions ; appréciation des compétences réelles.           |
| C6 • 23 à 25              | R • QUA03 veille                      | Source, analyse et décision ; qualité et pédagogie      | Impact tracé ; sélection et analyse humaines.                         |
| C6 • 26                   | R • ORG01 accessibilité               | Aménagement, contacts et orientation ; référent désigné | Accès restreint ; capacité réelle d'accompagnement.                   |
| C6 • 27                   | C • QUA03 sous-traitance              | Contrat, contrôle et suivi ; direction                  | Dossier et réalisation ; qualification du partenaire.                 |
| C6 • 28                   | C • formation en situation de travail | Partenaires et organisation si concernés ; coordinateur | Ne pas assimiler toute intra à une formation en situation de travail. |
| C6 • 29                   | H • apprentissage                     | Hors activité déclarée                                  | Revoir si le périmètre change.                                        |
| C7 • 30                   | R • EVA02 retours                     | Questionnaires et synthèse ; qualité                    | Parties interrogées ; interprétation des retours.                     |
| C7 • 31                   | R • QUA01 réclamations                | Dossier et réponse ; qualité                            | Échéance et clôture ; pertinence du traitement.                       |
| C7 • 32                   | R • QUA02 amélioration                | Action et vérification ; responsable nommé              | Efficacité documentée ; amélioration effective.                       |

## Structure de chaque preuve

Identifiant ; type ; formation et version ; session ou inscription concernée ; source ; auteur ; date de production ; version ; état de validation ; validateur ; confidentialité ; catégorie de conservation ; lien vers le fichier ou l'événement d'origine. Une nouvelle version conserve le lien avec la précédente.

## Dossier minimal proposé

Besoin et programme accepté ; éléments commerciaux pertinents ; liste des inscrits ; positionnement ; convocations ; affectations et moyens ; supports applicables ; présences ou traces d'activités adaptées ; évaluations des acquis ; recueil des retours ; attestations ; incidents et améliorations. Une pièce non applicable porte un motif, plutôt qu'un document vide.

Le statut « dossier complet » signifie uniquement que les pièces attendues par NeoPro sont présentes et validées. Il ne signifie ni certification Qualiopi ni validation par un financeur. Les besoins d'aménagement et réponses détaillées ne sont pas diffusés dans les exports clients par défaut.

# 15 Reprise des données et recette métier

## MIG01 Définir le périmètre indispensable

Priorité MVP. Lister contacts, offres actives, sessions futures ou en cours, inscriptions, soldes utiles, supports, résultats requis et pièces. Chaque lot porte source, cible, méthode, responsable et contrôle.

Acceptation — Nominal : les inscriptions en cours et leurs accès sont identifiés avant ouverture. Erreur ou limite : une source inconnue reste un manque déclaré ; aucune donnée n'est inventée.

## MIG02 Contrôler chaque reprise

Priorité MVP. Import ou saisie manuelle : conserver identifiant source, responsable, date, volumes et rapprochement. Vérifier liens, doublons, fichiers et montants par devise. Une donnée sans source fiable n'est pas présentée comme preuve historique.

Acceptation — Nominal : un échantillon manuel est vérifié par une seconde personne ; soldes réconciliés. Erreur ou limite : un import répété ne duplique pas le lot ; les écarts sont isolés et expliqués.

## MIG03 Décider de la bascule

Priorité MVP. La direction valide les données indispensables, les écarts acceptés et l'accès à l'archive avant ouverture. Reprise de code, configuration fonctionnelle et données restent trois décisions distinctes.

Acceptation — Nominal : un procès-verbal de reprise référence chaque contrôle. Erreur ou limite : une inscription active orpheline bloque l'ouverture du lot concerné.

## Contrôles de reprise par lot

| **Lot**                 | **Contrôle attendu**                                                                                              |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Contacts                | Distinguer personnes et entreprises, conserver pays et rôles ; traiter les doublons sans fusion aveugle.          |
| Formations et sessions  | Reprendre programmes, dates, modalités, intervenants et inscriptions liées.                                       |
| Supports et résultats   | Ouvrir les fichiers repris ; vérifier droits, scores et provenance ; signaler les versions historiques inconnues. |
| Commercial et financier | Rapprocher commandes et soldes par devise ; ne pas recréer automatiquement les écritures historiques.             |
| Historique archivé      | Index consultable, responsable, droits et durée validée ; aucun import du code ancien par défaut.                 |

La reprise des comptes exigera une activation sécurisée ; aucun mot de passe en clair ne doit être demandé ni stocké dans un fichier de migration. Les envois, relances et automatisations seront neutralisés pendant les futurs essais de reprise sur un environnement autorisé.

# 16 Scénarios de recette métier

Ces scénarios définissent la recette fonctionnelle. Leur exécution sera préparée à l'étape 3 puis réalisée sur un environnement de test autorisé. Ils ne constituent pas des tests déjà exécutés.

| **Test**                     | **Résultat observable attendu**                                                                                            |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| R01 • Intra MAD              | Forfait pour 10 places, 7 puis 3 noms, paiement différé autorisé, accès, présence, acquis et clôture ; onzième nom refusé. |
| R02 • Individuel EUR         | Demande, réservation, virement partiel puis solde, décision d'accès et convocation ; toutes les pièces restent en EUR.     |
| R03 • eLearning              | Accès sans session, PDF, quiz, examen réussi puis repassé, correction et deux tentatives conservées.                       |
| R04 • Mixte                  | Deux séances et trois activités ; présence partielle et progression distinctes ; attestation conforme aux preuves.         |
| R05 • Report et remplacement | Historique, nouvelle inscription, place libérée ; aucun transfert de score entre personnes.                                |
| R06 • Confidentialité        | Participant A ne lit pas les réponses, fichiers, exports ou liens de B ; entreprise A ne lit pas le dossier de B.          |
| R07 • Dossier qualité        | Export autorisé avec index, versions et manquants ; données confidentielles exclues de la version client.                  |
| R08 • Temps et erreurs       | Recharge, coupure réseau, double clic, échéance serveur et réponse tardive ; score final stable.                           |
| R09 • Migration              | Reprise manuelle et import contrôlés ; pièces accessibles ; volumes, relations et finances réconciliés.                    |

# 17 Décisions et références

## Décisions validées le 15 octobre 2026

Le périmètre et le séquencement sont acceptés : phase 1 P01 à P08, phase 2 P09 à P16, puis P17 à P20 sous validation complémentaire. Les règles du socle restent applicables, dont QCM exact sans points partiels, correction avec explications si renseignées, absence de certificat automatique d'examen blanc et ouverture manuelle des accès selon les conditions commerciales.

## Paramètres à fixer avant mise en service

Entité facturante et devise comptable ; tarifs MAD/EUR ; fiscalité et mentions validées ; coordonnées bancaires ; durées d'accès ; délai de réservation ; conditions d'annulation ; fenêtres d'émargement et niveau de signature ; responsabilités qualité ; conservation ; délai d'assistance ; volumes, concurrence, objectifs de service et échéance de lancement. Aucun de ces paramètres ne doit être deviné au déploiement.

## Passage à l'étape suivante

La prochaine étape de conception est la couverture prouvée Odoo 20 Community, puis l'analyse des écarts, l'architecture modulaire, les intégrations, le modèle technique, le backlog estimé, le plan détaillé de reprise et la recette technique, organisés selon les phases du chapitre 18. Prévoir environnements séparés, sauvegardes hors serveur, restauration testée, supervision, secrets, logs et rollback. Le dimensionnement dépendra des volumes. La compatibilité Odoo.sh reste un critère de maintenabilité, malgré la cible OVH. Aucun prototype ni déploiement n'est autorisé par cette mise à jour.

## Références consultées le 30 septembre 2026

S1 • Odoo, documentation 19.0, Scoring surveys. Fonctions documentées : score, correction, tentatives et option Certification.  
<https://www.odoo.com/documentation/19.0/applications/marketing/surveys/scoring.html>

S2 • Odoo, documentation 19.0, Create surveys. Durée limite et options de notation.  
<https://www.odoo.com/documentation/19.0/applications/marketing/surveys/create.html>

S3 • Ministère du Travail, page Référentiel national qualité et guide de lecture Qualiopi. La page officielle consultable par recherche référence le guide V9 du 8 janvier 2024.  
<https://travail-emploi.gouv.fr/referentiel-national-qualite-guide-de-lecture-qualiopi>

S4 • Légifrance, annexe du décret 2019-565 du 6 juin 2019, version initiale publiée au Journal officiel du 8 juin 2019 : repérage des indicateurs.  
<https://www.legifrance.gouv.fr/jorf/article_jo/JORFARTI000038565276>

Limites documentaires : le PDF intégral du guide V9 et la version consolidée du RNQ au 30 septembre 2026 n'ont pas pu être lus directement. La matrice est donc provisoire et devra être confrontée aux précisions officielles à jour avant tout usage de certification. Les fonctions Odoo 20 Community restent non vérifiées ; les sources 19 ne sont pas une preuve de disponibilité dans l'édition cible.

# 18 Séquencement et périmètre de livraison

Décision du 15 octobre 2026. Les propositions P01 à P20 sont intégrées aux spécifications avec le séquencement ci-dessous. Le lancement comprend le socle MVP des chapitres 1 à 17 et P01 à P08. Les ajouts ultérieurs ne reportent aucune obligation déjà prévue au lancement.

## Phase 1 au lancement

P01 Double parcours commercial ; P02 Demande intra guidée ; P03 Fiche formation enrichie ; P04 Aperçu pédagogique ; P05 Portail entreprise limité ; P06 Dossier intra personnalisé ; P07 Navigation des examens blancs ; P08 Analyse par thème.

## Phase 2 après la phase 1

P09 Parcours de plusieurs formations ; P10 Diagnostic d'orientation ; P11 Plan de mise en pratique ; P12 Projet pratique évalué ; P13 Réservation de tutorat ; P14 Avis vérifiés et cas clients ; P15 Comparaison et sélection ; P16 Statuts publics des sessions et alertes.

## Suite conditionnée à une validation

P17 Accords et budgets entreprise ; P18 Environnements pratiques ; P19 Assistant pédagogique ; P20 Attestation vérifiable. Leur description constitue un périmètre envisagé. Leur réalisation exige une validation explicite après examen des besoins, coûts, sécurité et résultats des phases précédentes.

Les phases de livraison ci-dessus sont distinctes des étapes de travail du projet : spécification, architecture, développement et déploiement. Le séquencement ne fixe aucune date ni aucun budget et n'autorise pas le démarrage automatique des travaux.

Invariants : marché francophone mondial ; intraentreprise prioritaire ; inscriptions individuelles ensuite ; MAD et EUR ; virement bancaire sans paiement en ligne ; supports surtout PDF ; émargement électronique dès le lancement avec papier au cas par cas ; reprise Odoo 19 indispensable ; absence de certification Qualiopi effective.

Les exigences ci-dessous complètent les règles existantes. SEC01, SEC02, NOT01 et UX01 s'appliquent à tous les ajouts : droits par périmètre, conservation définie, notifications tracées et interfaces accessibles. Les nouveaux tests constituent des critères de recette, pas des résultats déjà obtenus.

# 19 Phase 1 Parcours commercial et catalogue

## P01 Deux parcours commerciaux

L'accueil donne la priorité à « Former mon équipe » et propose « Me former ». Chaque parcours mène à un catalogue et à un appel à l'action adaptés : demande intra ou inscription/demande individuelle. La langue de référence est le français ; le pays et la devise ne sont pas déduits de la langue. Rattachement : CAT01, COM01.

Acceptation — Nominal : les deux parcours aboutissent au bon formulaire en conservant la formation sélectionnée. Limite : changer de parcours ne crée ni inscription ni accès pédagogique et ne perd pas silencieusement les données saisies.

## P02 Demande intra guidée

Le demandeur choisit catalogue, adaptation ou sur mesure et décrit objectifs, niveau, effectif, pays, dates souhaitées, modalité et outils disponibles. Il peut joindre un cahier des charges et demander un échange avec un conseiller. Le commercial reçoit une demande qualifiée, puis prépare un devis MAD ou EUR ; aucune disponibilité ni commande n'est confirmée automatiquement. Rattachement : COM01, ORG01.

Acceptation — Nominal : la demande et ses pièces sont retrouvées dans le dossier commercial avec accusé de réception. Erreur : champs indispensables absents ou pièce interdite empêchent la soumission avec indication claire ; les pièces ne sont jamais publiques.

## P03 Fiches formation enrichies

La fiche présente résultats attendus, exercices ou livrables, profils des intervenants, durée d'accès aux supports, modalités et éléments inclus. Elle distingue explicitement formation, préparation, examen blanc et éventuel examen officiel, en précisant si celui-ci est inclus. Les informations non confirmées sont signalées avant publication. Rattachement : CAT01, DOC02.

Acceptation — Nominal : programme public et fiche affichent les mêmes version, modalités et inclusions. Erreur : une fiche ne présente pas un examen blanc comme une certification officielle et ne promet pas une certification Qualiopi inexistante.

## P04 Aperçu pédagogique public

Une formation peut proposer un extrait PDF et un mini-quiz de démonstration, sélectionnés et validés pour publication. Ces contenus sont séparés des supports privés et des questions d'évaluation. La démonstration ne compte pas dans la progression ni dans les résultats de formation. Rattachement : CAT01, ESP01.

Acceptation — Nominal : un visiteur consulte l'extrait et obtient le retour prévu du quiz de démonstration. Erreur : les liens ou identifiants de démonstration ne permettent pas d'ouvrir un PDF privé, un corrigé ou une banque de questions.

# 20 Phase 1 Entreprises et examens blancs

## P05 Portail entreprise limité

Un contact expressément habilité suit les demandes et sessions de son entreprise, transmet les noms des participants et télécharge les documents autorisés. NeoPro contrôle les inscriptions et l'ouverture des accès. L'habilitation ne découle pas du domaine de messagerie. Les réponses, scores individuels et échanges privés sont exclus par défaut. Rattachement : INS01 à INS03, SEC01, DOC01.

Acceptation — Nominal : un contact voit uniquement ses dossiers et la liste autorisée. Erreur : accès croisé entre entreprises refusé, y compris par URL ou export ; une nomination ne donne pas immédiatement accès au cours.

## P06 Dossier intra personnalisé

Chaque réalisation intra peut porter une variante rattachée à une version du programme standard : objectifs du client, cas métiers, documents confidentiels et consignes. L'accord du client sur le périmètre et la version est enregistré avant confirmation de ce contenu. Une modification ultérieure conserve la version précédente et appelle une nouvelle validation. Rattachement : ORG01, DOC02.

Acceptation — Nominal : la réalisation utilise la variante approuvée avec auteur, date et validation. Erreur : modifier une variante ne modifie pas le catalogue ni le dossier d'un autre client ; un document confidentiel reste réservé aux habilités.

## P07 Navigation des examens blancs

Ajouter palette des questions, marquage « à revoir », distinction répondu/non répondu, récapitulatif et confirmation de remise. La liste et l'ordre restent fixés par le créateur. Le temps serveur continue pendant navigation ou rechargement ; à expiration, soumettre les réponses enregistrées. Aucune correction avant la fin. Rattachement : EXA01 à EXA06.

Acceptation — Nominal : revenir à une question conserve réponse et marquage ; la remise affiche score et correction. Erreur : recharger ne rallonge pas le temps ; une remise répétée ne crée pas une seconde tentative. Les nouvelles tentatives restent illimitées.

## P08 Résultats par thème

Associer chaque question à un thème principal ou objectif pour afficher points obtenus, points possibles et score par thème, puis des liens vers les ressources de révision autorisées. Conserver le classement et le barème dans la version de tentative. Un thème sans question est indiqué non évalué. Rattachement : EXA04, EXA06, PIL01.

Acceptation — Nominal : la somme des points par thème correspond au total et le corrigé renvoie aux bonnes ressources. Erreur : absence de thème ou division par zéro ne produit pas de score trompeur ; aucune ressource inaccessible n'est divulguée. Le résultat ne garantit aucune réussite à un examen officiel.

# 21 Phase 2 Parcours et mise en pratique

## P09 Parcours de plusieurs formations

Composer un parcours métier avec ordre conseillé ou obligatoire, prérequis, durée totale et prix global éventuel. Chaque formation conserve son inscription, ses droits et sa progression ; le parcours agrège ces données. Définir la politique commerciale du parcours avant vente, dans une seule devise par offre. Rattachement : CAT01, INS02, PED01.

Acceptation — Nominal : le participant suit les étapes et retrouve les acquis des formations déjà suivies selon les équivalences validées. Erreur : un prérequis bloquant non satisfait interdit l'étape concernée ; aucun double accès ou double comptage n'est créé.

## P10 Diagnostic d'orientation

Proposer avant achat un questionnaire facultatif orientant vers niveau, formation ou parcours, avec explication de la recommandation et possibilité de contact humain. Il ne remplace ni le positionnement pédagogique ni la validation des prérequis. Conserver les réponses uniquement selon finalité et durée définies. Rattachement : COM01, ORG01.

Acceptation — Nominal : des réponses complètes produisent une recommandation compréhensible. Limite : des réponses insuffisantes ou contradictoires conduisent à demander conseil, sans admission automatique ni promesse de résultat.

## P11 Plan de mise en pratique

À la fin de la formation, définir des actions à 30 et 60 jours avec échéances, rappels, preuves facultatives et retour du formateur selon la prestation. Le commanditaire reçoit seulement la synthèse convenue et autorisée. Cet ajout complète l'évaluation différée du socle, qui reste disponible dès le lancement. Rattachement : EVA02, PED02.

Acceptation — Nominal : une action passe de prévue à réalisée avec preuve et retour tracés. Erreur : rappels arrêtés lorsque l'action est clôturée ; aucune preuve privée n'est transmise automatiquement à l'employeur.

## P12 Projet pratique évalué

Ajouter des projets avec livrable attendu, grille de critères, niveaux de maîtrise, dépôt de versions, demandes de révision et validation par un évaluateur habilité. La grille utilisée est conservée avec l'évaluation. Les remises simples du socle ne sont pas différées par cet ajout. Rattachement : PED01, PED02, DOC02.

Acceptation — Nominal : un projet est déposé, évalué par critère puis validé après éventuelle révision. Erreur : une nouvelle grille ne réécrit pas une évaluation passée ; le participant ne peut valider lui-même son projet.

# 22 Phase 2 Accompagnement et commercialisation

## P13 Réservation de tutorat

Proposer des créneaux individuels ou collectifs en indiquant durée, nombre inclus, disponibilités et conditions d'annulation. Contrôler quota et capacité avant confirmation. L'accompagnement de base PED02 reste au lancement ; seule la réservation autonome est différée. Les modalités de synchronisation calendrier seront déterminées en architecture.

Acceptation — Nominal : une réservation confirmée consomme le quota prévu et notifie les parties. Erreur : deux demandes simultanées ne dépassent pas la capacité ; une annulation applique la règle de restitution annoncée.

## P14 Avis vérifiés et cas clients

Inviter des participants dont la participation est vérifiée à publier un avis, après consentement et modération tracée. Les cas clients nécessitent validation du contenu et autorisation de publication. Afficher le contexte et la date utiles. Les évaluations internes de satisfaction ne deviennent pas publiques par défaut. Rattachement : EVA01, QUA01, SEC02.

Acceptation — Nominal : un avis autorisé est publié avec son rattachement vérifié. Erreur : un avis non validé, une identité non autorisée ou un cas client confidentiel restent privés ; les retraits sont traités et tracés.

## P15 Sélection et comparaison

Permettre de sélectionner et comparer plusieurs formations selon objectifs, niveau, durée, modalités et prix disponibles, puis de demander un devis sur cette sélection. Afficher clairement les offres sur devis et la devise de chaque prix. Aucun paiement en ligne n'est ajouté. Rattachement : CAT01, COM01, COM02.

Acceptation — Nominal : la demande reprend les formations choisies et la devise commerciale retenue. Erreur : aucun total ne mélange MAD et EUR et aucun prix manquant n'est assimilé à zéro ; une formation retirée est signalée.

## P16 Statuts publics et alertes de session

Afficher les sessions ouvertes, confirmées ou complètes selon les états validés et proposer une alerte volontaire pour de nouvelles dates. Réserver la mention « départ garanti » à une décision explicite de NeoPro. Les alertes respectent les choix du destinataire ; le planning et les changements de séance du socle restent au lancement. Rattachement : INS01, ORG02, NOT01.

Acceptation — Nominal : une session complète n'accepte plus de confirmation au-delà de sa capacité ; une nouvelle date déclenche l'alerte attendue. Erreur : désabonnement effectif, absence de doublons et aucune garantie déduite automatiquement du seul nombre d'inscrits.

# 23 Fonctionnalités soumises à validation ultérieure

P17 à P20 ne font partie ni de la phase 1 ni de la phase 2. Les critères ci-dessous cadrent leur étude ; l'autorisation de réalisation devra être explicite et identifier le périmètre retenu ainsi que les conditions d'exploitation.

## P17 Accords et budgets entreprise

Gérer accords négociés, tarifs, périodes de validité, enveloppes et consommation par entreprise. Séparer MAD et EUR ; tracer engagements, consommation, annulations et restitutions. Définir les règles d'imputation avant activation. Aucun abonnement illimité n'est présumé. Dépend de P05 et des règles commerciales COM02 et COM03.

Acceptation — Nominal : une inscription consomme le montant autorisé et le solde est explicable. Erreur : dépassement bloqué ou soumis à dérogation tracée ; aucun mélange de devises ou remboursement non justifié.

## P18 Environnements de travaux pratiques

Prévoir, pour les formations qui le nécessitent, des environnements pratiques externes en priorité, avec accès par apprenant, isolation, durée de disponibilité, remise à zéro et extinction. Valider coûts, support, données autorisées et fournisseur avant toute intégration. Dépend des objectifs de formation et de la gestion des accès.

Acceptation — Nominal : un participant ouvre son environnement durant la période prévue puis l'accès expire. Erreur : aucun accès au travail d'un autre apprenant ; une panne ou un dépassement de budget entraîne la procédure prévue sans perte silencieuse des travaux.

## P19 Assistant pédagogique

Limiter les réponses aux sources pédagogiques autorisées pour le participant, avec références au document et à la page quand disponibles. Prévoir signalement d'incertitude et recours humain. Interdire la divulgation de corrigés pendant une épreuve ; définir conservation des échanges, évaluation de qualité et coûts avant activation.

Acceptation — Nominal : une question reçoit une réponse fondée sur un support accessible et une référence vérifiable. Erreur : sans source suffisante, l'assistant le signale ; aucune réponse ne révèle un support client confidentiel ou un corrigé protégé. Il ne décide pas d'une validation pédagogique.

## P20 Attestation vérifiable

Ajouter aux attestations retenues un QR code ou lien de vérification vers les seules informations nécessaires, avec gestion de validité, remplacement et révocation. Valider les données exposées avant publication. La vérification atteste l'authenticité du document ; elle ne confère aucune certification officielle ni Qualiopi. Rattachement : DOC01, SEC02.

Acceptation — Nominal : le vérificateur retrouve le statut du document authentique. Erreur : identifiant inconnu ou attestation révoquée ne sont pas présentés comme valides ; la page publique ne donne pas accès au dossier pédagogique.

# 24 Intégration et recette des ajouts

## Modèle fonctionnel et écrans

Phase 1 : compléter la demande commerciale et la fiche formation ; ajouter contenu public de démonstration, habilitation entreprise, variante de programme et validation client. Étendre la tentative avec réponses enregistrées, marquages et thèmes versionnés. Prévoir accueil à deux entrées, demande guidée, portail entreprise et résultats thématiques. Les objets existants restent la source des inscriptions, droits et résultats.

Phase 2 : prévoir parcours et étapes, diagnostic, plan d'actions, projet et grille, créneau et réservation, autorisation de publication, sélection de formations et abonnement aux alertes. Les écrans et droits suivent les acteurs définis dans chaque exigence. P17 à P20 feront l'objet d'une conception détaillée après leur validation.

## Dépendances et reprise Odoo 19

La reprise des clients, contacts, formations, sessions, inscriptions, documents et historiques nécessaires demeure un prérequis du lancement selon MIG01 à MIG03. Rattacher chaque donnée reprise à sa source et contrôler les droits avant exposition dans P05. Toute habilitation entreprise doit être confirmée ; aucune ouverture de portail en masse sur simple correspondance de domaine de messagerie.

Pour les données nouvelles absentes d'Odoo 19, prévoir enrichissement manuel contrôlé : contenus des fiches, extraits publics, variantes, thèmes et liens de révision. Les anciens examens sans classement thématique sont affichés sans analyse par thème ou enrichis par une opération validée ; ne pas inventer rétroactivement des résultats. Conserver le journal des reprises manuelles et automatiques.

## Vérification du candidat Certification Odoo

En architecture, démontrer sur la version cible Community le choix fixe des questions, le chronométrage serveur, la reprise des réponses, la remise à expiration, le score et la correction finale, les tentatives illimitées, les versions et l'isolation des droits. Vérifier aussi la palette, le marquage et l'analyse par thème P07/P08. Identifier explicitement ce qui relève du standard, d'un paramétrage, d'un module tiers ou d'un développement. Les références Odoo 19 du chapitre 17 ne constituent pas une preuve de couverture Odoo 20.

## Critères de sortie par phase

Phase 1 : réussir la recette du socle R01 à R09 et les cas nominaux et limites de P01 à P08 ; prouver l'isolation du portail entreprise, le parcours complet de demande intra, la confidentialité des variantes et la fiabilité des examens. La reprise et l'émargement électronique restent des conditions de lancement. Tout écart bloquant est corrigé ou fait l'objet d'un arbitrage explicite avant mise en service.

Phase 2 : réussir P09 à P16 et les régressions ciblées sur accès, inscription, facturation, planning, évaluations et notifications. Tester en particulier capacités et quotas concurrents, consentements, désabonnement et cohérence des devises. La livraison de la phase 2 ne déclenche pas automatiquement P17 à P20.

Suite : consigner la décision de validation de chaque fonctionnalité P17 à P20, puis finaliser sa conception et sa recette avant réalisation. Les tests décrits dans cette spécification restent à exécuter sur la solution retenue.