# S02 — Demande CRM, devis et facturation native

Incréments demande/devis, tarifs et rôles commerciaux de [#12](https://github.com/Progideo/training_management/issues/12),
à relire avec la [matrice de couverture](s02-native-coverage.md).
Ce document décrit le code de la PR en brouillon ; l'installation en développement
et l'ouverture aux clients restent des étapes séparées.

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
Le contrôle sérialise les validations simultanées d'un même journal. La
référence est figée après comptabilisation. Une devise de règlement différente
de celle de la facture est refusée dans cet assistant en attendant la règle
de rapprochement validée par la comptabilité.
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
politique de facturation n'est présumée. Le rapprochement bancaire réel,
la procédure comptable pour un règlement d'une autre devise et la recette navigateur
des pièces, échanges et notifications du portail restent à valider. Aucun accès pédagogique,
inscription, place ou session n'est créé par cet addon.
La saisie directe d'un paiement hors de l'assistant ne connaît pas encore sa
future facture de formation : elle n'exige donc pas cette référence lors de la
création. Son rapprochement avec cette facture est contrôlé. Le contrôle des
doublons agit également sur les paiements directs portant une référence.
Les lignes de relevé bancaire et les écritures manuelles sans objet paiement
relèvent du rapprochement natif ; leurs preuves et les imports bancaires
restent à cadrer avant une recette opérationnelle complète.
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
La page portail d'une commande de formation n'affiche que les liens des
factures pour lesquelles le contact connecté possède une habilitation propre.
Elle remplace également le libellé des lignes d'acompte par un libellé
générique, y compris sur le PDF de commande, car le libellé standard contient
le numéro de la facture d'acompte.
Le service binaire vérifie aussi les pièces liées directement au devis, à la
facture ou à leurs messages, y compris lors d'un téléchargement groupé : le
jeton propre à une pièce ne suffit pas. L'accès aux fils de discussion des
devis et factures suit la même habilitation, même avec son propre jeton.
Une recette complète des notifications et des autres chemins de téléchargement reste nécessaire
avant toute ouverture externe.

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
   l'habilitation du devis ne lui donne pas celle de la facture. Vérifier les
   notifications sortantes et tout lien de téléchargement qu'elles contiennent
   avant un envoi réel à un client.
7. Sur une base jetable avec comptes et journal fictifs, confirmer un forfait
   de 1 600 EUR facturable à la commande. Créer et valider une facture d'acompte
   de 25 %, puis une facture finale déduisant cet acompte. Vérifier 400 EUR et
   1 200 EUR, même débiteur, même devise et deux résiduels impayés. Ne pas
   confondre l'acompte facturé avec un règlement. Déclarer un avis de virement
   de 300 EUR : le résiduel reste 1 200 EUR et le portail ne lit pas l'avis.
   L'assistant Odoo doit refuser un journal de caisse, un paiement bancaire
   sans référence et une devise différente de celle de la facture. Enregistrer ensuite un
   paiement partiel de 300 EUR avec une référence fictive sur la facture
   finale : le résiduel passe à 900 EUR et l'état à « partiel » ; l'acompte
   demeure impayé. Tenter de réutiliser cette référence pour 100 EUR sur la
   facture d'acompte : l'assistant doit refuser sans motif, puis accepter un
   motif explicite de répartition, en ramenant son résiduel à 300 EUR. Le
   rapprochement direct d'un paiement bancaire sans référence avec la facture
   finale doit être refusé et laisser 900 EUR dus ; un paiement direct avec
   une nouvelle référence doit pouvoir être rapproché et ramener le solde à
   850 EUR. Le commercial ne peut pas annuler l'avis, la comptabilité le peut. Aucun de
   ces actes n'ouvre un accès pédagogique.
   Avec un acompte portail configuré, vérifier aussi que le devis de formation
   n'exige aucun paiement en ligne et qu'une transaction liée à la commande
   ou à sa facture est refusée, y compris par appel direct au modèle.
8. Vérifier sur base jetable l'installation depuis zéro, puis la mise à jour
   depuis S01 avec Website présent. Relever le comportement de la vue Website
   décrit dans la [PR #42](https://github.com/Progideo/training_management/pull/42),
   sans supposer que ce nouvel addon reproduit l'incident.

## Feuille de recette métier à signer

Exécuter les étapes ci-dessus dans l'interface Odoo d'une base de test autorisée,
avec des comptes réellement limités (commercial, coordinateur, comptable,
contacts portail habilité et non habilité) et des données fictives distinctes
de la recette S01. Pour chaque étape, consigner dans la PR #43 la date, la version
du module, le compte/rôle utilisé, le résultat attendu et obtenu, ainsi que les
références fictives du devis et des factures. Capturer les refus et les montants
résiduels ; ne joindre ni données personnelles réelles ni secrets au dépôt public.

La recette S02 n'est acceptée que si les étapes 1 à 8 passent, si aucun accès
documentaire n'est possible après révocation, et si les écarts comptables
ouverts (fiscalité, journaux, preuve du virement, autre devise et rapprochement
des relevés) sont décidés et documentés par le responsable comptable. Les tests
automatiques et les vérifications HTTP existants ne remplacent pas cette
validation dans l'interface. La recette ne vaut ni fusion, ni installation sur
la base de développement existante, ni ouverture du portail aux clients.

Les tests natifs se trouvent dans `addons/training_management_sale/tests/` ;
le workflow `.github/workflows/odoo.yml` exécute aussi l'installation et la
mise à jour de cet addon sur ses bases CI jetables. Les résultats obtenus sont
consignés dans la PR. Les comptes et formations de recette S01 de
`neopro_dev` sont préservés ; les nouvelles données de scénario seront distinctes.
