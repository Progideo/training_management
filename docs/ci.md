# CI Odoo — suite cumulative

Référence : [issue #47](https://github.com/Progideo/training_management/issues/47).
Un workflow **CI Training Management**, une suite cumulative et un verdict commun
**Validation CI Odoo**. Aucun réglage de protection GitHub n’est modifié.

## Suite et configurations

Tous les tests des addons sélectionnés sont découverts par Odoo avec des sélecteurs
au niveau du module, sans liste de classes ni découpage par incrément. Ajouter un
test dans le dossier `tests` de son addon et l’importer dans `tests/__init__.py`
suffit à enrichir cette même suite. Les tests d’orchestration vérifient cet import
et la présence des fichiers et méthodes déjà couverts, en partant de l’inventaire
Git de référence. Les nouveaux fichiers importés sont acceptés ; retirer un fichier
historique avec son import reste détecté.

La seule matrice porte sur les configurations :

| Configuration | Addons testés | Standard installé avant la suite |
| --- | --- | --- |
| Socle | Training Management | Base |
| Ventes | Socle et Ventes | Base |
| Surveys | Socle et Surveys | Base |
| Ventes + Surveys | Les trois addons | Base |
| Website + Ventes | Socle et Ventes | Website/eLearning en anglais puis variante française |
| Website + Ventes + Surveys | Les trois addons | Website/eLearning en anglais puis variante française |

Chaque configuration exécute toute sa suite une fois, sur une base vierge. Les
profils restreints, cas multi-sociétés, HTTP, PDF et régressions natives Surveys
restent dans leurs tests existants. Les variantes françaises Website préparent le français
avant l’installation des addons : les anciennes répétitions de deux classes HTTP
après préparation de la langue sont ainsi incluses dans la suite entière.

Le manifeste [suite.json](../tests/ci/suite.json) définit les configurations et les
preuves attendues. [run_suite.py](../tests/ci/run_suite.py) utilise l’image Odoo
Community `20.0-20261015` épinglée par digest et PostgreSQL 18.6. Les variantes Website en anglais restent présentes ; le français est une configuration
supplémentaire de la même suite, sans retirer leur couverture. Le job de qualité
exécute tous les tests du dépôt et `pre-commit` (ruff et pylint-odoo).

## Migrations, conservation et concurrence

Le relevé S08 antérieur à la mise à jour utilise le code de sa révision historique,
afin que le préchargement ORM ne demande pas des colonnes ajoutées depuis.
Ses données, sa sonde et ses comparaisons complètes restent inchangées.

Un contrôle commun conserve les vingt parcours historiques et ajoute P09 : installation progressive,
installation Ventes, reprises S02/S03, Website, catalogue avec/sans Website,
protection documentaire, préparation, supports, activités, examens, présences,
attestations, évaluations, retours, qualité S09.3, intervenants S09.4 et mise à jour S10. Le parcours P09 part du candidat V1 `99c079a`, compare toutes les lignes
historiques Training/Surveys (dont un programme HTML et les octets de son PDF antérieur), puis conserve les références de parcours après
une nouvelle mise à jour, teste deux rattachements concurrents et vérifie la
lecture du portail sans modification des historiques. Il conserve aussi les
définitions et règles P10 après mise à jour et vérifie qu’un calcul d’orientation
ne persiste aucune réponse. Le même parcours conserve ensuite actions P11, preuves
privées, retours et politiques après deux mises à jour ; deux transactions
concurrentes produisent une seule réalisation d’action et un seul rappel natif.
Les nouvelles colonnes P12 des lignes S05 antérieures sont vérifiées vides avant
la comparaison exacte de toutes leurs colonnes historiques.
Le même parcours conserve ensuite les grilles P12 V1/V2, remises et décisions par
critère après deux mises à jour ; des transactions concurrentes déposent puis
valident une seule version avec une notification par opération.
Il conserve aussi les droits P13, créneaux publiés, réservations et annulations,
conditions figées, notifications et fichiers après deux mises à jour. Les courses
P13 portent sur la dernière place, le dernier quota et les doubles confirmations
et restitutions, sans nouveau parcours général ni configuration supplémentaire.
P14 prolonge ce même parcours : avis nommé, avis retiré, cas client autorisé,
consentements, décisions, invitations et fichiers privés sont comparés exactement
après deux mises à jour. Les courses portent sur deux invitations d’une inscription,
la double soumission d’un accord, publication contre retrait et double retrait.
P16 prolonge ce parcours par deux mises à jour comparant exactement les décisions
publiques, consentements, journaux, courriels en file et fichiers antérieurs. Les
courses couvrent double abonnement, double publication, dernière place et
désabonnement face à la préparation du transport, puis double désabonnement.
Le parcours COM02/COM03 part de la V2 `367bfff`, conserve les colonnes et lignes
historiques métier, commandes, factures, écritures, paiements, rapprochements,
pièces et audits bancaires après deux mises à jour ; il vérifie également le
marqueur de confidentialité et la désactivation de l’ancien assistant.
Le parcours `native_rules` part de #103 (`f8c4591`) et compare les documents,
PDF, habilitations et courriels après deux mises à jour ; il vérifie la migration
des identités vers les modèles natifs et des anciens critères fiscaux.
Le parcours `p20` part du main fusionné `92b0c3d` (#103/#104) : anciens PDF et
preuves comparés intégralement, aucune publication rétroactive, nouveau PDF/registre
conservés après mise à jour, émissions et révocations concurrentes avec reprise
après conflit. Il rejoint le même job de migrations ; les tests P20 sont découverts
automatiquement dans les huit configurations. Le parcours `closure_continuity`
part de `149a303` (P20 fusionné) : dossier clos et responsable archivé, comparaison
exacte des PDF et preuves, réaffectation et rectification, seconde mise à jour,
puis concurrence réelle entre transfert/révocation et deux rectifications.
Le parcours P01–P06 part du main `1db3b95`, conserve
programmes/PDF, supports privés, demandes et inscriptions, vérifie l’absence
d’exposition implicite et ajoute des soumissions/nominations concurrentes réelles.

Les scripts historiques exécutent toujours les installations, mises à jour,
préparations d’historiques, comparaisons, mises à jour répétées et sondes de
concurrence réelle sur des données fictives. Ils ne relancent plus les tests des
addons. Les installations vierges autonomes qui ne servaient qu’à relancer ces
tests sont remplacées par les configurations correspondantes de la suite.
Les champs, droits, références, PDF et historiques persistés restent comparés
après migration ; les tests généraux du comportement courant sont centralisés.

Les anciens contrats [coverage.json](../tests/ci/coverage.json) et
[workflow_coverage.json](../tests/ci/workflow_coverage.json) restent des références
de conservation. Le nouveau manifeste indique explicitement les phases déplacées.
Les tests comparent les scripts à la version fusionnée S09.3 après retrait de ces
seules répétitions : révisions historiques, arguments métier et sondes inchangés.
Une nouvelle migration nécessite d’ajouter son parcours et ses preuves au contrat,
sans créer de nouveau lot de tests généraux.

Les parcours s’exécutent au maximum trois à la fois dans le contrôle commun.
Chacun possède son PostgreSQL, son réseau, ses bases et volumes ; les noms de
bases historiques fixes restent donc isolés. Les phases d’une même base restent
séquentielles. Un échec n’empêche pas les autres parcours de produire leurs preuves.
Une collision de noms est refusée avant toute création ; un échec de réservation
ne déclenche aucun nettoyage des ressources existantes. Une relance invalide son
ancien marqueur de succès avant de commencer.
Le nettoyage vise uniquement les ressources du run, sans purge Docker globale.
Aucun accès OVH, secret ou jeu de données réel n’est utilisé.

## Verdict et diagnostic

Onze contrôles sont visibles : qualité, huit configurations, migrations et verdict.
Les artefacts comprennent un dossier par configuration et un artefact de migration
avec les journaux de chacun des 23 parcours. Ils sont publiés même après échec.

[check_results.py](../tests/ci/check_results.py) refuse les prérequis échoués,
annulés, exclus ou manquants. Il vérifie chaque configuration, un résultat Odoo
réussi avec au moins un test, la préparation française, chaque phase historique
et les marqueurs de succès émis seulement après exécution et nettoyage.
Les journaux absents, vides ou contenant un échec font échouer la validation.
Le verdict utilise `needs` et `always()`, sans `continue-on-error`.

## Recette courte

1. Installer `tests/ci/requirements.txt`, puis lancer
   `python3 -m unittest discover -s tests -v`, `pre-commit run --all-files`,
   la vérification syntaxique Bash des scripts et `actionlint`.
2. Dans la PR, vérifier une seule CI, la matrice des huit configurations et le
   contrôle commun de migration. Aucun contrôle ne doit porter le nom d’un lot
   fonctionnel. La suite ne doit pas être relancée depuis les scripts historiques.
3. Examiner les neuf artefacts : résultats Odoo non vides, préparation française
   des deux variantes Website, sondes historiques et concurrence conservées.
4. Vérifier **Validation CI Odoo** et sa synthèse. Les tests locaux injectent aussi
   des pannes et des preuves manquantes ; ils ne remplacent pas les exécutions
   Odoo réelles sur GitHub.
