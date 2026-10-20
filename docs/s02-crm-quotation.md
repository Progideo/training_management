# S02 — Demande CRM et devis lié au programme

Premier incrément de [#12](https://github.com/Progideo/training_management/issues/12),
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

## Limites de l'incrément

Les listes de prix fixes indépendantes MAD/EUR, la preuve du tarif retenu et
ses contrôles sont encore à livrer ; le champ « base tarifaire » ne calcule pas
le prix. La règle actuelle bloque une confirmation en devise différente de la
demande mais ne certifie pas le montant. Aucune taxe, banque, règle de change ou
politique de facturation n'est présumée. Le circuit facture/virement, les rôles
commanditaire/payeur/contact administratif et les habilitations documentaires
du portail attendent les incréments suivants de S02. Aucun accès pédagogique,
inscription, place ou session n'est créé par cet addon.

## Recette sur données fictives et base isolée

1. Préparer un commercial limité à une société A ; créer dans A une formation
   et deux versions V1 validée, V2 brouillon. Vérifier que le commercial trouve
   V1 et ne lit pas V2, sans pouvoir modifier le catalogue.
2. Créer un produit de service « personne » lié à la formation. Dans CRM,
   qualifier une demande de groupe de 12 personnes, choisir V1 et EUR. La
   conversion native crée un devis portant les mêmes repères ; elle doit refuser
   une demande sans programme, effectif positif ou devise MAD/EUR.
3. Ajouter une ligne du produit, quantité 12 et version V1. Vérifier que le
   devis PDF indique la formation et V1. Modifier ensuite le nom de la formation :
   le libellé contractuel de la ligne et du PDF ne doit pas changer.
4. Tenter V2, une version d'une autre formation/société, puis une ligne de
   formation sans version : toutes doivent être refusées. Refuser aussi la
   confirmation en devise différente ou avec une version différente de celle
   de la demande. Un compte portail ne doit pas lire la fiche pédagogique.
5. Vérifier sur base jetable l'installation depuis zéro, puis la mise à jour
   depuis S01 avec Website présent. Relever le comportement de la vue Website
   décrit dans la [PR #42](https://github.com/Progideo/training_management/pull/42),
   sans supposer que ce nouvel addon reproduit l'incident.

Les tests natifs se trouvent dans `addons/training_management_sale/tests/` ;
le workflow `.github/workflows/odoo.yml` exécute aussi l'installation de cet
addon sur sa base CI jetable. Les résultats réellement obtenus seront consignés
dans la PR après exécution. Les comptes et formations de recette S01 de
`neopro_dev` sont préservés ; les nouvelles données de scénario seront distinctes.
