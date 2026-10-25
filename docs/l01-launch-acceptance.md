# L01 — Recette intégrée du lancement

Référence : [#31](https://github.com/Progideo/training_management/issues/31),
R01–R09 et P01–P08. Les résultats et écarts d’exécution restent dans l’issue et
les pull requests. Odoo 19 demeure la référence opérationnelle jusqu’à validation
d’Odoo 20 ; cette recette n’autorise ni reprise réelle ni ouverture de production.

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

## Preuves et limites

Consigner commit, configuration, profil, attendu, constat et journal/capture par
scénario. Les contrôles automatisés HTTP ne démontrent pas à eux seuls le
comportement JavaScript, l’ergonomie clavier/mobile ni une vraie coupure réseau :
compléter ces points par une recette navigateur bornée et qualifier les limites.
L’extraction de texte des PDF vérifie leur lecture, pas toute leur mise en page.

L01 reste ouvert tant que la reprise réelle nécessaire, la seconde vérification
humaine, les paramètres C06 et les conditions d’exploitation ne sont pas validés.
Un visa simulé par des comptes de test n’est pas un contrôle humain indépendant.
