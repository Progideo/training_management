# P09.2 — Parcours dans le portail participant

Référence : [P09 #32](https://github.com/Progideo/training_management/issues/32),
spécification §21. Ce volet complète [P09.1](p09-learning-paths.md).

## Fonctionnement

« Mes parcours » est accessible depuis l'accueil du portail et « Mes formations ».
Le participant voit les étapes dans leur ordre, leurs prérequis, la durée
pédagogique estimée et le nombre d'étapes terminées. Chaque lien ouvre l'espace
formation existant, uniquement lorsque son accès effectif est actif.

La synthèse relit les références P09.1, les inscriptions et les activités S05/S06.
Elle ne crée aucun droit, inscription, progression ou preuve. Une équivalence
validée porte un libellé simple ; son motif interne reste privé. La complétion
n'est pas une certification. Un parcours partageant une inscription avec un
autre conserve cette même source ; les totaux de parcours ne sont pas un total
global de formations distinctes.

## Autorisations

- Compte actif, inscription du même utilisateur et du même participant, dans
  une société autorisée : contrôles de l'identité du portail déjà utilisée.
- Références courantes de parcours validés et inscriptions confirmées ou
  clôturées. Les inscriptions suspendues ou révoquées encore non clôturées
  ne donnent aucun accès à cette synthèse. Une clôture conserve le résumé
  personnel de progression, sans réouvrir les supports.
- Une étape sans référence personnelle autorisée reste indisponible. Aucune
  référence d'un autre participant n'est projetée. Un parcours retiré du
  catalogue reste consultable si les références personnelles restent valides.
- Le retrait de toutes les références autorisées enlève le parcours. Le lien
  direct renvoie alors le même refus qu'un identifiant inconnu ou étranger.
- Aucun droit ORM supplémentaire sur les parcours ou inscriptions. Le service
  privé ne transmet à QWeb que des valeurs simples : ni score, corrigé, fichier,
  motif, contact, information commerciale ou acteur de validation.
- Pages authentifiées en lecture seule, contenu échappé et cache privé interdit.
  Aucun lien vers une formation bloquée, suspendue, révoquée, future ou expirée.

Les vues, l'authentification, la pagination et les styles sont ceux du portail
Community déjà utilisé par S05. Aucun frontend ni compte supplémentaire.
La commercialisation des parcours reste à définir avant réalisation.

## Recette courte

1. Affecter deux étapes à un participant fictif ; ouvrir seulement la première.
   Vérifier l'ordre, les durées, le prérequis et l'unique lien disponible.
2. Terminer les activités obligatoires de la première formation : le compteur
   évolue sans nouveau travail ni inscription. Ouvrir la seconde par le circuit
   existant : son lien apparaît. Tester aussi une équivalence déjà validée.
3. Clôturer une formation : progression conservée, aucun lien vers ses supports.
   Suspendre, révoquer ou retirer les références : vérifier la disparition des
   informations correspondantes et le refus des anciens liens directs.
4. Essayer un autre participant, un représentant client sans inscription propre,
   une autre société, un compte désactivé et des paramètres de requête falsifiés.
   Aucun accès supplémentaire ; les modèles restent interdits au portail.
5. Vérifier français, petits écrans, clavier, titres et ordre de lecture ; ouvrir
   une étape en une action et ne pas confondre heures estimées et présence.
6. Mettre à jour une base fictive avec des références P09.1 et comparer les
   historiques avant/après ; consulter la synthèse ne doit modifier aucune ligne.
