import { Component, t, useProps } from "@odoo/owl";
import { CopyButton } from "@web/core/copy_button/copy_button";
import { registry } from "@web/core/registry";

// Brand marks drawn inline (24 x 24): the website bundle has no icon font for them.
const ICONS = {
    linkedin:
        "M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.14 1.45-2.14 2.94v5.67H9.35V9h3.41v1.56h.05c.48-.9 1.64-1.85 3.37-1.85 3.6 0 4.27 2.37 4.27 5.46v6.28zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zM7.12 20.45H3.56V9h3.56v11.45zM22.22 0H1.77C.79 0 0 .77 0 1.73v20.54C0 23.23.79 24 1.77 24h20.45c.98 0 1.78-.77 1.78-1.73V1.73C24 .77 23.2 0 22.22 0z",
    facebook:
        "M24 12.07C24 5.44 18.63.07 12 .07S0 5.44 0 12.07c0 5.99 4.39 10.95 10.13 11.85v-8.38H7.08v-3.47h3.05V9.43c0-3.01 1.79-4.67 4.53-4.67 1.31 0 2.69.24 2.69.24v2.95h-1.51c-1.49 0-1.96.93-1.96 1.87v2.25h3.33l-.53 3.47h-2.8v8.38C19.61 23.03 24 18.06 24 12.07z",
    x: "M18.9 1.15h3.68l-8.04 9.19L24 22.85h-7.41l-5.8-7.58-6.64 7.58H.47l8.6-9.83L0 1.15h7.59l5.25 6.93zm-1.29 19.49h2.04L6.49 3.24H4.3z",
    whatsapp:
        "M17.47 14.38c-.3-.15-1.76-.87-2.03-.97-.27-.1-.47-.15-.67.15-.2.3-.77.97-.94 1.16-.17.2-.35.22-.64.08-.3-.15-1.26-.47-2.39-1.48-.88-.79-1.48-1.76-1.65-2.06-.17-.3-.02-.46.13-.61.13-.13.3-.35.45-.52.15-.17.2-.3.3-.5.1-.2.05-.37-.03-.52-.07-.15-.67-1.61-.92-2.21-.24-.58-.49-.5-.67-.51h-.57c-.2 0-.52.07-.79.37-.27.3-1.04 1.02-1.04 2.48s1.07 2.88 1.21 3.07c.15.2 2.1 3.2 5.08 4.49.71.31 1.26.49 1.7.63.71.23 1.36.2 1.87.12.57-.09 1.76-.72 2.01-1.41.25-.7.25-1.29.17-1.41-.07-.13-.27-.2-.57-.35zm-5.42 7.4h-.01a9.87 9.87 0 0 1-5.03-1.38l-.36-.21-3.74.98 1-3.65-.24-.37a9.86 9.86 0 0 1-1.51-5.26c0-5.45 4.44-9.88 9.89-9.88 2.64 0 5.12 1.03 6.99 2.9a9.83 9.83 0 0 1 2.89 6.99c0 5.45-4.44 9.88-9.88 9.88zm8.41-18.3A11.82 11.82 0 0 0 12.05 0C5.5 0 .16 5.34.16 11.89c0 2.1.55 4.14 1.59 5.95L.06 24l6.3-1.65a11.88 11.88 0 0 0 5.68 1.45h.01c6.55 0 11.89-5.34 11.89-11.89 0-3.18-1.24-6.16-3.48-8.41z",
    email: "M2 4h20a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm0 2v.4l10 6.25L22 6.4V6H2zm20 2.75-9.47 5.92a1 1 0 0 1-1.06 0L2 8.75V18h20V8.75z",
};

/**
 * Share block of the public course page: the page address, ready to copy, and
 * links to the main social networks. Share addresses are built in the browser
 * from the page address.
 */
class CourseShare extends Component {
    static template = "training_catalog.CourseShare";
    static components = { CopyButton };
    props = useProps({
        url: t.string(),
        email: t.string(),
        whatsapp: t.string(),
        title: t.string(),
        copyText: t.string(),
        copied: t.string(),
    });

    get name() {
        const query = this.props.email.split("?")[1] || "";
        return new URLSearchParams(query).get("subject") || document.title;
    }

    get networks() {
        const url = encodeURIComponent(this.props.url);
        const text = encodeURIComponent(this.name);
        return [
            {
                key: "linkedin",
                label: "LinkedIn",
                path: ICONS.linkedin,
                href: `https://www.linkedin.com/sharing/share-offsite/?url=${url}`,
            },
            {
                key: "facebook",
                label: "Facebook",
                path: ICONS.facebook,
                href: `https://www.facebook.com/sharer/sharer.php?u=${url}`,
            },
            {
                key: "x",
                label: "X",
                path: ICONS.x,
                href: `https://twitter.com/intent/tweet?url=${url}&text=${text}`,
            },
            { key: "whatsapp", label: "WhatsApp", path: ICONS.whatsapp, href: this.props.whatsapp },
            { key: "email", label: "E-mail", path: ICONS.email, href: this.props.email, local: true },
        ];
    }
}

registry.category("public_components").add("training_catalog.CourseShare", CourseShare);
