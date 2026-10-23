"""Run Odoo's own regression cases after the integration fields/rules are loaded.

Their original at_install timing precedes extensions on a module upgrade.
No standard test or framework code is copied or patched.
"""

from odoo.tests import tagged
from odoo.addons.survey.tests.test_survey import TestSurveyInternals as NativeInternals
from odoo.addons.survey.tests.test_survey_security import TestAccess as NativeAccess
from odoo.addons.survey.tests.test_survey_flow import TestSurveyFlow as NativeFlow
from odoo.addons.survey.tests.test_survey_results import TestSurveyResults as NativeResults
from odoo.addons.survey.tests.test_survey_security import TestSurveySecurityControllers as NativeControllers


@tagged("post_install", "-at_install")
class TestNativeInternals(NativeInternals):
    allow_inherited_tests_method = True
    """Unmodified native question, condition and scoring cases."""


@tagged("post_install", "-at_install")
class TestNativeAccess(NativeAccess):
    allow_inherited_tests_method = True
    """Unmodified native Survey roles and sharing cases."""


@tagged("post_install", "-at_install")
class TestNativeFlow(NativeFlow):
    allow_inherited_tests_method = True
    """Unmodified native survey HTTP flow."""


@tagged("post_install", "-at_install")
class TestNativeResults(NativeResults):
    allow_inherited_tests_method = True
    """Unmodified native result filtering cases."""


@tagged("post_install", "-at_install")
class TestNativeControllers(NativeControllers):
    allow_inherited_tests_method = True
    """Unmodified native private/public Survey routes."""
