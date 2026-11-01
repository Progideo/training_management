# Parcours navigateur à la demande

Point 9 de la revue : complément aux contrôles Odoo de [la CI](ci.md),
références UX01, SEC01 et supports privés S05. Robot Framework Browser pilote
réellement Chromium avec Playwright. Les mots clés métier sont dans
[`resources/business/training.resource`](../manual-browser/resources/business/training.resource).
Le choix s'appuie sur les documentations officielles
[d'installation](https://robotframework-browser.org/docs/start/installation/) et
[d'architecture](https://robotframework-browser.org/docs/concepts/architecture/).

## Périmètre

| Sélection | Parcours vérifié par l'interface |
| --- | --- |
| `portal` | Connexion participant, accueil, Mes formations, détail, téléchargement du PDF privé et contrôle des octets |
| `isolation` | Autre compte portail sans inscription : absence du lien et refus HTTP 404 du détail et du fichier par navigation navigateur |
| `submission` | Dépôt de plus de 20 Mo refusé, texte conservé et aucun dépôt créé, nouveau fichier accepté, texte et fichier présents après rechargement |
| `internal` | Coordinateur restreint : création d'une catégorie avec le formulaire natif et persistance après rechargement |

Le tag `private` sélectionne les deux premiers parcours. Chaque test possède un
contexte navigateur neuf. Les données sont en anglais pour stabiliser les
sélecteurs et assertions ; les noms techniques des champs et les identifiants
métier sont préférés aux positions dans la page. La suite ne prétend pas couvrir
les examens, le multi-société ou tous les rôles. L'émargement reste par
demi-journée et la durée des attestations issue du planning.

Les tableaux de présence et les signatures personnelles ne font pas partie de
cette suite Robot. Leur [recette dédiée](s07-attendance-signatures.md#mise-à-jour-et-recette-courte)
comprend clavier, chargement PNG, petit écran et tracé sur appareil tactile réel.
Consigner ces vérifications séparément dans la PR concernée.

## Structure des tests

La suite applique le Page Object Model avec des ressources Robot Framework,
sans ajouter une seconde bibliothèque Playwright ni une hiérarchie de classes.
Voir les principes officiels [Playwright](https://playwright.dev/docs/pom) et
[Robot Framework](https://docs.robotframework.org/docs/examples/project_structure).

- `journeys.robot` : scénarios, données attendues et tags ; uniquement des mots
  clés métier, sans sélecteur, URL ni commande Browser.
- `resources/business/training.resource` : bibliothèque de mots clés métier
  paramétrés, composition des pages et assertions fonctionnelles. Elle ne lit pas
  le DOM directement et ne connaît aucun sélecteur.
- `resources/pages/*_page.resource` : objets de page connexion, portail,
  formation et catégories. Ils encapsulent routes, sélecteurs, actions, attentes
  de disponibilité et lectures de l'interface. Ils retournent les valeurs utiles
  sans décider du résultat métier attendu. Les sélecteurs dynamiques sont
  construits ici à partir des identifiants reçus en arguments.
- `resources/browser.resource` : configuration et cycle de vie du navigateur,
  contexte neuf, capture d'échec et fermeture garantie même si la capture échoue.
- `fixture.py` et `run.py` : préparation et nettoyage indépendants des parcours.

Les appels aux pages sont qualifiés par leur nom pour éviter les ambiguïtés.
Une page ne dépend ni de la bibliothèque métier ni des données globales de la
fixture. Pour adapter l'interface, modifier la page concernée ; pour changer une
règle attendue, modifier le mot clé métier ; pour ajouter un parcours, composer
ces mots clés dans la suite. Le dépôt corrigé remplace seulement le fichier,
sans ressaisir le texte : cette propriété reste explicitement testée.

## Installation isolée

Prérequis : Python 3.10+, Docker actif, accès au registre des images et aux
binaires Playwright. Sous Linux, installer aussi les dépendances système de
Chromium selon la documentation Browser. Depuis la racine du dépôt :

```sh
python3 -m venv .venv-browser
.venv-browser/bin/python -m pip install -r manual-browser/requirements.txt
.venv-browser/bin/rfbrowser install chromium
```

L'extra `bb` fournit Node et les dépendances Browser ; ne pas ajouter
`rfbrowser init`. Les versions directes sont figées séparément des outils Odoo.
Browser et Robot Framework sont sous Apache-2.0 ; aucun code de ces bibliothèques
n'est incorporé aux addons.

## Lancement explicite

```sh
.venv-browser/bin/python manual-browser/run.py --list
.venv-browser/bin/python manual-browser/run.py
.venv-browser/bin/python manual-browser/run.py --include submission
.venv-browser/bin/python manual-browser/run.py --include portal --include internal --headed --port 18099
```

Plusieurs `--include` font une union. Un code retour non nul signale un échec.
Aucune installation ni exécution à l'import, aucun appel depuis les workflows,
la commande habituelle de tests ou un planificateur. Le dossier est en dehors de
`tests/` et n'est pas découvert par `unittest` ni par Odoo.

Le lanceur prépare un PostgreSQL et un Odoo neufs avec le code courant monté en
lecture seule ; il réutilise uniquement le gestionnaire de ressources jetables
existant. Il installe Website et Training Management sans démos, puis exécute
`fixture.py` par `odoo shell` pour préparer les comptes et les objets. La création
de catégorie et les dépôts vérifiés ne sont jamais faits par cet amorçage.
L'image Community est celle épinglée dans le gestionnaire ; `ODOO_IMAGE` permet
un remplacement explicite compatible.

Les comptes par défaut sont `browser_participant`, `browser_outsider` et
`browser_coordinator`. Les variables `TM_BROWSER_PARTICIPANT`,
`TM_BROWSER_OUTSIDER`, `TM_BROWSER_COORDINATOR` personnalisent les identifiants.
`TM_BROWSER_PASSWORD` personnalise le mot de passe ; sinon un secret aléatoire
est créé pour cette exécution. Ne pas le passer en argument de commande.
La saisie utilise `Fill Secret`, sans trace Playwright ni journal de débogage.
Les comptes n'ont que le rôle portail ou coordinateur, jamais administrateur.

L'URL locale dépend de `--port` et n'écoute que sur `127.0.0.1`. Pour un
**environnement de recette isolé déjà préparé**, la suite Robot accepte
`TM_BASE_URL` et un fichier de variables JSON contenant `ENROLLMENT`, `ACTIVITY`,
`MATERIAL`, `CATEGORY_ACTION`, `OVERSIZE_FILE`, `VALID_FILE` :

```sh
.venv-browser/bin/python -m robot --variablefile /chemin/prive/variables.json \
  --outputdir test-results/browser-externe --include portal manual-browser/journeys.robot
```

Les comptes, mots de passe et fichiers fictifs doivent correspondre à la fixture.
Cette exécution directe ne prépare ni ne nettoie le serveur cible : réserver une
base jetable dédiée et la supprimer ensuite. Préférer le lanceur local, dont le
nettoyage s'applique aussi aux échecs et interruptions ordinaires.

## Résultats et nettoyage

`test-results/browser_<identifiant>/` contient `report.html`, `log.html`,
`output.xml`, les journaux d'installation/serveur/nettoyage et les captures en
cas d'échec. Ces fichiers, téléchargements, variables locales et environnements
virtuels sont ignorés par Git. Ils restent privés même avec des données fictives ;
ne jamais y introduire des comptes ou données réels ni publier les rapports bruts.

Le lanceur désactive crons et serveurs sortants, ne démarre aucun worker cron et
pointe SMTP sur un port local fermé. Il supprime uniquement ses conteneurs,
volume et réseau à identifiant unique, en conservant les rapports. Après un arrêt
brutal de la machine, retrouver cet identifiant dans le dossier de résultats et
supprimer exclusivement les ressources `tm_suite_browser_<identifiant>_manual`
correspondantes ; ne jamais utiliser un nettoyage Docker global.

Recette courte : lancer les quatre parcours, ouvrir le rapport et vérifier
quatre succès, relancer un tag seul, contrôler les journaux `cleanup-*.log` et
`git status --short`. Les résultats réellement exécutés et leurs limites sont
consignés dans la PR.
