import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class TrainingOrientation extends Interaction {
    static selector = "[data-orientation-form]";

    dynamicContent = {
        _root: { "t-on-submit": this.onSubmit },
        "[data-orientation-previous]": { "t-on-click": this.onPrevious },
        "[data-orientation-next]": { "t-on-click": this.onNext },
    };

    start() {
        this.steps = [...this.el.querySelectorAll("[data-orientation-step]")];
        this.progress = this.el.querySelector("[data-orientation-progress]");
        this.counter = this.el.querySelector("[data-orientation-count]");
        this.previous = this.el.querySelector("[data-orientation-previous]");
        this.next = this.el.querySelector("[data-orientation-next]");
        this.submit = this.el.querySelector("button[type=submit]");
        this.progress.hidden = this.steps.length === 1;
        this.showStep(0);
    }

    showStep(index, focus = false) {
        this.index = index;
        this.steps.forEach((step, stepIndex) => {
            step.hidden = stepIndex !== index;
            step.querySelector("select, input[type=radio]").required = stepIndex === index;
        });
        this.counter.textContent = index + 1;
        this.previous.hidden = index === 0;
        this.next.hidden = index === this.steps.length - 1;
        this.submit.hidden = !this.next.hidden;
        if (focus) {
            this.steps[index].focus();
        }
    }

    onPrevious() {
        this.showStep(this.index - 1, true);
    }

    onNext() {
        if (this.el.reportValidity()) {
            this.showStep(this.index + 1, true);
        }
    }

    onSubmit(event) {
        if (!this.next.hidden) {
            event.preventDefault();
            this.onNext();
        }
    }
}

registry.category("public.interactions").add("training_management_survey.orientation", TrainingOrientation);
