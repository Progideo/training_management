import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

// The countdown is survey.SurveyTimer, unmodified. This interaction adds P07
// navigation and per-change saves to the native survey question widgets.
export class TrainingExam extends Interaction {
    static selector = ".o_training_exam";
    dynamicContent = {
        ".o_survey_form_choice_item, .tm_review": { "t-on-change": this.onChange },
        ".tm_clear": { "t-on-click": this.onClear },
        ".tm_question_link": { "t-on-click": this.onNavigate },
        ".tm_previous": { "t-on-click": () => this.show(this.current - 1) },
        ".tm_next": { "t-on-click": () => this.show(this.current + 1) },
        ".tm_summary": { "t-on-click": this.onSummary },
        ".tm_submit": { "t-on-click": this.onSubmit },
        ".o_survey_timer": { "t-on-time_up": this.onExpired },
        _window: { "t-on-beforeunload": this.beforeUnload },
    };
    setup() {
        this.questions = [...this.el.querySelectorAll(".tm_question")];
        this.queue = Promise.resolve();
        this.failed = false;
        this.pending = 0;
        this.ending = false;
        this.current = 0;
    }
    start() {
        this.show(0, false);
        this.updatePalette();
    }
    status(text, error = false) {
        const status = this.el.querySelector(".tm_save_status");
        status.textContent = text;
        status.classList.toggle("alert-danger", error);
        status.classList.toggle("alert-info", !error);
    }
    async send(values) {
        const data = new FormData();
        data.set("csrf_token", this.el.querySelector("[name=csrf_token]").value);
        for (const [key, value] of Object.entries(values)) {
            data.set(key, value);
        }
        const response = await fetch(this.el.dataset.endpoint, { method: "POST", body: data });
        if (!response.ok || !response.headers.get("Content-Type")?.includes("application/json")) {
            throw new Error("Exam operation refused");
        }
        return response.json();
    }
    onChange(ev) {
        this.save(ev.target.closest(".tm_question"));
    }
    onClear(ev) {
        const question = ev.target.closest(".tm_question");
        question.querySelectorAll(".o_survey_form_choice_item").forEach((input) => { input.checked = false; });
        this.save(question);
    }
    save(question) {
        if (this.ending || this.failed) {
            this.status(_t("Not saved. Reload to recover answers already received by the server."), true);
            return;
        }
        // Capture this change before queuing: later clicks cannot alter its payload.
        const values = {
            question: question.dataset.question,
            choices: JSON.stringify([...question.querySelectorAll(".o_survey_form_choice_item:checked")].map((i) => Number(i.value))),
            marked: question.querySelector(".tm_review").checked ? "1" : "0",
        };
        this.pending++;
        this.status(_t("Saving…"));
        this.queue = this.queue.then(async () => {
            if (this.failed) { return; }
            try {
                const result = await this.send(values);
                if (result.done) { window.location.reload(); return; }
                this.pending--;
                if (!this.pending) { this.status(_t("Saved on the server.")); }
            } catch {
                this.failed = true;
                this.status(_t("Not saved. Check your connection. Reload to recover only answers already received by the server."), true);
            }
        });
        this.updatePalette();
    }
    beforeUnload(ev) {
        if (this.pending || this.failed) { ev.preventDefault(); ev.returnValue = ""; }
    }
    show(index, focus = true) {
        this.current = Math.max(0, Math.min(this.questions.length - 1, index));
        this.questions.forEach((q, i) => { q.hidden = i !== this.current; });
        if (focus) { this.questions[this.current]?.querySelector("legend").focus(); }
        this.updatePalette();
    }
    onNavigate(ev) {
        this.show(this.questions.findIndex((q) => q.dataset.question === ev.currentTarget.dataset.question));
    }
    updatePalette() {
        this.el.querySelectorAll(".tm_question_link").forEach((button, index) => {
            const question = this.questions[index];
            const answered = !!question.querySelector(".o_survey_form_choice_item:checked");
            const review = question.querySelector(".tm_review").checked;
            button.querySelector(".tm_question_state").textContent = (answered ? " ✓" : " ○") + (review ? " ⚑" : "");
            button.setAttribute("aria-label", _t("Question %s", index + 1) + ": " + (answered ? _t("Answered") : _t("Unanswered")) + (review ? ", " + _t("Marked for review") : ""));
            button.setAttribute("aria-current", index === this.current ? "step" : "false");
        });
    }
    onSummary() {
        const answered = this.questions.filter((q) => q.querySelector(".o_survey_form_choice_item:checked")).length;
        const marked = this.questions.filter((q) => q.querySelector(".tm_review:checked")).length;
        this.el.querySelector(".tm_recap_text").textContent = _t("Answered: %s / %s. Marked for review: %s.", answered, this.questions.length, marked);
        this.el.querySelector(".tm_recap").hidden = false;
        this.el.querySelector(".tm_submit").focus();
    }
    async onSubmit() {
        if (this.ending) { return; }
        await this.queue;
        if (this.failed || this.pending) {
            this.status(_t("Submission blocked: some answers are not saved. Reload and verify your saved answers."), true);
            return;
        }
        this.ending = true;
        try {
            await this.send({ kind: "submit" });
            window.location.reload();
        } catch {
            this.ending = false;
            this.status(_t("Submission not confirmed. Check your connection and retry."), true);
        }
    }
    async onExpired() {
        // A native timer event prompts the server; only the server decides expiry.
        // Pending unsent answers are not replayed after the deadline.
        try {
            const result = await this.send({ kind: "status" });
            if (result.done) { this.pending = 0; this.failed = false; }
            window.location.reload();
        } catch {
            this.status(_t("Time elapsed. Only answers received before the server deadline are retained. Reconnect to see the result."), true);
        }
    }
}
registry.category("public.interactions").add("training_management_survey.exam", TrainingExam);
