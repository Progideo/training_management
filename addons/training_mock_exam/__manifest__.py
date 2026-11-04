# pylint: disable=manifest-required-author,missing-readme  # project documentation lives in docs/
{
    "name": "Training Mock Exam Library",
    "summary": "Shared native Survey definitions and immutable mock exam versions",
    "version": "20.0.1.4.1",
    "category": "Services/Training",
    "author": "Training Management contributors",
    "website": "https://github.com/Progideo/training_management",
    "license": "LGPL-3",
    "depends": ["training_catalog", "survey"],
    "data": [
        "security/groups.xml",
        "security/ir.access.csv",
        "views/exam_views.xml",
        "data/cron.xml",
        "views/runner_templates.xml",
        "views/result_revision.xml",
    ],
    "assets": {
        "web.assets_frontend": ["training_mock_exam/static/src/exam.js", "training_mock_exam/static/src/enriched.js"]
    },
}
