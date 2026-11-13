"""Run in an isolated tm_j1_* database only, before and after a same-generation update."""

import json

if not env.cr.dbname.startswith("tm_j1_"):
    raise RuntimeError("Only isolated J1 databases are allowed")


def normalized(value):
    return json.loads(json.dumps(value, default=str))


installed = env["ir.module.module"].search([("state", "=", "installed")]).mapped("name")
assert "sale_management" not in installed and "survey" not in installed
if "training.program.version" not in env:
    assert "training_management" not in installed
    assert not {"training_elearning", "training_management_elearning"} & set(installed)
print("J1_OPTIONAL_DEPENDENCIES_ABSENT")

params = env["ir.config_parameter"]
key = "training_catalog.j1_fixture"
snapshot = params.get_str(key)
if not snapshot:
    category = env["training.category"].create({"name": "Fictional J1 category"})
    course = env["training.course"].create(
        {
            "name": "Fictional J1 course",
            "category_id": category.id,
            "presentation": "Preserved general presentation",
            "general_objectives": "Preserved objectives",
        }
    )
    data = {
        "course": course.id,
        "category": category.id,
        "course_values": course.read(["name", "category_id", "company_id", "presentation", "general_objectives"]),
        "category_values": category.read(["name", "company_id"]),
    }
    if "training.program.version" in env:
        program = env["training.program.version"].create(
            {
                "course_id": course.id,
                "version": "J1",
                "title": "Fictional J1 programme",
            }
        )
        data.update(program=program.id, program_values=program.read(["course_id", "version", "title", "state"]))
    params.set_str(key, json.dumps(data, default=str))
    # Deliberate fixture commit: the update is a separate Odoo process.
    env.cr.commit()
    print("J1_FIXTURE_PREPARED")
else:
    data = json.loads(snapshot)
    course = env["training.course"].browse(data["course"]).exists()
    assert (
        normalized(course.read(["name", "category_id", "company_id", "presentation", "general_objectives"]))
        == data["course_values"]
    )
    assert (
        normalized(env["training.category"].browse(data["category"]).read(["name", "company_id"]))
        == data["category_values"]
    )
    if data.get("program"):
        assert (
            normalized(
                env["training.program.version"].browse(data["program"]).read(["course_id", "version", "title", "state"])
            )
            == data["program_values"]
        )
    print("J1_IDENTITIES_TEXT_AND_RELATIONS_PRESERVED")
