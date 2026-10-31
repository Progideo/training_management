# L01 — Recette intégrée du module

Référence : [#31](https://github.com/Progideo/training_management/issues/31),
R01–R09, P01–P14 et P16 ; P15 est annulé. La recette de livraison du module est
clôturée dans cette issue. Les résultats et écarts d’exécution restent dans les
issues et pull requests, notamment [#100](https://github.com/Progideo/training_management/pull/100).
P20 dispose de sa [recette complémentaire](p20-verifiable-certificates.md).
La bascule de chaque organisme depuis Odoo 19 relève de son exploitation ; cette
clôture n’autorise ni reprise réelle ni ouverture de production.

## Méthode

`training_management_survey/tests/test_l01.py` ajoute les parcours intégrés à la
suite cumulative existante, sans nouveau workflow ni nouvelle matrice. Les
fixtures des inscriptions, présences, évaluations et examens sont réutilisées.
Les parcours nécessitent les trois addons ; ils sont ignorés dans les
configurations sans intégration Ventes. Ce saut ne valide pas une recette globale.

Utiliser une base jetable avec Website/eLearning et français, sur l’image
Community épinglée. Isoler son PostgreSQL, son réseau et ses fichiers ; empêcher
les envois externes et les crons. Réserver tout accès navigateur à la boucle
locale. Créer uniquement sociétés, clients, comptes, cours, PDF et opérations
financières fictifs. Ne pas recopier une base active ni ses secrets.

## Parcours liés

- R01 : demande CRM répétée, devis/commande MAD, nominations 7 puis 3, dix places,
  refus du surnombre, accès différé autorisé, présence validée, évaluation dédiée
  puis preuve et attestations, contrôle des pièces et clôture qualité.
- R02 : demande individuelle EUR, réservation, facture et virements natifs
  partiel/solde vérifiés par le comptable ; accès manuel et convocation répétée
  sans doublon. Les tarifs, taux et comptes sont des fixtures sans valeur métier.
- R03/P07–P08 : accès autonome, PDF privé, examen réussi puis repassé, correction,
  thèmes et conservation des tentatives ; aucun certificat d’acquis induit.
- R04–R05 : deux séances et trois activités, durée réellement validée,
  attestations limitées aux preuves ; report/remplacement sans transfert de score.
- R06–R07 : refus public, participant et autre société, documents entreprise,
  révocation, retrait du superviseur et exports qualité selon leur destinataire.
- R08 : palette, sauvegardes HTTP répétées, rechargement, marquage, échéance
  serveur et réponse tardive sans modification du résultat final.
- R09 fictif : import/rejeu/export natifs de contacts archivés, liens et société,
  absence de comptes créés, saisie manuelle sans ouverture et PDF source conservé.
- P01–P06 : deux parcours publics, programme et aperçu, quiz sans résultat
  persistant, demande guidée, habilitations explicites et accord client sur chaque
  version intra, historique et programme standard conservés.

## Extension de recette V2

La phase 2 couvre P09 à P14 et P16 ; P15 est annulé par décision
[#38](https://github.com/Progideo/training_management/issues/38), sans retirer
le catalogue, les demandes ou les devis de parcours existants.
Les parcours `test_v2_*` prolongent la même classe L01 et ses fixtures ; ils
ne créent ni lot de tests ni configuration supplémentaires.

| Exigences | Enchaînement et preuve automatisée | Complément de recette |
| --- | --- | --- |
| P10, COM01–02, INS01, P16 | Orientation sans réponse persistée → devis MAD → capacité S03 → alerte volontaire → dates/fuseau révisés → désabonnement contrôlé dans le transport natif | Réception réelle, conditions et identité d’envoi de lancement |
| P09, PED01–02, P12–P13 | Projet révisé et évalué → prérequis acquis → ouverture manuelle de l’étape → tutorat sans doublon → révocation et conservation des preuves | Lecture et manipulation mobile/clavier des trois espaces |
| PRE01–03, P11, P14, SEC01–02 | Présence partielle validée → mise en pratique privée → accord sur l’avis exact → modération explicite → retrait sans perte des preuves privées | Accord métier, contenu et présentation publique |
| R01–R09, P01–P08 | Parcours L01 existants et régressions cumulatives : MAD/EUR, supports/examens, présences, attestations, qualité et portail entreprise | Contrôle humain indépendant, PDF et validations de lancement |
| UX01, français | Titres Website dans la langue des pages et durée du tutorat au format local ; paramètres QWeb et formatage natifs | Clavier, petits écrans et lecture visuelle des contenus réels |

Réutiliser les preuves CI du même arbre fonctionnel pour les cas unitaires,
HTTP, droits, dates/DST, migrations et courses. Ne relancer que les parcours
affectés ou un risque nouvellement identifié. Les résultats, écarts et limites
de chaque exécution restent dans la PR, avec commit, profils et journaux.
Une exécution de développement ne vaut pas visa humain et n’autorise aucune
fusion, ouverture, migration réelle ni activation d’envoi. Les exigences de
présence courantes sont celles de l’[émargement par demi-journée](s07-attendance.md) ;
les scénarios de présence partielle vérifient la conservation des anciennes preuves.

## Qualification des preuves

Consigner commit, configuration, profil, attendu, constat et journal/capture par
scénario. Les contrôles automatisés HTTP ne démontrent pas à eux seuls le
comportement JavaScript, l’ergonomie clavier/mobile ni une vraie coupure réseau :
compléter ces points par une recette navigateur bornée et qualifier les limites.
L’extraction de texte des PDF vérifie leur lecture, pas toute leur mise en page.

La session humaine guidée décrite dans #100 couvre une partie des parcours.
Les opérations financières et entreprise, l’émargement électronique en direct
et l’ensemble des attestations n’y ont pas été contrôlés intégralement. La clôture
de #31 ne transforme pas leurs preuves automatisées en validation humaine.
Les évolutions ultérieures, dont les demi-journées et P20, conservent leurs propres
critères de recette. Un visa simulé par des comptes de test n’est pas un contrôle
humain indépendant.

La reprise réelle, les paramètres d’envoi, l’hébergement, les sauvegardes, le PV
de bascule et les obligations locales d’un organisme sont suivis dans son dossier
d’exploitation, conformément à [#101](https://github.com/Progideo/training_management/pull/101).
Leur séparation ne les déclare pas achevés. Les tests et la sécurité du module
restent dans ce dépôt ; la [préparation de reprise](m01-migration-preparation.md)
et les [paramètres natifs](c06-launch-settings.md) restent des références techniques.
