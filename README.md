# Training Management

Module de gestion de formations pour Odoo Community `20.0-20261015`.
Il est livré par incréments (S01 catalogue, S02 circuit commercial, S03 réalisations
et inscriptions, S03.1 corrections de revue) ; le détail est dans l'[index documentaire](docs/README.md).

## Installation

Ajouter le dossier `addons/` au chemin des addons Odoo, puis installer
`training_management` (dépend de `base` et `mail`) et, pour le circuit commercial,
`training_management_sale` (dépend des Ventes et du CRM). Données de test fictives
uniquement. Les tests et la CI installent et mettent à jour des bases jetables.

## Contribution

Lire les [consignes du dépôt](AGENTS.md) et l'[index documentaire](docs/README.md).
Les besoins sont suivis dans les issues, notamment le
[backlog #3](https://github.com/Progideo/training_management/issues/3) ; les changements
et leurs validations dans les pull requests. Avant de pousser : `pre-commit run --all-files`
([CI](docs/ci.md)).

## Créateur et licence

NeoPro Academy. Licence GNU Lesser General Public License, version 3 uniquement
(`LGPL-3.0-only`) : voir `LICENSE` et `COPYING`.
