# S02.1 Politique documentaire et protections natives

Référence : [#50](https://github.com/Progideo/training_management/issues/50),
COM03 et SEC01. Ce préalable du [cadrage S05 validé](s05-private-materials.md)
consolide les protections de S02 sans changer les habilitations ni les parcours.
Le socle pédagogique reste indépendant de l'intégration Ventes.

## Règles retenues

Les permissions natives restent obligatoires. Les restrictions globales existantes
sur devis et factures restent dans `security/ir.access.csv` : elles limitent la
lecture portail aux contacts nommément habilités. Le client commercial, son arborescence
de contacts et une commande confirmée ne donnent aucun accès pédagogique.

Le service privé `training.document.policy` fournit seulement les restrictions
supplémentaires nécessaires aux chemins natifs qui acceptent un jeton ou un ancien
destinataire, ainsi que les destinataires d'envoi. Il ne remplace pas les ACL,
n'autorise aucune écriture et ne renvoie aucun contenu à une route publique.
Les lectures privilégiées concernent uniquement les métadonnées de décision.
Aucun référentiel supplémentaire d'habilitations n'est créé. Pour un salarié,
la résolution d'un jeton réapplique les ACL et règles natives de société et du
document, ainsi que celles de la pièce. Un objet déjà élevé par le standard ne
conserve pas cette élévation pour la décision. Hors document formation, le
comportement natif des jetons est conservé.

Devis et facture conservent chacun leur liste. Le reçu utilise l'intersection des
contacts autorisés sur ses factures rapprochées ; aucun destinataire externe pour
un paiement non affecté ou mêlant formation et autres factures. Les pièces et
messages suivent leur document d'origine. Sans adresse de courriel, un contact
habilité peut toujours consulter son devis/facture ; il n'est pas destinataire d'envoi.

Proposer des destinataires ne garantit pas l'envoi : vérifier aussi le courriel
préparé, les notifications et le transport, y compris après révocation et reprise.
Les adresses libres ne contournent pas une habilitation nominative. Les notifications
internes gardent leurs règles natives ; un envoi explicite de document conserve
l'obligation d'un destinataire nommé autorisé. Aucun compte portail n'est imposé
au seul destinataire d'un courriel. Contrôler aussi chaque pièce jointe selon sa
source, même quand le courriel porte sur un autre dossier ou ne porte pas sur une
formation. Les destinataires doivent respecter toutes les sources protégées.
Ce contrôle précède la lecture privilégiée des octets et la transformation native
des gros fichiers en liens. Un document déjà reçu ne peut être rappelé.

## Standard vérifié et adaptations conservées

Image Community exacte : `20.0-20261015`,
`odoo@sha256:61e3c71b0503c5f658e604c3e340bede20b97d05f726179fa006eae50a32fd23`.
Chemins natifs sous `/usr/lib/python3/dist-packages/odoo/addons/`.

Deux surcharges sont supprimées après lecture du code natif :

- `mail.compose.message._action_schedule_message` : le standard appelle déjà
  `_prepare_mail_values` avant de créer le message planifié. La même protection
  couvre donc envoi immédiat et programmation, sans double préparation.
  Le point d'extension natif `_notification_parameters_whitelist` de
  `mail.scheduled.message` conserve uniquement pour les documents formation le
  paramètre `notify_skip_followers` déjà produit par le compositeur. Sans cela,
  la publication différée réintroduirait les abonnés exclus de l'envoi immédiat.
- `mail.message.export_data` : le standard refuse déjà l'export aux personnes
  qui ne sont pas administratrices. Conserver ce refus natif suffit ; aucun
  droit d'export n'est ajouté aux commerciaux ou au portail.

L'assistant `account.move.send.wizard._compute_mail_partners` reste nécessaire :
le standard utilise `_get_default_mail_partner_ids` avec un modèle de courriel,
mais revient au partenaire commercial sans modèle. L'adaptation couvre ce second
cas ; elle lit la même politique que le service natif d'envoi.

Les règles natives d'accès aux messages peuvent accepter l'auteur ou un destinataire
historique. Les chemins binaires et portail peuvent accepter un jeton valide.
Ces mécanismes ne prouvent pas l'habilitation nominative actuelle : les points de
contrôle suivants restent nécessaires. La politique centralise la décision ;
elle ne supprime pas les différents points où cette décision doit être appliquée.

| Surcharges conservées dans le périmètre #50 | Justification | Tests Odoo de référence |
| --- | --- | --- |
| `sale.order`, `account.move`, `account.payment` : `_get_thread_with_access` | Les raccourcis natifs de discussion doivent respecter le mandat courant. | `test_named_contact_required_even_with_a_valid_token`, `test_invoice_requires_its_own_named_contact`, `test_native_eur_down_payment_and_final_invoice` |
| Mêmes modèles : `_message_get_default_recipients`, `_notify_get_recipients` | Proposer les contacts autorisés et filtrer les notifications externes, sans changer les notifications internes natives. | `test_message_notification_filters_unauthorized_external_recipients`, `test_invoice_requires_its_own_named_contact`, `test_native_eur_down_payment_and_final_invoice` |
| `mail.message` : `_access_domain`, `read`, `_get_with_access` | Recalculer les droits après révocation, y compris lecture directe et objet privilégié fourni par un contrôleur. | `test_revoked_message_recipient_cannot_read_new_content_by_rpc`, `test_message_file_and_binary_entry_points_recheck_revocation`, recette reçu du test commercial |
| `ir.binary` : `_find_record`, `_get_stream_from` | Contrôler résolution par jeton et diffusion d'un enregistrement déjà résolu, sans toucher aux fichiers hors formation. | `test_attachment_token_cannot_bypass_contact_grant`, `test_message_attachment_follows_document_grant`, `test_message_file_and_binary_entry_points_recheck_revocation`, `test_unallocated_receipt_and_non_training_native_fallback`, `test_internal_and_foreign_company_tokens_keep_native_permissions` |
| `mail.compose.message` : `_compute_recipient_partners`, `_prepare_mail_values` | Destinataires natifs du devis/reçu et contrôle des valeurs effectivement préparées, y compris programmation. | `test_quotation_pdf_mail_requires_named_recipient`, `test_native_scheduled_composer_uses_guarded_preparation`, recette reçu du test commercial |
| `mail.template.send_mail_batch` | Bloquer les destinataires libres ou forcés en API, même sans assistant. | `test_quotation_pdf_mail_requires_named_recipient`, `test_invoice_requires_its_own_named_contact`, recette reçu du test commercial |
| `mail.mail._prepare_outgoing_list` | Revérifier le dossier du courriel et chacune des sources de pièces avant transport et à la reprise de la file. | `test_queued_pdf_revalidates_recipients_at_transport_and_retry`, `test_ordinary_mail_cannot_send_a_foreign_protected_attachment`, recette reçu/facture du test commercial |
| `mail.scheduled.message._notification_parameters_whitelist` | Conserver le paramètre natif d'exclusion des abonnés pour les seules diffusions formation, sans réécrire le scheduler. | `test_scheduled_delivery_keeps_selected_recipients_only`, `test_scheduled_revocation_does_not_notify_the_old_recipient`, `test_non_training_schedule_keeps_native_followers` |
| `account.move.send` : `_get_default_mail_partner_ids`, `_get_mail_params`, `_send_mail` ; assistant `_compute_mail_partners` | Couvrir le circuit natif de facture, les destinataires forcés et les abonnés ; défaut sans modèle également protégé. | `test_invoice_requires_its_own_named_contact`, `test_invoice_sending_without_template_keeps_named_defaults`, `test_native_invoice_sender_ignores_followers_outside_selected_contacts` |
| Contrôleurs : `_document_check_access` via les quatre classes natives | Conserver les refus malgré un jeton ; utiliser ensuite les contrôles natifs du document. | Tests HTTP devis/facture et transactions portail |
| Contrôleurs : `_get_payment_values`, `invoice_transaction`, `portal_order_transaction` | Le lancement exclut les transactions en ligne, y compris appel direct des routes. | `test_portal_does_not_offer_payment_or_create_transaction`, `test_invoice_requires_its_own_named_contact` |
| `account.payment` : `create`, `write` et fabrique contrôlée `_create_training_guarded_payments` | Référence et audit bancaire imposés aussi par import/API et état de création. | `test_paid_write_create_and_audit_are_guarded`, recette bancaire du test commercial |
| `account.payment.register` : `_create_payment_vals_from_wizard`, `_create_payment_vals_from_batch`, `action_create_payments` | Conserver les métadonnées et contrôles banque/méthode/devise dans les deux modes natifs. | `test_batch_payments_preserve_bank_metadata`, `test_receipt_intersection_and_mixed_documents_use_real_reconciliation`, recette bancaire du test commercial |
| `account.partial.reconcile.create` | Vérifier les rapprochements directs et les lignes de relevé ; l'assistant seul ne couvre pas ce chemin. | `test_native_eur_down_payment_and_final_invoice` |
| `payment.transaction.create`, `write` | Refuser l'association d'une formation à une transaction, à la création comme après coup. | Tests de création du test commercial et `test_transaction_write_cannot_attach_a_training_document` |
| `payment.link.wizard` : `default_get`, `create`, `write`, `_compute_link` | Refuser les liens en ligne dans tous les points d'entrée de l'assistant natif. | Tests de création/défauts du test commercial et `test_payment_link_write_and_compute_still_refuse_training` |
| `sale.order` : `create`, `write`, `action_quotation_send`, `action_confirm`, `_has_to_be_paid` | Préserver validité de l'offre, engagements et absence de paiement en ligne. | `test_direct_sale_state_and_currency_are_guarded`, `test_missing_or_changed_tariff_cannot_be_sent_or_confirmed`, tests HTTP paiement |
| `account.move` : `_has_to_be_paid`, `_compute_display_link_qr_code`, `_get_portal_payment_link`, `_generate_portal_payment_qr` ; `account.move.line._get_aml_vals` | Retirer appels au paiement et libellés révélant une facture non habilitée. | `test_native_eur_down_payment_and_final_invoice`, `test_invoice_requires_its_own_named_contact` |

Les helpers métier et champs comptables ne sont pas de nouvelles règles d'accès.
Les méthodes des produits, prix et qualifications S02, hors consolidation #50,
gardent leurs tests existants. Les protections comptables ci-dessus ne sont pas
supprimées comme doublons d'une politique de confidentialité.

## Conservation et recette courte

Aucune migration de données métier ni copie de fichier. L'addon d'intégration
passe en `20.0.1.10.4` ; les listes, messages, pièces, jetons existants et la file
restent conservés, avec la réévaluation des droits lors de leur utilisation.
Le gel et l'autorisation des PDF de programme ainsi que les dossiers sensibles
S04 restent gérés par leurs mécanismes existants. Aucun droit pédagogique nouveau.

1. Avec vrais profils restreints, ouvrir devis/facture autorisés et refuser pair,
   autre société, public et utilisateur interne sans rôle. Révoquer puis tester à
   nouveau message, URL et fichier, y compris identifiant ou jeton conservé.
2. Préparer devis, facture sans modèle et reçu : vérifier les seuls destinataires
   autorisés ; refuser adresse libre, forçage API et abonné non autorisé. Programmer
   un message puis révoquer avant transport ; la reprise ne doit pas contourner le refus.
3. Tester reçu non affecté, intersection de deux factures et paiement mixte avec de
   vraies écritures rapprochées. Vérifier acompte, partiel/solde, avis sans effet
   comptable, référence répétée, autre devise et interdiction du paiement en ligne.
4. Installer sur base vierge ; mettre à jour depuis S03.1 via le scénario S04
   existant et depuis #56 avec Website/eLearning via `tests/ci/run_s021.sh`.
   Comparer les historiques, contacts autorisés, file et octets du PDF conservé,
   ainsi qu'une facture comptabilisée, son règlement rapproché et son audit bancaire.
   Les 21 étapes de CI Odoo restent inchangées. Le workflow #50 ajoute la preuve
   depuis #56 sans nouvelle infrastructure permanente.

Les résultats réels et les journaux sont dans la PR. Un succès de lecture du code
ne remplace pas un test de profil restreint ou de route HTTP.
