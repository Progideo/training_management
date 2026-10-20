# Training Management

Module de gestion de formations pour Odoo Community.

Version cible vérifiée pour le premier incrément : Odoo Community `20.0-20261015`.

## Périmètre

Ce dépôt contient exclusivement le code, les tests, la documentation et les workflows du module `training_management`.

Les besoins, anomalies et évolutions sont suivis dans GitHub Issues. Les modifications sont proposées et examinées par pull request.

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
Cette première étude ne livre pas encore le code métier S02.

## Créateur

NeoPro Academy.

## Licence

Ce module est distribué sous licence GNU Lesser General Public License, version 3 uniquement (`LGPL-3.0-only`).

Les textes complets figurent dans les fichiers `LICENSE` et `COPYING`.
