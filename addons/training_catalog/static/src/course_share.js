import { Component, t, useProps } from "@odoo/owl";
import { CopyButton } from "@web/core/copy_button/copy_button";
import { registry } from "@web/core/registry";

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
                icon: "fa-linkedin",
                href: `https://www.linkedin.com/sharing/share-offsite/?url=${url}`,
            },
            {
                key: "facebook",
                label: "Facebook",
                icon: "fa-facebook",
                href: `https://www.facebook.com/sharer/sharer.php?u=${url}`,
            },
            {
                key: "x",
                label: "X",
                icon: "fa-twitter",
                href: `https://twitter.com/intent/tweet?url=${url}&text=${text}`,
            },
            { key: "whatsapp", label: "WhatsApp", icon: "fa-whatsapp", href: this.props.whatsapp },
            { key: "email", label: "E-mail", icon: "fa-envelope", href: this.props.email, local: true },
        ];
    }
}

registry.category("public_components").add("training_catalog.CourseShare", CourseShare);
