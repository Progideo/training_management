# S02 — Demande CRM, devis et facturation native

> Référence historique S02. La [décision du 30 octobre 2026](native-commercial-accounting.md)
> remplace les restrictions MAD/EUR, prix fixes/remise nulle, virement manuel,
> vérification bancaire obligatoire et interdiction des paiements en ligne.
> Les preuves datées ci-dessous restent celles des règles anciennes ; elles ne
> constituent pas une validation des nouveaux parcours. Les protections documentaires demeurent.


Incréments demande/devis, tarifs et rôles commerciaux de [#12](https://github.com/Progideo/training_management/issues/12),
à relire avec la [matrice de couverture](s02-native-coverage.md).
Ce document décrit S02 livré par les PR #43 et #44 et son périmètre de recette.
L'installation en développement et l'ouverture aux clients restent des étapes séparées.

Le mode « Prix convenu au devis » et les offres de parcours complètes ou
partielles sont définis dans [P09.3](p09-commercial-paths.md). Les règles de
prix fixe décrites ici restent applicables aux offres conservant ce mode.

## Parcours interne livré

L'addon optionnel `training_management_sale` dépend de `training_management`,
`sale_management` et `sale_crm`. Il garde le catalogue S01 indépendant des ventes.
Un commercial qualifie une piste ou opportunité CRM en indiquant demande
individuelle/groupe, programme visé, effectif, devise demandée MAD/EUR,
modalité et dates souhaitées. Le standard CRM conserve responsable, client,
étapes et activités. La conversion native « Nouveau devis » reprend la demande,
le programme, l'effectif et la devise demandée sur le devis.

Une fiche produit Odoo de type service, rattachée à la même société que la
formation, peut être associée à une formation du
catalogue et étiquetée tarif « par personne » ou « forfait ». C'est le produit
commercial, distinct du programme pédagogique. Sur la ligne du devis, le
commercial choisit explicitement une version validée ou publiée correspondant
à cette formation. Une chaîne « formation — version » est enregistrée sur la
ligne au moment de la création ; elle figure sur le devis PDF, y compris si le
nom de la formation change ensuite. Le lien vers la version est conservé sur la
ligne de commande. La confirmation vérifie l'accord entre la version de la
demande, celle des lignes, et la devise du devis. Les contrôles sont côté serveur.

Les commerciaux disposent d'une lecture limitée des programmes validés,
publiés ou retirés de leurs sociétés autorisées ; les versions retirées restent
lisibles pour l'historique. Les brouillons et l'écriture du catalogue ne leur
sont pas ouverts. Le portail ne reçoit aucun droit de lecture du programme ;
le PDF utilise uniquement le libellé enregistré sur la ligne. Les droits
standards Odoo sur devis et contacts continuent à s'appliquer.

Les tarifs sont configurés dans les listes de prix Odoo : une liste MAD et une
liste EUR, avec pour chaque produit de formation une règle de prix fixe propre
au produit. Les montants sont indépendants ; aucune conversion depuis le prix
catalogue, une autre liste ou une règle générale n'est acceptée. L'effectif de
la demande fixe la quantité d'une ligne « par personne » ; une ligne « forfait »
porte une unité pour le groupe. Avant l'envoi du devis et la confirmation, le
serveur vérifie la devise, la règle réellement applicable (y compris ses dates
et seuils), la quantité, le prix unitaire et l'absence de remise manuelle.
La ligne et la liste Odoo conservent le montant et la devise du devis confirmé.
La devise d'une liste utilisée par une commande de formation confirmée est
figée, même si la liste est partagée entre sociétés.

Après confirmation, la facturation passe par l'assistant standard de Ventes.
Pour un service configuré « facturer les quantités commandées », il sait créer
une facture d'acompte en pourcentage ou en montant fixe, puis déduire cet
acompte de la facture finale. Le scénario fictif couvert par les tests prend
un forfait de 1 600 EUR : acompte de 25 % (400 EUR), puis facture finale de
1 200 EUR. Les deux factures gardent l'EUR et l'adresse de facturation Odoo.
Elles restent impayées après validation comptable, tant qu'aucun règlement
n'est enregistré. Un avis de virement interne peut être rattaché à la commande
et à sa facture : il ne crée aucun paiement et ne réduit pas le résiduel.
Seule la comptabilité peut annuler cet avis, qui reste alors visible comme
annulé. Le test enregistre ensuite un règlement comptable partiel de 300 EUR
sur la facture finale : son résiduel devient 900 EUR et son état « partiel ».
Pour une facture de formation et un journal bancaire, l'assistant demande une
référence bancaire distincte du libellé de facture. Il signale une référence
déjà comptabilisée dans la même société et le même journal, même si le montant
diffère ; une seconde affectation exige un motif conservé sur le paiement.
Décision du 20 octobre 2026 : le comptable vérifie manuellement l'encaissement
bancaire avant de créer le paiement Odoo. L'assistant exige une attestation
« Encaissement bancaire vérifié » ; le paiement direct portant une référence
de formation l'exige aussi avant comptabilisation. L'utilisateur qui valide
le paiement et l'horodatage sont conservés sur celui-ci, sans pouvoir être
modifiés ensuite par le formulaire. Cette attestation documente le contrôle
humain ; elle n'est pas une preuve bancaire indépendante. Décision du
20 octobre 2026 : pour un paiement de formation saisi dans Odoo, cette
attestation seule constitue la trace requise au lancement. Le module n'exige
pas de pièce bancaire jointe à ce paiement.
Un essai local avec le profil finance restreint a enregistré fictivement
10 EUR, attribué l'attestation à ce profil et réduit le solde de 850 à
840 EUR ; la transaction a ensuite été annulée et le solde conservé à
850 EUR.
Le 20 octobre 2026, le même contrôle a été rejoué dans l'interface de la base
locale `tm_s02_recette_fresh3` avec `s02_finance_local` sur la facture fictive
`INV/2026/00002` : l'assistant a refusé 10 EUR avec la référence
`FICTIONAL-UI-VERIFY-001` sans attestation, puis a créé le paiement
`PBNK2/2026/00005` après attestation. La fiche du paiement affiche le profil
finance et l'horodatage ; le résiduel de la facture est passé de 850 à 840 EUR.
Ce dernier paiement reste dans cette base jetable comme preuve de recette ;
les montants de 850 EUR décrits plus loin sont ceux du scénario avant cet essai.
Le contrôle provoque un conflit d’écriture entre les validations simultanées
d'un même journal ; une transaction utilisant un ancien instantané est annulée
puis reprise intégralement par le service Odoo avant un nouveau contrôle. La
référence est figée après comptabilisation. Décision du 20 octobre 2026 :
une devise de règlement différente de celle de la facture reste refusée au
lancement. Le refus s'applique à l'assistant, au paiement rapproché directement
et à la ligne de relevé bancaire affectée à cette facture.
Le même assistant refuse un journal de caisse ou une méthode autre que
« manuelle » pour ces factures. Un paiement direct portant la référence
spécifique de formation doit aussi être bancaire, entrant et manuel.
Lorsqu'un paiement saisi directement est rapproché d'une facture de formation,
le contrôle exige ces mêmes attributs, une référence bancaire et la devise de
la facture. Un paiement sans référence peut être comptabilisé, mais il ne peut
pas réduire le solde de cette facture par rapprochement direct.
Ce règlement comptabilisé ne constitue pas, à lui seul, une preuve bancaire.
Le test crée ses propres comptes et journaux fictifs ; il ne configure pas la
comptabilité d'une société réelle.

Le devis de formation n'appelle pas le paiement en ligne du portail Ventes,
même si la société a configuré un acompte par défaut ou si une URL contient un
montant. La création ou l'association d'une transaction de paiement à une
commande ou facture de formation est refusée côté serveur. Le virement reste
traité par l'avis interne et le règlement comptable contrôlé ci-dessus.
La facture de formation masque aussi l'action « Payer maintenant » du portail,
même si le paiement des factures est activé dans Odoo ; sa route de transaction
refuse un appel direct. Les autres factures Odoo conservent leur comportement.
Un test HTTP ouvre le devis sous un contact autorisé, avec un jeton valide et un montant dans l'URL :
aucun formulaire de paiement n'apparaît et l'appel direct à la route de
transaction est refusé. L'assistant de lien de paiement refuse les commandes
et factures de formation, y compris par création directe. Le lien et le QR
code de paiement en ligne sont retirés du rapport de facture même si l'option
de la société est activée.

La demande CRM et le devis portent trois contacts Odoo explicites : le
commanditaire, le payeur prévu et le contact administratif. Ils peuvent être
différents du client du devis ; une même personne peut aussi cumuler plusieurs
rôles si c'est la réalité du dossier. La conversion CRM transmet les trois
repères au devis. Ils ne changent ni `partner_id` (client du devis), ni
`partner_invoice_id` (adresse et débiteur repris sur la facture Odoo), ni les
droits d'accès. Leur rattachement à une société exploitante différente est
refusé. Les rôles sont figés sur une commande confirmée : une correction
contractuelle passe par une révision de l'offre. Le payeur indiqué ici ne vaut
pas constat de règlement. Les trois repères de contacts et la liste des avis
de virement sont réservés aux utilisateurs internes sur la commande. Un contact
de la même entreprise cliente ne lit le devis que s'il est nommé dans la liste
d'habilitation de ce devis.

## Limites de l'incrément

La version du prix fixe en vigueur au moment de l'envoi n'est pas encore
archivée séparément : une modification de règle avant confirmation exige de
revalider le devis et de réviser son montant. Aucune taxe, banque, règle de change ou
politique de facturation n'est présumée. Le rapprochement bancaire réel reste
à valider ; l'ouverture future des règlements dans une autre devise exigera
une procédure comptable distincte.
Les parcours portail vérifiés sont décrits ci-dessous ; les autres modèles de
notification restent à contrôler avant ouverture. Aucun accès pédagogique,
inscription, place ou session n'est créé par cet addon.
La saisie directe d'un paiement hors de l'assistant ne connaît pas encore sa
future facture de formation : elle n'exige donc pas cette référence lors de la
création. Son rapprochement avec cette facture est contrôlé. Le contrôle des
doublons agit également sur les paiements directs portant une référence.
Les constats ci-dessous sur les relevés sont historiques et techniques : leur
scénario navigateur est **reporté hors recette de lancement**, sur décision
explicite du 22 octobre 2026. Ils ne démontrent pas un parcours utilisateur livré.
Les lignes de relevé bancaire et les écritures manuelles sans objet paiement
relèvent du rapprochement natif. Sur la base fictive, une ligne bancaire de
50 EUR affectée directement au compte client a réduit le résiduel de la
facture de 850 à 800 EUR, même avec un libellé de transaction vide ; aucun
`account.payment` n'était créé. Les deux essais exploratoires ont été annulés
en transaction et le solde est resté à 850 EUR. Décision du 20 octobre 2026 :
une ligne de relevé sans référence peut être rapprochée après contrôle manuel
par la comptabilité. Le test automatisé rejoue ce rapprochement explicite.
Décision du 20 octobre 2026 : ce contrôle n'exige pas d'attestation enregistrée
dans Odoo. Le serveur ne peut donc pas démontrer que la revue humaine a eu
lieu : avant usage réel, la comptabilité doit vérifier qu'aucune règle de
rapprochement automatique ne valide ces lignes sans revue. Les imports
réels et leur traitement des doublons restent à recetter. Une ligne de relevé
de caisse ou tenue dans une autre devise que la facture est refusée au
rapprochement côté serveur.
Sur la base locale `tm_s02_recette_fresh3`, les seuls modèles de
rapprochement actifs consultés le 20 octobre 2026 sont « Internal Transfers »
et « Bank Fees », tous deux déclenchés manuellement. Ce constat local ne
valide pas la configuration de l'instance comptable cible ni son mode d'import.
La page générique `/payment/pay` ne porte pas l'identité d'un devis ou d'une
facture : un lien construit indépendamment avec un partenaire et un montant
ne peut pas être attribué avec certitude à une formation. L'absence de
prestataire de paiement actif devra être vérifiée lors du paramétrage du
lancement ; l'addon n'interrompt pas les paiements d'autres activités Odoo.
Sur décision du 20 octobre 2026, les devis et factures de formation ont une
liste distincte de contacts portail nommément autorisés, vide par défaut.
Le rattachement à la même entreprise ne suffit pas. Une copie de document ne
reprend pas ses habilitations. L'accès par URL exige une
session connectée correspondant à l'un de ces contacts, même avec le jeton
valide d'Odoo ; retirer un contact révoque son accès au portail. Les règles
serveur restreignent aussi la lecture ORM et les listes. Les contacts internes
du devis et les avis de virement restent invisibles au portail. Les autres
documents Odoo conservent leurs règles natives. Les PDF ou pièces déjà
transmis hors du portail ne peuvent pas être rappelés par cette révocation.
Sur une facture de formation en brouillon, un commercial autorisé à modifier
la facture peut choisir « Reprendre les contacts de la commande ». Cette action
explicite reprend uniquement les contacts communs à toutes les commandes de
formation liées ; elle refuse les factures mixtes ou sans contact commun.
La facture reste vide par défaut et ses habilitations restent indépendantes
après la reprise : toute révocation sur la commande doit être réexaminée sur
les factures déjà créées.
Les assistants d'envoi du devis et de la facture joignent le PDF uniquement
quand au moins un contact nommé sur le document possède une adresse e-mail.
Ils proposent ces contacts habilités à la place du client générique. La
préparation du courriel, y compris depuis le fil du document, refuse un autre
destinataire, une copie ou un envoi après révocation ; les abonnés du fil ne sont pas ajoutés à ces
notifications. Le PDF reçu par courriel reste en possession du destinataire
après une révocation. Utiliser des adresses individuelles pour les contacts
habilités : une boîte partagée ne permet pas d'en limiter la lecture.
Les notifications des autres messages du fil sont également filtrées côté
serveur : un abonné ou destinataire externe non habilité, ainsi qu'une adresse
libre sans contact nommé, ne reçoit pas de notification du devis ou de la
facture de formation. Les destinataires internes conservent le fonctionnement
Odoo habituel. Ce contrôle a été vérifié sur des messages fictifs, sans envoi.
La page portail d'une commande de formation n'affiche que les liens des
factures pour lesquelles le contact connecté possède une habilitation propre.
Elle remplace également le libellé des lignes d'acompte par un libellé
générique, y compris sur le PDF de commande, car le libellé standard contient
le numéro de la facture d'acompte.
Le PDF de facture finale masque également le numéro de la facture d'acompte
dans la ligne déduite ; la référence reste présente sur l'écriture interne.
Décision du 20 octobre 2026 : conserver ce libellé sans numéro sur le PDF
client. La comptabilité doit confirmer que cette présentation convient à la
facturation de la société exploitante avant usage réel.
Le service binaire vérifie aussi les pièces liées directement au devis, à la
facture ou à leurs messages, y compris lors d'un téléchargement groupé : le
jeton propre à une pièce ne suffit pas. L'accès aux fils de discussion des
devis et factures suit la même habilitation, même avec son propre jeton.
Les destinataires et PDF proposés ont été vérifiés dans les deux assistants
sur la base fictive locale. Deux messages ont ensuite été envoyés vers un
récepteur SMTP temporaire limité au conteneur local : un pour le devis, un
pour la facture, chacun adressé au seul contact habilité et muni d'un PDF.
Ce récepteur et sa configuration Odoo ont été retirés après le contrôle.
Les corps des modèles natifs prévisualisés ne contenaient pas de lien, mais
les courriels assemblés par Odoo ajoutent un lien `/mail/view`. Son accès HTTP
est vérifié avec anonyme, collègue non habilité, contact habilité et après
révocation, pour le devis et la facture. Les téléchargements HTTP de pièces
liées au document ou à un message sont contrôlés pour un contact habilité,
un collègue non habilité et après révocation ; l'aperçu PDF natif testé refuse
le jeton ordinaire de la
pièce, y compris pour le contact habilité. Les autres modèles de notification
et la configuration SMTP réelle restent à vérifier avant toute ouverture
externe.

Le modèle standard « Payment: Payment Receipt » joignait un PDF de paiement
et proposait initialement le client générique. Pour un paiement de formation,
le reçu prend désormais l'intersection des contacts nommément habilités sur
toutes les factures qu'il règle. S'il n'est pas encore affecté à une facture,
ou s'il règle aussi une facture non liée à une formation, aucun destinataire
externe n'est proposé. Un destinataire ou une copie ajoutés dans l'assistant
sont refusés côté serveur ; les notifications du fil et les pièces du paiement
suivent la même règle. L'API directe des modèles d'e-mail refuse également un
destinataire forcé sur un devis, une facture ou un reçu de formation. Sur la
base fictive, l'assistant du paiement `PBNK2/2026/00005` a proposé uniquement
le contact habilité et joint `Report.pdf` ; le brouillon a été fermé sans
envoi. Les tests natifs couvrent le refus du client générique, la révocation
et l'accès à une pièce du reçu.

## Recette sur données fictives et base isolée

1. Préparer un commercial limité à une société A ; créer dans A une formation
   et deux versions V1 validée, V2 brouillon. Vérifier que le commercial trouve
   V1 et ne lit pas V2, sans pouvoir modifier le catalogue.
2. Créer deux produits de service « personne » et « forfait » liés à la formation,
   deux listes de prix MAD/EUR, puis quatre règles fixes de montants fictifs
   différents. Dans CRM,
   qualifier une demande de groupe de 12 personnes, choisir V1 et EUR. La
   conversion native crée un devis portant les mêmes repères ; elle doit refuser
   une demande sans programme, effectif positif ou devise MAD/EUR.
   Renseigner séparément un commanditaire, un payeur prévu et un contact
   administratif fictifs ; vérifier leur reprise sans changement du client ni
   de l'adresse de facturation.
3. Ajouter une ligne du produit « personne », quantité 12 et version V1. Vérifier que le
   devis PDF indique la formation et V1. Modifier ensuite le nom de la formation :
   le libellé contractuel de la ligne et du PDF ne doit pas changer.
   Refaire la sélection de V1 dans le formulaire de ligne affiché sur écran
   étroit : elle doit être disponible aussi hors de la liste sur grand écran.
4. Tenter un envoi sans règle fixe propre au produit, avec quantité 1 pour le
   tarif « personne », un montant modifié ou une remise : refuser. Pour le
   forfait, accepter une quantité de 1 pour 12 participants. Vérifier le prix
   EUR indépendant du prix MAD et refuser la modification de devise d'une
   liste utilisée par une commande confirmée.
5. Tenter V2, une version d'une autre formation/société, puis une ligne de
   formation sans version : toutes doivent être refusées. Refuser aussi la
   confirmation en devise différente ou avec une version différente de celle
   de la demande. Un compte portail ne doit pas lire la fiche pédagogique.
6. Refuser un contact réservé à une autre société exploitante. Vérifier que le
   payeur prévu, sans lien avec le client, ne peut pas lire le devis par l'ORM
   portail. Créer deux contacts portail de la même entreprise cliente ; n'habiliter
   que le premier sur le devis. Sans connexion, puis connecté comme second
   contact, refuser page, PDF, pièce jointe et discussion, même avec les jetons
   valides. Le premier contact doit les ouvrir ; retirer son habilitation doit
   révoquer aussitôt son accès. Refaire le contrôle sur la facture :
   l'habilitation du devis ne lui donne pas celle de la facture. Vérifier que
   l'assistant du devis puis celui de la facture affichent seulement
   le contact habilité et le PDF joint. Ajouter un collègue non habilité en
   destinataire ou copie et vérifier le refus serveur ; révoquer l'habilitation
   puis vérifier le refus d'un brouillon déjà préparé. Contrôler les liens de
   téléchargement avant un envoi réel à un client.
7. Sur une base jetable avec comptes et journal fictifs, confirmer un forfait
   de 1 600 EUR facturable à la commande. Créer et valider une facture d'acompte
   de 25 %, puis une facture finale déduisant cet acompte. Vérifier 400 EUR et
   1 200 EUR, même débiteur, même devise et deux résiduels impayés. Ne pas
   confondre l'acompte facturé avec un règlement. Déclarer un avis de virement
   de 300 EUR : le résiduel reste 1 200 EUR et le portail ne lit pas l'avis.
   L'assistant Odoo doit refuser un journal de caisse, un paiement bancaire
   sans référence, sans attestation de vérification bancaire, ou dans une
   devise différente de celle de la facture. Enregistrer ensuite un
   paiement partiel de 300 EUR avec une référence fictive sur la facture
   finale : le résiduel passe à 900 EUR et l'état à « partiel » ; l'acompte
   demeure impayé. Tenter de réutiliser cette référence pour 100 EUR sur la
   facture d'acompte : l'assistant doit refuser sans motif, puis accepter un
   motif explicite de répartition, en ramenant son résiduel à 300 EUR. Le
   rapprochement direct d'un paiement bancaire sans référence avec la facture
   finale doit être refusé et laisser 900 EUR dus ; un paiement direct avec
   une nouvelle référence doit pouvoir être rapproché et ramener le solde à
   850 EUR. Ce solde clôt le scénario d'encaissement manuel du lancement ;
   le scénario supplémentaire des relevés bancaires est reporté ci-dessous.
   Ouvrir l'assistant « Envoyer le reçu par e-mail » du paiement rapproché :
   seul un contact habilité sur la facture doit être proposé, avec le PDF du
   reçu. Ajouter le client générique ou un collègue non habilité et vérifier
   le refus serveur ; après révocation, aucun reçu ne doit pouvoir partir.
   Le commercial ne peut pas annuler l'avis, la comptabilité le peut. Aucun de
   ces actes n'ouvre un accès pédagogique.
   Avec un acompte portail configuré, vérifier aussi que le devis de formation
   n'exige aucun paiement en ligne et qu'une transaction liée à la commande
   ou à sa facture est refusée, y compris par appel direct au modèle.
8. Vérifier sur base jetable l'installation depuis zéro, puis la mise à jour
   depuis S01 avec Website présent. Relever le comportement de la vue Website
   décrit dans la [PR #42](https://github.com/Progideo/training_management/pull/42),
   sans supposer que ce nouvel addon reproduit l'incident.

### Scénario reporté — relevés bancaires et imports

Décision explicite de l'utilisateur du **22 octobre 2026** : les encaissements
sont saisis manuellement au lancement, après vérification bancaire. Le scénario
des lignes de relevé est reporté à un incrément ultérieur, avec les imports ;
il ne conditionne plus l'acceptation de la recette S02 de lancement.

Restent **non validés par navigateur et non ouverts à l'exploitation** :

- affectation manuelle d'une ligne de relevé de 50 EUR sans référence,
  réduction du résiduel de 850 à 800 EUR et preuve de la revue comptable avant
  tout rapprochement automatique ;
- refus de rapprochement d'un relevé MAD avec une facture EUR et d'un relevé
  de caisse ;
- imports réels, formats, doublons/rejeux de fichiers, journaux, devises et
  règles de rapprochement.

La recette locale du 22 octobre a atteint, sous le profil comptable de base,
la liste native des relevés sans parcours complet de création/rapprochement
utilisable dans l'édition Community testée. Les essais ORM et tests serveur
antérieurs ne remplacent pas ce parcours navigateur. Ce constat reste conservé ;
le report ne transforme aucun scénario non exécuté en succès et ne retire aucun
contrôle serveur existant. Avant d'ouvrir cet incrément, cadrer un parcours
compatible avec le code exact Community, les droits et la procédure de revue
comptable, puis réaliser une recette dédiée.

## Feuille de recette métier à signer

Exécuter les étapes ci-dessus dans l'interface Odoo d'une base de test autorisée,
avec des comptes réellement limités (commercial, coordinateur, comptable,
contacts portail habilité et non habilité) et des données fictives distinctes
de la recette S01. Pour chaque étape, consigner dans la PR #43 la date, la version
du module, le compte/rôle utilisé, le résultat attendu et obtenu, ainsi que les
références fictives du devis et des factures. Capturer les refus et les montants
résiduels ; ne joindre ni données personnelles réelles ni secrets au dépôt public.

La recette S02 **de lancement manuel** n'est acceptée que si les étapes 1 à 8,
dans leur périmètre courant ci-dessus, passent, si aucun accès documentaire
n'est possible après révocation, et si les paramètres comptables de lancement
(fiscalité et journaux) sont décidés et documentés
par le responsable comptable, qui doit aussi accepter la règle choisie :
l'attestation Odoo seule pour les paiements saisis, ainsi que la présentation
du PDF final sans numéro d'acompte. Le refus multidevise
validé pour le lancement doit être vérifié sur les paiements saisis, y compris
leur affectation directe à une facture. Les relevés et imports font l'objet du
report explicite ci-dessus et ne sont pas un critère bloquant de cette recette
de lancement. La validation de la revue des lignes sans référence et des règles
de rapprochement sera exigée avant leur ouverture ultérieure. Les tests
automatiques et les vérifications HTTP existants ne remplacent pas cette
validation dans l'interface. La recette ne vaut ni fusion, ni installation sur
la base de développement existante, ni ouverture du portail aux clients.

Les tests natifs se trouvent dans `addons/training_management_sale/tests/` ;
le workflow `.github/workflows/odoo.yml` exécute aussi l'installation et la
mise à jour de cet addon sur ses bases CI jetables. Les résultats obtenus sont
consignés dans la PR. Les comptes et formations de recette S01 de
`neopro_dev` sont préservés ; les nouvelles données de scénario seront distinctes.

## Périmètre de lancement confirmé le 22 octobre 2026

La saisie des encaissements est **manuelle au lancement, après vérification
bancaire ; les lignes de relevé et l'import des fichiers bancaires sont reportés**.
Le report explicite du scénario de relevé remplace son ancien statut de réserve
bloquant l'acceptation globale de la recette navigateur. Il ne vaut pas validation
de ce scénario, ni autorisation de l'utiliser. S02 n'ajoute aucun importeur ni
contrôle des doublons de fichiers importés. Les contrôles du paiement manuel
restent inchangés : banque entrante et méthode manuelle, référence, attestation
avec auteur/horodatage serveur, motif de fractionnement d'une référence répétée,
refus multidevise, affectation contrôlée et habilitations documentaires.
Le futur circuit des relevés/imports nécessitera un cadrage distinct de ses
formats, doublons, journaux, devises, droits, interface Community et revue comptable.


## Contrôles serveur renforcés — 22 octobre 2026

La version `20.0.1.8.0` applique les exigences COM02, COM03 et SEC01 aux
entrées ORM et au traitement différé, en complément des assistants :

- Une écriture effective d’un compteur technique du journal remplace le verrou
  seul lors du contrôle des références. Sous `REPEATABLE READ`, PostgreSQL
  annule une transaction dont l’instantané précède une validation concurrente.
  Le service Odoo reprend toute la transaction ; un appel direct hors service
  doit gérer cette reprise complète. Aucun commit ni nouvelle connexion n’est
  introduit dans le code métier. Le motif de fractionnement reste nécessaire
  après reprise. Cette sérialisation par journal privilégie l’intégrité ; elle
  ne constitue pas un test de charge.
- Les créations et écritures d’état des paiements utilisent le même contrôle
  de référence et d’attestation que l’action native. L’auteur et l’heure sont
  exclusivement fixés par le serveur, y compris avec des valeurs par défaut
  de contexte. Un rapprochement de paiement saisi exige aussi ces métadonnées.
  Les paiements ordinaires et les relevés sans référence restent possibles.
- Les créations et transitions de devis vers `sent` ou `sale` contrôlent
  qualification, version et tarif. La devise effective et la devise de la liste
  doivent correspondre à la demande. Une commande de formation confirmée
  refuse la substitution directe de sa devise ; une révision reste nécessaire.
- Chaque préparation de transport `mail.mail`, y compris une reprise de file,
  revalide les destinataires externes des devis, factures et reçus protégés.
  Un contact révoqué fait passer le courriel en erreur avant le transport ;
  aucun destinataire de ce courriel ne reçoit alors son contenu. La comptabilité
  ou le commercial doit revoir les destinataires avant de relancer l’envoi.
  Les destinataires internes conservent les règles natives.
- Les lectures et recherches des messages ajoutent l’habilitation courante
  aux permissions natives d’auteur, de destinataire ou de notification. Cette
  restriction est recalculée, sans mémoriser une ancienne liste de contacts.
  Elle s’applique aussi aux raccourcis des contrôleurs et aux exports. Les
  reçus conservent l’intersection des contacts de toutes les factures réglées.
- L’avis de virement commercial utilise l’opérateur natif Odoo 20 `access` sur
  la commande : son portefeuille suit les droits courants de lecture de celle-ci.
  La facturation garde sa permission propre, avec la restriction par société.

La mise à jour ajoute uniquement un compteur technique de journal. Elle ne
réécrit aucun programme, devis, paiement ni historique antérieur. Elle ne
corrige pas automatiquement des données déjà incohérentes : leur éventuelle
régularisation exige une analyse et une autorisation distinctes. Aucun changement
S01, plan comptable national ou traitement d’import bancaire n’est ajouté.

### Vérification corrective reproductible

Sur bases jetables et données fictives, exécuter les suites natives S01/S02,
puis la sonde `addons/training_management_sale/tests/probes/bank_reference_concurrency.py`
dans `odoo shell`. Elle exige un nom de base préfixé `tm_s01_test_` ou
`tm_s02_test_`, persiste volontairement ses seules fixtures fictives, ouvre deux
transactions `REPEATABLE READ` sous facturation restreinte et relit les commits
avec une troisième connexion. Elle vérifie le conflit, le refus après reprise
et l’acceptation du fractionnement motivé. Le workflow Odoo exécute cette sonde
en plus de l’installation vierge, la mise à jour et la variante Website/eLearning.
Les journaux et résultats de la CI sont attachés à chaque exécution GitHub.

Les tests d’addon couvrent les écritures directes sous profils restreints,
les refus d’audit fourni par l’appelant, la lecture RPC d’un message modifié
après révocation, le transport de devis et les refus d’envoi de facture/reçu,
ainsi que lecture, recherche et export d’un avis hors portefeuille. Les connexions
et transports SMTP sont interceptés dans ces tests ; aucun envoi externe n’est
nécessaire. Ces tests ne remplacent pas la recette métier dans l’interface.

Recette courte : confirmer un devis fictif au tarif fixe ; refuser sa devise
modifiée et une confirmation directe à prix altéré ; poster un paiement vérifié,
refuser son doublon sans motif par action et écriture d’état ; préparer un PDF,
révoquer son contact et contrôler l’échec en file et la lecture du message ;
refuser enfin l’avis à un autre commercial limité, tout en le conservant pour
son propriétaire et la facturation.
