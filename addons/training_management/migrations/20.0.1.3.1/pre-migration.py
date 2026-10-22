"""Number existing dispatches without changing their messages or snapshots."""


def migrate(cr, version):
    # A S03 -> S04 update has no invitation table yet. A S04 review database
    # does: backfill before the ORM replaces the old fingerprint constraint.
    cr.execute("SELECT to_regclass('training_invitation')")
    if not cr.fetchone()[0]:
        return
    cr.execute("ALTER TABLE training_invitation ADD COLUMN IF NOT EXISTS dispatch_number integer")
    cr.execute(
        """
        UPDATE training_invitation AS invitation
           SET dispatch_number = numbered.dispatch_number
          FROM (SELECT id, row_number() OVER (PARTITION BY session_id, partner_id ORDER BY id) AS dispatch_number
                  FROM training_invitation) AS numbered
         WHERE invitation.id = numbered.id
        """
    )
