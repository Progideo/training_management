# CI Odoo — organisation et couverture

Référence : [issue #47](https://github.com/Progideo/training_management/issues/47).
Le workflow unique **CI Training Management** regroupe tous les contrôles de PR.
Son verdict final conserve le nom **Validation CI Odoo**. Il attend toutes les
tâches, même après un échec. Aucun paramètre de protection GitHub n’est modifié ;
si des contrôles spécialisés sont requis, remplacer leur sélection par ce verdict
commun au moment de la fusion, après vérification des protections applicables.

## Vue commune

Les tâches indépendantes se lancent en parallèle, avec leur propre runner,
PostgreSQL, bases et volumes. Les séquences de préparation, mise à jour et
comparaison restent internes à chaque tâche. La limite de quatre scénarios
parallèles du socle et les deux variantes du catalogue sont conservées.

| Tâches | Couverture conservée |
| --- | --- |
| Style et orchestration | Contrats de couverture, erreurs et règles Odoo |
| Socle : progressive, vierge, historiques, Website | Les quatre scénarios décrits ci-dessous |
| Catalogue et PDF, avec/sans Website | Versions, PDF et concurrence |
| S02.1 | Protection documentaire et historiques |
| S04 | Préparation, séances et concurrence |
| S05.1 / S05.2 | Supports privés, activités, tutorat et portail français |
| S06 / S07 | Examens blancs, présences et isolation |
| S08 | Attestations, preuves, historiques et concurrence |
| S09.1 / S09.2 | Évaluations, retours, droits, anonymat et concurrence |

Les dix anciens workflows spécialisés sont intégrés comme tâches du workflow
commun ; l’automatisation du Project reste indépendante. Les déclencheurs couvrent
les addons, tous les tests, les workflows et la configuration de qualité. Modifier
un scénario ou son orchestration déclenche ainsi toute la validation.

Le contrat [workflow_coverage.json](../tests/ci/workflow_coverage.json) référence
le code fusionné avant regroupement. Les tests comparent chaque ancienne tâche
à sa nouvelle définition (commandes, variables, services, matrices, délais et
artefacts) et vérifient que les scripts sont inchangés. Il recense aussi les
139 phases spécialisées attendues, en comptant les deux variantes du catalogue.
Les quatre scénarios du socle conservent leur contrat historique de 21 étapes.

## Style et règles Odoo

Le job d’orchestration exécute `pre-commit run --all-files`, configuré par
[.pre-commit-config.yaml](../.pre-commit-config.yaml) et [pyproject.toml](../pyproject.toml) :
`ruff check` et `ruff format` (longueur de ligne 120, règles E4/E7/E9/F ; F401 toléré
dans les `__init__.py`, `env` toléré dans les sondes `odoo shell`) puis `pylint-odoo`
avec ses règles par défaut (`--enable=odoolint`). En local : `pip install pre-commit`
puis `pre-commit run --all-files` avant de pousser. La version de `pylint-odoo`
n’est pas épinglée (aucun dépôt de hooks externe) : un durcissement de ses
règles peut donc faire échouer le contrôle sans changement du dépôt ; épingler
alors la version fautive. Les vues XML sont indentées à raison d’un élément par ligne.

## Quatre scénarios indépendants

Chaque entrée de la matrice utilise son propre runner, service PostgreSQL 18.6,
volume Docker et artefact. L’image Odoo reste celle épinglée pour S03 :
`odoo@sha256:61e3c71b0503c5f658e604c3e340bede20b97d05f726179fa006eae50a32fd23`.
Les données sont fictives ; aucun accès OVH ou secret de déploiement n’est utilisé.

| Scénario | Étapes conservées, dans l’ordre | Nombre |
| --- | --- | ---: |
| `incremental` | Installation/test du socle ; préparation de l’historique catalogue ; mise à jour/test du socle ; comparaison de l’historique ; installation/test Ventes sur ce socle ; concurrence des références bancaires | 6 |
| `fresh` | Installation/test Ventes sur base vierge ; concurrence S03 réelle | 2 |
| `history` | Installation S02 avec Website/eLearning depuis `a0c95fa` ; préparation historique S02 ; préchargement XML avec le registre S04 figé ; mise à jour/tests actuels ; comparaison S02 ; préparation historique S03 ; seconde mise à jour ; comparaison S03 | 8 |
| `website` | Installation Website/eLearning/socle courant ; préparation catalogue ; installation/tests Ventes ; mise à jour/tests Ventes ; comparaison catalogue | 5 |

L’installation progressive socle → Ventes reste dans un seul scénario : la séparer
en deux bases supprimerait la preuve de cette transition. Les noms de bases,
arguments Odoo, tags, sondes, phases et références historiques sont conservés.
Les profils restreints, cas multi-sociétés et intégrations continuent à être
exécutés par les mêmes suites Odoo ; aucun test d’addon n’est modifié.

Le contrat [coverage.json](../tests/ci/coverage.json) recense les 21 appels du
workflow de référence `80ad50c`. Les tests les comparent aux invocations effectives
du script, y compris le contenu des sondes transmis sur l'entrée standard.
Le préparateur historique utilise le registre S04 figé pour les anciennes vues
S03/S04 uniquement. Le lot catégories/PDF est aussi testé par une mise à jour
directe S04 avec et sans Website, sans préparation des vues ; voir le
[cadrage et la migration](catalogue-categories-pdf.md). Aucune étape
ni suite de tests n'est retirée. Un changement intentionnel de couverture doit
actualiser ce contrat et sa justification.

## Exécution et diagnostic

[run_odoo_scenario.sh](../tests/ci/run_odoo_scenario.sh) porte les opérations,
avec arrêt au premier échec dans un scénario. Les autres scénarios continuent
(`fail-fast: false`), pour conserver leurs résultats indépendants. La matrice est
limitée à quatre scénarios simultanés ; le petit job d’orchestration peut aussi
s’exécuter en parallèle, puis le contrôle final attend les deux ensembles.
Les étapes d’une même base restent strictement séquentielles.

Les bases sont propres à chaque scénario sur des services isolés. Les volumes et
conteneurs portent l’identifiant du run, de sa tentative et du scénario ; le
nettoyage vise seulement ces ressources. Aucun volume partagé entre jobs et
aucune commande globale de purge. Le code S02 archivé reste dans un dossier
temporaire, en dehors des artefacts, puis est supprimé.

Les artefacts `odoo-<scenario>-results` contiennent un journal par étape, les
résultats de nettoyage et `timings.tsv` (étape, code retour, secondes).
Ils sont téléversés même en cas d’échec ; l’absence de fichiers fait échouer
le téléversement. Le code retour de Docker et les erreurs d’écriture des journaux
ne sont pas masqués par `tee`.

[check_results.py](../tests/ci/check_results.py) exige :

- succès de toutes les tâches, dont les deux matrices ; échec, annulation, exclusion
  ou résultat manquant sont refusés ;
- présence des quatre artefacts du socle et des 21 étapes dans l’ordre attendu ;
- présence des onze artefacts spécialisés et de chaque journal de phase non vide ;
- codes retour nuls, durées valides et journaux présents.

Le job final utilise `needs` et `always()` pour ne pas devenir un succès implicite
lorsqu’un préalable échoue. Aucune exception `continue-on-error`. Une annulation
globale peut annuler le contrôle final lui-même ; elle ne produit pas de succès.
Voir les références officielles GitHub sur [les dépendances entre jobs](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-jobs)
et [les matrices et leur concurrence](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/run-job-variations).

La synthèse du verdict commun présente tous les scénarios et les phases vérifiées.
Les mesures de durée du socle restent disponibles. L’objectif du regroupement est
la lisibilité ; aucun scénario ni test n’est retiré pour réduire les minutes.

## Recette

1. `python3 -m pip install -r tests/ci/requirements.txt`, puis
   `python3 -m unittest discover -s tests -p 'test_odoo_ci.py' -v` : contrats de
   couverture, isolation, arrêt après panne injectée dans chaque scénario,
   propagation via `tee`, et refus des résultats incomplets/non réussis.
2. Vérifier la syntaxe Bash et GitHub Actions (actionlint 1.7.7 utilisé localement).
3. Sur la PR, vérifier une seule exécution **CI Training Management**, ses 17
   tâches nommées (matrices comprises), leurs quinze artefacts et le verdict
   **Validation CI Odoo**. Examiner les scénarios spécialisés et la synthèse ;
   les doubles Docker ne remplacent pas les exécutions Odoo réelles.
4. Les tests de l’orchestration injectent des échecs et vérifient le refus de
   toutes les tâches non réussies, des journaux manquants/vides et des phases
   incomplètes. Un échec produit aussi une synthèse finale explicite.

Cette modification concerne la CI uniquement ; aucune fusion ni aucun déploiement
n’est autorisé par cette documentation.
