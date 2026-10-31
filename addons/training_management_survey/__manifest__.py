# pylint: disable=manifest-required-author,missing-readme
{
    "name": "Training Management — Mock Exams",
    "summary": "Private versioned mock exams using native Odoo Surveys",
    "version": "20.0.2.8.0",
    "category": "Services/Training",
    "author": "Training Management contributors",
    "website": "https://github.com/Progideo/training_management",
    "license": "LGPL-3",
    "depends": ["training_management", "survey"],
    "data": [
        "security/groups.xml",
        "security/ir.access.csv",
        "views/exam_views.xml",
        "views/evaluation_views.xml",
        "views/feedback_views.xml",
        "views/exam_templates.xml",
        "views/orientation_views.xml",
        "views/orientation_templates.xml",
        "data/cron.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "training_management_survey/static/src/exam.js",
            "training_management_survey/static/src/feedback.js",
        ],
        "web.assets_unit_tests": [
            "training_management_survey/static/src/exam.js",
            "training_management_survey/static/tests/exam.test.js",
        ],
    },
}
