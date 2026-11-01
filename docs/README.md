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

Voir également [les parcours et optimisations de la revue](review-experience-performance.md)
et [la navigation et les thèmes](usability-theme.md).

## Validation continue

Voir [CI Odoo : scénarios, couverture, diagnostic et mesures](ci.md) et
[les parcours navigateur exclusivement manuels](manual-browser.md).

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

## Révision du périmètre — 29 octobre 2026

[P15 est entièrement annulé](https://github.com/Progideo/training_management/issues/38).
Le périmètre courant de la phase 2 est P09 à P14 et P16, sans renumérotation.
Le catalogue, les demandes de devis et les parcours déjà livrés sont conservés.
Les consignes du dépôt et la copie de la spécification intègrent cette décision.
Le prompt maître reste la référence de méthode d’origine ; ses plages historiques
P09–P16 se lisent avec cette annulation. Les fichiers synchronisés sous `sources/`
ne sont pas modifiés : la divergence avec l’import d’origine est volontaire et tracée.

Les empreintes ci-dessus restent celles de l’import initial. Empreinte courante
SHA-256 de la spécification amendée (y compris P20, #105, l’émargement par demi-journée et les signatures, #111) :

```text
d03e565ec89e73981315234d148204b05c16fae979b94087fca81bfa3ce6cb6a  docs/references/Training_Management_Specification_Fonctionnelle_v2.md
```

## Incréments

| Incrément | Page |
| --- | --- |
| S01 — catalogue standard | [development-readiness.md](development-readiness.md), [native-coverage.md](native-coverage.md) |
| COM02/COM03 — règles natives, révision du 30 octobre 2026 | [native-commercial-accounting.md](native-commercial-accounting.md) |
| Complément — sept règles natives | [native-rules-followup.md](native-rules-followup.md) |
| S02 — circuit commercial historique | [s02-native-coverage.md](s02-native-coverage.md), [s02-crm-quotation.md](s02-crm-quotation.md) |
| S03 — réalisations, places, inscriptions, accès | [s03-enrollment-access.md](s03-enrollment-access.md) |
| S03.1 — corrections de revue | [s03-1-review-fixes.md](s03-1-review-fixes.md), cadrage [s03-1-corrections.md](s03-1-corrections.md) |
| S04 — besoins, aménagements et séances | [s04-preparation-sessions.md](s04-preparation-sessions.md) |
| S02.1 — politique documentaire et protections natives | [s02-1-document-policy.md](s02-1-document-policy.md) |
| S05 — supports privés, activités, progression et tutorat | [s05-private-materials.md](s05-private-materials.md) |
| S06 — examens blancs, navigation et thèmes | [s06-mock-exams.md](s06-mock-exams.md) |
| S07 — présences et émargement | [s07-attendance.md](s07-attendance.md), [tableau et signatures](s07-attendance-signatures.md) |
| S08 — attestations, preuves et clôture | [s08-closure-documents.md](s08-closure-documents.md) |
| S09 — évaluations, retours et qualité (cadrage validé) | [s09-evaluations-quality.md](s09-evaluations-quality.md) |
| S09.1 — évaluations nominatives et droits | [s091-evaluations.md](s091-evaluations.md) |
| S09.2 — campagnes et retours | [s092-feedback.md](s092-feedback.md) |
| S09.3 — réclamations et amélioration continue | [s093-quality.md](s093-quality.md) |
| S09.4 — intervenants, sous-traitance et veille | [s094-intervenants-veille.md](s094-intervenants-veille.md) |
| S10 — tableau de suivi, indicateurs et notifications | [s10-operational-dashboard.md](s10-operational-dashboard.md) |
| S11 — sécurité transversale, conservation et accès | [s11-security-audit.md](s11-security-audit.md) |
| P01–P06 — couverture et droits C02/C04 | [p01-p06-coverage.md](p01-p06-coverage.md) |
| P01–P02 — parcours et demande guidée | [p01-p02-guided-requests.md](p01-p02-guided-requests.md) |
| P03–P04 — catalogue public et aperçu | [p03-p04-public-catalogue.md](p03-p04-public-catalogue.md) |
| P05–P06 — portail entreprise et versions intra | [p05-p06-company-dossiers.md](p05-p06-company-dossiers.md) |
| P09.1 — composition et suivi interne des parcours | [p09-learning-paths.md](p09-learning-paths.md) |
| P09.2 — portail participant des parcours | [p09-participant-portal.md](p09-participant-portal.md) |
| P09.3 — commercialisation complète ou partielle | [p09-commercial-paths.md](p09-commercial-paths.md) |
| P10 — diagnostic d’orientation avant achat | [p10-orientation.md](p10-orientation.md) |
| P11 — plan de mise en pratique | [p11-practice-plans.md](p11-practice-plans.md) |
| P12 — projet pratique évalué | [p12-assessed-projects.md](p12-assessed-projects.md) |
| P13 — réservation de tutorat | [p13-tutoring-booking.md](p13-tutoring-booking.md) |
| P14 — avis vérifiés et cas clients | [p14-verified-reviews.md](p14-verified-reviews.md) |
| Corrections avant recette — accès et continuité | [review-access-continuity.md](review-access-continuity.md) |
| P20 — attestations vérifiables | [p20-verifiable-certificates.md](p20-verifiable-certificates.md) |
| P16 — préparation des statuts et alertes | [p16-session-status-alerts.md](p16-session-status-alerts.md) |
| C06 — paramètres natifs au déploiement | [c06-launch-settings.md](c06-launch-settings.md) |
| M01 — préparation de la reprise Odoo 19 | [m01-migration-preparation.md](m01-migration-preparation.md) |
| L01 — recette intégrée du module | [l01-launch-acceptance.md](l01-launch-acceptance.md) |
| Lot distinct — catégories et PDF du programme (cadrage validé) | [catalogue-categories-pdf.md](catalogue-categories-pdf.md) |

Chaque page reste simple et concise (voir [AGENTS.md](../AGENTS.md)) : elle porte les décisions, les règles et une recette courte ; les autorisations et
les résultats d'exécution restent dans les pull requests. Phases : 1 = socle MVP et P01 à P08 ;
2 = P09 à P14 et P16 (P15 annulé) ; P20 est autorisé (#105) ; P17–P19 et les autres évolutions sont reportés. La cible vérifiée est
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

## Révision commerciale et comptable — 30 octobre 2026

La [décision #102](native-commercial-accounting.md) remplace les contraintes
MAD/EUR et virement manuel dans le module générique. COM02/COM03 et les consignes
du dépôt sont amendées ; les documents S02 gardent leur provenance historique.
Les fichiers synchronisés `sources/` et le prompt maître importé restent inchangés ;
leurs prescriptions commerciales historiques se lisent avec cette décision plus récente.
