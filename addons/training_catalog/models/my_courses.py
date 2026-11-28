"""« My courses » contributions shared by the training modules.

Training Management renders the page; an autonomous module (eLearning) adds its
courses here without depending on Training Management.
"""

from odoo import api, models


class TrainingMyCourses(models.AbstractModel):
    _name = "training.my.courses"
    _description = "My Courses Contributions"

    @api.private
    def _has_courses(self):
        """Whether a contributing module has a course for the current user."""
        return False

    @api.private
    def _online_rows(self):
        """Autonomous courses of the current user, already authorized.

        Row keys: ``label``, ``ongoing``, ``name``, ``detail``, ``progress`` (int or False),
        ``url``, ``button`` and ``sort``.
        """
        return []

    @api.private
    def _online_url(self):
        """Page listing every autonomous course, or False."""
        return False

    @api.private
    def _todo(self):
        """Actions of contributing modules, with the keys of « To do now » items."""
        return []
