# pylint: disable=manifest-required-author,missing-readme  # not an OCA module; documentation is in docs/
{
    "name": "Training Catalogue",
    "summary": "Shared course identities without attendance or learner progression",
    "version": "20.0.1.12.0",
    "category": "Services/Training",
    "author": "Training Management contributors",
    "website": "https://github.com/Progideo/training_management",
    "license": "LGPL-3",
    "depends": ["base", "mail", "portal", "rating", "website"],
    "assets": {
        "web.assets_frontend": [
            "training_catalog/static/src/course_share.js",
            "training_catalog/static/src/course_share.xml",
            "training_catalog/static/src/catalogue.scss",
        ],
    },
    "data": [
        "security/catalog_security.xml",
        "security/ir.access.csv",
        "views/catalog_views.xml",
        "views/website_menu.xml",
        "views/public_catalogue.xml",
        "views/rating_rating_views.xml",
        "views/res_company_views.xml",
        "data/course_review_activity.xml",
    ],
}
