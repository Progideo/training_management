"""A busy delivery must not roll back or starve unrelated inactivity reminders."""

from datetime import timedelta
from unittest.mock import patch

from odoo import api

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable S05 complement database only")
coordinator = env.ref("training_management_test.s052_coordinator")
participant = env.ref("training_management_test.s052_participant")
program = env.ref("training_management_test.s052_material").program_id
participant.partner_id.email = "r59-participant@example.invalid"
program.company_id.partner_id.email = "r59-sender@example.invalid"


def prepare(name):
    delivery = (
        env["training.delivery"]
        .with_user(coordinator)
        .create(
            {
                "name": name,
                "program_id": program.id,
                "kind": "autonomous",
                "access_policy": "duration",
                "access_days": 10,
                "learning_inactivity_days": 1,
                "learning_reminder_days": 1,
            }
        )
    )
    env["training.learning.activity"].with_user(coordinator).create(
        {
            "name": "Fictional required consultation",
            "delivery_id": delivery.id,
        }
    )
    enrollment = (
        env["training.enrollment"]
        .with_user(coordinator)
        .create(
            {
                "delivery_id": delivery.id,
                "participant_id": participant.partner_id.id,
                "user_id": participant.id,
                "free_reason": "Fictional reminder contention",
            }
        )
    )
    enrollment.action_validate_prerequisites(reason="Fictional review")
    enrollment.action_confirm()
    enrollment.action_authorize(reason="Fictional authorization")
    enrollment.action_open_access(reason="Fictional opening")
    return enrollment


first = prepare("Fictional busy delivery")
second = prepare("Fictional independent delivery")
ids = first.ids + second.ids
now = max(first.access_start, second.access_start) + timedelta(days=2, seconds=1)
env.cr.commit()  # Fictional fixtures in the explicitly guarded disposable database.
context = {"allowed_company_ids": program.company_id.ids}
with env.registry.cursor() as held, env.registry.cursor() as processing:
    busy = api.Environment(held, coordinator.id, context)["training.delivery"].browse(first.delivery_id.id)
    busy._serialize()
    cron_env = api.Environment(processing, coordinator.id, context)
    with patch("odoo.fields.Datetime.now", return_value=now):
        cron_env["training.learning.service"]._cron_reminders()
    notices = (
        cron_env["training.learning.notice"]
        .sudo()
        .search(
            [
                ("enrollment_id", "in", ids),
                ("entry_id", "=", False),
            ]
        )
    )
    assert notices.enrollment_id.ids == second.ids, "A busy delivery must not block an independent reminder"
    with patch("odoo.fields.Datetime.now", return_value=now):
        assert notices.mail_id and notices.mail_id._prepare_outgoing_list()
    processing.commit()
    held.rollback()

with env.registry.cursor() as retry:
    cron_env = api.Environment(retry, coordinator.id, context)
    with patch("odoo.fields.Datetime.now", return_value=now):
        cron_env["training.learning.service"]._cron_reminders()
        cron_env["training.learning.service"]._cron_reminders()
    notices = (
        cron_env["training.learning.notice"]
        .sudo()
        .search(
            [
                ("enrollment_id", "in", ids),
                ("entry_id", "=", False),
            ]
        )
    )
    assert len(notices) == 2
    assert set(notices.enrollment_id.ids) == set(ids)
    retry.commit()

# A cron snapshot may precede a committed change even though no lock is held now.
# It must leave that delivery for a fresh run and keep unrelated work.
now += timedelta(days=1)
with env.registry.cursor() as changed, env.registry.cursor() as stale:
    cron_env = api.Environment(stale, coordinator.id, context)
    cron_env["training.delivery"].browse(first.delivery_id.id).read(["revision"])
    api.Environment(changed, coordinator.id, context)["training.delivery"].browse(first.delivery_id.id)._serialize()
    changed.commit()
    with patch("odoo.fields.Datetime.now", return_value=now):
        cron_env["training.learning.service"]._cron_reminders()
    notices = (
        cron_env["training.learning.notice"]
        .sudo()
        .search(
            [
                ("enrollment_id", "in", ids),
                ("entry_id", "=", False),
            ]
        )
    )
    assert len(notices.filtered(lambda n: n.enrollment_id.id == first.id)) == 1
    assert len(notices.filtered(lambda n: n.enrollment_id.id == second.id)) == 2
    stale.commit()
with env.registry.cursor() as retry:
    cron_env = api.Environment(retry, coordinator.id, context)
    with patch("odoo.fields.Datetime.now", return_value=now):
        cron_env["training.learning.service"]._cron_reminders()
        cron_env["training.learning.service"]._cron_reminders()
    notices = (
        cron_env["training.learning.notice"]
        .sudo()
        .search(
            [
                ("enrollment_id", "in", ids),
                ("entry_id", "=", False),
            ]
        )
    )
    assert len(notices) == 4
    retry.commit()
print(
    "S052_REMINDER_CONCURRENCY_OK: busy/stale delivery skipped, independent reminder kept, fresh retry without duplicates"
)
