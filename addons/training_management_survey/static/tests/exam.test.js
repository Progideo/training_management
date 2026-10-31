import { describe, expect, test } from "@odoo/hoot";
import { click, queryOne } from "@odoo/hoot-dom";
import { patchWithCleanup } from "@web/../tests/web_test_helpers";
import { startInteraction } from "@web/../tests/public/helpers";
import { TrainingExam } from "@training_management_survey/exam";

const fixture = `
    <div class="o_training_exam" data-endpoint="/fictional-exam/save">
        <input name="csrf_token" value="fictional"/>
        <p class="tm_save_status"></p><button class="tm_retry" hidden>Retry</button>
        <button class="tm_question_link" data-question="1"><span class="tm_question_state"></span></button>
        <fieldset class="tm_question" data-question="1"><legend tabindex="-1">Question</legend>
            <input class="o_survey_form_choice_item" type="checkbox" value="11"/>
            <input class="tm_review" type="checkbox"/><button class="tm_clear">Clear</button>
            <p class="tm_question_save_state"></p>
        </fieldset>
        <button class="tm_summary">Review</button>
        <div class="tm_recap" hidden><p class="tm_recap_text"></p><button class="tm_submit">Submit</button></div>
        <span class="o_survey_timer"></span>
    </div>`;

async function runner(send) {
    patchWithCleanup(TrainingExam.prototype, {
        async send(values) { return send(values); },
        finished() { this.freeze(true); this.unsaved.clear(); this.failed = false; this.resultShown = true; },
    });
    const { core } = await startInteraction(TrainingExam, fixture);
    return core.interactions[0].interaction;
}

describe("training exam reconnection", () => {
    test("failed save retains later edits; explicit retry acknowledges the latest answer", async () => {
        let offline = true;
        const received = [];
        const exam = await runner(async (values) => {
            if (offline) { throw new TypeError("Fictional network interruption"); }
            received.push(values);
            return { done: false };
        });
        await click(".o_survey_form_choice_item");
        await exam.queue;
        expect(exam.failed).toBe(true);
        expect(".tm_retry").toBeVisible();
        await click(".tm_clear");
        await click(".tm_review");
        await exam.queue;
        expect(exam.unsaved.size).toBe(1);
        offline = false;
        await exam.onRetry();
        expect(received.map((r) => r.kind || "save")).toEqual(["status", "save"]);
        expect(received[1].choices).toBe("[]");
        expect(received[1].marked).toBe("1");
        expect(exam.unsaved.size).toBe(0);
        expect(exam.failed).toBe(false);
        expect(".tm_retry").not.toBeVisible();
    });

    test("a slow acknowledgement cannot discard a newer answer", async () => {
        let acknowledge;
        const received = [];
        const exam = await runner((values) => {
            received.push(values);
            if (received.length === 1) { return new Promise((resolve) => { acknowledge = resolve; }); }
            return Promise.resolve({ done: false });
        });
        await click(".o_survey_form_choice_item");
        await click(".tm_clear");
        acknowledge({ done: false });
        await exam.queue;
        expect(received.map((r) => r.choices)).toEqual(["[11]", "[]"]);
        expect(exam.unsaved.size).toBe(0);
    });

    test("submission waits for saved answers and blocks while offline", async () => {
        let offline = true;
        const received = [];
        const exam = await runner(async (values) => {
            if (offline) { throw new TypeError("Fictional network interruption"); }
            received.push(values.kind || "save");
            return { done: values.kind === "submit" };
        });
        await click(".o_survey_form_choice_item");
        await exam.queue;
        await exam.onSubmit();
        expect(exam.resultShown).toBe(undefined);
        expect(queryOne(".tm_question").disabled).toBe(false);
        offline = false;
        await exam.onRetry();
        await exam.onSubmit();
        expect(received).toEqual(["status", "save", "submit"]);
        expect(exam.resultShown).toBe(true);
    });

    test("server expiry on reconnection discards unsent answers without replay", async () => {
        let offline = true;
        const received = [];
        const exam = await runner(async (values) => {
            if (offline) { throw new TypeError("Fictional network interruption"); }
            received.push(values.kind || "save");
            return { done: true };
        });
        await click(".o_survey_form_choice_item");
        await exam.queue;
        offline = false;
        await exam.onRetry();
        expect(received).toEqual(["status"]);
        expect(exam.unsaved.size).toBe(0);
        expect(exam.resultShown).toBe(true);
    });
});
