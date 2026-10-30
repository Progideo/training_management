"""Release the old form inheritance before its parent moves the work form."""


def migrate(cr, version):
    # The module data reloads this owned view with the remaining activity/history
    # extensions. Its old form XPaths would reject the parent update beforehand.
    cr.execute(
        """
        UPDATE ir_ui_view
           SET arch_db = jsonb_build_object('en_US', '<data/>')
         WHERE id IN (
             SELECT res_id FROM ir_model_data
              WHERE module = 'training_management'
                AND name = 'portal_project_content'
                AND model = 'ir.ui.view'
         )
        """
    )
