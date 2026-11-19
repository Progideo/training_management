"""Retire the guaranteed departure: "Session confirmée" is the single public commitment."""

import logging

from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if column_exists(cr, "training_delivery", "session_guaranteed"):
        # The column is dropped with the field at the end of the upgrade. Past
        # decisions remain in the S03 operation journal of each delivery.
        cr.execute("SELECT count(*) FROM training_delivery WHERE session_guaranteed")
        _logger.info("Retiring guaranteed departure; %s deliveries held it", cr.fetchone()[0])
    # The module data reloads this owned view without the field. Its old arch
    # would otherwise reject the parent delivery form updated beforehand.
    cr.execute(
        """
        UPDATE ir_ui_view
           SET arch_db = jsonb_build_object('en_US', '<data/>')
         WHERE id IN (
             SELECT res_id FROM ir_model_data
              WHERE module = 'training_management'
                AND name = 'view_delivery_public_session'
                AND model = 'ir.ui.view'
         )
        """
    )
