# Démarrage du développement — cadrage proposé

État au 20 octobre 2026. Pilotage : [#3](https://github.com/Progideo/training_management/issues/3).
Ce document prépare C01–C06 et S01 ; il ne constate pas leur achèvement.

## Références et faits vérifiés

- `origin/main` actualisé : `9be5fcbe46788f5ca6b0c0c266f71de184dba6f5`.
  Aucun addon métier sur cette branche.
- La [PR #41](https://github.com/Progideo/training_management/pull/41)
  demeure ouverte : les références et `AGENTS.md` y figurent, mais ne sont
  pas encore intégrés à `main`. Leur fusion n'est pas présumée autorisée.
- Spécification v2.0 du 15 octobre et prompt maître lus dans cette branche
  documentaire et comparés aux sources du projet : empreintes identiques.
  Respectivement :
  `738834bd20869a343d2f808b08dfccf9b37b2b255fb3ab7bdacc2251fc218096`
  et `bf443e9ee30d5474d8044844724cc9aa66b63be0047179677a30a28bf5f92503`.
- [#8](https://github.com/Progideo/training_management/issues/8) porte une
  précision du 17 octobre : préférence portail pour participants et
  représentants ; faisabilité et choix définitif à démontrer. Cette précision
  complète la v2 ; elle n'autorise pas une attribution de droits.
- L'utilisateur déclare un environnement de développement opérationnel,
  Odoo Community `20.0-20261015`, PostgreSQL 18.6 et les applications Contacts,
  Ventes, Website, eLearning et Surveys installées. Ce sont des informations
  fournies, pas une inspection indépendante du serveur.
- La tentative de lecture de version par SSH a échoué à l'authentification
  (`Permission denied (publickey)`). Aucun code installé n'a été inspecté.
  Ne pas assimiler le numéro de paquet à un SHA des sources ou au digest
  d'une image. Aucun repli vers 19 ou une branche de développement.

Les issues existantes couvrent déjà le travail. Ne pas créer un second backlog.
La présente proposition ne modifie ni les exigences ni l'automatisation Project.

## Premier incrément recommandé : S01

Référence : [#11](https://github.com/Progideo/training_management/issues/11).
Objectif : un addon `training_management` installable, application
« Training Management », menu « Formations », avec catalogue interne et
programmes versionnés. CAT01 est partiellement couvert (gestion interne) ;
CAT02 et SEC01 sont traités dans le périmètre du catalogue.

Parcours de recette : le coordinateur crée une formation et son programme V1,
complète les informations obligatoires, valide puis publie V1 ; il prépare V2
sans modifier V1 ; un lecteur autorisé consulte ; un utilisateur non habilité
ne peut accéder aux objets, même directement par l'ORM.

« Publié » désigne ici l'état du programme : aucun accès public au site ne doit
être induit. Publication Web, commerce, inscriptions, examens et émargement
restent dans leurs incréments prévus. Ils ne sont pas retirés du lancement.

### Architecture soumise à validation

- Un seul addon initial, dans `addons/training_management/`.
- Dépendance initiale proposée : `base`, pour les sociétés, utilisateurs,
  contacts et mécanismes natifs. Disponibilité, API et licence exactes à
  vérifier dans la distribution cible avant implémentation ; licence du
  spécifique : `LGPL-3.0-only`. Aucun module tiers proposé.
- `training.course` : identité pédagogique stable, société exploitante,
  archivage et versions. Il ne remplace pas le produit commercial.
- `training.program.version` : formation, société cohérente, référence de
  version, objectifs, public, prérequis, contenu, durée, modalités, langue,
  méthodes, critères d'évaluation, conditions d'accès et contact
  accessibilité. La définition complète de publication CAT01 inclut prix
  ou sur devis ; S01 peut proposer uniquement « sur devis », explicitement,
  en attendant l'intégration commerciale.
- États : brouillon, validé, publié, retiré. Contenu validé figé ; changement
  substantiel par copie en nouveau brouillon. Validation et publication
  contrôlées côté serveur, y compris lors d'un appel direct à `create/write`.
  Pas de retour en brouillon permettant de réécrire une version validée.
- Unicité de référence par formation garantie en base ; aucune numérotation
  fondée sur un simple `max + 1` sans protection concurrente. Liens historiques
  protégés contre la suppression, pas de suppression en cascade des versions.
- Société obligatoire, cohérence des relations et règles multi-sociétés.
  Entreprise cliente distincte de cette société ; aucun client requis pour
  une formation de catalogue.
- Contacts réutilisés via `res.partner`. Le lien commercial vers
  `product.template` sera apporté avec l'intégration Ventes, sans prix,
  devise ni taxes concurrents. Le programme conserve ses propres versions.
- Aucun chatter initial : pas de besoin de diffusion justifiant cette
  dépendance pour S01. Auteur/date de validation et publication conservés.

Pour la suite : conserver le métier générique dans l'addon principal.
Des addons d'intégration Ventes, Website/Portal et eLearning/Surveys ne seront
créés que si leurs dépendances et leur caractère optionnel le justifient.
Ne pas figer aujourd'hui leur nombre ou leurs noms. Adaptations d'organisme,
localisation et scripts de migration restent séparés ; aucune donnée
d'entreprise codée en dur.

## Matrice de couverture préalable

Lecture : chaque ligne est une **hypothèse à examiner**, et non une couverture
démontrée. « Configuration » désigne une piste ; « extension/spécifique »
désigne le travail potentiel après inspection du standard exact.
Preuve actuelle commune : exigences lues ; applications déclarées installées
par l'utilisateur. Aucune preuve d'exécution fonctionnelle sur Odoo 20.

| Exigences | Standard candidat | Configuration à examiner | Extension / spécifique envisagé | Preuve à produire / incertitude |
| --- | --- | --- | --- | --- |
| CAT01–02 | Produits, Website, eLearning | Modalités, catégories, publication | Versions pédagogiques figées, contrôles de publication, PDF lié à la version | Modèles exacts, V1 conservée après V2, brouillon privé |
| COM01 | Ventes ; CRM à évaluer | Parties commerciales, devis | Demande qualifiée, idempotence et rattachements | Ne pas imposer CRM sans démonstration |
| COM02–03 | Ventes, facturation, devises | MAD/EUR, tarifs indépendants, virement | Contrôles de révision et rapprochement si écarts | Vente et facture par devise, acomptes, doublon de référence |
| INS01–02 | Ventes ; Event à comparer | Réservations, délais, capacité | Places non nominatives, registre unique, contraintes concurrentes | Dernière place, homonymes, double confirmation |
| INS03–05 | Utilisateurs, portail, eLearning | Périodes et autorisation manuelle | Politique d'accès, report/remplacement, prolongation motivée | Vente seule sans accès, révocation, historiques |
| ORG01–02 | Contacts, calendrier | Ressources et fuseaux | Dossier restreint, séances, conflits et dérogations | DST, concurrence de réservation, secret des aménagements |
| ESP01, PED01–02 | eLearning, portail, pièces jointes | Activités et progression | Vue unifiée, remises privées, tutorat et relances | Accès portail réel, fichiers directs, critères de complétion |
| EXA01–06 | Surveys / Certification | Questions fixes, notation, temps, répétitions | Seulement écarts prouvés : versionnement, échéance, barème, sauvegarde | Matrice détaillée ci-dessous ; aucun choix acquis |
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

### Preuves attendues sur Surveys

[#7](https://github.com/Progideo/training_management/issues/7) reste ouvert.
L'existence SQL de `survey.survey`, `survey.question`, `survey.user_input` et
`survey.user_input.line` confirmerait leur enregistrement, pas leur conformité.

| Besoin | Inspection et test nécessaires |
| --- | --- |
| EXA01 | Choix complet et ordre fixe des questions ; durée et barème positifs ; correction obligatoire |
| EXA02 | QCU et QCM à ensemble exact ; toutes les cases cochées ne donnent pas les points ; seuil inclusif |
| EXA03 | Début confirmé, échéance serveur, réponse tardive refusée ; fermeture du navigateur et expiration sans retour |
| EXA04 | Sauvegarde de chaque changement, reprise après déconnexion, aucun corrigé avant remise |
| EXA05 | Recommencer après 100 %, sans perdre l'historique ; une seule tentative active malgré deux onglets |
| EXA06 | Modifier/supprimer une question source ne change pas une ancienne tentative ; révision motivée |
| P07 | Palette, « à revoir », récapitulatif, confirmation et idempotence ; temps inchangé au rechargement |
| P08 | Points par thème figés, absence de thème et zéro traités, liens de révision filtrés |
| Sécurité | Deux vrais comptes portail ; URL, jeton, fichier, API et correction croisés refusés ; notifications/certificats maîtrisés |

Chaque résultat devra identifier version du code, configuration, profil,
scénario, résultat observé et écart. L'observation d'un champ de durée ou d'une
option de tentatives illimitées ne suffit pas à clore le scénario.

## Comptes et droits proposés

La préférence portail du 17 octobre est conservée. Aucun accès externe
automatique n'est créé par S01.

| Profil / compte envisagé | Espace et actions | Périmètre / refus | Standard ou extension et preuve |
| --- | --- | --- | --- |
| Coordinateur / interne | Gestion : créer/modifier brouillon, valider, publier, retirer, consulter/exporter catalogue | Sociétés autorisées ; contenu figé après validation ; suppression limitée aux brouillons | ACL/règles et contrôles spécifiques ; tests S01 à exécuter |
| Lecteur catalogue / interne | Gestion : lire/rechercher/exporter catalogue | Sociétés autorisées ; aucun changement ni transition | ACL/règles ; tests S01 à exécuter |
| Interne sans rôle, portail, public / S01 | Aucun accès aux modèles internes | Refus lecture, création, modification, suppression et méthodes | Tests ORM et accès direct à exécuter |
| Participant / portail préféré | Site : lire programme/agenda ; télécharger PDF personnels ; créer/modifier remise, répondre, remettre examen, émarger ; lire résultats/documents propres | Inscription et période actives ; aucun pair ; aucun corrigé avant remise ; aucune validation de son travail | Portail/eLearning/Surveys candidats, extension selon preuve ; prototype #7/#8 requis |
| Représentant / portail préféré | Site : demandes/devis autorisés, sessions, nomination, téléchargement documents autorisés | Mandat explicite par entreprise/dossier ; pas de score/réponse/échange privé ; nomination sans activation | Portail Ventes candidat et extension P05 ; prototype #8 requis |
| Commercial / interne | Gestion commerciale : lire/créer/modifier demandes et devis ; export commercial autorisé | Pas de remises, réponses détaillées ou aménagements | Droits natifs et extension à vérifier |
| Formateur/tuteur interne ou externe | Séances affectées, correction et validation des présences | Affectations explicites ; pas de comptabilité | Type de compte externe non décidé ; arbitrage #10 après prototype |
| Qualité / interne | Preuves nécessaires, réclamations, actions, exports autorisés | Données sensibles seulement sur habilitation | Extension et tests par dossier requis |
| Facturation / interne | Pièces commerciales, règlements et exports comptables | Pas de résultats individuels ni corrigés | Droits natifs à vérifier |

La charge du portail étendu n'est pas estimable de façon fiable avant inspection
et prototype. Comparer alors par action le standard, l'extension et un éventuel
compte interne restreint, sans attribuer ce dernier par défaut. Tester cumul
participant/représentant, mandats multiples, révocation, changement d'employeur
et reprise des comptes. Une recherche filtrée ou un bouton caché ne remplace
jamais une autorisation serveur.

## Validation technique prévue

1. Identifier le paquet installé, le chemin des sources, leur provenance et
   empreinte, ainsi que l'image effective et son digest. Vérifier `base`, les
   conventions des groupes, contraintes ORM, vues, manifest et tests dans ce code.
2. Figer cette cible dans un environnement de test reproductible. Aucun
   `odoo:latest` ni branche mouvante comme preuve de compatibilité.
3. Sur branche dédiée S01 : contrôles Python/XML/manifest et conventions
   vérifiées, puis tests natifs Odoo pour contenu obligatoire, transitions,
   écritures directes, copies, unicité, droits restreints et multi-sociétés.
4. Installer sur une base vierge jetable. Créer V1 et des données fictives ;
   mettre à jour le module sur cette base existante ; vérifier contenu,
   identifiants et historique conservés. Ne pas utiliser la production.
5. Recette française : menus, listes/formulaires, V1/V2, lecture seule,
   refus de publication incomplète, accès directs et export hors société.
   Vérifier les contacts standards affectés.
6. CI proposée : contrôles statiques à chaque PR et intégration Odoo sur
   cible figée lorsqu'elle est disponible. Workflow séparé, sans modifier
   l'automatisation Project. Aucun job de fusion ou déploiement automatique.

Tests **réalisés pour ce cadrage** : actualisation Git, vérification du commit
et de l'arborescence, lecture des issues de cadrage et S01, vérification de la
PR #41, comparaison SHA-256 des références. Aucun test Odoo, installation,
mise à jour ou démonstration Surveys exécuté. Aucun module métier livré ici.

## Dépendances restantes et prochaine étape

- C01 : obtenir la preuve de la distribution installée et l'accès au code exact.
- C02/C03 : remplir les résultats observés de la matrice et du prototype,
  en distinguant les écarts bloquants pour S01 des chantiers ultérieurs.
- C04/C06 : soumettre le choix des objets et de leur immutabilité ci-dessus
  avant code métier, conformément au prompt maître §12 et à #11.
- S01 : implémenter puis tester le premier module sur la cible vérifiée ;
  publier sa PR avec les résultats réels. Cette proposition documentaire
  ne remplace pas cette livraison.

Première opération à faire exécuter par l'utilisateur dans sa connexion SSH
existante, en lecture seule, puis attendre son résultat :

```sh
sudo docker exec neopro-odoo20-dev-odoo-1 odoo --version
```

Cette commande confirme seulement la version annoncée par l'exécutable.
Les chemins et empreintes seront vérifiés à l'étape suivante. Ne pas demander
de clé privée, mot de passe, fichier de configuration complet ou sauvegarde.
