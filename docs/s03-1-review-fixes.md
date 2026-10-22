# S03.1 — Corrections de revue de S03

Cadrage d'autorité, validé le 22 octobre 2026 : [s03-1-corrections.md](s03-1-corrections.md)
(conservé tel quel). Cette page résume les règles obtenues ; les autorisations et les
résultats d'exécution sont dans les pull requests de cet incrément ([S03.1](https://github.com/Progideo/training_management/pulls?q=is%3Apr+S03.1)).
Versions : `training_management` `20.0.1.2.2` (dépend désormais de `mail`),
`training_management_sale` `20.0.1.10.1`. Pas de nouvel addon.

## Règles

**Motif par action.** Aucun motif n'est conservé sur l'enregistrement : chaque action
motivée reçoit le sien (assistant générique `training.action.reason`, liste blanche
`_reason_actions`) ; un motif vide est refusé et le journal garde un motif par décision.

**Cycle de vie.** Clôturer une réalisation exige qu'aucune inscription ne soit demandée,
réservée ou en attente ; les inscriptions confirmées sont clôturées et leur accès révoqué.
L'accès effectif est bloqué sur une réalisation clôturée ou annulée. « Reportée » est un état
terminal. Retirer l'autorisation ou révoquer l'accès est idempotent (aucune ligne de journal
si rien ne change) et réservé aux inscriptions confirmées.

**Places et commandes.** Une ligne ou une commande n'est protégée que par un lot vivant ou
portant une inscription non terminale. « Prolonger l'échéance » prolonge un lot réservé non
expiré. Un index unique partiel interdit deux inscriptions non terminales du même participant
sur une réalisation ; le contrôle applicatif et son message passent en premier.

**Modifier les dates.** Action motivée et journalisée (avant/après) pour les réalisations en
préparation ou confirmées : dates de session et, si la politique est « période fixe », dates
d'accès. Programme, société, nature et politique restent figés ; les périodes d'accès déjà
calculées ne sont pas réécrites ; réduire une période fixe sous un accès actif est refusé.

**Ergonomie.** Recherche et filtres « À traiter » sur réalisations, lots et inscriptions ;
référence de réalisation par société (séquence `training.delivery`, préfixe modifiable sur
l'enregistrement de séquence, nom libre conservé) ; boutons contextuels ; actions groupées
depuis la liste des inscriptions (confirmer, autoriser, ouvrir l'accès) avec un motif et une
ligne de journal par inscription ; tâche quotidienne qui enregistre les échéances dépassées
(le contrôle à l'heure du serveur reste l'autorité) et planifie une activité pour le
responsable d'une session sous son seuil à J-7 ; chatter et activités sans suivi
automatique de champ ni envoi propre au module ; le journal conserve les libellés des
relations tels qu'ils étaient à l'écriture ; fuseaux horaires natifs.

**Lecture commerciale.** Le groupe Ventes lit réalisations, lots et états d'inscription de ses
sociétés depuis le menu natif Formations ; prérequis, compte personnel, accès et journal restent réservés au coordinateur. Les filtres opérationnels qui interrogent les accès privés, les boutons de gestion et les actions groupées sont réservés au coordinateur ; les boutons d’accès suivent les états autorisés côté serveur. Les formulaires commerciaux restent en lecture seule et les assistants et actions groupées sont traduits en français.

**Qualité.** `pre-commit` (ruff, pylint-odoo) est exécuté par la CI : voir [ci.md](ci.md).

## Limites connues

- Un commercial qui lit un dossier lit aussi ses notes de chatter.
- Un utilisateur assigné à une activité devient abonné du dossier (comportement natif).
- La version de `pylint-odoo` n'est pas épinglée.
- Hors S03.1 : décisions NeoPro en attente, catégorie et PDF du programme (S04),
  consolidation des surcharges S02, création automatique d'un lot depuis une commande individuelle.

## Recette courte

1. Valider les prérequis avec un motif, puis autoriser sans motif : refus ; le journal montre deux motifs.
2. Lot de 10, 7 noms : sélectionner les 7, confirmer, autoriser, ouvrir l'accès ; 7 lignes de journal.
3. Prolonger un lot réservé ; annuler un autre lot puis modifier sa ligne de commande : accepté.
4. Déplacer une session confirmée d'une semaine avec motif ; les inscriptions restent rattachées.
5. Reporter un inscrit : état « Reportée » ; clôturer la réalisation : accès effectifs bloqués.
6. Commercial seul : ouvrir Formations, puis chaque liste et fiche (réalisation, lot, inscription) ; aucune erreur, aucun bouton de gestion, prérequis, accès ou onglet Historique. Le coordinateur conserve les commandes ; sur une inscription reportée, aucun retrait d’autorisation ou d’accès n’est proposé. Vérifier les actions groupées et l’assistant de dates en français.
7. Mise à jour depuis S03 sur base jetable et installation sur base vierge : scénarios de la CI.
