# C06 — Paramétrage commercial au déploiement

Référence : [C06 #10](https://github.com/Progideo/training_management/issues/10).
La reprise M01 et le paramétrage de facturation sont deux étapes de la livraison.
La fiche société ne suffit pas à valider son pays fiscal ni son plan comptable.

## Socle natif

Odoo Community `20.0-20261015` fournit `l10n_ma`, dépendant de `account`.
Sur cette version exacte, le module contient le plan marocain, les taxes et
les positions fiscales. Son installation et le chargement du plan sont à vérifier
explicitement : une base précédemment initialisée avec un plan générique peut
conserver celui-ci après changement du pays de la société.

Le profil privé de déploiement reprend les décisions validées : pays et devise
de la société, module et modèle de localisation, taxe de vente applicable,
liste de prix par défaut et conditions de paiement. L’exemple public
[launch-settings.example.json](../deployment/launch-settings.example.json)
est fictif. Le profil réel reste hors Git ; aucun identifiant fiscal, compte
bancaire, client ou secret n’est nécessaire dans ce fichier de paramétrage.

## Application

1. Sauvegarder la base et le filestore ; vérifier la société cible et le pays
   de sa fiche. Pour la préparation, utiliser une copie isolée sans envoi de
   courriel ni tâche automatique.
2. Installer le module de localisation du profil avec le même binaire Odoo
   que l’application, sans données de démonstration, pendant une maintenance
   de l’application concernée. Pour le profil marocain avec règle export :
   `-i l10n_ma,sale_invoice_address_fiscal`. Livrer aussi cet addon.
3. Depuis `odoo shell`, charger le profil privé, puis exécuter
   [launch_settings.py](../deployment/launch_settings.py) et appeler
   `apply(env, profile)`. Examiner le résultat avant `env.cr.commit()` ; faire
   `env.cr.rollback()` en cas d’échec. La fonction ne valide jamais une facture.
4. Relancer `apply` et comparer les identifiants et le résultat. Les mêmes
   listes et valeurs par défaut doivent être réutilisées sans création de
   doublon. Vérifier aussi la conservation des données et des archives M01.
5. Redémarrer l’application et effectuer la recette commerciale ci-dessous.

L’initialisation d’un autre plan est refusée en présence d’écritures comptables,
de journaux bancaires renseignés ou de commandes confirmées. Une liste de prix
initiale vide n’est réutilisée qu’avant confirmation ; les prix fixes existants
ne sont pas convertis silencieusement. Les valeurs explicitement renseignées
sur les clients et les devis ouverts restent à contrôler : les nouveaux défauts
ne doivent pas écraser leurs choix.

## TVA suivant l’adresse de facturation

Le standard de cette version choisit la position fiscale selon la livraison.
L’addon optionnel `sale_invoice_address_fiscal` permet d’activer, société par
société, une politique commerciale suivant le pays de facturation : pays fiscal
local → position domestique native ; autre pays renseigné → position export
configurée ; pays absent → position domestique, jamais une exonération implicite.
Cette règle concerne les ventes, y compris les factures directes et avoirs ; les
achats et sociétés sans activation conservent leur sélection native.

Le profil `export_sales` crée une position dédiée et une taxe de vente à 0 % qui
remplace la taxe de services du profil. Il ajoute la mention validée aux rapports
natifs, sans imposer d’identifiant TVA. Aucun pays étranger n’est codé en dur.
La taxe reste distincte des catégories légales des déclarations : leurs rubriques
et droits à déduction ne sont pas qualifiés par ce réglage commercial.

Les champs restent modifiables selon les droits natifs. Au changement d’adresse
de facturation, la position est recalculée ; les taxes des lignes suivent la
position fiscale. Une dérogation manuelle reste une action de l’utilisateur.
L’activation ne réécrit pas les documents existants : recalculer seulement les
devis brouillons explicitement retenus pour la recette. Les rapports historiques
M01 restent des archives.

## Devises du parcours commercial

Décision de périmètre NeoPro : adresse de facturation au Maroc → MAD ; à
l’étranger → EUR. Les anciens scénarios Maroc/EUR et étranger/MAD sont écartés.
Le profil renseigne `domestic_sales_currencies: ["MAD"]` et
`foreign_sales_currencies: ["EUR"]`, après mise à jour de
`sale_invoice_address_fiscal`. Les listes sont configurées par société ; une liste
vide conserve les choix natifs pour la zone concernée. Aucun pays ni code devise
n’est codé en dur dans l’addon générique.

Les devis, factures de vente et avoirs hors de la liste autorisée sont refusés
côté serveur à la création/modification, puis à la confirmation du devis ou à la
comptabilisation de la facture. Ce second contrôle couvre aussi un pays modifié
sur le contact après l’enregistrement. Le pays de facturation détermine la zone ;
la livraison ne change pas la règle. Le message indique la devise attendue.
Les achats et les sociétés sans restriction configurée conservent leurs choix.
Un pays absent ne déclenche pas la règle de zone et ne qualifie pas l’exonération.

Le profil active MAD et EUR pour les usages autorisés. Au déploiement, rejouer le
profil et vérifier Maroc/MAD et étranger/EUR, puis le refus de Maroc/EUR et
étranger/MAD : devis, facture directe, avoir, changements d’adresse ou de devise.
Les anciens documents de recette restent conservés ; une combinaison désormais
interdite ne pourra plus être confirmée ou comptabilisée. Aucun montant ni prix
n’est converti automatiquement. Exclure les documents fictifs de la production.

## Coordonnées de virement sur les PDF

Utiliser le pied de page natif de la société, commun aux devis et factures :
Paramètres → mise en page des documents → pied de page. Conserver les mentions
existantes et ajouter le bénéficiaire, la banque, le RIB/IBAN et le BIC/SWIFT utiles,
repris et rapprochés des coordonnées de référence Odoo 19. Si les instructions
MAD et EUR diffèrent, identifier clairement chaque compte. Aucune valeur bancaire
réelle ne doit entrer dans ce dépôt public.

Ce pied de page permet aussi l’affichage sur facture brouillon : le bloc bancaire
natif du corps de facture dépend notamment de la référence de paiement et ne
suffit pas à notre contrôle. Le pied de page ne crée pas de compte bancaire ni de
mode de paiement ; leur rattachement natif reste à vérifier séparément. Il ne
nécessite aucune autorisation de prélèvement ou d’émission de virement.

Au déploiement de production autorisé, renseigner le même pied de page validé
sur la société cible, puis contrôler les PDF devis et facture en MAD et EUR :
coordonnées exactes, complètes et lisibles, sans coupure. Conserver Odoo 19 comme
référence des coordonnées jusqu’à leur validation. Cette étape fait partie du
déploiement ; elle n’est pas exécutée par `launch_settings.py`.

## Accès et réservations

Le socle propose une durée en mois calendaires depuis l’ouverture explicite,
en complément des jours et périodes fixes existants. Le dernier jour du mois
est retenu si le quantième n’existe pas à l’échéance. Les prolongations et
révocations gardent leurs actions motivées et leurs droits ; aucun historique
ni accès expiré/révoqué n’est effacé ou rouvert par le paramétrage.

La durée de réservation de la réalisation fournit une échéance relative si
aucune date ni échéance de lot n’est renseignée. Zéro conserve le fonctionnement
manuel. Une échéance explicite reste prioritaire. L’assistant propose la date ;
la modifier sur une réservation encore active exige un motif et conserve
avant/après. Les lots gardent leur action dédiée de prolongation.
À expiration, la place est immédiatement libre pour le calcul de capacité,
même avant le traitement planifié qui met à jour l’état affiché.

Depuis le même fichier `launch_settings.py`, appeler `apply_pedagogical(env, profile)`
avec le profil privé suivant, puis vérifier avant de valider la transaction :

```json
{
  "database": "fictional_pedagogical_test",
  "company_xmlid": "base.main_company",
  "expected_company_name": "Fictional Training Company",
  "access_months": 12,
  "reservation_days": 7
}
```

Les défauts natifs sont limités à la société cible et aux nouvelles réalisations.
Le rejeu réutilise les mêmes défauts ; les périodes, réservations, historiques
et réalisations déjà enregistrés ne sont pas recalculés. L’expiration des accès
ne supprime pas les données. Les annulations, reports et remplacements restent
manuels et motivés ; aucun avoir ou remboursement automatique n’est créé.
Le devis accepté porte les éventuels frais. La liste d’attente conserve son ordre
d’arrivée ; la proposition et la confirmation restent manuelles.

Recette reproductible : `python3 tests/ci/run_pedagogical_policy.py`.
Contrôler 12 mois depuis l’activation, année bissextile, prolongation/révocation,
7 jours modifiables, expiration/capacité, attente, droits, reports/remplacements
et absence de mouvement financier automatique. La dev garde ses tâches et
courriels neutralisés ; ne pas activer le cron global pour ces essais.

## Recette et passage en production

- Nouveau client fictif marocain, service fictif à 1 000 MAD HT : vérifier
  liste MAD, TVA de services à 20 %, total 1 200 MAD et paiement à 30 jours.
- Vérifier devis PDF puis facture brouillon et échéance. Les vérifications
  techniques sur copie ne remplacent pas le contrôle utilisateur.
- Contrôler le scénario export à 0 % suivant l’adresse de facturation, sans
  numéro de TVA exigé : 100 EUR HT = 100 EUR TTC et mention
  « Exonération de TVA – Exportation de services » sur devis et facture.
  Tester aussi facturation France/livraison Maroc et l’inverse.
- Les prix EUR et les coordonnées de virement font également partie de C06.
  Ne pas interpréter un taux de change d’initialisation comme un tarif validé.
- Rejouer ce paramétrage sur la cible de production lors du déploiement autorisé,
  puis refaire les contrôles. Exclure les clients, produits et devis fictifs de
  recette : livrer les réglages ne signifie pas recopier la base de dev.
- Reprendre les compteurs commerciaux à la bascule selon le gel Odoo 19 ; ce
  script ne règle ni les séquences ni les compteurs et ne déclenche aucune bascule.

Odoo 19 reste la référence jusqu’à validation et autorisation de bascule.
Aucune écriture historique active ne doit être créée par ce paramétrage.

Contrôle automatisé reproductible : `python3 tests/ci/run_launch_settings.py`.
La CI exécute ce scénario natif avec des données fictives, puis son rejeu dans
une nouvelle session. Les essais de devis et facture sont annulés par retour de
transaction ; les réglages restent disponibles pour le second passage.


## Notifications de formation

La société configure une adresse commune d’expédition et de réponse, le
responsable interne et, si nécessaire, sa boîte d’alerte distincte de son compte.
Ces champs administrateur n’activent aucun transport ni tâche automatique.
Appliquer `apply_notifications(env, profile)` depuis
[launch_settings.py](../deployment/launch_settings.py), avec un profil privé
fondé sur [l’exemple fictif](../deployment/notification-settings.example.json).
Vérifier la cible et rejouer avant validation de la transaction.

Les notifications d’accès suivent les opérations réellement enregistrées, sans
rouvrir les accès. Les convocations restent une action explicite. Les alertes
formateur suivent les déclarations à contrôler ; celles du responsable couvrent
les demandes CRM, réclamations/améliorations autorisées, anomalies de présence
et échecs de distribution non privés. Une question pédagogique privée reste
adressée à son tuteur, sans alerte au responsable sur son contenu.

Les journaux empêchent les doublons et revérifient les destinataires avant
transport. Les messages ne contiennent ni résultat individuel ni support privé.
Un changement d’affectation, de droit ou d’adresse peut bloquer une ancienne
file : la revoir, sans réécrire ni réexpédier les historiques. Le journal des
alertes est limité à son destinataire habilité. Les envois et automatismes restent
neutralisés sur dev ; authentification et délivrabilité se vérifient séparément
avant production.

Recette : `python3 tests/ci/run_notification_policy.py` ; contrôler aussi sur la
cible les adresses, liens, droits, absence de doublon et absence d’envoi réel.
