"""Offline technical relocation, executed with the OLD registry using ``odoo shell``.

Stop HTTP/cron/workers and back up database AND filestore before executing this
file. No business rows, attachment bytes, model names or table names are moved.
The caller must explicitly commit after this script has completed successfully.
Switch to the new source tree only after committing; update the renamed addon
and training_catalog before restarting any service. See docs/j15-module-layout.md.
"""


def relocate_modules(env):
    if not env.su:
        raise RuntimeError("Run through the offline administrator shell")
    cr = env.cr
    old = "training_management_elearning"
    new = "training_management_interactive"
    with cr.savepoint():
        cr.execute("SELECT id, name, state FROM ir_module_module WHERE name IN %s FOR UPDATE", [(old, new)])
        modules = {name: (identifier, state) for identifier, name, state in cr.fetchall()}
        if old in modules and modules[old][1] == "installed":
            if new in modules:
                raise RuntimeError("Target module metadata already exists; restore the pre-switch backup")
            if modules[old][1] != "installed":
                raise RuntimeError("The old adapter must be installed, without a pending module operation")
            cr.execute("UPDATE ir_module_module SET name=%s WHERE id=%s", (new, modules[old][0]))
            cr.execute("UPDATE ir_module_module_dependency SET name=%s WHERE name=%s", (new, old))
            cr.execute("UPDATE ir_model_data SET module=%s WHERE module=%s", (new, old))
            cr.execute(
                "UPDATE ir_model_data SET name=%s WHERE module='base' AND name=%s",
                ("module_" + new, "module_" + old),
            )
            # These fields contain technical XML/template/static names, never
            # learner answers. Keep every translation and every record identity.
            cr.execute(
                "UPDATE ir_ui_view SET key=replace(key,%s,%s) WHERE key LIKE %s",
                (old + ".", new + ".", old + ".%"),
            )
            cr.execute(
                "UPDATE ir_ui_view SET arch_db=replace(arch_db::text,%s,%s)::jsonb WHERE arch_db::text LIKE %s",
                (old + ".", new + ".", "%" + old + ".%"),
            )
            cr.execute(
                "UPDATE ir_asset SET path=replace(path,%s,%s) WHERE path LIKE %s",
                (old + "/static/", new + "/static/", "%" + old + "/static/%"),
            )
        elif old in modules:
            if modules[old][1] not in ("uninstalled", "uninstallable"):
                raise RuntimeError("Finish or cancel the pending old adapter operation")
            cr.execute("SELECT name FROM ir_model_data WHERE module=%s LIMIT 1", (old,))
            if cr.fetchone():
                raise RuntimeError("The inactive old adapter still owns data; inspect before relocating")
            # A never-installed old app may still have a discovered metadata
            # row. It must not block the independent fresh target installation.
            cr.execute(
                "UPDATE ir_module_module SET state='uninstallable', auto_install=false WHERE id=%s", (modules[old][0],)
            )
        if new in modules and modules[new][1] not in ("installed", "uninstalled"):
            raise RuntimeError("The relocated adapter has an unexpected state")

        old_menu_module = "training_management_website"
        cr.execute("SELECT id, state FROM ir_module_module WHERE name=%s FOR UPDATE", (old_menu_module,))
        row = cr.fetchone()
        if row and row[1] in ("to remove", "to upgrade"):
            raise RuntimeError("Finish or cancel the pending website module operation before relocation")
        if row:
            cr.execute(
                "SELECT d.name FROM ir_module_module_dependency d JOIN ir_module_module m ON m.id=d.module_id "
                "WHERE d.name=%s AND m.state IN ('installed','to install','to upgrade')",
                (old_menu_module,),
            )
            if cr.fetchall():
                raise RuntimeError("An installed extension still depends on the retired website addon")
            cr.execute("SELECT name FROM ir_model_data WHERE module=%s", (old_menu_module,))
            if {name for (name,) in cr.fetchall()} - {"menu_training_catalogue"}:
                raise RuntimeError("Unexpected data in the retired website addon")
            cr.execute(
                "UPDATE ir_model_data SET module='training_catalog' WHERE module=%s",
                (old_menu_module,),
            )
            # Do not invoke uninstall: it would delete the editable native menu.
            # Missing source alone does not clear the old auto-install flag.
            # Keep the technical history, but prevent an orphan reinstall.
            cr.execute("UPDATE ir_module_module SET state='uninstallable', auto_install=false WHERE id=%s", (row[0],))
        env.invalidate_all()
    print("TM_MODULE_RELOCATION_PREPARED_NO_BUSINESS_CONVERSION")


relocate_modules(env)  # noqa: F821 -- provided by the offline Odoo shell
