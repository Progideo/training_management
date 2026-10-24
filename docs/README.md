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

## Validation continue

Voir [CI Odoo : scénarios, couverture, diagnostic et mesures](ci.md).

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

## Incréments

| Incrément | Page |
| --- | --- |
| S01 — catalogue standard | [development-readiness.md](development-readiness.md), [native-coverage.md](native-coverage.md) |
| S02 — circuit commercial | [s02-native-coverage.md](s02-native-coverage.md), [s02-crm-quotation.md](s02-crm-quotation.md) |
| S03 — réalisations, places, inscriptions, accès | [s03-enrollment-access.md](s03-enrollment-access.md) |
| S03.1 — corrections de revue | [s03-1-review-fixes.md](s03-1-review-fixes.md), cadrage [s03-1-corrections.md](s03-1-corrections.md) |
| S04 — besoins, aménagements et séances | [s04-preparation-sessions.md](s04-preparation-sessions.md) |
| S02.1 — politique documentaire et protections natives | [s02-1-document-policy.md](s02-1-document-policy.md) |
| S05 — supports privés, activités, progression et tutorat | [s05-private-materials.md](s05-private-materials.md) |
| S06 — examens blancs, navigation et thèmes | [s06-mock-exams.md](s06-mock-exams.md) |
| S07 — présences et émargement | [s07-attendance.md](s07-attendance.md) |
| S08 — attestations, preuves et clôture | [s08-closure-documents.md](s08-closure-documents.md) |
| S09 — évaluations, retours et qualité (cadrage validé) | [s09-evaluations-quality.md](s09-evaluations-quality.md) |
| S09.1 — évaluations nominatives et droits | [s091-evaluations.md](s091-evaluations.md) |
| S09.2 — campagnes et retours | [s092-feedback.md](s092-feedback.md) |
| S09.3 — réclamations et amélioration continue | [s093-quality.md](s093-quality.md) |
| S09.4 — intervenants, sous-traitance et veille | [s094-intervenants-veille.md](s094-intervenants-veille.md) |
| S10 — tableau de suivi, indicateurs et notifications | [s10-operational-dashboard.md](s10-operational-dashboard.md) |
| Lot distinct — catégories et PDF du programme (cadrage validé) | [catalogue-categories-pdf.md](catalogue-categories-pdf.md) |

Chaque page reste simple et concise (voir [AGENTS.md](../AGENTS.md)) : elle porte les décisions, les règles et une recette courte ; les autorisations et
les résultats d'exécution restent dans les pull requests. Phases : 1 = socle MVP et P01 à P08 ;
2 = P09 à P16 ; P17 à P20 exigent une validation complémentaire explicite. La cible vérifiée est
Odoo Community `20.0-20261015` ([couverture native](native-coverage.md)). Les réserves sur les
références Odoo 19, Qualiopi et l'émargement sont conservées. L'audit historique
`MASTER_PROMPT_AUDIT_ODOO_19_NEOPRO_ACADEMY.md` n'est pas importé.

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
