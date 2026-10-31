import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

// Full-page form responses announce the outcome without a separate UI framework.
export class TrainingFeedback extends Interaction {
    static selector = ".o_training_feedback";
    start() { this.el.focus(); }
}
registry.category("public.interactions").add("training_management.feedback", TrainingFeedback);
