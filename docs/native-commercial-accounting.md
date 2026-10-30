# Ventes et comptabilité natives

Référence : [#102](https://github.com/Progideo/training_management/issues/102),
COM02/COM03 amendés le 30 octobre 2026, séparation module/exploitation [#101](https://github.com/Progideo/training_management/issues/101).
Cette décision remplace la politique de lancement décrite historiquement dans S02.

## Règles

Odoo et les extensions/localisations installées portent devises, taux, conversions,
arrondis, listes de prix, remises, fiscalité, factures/avoirs, échéances, journaux,
méthodes de paiement, rapprochements, écarts et résiduels. La devise demandée est
indicative ; l’offre utilise la devise de sa liste native. Le formulaire public
propose les devises actives. Aucun pays, devise, mode d’encaissement ou prestataire
n’est imposé ou activé par Training Management. Les restrictions volontaires
d’un organisme relèvent de sa configuration ou d’une extension distincte.
`sale_invoice_address_fiscal` reste une extension optionnelle, sans dépendance
avec le module ; ses profils C06 propres au premier organisme restent hors des
règles génériques.

Training Management conserve les versions contractuelles, quantités personne/forfait,
places, inscriptions, autorisations pédagogiques explicites et habilitations
nominatives sur devis, factures, avoirs, reçus, pièces, messages et notifications.
Un paiement ou une confirmation native de vente ne donne aucun accès pédagogique.
Les contrats de parcours acceptés gardent leurs termes et leur périmètre figés.
Le contrôle de devise des commandes confirmées et des listes qu’elles utilisent
évite une réécriture de leur historique : le calcul natif de devise dépend de la
liste, même après confirmation. Il ne limite aucune devise disponible.

Les liens, QR et transactions de paiement natifs sont rétablis. Les routes de
transaction et la page générique de paiement de facture exigent encore les
habilitations documentaires, en plus des jetons et contrôles Odoo. Le suivi et
la confirmation des transactions les revérifient ; leurs notifications utilisent
les canaux privés natifs des contacts actuellement habilités. Aucun prestataire
ni service externe n’est activé. Les reçus conservent l’intersection courante des
contacts habilités sur toutes les factures/avoirs ; une affectation mixte avec un
document ordinaire ferme l’accès externe. Un marqueur de confidentialité persiste
après dérapprochement ; il n’est ni un état de paiement ni un second solde.

## Source native vérifiée

Odoo Community `20.0-20261015`, image
`odoo@sha256:61e3c71b0503c5f658e604c3e340bede20b97d05f726179fa006eae50a32fd23`,
provenance déclarée `49529f034a60e4e9838e08e0a5616e5f2f38c601`.
Sous `/usr/lib/python3/dist-packages/odoo/addons/` :
`product/models/product_pricelist*.py`, `sale/models/sale_order*.py`,
`account/wizard/account_payment_register.py`, `account/models/account_move_line.py`,
`account/models/account_payment.py` et les contrôleurs portail `sale`, `account_payment`.
Ces interfaces natives ne démontrent pas la compatibilité de toute localisation,
extension ou prestataire tiers ; leurs validations restent spécifiques.

## Mise à jour

Version Ventes `20.0.2.3.0`. Aucun paiement, facture, prix, programme, inscription,
référence bancaire ou audit antérieur n’est supprimé ou recalculé par la migration.
Les cinq champs d’ancienne vérification bancaire restent consultables, figés côté
serveur ; le compteur historique de journal reste stocké sans verrou ni usage métier.
L’ancien assistant de contrôle bancaire est désactivé par son identifiant XML stable.
La migration marque par lots les reçus déjà protégés ou rapprochés d’une facture
de formation. Réexécuter la mise à jour conserve les mêmes preuves et habilitations.
Les avis de virement privés restent facultatifs et sans effet comptable.

## Recette courte sur base jetable

1. Activer une troisième devise, configurer ses taux et une liste native à formule.
   Depuis une société d’une autre devise, qualifier une demande, négocier prix et
   remise, confirmer puis vérifier version et quotas personne/forfait.
2. Facturer, enregistrer un paiement partiel dans une autre devise puis un avoir ;
   rapprocher avec les outils natifs et vérifier résiduels, arrondis et écarts.
   Refaire avec caisse, autre méthode installée et relevé. Aucun accès pédagogique
   ne doit s’ouvrir automatiquement.
3. Vérifier devis/facture/reçu et leurs pièces/messages : contact habilité, collègue
   non habilité, anonyme avec jeton, révocation et dérapprochement. Vérifier également
   les routes de paiement directes. Un utilisateur interne reste soumis à ses droits
   et à sa société ; un paiement ordinaire garde son comportement natif.
4. Mettre à jour une copie V2 fictive, comparer pièces, montants, rapprochements,
   références et audits, puis répéter. Installer aussi sur une base vierge.

Les résultats réellement exécutés et les limites sont consignés dans la PR.
