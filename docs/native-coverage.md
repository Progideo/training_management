# Preuves Odoo 20 et limites de couverture

Vérifications du 20 octobre 2026 pour #5, #6, #7, #9 et #11.
Les sources standard ont été lues depuis le conteneur réellement installé.
Les copies de travail restent hors dépôt ; seules les empreintes sont conservées.

## Distribution et composants

- Exécutable : `Odoo Server 20.0-20261015`.
- Paquet système : `odoo 20.0.20261015`.
- Image effective et RepoDigest :
  `odoo@sha256:61e3c71b0503c5f658e604c3e340bede20b97d05f726179fa006eae50a32fd23`.
- Sources : `/usr/lib/python3/dist-packages/odoo`.
- `release.py` déclare la série 20.0 finale et le commit Odoo
  `49529f034a60e4e9838e08e0a5616e5f2f38c601`.
  Ce SHA est la provenance déclarée par le paquet ; il ne constitue pas une
  comparaison indépendante de chaque fichier avec le dépôt amont.
- Python 3.12.3 et PostgreSQL 18.6.
- Manifest `base` : licence LGPL-3 ; version installée `20.0.1.3`.
- Manifest `survey` : version 3.7, licence LGPL-3 ; dépendances déclarées
  `auth_signup`, `http_routing`, `mail`, `web_tour`, `gamification`, `digest`.
  Leur présence ne signifie pas que Training Management les rend obligatoires.
- Vérification SQL en transaction `BEGIN READ ONLY` puis `ROLLBACK` :
  `survey.survey`, `survey.question`, `survey.user_input`,
  `survey.user_input.line` présents.
- Contacts, Ventes (`sale_management`), Website, eLearning (`website_slides`,
  version installée `20.0.2.7`) et Surveys (`20.0.3.7`) installés dans la base
  de développement. `crm`, `event`, `website_sale` : `uninstalled`.

Empreintes SHA-256 des fichiers examinés :

```text
40de3f257ad530160009f2ebf00454b45222973d514837c1b55c146c0301290c release.py
e144d6d7fe1700e5937158cedd23c97b1a3b5f6a40821b863e33226198f24a51 addons/base/models/ir_access.py
e84f13aeaf02b61f69a38f4e293400279334386fd7619e64f6a21a6b5a383668 orm/models.py
adfacc45f92cbf26c62359bf22d76cc40b56dff8763a7b20b66e2d863220bb57 addons/survey/models/survey_survey.py
2e615254097beddd69ce3a60f09029d7931c62be619a7b907177d3ed62e51894 addons/survey/models/survey_user_input.py
5f0bcace50441f07bb2ed773592f6cbf1942b9407ac8866d3ec6d5af57c5c685 addons/survey/controllers/main.py
61629a7bca539ad03342fb88fa0e4129057b08edbfcbbb2bb7ca42fc276872cf addons/survey/views/survey_templates_management.xml
```

Conventions confirmées par le code et utilisées par S01 : `models.Constraint`,
`res.groups.privilege`, `ir.access` et ses restrictions globales, `check_access`,
`lock_for_update`, vues `list`, champs `res.users.group_ids`.
Les autorisations d'export et contrôles de cohérence multi-sociétés sont ceux du
standard. Les libellés sont exportés via `odoo.tools.translate.trans_export` ;
l'ancien argument serveur `--i18n-export` n'existe pas dans cette version.

## Surveys : code observé

| Exigence | Constat précis dans les sources installées | Conclusion |
| --- | --- | --- |
| EXA01 | `survey_survey.py` : `questions_selection=all`, ordre des questions et contrainte de durée positive | Configuration candidate ; la publication conforme au besoin reste à tester |
| EXA02 | `survey_user_input.py:68` et `_compute_answer_score` : somme des points par réponse cochée, pas ensemble exact du QCM | Extension nécessaire pour le barème proposé par la spécification |
| EXA03 | `_compute_survey_time_limit_reached` lit la durée actuelle du sondage ; `controllers/main.py:562` ajoute dix secondes avant de rejeter une remise hors délai | Durée non figée ; tolérance standard différente de l'échéance stricte demandée |
| EXA04 | Sauvegarde dans `survey_submit` par page ; correction finale configurable avec `scoring_with_answers` | Pas de preuve de sauvegarde de chaque changement ; déconnexion et correction à tester par HTTP |
| EXA05 | `_create_answer` peut créer plusieurs réponses ; `survey_button_retake` masque le bouton si certification réussie | Répétition possible au niveau modèle ; UX Certification et unicité active insuffisantes |
| EXA06 | Références vivantes aux questions et réponses ; `question_id` de la ligne en suppression cascade | Pas de photographie historique immuable conforme |
| P07 | Retour et navigation existent, confirmation de remise conditionnée dans le frontend à Certification | Palette, marquage, autosauvegarde et fin à expiration restent à démontrer/étendre |
| P08 | Aucun instantané de thèmes/barèmes propre aux exigences identifié dans les fichiers examinés | Analyse par thème et liens autorisés non démontrés |
| SEC01 | `controllers/main.py:92` ne vérifie pas l'identité du partenaire si un jeton explicite est fourni ; login et possession de jeton sont des mécanismes distincts | Ne pas assimiler « connecté » à « propriétaire de la tentative » ; tests HTTP croisés indispensables |

