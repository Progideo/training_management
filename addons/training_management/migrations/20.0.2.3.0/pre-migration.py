"""Bridge Website's required ORM default during the partial upgrade registry.

In Community 20.0-20261015 Website is loaded after Training Management. Its
required visibility column already exists, but its ORM default is not registered
when our new views are inserted. Supply that exact native default only for this
module upgrade transaction; post-migration restores the absence of SQL default
before the native loader commits this module.
No view, existing visibility value or NOT NULL constraint is modified.
"""


def migrate(cr, version):
    cr.execute(
        """SELECT a.attnotnull, pg_get_expr(d.adbin, d.adrelid)
             FROM pg_attribute a
        LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
            WHERE a.attrelid = 'ir_ui_view'::regclass
              AND a.attname = 'visibility' AND NOT a.attisdropped"""
    )
    column = cr.fetchone()
    if column and column[0] and column[1] is None:
        cr.execute("CREATE TEMP TABLE training_s10_visibility_default_restore (id integer) ON COMMIT DROP")
        cr.execute("ALTER TABLE ir_ui_view ALTER COLUMN visibility SET DEFAULT 'public'")
