# S03.1 — Corrections de revue et allègement

Références : [S03](s03-enrollment-access.md), [backlog #3](https://github.com/Progideo/training_management/issues/3),
spécification v2 (INS01–INS05, ORG02, SEC02, §10). Origine : revue fonctionnelle
et technique du 22 octobre 2026, au commit `7647393`, validée par l'utilisateur
le même jour.

Incrément correctif, livré avant S04 par une PR unique, sans nouvel addon.
Versions cibles : `training_management` **20.0.1.2.0**, `training_management_sale`
**20.0.1.10.0**. Aucune fusion, aucun déploiement ni migration réelle n'est
autorisé par ce document.

## 1. Motif saisi pour chaque action (A1 — bloquant)

Constat : `change_reason` est un champ stocké, jamais vidé. Un motif saisi une
fois satisfait ensuite toutes les actions motivées ; le journal répète le même
texte pour des décisions différentes.

Règle : chaque action motivée reçoit son propre motif, saisi au moment de
l'action. Aucun motif n'est conservé sur l'enregistrement après l'action.

- Les actions motivées prennent le motif en paramètre (`reason=None`) et le
  refusent s'il est vide : prérequis (validation, dérogation), confirmation sous
  le seuil, annulations, autorisation et retrait, ouverture, suspension,
  révocation, prolongation, clôture, abandon, transfert, libération de places.
- Les boutons ouvrent un assistant générique `training.action.reason` (modèle,
  identifiants, action, motif). L'assistant appelle la méthode publique avec le
  motif ; les contrôles restent dans les modèles.
- Supprimer le champ `change_reason` de `training.controlled`, des vues et des
  traductions. Les motifs historiques restent dans `training.operation`.
- Tests : deux actions successives, la seconde sans motif → refus ; le journal
  contient deux motifs distincts. Adapter les tests qui reposaient sur la
  réutilisation (`test_enrollment.py`, `admitted()`).

## 2. Cycle de vie et accès (A2, A4, A5)

- **Clôture de la réalisation** : `action_close` exige qu'aucune inscription ne
  soit `requested`, `reserved` ou `waiting` ; les inscriptions `confirmed` passent
  à `closed` avec accès révoqué, dans la même transaction et avec le motif de
  clôture. `_effective_state()` renvoie `blocked` si la réalisation est
  `closed` ou `cancelled`.
- **Report** : nouvel état terminal `postponed` (« Reportée »), ajouté à
  `TERMINAL`. Le report y conduit ; le remplacement reste `replaced`. Pas de
  réécriture des reports antérieurs (déjà `cancelled` avec successeur) : la
  migration n'y touche pas.
- **Retrait d'autorisation, révocation d'accès** : gardes d'état comme les autres
  actions et idempotence (aucune ligne de journal si rien ne change).

## 3. Places et commandes (A3, A6, A7)

- La protection de la ligne et de la commande (`training_management_sale`)
  ne s'applique qu'aux lots vivants (`_available()`) ou portant une inscription
  non terminale. Un lot annulé ou expiré ne fige plus la commande.
- Nouvelle action motivée « Prolonger l'échéance » sur un lot `reserved` non
  expiré : nouvelle échéance future et postérieure, journalisée.
- Index unique partiel en base : `(delivery_id, participant_id)` pour les
  inscriptions non terminales (`models.UniqueIndex` avec `WHERE`). Le contrôle
  applicatif et son message restent.

## 4. Dates de session modifiables (ORG02)

Une réalisation `preparation` ou `confirmed` peut changer `start_at` / `end_at`
après inscriptions, par une action motivée « Modifier les dates », journalisée
avant/après. Programme, société, nature et politique d'accès restent figés.
Les périodes d'accès déjà calculées des inscriptions ne sont pas réécrites ; si
la politique est `fixed`, la modification des dates d'accès suit la même action
et refuse un raccourcissement sous un accès actif.

## 5. Ergonomie

- Vues de recherche pour réalisations, lots et inscriptions : filtres « À
  traiter » (demandes, réservations expirées, accès à ouvrir), regroupements par
  réalisation, état, client.
- Séquence de référence pour les réalisations (`training.delivery`, préfixe
  configurable, par société). Le nom libre reste.
- Boutons contextuels à la place du bouton unique « Réserver / Prolonger /
  Transférer ».
- Actions groupées depuis la liste des inscriptions : confirmer, autoriser,
  ouvrir l'accès, avec un motif saisi une fois pour la sélection et une ligne de
  journal par inscription.
- Tâche planifiée quotidienne qui matérialise les expirations de lots et de
  réservations (`action_expire`). Le contrôle à l'heure serveur reste l'autorité.
- Chatter et activités (`mail.thread`, `mail.activity.mixin`) sur réalisations,
  lots et inscriptions, sans suivi automatique des champs contrôlés ni envoi
  externe. `training.operation` reste la preuve. Ajouter `mail` aux dépendances
  du socle.
- Activité pour le responsable quand une réalisation confirmée ou en préparation
  reste sous son seuil d'ouverture à J-7 de son début (session datée).
- Journal : pour les relations, afficher le libellé capturé de l'ancienne et de
  la nouvelle valeur, sans suivre un lien réaffecté.
- Renommer dans le code le report en `postpone` (méthodes, sélection
  d'opération) ; libellés français inchangés.
- Fuseau : `_tz_get` de `base`.

## 6. Accès commercial en lecture (§10)

Groupe ventes (`sales_team.group_sale_salesman`) : lecture des réalisations, des
lots et des états d'inscription de ses sociétés, via `training_management_sale`.
Champs exclus : prérequis, compte personnel, accès, journal. Tests avec un
commercial réellement restreint.

## 7. Qualité de code

- `pre-commit` avec `ruff` (lignes 120) et `pylint-odoo` (règles par défaut),
  exécuté par la CI. Reformater une fois, dans un commit séparé sans changement
  fonctionnel.
- Vues XML indentées, un élément par ligne.

## 8. Documentation allégée

- README : présentation, installation, liens ; plus d'historique d'autorisations.
- `docs/README.md` : ordre de lecture, provenance des références, empreintes.
  Supprimer la revue de #41 et les répétitions d'état.
- Une page par incrément : décisions, règles, recette courte. Les autorisations
  et résultats d'exécution restent dans les PR.
- Corriger le chemin `sources/` → `docs/references/` dans la page S03.
- Mettre à jour le corps du backlog #3 (S01–S03 livrés, S03.1, S04 suivant).
- `AGENTS.md` : ajouter que simplicité et ergonomie font partie de la recette ;
  un garde-fou doit protéger une exigence identifiée.

## Hors S03.1

- Décisions NeoPro à obtenir : prix négocié ou remise sur les demandes groupe ;
  commandes multi-formations ; accès au devis par lien à jeton sans compte
  portail ; partage du catalogue entre sociétés. Rien n'est développé avant
  décision.
- Catégorie et PDF du programme (CAT01) : S04.
- Consolidation des surcharges messagerie et comptabilité de S02 : PR dédiée
  après S03.1, avec un test de non-régression par surcharge.
- Automatisation de la création d'un lot depuis une commande individuelle
  confirmée : avec S04 ou P01.

## Recette courte

1. Coordinateur : valider les prérequis avec un motif, puis tenter d'autoriser
   sans motif → refus ; le journal montre deux motifs distincts.
2. Lot de 10, 7 noms, sélectionner les 7 → confirmer, autoriser, ouvrir en une
   fois ; 7 lignes de journal.
3. Prolonger un lot réservé ; annuler un autre lot puis modifier sa ligne de
   commande → accepté.
4. Déplacer une session confirmée d'une semaine avec motif ; les inscriptions
   restent rattachées.
5. Reporter un inscrit → état « Reportée » ; clôturer la réalisation → accès
   effectifs bloqués.
6. Commercial seul : lit lots et états, pas les prérequis ni le journal.
7. Mise à jour depuis S03 sur une base jetable (scénarios CI) ; installation
   sur base vierge.