Le délai de dix secondes est un constat de code, pas un test navigateur.
La fermeture automatique sans nouvelle requête, les scénarios mobiles/clavier,
les routes de correction, les fichiers et l'intégration eLearning n'ont pas été
recettés. Aucune vulnérabilité générique d'Odoo n'est revendiquée : on constate
des différences avec le périmètre de confidentialité et d'historisation demandé.

## Surveys : essais réellement exécutés

Script : [survey_native_probe.py](../tests/probes/survey_native_probe.py).
Base jetable dédiée avec `base,survey`, sans serveur HTTP ni cron, données
fictives et transaction annulée après la sonde. Le script refuse les bases
ne commençant pas par `tm_s01_test_`.

Les créations de tentatives utilisent l'API modèle avec l'identité d'un compte
portail fictif, depuis un environnement privilégié comme le font les contrôleurs.
Cela ne constitue **pas** une preuve du parcours HTTP portail. Le refus de lecture
ORM est, lui, exécuté sous le véritable utilisateur portail.
Le passage à `done` du scénario est écrit directement pour éviter les effets de
notification : la sonde ne valide pas le workflow de remise.

Sortie réelle :

```json
{
  "all_choices_including_wrong_score": 100.0,
  "partial_answer_score": 50.0,
  "new_attempt_after_success": true,
  "simultaneous_unfinished_attempts": 2,
  "expired_at_ten_minutes": true,
  "expired_after_source_duration_change": false,
  "completed_attempt_question_title": "Changed after completion",
  "lines_before_question_deletion": 3,
  "lines_after_question_deletion": 0,
  "portal_direct_orm_read": "denied"
}
```

Le QCM contenait A et B correctes (un point chacune), C incorrecte (zéro).
Cocher les trois donne 100 % ; cocher seulement A donne 50 %. Modifier la durée
du sondage de 10 à 20 minutes rend non expirée une tentative commencée onze
minutes avant. Le titre modifié devient celui de l'ancienne tentative et la
suppression de la question supprime ses trois lignes historiques.

Recommandation : conserver Surveys comme candidat à une intégration ciblée,
mais ne pas le déclarer conforme ni implémenter les examens avant une décision
sur les écarts, la recette HTTP avec comptes portail et la charge des extensions.
Le catalogue S01 reste indépendant de cette décision.

## S01 : protocole de validation

Les tests utilisent l'image ci-dessus dans un processus Odoo séparé, avec
`--no-http --workers=0 --max-cron-threads=0`, un répertoire d'addons temporaire
et une base jetable distincte. Le mode test démarre néanmoins son serveur HTTP :
`--http-interface=127.0.0.1 --http-port=0` impose un port local dynamique, sans
conflit avec le service actif et sans exposition extérieure. Aucun changement
de configuration, d'addons actifs ou de données de `neopro_dev`.

Commande Odoo d'installation utilisée, après résolution de la connexion par
l'entrypoint existant (aucun secret inclus ici) :

```sh
odoo -d tm_s01_test_final_20261020 -i training_management \
  --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/tmp/tm_s01_addons \
  --without-demo --stop-after-init --no-http --workers=0 \
  --http-interface=127.0.0.1 --http-port=0 \
  --max-cron-threads=0 --data-dir=/tmp/tm_s01_test_final_20261020 \
  --test-enable --test-tags=/training_management
```

Les 14 méthodes de test natives couvrent versions, transitions, contenu
incomplet, audit, contexte hostile, traductions, unicité, durée négative,
opérations par lots, conservation du parent, utilisateurs restreints,
contacts standards et accès/exports intersociétés.

