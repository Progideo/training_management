# M01 — Préparation de la reprise Odoo 19

Référence : [#22](https://github.com/Progideo/training_management/issues/22),
MIG01–MIG03 et chapitre 24. Cet incrément prépare la reprise ; il ne migre pas
une base Odoo 19. Aucun schéma source réel n’est encore démontré. L’audit
historique reste suspendu. Les migrations de versions de l’addon dans la CI
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
| Soldes | Décimaux exacts, rapprochement séparé MAD/EUR ; aucune écriture comptable historique recréée. Autres devises : écart à instruire. |
| Supports et pièces | Chemins relatifs, fichiers locaux réguliers, empreintes SHA-256, responsable des accès et conservation déclarés. Le contrôle d’empreinte ne prouve pas la lisibilité d’un PDF. |
| Résultats | Version historique identifiée ; inconnue signalée. Pas de tentative, score, thème ou certificat inventé. |
| Archive | Index source/fichiers, responsable, accès et conservation à valider. Préservation des originaux ; pas de nouvelle preuve générée à leur place. |

Les méthodes `manual` et `archive` documentent une destination à traiter :
elles n’exécutent aucun import. L’outil vérifie la cohérence du paquet déclaré,
pas sa fidélité à une base source non inspectée. Seuls les contacts ont un
format d’import natif démontré dans cet incrément, vers `res.partner` uniquement.
Le rapprochement CSV est réservé à cette méthode, pas aux lots manuels.

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
devise) et, si le paquet est cohérent, `contacts.csv`. Aucun accès réseau ni
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
4. Faire contrôler l’échantillon par une seconde personne. Archiver paquet,
   empreintes, relevés cible, écarts et procès-verbal dans un espace restreint,
   hors dépôt public. Une version historique inconnue reste une réserve.

Les essais réels, l’activation sécurisée des comptes, la validation des
habilitations entreprise et la bascule exigent des décisions distinctes. Aucun
mot de passe source à extraire, aucun compte activé par correspondance de domaine,
aucune reprise automatique des personnalisations anciennes.
