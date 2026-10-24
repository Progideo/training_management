"""Actual independent transactions: anonymous replay, revocation and closure race."""

from psycopg2.errors import SerializationFailure
from odoo import api
from odoo.exceptions import AccessError, LockError, ValidationError

if env.cr.dbname != "tm_s01_test_s021_s052":
    raise RuntimeError("Disposable S09.2 fixture database only")
campaign = env.ref("training_management_test.s092_concurrent_campaign")
question = env.ref("training_management_test.s092_question")
actor = env.ref("training_management_test.s052_coordinator")
user = env.ref("training_management_test.s092_user_0")
second_user = env.ref("training_management_test.s092_user_1")
third_user = env.ref("training_management_test.s092_user_2")
campaign_id, question_id, choices = campaign.id, question.id, question.suggested_answer_ids[:1].ids
context = {"allowed_company_ids": campaign.company_id.ids}
env.cr.commit()  # Release synthetic fixture locks.
with env.registry.cursor() as first, env.registry.cursor() as second:
    one, two = [api.Environment(c, user.id, context)["training.feedback.service"] for c in (first, second)]
    one._submit(campaign_id, "participant", {question_id: choices})
    try:
        two._submit(campaign_id, "participant", {question_id: choices})
    except LockError:
        pass
    else:
        raise AssertionError("Concurrent anonymous submission ignored the held delivery lock")
    first.commit()
    try:
        two._submit(campaign_id, "participant", {question_id: choices})
    except SerializationFailure:
        second.rollback()
    else:
        raise AssertionError("Stale transaction did not require a retry")
with env.registry.cursor() as retry:
    scoped = api.Environment(retry, user.id, context)
    scoped["training.feedback.service"]._submit(campaign_id, "participant", {question_id: choices})
    assert scoped["survey.user_input"].sudo().search_count([("training_feedback_campaign_id", "=", campaign_id)]) == 1
    retry.commit()
with env.registry.cursor() as revoke:
    row = api.Environment(revoke, actor.id, context)["training.feedback.recipient"].search(
        [("campaign_id", "=", campaign_id), ("user_id", "=", second_user.id)]
    )
    row.write({"active": False, "exclusion_reason": "Fictional concurrent withdrawal"})
    revoke.commit()
with env.registry.cursor() as after:
    try:
        api.Environment(after, second_user.id, context)["training.feedback.service"]._submit(
            campaign_id, "participant", {question_id: choices}
        )
    except AccessError:
        pass
    else:
        raise AssertionError("Withdrawn recipient submitted")
with env.registry.cursor() as close, env.registry.cursor() as submit:
    closing = api.Environment(close, actor.id, context)["training.feedback.campaign"].browse(campaign_id)
    closing.action_close()
    try:
        api.Environment(submit, third_user.id, context)["training.feedback.service"]._submit(
            campaign_id, "participant", {question_id: choices}
        )
    except LockError:
        pass
    else:
        raise AssertionError("Submission raced past a closing campaign")
    close.commit()
with env.registry.cursor() as after:
    scoped = api.Environment(after, third_user.id, context)
    try:
        scoped["training.feedback.service"]._submit(campaign_id, "participant", {question_id: choices})
    except ValidationError:
        pass
    else:
        raise AssertionError("Closed campaign accepted a late response")
    assert scoped["training.feedback.campaign"].sudo().browse(campaign_id).snapshot == {"insufficient": True}
print("S092_CONCURRENCY_OK: one anonymous response, stale retry, revocation and frozen closure")
