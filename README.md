# Training Management

Module de gestion de formations pour Odoo Community.

Version cible vérifiée pour le premier incrément : Odoo Community `20.0-20261015`.

## Périmètre

Ce dépôt contient exclusivement le code, les tests, la documentation et les workflows du module `training_management`.

Les besoins, anomalies et évolutions sont suivis dans GitHub Issues. Les modifications sont proposées et examinées par pull request.

## Références et contribution

Lire les [consignes du dépôt](AGENTS.md) et l’[index documentaire](docs/README.md)
avant toute contribution. L’index conserve les références validées, leur
provenance, leurs empreintes et les décisions d’architecture par incrément.
Le [backlog de référence — issue #3](https://github.com/Progideo/training_management/issues/3)
porte les besoins et leur avancement.

## Premier incrément

L'addon se trouve dans `addons/training_management/`. Il apporte la gestion
interne des formations standards et de leurs programmes versionnés, avec
validation, publication, retrait, droits coordinateur/lecteur et isolation
multi-sociétés. Les programmes standards sont destinés au futur catalogue
public ; la publication Web et les variantes privées par client restent à réaliser.

Consulter [l'architecture et la recette S01](docs/development-readiness.md)
et [les preuves et limites de couverture](docs/native-coverage.md).
L'ajout au chemin des addons utilise le dossier parent `addons/`.
Les tests natifs et la CI vérifient installation et mise à jour sur des bases
jetables. Aucune mise en production n'est autorisée par cette documentation.

## Circuit commercial S02

Le cadrage interne demande → devis → commande → facture → virement est validé.
Consulter [l’étude du standard exact, les écarts et la validation prévue](docs/s02-native-coverage.md).
Le premier incrément CRM → devis est décrit dans [sa procédure de recette](docs/s02-crm-quotation.md).
S02 est fusionné, avec encaissements manuels après vérification bancaire ; les relevés et imports bancaires restent reportés. Le [bilan #45](https://github.com/Progideo/training_management/pull/45#issuecomment-6340365735) précise la validation et le déploiement en développement.

## Réalisations et inscriptions S03

S03 ajoute les réalisations datées/autonomes, les lots de places, les inscriptions
nominatives et leurs autorisations/périodes d'accès, avec historique et contrôles
serveur. Consulter [la décision, les règles et la recette S03](docs/s03-enrollment-access.md).
Le modèle dédié est validé ; la PR S03 et sa validation sont suivies dans [#46](https://github.com/Progideo/training_management/pull/46). Aucun portail pédagogique,
PDF ou examen n'est ouvert par cet incrément. La fusion et le déploiement sur `neopro_dev` ont été autorisés le 22 octobre 2026 après traitement de #41 ; leurs résultats sont consignés dans la PR. La production reste hors de cette opération.

## Créateur

NeoPro Academy.

## Licence

Ce module est distribué sous licence GNU Lesser General Public License, version 3 uniquement (`LGPL-3.0-only`).

Les textes complets figurent dans les fichiers `LICENSE` et `COPYING`.
