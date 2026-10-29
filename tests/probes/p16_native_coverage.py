"""Exact Community Event and Mailing facts; synthetic data, no transport, rollback."""

from datetime import timedelta
import json
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import ValidationError


def probe():
    assert env.cr.dbname == "tm_suite_test", "Disposable suite database required"
    start = fields.Datetime.now() + timedelta(days=10)
    event = env["event.event"].create(
        {
            "name": "Fictional P16 native event",
            "date_begin": start,
            "date_end": start + timedelta(hours=2),
            "date_tz": "Europe/Paris",
            "seats_limited": True,
            "seats_max": 1,
        }
    )
    assert not event.is_published and event.event_registrations_open
    draft = env["event.registration"].create({"event_id": event.id, "name": "Fictional pending", "state": "draft"})
    assert event.seats_available == 1
    draft.write({"state": "open"})
    assert event.seats_available == 0 and event.event_registrations_sold_out
    try:
        with env.cr.savepoint():
            env["event.registration"].create({"event_id": event.id, "name": "Fictional over capacity", "state": "open"})
    except ValidationError:
        pass
    else:
        raise AssertionError("Expected sequential over-capacity rejection")
    draft.write({"state": "cancel"})
    assert event.seats_available == 1
    assert "training_seat_allocation_ids" not in event._fields
    mailing_list = env["mailing.list"].create({"name": "Fictional P16 date alerts"})
    partner = env["res.partner"].create({"name": "Fictional P16 partner", "email": "p16@example.invalid"})
    contact = env["mailing.contact"].create({"name": "Fictional P16 mailing contact", "email": partner.email})
    assert not contact.partner_id
    subscription = env["mailing.subscription"].create({"contact_id": contact.id, "list_id": mailing_list.id})
    subscription.write({"opt_out": True})
    assert subscription.opt_out and subscription.opt_out_datetime
    assert (
        env["mailing.subscription"].search_count([("contact_id", "=", contact.id), ("list_id", "=", mailing_list.id)])
        == 1
    )
    print(
        "P16_NATIVE_COVERAGE "
        + json.dumps(
            {
                "event_private_by_default": True,
                "draft_does_not_occupy_event_capacity": True,
                "registered_occupies_event_capacity": True,
                "sequential_excess_rejected": True,
                "cancel_releases_event_capacity": True,
                "mailing_contact_can_be_separate_from_partner": True,
                "native_list_opt_out_timestamp": True,
            },
            sort_keys=True,
        )
    )


try:
    with patch.object(
        type(env["ir.mail_server"]), "send_email", side_effect=AssertionError("Transport forbidden in P16 probe")
    ) as transport:
        probe()
        assert not transport.called
        print("P16_NATIVE_NO_TRANSPORT_OK")
finally:
    env.cr.rollback()
