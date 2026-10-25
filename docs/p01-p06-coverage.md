# Couverture P01–P06 et périmètres C02/C04

Références : [backlog #3](https://github.com/Progideo/training_management/issues/3),
[C02 #6](https://github.com/Progideo/training_management/issues/6),
[C04 #8](https://github.com/Progideo/training_management/issues/8), spécification v2 §19–20.

## Écarts qualifiés sur main 1db3b95

| Besoin | Déjà livré | Écart à traiter | Intégration retenue |
| --- | --- | --- | --- |
| P01 #23 | Catalogue interne, CRM, devis, comptes Odoo | Deux entrées publiques, contexte conservé, formulaire approprié | QWeb/HTTP/Portal natifs ; pas de boutique ni de paiement |
| P02 #24 | `crm.lead`, modalités/dates/effectif/devise, création du devis | Qualification intra, dépôt privé, accusé, répétition | Héritage CRM ; pièces jointes natives et soumission idempotente |
| P03 #25 | Programme immuable, validation/auteurs, PDF figé | Résultats, livrables, profils, inclusions et informations en attente ; fiche publique | Extension du programme ; sections communes fiche/PDF |
| P04 #26 | PDF privés S05, évaluations et examens S06 | Extrait et mini-quiz indépendants publiables | Projection publique explicite ; questions de démonstration sans tentative ni résultat |
| P05 #27 | Documents commerciaux à contacts nommés ; portail participant ; inscriptions contrôlées | Habilitation entreprise, demandes/sessions/listes, nominations sans accès | Compte portail Odoo et habilitation explicite par société exploitante/entreprise cliente |
| P06 #28 | Besoins sur réalisation, adaptations individuelles confidentielles, clôture | Variante intra versionnée et accord client avant confirmation | Variante liée à la réalisation et au programme ; aucune réécriture du catalogue |

Le standard CRM ne porte pas ces parcours métier ; Portal fournit authentification,
QWeb et session, sans habilitation entreprise métier. Les autorisations commerciales
S02.1 restent distinctes des habilitations de suivi P05. Les adaptations S04 concernent
un participant et leur référent ; elles ne sont pas un dossier client P06.

## Socle cumulatif et preuves natives

| Exigences | Couverture durable / choix |
| --- | --- |
| CAT01–CAT02 | S01 et catégories/PDF ; programme versionné spécifique, catégories et rapports natifs |
| COM01–COM03 | S02/S02.1 ; CRM/Sales/Account/contacts/devises officiels, virement et restrictions documentaires |
| INS01–INS03, ACC | S03 ; allocations, inscriptions, activation manuelle, comptes Odoo |
| ORG01–ORG02 | S04 ; séances, besoins, ressources natives et adaptations confidentielles |
| ESP01, supports/progression | S05 ; Portal et pièces jointes natifs, accès par inscription active |
| EXA01–EXA06, P07–P08 | S06 ; Surveys étendu, tentatives et instantanés contrôlés |
| Présences/émargement | S07 ; événements append-only et corrections tracées |
| DOC, clôture | S08 ; QWeb et preuves conservées |
| Évaluation/retours/qualité | S09.1–S09.4 ; Survey, acteurs et dossiers qualité |
| NOT, indicateurs, UX | S10 ; notifications et tableaux/portails natifs |
| SEC01–SEC02 | S11 et contrôles par objet ; pas de privilège via simple lien ou jeton |
| MIG | Préparateur M01 ; qualification/reprise réelle hors P01–P06 |

Preuves détaillées : [index](README.md), [code exact et licence](native-coverage.md),
[couverture CRM/Ventes](s02-native-coverage.md), [Surveys](s06-mock-exams.md),
[sécurité](s11-security-audit.md). Distribution cible inchangée : Community
`20.0-20261015`, digest épinglé dans la [suite cumulative](ci.md).
Aucun addon Enterprise ou communautaire supplémentaire requis.

## Droits à préserver

| Profil | Accès | Exclusions |
| --- | --- | --- |
| Visiteur | Projection des programmes explicitement approuvés et publiés, extrait et mini-quiz publics | ORM métier, brouillons, autres sociétés du site, supports privés, résultats |
| Demandeur | Soumission et accusé de sa demande | Commande, inscription et activation automatiques |
| Contact entreprise habilité | Périmètre explicite entreprise cliente + société exploitante + dossiers autorisés | Autres clients, réponses, scores, positionnements, tutorat, adaptations personnelles |
| Participant | Ses accès S03–S11 existants | Aucun élargissement par rattachement à une entreprise |
| Coordinateur | Programme/variante et contrôle des nominations/inscriptions | Pas de modification du contenu déjà validé ni de suppression des preuves |
| Commercial/comptable | Droits CRM/Ventes/comptabilité existants | Aucune ouverture des supports ou échanges privés |

Un contenu déjà publié dans le catalogue interne n’est pas rendu public par la
mise à jour : l’approbation publique est désactivée par défaut et choisie sur une
nouvelle version brouillon. Aucun domaine email ne vaut habilitation.

## Preuves de l’extension P01–P06

| Parcours | Fonctions et recette | Tests ajoutés à la suite cumulative |
| --- | --- | --- |
| P01–P02 | [Parcours et demande guidée](p01-p02-guided-requests.md), PR #81 après #80 | `TestPublicRequest` : contexte HTTP, erreurs, champs/PDF, accusé, répétition, droits CRM et jetons |
| P03–P04 | [Catalogue et aperçu](p03-p04-public-catalogue.md), PR #80 | `TestPublicCatalogue` : fiche/PDF, mini-quiz, programme privé, société, immutabilité et retrait |
| P05 | [Portail entreprise](p05-p06-company-dossiers.md) | `TestCompanyPortal` : lots/participants/fichiers, nomination, export, révocation ; `TestCompanyRequests` : CRM par client et exploitant |
| P06 | [Versions intra](p05-p06-company-dossiers.md) | `TestCompanyPortal` : accord exact, métadonnées protégées, succession, catalogue inchangé, isolation des PDF |
| Mise à jour/concurrence | [CI](ci.md), parcours `p01p06` | Main `1db3b95` → nouvelle version → mise à jour répétée ; fichiers et historiques conservés ; deux connexions réelles sur une même demande et nomination |

Les résultats d’exécution et réserves de revue restent dans les PR. La recette
L01 et la reprise réelle M01 restent distinctes ; cette matrice ne vaut pas décision
de lancement. Website et eLearning ne deviennent pas des dépendances du socle.
Le mini-quiz P04 utilise deux choix publics sans tentative persistée : Surveys,
déjà intégré aux véritables évaluations, n’est pas imposé au catalogue seul.
