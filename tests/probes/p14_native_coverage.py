"""Native Rating evidence on synthetic records, with rollback and no transport."""

import json
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.modules.module import get_module_path
from odoo.tests import new_test_user


def probe():
    learner = new_test_user(env, login="p14_fictional_learner", groups="base.group_portal")
    partner = env["res.partner"].create({"name": "Fictional P14 training customer"})
    rating = env["rating.rating"].create(
        {
            "res_model_id": env["ir.model"]._get("res.partner").id,
            "res_id": partner.id,
            "partner_id": learner.partner_id.id,
            "rating": 5,
            "feedback": "Fictional first version",
        }
    )
    assert rating.access_token and rating.rated_on
    try:
        rating.with_user(learner).read(["feedback"])
    except AccessError:
        pass
    else:
        raise AssertionError("Expected no direct portal ORM grant")
    # Rating permits a resource without any training enrollment or attendance.
    assert rating.res_model == "res.partner"
    assert "training_enrollment_id" not in rating._fields
    token = rating.access_token
    rating.write({"feedback": "Fictional overwritten version"})
    assert rating.feedback == "Fictional overwritten version" and rating.access_token == token
    rating.reset()
    assert not rating.feedback and rating.rating == 0 and rating.access_token != token
    assert get_module_path("portal_rating", display_warning=False)
    assert not get_module_path("website_rating", display_warning=False)
    print(
        "P14_NATIVE_COVERAGE "
        + json.dumps(
            {
                "rating_without_training_participation": True,
                "portal_direct_orm_read_denied": True,
                "feedback_mutable_without_versioned_consent": True,
                "reset_clears_feedback_and_rotates_token": True,
                "portal_rating_present_website_rating_absent": True,
            },
            sort_keys=True,
        )
    )


try:
    with patch.object(
        type(env["ir.mail_server"]), "send_email", side_effect=AssertionError("Transport forbidden in P14 probe")
    ) as transport:
        probe()
        assert not transport.called
        print("P14_NATIVE_NO_TRANSPORT_OK")
finally:
    env.cr.rollback()
