def migrate(cr, version):
    # Existing immutable programmes keep their workflows, with no invented PDF.
    cr.execute("UPDATE training_program_version SET pdf_legacy = TRUE WHERE state != 'draft' AND pdf_sha256 IS NULL")
    # Native loading commits each upgraded module before its end migration.
    # Restore within this module's transaction, after all its XML is loaded.
    cr.execute("SELECT to_regclass('pg_temp.training_pdf_visibility_default_restore')")
    if cr.fetchone()[0]:
        cr.execute("ALTER TABLE ir_ui_view ALTER COLUMN visibility DROP DEFAULT")
        cr.execute("DROP TABLE pg_temp.training_pdf_visibility_default_restore")
