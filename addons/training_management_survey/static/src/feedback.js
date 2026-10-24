import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class TrainingFeedbackMessage extends Interaction {
    static selector = "#feedback-message";
    start() {
        this.el.focus();
    }
}
registry.category("public.interactions").add("training_management_survey.feedback_message", TrainingFeedbackMessage);
