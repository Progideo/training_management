"""Reconcile separation branches which still carried the retired attendance windows."""

import logging

from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # An upgrade from before these columns has nothing to remove.
    if not column_exists(cr, "training_session", "attendance_before"):
        return
    cr.execute(
        """
        SELECT count(*) FROM training_session
         WHERE COALESCE(attendance_before, 0) <> 0 OR COALESCE(attendance_after, 30) <> 30
        """
    )
    _logger.info("Removing unused attendance windows; %s sessions held a non-default value", cr.fetchone()[0])
    # The module data reloads these owned views without the fields. Their old
    # arch would otherwise reject the parent forms updated beforehand.
    cr.execute(
        """
        UPDATE ir_ui_view
           SET arch_db = jsonb_build_object('en_US', '<data/>')
         WHERE id IN (
             SELECT res_id FROM ir_model_data
              WHERE module = 'training_management'
                AND name IN ('view_session_attendance', 'view_session_edit_attendance')
                AND model = 'ir.ui.view'
         )
        """
    )
