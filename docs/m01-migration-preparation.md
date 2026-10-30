# M01 — Préparation de la reprise Odoo 19

Référence : [#22](https://github.com/Progideo/training_management/issues/22),
MIG01–MIG03 et chapitre 24. Cet incrément prépare la reprise ; il ne migre pas
une base Odoo 19. L’inventaire ciblé en lecture seule et les correspondances
validées dans #22 orientent cette version ; le relevé détaillé reste privé.
L’audit historique général reste suspendu. Les migrations de versions de l’addon dans la CI
ne prouvent pas une reprise depuis Odoo 19.

## Contrat et correspondances

`migration/example/bundle.json` est un exemple entièrement fictif, pas un
connecteur Odoo 19. Pour chaque lot : modèle source constaté, cible, méthode,
responsable, nombre attendu et lignes identifiées par leur identifiant source.
`source.system` distingue durablement les instances ; ne jamais le renommer
entre deux essais du même lot. `snapshot` identifie l’extraction conservée.
Une méthode inconnue reste `unknown` et produit un écart bloquant.

| Lot | Cible préparée / contrôle |
| --- | --- |
| Contacts | Import natif `res.partner`, identifiants externes stables ; personne/entreprise, pays et parent explicites. Aucun rapprochement automatique par nom ou e-mail. |
| Offres et sessions | Programmes et réalisations : correspondances et liens déclarés, saisie contrôlée ; aucun ancien code installé. |
| Inscriptions | Participant et réalisation retrouvés avant toute ouverture. Un actif orphelin bloque le lot. Aucune ouverture d’accès automatique. |
| Soldes | Décimaux exacts, rapprochement séparé par devise, sans restriction MAD/EUR ni arrondi implicite (#102) ; aucune écriture comptable historique recréée. Disponibilité, conversion et arrondi de la cible à vérifier dans Odoo. |
| Supports et pièces | Chemins relatifs, fichiers locaux réguliers, empreintes SHA-256, responsable des accès et conservation déclarés. Le contrôle d’empreinte ne prouve pas la lisibilité d’un PDF. |
| Résultats | Version historique identifiée ; inconnue signalée. Pas de tentative, score, thème ou certificat inventé. |
| Archive | Index source/fichiers, responsable, accès et conservation à valider. Préservation des originaux ; pas de nouvelle preuve générée à leur place. |

Les méthodes `manual` et `archive` documentent une destination à traiter :
elles n’exécutent aucun import. L’outil vérifie la cohérence du paquet déclaré,
pas sa fidélité à une base source non inspectée. Seuls les contacts ont un
format d’import natif démontré dans cet incrément, vers `res.partner` uniquement.
Le rapprochement CSV est réservé à cette méthode, pas aux lots manuels.

### Correspondances validées : contrat 2

`migration/example/qualified-bundle.json` illustre toutes les politiques avec
**des champs et données fictifs**. Le contrat 1 reste accepté sans changement ;
il ne peut pas contenir les nouvelles déclarations et ne revendique pas leur
validation. Le contrat 2 ajoute :

- `field_inventory` : `expected_count` et `fields`, liste exhaustive des couples
  `[modèle_source, champ_source]` de l’extraction. Comparer cette liste au relevé
  privé des 44 correspondances approuvées ; l’exemple ne remplace pas ce relevé.
- `field_mappings` : exactement une décision par couple, avec `source`, `policy`,
  `records` (couples lot/identifiant uniques), `expected_record_count` (leur nombre),
  `archive` (couples archive/identifiant) et
  `qualification` lorsque le sens ou l’affectation exige un contrôle métier.
  Les références doivent exister. Chaque champ persistant doit renvoyer à des
  originaux locaux vérifiés ; ces archives doivent effectivement couvrir ses
  valeurs, relations et provenance. L’outil vérifie liens et empreintes, pas leur
  exhaustivité sémantique. Les assistants transitoires n’ont aucune ligne à importer.

Un champ inutilisé peut déclarer zéro ligne : `records: []`,
`expected_record_count: 0`, justification de cette absence et archive des
métadonnées/preuves de contrôle. Ne pas inventer de question ou de ligne cible
pour satisfaire le plan. Un inventaire réellement vide déclare zéro champ et
zéro correspondance. La fidélité de ces constats à la source reste à contrôler.

Les décisions absentes, en double, hors inventaire, sans qualification requise
ou sans originaux bloquent tout CSV. La qualification est une déclaration humaine,
pas une déduction depuis le nom du champ. Aucun chemin cible libre n’est accepté :
les politiques autorisées sont définies dans `migration/mapping.py`.

| Politiques | Préparation autorisée, contrôles à effectuer sur copie |
| --- | --- |
| `catalogue`, `delivery`, `programme_template` | Cours, programme versionné et réalisation TM ; identités et liens source conservés, aucune fusion par nom ni version historique inventée. Produit commercial natif si nécessaire. |
| `instructors`, `partner_projection` | Contacts professionnels et missions/séances existantes ; rapprocher les projections utilisateur avec leur contact, sans importer RH, paie ou comptes. |
| `description`, `duration`, `commercial_reference` | Description HTML native à assainir ; durée annoncée dans le programme, jamais dans `total_time` calculé ; code commercial unique/société confirmé, jamais utilisé comme version historique. |
| `category`, `inverse_relation` | Catégorie TM et tags natifs après arbitrage des classements multiples ; reconstruire les inverses depuis les liens, pas de second champ miroir. |
| `publication` | Politique manuelle fermée : cours non publié, visibilité restreinte, inscription contrôlée ; aucun ancien drapeau n’accorde de droits. Vérifier le comportement des choix natifs dans la copie avant ouverture. |
| `exam`, `survey_purpose`, `survey_context`, `answer_image` | Surveys et fonctions S06/S09 existantes ; finalité réelle examen/évaluation nominative/satisfaction anonyme. Types natifs selon finalité, jamais recopie des anciennes sélections. Image vers `survey.question.answer.value_image` uniquement si conversion qualifiée d’une vraie question ; original conservé. |
| `historical_result`, `historical_presence`, `legacy_state` | Archive des résultats, preuves et drapeaux ; aucune tentative, anonymisation rétroactive, signature ou confirmation reconstituée. Une version inconnue va en archive avec sa réserve, jamais comme résultat opérationnel inventé. |
| `ice`, `fiscal_identifier` | ICE JSON natif uniquement ; autre identifiant vers `vat` après qualification de sa nature, du pays et du format, pas par copie globale. |
| `analytic_identity` | Rapprocher plans et comptes natifs par identité métier et société ; laisser Odoo générer les colonnes, sans recopier un suffixe local. |
| `amount_words` | Archiver les anciens documents ; montant en lettres natif pour les nouveaux documents uniquement. Aucun mouvement validé ni PDF historique réécrit. |
| `optional_project`, `transient` | Réserve sur le projet facultatif, aucune dépendance installée ; assistants exclus de la reprise. |
| `fiscal_period`, `unqualified` | Réserve et originaux restreints : les paramètres annuels ne remplacent pas toutes les périodes ; pas de clé JSON fiscale inventée ni de sens supposé pour un champ RH inconnu. Lot comptable/RH distinct à qualifier si nécessaire. |

La sortie privée `mapping-plan.json` rend ces décisions vérifiables avec leurs
cibles imposées, références et actions. Elle n’est **jamais un fichier d’import**.
Les lots hors contacts restent manuels/archives ; ils ne deviennent pas des
transformations automatiques. Les réserves sont comptées dans le rapport,
`field_mapping_validation` reste `not_executed` et chaque ligne du plan porte
`execution_authorized: false`. La validation des correspondances ne lève pas les
réserves portant sur des données dont le sens reste inconnu.

### ICE natif

Le contrat 2 accepte `values.additional_identifiers: {"MA_ICE": "…"}` pour les
contacts explicitement couverts par une politique `ice`, avec `country_xmlid:
base.ma`. La colonne CSV `additional_identifiers` contient un objet JSON.
Seule cette clé native démontrée est autorisée : aucune clé arbitraire pour RC,
CNSS, ITP ou capital. Une valeur non canonique de quinze chiffres ASCII bloque ;
le validateur officiel Odoo contrôle ensuite le numéro et sa clé de contrôle.
Le préparateur hors ligne ne prouve pas sa validité fiscale ni son attribution.
La valeur de test `000000000000097` est synthétique, sans valeur fiscale.

L’ICE parent/contact doit être identique avant préparation : le standard le
synchronise. Ne pas ajouter de faux `vat` pour faire apparaître une société.
L’import JSON remplace le dictionnaire : avant un rejeu sur des contacts déjà
enrichis, exporter la sélection et arrêter l’opération si des identifiants cible
supplémentaires seraient effacés ; arbitrer leur conservation hors de ce format
limité. Le rapprochement compare l’objet JSON sémantiquement (y compris les clés
supplémentaires), refuse les clés dupliquées et accepte la cellule vide native
comme objet vide. Une cellule absente dans une ligne tronquée reste inconnue :
elle ne vaut pas un objet vide. Les lignes avec cellules manquantes ou
supplémentaires bloquent le rapprochement et toute sortie CSV/plan. Les autres
colonnes gardent leur comparaison exacte.

Dans cette version exacte d’Odoo 20, `is_company` est calculé : entité commerciale
racine avec identifiant fiscal renseigné. Le booléen source est contrôlé mais
n’est pas envoyé comme champ modifiable. Une entreprise source sans identifiant
fiscal, ou une personne racine que le standard classerait comme entreprise,
produit `native_company_type_unresolved` ; ne pas inventer un numéro pour lever
cet écart. Odoo synchronise aussi adresse et identifiant fiscal entre parent et
contact lié. Des valeurs source divergentes bloquent ce format natif pour éviter
leur écrasement silencieux. Elles nécessitent une correspondance manuelle validée.
L’identifiant fiscal de l’exemple est explicitement fictif et sans valeur fiscale.

## Préparation et rapprochement

Depuis la racine du dépôt, avec Python standard :

```sh
python3 -m migration.prepare migration/example/bundle.json /tmp/m01-preparation
```

Le répertoire de sortie doit être nouveau. Il contient un rapport privé
(`report.json`, empreinte du paquet, date UTC, volumes, écarts et soldes par
devise) et, si le paquet est cohérent, `contacts.csv` et le plan du contrat 2. Aucun accès réseau ni
écriture Odoo. Les clés de secrets et d’autorisations sont refusées.

Codes de sortie : `0` préparation cohérente avec seconde vérification déclarée ;
`2` écarts bloquants ou seconde vérification à effectuer ; `1` entrée/sortie
invalide. Un paquet bloqué ne produit pas de CSV de contacts. `prepared` ne
signifie jamais « migration validée » : `cutover_authorized` reste faux.

Sur une **copie autorisée et isolée uniquement**, neutraliser d’abord serveurs
SMTP, courriels en attente, tâches planifiées, automatisations et intégrations
sortantes ; vérifier cette neutralisation, les sauvegardes et leur restauration.
Ne jamais pointer les essais vers la production. L’outil hors ligne ne configure
pas cet environnement et n’en atteste pas la neutralisation.

Importer le CSV par l’import officiel de Contacts avec un opérateur autorisé
dans la société exploitante cible. `company_id/id` désigne cette société ;
`parent_id/id` désigne l’entreprise cliente. Les identifiants de pays et de
société doivent exister sur la cible. Les contacts importés restent archivés ;
aucun utilisateur, mot de passe, invitation ou droit portail n’est créé.
Rejouer le même CSV, avec les mêmes identifiants externes : mise à jour des mêmes
contacts. Pour voir les lignes, inclure les contacts archivés.

Exporter ensuite **la sélection importée uniquement**, avec les colonnes
techniques et leur ordre de `contacts.csv` (export natif compatible avec
l’import, langue anglaise pour les booléens). Conserver ce relevé comme preuve
de cible ; ne pas recopier le CSV source pour simuler un rapprochement.

```sh
python3 -m migration.prepare migration/example/bundle.json /tmp/m01-rapprochement \
  --target-contacts /chemin/prive/contacts-exportes.csv
```

La comparaison porte sur population, identifiants, valeurs, pays, société et
parent. Sans ce relevé, le rapport indique `contact_target_reconciliation:
pending`. Pour les autres lots, rapprocher manuellement source et cible :
volumes, liens, ouverture des fichiers et soldes par devise. Consigner les écarts,
les inconnus et leur décision dans le procès-verbal ; ne pas les masquer par un
total global.

Une seconde personne contrôle un échantillon et consigne `review` : `reviewer`
distinct du préparateur source, date ISO, notes et `samples` de couples
`[lot, identifiant_source]`. Il s’agit d’une déclaration de contrôle, sans
authentification ni signature fournie par l’outil. Les contrôles de cible des
autres lots et l’accord de direction restent indispensables à une bascule.

## Recette courte

1. Préparer l’exemple fictif ; retrouver neuf lots, les trois fichiers vérifiés,
   les deux devises séparées et la seconde vérification encore à effectuer.
2. Dans la base d’essai neutralisée, importer puis réimporter les contacts.
   Vérifier les mêmes identifiants, les liens parent/pays/société, l’archivage,
   l’absence de compte et de courriel. Vérifier les droits avec un autre profil
   de société et le public. Exporter et rapprocher les contacts effectivement lus.
3. Retirer une référence d’inscription, altérer un fichier, un solde ou une valeur
   exportée : rapport bloqué. Dupliquer un identifiant : aucun nouveau CSV émis.
   Deux contacts partageant un e-mail restent distincts.
4. Préparer `qualified-bundle.json` dans un nouveau répertoire. Vérifier la
   couverture de l’inventaire, les cibles et les réserves du plan. Retirer une
   décision, sa qualification ou son archive : rapport bloqué et aucun CSV/plan.
   Vérifier manuellement la couverture des 44 champs du relevé privé avant toute
   extraction réelle, sans publier ce relevé ni des valeurs métier dans GitHub.
5. Sur copie neutralisée, importer/rejouer le CSV ICE, exporter et rapprocher.
   Vérifier l’ICE parent/contact, le pays, les mêmes contacts archivés et l’absence
   de comptes/courriels. Un mauvais contrôle ICE doit faire échouer tout le lot
   natif ; une clé inconnue, un pays incohérent ou un conflit parent/contact doit
   être bloqué avant émission du CSV. Tester aussi les profils société/portail.
6. Pour les lots manuels, vérifier sur copie les liens cours/programme/réalisation,
   la durée, la classification des questionnaires, les pièces et les droits fermés.
   Aucun résultat historique transformé en tentative/signature/anonymat. Ces essais
   ne sont pas couverts par les seuls tests d’import des contacts.
7. Faire contrôler l’échantillon par une seconde personne. Archiver paquet,
   empreintes, relevés cible, écarts et procès-verbal dans un espace restreint,
   hors dépôt public. Une version historique inconnue reste une réserve.

Les essais réels, l’activation sécurisée des comptes, la validation des
habilitations entreprise et la bascule exigent des décisions distinctes. Aucun
mot de passe source à extraire, aucun compte activé par correspondance de domaine,
aucune reprise automatique des personnalisations anciennes.

## Validation de cet incrément

Les tests hors ligne couvrent le contrat 1 conservé, la couverture des décisions,
les réserves, les archives, les conflits et le rapprochement JSON. Les tests natifs
utilisent l’image Community épinglée `20.0-20261015`, l’ORM officiel `load`/`export_data`
et des données fictives sur base jetable : rejeu, annulation du lot invalide,
relations, sociétés, public, absence de comptes et courriels. Ils ne constituent
pas une migration réelle ni une recette dynamique de tous les lots manuels.
La CI cumulative, ses configurations et les migrations historiques restent
inchangées. Les résultats réellement exécutés figurent dans la PR.
