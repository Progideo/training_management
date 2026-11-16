import { Component, t, useProps } from "@odoo/owl";
import { CopyButton } from "@web/core/copy_button/copy_button";
import { Dialog } from "@web/core/dialog/dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class CourseShareDialog extends Component {
    static template = "training_catalog.CourseShareDialog";
    static components = { CopyButton, Dialog };
    props = useProps({
        close: t.function(),
        url: t.string(),
        email: t.string(),
        whatsapp: t.string(),
        title: t.string(),
        copyText: t.string(),
        copied: t.string(),
    });
}

class CourseShare extends Component {
    static template = "training_catalog.CourseShare";
    props = useProps({
        url: t.string(), email: t.string(), whatsapp: t.string(),
        title: t.string(), copyText: t.string(), copied: t.string(),
    });

    setup() {
        this.dialog = useService("dialog");
    }

    share() {
        this.dialog.add(CourseShareDialog, { ...this.props });
    }
}

registry.category("public_components").add("training_catalog.CourseShare", CourseShare);
