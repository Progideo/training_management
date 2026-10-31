# Training Management

Module de gestion de formations pour Odoo Community `20.0-20261015`.
Il couvre le catalogue, les inscriptions, les parcours pédagogiques, les présences,
les attestations et le suivi qualité, avec des espaces internes et portail.
Le socle, P01 à P14, P16 et P20 sont livrés ; P15 est annulé et P17 à P19 restent
reportés. Le détail et les décisions sont dans l'[index documentaire](docs/README.md).

## Installation

Ajouter le dossier `addons/` au chemin des addons Odoo, puis installer
`training_management` et les intégrations nécessaires. Dépendances directes des manifests :

| Addon | Usage | Dépendances |
| --- | --- | --- |
| `training_management` | Socle et portail de formation | `base`, `mail`, `resource`, `portal`, `web`, `base_report_wkhtmltox` |
| `training_management_sale` | Ventes et CRM | `training_management`, `sale_management`, `sale_crm` |
| `training_management_survey` | Examens blancs et questionnaires natifs | `training_management`, `survey` |
| `training_management_website` | Menu du catalogue dans Website | `training_management`, `website` |
| `sale_invoice_address_fiscal` | Option fiscale indépendante, selon l’adresse de facturation | `sale_management` |

Le pont Website s’installe automatiquement avec le socle et Website ; Website
reste facultatif. Voir [navigation et thèmes](docs/usability-theme.md).
L’option fiscale s’installe séparément et n’est requise par aucun addon de formation.

## Validation du module

La [recette de livraison L01](docs/l01-launch-acceptance.md) est clôturée dans
[#31](https://github.com/Progideo/training_management/issues/31). Les tests techniques,
la recette humaine et les conditions d’exploitation constituent des preuves
distinctes. Les réserves humaines restantes sont explicites dans L01 ; sa clôture
ne vaut ni validation universelle de compatibilité ni autorisation de production.
Les tests et la [CI](docs/ci.md) utilisent des données fictives et des bases jetables.

## Périmètre du module

Training Management est générique et indépendant de NeoPro Academy. Son installation
vise tout environnement compatible avec Odoo 20 Community, quel que soit le pays.
Les données de l’organisme et les localisations se configurent dans Odoo ; elles
ne sont pas fournies comme paramètres obligatoires propres à NeoPro.

La production, l’hébergement, les sauvegardes opérationnelles et les dossiers
réglementaires locaux (dont la CNDP) relèvent de l’exploitation de chaque organisme,
gérée hors de ce projet. La sécurité et les tests du module restent dans ce dépôt.
Les preuves de compatibilité effectivement exécutées figurent dans la CI ; cette
séparation ne constitue pas une validation de tous les environnements possibles.

## Contribution

Lire les [consignes du dépôt](AGENTS.md) et l'[index documentaire](docs/README.md).
Les besoins sont suivis dans les issues, notamment le
[backlog #3](https://github.com/Progideo/training_management/issues/3) ; les changements
et leurs validations dans les pull requests. Avant de pousser : `pre-commit run --all-files`
([CI](docs/ci.md)).

## Créateur et licence

NeoPro Academy. Licence GNU Lesser General Public License, version 3 uniquement
(`LGPL-3.0-only`) : voir `LICENSE` et `COPYING`.
