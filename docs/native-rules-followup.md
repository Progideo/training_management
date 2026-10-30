# Règles natives — complément à COM02/COM03

Suite de [#102](native-commercial-accounting.md), après revue des sept candidats.
Le périmètre pédagogique, les habilitations et les historiques restent protégés.

## Comportement

- Les offres acceptées figent leurs lignes pédagogiques, programmes et quotas.
  Les remises globales/forfaitaires, notes et autres lignes sans droit pédagogique
  suivent les règles natives. Transformer une ligne ordinaire en ligne pédagogique,
  ou déplacer une ligne pédagogique vers une offre acceptée, reste refusé.
- Contact administratif, commanditaire, payeur prévu et devise demandée peuvent
  être corrigés sous les droits natifs, avec suivi dans le chatter. Ils n’accordent
  aucun droit documentaire et ne changent ni débiteur comptable ni PDF conservé.
- Le catalogue utilise la langue du contexte natif, avec ou sans Website. Le français
  se configure dans Odoo ; changer de langue ne remplace pas le PDF contractuel.
- Survey impose déjà le seuil entre 0 et 100 par contrainte native. La publication
  conserve questions fixes, correction, durée finie et historique immuable.
- L’extension facultative `sale_invoice_address_fiscal` choisit l’adresse de
  facturation puis appelle le sélecteur natif, y compris positions manuelles et
  critères automatiques. Elle n’impose plus un choix binaire domestique/export.
  Les taxes existantes ne sont plus recalculées par une dépendance ORM supplémentaire :
  le changement de position dans le formulaire suit l’onchange natif ; un appel API
  doit demander explicitement le recalcul natif s’il est souhaité.
- L’identité des notifications utilise un modèle `mail.template` sur `res.company`,
  sélectionné par société. Seuls `email_from` et `reply_to` sont rendus ; contenu,
  destinataires, pièces et rapports du modèle ne sont pas repris. Sans modèle,
  les notifications existantes utilisent le domaine de messagerie/la société.
  La sélection du modèle conserve l’activation explicite des alertes et notifications
  de changement d’accès auparavant liée à la présence d’une adresse.
  Le changement d’expéditeur ne bloque plus une ancienne file. Les destinataires
  et leurs habilitations sont toujours revérifiés au transport.

## Mise à jour

Socle et Surveys `20.0.2.7.0`, Ventes `20.0.2.4.0`, extension fiscale `20.0.1.2.0`.
L’ancienne adresse est conservée en lecture seule dans la fiche société. Une
migration crée un modèle natif par société précédemment configurée, reprenant
exactement l’identité et l’adresse de réponse. Elle ne modifie aucun courriel,
état de distribution ou destinataire et ne lance aucun envoi. Les messages en
échec restent en échec jusqu’à une reprise explicite ; les messages envoyés ne
sont pas réexpédiés. Le rejeu ne crée pas de modèle supplémentaire.

Pour une ancienne politique fiscale activée, une position export sans critères
natifs reçoit un groupe de pays étrangers et devient automatique. Les positions
ayant déjà des critères restent intactes. La priorité native des positions manuelles
et automatiques s’applique désormais. Ces critères natifs sont également pris en
compte par les achats : vérifier les positions de la société avant déploiement.
Le groupe contient les pays présents à la migration ; toute évolution se configure
ensuite dans Odoo. Aucun document existant n’est recalculé par la migration.
Le champ d’ancienne position export reste consultable. Les profils C06 sont
optionnels ; leur application configure explicitement ces critères natifs.

## Recette courte

1. Confirmer puis déverrouiller une offre de parcours ; appliquer remise globale
   et forfaitaire, modifier une note et les contacts administratifs. Vérifier
   montants natifs, trace et absence de nouveau droit. Refuser modification de
   programme/quota et transformation d’une ligne de remise en ligne pédagogique.
2. Consulter une fiche avec deux langues actives, comparer recherche et contenu ;
   contrôler que les octets du PDF et les refus hors publication restent identiques.
3. Publier un examen avec seuil 0 puis 100 ; refuser -1 et 101 au stockage natif.
   Conserver les refus de durée invalide, accès non autorisé et correction prématurée.
4. Avec/sans politique fiscale : tester adresse de livraison différente, position
   manuelle prioritaire, critères automatiques, ventes/achats, API et formulaire.
   Comparer taxes de devis, commandes confirmées et factures comptabilisées.
5. Configurer un modèle d’identité, préparer une notification puis changer
   l’expéditeur. L’ancienne file reste intacte ; une révocation du destinataire
   bloque toujours le transport. Aucun destinataire/pièce du modèle ne doit fuiter.
6. Installer sur base vierge ; mettre à jour deux fois une copie fictive de #103.
   Comparer programmes/PDF, documents commerciaux/comptables, habilitations et
   courriels sortants/en échec/envoyés ; vérifier les deux sociétés et le rejeu.

Référence de code natif : Odoo Community `20.0-20261015`, image et provenance
identiques à [COM02/COM03](native-commercial-accounting.md#source-native-vérifiée).
Les résultats d’exécution restent dans la PR.
