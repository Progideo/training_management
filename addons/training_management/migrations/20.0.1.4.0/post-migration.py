def migrate(cr, version):
    # Existing immutable programmes keep their workflows, with no invented PDF.
    cr.execute("UPDATE training_program_version SET pdf_legacy = TRUE WHERE state != 'draft' AND pdf_sha256 IS NULL")
