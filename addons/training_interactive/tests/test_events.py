"""The common validator accepts only bounded finite formative reports."""

from odoo.tests import TransactionCase, tagged
from ..services.events import encode_report, validate_result


@tagged("post_install", "-at_install")
class TestFormativeReports(TransactionCase):
    def test_finite_schema_and_h5p_whole_result(self):
        for score, maximum in (
            (True, 1),
            (1, False),
            (-1, 1),
            (2, 1),
            (10**400, 10**400),
            (float("nan"), 1),
            (1, float("inf")),
        ):
            with self.subTest(score=score, maximum=maximum), self.assertRaises(ValueError):
                validate_result({"score": score, "maximum": maximum, "completed": True}, "scorm12")
        with self.assertRaises(ValueError):
            validate_result({"score": 0.5, "maximum": 1, "completed": True}, "h5p")
        self.assertEqual(validate_result({"score": 1, "maximum": 1, "completed": True}, "h5p")["score"], 1)
        self.assertEqual(validate_result({"score": 75.5, "maximum": 100, "completed": False}, "scorm12")["score"], 75.5)

    def test_serialization_bound_and_nonfinite_nested_state(self):
        with self.assertRaises(ValueError):
            encode_report({"state": {"nested": [float("nan")]}})
        with self.assertRaises(ValueError):
            encode_report({"state": "a" * (128 * 1024)})
        self.assertEqual(encode_report({"b": 2, "a": 1}), '{"a":1,"b":2}')
