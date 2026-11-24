# pylint: disable=manifest-required-author,missing-readme  # project documentation lives in docs/
{
    "name": "Training Gamification",
    "summary": "Optional points for training engagement, credited as native karma",
    "version": "20.0.1.0.0",
    "category": "Services/Training",
    "author": "Training Management contributors",
    "website": "https://github.com/Progideo/training_management",
    "license": "LGPL-3",
    "depends": ["training_management", "gamification"],
    "data": [
        "security/ir.access.csv",
        "data/cron.xml",
        "views/gamification_views.xml",
        "views/portal_templates.xml",
        "views/challenge_views.xml",
    ],
}
