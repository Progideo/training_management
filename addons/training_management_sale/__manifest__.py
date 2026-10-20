{
    "name": "Training Management - Sales",
    "summary": "Qualify training requests and price programme quotations in MAD or EUR",
    "version": "20.0.1.1.0",
    "category": "Services/Training",
    "author": "Training Management contributors",
    "website": "https://github.com/Progideo/training_management",
    "license": "LGPL-3",
    "depends": ["training_management", "sale_management", "sale_crm"],
    "data": [
        "security/ir.access.csv",
        "views/crm_lead_views.xml",
        "views/product_template_views.xml",
        "views/sale_order_views.xml",
        "report/sale_report_templates.xml",
    ],
    "installable": True,
}
