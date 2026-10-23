def migrate(cr, version):
    # Native loading commits each upgraded module before its end migration.
    # Restore within this module's transaction, after all its XML is loaded.
    cr.execute("SELECT to_regclass('pg_temp.training_s05_visibility_default_restore')")
    if cr.fetchone()[0]:
        cr.execute("ALTER TABLE ir_ui_view ALTER COLUMN visibility DROP DEFAULT")
        cr.execute("DROP TABLE pg_temp.training_s05_visibility_default_restore")
