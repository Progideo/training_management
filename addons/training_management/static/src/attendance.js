import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";

export class TrainingAttendance extends Interaction {
    static selector = ".o_training_attendance_form";
    dynamicContent = {
        "select[name=attendance]": { "t-on-change": this.updateWording },
    };
    start() { this.updateWording(); }
    updateWording() {
        const label = this.el.querySelector(".tm_attendance_wording");
        if (label) {
            label.textContent = this.el.querySelector("[name=attendance]").value === "absent"
                ? label.dataset.absent : label.dataset.present;
        }
    }
}
registry.category("public.interactions").add("training_management.attendance", TrainingAttendance);

function openAttendanceTarget() {
    const target = document.getElementById(decodeURIComponent(window.location.hash.slice(1)));
    if (target?.classList.contains("tm_attendance_details")) {
        target.open = true;
    }
}
window.addEventListener("hashchange", openAttendanceTarget);
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", openAttendanceTarget);
} else {
    openAttendanceTarget();
}
