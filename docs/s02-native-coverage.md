# S02 — Étude du circuit commercial natif et écarts

État du 20 octobre 2026, première étude préalable au code métier.
Besoin : [#12](https://github.com/Progideo/training_management/issues/12).
[Cadrage accepté](https://github.com/Progideo/training_management/issues/12#issuecomment-6290595309).
Cette étude ne termine pas S02 et ne constitue pas une recette fonctionnelle.
Pour l'état de validation plus récent et la décision de lancement sans import
bancaire, voir la [validation complémentaire du 22 octobre 2026](s02-crm-quotation.md#validation-complémentaire-du-22-octobre-2026).

## Reprise vérifiée

- Dépôt local propre à la reprise, tête S01 `7cb4e4c`.
- `main` distant et `origin/main` après actualisation :
  `8343a0977ab4cb973a0a113f6a93485ef576cf5e` (fusion #42).
- Branche S02 créée depuis ce commit : `feat/12-s02-commercial-flow`.
- Consignes du dossier parent et documents de référence sous `sources/` lus ;
  aucun `AGENTS.md` trouvé dans l'arbre du dépôt à ce commit.
  Les références synchronisées restent en lecture seule, audit Odoo 19 suspendu.
- Serveur interrogé en lecture seule : `Odoo Server 20.0-20261015`.
  Sources étudiées directement issues de `/usr/lib/python3/dist-packages/odoo`.
  `release.py` porte la provenance déclarée `49529f034a60e4e9838e08e0a5616e5f2f38c601` ;
  ce n'est pas une comparaison exhaustive avec le dépôt amont.
- SQL exécuté dans `BEGIN READ ONLY` / `ROLLBACK`, limité à l'état des modules.
  Aucune installation, mise à jour, modification de configuration ou de recette.

Les anciennes sections S01 de `native-coverage.md` retracent des états
intermédiaires. Le résultat final de référence est la
[recette multilingue et multi-sociétés de #42](https://github.com/Progideo/training_management/pull/42#issuecomment-6290431549),
module `20.0.1.0.3` ; les tests et la recette S01 ne valent pas validation S02.
L'inventaire de recette est réservé au Project GitHub privé nº 1 : aucun
inventaire, mot de passe ou export de base n'est ajouté à ce dépôt public.
Son enregistrement dans une note privée du Project a été confirmé et vérifié
dans le chat précédent ; cette fiche est la référence de reprise des fixtures.

## Disponibilité exacte

| Module | État en développement | Version installée ou manifest lu | Utilité / dépendances directes décisives |
| --- | --- | --- | --- |
| `training_management` | installé | 20.0.1.0.3 | Catalogue pédagogique distinct, programmes immuables |
| `sale_management` / `sale` | installés | 20.0.1.0 / 20.0.1.2 | Devis/commandes ; `sale` dépend notamment de `account_payment` |
| `account` | installé | 20.0.1.6 | Factures, échéances, paiements et rapprochements |
| `crm` | non installé | manifest 1.9 | Demande/qualification, contacts, activités ; dépend de `sales_team`, `mail`, etc. |
| `sale_crm` | non installé | sans version explicite | Pont opportunité–devis ; dépend de `sale,crm`, auto-installable |
| `payment` | installé | 20.0.2.0 | Mécanismes de transaction ; ne prouve aucun prestataire actif |
| `payment_custom` | non installé | manifest 2.0 | Mode virement disponible, dépend de `payment` |
| `website_sale` | non installé | manifest 1.1 | Panier/commande ; dépend notamment de `website,sale,website_payment,delivery,html_builder` |
| `event` | non installé | manifest 1.9 | Événement daté, capacités, inscriptions |
| `event_sale` | non installé | manifest 1.3 | Billets/ventes ; dépend de `event_product,sale_management`, auto-installable |
| `website_event_sale` | non installé | sans version explicite | Pont Web, dépend de `website_event,event_sale,website_sale`, auto-installable |
| `website` / `website_slides` | installés | 20.0.1.0 / 20.0.2.7 | Site / eLearning existants, sans activation commerciale supplémentaire |

Les manifests standard examinés déclarent LGPL-3. Les dépendances transitives
et leurs effets d'installation devront être relevés sur base jetable avant
activation ; cette liste ne signifie pas qu'elles sont déjà toutes installées.
`website_sale_slides` est aussi présent dans les sources : il dépend de
`website_slides,website_sale` et inscrit le client du bon de commande aux cours
liés lors de la confirmation (`models/sale_order.py:_action_confirm`). Son état
en base n'a pas été interrogé dans ce relevé ; aucun usage S02 n'est proposé.

## Matrice couverture / écarts

« Code » signifie lecture de la distribution exacte, sans preuve d'exécution
fonctionnelle. Les chemins ci-dessous sont relatifs à `odoo/addons/`.

| Exigence | Standard constaté (preuve de code) | Configuration réutilisable | Extension / spécifique justifié | Incertitude / validation attendue |
| --- | --- | --- | --- | --- |
| COM01 — demande et qualification | `crm/models/crm_lead.py` : piste/opportunité, contact, étapes, activités ; `sale_crm/models/crm_lead.py:action_new_quotation`, `_prepare_opportunity_quotation_context` et `sale.order.opportunity_id` | Équipes, étapes, affectation commerciale | Champs formation, type individuel/groupe, besoin, modalité, dates souhaitées, effectif, devise demandée ; propagation contrôlée vers devis | `expected_revenue` CRM utilise la devise société : ne pas le confondre avec le budget MAD/EUR demandé. Tester un devis EUR depuis une société de test dans une autre devise |
| COM01 — demande répétée | `crm.lead._get_lead_duplicates` recherche des similitudes partenaire/email ; fusion disponible. Ventes signale certains devis proches | Avertissement des doublons possibles à la qualification | Clé de demande/rejeu et unicité en base pour une entrée identifiée ; ne pas interdire plusieurs besoins légitimes du même contact | Double clic, création directe, concurrence ; détection heuristique CRM distincte de l'idempotence. Aucun formulaire public dans cet incrément |
| CAT02 / COM01 — version contractuelle | Produits et lignes de vente standards, mais aucun lien vers `training.program.version` dans le standard | Produits de service distincts du catalogue | Formation liée au produit, version explicitement choisie sur la ligne ; validée/publiée et de même société ; relation conservée, aucune sélection automatique de la dernière version | Refuser brouillon, mauvais produit/société, substitution après confirmation ; conserver le lien après retrait de la version ; copie/révision et facturation à tester |
| COM02 — MAD/EUR indépendants | `product/models/product_pricelist_item.py:_compute_price` : prix fixe dans la devise de la liste ; conversion possible pour les prix de base et suppléments. `product_pricelist.py:_compute_price_rule` peut utiliser une règle vide en l'absence de tarif | Deux listes et prix fixes explicitement définis ; services personne et forfait distincts | L'envoi et la confirmation exigent une règle fixe propre au produit, réellement applicable, sans supplément converti ; prix de ligne conforme et remise nulle | Tests CI : absence de tarif, montant modifié, règle de remise, MAD/EUR indépendants. L'archive séparée de la version de règle et les prix négatifs restent à étudier ; aucun montant réel inventé |
| COM02 — personne/forfait | `sale.order.line` : produit, quantité, unité, prix et taxes standards | Personne : quantité vendue ; forfait : quantité de forfaits, effectif distinct | Base commerciale sur le produit ; quantité contrôlée selon l'effectif ou un forfait, sans création d'inscription | Test CI : un forfait de 12 personnes facture une unité ; les cas de plusieurs lignes tarifaires restent à cadrer |
| COM02 — une devise et révision | `sale/models/sale_order.py:_compute_currency_id` prend la devise de la liste ; `write` interdit de changer `pricelist_id` sur une commande confirmée ; `_prepare_invoice` transmet `currency_id` | Une liste par devise, une devise par bon et facture | Confirmation et envoi contrôlent la devise demandée ; modification de devise d'une liste utilisée par une commande de formation confirmée refusée, même entre sociétés | Test ORM CI de la devise de liste. Révision traçable, réouverture et facturation seront validées dans les incréments suivants |
| Rôles commerciaux | `sale.order.partner_id`, `partner_invoice_id`, `partner_shipping_id` ; facture créée pour l'adresse de facturation | Contacts/adresses Odoo réutilisés | Commanditaire, payeur prévu et contact administratif ajoutés à CRM et au devis, transmis par la conversion native ; payeur prévu sans effet sur le débiteur comptable ; contrôle multi-sociétés et gel après confirmation | Tests ORM CI réussis : contacts distincts, facture préparée pour `partner_invoice_id`, payeur externe sans accès par son seul rôle, contact d'une autre société refusé. Les contacts internes du devis et la liste des avis sont réservés aux utilisateurs internes ; l'accès documentaire de collègues du même client exige maintenant une habilitation par document |
| COM03 — factures/acompte/solde | `sale/wizard/sale_make_invoice_advance.py:_create_invoices` : pourcentage, montant fixe, déduction des acomptes ; `account.move` calcule montant résiduel et état de paiement | Politique de facturation du service, échéanciers et journaux approuvés | Assistant standard réutilisé, sans second solde métier ni nouvel état « payé » indépendant ; PDF final avec libellé d'acompte générique pour ne pas exposer le numéro d'une facture non habilitée, référence conservée en interne | Test CI fictif : forfait EUR, acompte de 25 %, facture finale nette, même débiteur et devise ; règlement comptabilisé de 300 EUR sur la facture finale de 1 200 EUR, résiduel 900 EUR et état « partiel ». Le PDF final a été rendu et son libellé vérifié localement. Ce test ne prouve pas la réception bancaire. Annulation/avoir, fiscalité, présentation légale de l'acompte et paramétrage réel restent à valider. Une échéance de facture et un acompte facturé sont deux objets différents |
| COM03 — avis de virement | `payment_custom/models/payment_transaction.py:_apply_updates` met un virement ordinaire en `pending` ; `pay_on_invoice` et un marqueur spécifique peuvent le mettre en `done` | Aucun prestataire requis pour le circuit interne ; ne pas installer `payment_custom` pour enregistrer un avis | `training.bank.transfer.notice` interne et privé : commande confirmée, facture facultative de la même commande et devise, montant/date/référence déclarés, retrait par comptabilité. Aucun `account.payment` créé et aucun effet sur le résiduel ou l'accès pédagogique | Test ORM : avis déclaré sans règlement, accès portail refusé, retrait réservé à la comptabilité. Aucune preuve bancaire ni saisie portail ; pièces jointes et transmission client restent à cadrer |
| COM03 — règlement constaté | `account/models/account_payment.py:action_post` fait passer à `paid` ; `action_validate` à `reconciled` ; `account.move._compute_payment_state` utilise résiduel et rapprochements | Rôle financier et procédure de preuve bancaire, comptes d'attente et journaux validés | Contrôles métier sur la constatation, en conservant la comptabilité standard ; l'assistant des factures de formation exige un journal bancaire, la méthode manuelle et l'attestation d'une vérification bancaire préalable. Un paiement direct porteur d'une référence de formation subit les mêmes exigences ; l'auteur et la date de validation sont conservés | Tests de refus d'un journal de caisse et d'un paiement non vérifié. L'attestation du comptable n'est pas une preuve bancaire indépendante. Un paiement direct sans référence ne peut pas être rapproché de la facture de formation. Une ligne de relevé directement affectée au compte client réduit le résiduel de 850 à 800 EUR avec ou sans libellé, sans `account.payment`. Décision du 20 octobre : ligne sans référence autorisée après contrôle manuel comptable ; vérifier preuve, imports et absence de rapprochement automatique avant revue |
| COM03 — référence répétée | `account.payment._compute_duplicate_payment_ids`, `_fetch_duplicate_reference` : contrôles partenaire/montant/date/type/société ; pas une garantie d'unicité de référence bancaire | Alerte native utile, à conserver | Référence bancaire dédiée dans l'assistant des factures de formation ; normalisation casse/espaces, recherche des paiements comptabilisés dans la société et le journal, verrou du journal avant validation ; motif obligatoire pour une répartition volontaire sur plusieurs paiements | Test CI fictif : même référence et montants 300/100 EUR, refus sans motif, acceptation de la répartition avec motif. La saisie directe sans référence reste possible, mais son rapprochement avec une facture de formation est refusé. Les lignes de relevé et imports restent à cadrer ; la référence n'est pas une preuve bancaire |
| COM03 — autre devise | `account/wizard/account_payment_register.py` gère devise du journal, source, conversion et écarts | Taux, journaux/devises et traitement des écarts approuvés | Décision du 20 octobre : refus au lancement d'un règlement de facture de formation dans une autre devise. L'assistant, le paiement direct et le rapprochement d'une ligne de relevé contrôlent la devise ; le relevé de caisse est aussi refusé | Tests de refus d'une devise différente dans l'assistant et sur un relevé MAD rapproché d'une facture EUR. Aucun taux ni écart n'est inventé ; ce parcours ne sera ouvert qu'après une règle comptable distincte |
| COM03 — aucun paiement en ligne | `sale.order._has_to_be_paid`, le formulaire du portail Ventes et les transactions `payment.transaction` acceptent aussi un montant transmis par URL | Virement bancaire sans prestataire en ligne au lancement | Aucun appel au paiement du portail pour un devis de formation ; transactions et assistant de lien refusés pour ses commandes et factures ; lien et QR de paiement en ligne retirés du rapport de facture | Tests serveur et HTTP : acompte de 25 %, montant explicite dans l’URL, absence de formulaire, route JSON refusée, liens documentaires bloqués. Un lien `/payment/pay` construit sans identité documentaire reste indissociable d’une formation ; vérifier les prestataires actifs au lancement |
| SEC01 — portail commercial | `sale/security/ir.access.csv:sale_order_rule_portal` et `account/security/ir.access.csv:account_invoice_rule_portal` utilisent `child_of user.commercial_partner_id` ; `portal/controllers/portal.py:_document_check_access` et `ir.binary._find_record` acceptent aussi des jetons valides | Profils internes commerce/finance et portail pour les externes | Décision du 20 octobre : contacts nommément habilités par devis et par facture, vides par défaut. Règles globales de lecture, contrôle des pages à jeton et des pièces binaires liées aux documents de formation, avec connexion obligatoire. Les contacts commerciaux internes et les avis restent protégés par sécurité de champ | HTTP local : devis et factures, PDF, pièces directement liées et pièces de message, aperçu texte, discussion et révocation testés avec profils restreints. L'aperçu PDF natif refuse le jeton ordinaire de la pièce. Autres routes à surveiller avant ouverture ; les pièces déjà envoyées hors portail ne sont pas révocables |

L'habilitation d'une facture issue d'une commande de formation reste vide par
défaut. Un commercial disposant du droit d'écriture sur la facture peut
reprendre explicitement les contacts autorisés de la commande tant que la
facture est en brouillon. Si plusieurs commandes sont liées, seuls les
contacts autorisés sur **toutes** sont proposés ; une facture mêlant une
commande non liée à une formation est refusée. La copie ne synchronise pas les
habilitations : une révocation sur la commande exige une revue des factures
déjà créées.
| SEC01 — PDF par courriel | Les assistants natifs `mail.compose.message` et `account.move.send.wizard` proposent le client commercial par défaut et joignent les rapports PDF ; le reçu de paiement standard propose aussi le client générique et joint son PDF. Les messages du fil notifient leurs destinataires directs et abonnés ; `mail.template.send_mail_batch` accepte des destinataires forcés | Décision du 20 octobre : PDF joint uniquement aux contacts nommément habilités sur le document | Destinataires proposés depuis la liste d'habilitation de chaque devis ou facture ; pour un reçu de paiement, intersection des habilitations des factures rapprochées. Contrôle serveur dans les assistants, les notifications, les pièces et l'API directe des modèles d'e-mail, y compris après révocation. Aucun destinataire externe si le paiement est encore non affecté ou mêle factures de formation et autres factures | Tests locaux avec contacts habilité et non habilité, destinataire direct, abonné, adresse libre et forçage via `mail.template` ; deux courriels fictifs de devis/facture capturés par SMTP local, un PDF chacun. L'assistant du reçu a proposé le seul contact habilité et un PDF, sans envoi. Liens `/mail/view` du devis et de la facture contrôlés par HTTP avec révocation. Le SMTP réel et les autres modèles restent à valider. Un PDF déjà envoyé ne peut être révoqué et une boîte e-mail partagée ne garantit pas une lecture individuelle |
| INS03 — aucun accès par vente | Catalogue S01 sans accès pédagogique ; `website_sale_slides` inscrit le client aux cours liés lors de `_action_confirm` | Produits S02 sans lien déclenchant la vente d'un cours ; aucun pont d'inscription activé | Contrôle de non-régression sur les intégrations présentes ; aucune inscription ou ouverture pédagogique ajoutée à la confirmation | Tester aussi l'installation future d'un pont ; le client/payeur n'est pas nécessairement participant |

## Website Sale et Événements étudiés dès S02

- Website Sale représente des produits commerciaux et des paniers ; ce n'est pas
  une publication automatique du programme pédagogique S01. Son contrôleur
  `controllers/main.py:shop_payment_validate` peut valider un panier gratuit.
  Les routes de signature du portail Ventes peuvent également valider une commande.
  Masquer un bouton de paiement ne démontre donc pas l'absence d'autres chemins
  de confirmation. Publication, commande Web, consentement et habilitations
  attendent le cadrage séparé déjà convenu.
- Événements apporte événements, billets, capacités et inscriptions.
  `event_sale/models/sale_order.py:action_confirm` appelle
  `sale.order.line._init_registrations` pour les lignes suivies comme événement.
  Cette dernière crée autant d'inscriptions que la quantité vendue, avec des
  différences entre gratuit/payant et confirmation simple/multiple.
  `event_registration.py:_compute_registration_status` lie aussi les états à la vente.
  Ce comportement ne démontre ni le registre unique demandé, ni les places non
  nominatives, ni l'autorisation pédagogique indépendante, ni la concurrence
  sur la dernière place. Aucun choix de modèle de session n'est conclu ici.
- `event_product`, `event_sale`, `website_event_sale` comportent des mécanismes
  d'auto-installation. Le graphe d'installation doit être testé avant ajout de
  Website Sale ou Événements sur une base déjà équipée.

Conséquence technique : commencer avec `training_management_sale`, addon
optionnel d'intégration dépendant de `training_management`, `sale_management`
et `sale_crm`. Le socle S01 reste indépendant du commerce et du site.
Ce choix applique les orientations acceptées ; aucun nouveau moteur de ventes,
référentiel clients, moteur de tarification ou système comptable n'est créé.
Website Sale, Événements et leurs ponts restent des intégrations ultérieures
après le cadrage de leurs parcours, sans retarder leur étude.

## Droits et séquencement d'implémentation

1. Demande interne CRM avec champs de qualification et transmission au devis ;
   produits/services et programme explicite sur ligne. Lecture des seules
   versions éligibles pour le commercial, sans modification du catalogue.
   Le commercial ne reçoit pas le rôle de coordinateur par implication.
2. Tarifs personne/forfait et devise contrôlée, version conservée à confirmation,
   document commercial identifiant sans ambiguïté le programme et sa version.
   PDF pédagogique contractuel à rattacher à la version, sans pièce privée
   globalement exposée via un document produit.
3. Avis de virement distinct, contrôles de référence/devise, réutilisation des
   factures, acomptes et paiements natifs. Les paramètres comptables réels restent
   en attente du responsable comptable ; les tests utilisent des valeurs fictives.
   Le compte d'acompte natif `res.company.downpayment_account_id` est exposé sur
   la fiche société au responsable comptable. Il s'applique à **toutes** les
   factures d'acompte de ventes de cette société, pas seulement aux formations ;
   aucun numéro de compte ni taux de taxe n'est fixé dans l'addon. Un test fictif
   vérifie l'imputation automatique sur un compte de passif courant et la reprise
   de l'acompte sur la facture finale créée après comptabilisation de l'acompte.
   Le compte de revenus natif `product.template.property_account_income_id`,
   lui aussi propre à chaque société, est accessible au responsable comptable
   sur les produits liés à une formation. Ce réglage s'applique à toutes les
   factures de ce produit dans la société active ; le module n'impose aucun
   numéro de compte de prestation national.
4. Habilitations et recette du portail commercial de S02 avant toute ouverture
   aux clients. Le portail entreprise complet P05 n'est pas déclaré livré.

Les rôles commerce, finance et coordination restent distincts et cumulables
uniquement par attribution explicite. Les refus doivent être contrôlés avec les
véritables comptes restreints, pas seulement un administrateur.

## Validation à exécuter avant livraison métier

- Installation vierge de l'addon d'intégration sur l'image exacte ; tests natifs
  métier, refus ORM et accès directs sous commercial, finance, lecteur,
  coordinateur, portail et interne sans rôle ; deux sociétés indépendantes.
- Mise à jour depuis S01 sur une base jetable contenant un historique synthétique,
  et même scénario avec Website/eLearning déjà présents ; comparaison des
  programmes, traductions et documents avant/après.
- Incident Website de #42 : la colonne `ir_ui_view.visibility` peut être obligatoire
  avant que le modèle Website soit chargé. La reprise déjà démontrée chargeait le
  XML du dialogue via `odoo.tools.convert.convert_file` dans un registre complet,
  puis lançait la mise à jour native. Ne pas supposer que l'installation d'un
  nouvel addon rencontre forcément le même défaut ; tester cette combinaison.
  Aucun patch cœur, retrait de contrainte SQL ou dépendance Website artificielle.
- Recette bout en bout : groupe de 12, forfait EUR, version V1 conservée après V2,
  acompte/partiel/solde, avis sans effet comptable, doublon/rejeu/concurrence,
  devise différente et révision ; aucune inscription ou ouverture pédagogique.
- Tests HTTP portail, PDF/pièces/jetons et refus hors mandat avant livraison.
  La recette navigateur reste distincte des tests serveur.

## Résultats et limites de cette étape

Exécutés : vérification Git local/distant, lecture du cadrage et de #42,
version serveur, état des modules en transaction SQL de lecture seule,
lecture des sources exactes et comparaison d'empreintes entre serveur et copie
locale pour les quatre fichiers repères ci-dessous. Les sources copiées restent
hors Git. La CI de la PR S02 installe l'addon sur base standard et sur base
Website/eLearning, puis le met à jour avec comparaison de l'historique S01.
Neuf tests S02 passent dans chaque configuration, dont un test HTTP du devis
avec montant explicite et appel direct à la route de transaction. Les recettes
navigateur, les liens de paiement génériques et les accès documentaires complets
du portail restent à réaliser avant une ouverture externe.

Seuls arbitrages à préparer : paramètres comptables/fiscaux et traitement des
écarts avec le responsable comptable ; parcours Web/places/sessions lors de leur
cadrage séparé. Aucun renouvellement du cadrage commercial déjà accepté n'est requis.
Aucune fusion ni aucun déploiement S02 autorisé par cette étude.

## Empreintes des sources lues

SHA-256 ; chemins relatifs à `odoo/`. Les quatre premières empreintes ont aussi
été relevées côté serveur et comparées à la copie locale.

```text
40de3f257ad530160009f2ebf00454b45222973d514837c1b55c146c0301290c  release.py
dfb51dfbd9b76c60f7ef80c1b5319384dd59455df9d6d9f834a8e2a527830645  addons/sale/models/sale_order.py
ac185c2e08b3a70631151c4317e96dd20202e13b5a86a6833b124f52ebf6c694  addons/account/models/account_payment.py
643ee4b9c680f1cf6d144fb33ff2aeea854863c4af59acf5ec68c4804f9afd1f  addons/sale/security/ir.access.csv
72b78123f2fb69e84bf1fdaacb3f80b9afed494186e634f5f752fbc5dc1951fc  addons/crm/models/crm_lead.py
199f68394b0a1701c1bd618ca0c46209c7a1d2a6d7d0d1951dceef562c49673b  addons/sale_crm/models/crm_lead.py
7104f543f80bda270ce8a2cfe668f73a727e533970fe0417cfccfaff14a0dad5  addons/product/models/product_pricelist.py
73ab03e037a82bc330a86c93eeb6b9efb4d0f013979250457de5937e5eff1aef  addons/product/models/product_pricelist_item.py
bcdbadf26088450d24664d8e686f9d24a7b1cdbc80d1d825e9c1ee4a06e3c52a  addons/sale/wizard/sale_make_invoice_advance.py
2cbd76cec77585f10f852c5fe944045ed31694f9dd85a0d64a33fce4274bc761  addons/account/models/account_move.py
0d730f0ba917d2da4be54597259f0fa7c9bc59b10aba983230992a69da1e7e29  addons/account/wizard/account_payment_register.py
b3453bde2c6726d484da52de1db886bd8c4dc0f48d7e6a518f5e8de6fb98c7b5  addons/account/security/ir.access.csv
306318b804f760e9ecac0f28fc7ef30a387de492c57e9ef49ef3efe639464eba  addons/portal/controllers/portal.py
af3d7d15398241c00c3344e9cca919c45652def412a6fd784f58f61615e4014f  addons/payment_custom/models/payment_transaction.py
ae3d68fa4832ea7ffbe368df284e8923dede32eded39115920dffceb9e5c323b  addons/website_sale/controllers/main.py
80ab8b602134bee84f170a6bb378c668f871d015745b3343e37758ab5a91089b  addons/event_sale/models/sale_order.py
614b6819fb0ec1ed17fca9c9d478ec1df845add5a36131cbdb1da89e0f2cd2fc  addons/event_sale/models/sale_order_line.py
ee77b271b6763b1f2367ffe7ac9863d61f2dd2e3e94262ac7ae274c659bfdb5f  addons/event_sale/models/event_registration.py
cb783eee09a276c55ae11434808e650d23fb240f1545a64466445baf06d2f7e2  addons/website_sale_slides/models/sale_order.py
```
