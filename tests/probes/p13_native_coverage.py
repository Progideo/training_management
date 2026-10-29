"""P13 architecture evidence; run in an isolated Odoo shell with Calendar installed.

Synthetic identities only. No transport is called; everything is rolled back.
This probe demonstrates native behavior, not an implemented booking service.
"""

import json
from unittest.mock import patch
from odoo import Command
from odoo.modules.module import get_module_path
from odoo.tests import new_test_user


def probe():
    organizer = new_test_user(
        env, login="p13_fictional_tutor", name="Fictional P13 Tutor", email="tutor@example.invalid"
    )
    learner = new_test_user(
        env,
        login="p13_fictional_learner",
        name="Fictional P13 Learner",
        groups="base.group_portal",
        email="learner@example.invalid",
    )
    peer = new_test_user(
        env,
        login="p13_fictional_peer",
        name="Fictional P13 Peer",
        groups="base.group_portal",
        email="peer@example.invalid",
    )
    event_model = (
        env["calendar.event"]
        .with_user(organizer)
        .with_context(no_mail_to_attendees=True, skip_contact_description=True, tracking_disable=True)
    )
    values = {
        "name": "Fictional P13 collective tutoring",
        "start": "2027-01-04 09:00:00",
        "stop": "2027-01-04 10:00:00",
        "user_id": organizer.id,
        "privacy": "private",
        "partner_ids": [Command.set((organizer.partner_id | learner.partner_id | peer.partner_id).ids)],
        "alarm_ids": [Command.clear()],
    }
    first = event_model.create(values)
    second = event_model.create(dict(values, name="Fictional P13 overlapping tutoring"))
    assert first.id != second.id and first.start == second.start and first.stop == second.stop
    # Test the actual restricted ORM read, not a sudo rendering assumption.
    visible = env["calendar.event"].with_user(learner).browse(first.id).read(["partner_ids"])[0]
    assert peer.partner_id in first.sudo().partner_ids
    assert visible["partner_ids"] == learner.partner_id.ids
    assert not event_model._fields.get("training_enrollment_id")
    assert not get_module_path("appointment", display_warning=False)
    print(
        "P13_NATIVE_COVERAGE "
        + json.dumps(
            {
                "two_overlapping_native_events_accepted": True,
                "private_event_masks_peer_partner_id_for_portal": True,
                "native_enrollment_quota_absent": True,
                "appointment_addon_absent": True,
            },
            sort_keys=True,
        )
    )


try:
    # Even an unexpected native invitation cannot reach a real transport.
    with patch.object(
        type(env["ir.mail_server"]), "send_email", side_effect=AssertionError("Transport forbidden in P13 probe")
    ) as transport:
        probe()
        assert not transport.called
        print("P13_NATIVE_NO_TRANSPORT_OK")
finally:
    env.cr.rollback()
