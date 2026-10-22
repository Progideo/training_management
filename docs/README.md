# Documentation de référence

Point d’entrée documentaire pour le dépôt `Progideo/training_management`.
Les besoins et leur avancement restent dans les issues ; les changements et
leurs validations dans les pull requests ; les décisions durables dans la documentation.

## Ordre de lecture et autorité

1. [AGENTS.md](../AGENTS.md) : consignes applicables au dépôt.
2. [Spécification fonctionnelle v2](references/Training_Management_Specification_Fonctionnelle_v2.md) : exigences, décisions fonctionnelles et recette attendue.
3. [Prompt maître Training Management](references/MASTER_PROMPT_TRAINING_MANAGEMENT_MODULE.md) : méthode de conception, développement, sécurité et validation.
4. [Backlog de référence — issue #3](https://github.com/Progideo/training_management/issues/3) et issue concernée : ordre de travail et besoin à traiter.
5. [Automatisation du Project](project-automation.md) : procédure propre au tableau GitHub et validations d’activation.

Les décisions explicites les plus récentes de l’utilisateur prévalent sur les
documents antérieurs. La spécification et ses évolutions validées définissent le
périmètre ; le prompt maître définit la méthode. Les chapitres 18 à 24 de la
spécification détaillent les ajouts et priment en cas de conflit de priorité,
conformément à son paragraphe « Statut des propositions ».

Une divergence entre pièce jointe, dépôt et décision doit être signalée et sa
version de référence identifiée avant correction. Ne pas synchroniser
automatiquement des sources externes ni modifier silencieusement une exigence.

## Provenance et statut des documents importés

Import documentaire préparé le **15 octobre 2026** pour
l’[issue #4](https://github.com/Progideo/training_management/issues/4).
Les deux fichiers proviennent des références disponibles dans le projet ChatGPT
« NeoPro - odoo 20 » et sont copiés **octet pour octet**, avec leurs noms d’origine,
dans `docs/references/`. Les sources synchronisées restent en lecture seule.
Cet import ne signifie pas que le projet ChatGPT et GitHub resteront synchronisés.

| Document | Version et statut |
| --- | --- |
| Spécification fonctionnelle | Version 2.0 du 15 octobre 2026 : périmètre et séquencement validés. Les hypothèses, propositions conditionnelles, paramètres à fixer et limites documentaires restent qualifiés comme tels dans le texte. |
| Prompt maître | Aucun numéro de version ni date interne. Référence de méthode fournie par l’utilisateur ; copie identifiée par son empreinte ci-dessous, sans lui attribuer une version inventée. |
| `AGENTS.md` | Adaptation des consignes du projet fournies par l’utilisateur : retrait du préambule décrivant le miroir local ChatGPT, ajout des liens de lecture et rappel de la licence existante. Les consignes métier et les limites d’autorisation sont conservées. |

Empreintes SHA-256 des copies importées :

```text
bf443e9ee30d5474d8044844724cc9aa66b63be0047179677a30a28bf5f92503  docs/references/MASTER_PROMPT_TRAINING_MANAGEMENT_MODULE.md
738834bd20869a343d2f808b08dfccf9b37b2b255fb3ab7bdacc2251fc218096  docs/references/Training_Management_Specification_Fonctionnelle_v2.md
```

Pour contrôler ces empreintes depuis la racine du dépôt :

```sh
shasum -a 256 docs/references/*.md
```

Ces empreintes identifient l’import initial, pas une nouvelle validation
fonctionnelle. Toute évolution approuvée passe par une issue et une PR qui
précisent la décision, les exigences affectées et la nouvelle référence ; conserver
la traçabilité de l’import et ajouter les informations de révision correspondantes.

## État du cadrage

- Phase 1 : socle MVP et P01 à P08, dont émargement électronique et reprise Odoo 19.
- Phase 2 : P09 à P16.
- P17 à P20 : hors phases 1 et 2 ; réalisation soumise à validation complémentaire explicite.
- La cible vérifiée est Odoo Community `20.0-20261015`, image épinglée et provenance décrites dans [la couverture native](native-coverage.md).
- Le socle S01 et le circuit commercial S02 sont livrés : [architecture S01](development-readiness.md), [étude native S02](s02-native-coverage.md) et [règles/recette S02](s02-crm-quotation.md). Les preuves sont propres à chaque incrément ; elles ne démontrent pas toute la spécification.
- S03 utilise un modèle dédié de réalisations, places et inscriptions, sans dépendance obligatoire à Événements, sur décision validée le 22 octobre 2026 ; [PR #46](https://github.com/Progideo/training_management/pull/46). Sa documentation précise les contrôles et limites de l’incrément.
- Surveys/Certification reste un candidat à démontrer pour les examens blancs, sans choix technique acquis.
- Les encaissements au lancement sont manuels après vérification bancaire ; relevés et imports bancaires reportés par décision du 22 octobre 2026 ([PR #45](https://github.com/Progideo/training_management/pull/45)).
- Les scénarios de recette décrits sont des attentes, pas des tests exécutés.
- Les réserves sur les références Odoo 19, Qualiopi et le niveau juridique de l’émargement sont conservées ; cette PR documentaire ne les vérifie ni ne les lève.

Le fichier historique `MASTER_PROMPT_AUDIT_ODOO_19_NEOPRO_ACADEMY.md` n’est pas
importé : l’audit est suspendu et ne constitue pas la mission active. La reprise
des données Odoo 19 demeure une exigence distincte du lancement.

## Revue de la PR #41 — 22 octobre 2026

Les cinq fichiers documentaires de #41 ne sont pas des doublons de `main` :
`AGENTS.md`, les deux références et leur index étaient absents. Ils sont conservés.
Le conflit du README est résolu en conservant les descriptions S01/S02 actuelles
et en ajoutant les liens de contribution ; les affirmations de cadrage devenues
obsolètes sont actualisées ici. Les deux références restent octet pour octet
identiques à l’import initial. Les décisions ultérieures sont consignées dans
les documents d’incrément et ne réécrivent pas silencieusement la spécification.

L’utilisateur a autorisé le traitement de #41 puis la fusion et le déploiement
S03 le 22 octobre 2026. Cette autorisation concerne la cible de développement
`neopro_dev` utilisée pour les incréments précédents ; la production et une
migration Odoo 19 restent hors de cette opération.

## Licence, publication et validations

La licence existante du dépôt reste **LGPL-3.0-only** ; consulter
[LICENSE](../LICENSE) et [COPYING](../COPYING). Les mentions de NeoPro Academy dans
la spécification décrivent le premier organisme utilisateur et ne justifient
aucune donnée d’entreprise codée en dur dans le module générique.

Le dépôt est public : ne publier aucun secret, donnée personnelle réelle, export
client ou sauvegarde de production. Les références importées décrivent le besoin ;
elles ne sont ni une preuve de compatibilité Odoo 20, ni une certification Qualiopi.

La validation des spécifications ne vaut pas autorisation de fusion, activation de
l’automatisation du Project, déploiement, intervention en production ou migration
réelle. Ces opérations conservent leurs validations explicites respectives.

## Recette documentaire courte

1. Ouvrir les liens depuis le README principal, cet index et `AGENTS.md`.
2. Vérifier les empreintes des références et, si les sources sont disponibles,
   comparer directement les fichiers aux originaux.
3. Vérifier le découpage des phases, les limites de couverture Community et la
   suspension de l’audit historique, sans changement des exigences importées.
4. Relire le diff de la PR : uniquement la documentation et les consignes ; aucun
   changement des licences, scripts ou workflows, aucune donnée de production.
