"""P12 rubrics extend S05 work and S09 authorizations; no second progress ledger."""

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain
from odoo.tools import SQL

from .training_evaluation import clean_context
from .training_material import COORDINATOR


def project_levels(env):
    return [
        ("0", env._("Non acquis")),
        ("1", env._("En cours d’acquisition")),
        ("2", env._("Acquis")),
        ("3", env._("Maîtrisé")),
    ]


class ProjectRubric(models.Model):
    _name = "training.project.rubric"
    _description = "Grille de projet pratique"
    _check_company_auto = True

    name = fields.Char(required=True, string="Nom")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, string="Société exploitante"
    )
    previous_id = fields.Many2one(
        "training.project.rubric", ondelete="restrict", check_company=True, copy=False, string="Version précédente"
    )
    state = fields.Selection(
        [("draft", "Brouillon"), ("published", "Publiée")], default="draft", required=True, copy=False, string="État"
    )
    criterion_ids = fields.One2many("training.project.criterion", "rubric_id", copy=True, string="Critères")

    @api.private
    def _editable(self):
        if not self.env.user.active or not self.env.user.has_group(COORDINATOR):
            raise AccessError(self.env._("La coordination de formation est requise."))
        self.check_access("write")
        self.lock_for_update()
        if self:
            # Child edits and publication share this parent fence. A stale
            # REPEATABLE READ snapshot must retry after a criterion edit/delete,
            # even once its lock is released. Preserve all business metadata.
            self.env.cr.execute(
                SQL("UPDATE training_project_rubric SET write_date = write_date WHERE id IN %s", tuple(self.ids))
            )
        self.invalidate_recordset()
        if any(row.state != "draft" for row in self):
            raise ValidationError(self.env._("Conservez la grille publiée ; créez une nouvelle version."))

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.user.active or not self.env.user.has_group(COORDINATOR):
            raise AccessError(self.env._("La coordination de formation est requise."))
        if any(v.get("state", "draft") != "draft" for v in vals_list):
            raise ValidationError(self.env._("Publiez la grille depuis son formulaire."))
        return super(ProjectRubric, clean_context(self)).create(vals_list)

    def write(self, vals):
        self._editable()
        if "state" in vals:
            raise ValidationError(self.env._("Publiez la grille depuis son formulaire."))
        return super().write(vals)

    def action_publish(self):
        self._editable()
        if any(not row.criterion_ids for row in self):
            raise ValidationError(self.env._("Ajoutez au moins un critère et ses niveaux de maîtrise."))
        return super().write({"state": "published"})  # pylint: disable=super-method-mismatch  # publication alone may change state

    def action_new_version(self):
        self.ensure_one()
        self.check_access("read")
        version = self.copy({"previous_id": self.id})
        return {"type": "ir.actions.act_window", "res_model": self._name, "res_id": version.id, "view_mode": "form"}

    @api.ondelete(at_uninstall=False)
    def _keep_rubric(self):
        self._editable()

    @api.private
    def _snapshot(self):
        self.ensure_one()
        return {
            "id": self.id,
            "name": self.name,
            "level_labels": [label for _value, label in project_levels(self.env)],
            "criteria": [
                {"id": c.id, "name": c.name, "levels": [c.level_0, c.level_1, c.level_2, c.level_3]}
                for c in self.criterion_ids.sorted(lambda c: (c.sequence, c.id))
            ],
        }


class ProjectCriterion(models.Model):
    _name = "training.project.criterion"
    _description = "Critère du projet pratique"
    _order = "sequence, id"
    _check_company_auto = True

    rubric_id = fields.Many2one("training.project.rubric", required=True, ondelete="cascade", check_company=True)
    company_id = fields.Many2one(related="rubric_id.company_id", store=True)
    sequence = fields.Integer(default=10, string="Ordre")
    name = fields.Char(required=True, string="Critère")
    level_0 = fields.Text(required=True, string="Non acquis")
    level_1 = fields.Text(required=True, string="En cours d’acquisition")
    level_2 = fields.Text(required=True, string="Acquis")
    level_3 = fields.Text(required=True, string="Maîtrisé")

    @api.model_create_multi
    def create(self, vals_list):
        self.env["training.project.rubric"].browse([v.get("rubric_id") for v in vals_list])._editable()
        return super(ProjectCriterion, clean_context(self)).create(vals_list)

    def write(self, vals):
        self.rubric_id._editable()
        if "rubric_id" in vals:
            self.env["training.project.rubric"].browse(vals["rubric_id"])._editable()
        return super().write(vals)

    @api.constrains("name", "level_0", "level_1", "level_2", "level_3")
    def _check_text(self):
        if any(
            not row[field].strip() for row in self for field in ("name", "level_0", "level_1", "level_2", "level_3")
        ):
            raise ValidationError(self.env._("Décrivez chaque critère et ses quatre niveaux de maîtrise."))

    @api.ondelete(at_uninstall=False)
    def _keep_published(self):
        self.rubric_id._editable()


