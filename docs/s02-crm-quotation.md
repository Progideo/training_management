# S02 — Demande CRM et devis lié au programme

Incréments demande/devis et tarifs de [#12](https://github.com/Progideo/training_management/issues/12),
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

## Limites de l'incrément

La version du prix fixe en vigueur au moment de l'envoi n'est pas encore
archivée séparément : une modification de règle avant confirmation exige de
revalider le devis et de réviser son montant. Aucune taxe, banque, règle de change ou
politique de facturation n'est présumée. Le circuit facture/virement, les rôles
commanditaire/payeur/contact administratif et les habilitations documentaires
du portail attendent les incréments suivants de S02. Aucun accès pédagogique,
inscription, place ou session n'est créé par cet addon.

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
3. Ajouter une ligne du produit « personne », quantité 12 et version V1. Vérifier que le
   devis PDF indique la formation et V1. Modifier ensuite le nom de la formation :
   le libellé contractuel de la ligne et du PDF ne doit pas changer.
4. Tenter un envoi sans règle fixe propre au produit, avec quantité 1 pour le
   tarif « personne », un montant modifié ou une remise : refuser. Pour le
   forfait, accepter une quantité de 1 pour 12 participants. Vérifier le prix
   EUR indépendant du prix MAD et refuser la modification de devise d'une
   liste utilisée par une commande confirmée.
5. Tenter V2, une version d'une autre formation/société, puis une ligne de
   formation sans version : toutes doivent être refusées. Refuser aussi la
   confirmation en devise différente ou avec une version différente de celle
   de la demande. Un compte portail ne doit pas lire la fiche pédagogique.
6. Vérifier sur base jetable l'installation depuis zéro, puis la mise à jour
   depuis S01 avec Website présent. Relever le comportement de la vue Website
   décrit dans la [PR #42](https://github.com/Progideo/training_management/pull/42),
   sans supposer que ce nouvel addon reproduit l'incident.

Les tests natifs se trouvent dans `addons/training_management_sale/tests/` ;
le workflow `.github/workflows/odoo.yml` exécute aussi l'installation de cet
addon sur sa base CI jetable. Les résultats réellement obtenus seront consignés
dans la PR après exécution. Les comptes et formations de recette S01 de
`neopro_dev` sont préservés ; les nouvelles données de scénario seront distinctes.
