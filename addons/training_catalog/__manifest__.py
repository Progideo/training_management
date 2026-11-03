# pylint: disable=manifest-required-author,missing-readme  # not an OCA module; documentation is in docs/
{
    "name": "Training Catalogue",
    "summary": "Shared course identities without attendance or learner progression",
    "version": "20.0.1.0.0",
    "category": "Services/Training",
    "author": "Training Management contributors",
    "website": "https://github.com/Progideo/training_management",
    "license": "LGPL-3",
    "depends": ["base", "mail", "portal", "website"],
    "data": ["security/catalog_security.xml", "security/ir.access.csv", "views/catalog_views.xml"],
}
