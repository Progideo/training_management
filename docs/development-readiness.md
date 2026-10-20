# S01 — Catalogue standard et programmes versionnés

État au 20 octobre 2026. Références : [pilotage #3](https://github.com/Progideo/training_management/issues/3),
[S01 #11](https://github.com/Progideo/training_management/issues/11),
[architecture #8](https://github.com/Progideo/training_management/issues/8),
[décisions #10](https://github.com/Progideo/training_management/issues/10).

## Références et décisions validées

La spécification v2.0 du 15 octobre et le prompt maître sont portés par la
[PR #41](https://github.com/Progideo/training_management/pull/41), toujours ouverte
lors de la vérification. Les copies ont été comparées aux sources du projet :
empreintes identiques. Aucun changement de spécification, fusion de #41 ou
réactivation de l'audit historique Odoo 19 n'est implicite.

Le 20 octobre 2026, l'utilisateur a explicitement validé dans la conversation :

- Un catalogue pédagogique distinct des produits commerciaux Odoo, des versions
  figées dès validation, des droits coordinateur/lecteur et l'isolation par société.
- Les **programmes standards** sont au cœur du catalogue et destinés à la
  publication publique. Leur gestion interne est S01 ; leur site public vient
  avec l'intégration Website, sans les réserver à un client particulier.
- Les variantes client P06 seront privées et rattachées au standard, sans
  réécriture de celui-ci. Elles ne sont pas implémentées par S01.
- Produits, devis et factures standards seront reliés lors de l'intégration
  commerciale. Pas de second référentiel comptable.
- CRM, Événements et Website Sale seront inclus dans la suite. Leur installation
  immédiate n'a pas été effectuée : rôle, dépendances et articulation avec les
  sessions/inscriptions doivent être vérifiés avant cet incrément. Le paiement
  en ligne reste exclu du lancement ; le parcours demeure devis/virement.

La préférence portail du 17 octobre dans #8 est conservée pour participants et
représentants. Aucun compte externe n'est converti en compte interne par S01.
L'utilisateur l'a confirmée le 20 octobre : le choix portail/interne doit être
validé **pour chaque profil**, en privilégiant le portail pour les personnes
extérieures à la société exploitante. Les limites doivent être prouvées action
par action avant un arbitrage ; aucune généralisation à partir du seul
statut « externe ». Cela concerne aussi les formateurs et tuteurs externes.

Matrice de travail à valider lors de chaque intégration ; les orientations
ci-dessous ne sont pas une preuve de couverture du portail standard :

| Profil | Orientation | Vérification décisive |
| --- | --- | --- |
| Visiteur | Public, sans compte | Catalogue et demande seuls ; aucun document privé |
| Participant | Portail privilégié | Supports, remises, examens, émargement et documents personnels |
| Représentant d'entreprise cliente | Portail privilégié (P05) | Habilitation explicite, participants/documents autorisés, aucun score individuel par défaut |
| Formateur ou tuteur externe | Portail à étudier en priorité | Séances affectées, correction, suivi, validation des présences et pièces utiles |
| Formateur ou tuteur salarié | À valider selon ses actions | Même périmètre métier ; statut salarié insuffisant pour attribuer des droits larges |
| Coordinateur, lecteur du catalogue | Interne pour S01, validé | Catalogue uniquement selon le rôle ; autres fonctions à valider par incrément |
| Commercial | Interne envisagé | Actions CRM/devis réellement nécessaires ; cas d'un intervenant externe à arbitrer |
| Responsable qualité | À valider selon son statut et ses actions | Preuves et exports nécessaires, habilitation spécifique aux données sensibles |
| Administration et facturation | Interne envisagé pour la gestion | Pièces, factures, règlements ; aucune ouverture des résultats pédagogiques |
| Administrateur technique | Interne privilégié | Administration et support exceptionnel tracé |

Pour chaque profil, consigner les actions requises, ce que couvre le standard
Odoo exact, les extensions nécessaires, les limites de confidentialité et le
coût de maintenance. Tester avec le véritable type de compte et les liens
directs avant de soumettre le choix important. Toute exception à la préférence
portail pour un externe doit être justifiée et validée explicitement.

## Cible vérifiée et architecture S01

Le conteneur répond `Odoo Server 20.0-20261015` ; paquet `20.0.20261015`.
Image : `odoo@sha256:61e3c71b0503c5f658e604c3e340bede20b97d05f726179fa006eae50a32fd23`.
Le fichier `release.py` déclare le commit Community
`49529f034a60e4e9838e08e0a5616e5f2f38c601`. Python 3.12.3, PostgreSQL 18.6.
Les chemins, empreintes et observations sont dans [native-coverage.md](native-coverage.md).

L'addon `addons/training_management/` dépend uniquement de `base` (version
installée `20.0.1.3`, licence déclarée LGPL-3). Le code spécifique reste
LGPL-3.0-only selon LICENSE/COPYING ; la valeur de manifest Odoo est `LGPL-3`.
Aucun code standard n'est copié dans le dépôt et aucun cœur Odoo n'est modifié.

- `training.course` : identité du catalogue standard, société exploitante et
  archivage. Les contacts restent des `res.partner` standards.
- `training.program.version` : titre et référence propres, objectifs, public,
  prérequis, contenu, durée, modalité, langue, méthodes, évaluation, conditions
  d'accès, contact et consignes d'accessibilité. Tarification « sur devis »
  uniquement dans S01 ; MAD/EUR et tarifs seront gérés par les produits/devis.
- Brouillon → validé → publié → retiré. Les champs requis sont contrôlés à la
  validation et à la publication. « Publié » n'ouvre aucun site ou accès public.
- Contenu immuable dès validation, y compris via écriture directe ou traduction.
  Le bouton « Nouvelle version » demande la référence dans une fenêtre native,
  puis « Créer le brouillon » copie le programme avec l'ORM Odoo et ouvre sa fiche.
  Tous les champs traduisibles reprennent leurs traductions, indépendamment de la
  langue de session. Annuler la fenêtre ne crée aucun programme.
  Unicité en base par formation ; aucune séquence `max + 1` vulnérable.
- Auteur et date de chaque transition sont générés côté serveur. Les champs
  d'audit et les valeurs par défaut du contexte ne permettent pas de contourner
  la validation. Une transition répétée vers le même état conserve sa date.
- Les versions validées ne peuvent pas être supprimées ; la formation est
  archivée. Changer la société d'une formation possédant des versions est refusé.
- Les changements utilisent `lock_for_update()` natif Odoo 20, après contrôle
  d'accès. Une écriture simultanée est refusée par le verrou natif, sans SQL
  spécifique, `sudo()` ou commit manuel dans le code métier.
- Les groupes utilisent `res.groups.privilege`, les autorisations et restrictions
  `ir.access` dans `security/ir.access.csv` : mécanismes du code exact cible.
  Les anciens modèles `ir.rule`/`ir.model.access` ne sont pas utilisés.
- Aucune route, pièce jointe pédagogique, diffusion par chatter ou notification
  spécifique n'est introduite dans S01. Le module prépare le catalogue interne.

## Droits S01

| Profil | Actions | Limites |
| --- | --- | --- |
| Coordinateur | Créer/modifier les brouillons, valider, publier, retirer, consulter | Sociétés autorisées ; contenu validé immuable ; suppression des seuls brouillons |
| Lecteur | Lire/rechercher le catalogue | Sociétés autorisées ; aucune écriture ou transition |
| Interne sans rôle, portail, public | Aucun accès aux deux modèles | Refus côté serveur, indépendamment des menus |

L'export nécessite **également** la permission Odoo native d'export, attribuée
séparément par l'administrateur. Le module ne l'accorde pas globalement.
Les essais d'export utilisent de vrais utilisateurs restreints avec cette
permission, puis vérifient le refus hors société. Les administrateurs techniques
conservent les capacités privilégiées normales d'Odoo.

Les groupes sont cumulables conformément aux règles natives. L'isolement client,
session et participant sera testé avec les objets et portails correspondants ;
S01 ne prétend pas couvrir ces parcours encore absents.

## Matrice de couverture préalable

Lecture : chaque ligne est une **hypothèse à examiner**, et non une couverture
démontrée. « Configuration » désigne une piste ; « extension/spécifique »
désigne le travail potentiel après inspection du standard exact.
Les modules installés ont été contrôlés en SQL le 20 octobre. Les preuves
S01 et les essais Surveys figurent dans [les résultats](native-coverage.md).
Les autres lignes restent des pistes, pas une couverture démontrée.

| Exigences | Standard candidat | Configuration à examiner | Extension / spécifique envisagé | Preuve à produire / incertitude |
| --- | --- | --- | --- | --- |
| CAT01–02 | Produits, Website, eLearning | Modalités, catégories, publication | Versions pédagogiques figées, contrôles de publication, PDF lié à la version | S01 implémenté et testé : catalogue interne, V1/V2 et droits ; site, PDF et catégories restent à réaliser |
| COM01 | Ventes ; CRM à évaluer | Parties commerciales, devis | Demande qualifiée, idempotence et rattachements | Ne pas imposer CRM sans démonstration |
| COM02–03 | Ventes, facturation, devises | MAD/EUR, tarifs indépendants, virement | Contrôles de révision et rapprochement si écarts | Vente et facture par devise, acomptes, doublon de référence |
| INS01–02 | Ventes ; Event à comparer | Réservations, délais, capacité | Places non nominatives, registre unique, contraintes concurrentes | Dernière place, homonymes, double confirmation |
| INS03–05 | Utilisateurs, portail, eLearning | Périodes et autorisation manuelle | Politique d'accès, report/remplacement, prolongation motivée | Vente seule sans accès, révocation, historiques |
| ORG01–02 | Contacts, calendrier | Ressources et fuseaux | Dossier restreint, séances, conflits et dérogations | DST, concurrence de réservation, secret des aménagements |
| ESP01, PED01–02 | eLearning, portail, pièces jointes | Activités et progression | Vue unifiée, remises privées, tutorat et relances | Accès portail réel, fichiers directs, critères de complétion |
| EXA01–06 | Surveys / Certification | Questions fixes, notation, temps, répétitions | Seulement écarts prouvés : versionnement, échéance, barème, sauvegarde | Écarts démontrés dans native-coverage.md ; intégration non décidée |
| PRE01–03 | Authentification, pièces jointes | Fenêtres et modes papier/électronique | Présences, déclaration horodatée, validation distincte, révisions | Pas de double compte, ni antidatage, ni signature pour autrui |
| DOC01–02 | Rapports QWeb, pièces jointes | Modèles et destinataires | Éligibilité, versions, index de clôture et exports filtrés | Rapport et fichier refusés hors périmètre |
| EVA01–02 | Surveys | Finalité, destinataires, relances | Versions, règles de complétion, anonymat selon écarts | Risque de réidentification et petits effectifs |
| QUA01–03 | Contacts, activités à évaluer | Responsables, délais | Réclamations, actions, habilitations, veille | Confidentialité et preuve d'efficacité distincte de réalisation |
| SEC01–02 | Groupes, ACL, règles d'enregistrement | Rôles, sociétés, politique de conservation | Mandats explicites, exports tracés, gels | Refus ORM, routes, fichiers, métadonnées et notifications |
| NOT01 | Messages, modèles de courriel | Déclencheurs et destinataires | Déduplication et journal selon couverture | Rejeu sans nouvel envoi, aucune fuite collective |
| UX01 | Vues natives, QWeb | Traductions et libellés | Corrections d'accessibilité nécessaires | Recette mobile/clavier réelle |
| PIL01 | Agrégations et vues natives | Période, population | Indicateurs métier avec dénominateurs et provenance | Réconciliation, zéro dénominateur, devises séparées |
| MIG01–03 | Imports et identifiants externes à étudier | Correspondances contrôlées | Reprise distincte, journal, réconciliation et activation | Essai autorisé, rejeu, fichiers et droits ; audit historique suspendu |
| P01 | Website | Deux parcours | Conservation du contexte entre parcours | Pas d'inscription ni accès implicite |
| P02 | Website, Ventes | Champs et accusé | Formulaire intra, pièces privées et doublons | Validation serveur, pièce interdite, visibilité |
| P03 | Catalogue et programme | Présentation des inclusions | Fiche enrichie liée à la version | Cohérence PDF/site, pas de certification annoncée à tort |
| P04 | Website, Surveys | Sélection explicite des extraits | Séparation de la démonstration et du privé | Liens directs sans accès aux supports/corrigés privés |
| P05 | Portal, Ventes | Comptes et délégations | Dossier entreprise, nominations contrôlées | Mandats révoqués, interentreprises, scores exclus |
| P06 | Programme versionné | Approbation client | Variante privée par réalisation, historique | Ne modifie ni catalogue ni autre dossier |
| P07 | Surveys | Navigation et remise à examiner | Palette, marquage, sauvegarde si absents | Rechargement, expiration, remise double, clavier |
| P08 | Surveys | Thèmes et ressources à examiner | Classement et barème figés par tentative | Total réconcilié, thème non évalué, ressource autorisée |

## Installation et recette

Le dossier à ajouter à `addons_path` est `addons/`, parent du module valide.
L'installation en environnement utilisateur reste une étape séparée ; les essais
ont utilisé exclusivement un répertoire et des bases temporaires. La configuration
courante et la base `neopro_dev` n'ont pas été modifiées par ces essais.

Recette après installation sur une base autorisée :

1. Activer le français et attribuer « Coordinateur des formations » à un
   utilisateur interne de test ; attribuer « Lecteur du catalogue » à un autre.
2. Dans **Formations → Formations standards**, créer et enregistrer une formation.
   Cliquer sur **Versions de programme**, puis **Nouveau** pour créer V1 dans sa
   propre fiche. La formation et le titre sont préremplis. Enregistrer, quitter
   et rouvrir la fiche pour vérifier la persistance avant toute validation.
3. Vérifier que les informations incomplètes bloquent la validation. Compléter
   les champs, valider et publier ; constater auteur/date et contenu figé.
4. Sur une source possédant des objectifs distincts en français et anglais,
   cliquer sur « Nouvelle version », saisir V2 puis « Créer le brouillon ».
   Vérifier après relecture les deux traductions, l'état brouillon et l'absence
   d'historique de validation. Modifier le contenu de V2 et vérifier que V1 reste
   inchangée. Refaire la copie depuis l'autre langue de session avec une référence
   distincte ; retirer V1 si nécessaire.
5. Vérifier lecture seule, refus hors société et refus pour un compte portail.
   Les programmes sont destinés au futur site public, mais restent internes ici.
6. Sur une base de test avec V1 persistée, mettre à jour le module et comparer
   identifiants, contenus et métadonnées de validation avant/après.

Les tests natifs sont dans `addons/training_management/tests/`. Le scénario
persistant `tests/probes/catalogue_upgrade_probe.py` sépare préparation et
vérification de mise à jour ; son commit est volontaire et limité aux bases
jetables `tm_s01_test_*`, jamais au code métier.

La CI `.github/workflows/odoo.yml` utilise l'image Odoo figée, PostgreSQL 18.6,
une base éphémère et un mot de passe fictif réservé au service de test. Elle
exécute installation, tests, mise à jour, conservation historique, traduction
française et verrou concurrent. Aucun secret du serveur n'est requis. Le workflow
Project existant reste inchangé. Les résultats réellement obtenus et les limites
sont dans [native-coverage.md](native-coverage.md).

## Suite

S01 couvre CAT01 partiellement (catalogue interne), CAT02 dans son périmètre et
SEC01 pour sociétés/rôles du catalogue. Il ne termine pas la phase 1 : publication
Web et PDF contractuel, commerce, réalisations, inscriptions, portail, examens,
émargement et reprise restent à traiter selon #3. Les écarts Surveys nécessitent
une décision distincte avant de choisir l'intégration d'examens ; aucune réécriture
automatique de la spécification ou moteur supplémentaire n'est décidé.

Aucune fusion, installation dans `neopro_dev`, modification de production ou
migration réelle n'est incluse dans cette livraison.