Le scénario [catalogue_upgrade_probe.py](../tests/probes/catalogue_upgrade_probe.py)
persiste ensuite une V1 publiée fictive, son identité et les valeurs attendues.
Une nouvelle exécution Odoo avec `-u training_management` est suivie d'une
comparaison exacte. Deux transactions distinctes tentent également de retirer
la même version ; la seconde doit recevoir `LockError`. Elles sont annulées.
Le français est chargé et ses libellés contrôlés dans ce scénario.

La CI proposée reproduit ce protocole et archive les journaux. Les détails des
résultats finaux sont consignés dans la PR ; ne pas confondre un workflow ajouté
avec une exécution GitHub Actions réussie.

### Résultats exécutés le 20 octobre 2026

Sur la base jetable `tm_s01_test_final_20261020`, avec le code livré :

- Installation vierge, code retour 0 : `0 failed, 0 error(s) of 16 tests`.
- Mise à jour, code retour 0 : `0 failed, 0 error(s) of 14 tests`.
- Les 14 méthodes métier de `TestCatalogue` sont exécutées dans les deux cas ;
  le bilan d'installation inclut également des contrôles natifs chargés à
  l'installation. Le compteur statistique interne n'est pas un décompte des
  seules méthodes métier.
- Scénario persistant : `UPGRADE_BASELINE_PERSISTED`, puis
  `FRENCH_LABELS_VERIFIED`, `CONCURRENT_TRANSITION_REFUSED` et
  `UPGRADE_HISTORY_UNCHANGED`, codes retour 0.
- Journaux dans le conteneur de test : `/tmp/tm_s01_final_install.log`,
  `/tmp/tm_s01_final_update.log`, `/tmp/tm_s01_final_prepare.log` et
  `/tmp/tm_s01_final_verify.log`. Aucun secret ni journal brut exporté au dépôt.
- Aucune erreur ou alerte critique dans les deux exécutions finales. Le paquet
  standard signale seulement l'absence de `markdown2` dans son contrôleur de
  pièces jointes ; S01 ne dépend pas de ce rendu.

Les premières exécutions avaient révélé les API propres à Odoo 20, des attentes
de test à corriger et un conflit de port du serveur de test. Ces points ont été
corrigés puis installation et mise à jour rejouées. Les résultats ci-dessus
proviennent des exécutions finales, pas des essais préliminaires.

Limites : aucune recette navigateur complète, aucun parcours HTTP portail, aucun
test de migration depuis Odoo 19 et aucune installation dans `neopro_dev`.
Les bases temporaires contiennent uniquement les données fictives des essais.

### Incident de recette et correctif 20.0.1.0.1

Après l'installation de 20.0.1.0.0 dans `neopro_dev`, explicitement autorisée
par l'utilisateur et précédée d'une sauvegarde base/fichiers le 20 octobre,
la recette manuelle a révélé deux lignes V1 dans la fiche formation. Après
actualisation, une seule restait, sans les informations pédagogiques saisies.

Le contrôle SQL en lecture seule confirme une seule V1 brouillon, avec date de
modification identique à la création et champs pédagogiques non renseignés.
Les traces montrent un `training.program.version.web_save` suivi du refus de
`action_validate`, puis un `training.course.web_save`. Aucun enregistrement
ultérieur des champs du programme n'est démontré. Il ne s'agit donc pas d'un
doublon persistant en base. Le mécanisme exact du client navigateur n'a pas
été reproduit automatiquement ; ne pas attribuer l'incident à une faute de
saisie ni prétendre avoir démontré un défaut du cœur Odoo.

Le correctif supprime le parcours d'édition imbriquée : la fiche formation
propose **Versions de programme**, ouvrant la liste filtrée puis une fiche
programme autonome. Les valeurs de formation et de titre sont préremplies.
Aucune donnée existante n'est supprimée ou reconstruite.

Deux tests s'ajoutent aux 14 tests métier : accès à l'action sous profils
restreints et scénario de formulaire natif `Form` (création incomplète, refus de
validation, complétion, enregistrement, invalidation du cache et relecture,
unicité et validation). Mise à jour exécutée sur `tm_s01_test_final_20261020` :
`0 failed, 0 error(s) of 16 tests`, code retour 0.
Ce test de formulaire serveur ne remplace pas une recette du client navigateur.

Recette de non-régression à exécuter après autorisation de mise à jour de
`neopro_dev` : ouvrir la V1 existante via le nouveau bouton, renseigner un
objectif, enregistrer puis actualiser et vérifier sa conservation ; compléter
ensuite tous les champs et contrôler à nouveau leur persistance avant validation.
Au moment de la préparation de ce correctif, la recette navigateur reste
bloquée et `neopro_dev` conserve la version 20.0.1.0.0.