class ProjectActivity(models.Model):
    _inherit = "training.learning.activity"

    project_rubric_id = fields.Many2one(
        "training.project.rubric", ondelete="restrict", check_company=True, string="Grille du projet"
    )
    project_deliverable = fields.Text(string="Livrable attendu")
    project_service_reference = fields.Char(string="Référence de prestation")
    project_retention_id = fields.Many2one(
        "training.retention.category", ondelete="restrict", check_company=True, string="Conservation du projet"
    )

    @api.onchange("project_rubric_id")
    def _onchange_project_rubric(self):
        if self.project_rubric_id:
            self.criterion = "validation"

    @api.constrains(
        "project_rubric_id", "project_deliverable", "project_service_reference", "project_retention_id", "criterion"
    )
    def _check_project(self):
        for row in self.filtered("project_rubric_id"):
            if (
                row.criterion != "validation"
                or row.project_rubric_id.state != "published"
                or not (row.project_deliverable or "").strip()
                or not (row.project_service_reference or "").strip()
                or not row.project_retention_id.approved_at
            ):
                raise ValidationError(
                    self.env._(
                        "Un projet exige une grille publiée, un livrable, une prestation, une politique approuvée et le critère Validation du tuteur."
                    )
                )


class ProjectAuthorization(models.Model):
    _inherit = "training.evaluation.authorization"

    purpose = fields.Selection(selection_add=[("project", "Projet pratique")], ondelete={"project": "cascade"})


class ProjectEntry(models.Model):
    _inherit = "training.learning.entry"

    project_snapshot = fields.Json(readonly=True, copy=False, string="Grille et évaluation conservées")
    project_digest = fields.Char(readonly=True, copy=False)

    def _access_domain(self, operation):
        domain = super()._access_domain(operation)
        if operation == "read":
            domain &= self.env["training.learning.service"]._project_entry_domain()
        return domain


class ProjectLearningService(models.AbstractModel):
    _inherit = "training.learning.service"  # pylint: disable=consider-merging-classes-inherited  # P12 qualifications are separate from S08 closure issuance

    @api.private
    def _project_evaluator(self, enrollment):
        user = self.env.user
        now = fields.Datetime.now()
        return bool(
            self._is_tutor(enrollment)
            and user != enrollment.user_id
            and self.env["training.evaluation.service"]._teaching_mission(enrollment.delivery_id)
            and self.env["training.evaluation.authorization"]
            .sudo()
            .search_count(
                [
                    ("delivery_id", "=", enrollment.delivery_id.id),
                    ("user_id", "=", user.id),
                    ("purpose", "=", "project"),
                    ("active", "=", True),
                    ("valid_from", "<=", now),
                    ("valid_until", ">=", now),
                ],
                limit=1,
            )
        )

    @api.private
    def _project_can_read(self, enrollment):
        return self._is_participant(enrollment) or self._project_evaluator(enrollment)

    @api.private
    def _project_entry_domain(self):
        enrollments = self.env["training.document.policy"]._enrollments() | self._tutored_enrollments()
        allowed = enrollments.filtered(self._project_can_read)
        # Match absent activities too (S05 private help). The classifier reads
        # only the project marker, independently of coordinator-only activity
        # rules; the enclosing S05 enrollment domain still enforces the mission.
        ordinary = Domain("activity_id", "not any!", Domain("project_rubric_id", "!=", False))
        return ordinary | Domain("enrollment_id", "in", allowed.ids)

    @api.private
    def _project_snapshot(self, enrollment, activity, kind, ratings, body):
        if not activity.project_rubric_id:
            return False
        if kind not in ("submission", "correction"):
            raise ValidationError(self.env._("Utilisez une remise ou une évaluation pour ce projet."))
        if kind == "correction" and not self._project_evaluator(enrollment):
            raise AccessError(self.env._("Une mission et une habilitation de projet en cours sont requises."))
        if not self._project_can_read(enrollment):
            raise AccessError(self.env._("Ce projet privé est indisponible."))
        grid = activity.project_rubric_id._snapshot()
        if kind == "correction":
            expected = {str(c["id"]) for c in grid["criteria"]}
            if (
                not isinstance(ratings, dict)
                or set(ratings) != expected
                or any(v not in dict(project_levels(self.env)) for v in ratings.values())
                or not body.strip()
            ):
                raise ValidationError(self.env._("Renseignez un niveau pour chaque critère et un retour motivé."))
        return {
            "rubric": grid,
            "ratings": ratings if kind == "correction" else {},
            "deliverable": activity.project_deliverable,
            "service": activity.project_service_reference,
            "retention": activity.project_retention_id.id,
        }

    @api.private
    def _rows(self, enrollment):
        rows = super()._rows(enrollment)
        for row in rows:
            activity = self.env["training.learning.activity"].sudo().browse(row["id"])
            project = activity.project_rubric_id
            row.update(
                project=bool(project),
                project_allowed=not project or self._project_can_read(enrollment),
                project_grid=project._snapshot() if project else False,
                project_deliverable=activity.project_deliverable,
                project_levels=project_levels(self.env),
            )
            if project and not row["project_allowed"]:
                row.update(complete=False, state="pending", revision=0, latest_submission=False)
        return rows

    @api.private
    def _certificate_origin(self, enrollment, activity):
        origin = super()._certificate_origin(enrollment, activity)
        if activity.project_rubric_id:
            origin["project_rubric"] = activity.project_rubric_id.id
            # Trace the exact immutable decision without exposing private feedback.
            entry = self.env["training.learning.entry"].sudo().browse(origin.get("correction"))
            origin["project_digest"] = entry.project_digest
        return origin


class ProjectDocumentPolicy(models.AbstractModel):
    _inherit = "training.document.policy"  # pylint: disable=consider-merging-classes-inherited  # project grants differ from S08 closure grants

    @api.private
    def _can_read(self, record):
        document = self._document(record)
        if document._name == "training.learning.entry" and document.sudo().activity_id.project_rubric_id:
            return self.env["training.learning.service"]._project_can_read(document.sudo().enrollment_id)
        return super()._can_read(record)
